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

    def _convert_timezone_fast(self, df, columns):
        """
        タイムゾーン変換を高速に実行（ベクトル化処理）

        Args:
            df (pd.DataFrame): データフレーム（in-place更新）
            columns (list): 変換対象のカラム名リスト
        """
        for col in columns:
            if col not in df.columns:
                continue

            # すでにdatetime型の場合
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                if df[col].dt.tz is None:
                    df[col] = df[col].dt.tz_localize('UTC').dt.tz_convert('America/Vancouver')
                else:
                    # タイムゾーンが設定されている場合は、Vancouver以外なら変換
                    tz_str = str(df[col].dt.tz)
                    if 'Vancouver' not in tz_str and 'America/Vancouver' != tz_str:
                        df[col] = df[col].dt.tz_convert('America/Vancouver')
            # datetime型でない場合は変換
            else:
                df[col] = pd.to_datetime(df[col], utc=True).dt.tz_convert('America/Vancouver')

    def get_gtfs_data(self, route_id=None, start_date='20250818', end_date=None):
        """
        バンクーバー遅延予測用GTFSデータを取得

        Args:
            route_id (str or list): 路線ID（単一文字列または複数IDのリスト）
            start_date (str): 開始日 (YYYYMMDD形式)
            end_date (str, optional): 終了日 (YYYYMMDD形式)。指定しない場合は制限なし

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
        print(f"Date range: {start_date}" + (f" to {end_date}" if end_date else " (no end limit)"))
        print(f"Data source: Analytics MV (fully processed)")

        gtfs_data = self._get_from_analytics_mv(route_id_list, start_date)

        print("Successfully retrieved raw data.")
        
        # タイムゾーン変換（ベクトル化された高速処理）
        self._convert_timezone_fast(gtfs_data, ['datetime', 'datetime_60'])

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
        import time

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
                arrival_delay,
                -- 統計特徴量 (事前計算済み)
                delay_mean_by_stop_datetime,
                -- 時系列特徴量 (事前計算済み)
                hour_of_day,
                hour_sin,
                hour_cos,
                day_sin,
                day_cos,
                is_peak_hour,
                is_weekend,
                -- 地理的特徴量 (事前計算済み)
                region_id,
                distance_from_downtown_km,
                lat_sin,
                lat_cos,
                lon_sin,
                lon_cos,
                lat_relative,
                lon_relative,
                area_density_score
            FROM gtfs_realtime.gtfs_rt_analytics_mv
            """
        # route_id_listがNoneの場合はフィルターを適用しない
        if route_id_list is None:
            gtfs_query += """
            WHERE start_date >= %(start_date)s
            ORDER BY route_id, direction_id, start_date, trip_id, line_direction_link_order
            """
            params = {'start_date': start_date}
        else:
            gtfs_query += """
            WHERE route_id = ANY(%(route_ids)s)
              AND start_date >= %(start_date)s
            ORDER BY route_id, direction_id, start_date, trip_id, line_direction_link_order
            """
            params = {'route_ids': route_id_list, 'start_date': start_date}

        # 詳細なタイミング計測
        start_time = time.time()
        print("  [1/3] Executing SQL query...")

        # データ型を明示的に指定して高速化
        dtype_spec = {
            'day_of_week': 'int16',
            'line_direction_link_order': 'int16',
            'trip_id': 'str',
            'stop_id': 'str',
            'start_date': 'str',
            'route_id': 'str',
            'direction_id': 'int8',
            'arrival_delay': 'float32',
            'delay_mean_by_stop_datetime': 'float32',
            'hour_of_day': 'int8',
            'hour_sin': 'float32',
            'hour_cos': 'float32',
            'day_sin': 'float32',
            'day_cos': 'float32',
            'is_peak_hour': 'bool',
            'is_weekend': 'bool',
            'region_id': 'str',
            'distance_from_downtown_km': 'float32',
            'lat_sin': 'float32',
            'lat_cos': 'float32',
            'lon_sin': 'float32',
            'lon_cos': 'float32',
            'lat_relative': 'float32',
            'lon_relative': 'float32',
            'area_density_score': 'float32'
        }

        result = self.db_connector.read_sql(
            gtfs_query,
            params=params,
            parse_dates=['datetime', 'datetime_60'],
            convert_tz=False,  # 後でまとめて変換するのでここではスキップ
            debug=True  # デバッグ情報を表示
            # use_server_cursor は逆効果なので無効化
        )

        query_time = time.time() - start_time
        print(f"  [2/3] SQL executed in {query_time:.2f}s, converting dtypes...")

        # データ型変換
        dtype_start = time.time()
        for col, dtype in dtype_spec.items():
            if col in result.columns:
                try:
                    result[col] = result[col].astype(dtype)
                except:
                    pass  # 変換失敗時はスキップ

        dtype_time = time.time() - dtype_start
        print(f"  [3/3] Dtype conversion done in {dtype_time:.2f}s")
        print(f"  Total time: {time.time() - start_time:.2f}s")

        return result

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
