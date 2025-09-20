import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

class DataPreprocessor:
    def __init__(self):
        pass
    
    def show_missing_data_summary(self, data):
        table = pd.DataFrame(columns=['Missing Count', 'Missing Percentage'])
        for col in data.columns:
            missing_count = int(data[col].isnull().sum())
            missing_percentage = f'{round((missing_count / len(data)) * 100, 1)}%'
            table.loc[col] = (missing_count, missing_percentage)
        return table
    
    def delete_missing_values(self, data, columns):
        for col in columns:
            data = data.dropna(subset=[col])
        return data
    
    def remove_outliers_mad(self, df, column, threshold=3):
        if column not in df.columns or df[column].isna().all():
            return df
        
        median = df[column].median()
        mad = (df[column] - median).abs().median()
        
        if mad == 0:
            return df
        
        outlier_mask = (df[column] - median).abs() <= threshold * mad
        removed_count = len(df) - outlier_mask.sum()
        print(f"  {column}: Removed {removed_count} outliers using MAD method")
        return df[outlier_mask]
    
    def generate_time_features(self, data):
        data = data.copy()
        
        if 'hour_of_day' in data.columns:
            data['hour_sin'] = np.sin(2 * np.pi * data['hour_of_day'] / 24)
            data['hour_cos'] = np.cos(2 * np.pi * data['hour_of_day'] / 24)
        
        if 'day_of_week' in data.columns:
            data['day_sin'] = np.sin(2 * np.pi * data['day_of_week'] / 7)
            data['day_cos'] = np.cos(2 * np.pi * data['day_of_week'] / 7)
        
        if 'hour_of_day' in data.columns:
            data['time_period_detailed'] = pd.cut(
                data['hour_of_day'],
                bins=[0, 5, 7, 9, 12, 15, 18, 22, 24],
                labels=['Late_Night', 'Early_Morning', 'Morning_Peak', 'Midday', 
                        'Afternoon', 'Evening_Peak', 'Night', 'Late_Evening'],
                right=False,
                include_lowest=True
            )
        
        if 'hour_of_day' in data.columns:
            data['is_peak_hour'] = data['hour_of_day'].isin([7, 8, 17, 18])
        
        if 'day_of_week' in data.columns:
            data['is_weekend'] = data['day_of_week'].isin([6, 7])
        
        return data
    
    def generate_statistical_features(self, data):
        data = data.copy()
        
        required_cols = ['route_id', 'direction_id', 'hour_of_day', 'arrival_delay']
        if not all(col in data.columns for col in required_cols):
            return data
        
        agg_dict = {
            'arrival_delay': ['mean', 'std', 'count']
        }
        
        if 'travel_time_duration' in data.columns:
            agg_dict['travel_time_duration'] = ['mean', 'std']
        
        route_stats = data.groupby(['route_id', 'direction_id', 'hour_of_day']).agg(agg_dict).round(3)
        
        if 'travel_time_duration' in data.columns:
            route_stats.columns = ['delay_mean_by_route_hour', 'delay_std_by_route_hour', 'delay_count_by_route_hour',
                                  'travel_mean_by_route_hour', 'travel_std_by_route_hour']
        else:
            route_stats.columns = ['delay_mean_by_route_hour', 'delay_std_by_route_hour', 'delay_count_by_route_hour']
        
        route_stats = route_stats.reset_index()
        
        data = data.merge(
            route_stats, 
            on=['route_id', 'direction_id', 'hour_of_day'],
            how='left'
        )
        
        if 'delay_mean_by_route_hour' in data.columns:
            data['delay_deviation'] = data['arrival_delay'] - data['delay_mean_by_route_hour']
        
        return data