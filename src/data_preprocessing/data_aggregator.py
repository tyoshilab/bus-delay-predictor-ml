class DataAggregator:
    def __init__(self, reference_frequency=60):
        self.reference_frequency = reference_frequency
    
    def create_delay_aggregation(self, data):
        data['time_bucket'] = data['datetime_60']
        
        aggregation_keys = [
            'route_id',
            'direction_id', 
            'stop_id',
            'line_direction_link_order',
            'time_bucket',
            'day_of_week'
        ]
        
        agg_dict = {
            'arrival_delay': 'mean',
            'travel_time_duration': 'mean',
            'trip_id': 'count'  # データ数（信頼性指標）
        }

        # Add statistical features if they exist
        if 'delay_mean_by_route_hour' in data.columns:
            agg_dict['delay_mean_by_route_hour'] = 'first'
        if 'travel_mean_by_route_hour' in data.columns:
            agg_dict['travel_mean_by_route_hour'] = 'first'

        aggregated = data.groupby(aggregation_keys).agg(agg_dict).reset_index()
        aggregated = aggregated.rename(columns={'trip_id': 'observation_count'})
        
        # データ数が少ない組み合わせを除外（信頼性向上のため）
        min_observations = 2
        aggregated = aggregated[aggregated['observation_count'] >= min_observations].copy()
        return aggregated
    
    def create_weather_aggregation(self, data):
        data = data.rename(columns={'datetime': 'time_bucket'})

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
