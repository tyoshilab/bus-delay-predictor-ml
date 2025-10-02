"""
GTFS Bus Delay Prediction Package

バス遅延予測のためのデータ管理・機械学習パッケージ
"""

# データ接続
from .data_connection import DatabaseConnector, GTFSDataRetriever, GTFSDataRetrieverV2, WeatherDataRetriever

# データ前処理
from .data_preprocessing import DataPreprocessor, DataAggregator, FeatureEngineer

# 時系列処理
from .timeseries_processing import SequenceCreator, DataSplitter, DataStandardizer

# モデル訓練
from .model_training import DelayPredictionModel

# 評価
from .evaluation import ModelEvaluator, ModelVisualizer

# パイプライン
from .pipeline.main_pipeline import main
from .pipeline.data_processing_pipeline import main

__version__ = "1.0.0"
__author__ = "GTFS Analysis Team"

__all__ = [
    # Data Connection
    'DatabaseConnector',
    'GTFSDataRetriever', 
    'GTFSDataRetrieverV2',
    'WeatherDataRetriever',
    
    # Data Preprocessing
    'DataPreprocessor',
    'DataAggregator',
    'FeatureEngineer',
    
    # Time Series Processing
    'SequenceCreator',
    'DataSplitter',
    'DataStandardizer',
    
    # Model Training
    'DelayPredictionModel',
    
    # Evaluation
    'ModelEvaluator',
    'ModelVisualizer',
    
    # Pipeline
    'main',
]
