import pandas as pd
import numpy as np
import datetime
import warnings
warnings.filterwarnings('ignore')

from src.data_connection import DatabaseConnector, GTFSDataRetriever, WeatherDataRetriever
from src.data_preprocessing import DataPreprocessor, DataAggregator, FeatureEngineer
from .utils import PipelineLogger



def main():
    logger = PipelineLogger("data_processing_main", "INFO")
    
    try:
        # ===== 1. データベース接続 =====
        logger.info("\n=== 1. データベース接続 ===")
        db_connector = DatabaseConnector()
        if not db_connector.test_connection():
            logger.error("データベース接続に失敗しました")
            return
        logger.info("✓ データベース接続成功")
        
        # ===== 2. データ取得 =====
        logger.info("\n=== 2. データ取得 ===")
        
        # GTFSデータ取得
        logger.info("GTFSデータを取得中...")
        gtfs_retriever = GTFSDataRetriever(db_connector)
        gtfs_data = gtfs_retriever.get_gtfs_data(route_id=['6618'], start_date='20250818')
        logger.info(f"✓ GTFSデータ: {len(gtfs_data):,} records")
        
        # 気象データ取得
        logger.info("気象データを取得中...")
        weather_retriever = WeatherDataRetriever(db_connector)
        weather_data = weather_retriever.get_weather_data()
        logger.info(f"✓ 気象データ: {len(weather_data):,} records")
        
        # ===== 3. データ前処理 =====
        logger.info("\n=== 3. データ前処理 ===")
        preprocessor = DataPreprocessor()
        
        # 欠損値確認
        logger.info("欠損値をチェック中...")
        missing_summary = preprocessor.show_missing_data_summary(gtfs_data)
        
        # 欠損値削除
        required_columns = ['travel_time_duration', 'travel_time_raw_seconds']
        available_columns = [col for col in required_columns if col in gtfs_data.columns]
        
        if available_columns:
            filtered_gtfs_data = preprocessor.delete_missing_values(gtfs_data, available_columns)
        else:
            logger.warning("⚠️ 重要な列が見つからないため、欠損値削除をスキップ")
            filtered_gtfs_data = gtfs_data.copy()
        
        # 外れ値除去
        logger.info("外れ値を除去中...")
        filtered_gtfs_data = preprocessor.clean_gtfs_with_asymmetric_thresholds(filtered_gtfs_data)
        filtered_gtfs_data = filtered_gtfs_data[~filtered_gtfs_data['should_exclude']]
        
        logger.info(f"✓ データ前処理完了: {len(gtfs_data):,} -> {len(filtered_gtfs_data):,} records")
        
        # ===== 4. 特徴量エンジニアリング =====
        logger.info("\n=== 4. 特徴量エンジニアリング ===")
        feature_engineer = FeatureEngineer()
        aggregator = DataAggregator()
        
        # 統計特徴量生成
        logger.info("統計特徴量を生成中...")
        processed_gtfs_data = feature_engineer.generate_statistical_features(filtered_gtfs_data)
        
        # データ集約
        logger.info("データを集約中...")
        delay_aggregated = aggregator.create_delay_aggregation(processed_gtfs_data)
        logger.info(f"✓ GTFS集約: {len(processed_gtfs_data):,} -> {len(delay_aggregated):,} records")
        
        # 気象データ処理
        if not weather_data.empty:
            weather_aggregated = aggregator.create_weather_aggregation(weather_data)
            logger.info(f"✓ 気象データ集約: {len(weather_data):,} -> {len(weather_aggregated):,} records")
            
            # 特徴量結合
            logger.info("特徴量を結合中...")
            delay_features = feature_engineer.generate_time_features(delay_aggregated)
            merged_data = feature_engineer.merge_features(delay_features, weather_aggregated)
        else:
            logger.warning("⚠️ 気象データなしで時系列特徴量のみ生成")
            merged_data = feature_engineer.generate_time_features(delay_aggregated)
        
        logger.info(f"✓ 特徴量エンジニアリング完了: {len(merged_data):,} records")
        
        # ===== 5. 最終検証 =====
        logger.info("\n=== 5. 最終検証 ===")
        logger.info(f"データセット形状: {merged_data.shape}")
        logger.info(f"特徴量数: {len(merged_data.columns)} columns")
        
        missing_values = merged_data.isnull().sum().sum()
        logger.info(f"欠損値: {missing_values:,}")
        
        memory_usage = merged_data.memory_usage(deep=True).sum() / 1024 / 1024
        logger.info(f"メモリ使用量: {memory_usage:.2f} MB")
        
        # ===== 6. 結果保存 =====
        logger.info("\n=== 6. 結果保存 ===")
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"processed_data_{timestamp}.csv"
        filepath = f"/workspace/GTFS/data/{filename}"
        merged_data.to_csv(filepath, index=False)
        
        logger.info("\n=== パイプライン完了 ===")
        logger.info("結果:")
        logger.info(f"  - データセット形状: {merged_data.shape}")
        logger.info(f"  - メモリ使用量: {memory_usage:.2f} MB")
        logger.info(f"  - 保存ファイル: {filepath}")
        
        return merged_data
        
    except Exception as e:
        logger.error(f"パイプライン実行エラー: {str(e)}")
        raise e


if __name__ == "__main__":
    # スタイル設定
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)
    
    # メイン実行
    main()


