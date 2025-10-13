"""
GTFSデータ取得クラス v2.0
最適化版: Layered Materialized Viewsを使用
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class GTFSDataRetrieverV2:
    """GTFSデータ取得用クラス (最適化版)"""

    def __init__(self, db_connector):
        """
        Args:
            db_connector (DatabaseConnector): データベース接続オブジェクト
        """
        self.db_connector = db_connector

    def get_gtfs_data(self, route_id=None, start_date='20250818', use_analytics_mv=True):
        """
        バンクーバー遅延予測用GTFSデータを取得

        Args:
            route_id (str or list): 路線ID（単一文字列または複数IDのリスト）
            start_date (str): 開始日 (YYYYMMDD形式)
            use_analytics_mv (bool): Analytics MVを使用するか（False=Enriched MVのみ）

        Returns:
            pd.DataFrame: GTFSデータ
        """
        # route_idの正規化（文字列の場合はリストに変換）
        if isinstance(route_id, str):
            route_id_list = [route_id]
        elif isinstance(route_id, list):
            route_id_list = route_id
        else:
            route_id_list = None

        print(f"Retrieving Vancouver delay prediction GTFS data for routes: {route_id_list}...")
        print(f"Data source: {'Analytics MV (fully processed)' if use_analytics_mv else 'Enriched MV (minimal processing)'}")

        if use_analytics_mv:
            # Analytics MV: すべての特徴量が事前計算済み
            gtfs_data = self._get_from_analytics_mv(route_id_list, start_date)
        else:
            # Enriched MV: 基本的な特徴量のみ（Python側で追加処理が必要）
            gtfs_data = self._get_from_enriched_mv(route_id_list, start_date)

        # タイムゾーン変換
        if 'datetime' in gtfs_data.columns:
            # datetime型でない場合は変換
            if not pd.api.types.is_datetime64_any_dtype(gtfs_data['datetime']):
                gtfs_data['datetime'] = pd.to_datetime(gtfs_data['datetime'])
            # タイムゾーンがない場合はUTCとして扱い、Vancouverに変換
            if gtfs_data['datetime'].dt.tz is None:
                gtfs_data['datetime'] = gtfs_data['datetime'].dt.tz_localize('UTC').dt.tz_convert('America/Vancouver')
            else:
                gtfs_data['datetime'] = gtfs_data['datetime'].dt.tz_convert('America/Vancouver')

        if 'datetime_60' in gtfs_data.columns:
            # datetime型でない場合は変換
            if not pd.api.types.is_datetime64_any_dtype(gtfs_data['datetime_60']):
                gtfs_data['datetime_60'] = pd.to_datetime(gtfs_data['datetime_60'])
            # タイムゾーンがない場合はUTCとして扱い、Vancouverに変換
            if gtfs_data['datetime_60'].dt.tz is None:
                gtfs_data['datetime_60'] = gtfs_data['datetime_60'].dt.tz_localize('UTC').dt.tz_convert('America/Vancouver')
            else:
                gtfs_data['datetime_60'] = gtfs_data['datetime_60'].dt.tz_convert('America/Vancouver')

        print(f"Retrieved {len(gtfs_data):,} records")
        return gtfs_data

    def _get_from_analytics_mv(self, route_id_list, start_date):
        """
        Analytics MVから完全に処理済みのデータを取得

        特徴:
        - すべての統計特徴量・時系列特徴量が事前計算済み
        - Python側での集約処理が不要
        - 最も高速だが、MVの更新頻度に依存
        """
        gtfs_query = """
            SELECT
                actual_arrival_time as datetime,
                datetime_60,
                day_of_week,
                stop_sequence as line_direction_link_order,
                trip_id,
                stop_id,
                start_date,
                route_id,
                direction_id,
                travel_time_raw_seconds,
                arrival_delay,
                travel_time_duration,
                -- 統計特徴量 (事前計算済み)
                delay_mean_by_route_hour,
                delay_mean_by_stop_hour,
                travel_mean_by_route_hour,
                -- 時系列特徴量 (事前計算済み)
                hour_of_day,
                hour_sin,
                hour_cos,
                day_sin,
                day_cos,
                is_peak_hour,
                is_weekend,
                time_period_basic,
                -- 地理的特徴量 (事前計算済み)
                stop_lat,
                stop_lon,
                region_id,
                distance_from_downtown_km,
                lat_sin,
                lat_cos,
                lon_sin,
                lon_cos,
                lat_relative,
                lon_relative,
                area_type,
                area_density_score
            FROM gtfs_realtime.gtfs_rt_analytics_mv
            """
        # route_id_listがNoneの場合はフィルターを適用しない
        if route_id_list is None:
            gtfs_query += """
            WHERE start_date >= %(start_date)s
              AND travel_time_duration IS NOT NULL
            ORDER BY route_id, direction_id, start_date, trip_id, line_direction_link_order
            """
            params = {'start_date': start_date}
        else:
            gtfs_query += """
            WHERE route_id = ANY(%(route_ids)s)
              AND start_date >= %(start_date)s
              AND travel_time_duration IS NOT NULL
            ORDER BY route_id, direction_id, start_date, trip_id, line_direction_link_order
            """
            params = {'route_ids': route_id_list, 'start_date': start_date}
        
        return self.db_connector.read_sql(gtfs_query, params=params)

    def _get_from_enriched_mv(self, route_id_list, start_date):
        """
        Enriched MVから基本データを取得（レガシー互換用）

        特徴:
        - 基本的な特徴量のみ
        - 統計特徴量・時系列特徴量はPython側で計算が必要
        - より新鮮なデータが必要な場合に使用
        """
        gtfs_query = """
        WITH travel_time_calc AS (
            SELECT
                *,
                EXTRACT(EPOCH FROM (
                    actual_arrival_time - LAG(actual_arrival_time)
                    OVER (PARTITION BY start_date, route_id, trip_id ORDER BY stop_sequence)
                )) as travel_time_raw_seconds
            FROM gtfs_realtime.gtfs_rt_enriched_mv
            WHERE route_id = ANY(%(route_ids)s)
              AND start_date >= %(start_date)s
        ),
        filtered AS (
            SELECT *,
                CASE
                    WHEN travel_time_raw_seconds BETWEEN 10 AND 3600
                    THEN travel_time_raw_seconds
                    ELSE NULL
                END as travel_time_duration
            FROM travel_time_calc
            WHERE arrival_delay BETWEEN -3600 AND 3600
        )
        SELECT
            actual_arrival_time as datetime,
            datetime_60,
            day_of_week,
            stop_sequence as line_direction_link_order,
            trip_id,
            stop_id,
            start_date,
            route_id,
            direction_id,
            travel_time_raw_seconds,
            arrival_delay,
            travel_time_duration
        FROM filtered
        WHERE travel_time_duration IS NOT NULL
           OR travel_time_raw_seconds IS NULL
        ORDER BY route_id, direction_id, start_date, trip_id, line_direction_link_order
        """

        params = {'route_ids': route_id_list, 'start_date': start_date}
        return self.db_connector.read_sql(gtfs_query, params=params)

    def get_gtfs_data_summary(self, route_id=['6612'], start_date='20250818'):
        """
        データのサマリー統計を取得（データ量の確認用）

        Args:
            route_id (str or list): 路線ID
            start_date (str): 開始日 (YYYYMMDD形式)

        Returns:
            pd.DataFrame: サマリー統計
        """
        if isinstance(route_id, str):
            route_id_list = [route_id]
        else:
            route_id_list = route_id

        summary_query = """
        SELECT
            route_id,
            COUNT(*) as total_records,
            COUNT(DISTINCT start_date) as unique_dates,
            COUNT(DISTINCT trip_id) as unique_trips,
            COUNT(DISTINCT stop_id) as unique_stops,
            MIN(start_date) as earliest_date,
            MAX(start_date) as latest_date,
            AVG(arrival_delay) as avg_delay,
            STDDEV(arrival_delay) as stddev_delay,
            AVG(travel_time_duration) as avg_travel_time,
            COUNT(*) FILTER (WHERE arrival_delay > 300) as late_records,
            COUNT(*) FILTER (WHERE arrival_delay < -300) as early_records
        FROM gtfs_realtime.gtfs_rt_analytics_mv
        WHERE route_id = ANY(%(route_ids)s)
          AND start_date >= %(start_date)s
        GROUP BY route_id
        ORDER BY route_id
        """

        params = {'route_ids': route_id_list, 'start_date': start_date}
        summary = self.db_connector.read_sql(summary_query, params=params)

        print("\n=== GTFS Data Summary ===")
        print(summary.to_string(index=False))
        print("=========================\n")

        return summary

    def check_mv_freshness(self):
        """
        Materialized Viewの更新状況を確認

        Returns:
            pd.DataFrame: 各MVの最終更新時刻と状態
        """
        freshness_query = """
        SELECT * FROM gtfs_realtime.get_refresh_status()
        ORDER BY view_name
        """

        freshness = self.db_connector.read_sql(freshness_query)

        print("\n=== Materialized View Freshness ===")
        print(freshness.to_string(index=False))
        print("====================================\n")

        return freshness

    def get_available_routes(self, start_date='20250818', min_records=1000):
        """
        利用可能な路線リストを取得

        Args:
            start_date (str): 開始日 (YYYYMMDD形式)
            min_records (int): 最小レコード数（この数以上のデータがある路線のみ返す）

        Returns:
            pd.DataFrame: 路線リストとデータ量
        """
        routes_query = """
        SELECT
            route_id,
            route_short_name,
            COUNT(*) as record_count,
            COUNT(DISTINCT start_date) as date_count,
            MIN(start_date) as earliest_date,
            MAX(start_date) as latest_date
        FROM gtfs_realtime.gtfs_rt_analytics_mv
        WHERE start_date >= %(start_date)s
        GROUP BY route_id, route_short_name
        HAVING COUNT(*) >= %(min_records)s
        ORDER BY record_count DESC
        """

        params = {'start_date': start_date, 'min_records': min_records}
        routes = self.db_connector.read_sql(routes_query, params=params)

        print(f"\n=== Available Routes (>= {min_records:,} records) ===")
        print(routes.to_string(index=False))
        print("=" * 60 + "\n")

        return routes

    def get_date_range_coverage(self, route_id=['6612']):
        """
        特定路線の日付カバレッジを確認

        Args:
            route_id (str or list): 路線ID

        Returns:
            pd.DataFrame: 日付別のレコード数
        """
        if isinstance(route_id, str):
            route_id_list = [route_id]
        else:
            route_id_list = route_id

        coverage_query = """
        SELECT
            start_date,
            COUNT(*) as record_count,
            COUNT(DISTINCT trip_id) as trip_count,
            AVG(arrival_delay) as avg_delay
        FROM gtfs_realtime.gtfs_rt_analytics_mv
        WHERE route_id = ANY(%(route_ids)s)
        GROUP BY start_date
        ORDER BY start_date DESC
        LIMIT 30
        """

        params = {'route_ids': route_id_list}
        coverage = self.db_connector.read_sql(coverage_query, params=params)

        print("\n=== Date Range Coverage (Last 30 dates) ===")
        print(coverage.to_string(index=False))
        print("=" * 60 + "\n")

        return coverage


# Backward compatibility: alias for legacy code
GTFSDataRetriever = GTFSDataRetrieverV2


if __name__ == "__main__":
    # テスト用コード
    from data_connection import DatabaseConnector

    db_connector = DatabaseConnector()
    retriever = GTFSDataRetrieverV2(db_connector)

    # MVの鮮度チェック
    retriever.check_mv_freshness()

    # 利用可能な路線を確認
    available_routes = retriever.get_available_routes(start_date='20250818', min_records=500)

    # データ取得テスト
    if len(available_routes) > 0:
        test_route = available_routes.iloc[0]['route_id']
        print(f"Testing data retrieval for route: {test_route}")

        # サマリー取得
        summary = retriever.get_gtfs_data_summary(route_id=test_route, start_date='20250818')

        # 日付カバレッジ確認
        coverage = retriever.get_date_range_coverage(route_id=test_route)

        # 実データ取得
        data = retriever.get_gtfs_data(route_id=test_route, start_date='20250818')
        print(f"\nRetrieved {len(data):,} records")
        print(f"Columns: {list(data.columns)}")
        print(f"\nFirst few records:")
        print(data.head())
