import pandas as pd
import numpy as np
import warnings
warnings.filterwarnings('ignore')

class FeatureEngineer:
    
    def __init__(self):
        pass
    
    def generate_statistical_features(self, data):
        data = data.copy()
        data['hour_of_day'] = data['datetime'].dt.hour
        
        agg_dict = {
            'arrival_delay': 'mean',
            'travel_time_duration': 'mean'
        }
        route_stats = data.groupby(['route_id', 'direction_id', 'hour_of_day']).agg(agg_dict).round(3)
        route_stats.columns = ['delay_mean_by_route_hour', 'travel_mean_by_route_hour']
        route_stats = route_stats.reset_index()
        data = data.merge(
            route_stats, 
            on=['route_id', 'direction_id', 'hour_of_day'],
            how='left'
        )        
        
        return data
    
    def generate_time_features(self, data):
        data = data.copy()
        data['hour_of_day'] = pd.to_datetime(data['time_bucket']).dt.hour
        
        data['hour_sin'] = np.sin(2 * np.pi * data['hour_of_day'] / 24)
        data['hour_cos'] = np.cos(2 * np.pi * data['hour_of_day'] / 24)
        
        data['day_sin'] = np.sin(2 * np.pi * data['day_of_week'] / 7)
        data['day_cos'] = np.cos(2 * np.pi * data['day_of_week'] / 7)
        
        data['time_period_detailed'] = pd.cut(
            data['hour_of_day'],
            bins=[0, 5, 7, 9, 12, 15, 18, 22, 24],
            labels=['Late_Night', 'Early_Morning', 'Morning_Peak', 'Midday', 
                    'Afternoon', 'Evening_Peak', 'Night', 'Late_Evening'],
            right=False,
            include_lowest=True
        )
        
        data['is_peak_hour'] = data['hour_of_day'].isin([7, 8, 17, 18]).astype(int)
        data['is_weekend'] = data['day_of_week'].isin([6, 7]).astype(int)
        
        return data

    def merge_features(self, delay_aggregated, weather_aggregated):
        delay_features = delay_aggregated.merge(
            weather_aggregated, 
            on='time_bucket', 
            how='inner'
        )

        return delay_features
    
    def get_feature_columns(self, delay_features):
        base_feature_cols = ['weather', 'temp', 'precipitation', 'arrival_delay', 'travel_time_duration', 'day_of_week', 'time_period_basic']

        advanced_feature_candidates = ['hour_sin', 'hour_cos', 'day_sin', 'day_cos']
        available_advanced = [col for col in advanced_feature_candidates if col in delay_features.columns]
        base_feature_cols.extend(available_advanced)
        
        return base_feature_cols
