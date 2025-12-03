"""
Regional Delay Repository - Database access for regional delay data
"""

from typing import Optional, Dict
import logging
import pandas as pd
from ..database_connector import DatabaseConnector

logger = logging.getLogger(__name__)


class RegionalDelayRepository:
    """Regional delay data access layer"""

    def __init__(self, db_connector: DatabaseConnector):
        self.db_connector = db_connector

    def find_recent_status(self) -> Optional[Dict]:
        """
        Find recent status for a region

        Returns:
            Most recent delay status or None
        """
        query = f"""
            select 
                region_id,
                max(base.stop_lat) as stop_lat,
                min(base.stop_lat) as stop_lat,
                avg(base.arrival_delay) as avg_delay_seconds
            from
                gtfs_realtime.gtfs_rt_base_v base
            group by base.region_id
            order by base.region_id;
        """

        return self.db_connector.read_sql(query)

    def find_latest_predictions(self, region_id: str, forecast_hours: int = 3) -> Optional[pd.DataFrame]:
        """
        バッチジョブで作成された最新の予測データを取得

        Args:
            region_id: 地域ID
            forecast_hours: 予測時間数（1-3）

        Returns:
            最新の予測データのDataFrame
        """
        query = f"""
            SELECT
                region_id,
                route_id,
                direction_id,
                stop_id,
                stop_name,
                stop_lat,
                stop_lon,
                prediction_created_at,
                prediction_target_time,
                prediction_hour_offset,
                predicted_delay_seconds,
                predicted_delay_minutes,
                model_version
            FROM gtfs_realtime.regional_predictions_latest
            WHERE region_id = '{region_id}'
                AND prediction_hour_offset <= {forecast_hours}
            ORDER BY route_id, direction_id, stop_id, prediction_hour_offset;
        """

        return self.db_connector.read_sql(query)

    def find_all_latest_predictions(self) -> Optional[pd.DataFrame]:
        """
        全地域の最新予測データを取得

        Returns:
            全地域の最新予測データのDataFrame
        """
        query = """
            SELECT
                region_id,
                route_id,
                direction_id,
                stop_id,
                stop_name,
                stop_lat,
                stop_lon,
                prediction_created_at,
                prediction_target_time,
                prediction_hour_offset,
                predicted_delay_seconds,
                predicted_delay_minutes,
                model_version
            FROM gtfs_realtime.regional_predictions_latest
            ORDER BY region_id, route_id, direction_id, stop_id, prediction_hour_offset;
        """

        return self.db_connector.read_sql(query)