"""
データ集約処理クラス
"""

import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class DataAggregator:
    def __init__(self, reference_frequency=60):
        self.reference_frequency = reference_frequency
    
    def create_delay_aggregation(self, data, freq_minutes=60):
        data = data.copy()
        data['time_bucket'] = data['datetime_60']
        
        # route_id + direction_id + stop_id + 時間バケット + 曜日で集約
        aggregation_keys = [
            'route_id',
            'direction_id', 
            'stop_id',
            'line_direction_link_order',
            'time_bucket',
            'day_of_week'
        ]
        
        # 集約対象カラムを動的に決定
        agg_dict = {
            'arrival_delay': 'mean',  # 平均遅延時間（予測目標）
            'trip_id': 'count'        # データ数（信頼性指標）
        }
        
        # travel_time_durationが存在する場合のみ追加
        if 'travel_time_duration' in data.columns and data['travel_time_duration'].notna().sum() > 0:
            agg_dict['travel_time_duration'] = 'mean'
        
        # 高度特徴量が存在する場合は平均値を使用
        advanced_features = ['hour_sin', 'hour_cos', 'day_sin', 'day_cos', 
                            'delay_mean_by_route_hour', 'delay_deviation']
        for feature in advanced_features:
            if feature in data.columns:
                agg_dict[feature] = 'mean'
        
        aggregated = data.groupby(aggregation_keys).agg(agg_dict).reset_index()
        
        # 列名変更
        aggregated = aggregated.rename(columns={'trip_id': 'observation_count'})
        
        # データ数が少ない組み合わせを除外（信頼性向上のため）
        min_observations = 2
        aggregated = aggregated[aggregated['observation_count'] >= min_observations].copy()
        return aggregated
    
    def create_weather_aggregation(self, data):
        """気象データの時間バケット集約"""
        # time_bucket生成
        data = data.rename(columns={'datetime': 'time_bucket'})

        # 時間バケットで集約
        weather_aggregated = data.groupby('time_bucket').agg({
            'temp': 'mean',
            'precipitation': 'mean',
            'humidex': 'mean',
            'wind_speed': 'mean',
            'weather_sunny': 'mean',
            'weather_cloudy': 'mean',
            'weather_rainy': 'mean'
        }).reset_index()

        return weather_aggregated
