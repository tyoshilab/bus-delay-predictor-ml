"""
特徴量エンジニアリングクラス
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class FeatureEngineer:
    """特徴量エンジニアリングクラス"""
    
    def __init__(self):
        """初期化"""
        pass
    
    def merge_features(self, delay_aggregated, weather_aggregated):
        """特徴量を結合"""
        # 遅延予測用データセットの作成
        delay_features = delay_aggregated.merge(
            weather_aggregated, 
            on='time_bucket', 
            how='inner'
        )
        
        # 結合後のデータ品質チェック
        print(f"\n=== 特徴量結合後の分析 ===")
        print(f"結合前 - 遅延データ: {len(delay_aggregated)} レコード")
        print(f"結合前 - 気象データ: {len(weather_aggregated)} レコード")
        print(f"結合後:             {len(delay_features)} レコード")
        
        return delay_features
    
    def get_feature_columns(self, delay_features):
        """利用可能な特徴量を動的に決定"""
        base_feature_cols = ['weather', 'temp', 'precipitation', 'arrival_delay', 'travel_time_duration', 'day_of_week', 'time_period_basic']

        # 高度な特徴量が利用可能な場合は追加
        advanced_feature_candidates = ['hour_sin', 'hour_cos', 'day_sin', 'day_cos', 'delay_deviation']
        available_advanced = [col for col in advanced_feature_candidates if col in delay_features.columns]
        base_feature_cols.extend(available_advanced)
        
        return base_feature_cols
