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

        weekday = {0: "monday", 1: "tuesday", 2: "wednesday", 3: "thursday", 4: "friday", 5: "saturday", 6: "sunday"}
        today_weekday = datetime.today().weekday()

        query = f"""
            WITH next_arrivals AS (
            select trip.route_id, trip.direction_id, trip.service_id, min(st.arrival_time) as next_arrival_time
            from
                gtfs_static.gtfs_stop_times st
                inner join gtfs_static.gtfs_trips_static trip USING (trip_id)
                left join gtfs_static.gtfs_calendar cal USING (service_id)
                left join gtfs_static.gtfs_calendar_dates cal_dates USING (service_id)
            where
                st.stop_id = '{stop_id}'
                and st.arrival_time >= current_time
                and (
                    cal.{weekday[today_weekday]} = 1
                    or cal_dates.date = current_date
                )
            GROUP BY
                trip.route_id,
                trip.direction_id,
                trip.service_id
            )
            select na.*, trip.trip_id, trip.trip_headsign, st.stop_sequence, rpl.predicted_delay_seconds, rt.arrival_delay as previous_stop_arrival_delay
            from gtfs_static.gtfs_stop_times st
                inner join next_arrivals na 
                on st.arrival_time = na.next_arrival_time
                and st.stop_id = '{stop_id}'
            inner join gtfs_static.gtfs_trips_static trip
                on trip.trip_id = st.trip_id
            left join gtfs_realtime.gtfs_rt_base_mv rt
                on rt.trip_id = trip.trip_id
                and rt.stop_sequence = st.stop_sequence - 1
            left join gtfs_realtime.regional_predictions_latest rpl
                on rpl.stop_id = st.stop_id
                and rpl.prediction_target_time = date_trunc('hour', current_date + na.next_arrival_time);
        """

        return self.db_connector.read_sql(query)


    def find_arrival_time_and_predictions(self, stop_id: str, route_id: str) -> Optional[pd.DataFrame]:
        """
        指定したroute_idとstop_idの時刻表と予測データを取得

        Args:
            stop_id: 停車駅ID
            route_id: 路線ID

        Returns:
            最新の予測データと時刻表のDataFrame
        """
        query = f"""
            select trip.route_id, st.trip_id, st.stop_id, trip.direction_id, st.stop_sequence, trip.trip_headsign, st.arrival_time, rpl.prediction_target_time, rpl.predicted_delay_seconds
            from gtfs_static.gtfs_stops s
            inner join gtfs_static.gtfs_stop_times st USING (stop_id)
            inner join gtfs_static.gtfs_trips_static trip USING (trip_id)
            left join gtfs_realtime.regional_predictions_latest rpl
            on rpl.stop_id = st.stop_id
                and rpl.route_id = trip.route_id
                and rpl.prediction_target_time <= CURRENT_DATE + st.arrival_time
                and rpl.prediction_target_time + interval '1 hour' > CURRENT_DATE + st.arrival_time
            where s.stop_id = '{stop_id}'
                and trip.route_id = '{route_id}'
                and st.arrival_time >= current_time - interval '5 minutes'
            ORDER BY trip.trip_headsign, st.arrival_time;
        """

        return self.db_connector.read_sql(query)