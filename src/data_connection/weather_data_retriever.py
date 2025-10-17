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
    
    def get_weather_data(self, start_date=None):
        """
        気象データを取得

        Args:
            start_date (str, optional): 開始日 (YYYYMMDD形式)。Noneの場合は全データ取得

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
        """

        params = None
        if start_date:
            # start_date をタイムスタンプに変換 (YYYYMMDD -> UNIX timestamp)
            from datetime import datetime
            start_dt = datetime.strptime(start_date, '%Y%m%d')
            start_unix = int(start_dt.timestamp())
            weather_query += " WHERE unixtime >= %(start_unix)s"
            params = {'start_unix': start_unix}

        weather_query += " ORDER BY datetime"

        print(f"Retrieving weather data{' from ' + start_date if start_date else ''}...")

        # parse_datesとconvert_tz=Falseで高速化
        weather_data = self.db_connector.read_sql(
            weather_query,
            params=params,
            parse_dates=['datetime'],
            convert_tz=False
        )

        # タイムゾーン変換（高速版）
        if 'datetime' in weather_data.columns:
            if pd.api.types.is_datetime64_any_dtype(weather_data['datetime']):
                if weather_data['datetime'].dt.tz is None:
                    weather_data['datetime'] = weather_data['datetime'].dt.tz_localize('UTC').dt.tz_convert('America/Vancouver')
            else:
                weather_data['datetime'] = pd.to_datetime(weather_data['datetime'], utc=True).dt.tz_convert('America/Vancouver')

        return weather_data
