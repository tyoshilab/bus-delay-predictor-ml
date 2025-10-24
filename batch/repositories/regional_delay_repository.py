"""
Regional Delay Repository - Database access for regional delay data
"""

import sys
from pathlib import Path
from typing import Optional, Dict
import logging

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from batch.config.database_connector import DatabaseConnector

logger = logging.getLogger(__name__)


class RegionalDelayRepository:
    """Regional delay data access layer"""

    def __init__(self, db_connector: DatabaseConnector):
        self.db_connector = db_connector

    def find_predict_status(self, region_id: str) -> Optional[Dict]:
        """
        Find prediction status for a region with stop information.
        Retrieves last 9 hours of data for model input.
        (9 hours is used because climate data is only available up to 1 hour ago)

        Args:
            region_id: Region identifier

        Returns:
            DataFrame with historical data including stop metadata
        """
        query = f"""
            SELECT
                gtfs_status.route_id,
                gtfs_status.stop_id,
                gtfs_status.stop_name,
                gtfs_status.stop_lat,
                gtfs_status.stop_lon,
                gtfs_status.datetime_60 as time_bucket,
                gtfs_status.direction_id,
                gtfs_status.hour_sin,
                gtfs_status.hour_cos,
                gtfs_status.day_cos,
                gtfs_status.day_sin,
                gtfs_status.is_peak_hour,
                gtfs_status.is_weekend,
                gtfs_status.arrival_delay,
                gtfs_status.stop_sequence as line_direction_link_order,
                gtfs_status.delay_mean_by_route_hour,
                gtfs_status.distance_from_downtown_km,
                weather.humidex_v as humidex,
                weather.wind_speed,
                CASE
                    WHEN weather.cloud_cover_8 > 6 THEN 1
                    ELSE 0
                END as weather_rainy
            FROM gtfs_realtime.gtfs_rt_analytics_mv gtfs_status
            INNER JOIN climate.weather_hourly weather
                ON gtfs_status.datetime_60 = to_timestamp(weather.unixtime)
            WHERE gtfs_status.datetime_60 >= CURRENT_TIMESTAMP - INTERVAL '9 hours'
                AND gtfs_status.region_id = '{region_id}'
            ORDER BY gtfs_status.datetime_60, gtfs_status.route_id,
                        gtfs_status.direction_id, gtfs_status.stop_sequence;
        """

        return self.db_connector.read_sql(query)