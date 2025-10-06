import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder, OneHotEncoder
import warnings
warnings.filterwarnings('ignore')

class FeatureEngineer:
    
    def __init__(self):
        self.region_label_encoder = None
        self.area_type_label_encoder = None
    
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
    
    def encode_geographic_features(self, data, fit=True):
        """
        地理的特徴量のエンコーディング

        Args:
            data: DataFrameまたはSeries（集約後のデータ）
            fit: Trueの場合はエンコーダーを学習、Falseの場合は既存のエンコーダーを使用

        Returns:
            エンコード済みデータ
        """
        data = data.copy()

        # region_id のラベルエンコーディング
        if 'region_id' in data.columns:
            if fit:
                self.region_label_encoder = LabelEncoder()
                data['region_id_encoded'] = self.region_label_encoder.fit_transform(
                    data['region_id'].fillna('unknown')
                )
            else:
                if self.region_label_encoder is not None:
                    # 未知のラベルを処理
                    known_classes = set(self.region_label_encoder.classes_)
                    data['region_id_encoded'] = data['region_id'].fillna('unknown').apply(
                        lambda x: self.region_label_encoder.transform([x])[0]
                        if x in known_classes else -1
                    )
                else:
                    raise ValueError("region_label_encoder is not fitted yet")

        # area_type のラベルエンコーディング
        if 'area_type' in data.columns:
            if fit:
                self.area_type_label_encoder = LabelEncoder()
                data['area_type_encoded'] = self.area_type_label_encoder.fit_transform(
                    data['area_type'].fillna('unclassified')
                )
            else:
                if self.area_type_label_encoder is not None:
                    known_classes = set(self.area_type_label_encoder.classes_)
                    data['area_type_encoded'] = data['area_type'].fillna('unclassified').apply(
                        lambda x: self.area_type_label_encoder.transform([x])[0]
                        if x in known_classes else -1
                    )
                else:
                    raise ValueError("area_type_label_encoder is not fitted yet")

        # area_density_score は既に数値なのでそのまま使用
        # distance_from_downtown_km も数値なのでそのまま使用
        # lat_sin, lat_cos, lon_sin, lon_cos も既にエンコード済み

        return data

    def get_geographic_feature_summary(self, data):
        """
        地理的特徴量のサマリーを表示
        """
        print("\n=== Geographic Features Summary ===")

        if 'region_id' in data.columns:
            print(f"\nUnique regions: {data['region_id'].nunique()}")
            print(f"Region distribution:\n{data['region_id'].value_counts().head(10)}")

        if 'area_type' in data.columns:
            print(f"\nArea type distribution:\n{data['area_type'].value_counts()}")

        if 'area_density_score' in data.columns:
            print(f"\nArea density score distribution:\n{data['area_density_score'].value_counts().sort_index()}")

        if 'distance_from_downtown_km' in data.columns:
            print(f"\nDistance from downtown (km):")
            print(f"  Mean: {data['distance_from_downtown_km'].mean():.2f}")
            print(f"  Median: {data['distance_from_downtown_km'].median():.2f}")
            print(f"  Range: {data['distance_from_downtown_km'].min():.2f} - {data['distance_from_downtown_km'].max():.2f}")

        print("=" * 40)

    def get_feature_columns(self, delay_features):
        base_feature_cols = ['weather', 'temp', 'precipitation', 'arrival_delay', 'travel_time_duration', 'day_of_week', 'time_period_basic']

        advanced_feature_candidates = ['hour_sin', 'hour_cos', 'day_sin', 'day_cos']
        available_advanced = [col for col in advanced_feature_candidates if col in delay_features.columns]
        base_feature_cols.extend(available_advanced)

        # 地理的特徴量を追加
        geographic_feature_candidates = [
            'distance_from_downtown_km', 'lat_sin', 'lat_cos', 'lon_sin', 'lon_cos',
            'lat_relative', 'lon_relative', 'area_density_score',
            'region_id_encoded', 'area_type_encoded'
        ]
        available_geographic = [col for col in geographic_feature_candidates if col in delay_features.columns]
        base_feature_cols.extend(available_geographic)

        return base_feature_cols
