"""
Pipeline Configuration

データ処理パイプラインの設定とコンフィグレーション
"""

import os
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


@dataclass
class PipelineConfig:
    """
    パイプライン設定クラス
    """
    # データベース設定
    database_timeout: int = 30
    max_retry_attempts: int = 3
    
    # データ取得設定
    default_start_date: str = '20250818'
    max_records_per_route: Optional[int] = None
    
    # データ前処理設定
    missing_value_threshold: float = 0.5  # 50%以上欠損で列削除
    outlier_removal_method: str = 'asymmetric'  # 'asymmetric', 'iqr', 'zscore'
    
    # 特徴量エンジニアリング設定
    aggregation_frequency: int = 60  # 分単位での集約
    include_weather_features: bool = True
    include_time_features: bool = True
    include_statistical_features: bool = True
    
    # 出力設定
    output_directory: str = '/workspace/GTFS/data'
    save_intermediate_results: bool = False
    include_timestamp_in_filename: bool = True
    
    # ロギング設定
    verbose: bool = True
    log_level: str = 'INFO'  # 'DEBUG', 'INFO', 'WARNING', 'ERROR'


@dataclass
class RouteConfig:
    """
    ルート固有の設定
    """
    route_id: str
    route_name: Optional[str] = None
    expected_frequency_minutes: int = 15
    service_hours: Dict[str, str] = None  # {'start': '05:00', 'end': '23:30'}
    
    def __post_init__(self):
        if self.service_hours is None:
            self.service_hours = {'start': '05:00', 'end': '23:30'}

class PipelineConfigManager:
    """
    パイプライン設定管理クラス
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        
    def get_processing_params(self) -> Dict[str, Any]:
        """
        データ処理パラメータを取得
        
        Returns:
        --------
        Dict: Processing parameters
        """
        return {
            'missing_value_threshold': self.config.missing_value_threshold,
            'outlier_removal_method': self.config.outlier_removal_method,
            'aggregation_frequency': self.config.aggregation_frequency,
            'include_weather_features': self.config.include_weather_features,
            'include_time_features': self.config.include_time_features,
            'include_statistical_features': self.config.include_statistical_features,
        }
    
    def get_output_params(self) -> Dict[str, Any]:
        """
        出力パラメータを取得
        
        Returns:
        --------
        Dict: Output parameters
        """
        return {
            'output_directory': self.config.output_directory,
            'save_intermediate_results': self.config.save_intermediate_results,
            'include_timestamp_in_filename': self.config.include_timestamp_in_filename,
        }
    
    def validate_config(self) -> List[str]:
        """
        設定を検証
        
        Returns:
        --------
        List[str]: Validation errors (empty if valid)
        """
        errors = []
        
        # 出力ディレクトリの存在確認
        if not os.path.exists(self.config.output_directory):
            try:
                os.makedirs(self.config.output_directory, exist_ok=True)
            except Exception as e:
                errors.append(f"Cannot create output directory: {e}")
        
        # 数値パラメータの検証
        if not 0 <= self.config.missing_value_threshold <= 1:
            errors.append("missing_value_threshold must be between 0 and 1")
        
        if self.config.aggregation_frequency <= 0:
            errors.append("aggregation_frequency must be positive")
        
        if self.config.max_retry_attempts < 0:
            errors.append("max_retry_attempts must be non-negative")
        
        return errors
    
    def update_config(self, **kwargs):
        """
        設定を更新
        
        Parameters:
        -----------
        **kwargs: Configuration parameters to update
        """
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                print(f"Warning: Unknown configuration parameter '{key}'")


# デフォルト設定インスタンス
DEFAULT_CONFIG = PipelineConfig()
DEFAULT_CONFIG_MANAGER = PipelineConfigManager(DEFAULT_CONFIG)


def get_config() -> PipelineConfig:
    """
    デフォルト設定を取得
    
    Returns:
    --------
    PipelineConfig: Default pipeline configuration
    """
    return DEFAULT_CONFIG


