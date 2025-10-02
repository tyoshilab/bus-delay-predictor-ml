"""
バス遅延予測モデル - メインパイプライン

各プロセスを統合して実行するメインスクリプト
"""

# 必要なライブラリのインポート
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
warnings.filterwarnings('ignore')

# TensorFlow設定
import tensorflow as tf
tf.random.set_seed(42)
np.random.seed(42)

# カスタムモジュールのインポート
from src.data_connection import DatabaseConnector, GTFSDataRetriever, WeatherDataRetriever
from src.data_preprocessing import DataPreprocessor, DataAggregator, FeatureEngineer
from src.timeseries_processing import SequenceCreator, DataSplitter, DataStandardizer
from src.model_training import DelayPredictionModel
from src.evaluation import ModelEvaluator, ModelVisualizer
from .utils import PipelineLogger

def main():
    """
    メインパイプライン実行
    """
    # ロガー初期化
    logger = PipelineLogger("main_pipeline", "INFO")
    
    logger.info("=== バス遅延予測モデル - メインパイプライン ===")
    logger.info(f"TensorFlow バージョン: {tf.__version__}")
    logger.info(f"Pandas バージョン: {pd.__version__}")
    logger.info(f"NumPy バージョン: {np.__version__}")
    
    # ===== 1. データベース接続・データ取得 =====
    logger.info("\n=== 1. データベース接続・データ取得 ===")
    
    # データベース接続
    db_connector = DatabaseConnector()
    if not db_connector.test_connection():
        logger.error("データベース接続に失敗しました")
        return
    
    # GTFSデータ取得
    gtfs_retriever = GTFSDataRetriever(db_connector)
    gtfs_data = gtfs_retriever.get_gtfs_data(route_id='6612', start_date='20250818')
    
    # 気象データ取得
    weather_retriever = WeatherDataRetriever(db_connector)
    weather_data = weather_retriever.get_weather_data()
    
    logger.info(f"GTFSデータ: {gtfs_data.shape}")
    logger.info(f"気象データ: {weather_data.shape}")
    
    # ===== 2. データ前処理・特徴量エンジニアリング =====
    logger.info("\n=== 2. データ前処理・特徴量エンジニアリング ===")
    
    # データ前処理
    preprocessor = DataPreprocessor()
    
    # 欠損値の確認
    logger.info("=== GTFS data ===")
    missing_summary = preprocessor.show_missing_data_summary(gtfs_data)
    logger.info(missing_summary)
    
    logger.info("\n=== Weather data ===")
    missing_summary = preprocessor.show_missing_data_summary(weather_data)
    logger.info(missing_summary)
    
    # 欠損値削除
    filtered_gtfs_data = preprocessor.delete_missing_values(
        gtfs_data, ['datetime', 'travel_time_duration', 'arrival_delay']
    )
    
    # 高度な前処理
    filtered_gtfs_data = preprocessor.sophisticated_preprocessing(filtered_gtfs_data)
    
    # データ集約
    aggregator = DataAggregator(reference_frequency=60)
    delay_aggregated = aggregator.create_delay_aggregation(filtered_gtfs_data)
    weather_aggregated = aggregator.create_weather_aggregation(weather_data)
    
    # 特徴量結合
    feature_engineer = FeatureEngineer()
    delay_features = feature_engineer.merge_features(delay_aggregated, weather_aggregated)
    
    # 特徴量リスト取得
    feature_cols = feature_engineer.get_feature_columns(delay_features)
    target_col = 'arrival_delay'
    
    logger.info(f"使用特徴量: {feature_cols}")
    logger.info(f"予測対象: {target_col}")
    
    # ===== 3. 時系列データ作成・データ分割 =====
    logger.info("\n=== 3. 時系列データ作成・データ分割 ===")
    
    # シーケンス作成
    sequence_creator = SequenceCreator(input_timesteps=8, output_timesteps=3)
    X, y, route_direction_info, used_features = sequence_creator.create_route_direction_aware_sequences(
        delay_features, target_col, feature_cols
    )
    
    if len(X) == 0:
        logger.error("シーケンス作成に失敗しました")
        return
    
    # データ分割
    data_splitter = DataSplitter()
    X_train, X_test, y_train, y_test = data_splitter.train_test_split_temporal(X, y, train_ratio=0.9)
    
    # データ標準化
    standardizer = DataStandardizer()
    standardizer.fit_scalers(X_train, y_train)
    
    X_train_scaled = standardizer.transform_features(X_train)
    X_test_scaled = standardizer.transform_features(X_test)
    y_train_scaled = standardizer.transform_targets(y_train)
    y_test_scaled = standardizer.transform_targets(y_test)
    
    # ConvLSTM用reshape
    actual_feature_count = X_train_scaled.shape[2]
    X_train_reshaped = data_splitter.reshape_for_convlstm(
        X_train_scaled, target_height=1, target_width=actual_feature_count
    )
    X_test_reshaped = data_splitter.reshape_for_convlstm(
        X_test_scaled, target_height=1, target_width=actual_feature_count
    )
    
    logger.info(f"訓練データ形状: {X_train_reshaped.shape}")
    logger.info(f"テストデータ形状: {X_test_reshaped.shape}")
    
    # ===== 4. モデル構築・訓練 =====
    logger.info("\n=== 4. モデル構築・訓練 ===")
    
    # モデル作成
    model_trainer = DelayPredictionModel(input_timesteps=8, output_timesteps=3)
    
    # モデル構築
    input_shape = (8, 1, actual_feature_count, 1)  # (timesteps, height, width, channels)
    model = model_trainer.build_model(input_shape)
    
    # モデル訓練
    history = model_trainer.train_model(
        X_train_reshaped, y_train_scaled,
        batch_size=32, epochs=50, validation_split=0.2
    )
    
    # ===== 5. 評価・可視化 =====
    logger.info("\n=== 5. 評価・可視化 ===")
    
    # 予測実行
    predictions = model_trainer.predict(X_test_reshaped)
    
    # 逆標準化
    y_pred_original = standardizer.inverse_transform_targets(predictions.flatten())
    y_test_original = standardizer.inverse_transform_targets(y_test_scaled)
    
    # 最新の予測値のみを使用（系列の最後）
    y_pred_final = y_pred_original[-len(X_test):] if predictions.ndim > 1 else y_pred_original
    y_true_final = y_test_original if y_test.ndim == 1 else y_test[:, -1]
    
    # 評価
    evaluator = ModelEvaluator()
    overall_metrics = evaluator.calculate_delay_metrics(y_true_final, y_pred_final)
    delay_level_analysis = evaluator.analyze_by_delay_level(y_true_final, y_pred_final)
    
    # 評価結果表示
    evaluator.print_evaluation_summary(overall_metrics, delay_level_analysis)
    
    # 可視化
    visualizer = ModelVisualizer()
    
    # 予測分析の可視化
    visualizer.plot_prediction_analysis(y_true_final, y_pred_final, overall_metrics)
    
    # 遅延レベル別分析の可視化
    visualizer.plot_delay_level_analysis(y_true_final, y_pred_final, delay_level_analysis)
    
    # 訓練履歴の可視化
    if history is not None:
        visualizer.plot_training_history(history)
    
    # モデル保存
    model_trainer.save_model('delay_prediction_model.h5')
    
    logger.info("\n=== パイプライン完了 ===")
    logger.info("結果:")
    logger.info(f"  - MAE: {overall_metrics['mae']/60:.2f} 分")
    logger.info(f"  - RMSE: {overall_metrics['rmse']/60:.2f} 分")
    logger.info(f"  - R²: {overall_metrics['r2']:.3f}")
    logger.info(f"  - 方向予測精度: {overall_metrics['direction_accuracy']*100:.1f}%")
    logger.info(f"  - 1分以内精度: {overall_metrics['range_accuracies']['Within 1min']*100:.1f}%")

if __name__ == "__main__":
    # スタイル設定
    plt.style.use('seaborn-v0_8')
    pd.set_option('display.max_columns', None)
    
    # メイン実行
    main()
