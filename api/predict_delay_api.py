"""
Bus Delay Prediction API

現在時刻から3時間先のバス遅延を予測するAPIファイル。
学習済みモデル(.h5)を使用して、特定路線の遅延情報を取得します。
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import tensorflow as tf
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.append(str(Path(__file__).parent.parent))

from src.data_connection import DatabaseConnector, GTFSDataRetrieverV2 as GTFSDataRetriever, WeatherDataRetriever
from src.data_preprocessing import DataPreprocessor, DataAggregator, FeatureEngineer
from src.timeseries_processing import SequenceCreator, DataSplitter, DataStandardizer
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DelayPredictionAPI:
    """バス遅延予測API"""

    # ノートブックと同じ特徴量グループ定義
    FEATURE_GROUPS = {
        'temporal': ['hour_sin', 'hour_cos', 'day_sin', 'day_cos', 'is_peak_hour', 'is_weekend', 'arrival_delay'],
        'weather': ['weather_sunny', 'weather_cloudy', 'weather_rainy', 'temp', 'precipitation'],
        'target': ['arrival_delay']
    }

    # シーケンスパラメータ（ノートブックと同じ）
    INPUT_TIMESTEPS = 8
    OUTPUT_TIMESTEPS = 3

    def __init__(self, model_path: str = 'best_delay_model.h5'):
        """
        Args:
            model_path: 学習済みモデルのパス
        """
        self.model_path = model_path
        self.model = None
        self.standardizer = None
        self.db_connector = None
        self.gtfs_retriever = None
        self.weather_retriever = None
        self.preprocessor = None
        self.aggregator = None
        self.feature_engineer = None
        self.sequence_creator = None

        self._initialize_components()

    def _initialize_components(self):
        """コンポーネントの初期化"""
        logger.info("Initializing API components...")

        # モデル読み込み
        try:
            # カスタムオブジェクトを定義してモデルを読み込み
            custom_objects = {
                'mse': tf.keras.metrics.MeanSquaredError(),
                'keras.metrics.mse': tf.keras.metrics.MeanSquaredError()
            }
            self.model = tf.keras.models.load_model(
                self.model_path,
                custom_objects=custom_objects,
                compile=False  # コンパイルをスキップして読み込みの問題を回避
            )
            
            # モデルを手動でコンパイル
            self.model.compile(
                optimizer='adam',
                loss='mse',
                metrics=['mse']
            )
            
            logger.info(f"Model loaded from {self.model_path}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise

        # データベース接続
        self.db_connector = DatabaseConnector()
        if not self.db_connector.test_connection():
            raise ConnectionError("Failed to connect to database")

        # データ取得用コンポーネント
        self.gtfs_retriever = GTFSDataRetriever(self.db_connector)
        self.weather_retriever = WeatherDataRetriever(self.db_connector)

        # 前処理用コンポーネント
        self.preprocessor = DataPreprocessor()
        self.aggregator = DataAggregator()
        self.feature_engineer = FeatureEngineer()

        # シーケンス作成
        self.sequence_creator = SequenceCreator(
            input_timesteps=self.INPUT_TIMESTEPS,
            output_timesteps=self.OUTPUT_TIMESTEPS,
            feature_groups=self.FEATURE_GROUPS
        )

        # 標準化器（新規作成 - 予測時にfit_transformする）
        self.standardizer = DataStandardizer()

        logger.info("All components initialized successfully")

    def predict_delay(
        self,
        route_id: str,
        direction_id: int = 0,
        lookback_days: int = 7
    ) -> Dict:
        """
        特定路線の現在から3時間先の遅延を予測

        Args:
            route_id: 路線ID
            direction_id: 方向ID (0 or 1)
            lookback_days: 過去データを取得する日数（デフォルト7日間）

        Returns:
            予測結果の辞書
            {
                'route_id': 路線ID,
                'direction_id': 方向ID,
                'current_time': 現在時刻,
                'predictions': [
                    {'time': '予測時刻', 'delay_minutes': 遅延分数},
                    ...
                ]
            }
        """
        logger.info(f"Predicting delay for route {route_id}, direction {direction_id}")

        # 1. データ取得
        gtfs_data, weather_data = self._retrieve_recent_data(
            route_id, direction_id, lookback_days
        )

        if len(gtfs_data) == 0:
            raise ValueError(f"No GTFS data found for route {route_id}")

        # 2. データ前処理
        processed_data = self._preprocess_data(gtfs_data, weather_data)

        if len(processed_data) < self.INPUT_TIMESTEPS:
            raise ValueError(
                f"Insufficient data: need {self.INPUT_TIMESTEPS} timesteps, "
                f"got {len(processed_data)}"
            )

        # 3. シーケンス作成（最新のINPUT_TIMESTEPSのみ使用）
        X_seq = self._create_prediction_sequence(processed_data)

        # 4. 予測実行
        predictions = self._make_prediction(X_seq)

        # 5. 結果フォーマット
        result = self._format_prediction_result(
            route_id, direction_id, processed_data, predictions
        )

        logger.info(f"Prediction completed: {len(result['predictions'])} timesteps")
        return result

    def _retrieve_recent_data(
        self,
        route_id: str,
        direction_id: int,
        lookback_days: int
    ) -> tuple:
        """過去データを取得"""
        logger.info(f"Retrieving data for the past {lookback_days} days...")

        # 開始日を計算（lookback_days日前）
        start_date = (datetime.now() - timedelta(days=lookback_days)).strftime('%Y%m%d')

        # GTFSデータ取得
        gtfs_data = self.gtfs_retriever.get_gtfs_data(
            route_id=[route_id],
            start_date=start_date
        )

        # 特定の方向のみフィルタ
        gtfs_data = gtfs_data[gtfs_data['direction_id'] == direction_id].copy()

        # 天気データ取得
        weather_data = self.weather_retriever.get_weather_data()

        logger.info(f"Retrieved {len(gtfs_data)} GTFS records, {len(weather_data)} weather records")

        return gtfs_data, weather_data

    def _preprocess_data(self, gtfs_data: pd.DataFrame, weather_data: pd.DataFrame) -> pd.DataFrame:
        """データの前処理とマージ"""
        logger.info("Preprocessing data...")

        # 欠損値削除
        filtered_gtfs = self.preprocessor.delete_missing_values(
            gtfs_data, ['travel_time_duration', 'travel_time_raw_seconds']
        )

        # 外れ値削除
        filtered_gtfs = self.preprocessor.clean_gtfs_with_asymmetric_thresholds(filtered_gtfs)
        filtered_gtfs = filtered_gtfs[~filtered_gtfs['should_exclude']].copy()

        # 統計的特徴量生成
        processed_gtfs = self.feature_engineer.generate_statistical_features(filtered_gtfs)

        # データ集約
        delay_aggregated = self.aggregator.create_delay_aggregation(processed_gtfs)
        weather_aggregated = self.aggregator.create_weather_aggregation(weather_data)

        # 時間特徴量生成
        delay_features = self.feature_engineer.generate_time_features(delay_aggregated)

        # マージ
        merged_data = self.feature_engineer.merge_features(delay_features, weather_aggregated)

        # 時系列順にソート（time_bucketを使用）
        merged_data = merged_data.sort_values('time_bucket').reset_index(drop=True)
        
        # datetime_60カラムとして追加（後続の処理で使用）
        merged_data['datetime_60'] = merged_data['time_bucket']

        logger.info(f"Preprocessed data: {len(merged_data)} timesteps")

        return merged_data

    def _create_prediction_sequence(self, data: pd.DataFrame) -> np.ndarray:
        """予測用シーケンスを作成（最新データのみ）"""
        logger.info("Creating prediction sequence...")

        # 最新のINPUT_TIMESTEPS分のデータを取得
        recent_data = data.tail(self.INPUT_TIMESTEPS).copy()

        # モデルが期待する特徴量（7つ）を明示的に指定
        # モデルの入力形状 (None, 8, 1, 7, 1) に合わせて
        feature_cols = [
            'hour_sin', 'hour_cos', 'day_sin', 'day_cos', 
            'is_peak_hour', 'is_weekend', 'arrival_delay'
        ]

        # 必要な特徴量の存在確認
        missing_cols = [col for col in feature_cols if col not in recent_data.columns]
        if missing_cols:
            raise ValueError(f"Missing required features: {missing_cols}")

        # numpy配列に変換
        X = recent_data[feature_cols].values

        # (1, timesteps, features)の形状に変更
        X = X.reshape(1, self.INPUT_TIMESTEPS, -1)

        # 標準化（予測データでfit_transform）
        X_scaled = self.standardizer.fit_transform_features(X)

        # ConvLSTM用にreshape: (samples, timesteps, height, width, channels)
        actual_feature_count = X_scaled.shape[2]
        splitter = DataSplitter()
        X_reshaped = splitter.reshape_for_convlstm(
            X_scaled, target_height=1, target_width=actual_feature_count
        )

        logger.info(f"Sequence shape: {X_reshaped.shape}")

        return X_reshaped

    def _make_prediction(self, X_seq: np.ndarray) -> np.ndarray:
        """モデルで予測実行"""
        logger.info("Making prediction...")

        predictions = self.model.predict(X_seq, verbose=0)

        logger.info(f"Prediction shape: {predictions.shape}")

        return predictions

    def _format_prediction_result(
        self,
        route_id: str,
        direction_id: int,
        data: pd.DataFrame,
        predictions: np.ndarray
    ) -> Dict:
        """予測結果をフォーマット"""

        # 最新の時刻を取得
        latest_time = pd.to_datetime(data['datetime_60'].iloc[-1])
        current_time = datetime.now()

        # 予測結果（OUTPUT_TIMESTEPS=3）を1時間ごとに展開
        prediction_list = []
        for i in range(self.OUTPUT_TIMESTEPS):
            pred_time = latest_time + timedelta(hours=i+1)
            delay_seconds = float(predictions[0, i])
            delay_minutes = delay_seconds / 60.0

            prediction_list.append({
                'time': pred_time.strftime('%Y-%m-%d %H:%M:%S'),
                'delay_seconds': round(delay_seconds, 2),
                'delay_minutes': round(delay_minutes, 2)
            })

        result = {
            'route_id': route_id,
            'direction_id': direction_id,
            'current_time': current_time.strftime('%Y-%m-%d %H:%M:%S'),
            'latest_data_time': latest_time.strftime('%Y-%m-%d %H:%M:%S'),
            'predictions': prediction_list
        }

        return result


def predict_route_delay(
    route_id: str,
    direction_id: int = 0,
    model_path: str = 'delay_prediction_model.h5',
    lookback_days: int = 7
) -> Dict:
    """
    指定路線の遅延を予測する関数（簡易インターフェース）

    Args:
        route_id: 路線ID（例: '6618'）
        direction_id: 方向ID（0 or 1）
        model_path: モデルファイルパス
        lookback_days: 過去データ取得日数

    Returns:
        予測結果の辞書
    """
    api = DelayPredictionAPI(model_path=model_path)
    return api.predict_delay(route_id, direction_id, lookback_days)


def main():
    """使用例"""
    import json

    # 使用例: 路線6618の遅延予測
    route_id = '6618'
    direction_id = 0

    try:
        result = predict_route_delay(
            route_id=route_id,
            direction_id=direction_id,
            model_path='files/model/best_delay_model.h5',
            lookback_days=7
        )

        print("=" * 60)
        print(f"Bus Delay Prediction for Route {route_id} (Direction {direction_id})")
        print("=" * 60)
        print(f"Current Time: {result['current_time']}")
        print(f"Latest Data Time: {result['latest_data_time']}")
        print("\nPredictions for next 3 hours:")
        print("-" * 60)

        for pred in result['predictions']:
            print(f"Time: {pred['time']}")
            print(f"  Delay: {pred['delay_minutes']:.2f} minutes ({pred['delay_seconds']:.2f} seconds)")
            print()

        # JSON形式で保存
        output_path = f'prediction_route_{route_id}_dir_{direction_id}.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"Result saved to: {output_path}")

    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
