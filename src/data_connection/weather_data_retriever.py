"""
気象データ取得クラス
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class WeatherDataRetriever:
    """気象データ取得用クラス"""
    
    def __init__(self, db_connector):
        """
        Args:
            db_connector (DatabaseConnector): データベース接続オブジェクト
        """
        self.db_connector = db_connector
    
    def get_weather_data(self):
        """
        気象データを取得
        
        Returns:
            pd.DataFrame: 気象データ
        """
        weather_query = """
        SELECT 
            to_timestamp(unixtime) as datetime,
            temperature as temp,
            relative_humidity,
            pressure_sea,
            wind_speed,
            visibility,
            humidex_v as humidex,
            cloud_cover_8,
            CASE 
                WHEN cloud_cover_8 <= 2 THEN 1
                ELSE 0
            END as weather_sunny,
            CASE 
                WHEN cloud_cover_8 > 2 and cloud_cover_8 <= 6 THEN 1
                ELSE 0
            END as weather_cloudy,
            CASE 
                WHEN cloud_cover_8 > 6 THEN 1
                ELSE 0
            END as weather_rainy,
            -- 降水量（実際のデータがない場合は相対湿度から推定）
            CASE 
                WHEN relative_humidity > 90 AND cloud_cover_8 > 6 THEN 2.0
                WHEN relative_humidity > 80 AND cloud_cover_8 > 4 THEN 0.5
                ELSE 0.0
            END as precipitation
        FROM climate.weather_hourly
        ORDER BY datetime
        """
        
        print("Retrieving weather data...")
        weather_data = self.db_connector.read_sql(weather_query)
        
        # タイムゾーン変換
        weather_data['datetime'] = pd.to_datetime(weather_data['datetime'], utc=True).dt.tz_convert('America/Vancouver')
        
        return weather_data
