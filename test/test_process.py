import pytest
from unittest.mock import patch
import pandas as pd
import numpy as np
import sys
import os

# Add project root to path to allow importing modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.data_process.process import DataAggregator, FeatureEngineer, DataProcessor

class TestDataAggregator:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.aggregator = DataAggregator()
        self.df = pd.DataFrame({
            'start_date': [20231001, 20231001, 20231001],
            'route_id': [100, 100, 100],
            'direction_id': [0, 0, 0],
            'trip_id': [123, 123, 123],
            'stop_sequence': [1, 2, 3],
            'arrival_delay': [10, 20, 30]
        })

    def test_create_trip_key(self):
        df = self.aggregator.create_trip_key(self.df.copy())
        expected_key = '20231001_100_0_123'
        assert 'trip_key' in df.columns
        assert df['trip_key'].iloc[0] == expected_key

    def test_create_route_direction_key(self):
        df = self.aggregator.create_route_direction_key(self.df.copy())
        expected_key = '100_0'
        assert 'route_direction_key' in df.columns
        assert df['route_direction_key'].iloc[0] == expected_key

    def test_calculate_stop_types(self):
        df = self.df.copy()
        df = self.aggregator.create_trip_key(df)
        df = self.aggregator.calculate_stop_types(df)
        
        assert df.loc[df['stop_sequence'] == 1, 'stop_type'].iloc[0] == 'first'
        assert df.loc[df['stop_sequence'] == 2, 'stop_type'].iloc[0] == 'middle'
        assert df.loc[df['stop_sequence'] == 3, 'stop_type'].iloc[0] == 'last'

    def test_aggregate_arrival_delays(self):
        df = self.df.copy()
        df = self.aggregator.create_trip_key(df)
        df = self.aggregator.calculate_stop_types(df)
        
        # Create duplicate entries logic simulation
        df_dup = pd.concat([df, df]).sort_values('stop_sequence').reset_index(drop=True)
        # Sequence 1 (first): Delays 10 and 100. Should pick max (100)
        df_dup.loc[1, 'arrival_delay'] = 100
        # Sequence 2 (middle): Delays 20 and 200. Should pick first (20)
        df_dup.loc[3, 'arrival_delay'] = 200
        # Sequence 3 (last): Delays 30 and 5. Should pick min (5)
        df_dup.loc[5, 'arrival_delay'] = 5

        result = self.aggregator.aggregate_arrival_delays(df_dup)
        
        assert result.loc[result['stop_sequence'] == 1, 'arrival_delay'].max() == 100.0
        assert result.loc[result['stop_sequence'] == 2, 'arrival_delay'].iloc[0] == 20.0
        assert result.loc[result['stop_sequence'] == 3, 'arrival_delay'].min() == 5.0

    def test_deduplicate_and_interpolate(self):
        df = pd.DataFrame({
            'trip_key': ['T1', 'T1', 'T1'],
            'stop_sequence': [1, 2, 3],
            'arrival_delay': [10.0, np.nan, 30.0],
            'seq_min': [1, 1, 1],
            'seq_max': [3, 3, 3],
            'stop_type': ['first', 'middle', 'last']
        })
        
        result = self.aggregator.deduplicate_and_interpolate(df)
        
        assert len(result) == 3
        assert result.iloc[1]['arrival_delay'] == 20.0
        assert 'stop_type' not in result.columns

class TestFeatureEngineer:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.engineer = FeatureEngineer(region_id_categories=['van', 'richmond'])
        self.df = pd.DataFrame({
            'stop_id': ['123', '9956', '456'],
            'region_id': ['van', np.nan, 'richmond'],
            'start_date': [20231001, 20231002, 20231003],
            'scheduled_arrival_time': ['2023-10-01 08:30:00', '2023-10-02 17:30:00', '2023-10-03 12:00:00'],
            'route_direction_key': ['R1_0', 'R1_1', 'R2_0'],
            'alert_effect_detour': [0, 1, 0],
            'alert_police_activity': [1, 0, 0]
        })

    def test_fix_region_id(self):
        df = self.engineer.fix_region_id(self.df.copy())
        assert df.loc[df['stop_id'] == '9956', 'region_id'].iloc[0] == 'maple_ridge'

    def test_prepare_basic_fields(self):
        df = self.engineer.prepare_basic_fields(self.df.copy())
        assert pd.api.types.is_string_dtype(df['start_date'])
        assert df.loc[df['stop_id'] == '9956', 'region_id'].iloc[0] == 'unknown'

    def test_create_region_dummies(self):
        df = self.engineer.prepare_basic_fields(self.df.copy())
        df = self.engineer.create_region_dummies(df)
        assert 'region_id_van' in df.columns
        assert 'region_id_richmond' in df.columns
        assert df.loc[0, 'region_id_van'] == 1

    def test_create_time_features(self):
        df, _ = self.engineer.create_time_features(self.df.copy())
        # 08:30 is 8.5
        assert df.loc[0, 'time_of_day'] == 8.5
        assert df.loc[0, 'hour'] == 8
        # 2023-10-01 Sunday
        assert df.loc[0, 'is_weekend'] == 1

    def test_create_rush_hour_features(self):
        df = self.df.copy()
        df['hour'] = [8, 17, 12]
        df = self.engineer.create_rush_hour_features(df)
        assert df.loc[0, 'is_morning_rush_hour'] == 1
        assert df.loc[1, 'is_evening_rush_hour'] == 1

    def test_create_alert_features(self):
        df = self.engineer.create_alert_features(self.df.copy())
        assert df.loc[0, 'has_police_alert'] == 1
        assert df.loc[1, 'has_detour'] == 1

    def test_create_lag_features(self):
        data = {
            'route_direction_key': ['R1_0', 'R1_0', 'R1_0'],
            'stop_id': ['S1', 'S1', 'S1'],
            'trip_key': ['T1', 'T2', 'T3'],
            'arrival_delay': [10.0, 20.0, 30.0],
            'scheduled_arrival_time': [
                pd.Timestamp('2023-10-01 08:00:00', tz='UTC'),
                pd.Timestamp('2023-10-01 08:30:00', tz='UTC'), 
                pd.Timestamp('2023-10-01 09:00:00', tz='UTC')
            ],
            'start_date': [20231001, 20231001, 20231001]
        }
        df = pd.DataFrame(data)
        df, scheduled_time = self.engineer.create_time_features(df)
        
        # Test lag creation
        df = self.engineer.create_lag_features(df, scheduled_time, n_lags=1)
        
        assert df.loc[1, 'lag_arrival_delay_1'] == 10.0
        assert df.loc[2, 'lag_arrival_delay_1'] == 20.0

class TestDataProcessor:
    @patch('src.utils.load_data')
    def test_process(self, mock_load_data):
        mock_df = pd.DataFrame({
            'arrival_delay': [10, 20, 30],
            'region_id': ['van', 'van', 'richmond'],
            'start_date': [20231001, 20231001, 20231001],
            'route_id': [100, 100, 100],
            'direction_id': [0, 0, 0],
            'trip_id': [123, 123, 123],
            'stop_sequence': [1, 2, 3],
            'stop_id': ['S1', 'S2', 'S3'],
            'scheduled_arrival_time': ['2023-10-01 08:30:00', '2023-10-01 08:35:00', '2023-10-01 08:40:00'],
            'alert_effect_detour': [0, 0, 0],
            'alert_police_activity': [0, 0, 0]
        })
        mock_load_data.return_value = mock_df

        processor = DataProcessor()
        processed_df = processor.process(mock_df.copy())
        
        assert 'trip_key' in processed_df.columns
        assert 'region_id_van' in processed_df.columns
        assert 'lag_arrival_delay_1' in processed_df.columns
