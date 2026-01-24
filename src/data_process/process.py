import pandas as pd
import numpy as np
from sklearn.preprocessing import LabelEncoder
from typing import List, Optional
from src import utils


class DataAggregator:
    """Handles trip data aggregation and deduplication."""

    def __init__(self):
        pass

    def create_trip_key(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create unique trip identifier."""
        df['trip_key'] = (
            df['start_date'].astype(str) + '_' +
            df['route_id'].astype(str) + '_' +
            df['direction_id'].astype(str) + '_' +
            df['trip_id'].astype(str)
        )
        return df

    def create_route_direction_key(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create route-direction composite key."""
        df['route_direction_key'] = (
            df['route_id'].astype(str) + '_' +
            df['direction_id'].astype(str)
        )
        return df

    def calculate_stop_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """Identify first, middle, and last stops in each trip."""
        seq_group = df.groupby('trip_key')['stop_sequence']
        df['seq_min'] = seq_group.transform('min')
        df['seq_max'] = seq_group.transform('max')

        df['stop_type'] = 'middle'
        df.loc[df['stop_sequence'] == df['seq_min'], 'stop_type'] = 'first'
        df.loc[df['stop_sequence'] == df['seq_max'], 'stop_type'] = 'last'

        return df

    def aggregate_arrival_delays(self, df: pd.DataFrame) -> pd.DataFrame:
        """Aggregate arrival delays by stop type."""
        group_cols = ['trip_key', 'stop_sequence']
        grouped_arrival = df.groupby(group_cols)['arrival_delay']

        arrival_first = grouped_arrival.transform('first')
        arrival_max = grouped_arrival.transform('max')
        arrival_min = grouped_arrival.transform('min')

        df['arrival_delay'] = np.where(
            df['stop_type'] == 'first',
            arrival_max,
            np.where(df['stop_type'] == 'last', arrival_min, arrival_first)
        ).astype('float32')

        return df

    def deduplicate_and_interpolate(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicates and interpolate missing delay values."""
        group_cols = ['trip_key', 'stop_sequence']

        df_unique = (
            df.sort_values(['trip_key', 'stop_sequence'])
            .drop_duplicates(subset=group_cols, keep='first')
            .drop(columns=['seq_min', 'seq_max', 'stop_type'])
        )

        df_unique['arrival_delay'] = df_unique.groupby('trip_key')['arrival_delay'].transform(
            lambda x: x.interpolate(method='linear', limit_direction='both')
        )

        return df_unique

    def aggregate_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Main aggregation pipeline."""
        data = df.copy()

        data = self.create_trip_key(data)
        data = self.create_route_direction_key(data)
        data = self.calculate_stop_types(data)
        data = self.aggregate_arrival_delays(data)
        data = self.deduplicate_and_interpolate(data)

        return data


class FeatureEngineer:
    """Handles feature engineering and transformation."""

    def __init__(self, region_id_categories: Optional[List[str]] = None):
        self.region_id_categories = region_id_categories or []
        self.region_dummy_columns = [f"region_id_{region}" for region in self.region_id_categories]
        self.rd_encoder = LabelEncoder()

    def fix_region_id(self, df: pd.DataFrame) -> pd.DataFrame:
        """Fix specific region_id issues."""
        mask_9956 = df['stop_id'].astype(str) == '9956'
        df.loc[mask_9956, 'region_id'] = 'maple_ridge'
        return df

    def prepare_basic_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare basic field types and handle missing values."""
        df['start_date'] = df['start_date'].astype(str)
        df['region_id'] = df['region_id'].fillna('unknown').astype(str)
        return df

    def create_region_dummies(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create one-hot encoded region_id features."""
        region_dummies = pd.get_dummies(df['region_id'], prefix='region_id')

        if self.region_dummy_columns:
            region_dummies = region_dummies.reindex(columns=self.region_dummy_columns, fill_value=0)
        else:
            region_dummies = region_dummies.reindex(columns=sorted(region_dummies.columns), fill_value=0)

        region_dummies = region_dummies.astype('int8')
        df = pd.concat([df, region_dummies], axis=1)

        return df

    def create_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create time-based features."""
        scheduled_time = pd.to_datetime(df['scheduled_arrival_time'], utc=True)

        df['time_of_day'] = scheduled_time.dt.hour + scheduled_time.dt.minute / 60
        df['hour'] = scheduled_time.dt.hour
        df['time_sin'] = np.sin(2 * np.pi * df['time_of_day'] / 24)
        df['time_cos'] = np.cos(2 * np.pi * df['time_of_day'] / 24)
        df['day_of_week'] = pd.to_datetime(df['start_date'], format='%Y%m%d').dt.dayofweek
        df['is_weekend'] = (df['day_of_week'] >= 6).astype(int)

        return df, scheduled_time

    def create_rush_hour_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create rush hour indicator features."""
        df['is_morning_rush_hour'] = ((df['hour'] >= 7) & (df['hour'] <= 9)).astype(int)
        df['is_evening_rush_hour'] = ((df['hour'] >= 16) & (df['hour'] <= 19)).astype(int)
        return df

    def create_alert_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create alert-based features."""
        df['has_detour'] = (df['alert_effect_detour'] > 0).astype(int)
        df['has_police_alert'] = (df['alert_police_activity'] > 0).astype(int)
        return df

    def encode_route_direction(self, df: pd.DataFrame) -> pd.DataFrame:
        """Encode route_direction_key as numeric."""
        df['route_direction_encoded'] = self.rd_encoder.fit_transform(df['route_direction_key'])
        return df

    def create_lag_features(self, df: pd.DataFrame, scheduled_time: pd.Series, n_lags: int = 5) -> pd.DataFrame:
        """Create lag features based on previous trips."""
        trip_features = df[['route_direction_key', 'stop_id', 'trip_key']].copy()
        trip_features['trip_start_time'] = scheduled_time
        trip_features['trip_delay'] = df['arrival_delay'].astype('float32')

        trip_features = (
            trip_features.groupby(['route_direction_key', 'stop_id', 'trip_key'], as_index=False)
            .agg(
                trip_start_time=('trip_start_time', 'min'),
                trip_delay=('trip_delay', 'mean')
            )
            .sort_values(['route_direction_key', 'stop_id', 'trip_start_time', 'trip_key'])
        )

        lag_columns = []
        for lag in range(1, n_lags + 1):
            col = f'lag_arrival_delay_{lag}'
            trip_features[col] = (
                trip_features.groupby(['route_direction_key', 'stop_id'])['trip_delay']
                .shift(lag)
                .astype('float32')
            )
            lag_columns.append(col)

        df = df.merge(
            trip_features[['route_direction_key', 'stop_id', 'trip_key'] + lag_columns],
            on=['route_direction_key', 'stop_id', 'trip_key'],
            how='left'
        )

        df[lag_columns] = df[lag_columns].fillna(0.0)

        return df

    def process_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Main feature engineering pipeline."""
        df = self.fix_region_id(df)
        df = self.prepare_basic_fields(df)
        df = self.create_region_dummies(df)
        df, scheduled_time = self.create_time_features(df)
        df = self.create_rush_hour_features(df)
        df = self.create_alert_features(df)
        df = self.encode_route_direction(df)
        df = self.create_lag_features(df, scheduled_time)

        return df


class DataProcessor:
    """Main data processing orchestrator."""

    def __init__(self):
        base_df = utils.load_data()

        self.per99 = base_df['arrival_delay'].quantile(0.99)
        self.per1 = base_df['arrival_delay'].quantile(0.01)

        self.region_id_categories = sorted(base_df['region_id'].fillna('unknown').astype(str).unique())
        self.region_dummy_columns = [f"region_id_{region}" for region in self.region_id_categories]

        del base_df

        self.aggregator = DataAggregator()
        self.feature_engineer = FeatureEngineer(region_id_categories=self.region_id_categories)

    def get_feature_columns(self) -> List[str]:
        """Return the list of feature columns to select."""
        base_feature_columns = [
            'trip_key', 'route_direction_key', 'start_date', 'stop_sequence', 'stop_id', 'region_id',
            'scheduled_arrival_time', 'time_bucket', 'hour_of_day', 'day_of_week',
            'time_of_day', 'hour', 'time_sin', 'time_cos',
            'is_weekend', 'is_morning_rush_hour', 'is_evening_rush_hour',
            'arrival_delay',
            'has_active_alert', 'has_detour', 'has_police_alert',
            'route_direction_encoded'
        ]

        lag_feature_columns = [
            'lag_arrival_delay_1', 'lag_arrival_delay_2', 'lag_arrival_delay_3',
            'lag_arrival_delay_4', 'lag_arrival_delay_5'
        ]

        return base_feature_columns + self.region_dummy_columns + lag_feature_columns

    def process(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process raw data through aggregation and feature engineering."""
        df_aggregated = self.aggregator.aggregate_data(df)
        df_processed = self.feature_engineer.process_features(df_aggregated)
        return df_processed