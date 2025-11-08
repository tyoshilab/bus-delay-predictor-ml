"""
Delay Prediction Repository - Database access for delay prediction data
"""

from typing import Optional
import logging
import pandas as pd
from ..database_connector import DatabaseConnector
from datetime import datetime

logger = logging.getLogger(__name__)


class DelayPredictionRepository:
    """Delay prediction data access layer"""

    def __init__(self, db_connector: DatabaseConnector):
        self.db_connector = db_connector
    
    def find_predictions_by_stop(self, stop_id: str) -> Optional[pd.DataFrame]:
        """
        指定した停車駅の予測データを取得
        Args:
            stop_id: 停車駅ID
        Returns:
            最新の予測データのDataFrame
        """

        query = """
            WITH next_arrivals AS (
                SELECT
                    trip.route_id,
                    trip.trip_headsign,
                    trip.service_id,
                    MIN(gtfs_static.get_stop_actual_time(
                        CURRENT_DATE,
                        st.arrival_time,
                        st.arrival_day_offset
                    )) as next_arrival_timestamp,
                    MIN(st.arrival_time) as next_arrival_time,
                    MIN(st.arrival_day_offset) as arrival_day_offset
                FROM gtfs_static.gtfs_stop_times st
                INNER JOIN gtfs_static.gtfs_trips_static trip USING (trip_id)
                INNER JOIN gtfs_static.gtfs_active_service_dates_mv asd
                    ON trip.service_id = asd.service_id
                    AND asd.service_date = CURRENT_DATE
                WHERE st.stop_id = %s
                    AND gtfs_static.get_stop_actual_time(
                        CURRENT_DATE,
                        st.arrival_time,
                        st.arrival_day_offset
                    ) >= NOW()
                GROUP BY trip.route_id, trip.trip_headsign, trip.service_id
            )
            SELECT
                na.route_id,
                na.service_id,
                na.arrival_day_offset,
                na.next_arrival_timestamp as next_arrival_time,
                trip.trip_id,
                trip.direction_id,
                trip.trip_headsign,
                st.stop_sequence,
                COALESCE(rpl.predicted_delay_seconds, rt2.arrival_delay) as predicted_delay_seconds,
                rt.arrival_delay as previous_stop_arrival_delay
            FROM gtfs_static.gtfs_stop_times st
            INNER JOIN next_arrivals na
                ON st.arrival_time = na.next_arrival_time
                AND st.arrival_day_offset = na.arrival_day_offset
                AND st.stop_id = %s
            INNER JOIN gtfs_static.gtfs_trips_static trip
                ON trip.trip_id = st.trip_id
                AND trip.route_id = na.route_id
                AND trip.trip_headsign = na.trip_headsign
                AND trip.service_id = na.service_id
            LEFT JOIN gtfs_realtime.gtfs_rt_base_mv rt
                ON rt.trip_id = trip.trip_id
                AND rt.stop_sequence = st.stop_sequence - 1
            LEFT JOIN gtfs_realtime.gtfs_rt_base_mv rt2
                ON rt2.trip_id = trip.trip_id
                AND rt2.stop_sequence = st.stop_sequence
            LEFT JOIN gtfs_realtime.regional_predictions_latest rpl
                ON rpl.stop_id = st.stop_id
                AND rpl.stop_sequence = st.stop_sequence
                AND rpl.prediction_target_time = DATE_TRUNC('hour', na.next_arrival_timestamp)
            ORDER BY na.next_arrival_timestamp;
        """

        return self.db_connector.read_sql(query, params=(stop_id, stop_id))


    def find_arrival_time_and_predictions(self, stop_id: str, route_id: str) -> Optional[pd.DataFrame]:
        """
        指定したroute_idとstop_idの時刻表と予測データを取得

        Args:
            stop_id: 停車駅ID
            route_id: 路線ID

        Returns:
            最新の予測データと時刻表のDataFrame
        """
        query = """
            SELECT
                trip.route_id,
                st.trip_id,
                st.stop_id,
                trip.direction_id,
                st.stop_sequence,
                trip.trip_headsign,
                st.arrival_time,
                st.arrival_day_offset,
                gtfs_static.get_stop_actual_time(
                    CURRENT_DATE,
                    st.arrival_time,
                    st.arrival_day_offset
                ) as actual_arrival_timestamp,
                rpl.prediction_target_time,
                COALESCE(rpl.predicted_delay_seconds, rt2.arrival_delay) as predicted_delay_seconds
            FROM gtfs_static.gtfs_stops s
            INNER JOIN gtfs_static.gtfs_stop_times st USING (stop_id)
            INNER JOIN gtfs_static.gtfs_trips_static trip USING (trip_id)
            INNER JOIN gtfs_static.gtfs_active_service_dates_mv asd
                ON trip.service_id = asd.service_id
                AND asd.service_date = CURRENT_DATE
            LEFT JOIN gtfs_realtime.gtfs_rt_base_mv rt2
                ON rt2.trip_id = trip.trip_id
                AND rt2.stop_sequence = st.stop_sequence
            LEFT JOIN gtfs_realtime.regional_predictions_latest rpl
                ON rpl.stop_id = st.stop_id
                AND rpl.route_id = trip.route_id
                AND rpl.prediction_target_time <= gtfs_static.get_stop_actual_time(
                    CURRENT_DATE,
                    st.arrival_time,
                    st.arrival_day_offset
                )
                AND rpl.prediction_target_time + INTERVAL '1 hour' > gtfs_static.get_stop_actual_time(
                    CURRENT_DATE,
                    st.arrival_time,
                    st.arrival_day_offset
                )
            WHERE s.stop_id = %s
                AND trip.route_id = %s
                AND gtfs_static.get_stop_actual_time(
                    CURRENT_DATE,
                    st.arrival_time,
                    st.arrival_day_offset
                ) >= NOW() - INTERVAL '5 minutes'
            ORDER BY trip.trip_headsign, actual_arrival_timestamp;
        """

        return self.db_connector.read_sql(query, params=(stop_id, route_id))