"""
Regional Delay Repository - Database access for regional delay data
"""

from typing import Optional, Dict
import logging
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
            WITH region_hourly AS (
                SELECT
                    a.region_id,
                    DATE_TRUNC('hour', a.datetime_60) AS time_bucket,
                    MAX(a.stop_lat) AS stop_lat,
                    MAX(a.stop_lon) AS stop_lon,
                    AVG(a.arrival_delay) / 60.0 AS avg_delay_minutes
                FROM gtfs_realtime.gtfs_rt_enriched_mv a
                WHERE a.datetime_60 >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
                AND a.arrival_delay IS NOT NULL
                GROUP BY a.region_id, time_bucket
            ),
            ranked AS (
                SELECT
                    *,
                    ROW_NUMBER() OVER (PARTITION BY region_id ORDER BY time_bucket DESC) AS rn
                FROM region_hourly
            )
            SELECT
                region_id,
                stop_lat as center_lat,
                stop_lon as center_lon,
                avg_delay_minutes
            FROM ranked
            WHERE rn = 1
            AND region_id IS NOT NULL
            ORDER BY region_id;
        """

        return self.db_connector.read_sql(query)