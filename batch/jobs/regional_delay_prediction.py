#!/usr/bin/env python3
"""
Regional Delay Prediction Job

Metro Vancouver地域内の全地域についてバス遅延予測を実行し、
結果をデータベースに保存します。
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import time
import numpy as np
import pandas as pd
import tensorflow as tf
import pytz

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from batch.config.database_connector import DatabaseConnector
from batch.repositories.regional_delay_repository import RegionalDelayRepository
from batch.timeseries_processing import SequenceCreator, DataSplitter, DataStandardizer
from batch.config.settings import config
from batch.jobs.base_job import DataProcessingJob
from batch.utils.error_handler import DataProcessingError


class RegionalDelayPredictionJob(DataProcessingJob):
    """地域遅延予測ジョブ"""

    def __init__(
        self,
        model_path: Optional[str] = None,
        input_timesteps: Optional[int] = None,
        output_timesteps: Optional[int] = None,
        feature_groups: Optional[Dict] = None
    ):
        """
        初期化

        Args:
            model_path: 学習済みモデルのパス（Noneの場合は設定から取得）
            input_timesteps: 入力時系列長（Noneの場合は設定から取得）
            output_timesteps: 出力時系列長（Noneの場合は設定から取得）
            feature_groups: 特徴量グループ定義
        """
        super().__init__(job_name="RegionalDelayPredictionJob")

        self.model_path = model_path or str(config.prediction.get_model_path())
        self.input_timesteps = input_timesteps if input_timesteps is not None else config.prediction.input_timesteps
        self.output_timesteps = output_timesteps if output_timesteps is not None else config.prediction.output_timesteps

        # 特徴量グループのデフォルト設定
        if feature_groups is None:
            self.feature_groups = {
                'temporal': [
                    'hour_sin', 'hour_cos', 'day_sin', 'day_cos',
                    'is_peak_hour', 'is_weekend', 'arrival_delay'
                ],
                'region': [
                    'direction_id', 'line_direction_link_order',
                    'delay_mean_by_route_hour', 'distance_from_downtown_km'
                ],
                'weather': ['humidex', 'wind_speed', 'weather_rainy'],
                'target': ['arrival_delay']
            }
        else:
            self.feature_groups = feature_groups

        # データベース接続
        self.db_connector = DatabaseConnector()
        self.repository = RegionalDelayRepository(self.db_connector)

        # コンポーネント初期化
        self.sequence_creator = SequenceCreator(
            input_timesteps=self.input_timesteps,
            output_timesteps=self.output_timesteps,
            feature_groups=self.feature_groups
        )
        self.splitter = DataSplitter()
        self.standardizer = DataStandardizer()

        # モデル読み込み
        self.model = self._load_model()

        self.logger.info("RegionalDelayPredictionJob initialized successfully")

    def _load_model(self) -> tf.keras.Model:
        """モデルをロード"""
        try:
            self.logger.info(f"Loading model from: {self.model_path}")

            custom_objects = {
                'mse': tf.keras.metrics.MeanSquaredError(),
                'keras.metrics.mse': tf.keras.metrics.MeanSquaredError()
            }

            model = tf.keras.models.load_model(
                self.model_path,
                custom_objects=custom_objects,
                compile=False
            )

            # モデルを手動でコンパイル
            model.compile(optimizer='adam', loss='mse', metrics=['mse'])

            self.logger.info("Model loaded and compiled successfully")
            return model

        except Exception as e:
            self.logger.error(f"Failed to load model: {e}")
            raise DataProcessingError(f"Failed to load model from {self.model_path}") from e

    def get_all_regions(self) -> List[str]:
        """全地域IDを取得"""
        query = "SELECT region_id FROM gtfs_static.regions ORDER BY region_id"
        df = self.db_connector.read_sql(query)
        regions = df['region_id'].tolist() if df is not None and not df.empty else []
        self.logger.info(f"Found {len(regions)} regions: {regions}")
        return regions

    def predict_region(self, region_id: str) -> Optional[Dict[str, Any]]:
        """
        特定地域の遅延予測を実行

        Args:
            region_id: 地域ID

        Returns:
            予測結果を含む辞書 {'predictions': DataFrame, 'metadata': Dict}
        """
        start_time = time.time()
        self.logger.info(f"Starting prediction for region: {region_id}")

        try:
            # 1. データ取得（過去8時間）
            self.logger.info(f"  [1/6] Fetching data for {region_id}...")
            data = self.repository.find_predict_status(region_id)

            if data is None or data.empty:
                self.logger.warning(f"  No data found for region: {region_id}")
                return None

            self.logger.info(f"  Retrieved {len(data)} records")

            # 入力データの時間範囲を記録
            if 'time_bucket' in data.columns:
                input_data_start = data['time_bucket'].min()
                input_data_end = data['time_bucket'].max()
            else:
                input_data_start = None
                input_data_end = None

            # 2. シーケンス作成（バス停ごと）
            self.logger.info(f"  [2/6] Creating sequences (per stop)...")
            X_delay, _, metadata, _, _ = \
                self.sequence_creator.create_stop_aware_sequences(
                    data, spatial_organization=True, prediction_mode=True
                )

            if X_delay is None or len(X_delay) == 0:
                self.logger.warning(f"  No sequences created for region: {region_id}")
                return None

            sequence_count = len(X_delay)
            self.logger.info(f"  Created {sequence_count} sequences")

            # 3. データ標準化
            self.logger.info(f"  [3/6] Standardizing features...")
            X_scaled = self.standardizer.fit_transform_features(X_delay)

            # 4. ConvLSTM用Reshape
            self.logger.info(f"  [4/6] Reshaping for ConvLSTM...")
            actual_feature_count = X_scaled.shape[2]
            X_reshaped = self.splitter.reshape_for_convlstm(
                X_scaled, target_height=1, target_width=actual_feature_count
            )

            # 5. モデル予測
            self.logger.info(f"  [5/6] Running model prediction...")
            y_pred = self.model.predict(X_reshaped, verbose=0)

            # 6. 結果のデコード
            self.logger.info(f"  [6/6] Decoding predictions...")
            predictions_df = self._decode_predictions(
                y_pred, metadata, data, region_id
            )

            # 予測結果が空の場合は早期リターン
            if predictions_df.empty:
                self.logger.warning(f"  No valid predictions decoded for {region_id}")
                return None

            elapsed_time = time.time() - start_time
            self.logger.info(
                f"  Prediction completed for {region_id} in {elapsed_time:.2f}s "
                f"({len(predictions_df)} predictions)"
            )

            return {
                'predictions': predictions_df,
                'metadata': {
                    'input_data_start': input_data_start,
                    'input_data_end': input_data_end,
                    'sequence_count': sequence_count
                }
            }

        except Exception as e:
            self.logger.error(f"  Failed to predict region {region_id}: {e}", exc_info=True)
            return None

    def _decode_predictions(
        self,
        y_pred: np.ndarray,
        metadata: List[str],
        original_data: pd.DataFrame,
        region_id: str
    ) -> pd.DataFrame:
        """予測結果をDataFrameにデコード（バス停ごと）"""
        # バス停情報キャッシュ構築
        stop_cache = self._build_stop_cache(original_data)

        # 予測値の次元を統一
        if y_pred.ndim == 3:
            y_pred_2d = y_pred[:, :self.output_timesteps, 0]
        else:
            y_pred_2d = y_pred[:, :self.output_timesteps]

        # Vancouver タイムゾーンを設定
        vancouver_tz = pytz.timezone('America/Vancouver')

        # 予測基準時刻（現在時刻 - タイムゾーン aware）
        prediction_created_at = datetime.now(vancouver_tz)

        # 今の0分時点を計算（例: 14:23 -> 14:00）
        current_time = datetime.now(vancouver_tz)
        current_hour = current_time.replace(minute=0, second=0, microsecond=0)

        results = []
        for idx, rds_key in enumerate(metadata):
            # route_id, direction_id, stop_idをパース (format: route_id_direction_id_stop_id)
            parts = rds_key.split('_')
            if len(parts) < 3:
                self.logger.warning(f"Invalid metadata key format: {rds_key}")
                continue

            route_id = parts[0]
            direction_id = int(parts[1])
            stop_id = parts[2]

            # 該当するバス停情報を検索（キャッシュから全候補を探す）
            # キャッシュキーは route_id_direction_id_stop_id_stop_sequence の4パート形式
            matching_stops = {k: v for k, v in stop_cache.items() if k.startswith(rds_key + '_')}

            if not matching_stops:
                self.logger.warning(f"Stop info not found for key: {rds_key}")
                continue

            # 複数のstop_sequenceが存在する可能性があるので、最初のものを使用
            # (通常は1つのはず)
            cache_key = list(matching_stops.keys())[0]
            stop_info = matching_stops[cache_key]

            # 各時間オフセットの予測（今の0分時点から開始）
            for hour_offset in range(1, self.output_timesteps + 1):
                try:
                    delay_seconds = float(y_pred_2d[idx, hour_offset - 1])

                    # NaNや無限大のチェック
                    if not np.isfinite(delay_seconds):
                        self.logger.warning(
                            f"Invalid prediction value for {rds_key} at offset {hour_offset}: {delay_seconds}"
                        )
                        continue

                    delay_minutes = delay_seconds / 60.0

                    # 0分時点での予測時刻（例: 14:00, 15:00, 16:00...）
                    prediction_target_time = current_hour + timedelta(hours=hour_offset - 1)

                    results.append({
                        'region_id': region_id,
                        'route_id': route_id,
                        'direction_id': direction_id,
                        'stop_id': stop_info['stop_id'],
                        'stop_name': stop_info.get('stop_name'),
                        'stop_lat': stop_info.get('stop_lat'),
                        'stop_lon': stop_info.get('stop_lon'),
                        'stop_sequence': stop_info.get('stop_sequence'),
                        'prediction_created_at': prediction_created_at,
                        'prediction_target_time': prediction_target_time,
                        'prediction_hour_offset': hour_offset,
                        'predicted_delay_seconds': round(delay_seconds, 2),
                        'predicted_delay_minutes': round(delay_minutes, 2),
                    })
                except (ValueError, IndexError, TypeError) as e:
                    self.logger.warning(
                        f"Failed to decode prediction for {rds_key} at offset {hour_offset}: {e}"
                    )
                    continue

        return pd.DataFrame(results)

    def _build_stop_cache(self, data: pd.DataFrame) -> Dict:
        """バス停情報のキャッシュ構築（バス停ごと）"""
        cache = {}
        grouped = data.sort_values('time_bucket', ascending=False).groupby(
            ['route_id', 'direction_id', 'stop_id', 'line_direction_link_order'], as_index=False
        ).first()

        for _, row in grouped.iterrows():
            cache_key = f"{row['route_id']}_{row['direction_id']}_{row['stop_id']}_{row['line_direction_link_order']}"
            cache[cache_key] = {
                'stop_id': str(row.get('stop_id', 'unknown')),
                'stop_name': row.get('stop_name'),
                'stop_sequence': row.get('line_direction_link_order'),
                'stop_lat': float(row['stop_lat']) if pd.notna(row.get('stop_lat')) else None,
                'stop_lon': float(row['stop_lon']) if pd.notna(row.get('stop_lon')) else None
            }

        return cache

    def save_predictions(
        self,
        predictions_df: pd.DataFrame,
        model_version: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        input_data_start: Optional[datetime] = None,
        input_data_end: Optional[datetime] = None,
        sequence_count: Optional[int] = None
    ):
        """予測結果をデータベースに保存"""
        if predictions_df is None or predictions_df.empty:
            self.logger.warning("No predictions to save")
            return

        try:
            # DataFrameをコピーして元のデータを変更しない
            df_to_save = predictions_df.copy()

            # モデル情報を追加
            df_to_save['model_version'] = model_version or Path(self.model_path).stem
            df_to_save['model_path'] = self.model_path
            df_to_save['prediction_execution_time_ms'] = execution_time_ms

            # データ品質情報を追加
            df_to_save['input_data_start'] = input_data_start
            df_to_save['input_data_end'] = input_data_end
            df_to_save['sequence_count'] = sequence_count
            df_to_save['confidence_score'] = None  # 将来の拡張用

            # データベースに保存（スキーマとテーブル名を分離）
            table_name = 'regional_delay_predictions'
            schema = 'gtfs_realtime'

            self.db_connector.insert_dataframe(
                df_to_save,
                table_name=table_name,
                schema=schema,
                if_exists='append'
            )

            self.logger.info(f"Saved {len(df_to_save)} predictions to {schema}.{table_name}")

        except Exception as e:
            self.logger.error(f"Failed to save predictions: {e}", exc_info=True)
            raise DataProcessingError("Failed to save predictions to database") from e

    def execute(
        self,
        regions: Optional[List[str]] = None,
        dry_run: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        バッチ予測を実行

        Args:
            regions: 予測する地域のリスト（Noneの場合は全地域）
            dry_run: Trueの場合、DBに保存せず予測のみ実行
            **kwargs: 追加のキーワード引数（BaseJobとの互換性のため）

        Returns:
            実行結果のサマリ
        """
        start_time = time.time()

        # 地域リスト取得
        if regions is None:
            regions = self.get_all_regions()

        if not regions:
            self.logger.error("No regions to process")
            return {
                'status': 'error',
                'message': 'No regions to process',
                'total_regions': 0,
                'total_predictions': 0
            }

        # 各地域について予測実行
        region_results = {}
        total_predictions = 0

        for idx, region_id in enumerate(regions, 1):
            self.logger.info(f"\n[{idx}/{len(regions)}] Processing region: {region_id}")

            region_start = time.time()
            result = self.predict_region(region_id)
            region_elapsed = int((time.time() - region_start) * 1000)

            if result is not None:
                predictions_df = result['predictions']
                metadata = result['metadata']

                if predictions_df is not None and not predictions_df.empty:
                    prediction_count = len(predictions_df)
                    region_results[region_id] = prediction_count
                    total_predictions += prediction_count

                    # データベースに保存（dry_runでない場合）
                    if not dry_run:
                        self.save_predictions(
                            predictions_df,
                            execution_time_ms=region_elapsed,
                            input_data_start=metadata.get('input_data_start'),
                            input_data_end=metadata.get('input_data_end'),
                            sequence_count=metadata.get('sequence_count')
                        )
                    else:
                        self.logger.info(f"  [DRY RUN] Would save {prediction_count} predictions")
                else:
                    region_results[region_id] = 0
                    self.logger.warning(f"  No predictions generated for {region_id}")
            else:
                region_results[region_id] = 0
                self.logger.warning(f"  No predictions generated for {region_id}")

        # 実行時間計算
        total_elapsed = time.time() - start_time

        return {
            'status': 'success',
            'total_regions': len(regions),
            'total_predictions': total_predictions,
            'execution_time_seconds': round(total_elapsed, 2),
            'average_time_per_region': round(total_elapsed / len(regions), 2) if regions else 0,
            'region_results': region_results,
            'dry_run': dry_run
        }

    def _print_job_specific_summary(self, results: Dict[str, Any]):
        """ジョブ固有のサマリを表示"""
        if results.get('status') != 'success':
            return

        self.logger.info(f"Total regions processed: {results['total_regions']}")
        self.logger.info(f"Total predictions: {results['total_predictions']}")
        self.logger.info(
            f"Average time per region: {results['average_time_per_region']:.2f}s"
        )

        region_results = results.get('region_results', {})
        if region_results:
            self.logger.info("\nResults by region:")
            for region_id, count in region_results.items():
                self.logger.info(f"  {region_id}: {count} predictions")
