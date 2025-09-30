"""
Pipeline Utilities

データ処理パイプライン用のユーティリティ関数群
"""

import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
import logging

from .config import PipelineConfig, PipelineConfigManager


class PipelineLogger:
    """
    パイプライン専用ロガー
    """
    
    def __init__(self, name: str = "pipeline", level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # コンソールハンドラー
        if not self.logger.handlers:
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
    
    def info(self, message: str):
        self.logger.info(message)
    
    def warning(self, message: str):
        self.logger.warning(message)
    
    def error(self, message: str):
        self.logger.error(message)
    
    def debug(self, message: str):
        self.logger.debug(message)


class PipelineMetrics:
    """
    パイプライン実行メトリクス管理
    """
    
    def __init__(self):
        self.metrics = {
            'pipeline_start_time': None,
            'pipeline_end_time': None,
            'processing_stages': {},
            'data_transformations': {},
            'error_count': 0,
            'warnings_count': 0
        }
    
    def start_pipeline(self):
        """パイプライン開始時刻を記録"""
        self.metrics['pipeline_start_time'] = datetime.now()
    
    def end_pipeline(self):
        """パイプライン終了時刻を記録"""
        self.metrics['pipeline_end_time'] = datetime.now()
        if self.metrics['pipeline_start_time']:
            duration = self.metrics['pipeline_end_time'] - self.metrics['pipeline_start_time']
            self.metrics['total_duration_seconds'] = duration.total_seconds()
    
    def start_stage(self, stage_name: str):
        """処理ステージ開始を記録"""
        if stage_name not in self.metrics['processing_stages']:
            self.metrics['processing_stages'][stage_name] = {}
        self.metrics['processing_stages'][stage_name]['start_time'] = datetime.now()
    
    def end_stage(self, stage_name: str):
        """処理ステージ終了を記録"""
        if stage_name in self.metrics['processing_stages']:
            end_time = datetime.now()
            self.metrics['processing_stages'][stage_name]['end_time'] = end_time
            
            start_time = self.metrics['processing_stages'][stage_name].get('start_time')
            if start_time:
                duration = end_time - start_time
                self.metrics['processing_stages'][stage_name]['duration_seconds'] = duration.total_seconds()
    
    def record_transformation(self, transformation_name: str, before_shape: Tuple, after_shape: Tuple):
        """データ変換を記録"""
        self.metrics['data_transformations'][transformation_name] = {
            'before_shape': before_shape,
            'after_shape': after_shape,
            'records_change': after_shape[0] - before_shape[0],
            'columns_change': after_shape[1] - before_shape[1] if len(after_shape) > 1 and len(before_shape) > 1 else 0
        }
    
    def increment_error(self):
        """エラーカウントを増加"""
        self.metrics['error_count'] += 1
    
    def increment_warning(self):
        """警告カウントを増加"""
        self.metrics['warnings_count'] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """メトリクスサマリーを取得"""
        return self.metrics.copy()
    
    def save_metrics(self, filepath: str):
        """メトリクスをJSONファイルに保存"""
        # datetime オブジェクトを文字列に変換
        serializable_metrics = self._make_serializable(self.metrics)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(serializable_metrics, f, indent=2, ensure_ascii=False)
    
    def _make_serializable(self, obj):
        """オブジェクトをシリアライズ可能な形に変換"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {key: self._make_serializable(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._make_serializable(item) for item in obj]
        else:
            return obj


class FileManager:
    """
    ファイル管理ユーティリティ
    """
    
    @staticmethod
    def ensure_directory(directory_path: str):
        """ディレクトリの存在を確認し、必要に応じて作成"""
        os.makedirs(directory_path, exist_ok=True)
    
    @staticmethod
    def generate_filename(base_name: str, route_ids: List[str], start_date: str, 
                         include_timestamp: bool = True, extension: str = 'csv') -> str:
        """
        ファイル名を生成
        
        Parameters:
        -----------
        base_name : str
            ベースファイル名
        route_ids : List[str]
            ルートIDリスト
        start_date : str
            開始日付
        include_timestamp : bool
            タイムスタンプを含めるかどうか
        extension : str
            ファイル拡張子
            
        Returns:
        --------
        str: Generated filename
        """
        # ルートID部分
        if len(route_ids) == 1:
            route_part = f"route_{route_ids[0]}"
        elif len(route_ids) <= 3:
            route_part = f"routes_{'_'.join(route_ids)}"
        else:
            route_part = f"routes_{len(route_ids)}routes"
        
        # 日付部分
        date_part = f"from_{start_date}"
        
        # タイムスタンプ部分
        timestamp_part = ""
        if include_timestamp:
            timestamp_part = f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return f"{base_name}_{route_part}_{date_part}{timestamp_part}.{extension}"
    
    @staticmethod
    def save_dataframe_with_metadata(df: pd.DataFrame, filepath: str, metadata: Dict[str, Any] = None):
        """
        データフレームをメタデータ付きで保存
        
        Parameters:
        -----------
        df : pd.DataFrame
            保存するデータフレーム
        filepath : str
            保存先ファイルパス
        metadata : Dict[str, Any]
            メタデータ
        """
        # データフレームを保存
        df.to_csv(filepath, index=False)
        
        # メタデータを保存（同じディレクトリにJSONファイル）
        if metadata:
            metadata_filepath = filepath.replace('.csv', '_metadata.json')
            
            # データフレームの基本情報を追加
            enhanced_metadata = metadata.copy()
            enhanced_metadata.update({
                'file_info': {
                    'filename': os.path.basename(filepath),
                    'creation_time': datetime.now().isoformat(),
                    'file_size_mb': round(os.path.getsize(filepath) / (1024 * 1024), 2)
                },
                'data_info': {
                    'shape': df.shape,
                    'columns': list(df.columns),
                    'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
                    'memory_usage_mb': round(df.memory_usage(deep=True).sum() / (1024 * 1024), 2)
                }
            })
            
            with open(metadata_filepath, 'w', encoding='utf-8') as f:
                json.dump(enhanced_metadata, f, indent=2, ensure_ascii=False, default=str)

def format_duration(seconds: float) -> str:
    """
    秒数を人間が読みやすい形式に変換
    
    Parameters:
    -----------
    seconds : float
        秒数
        
    Returns:
    --------
    str: Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.1f}秒"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}分"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}時間"


