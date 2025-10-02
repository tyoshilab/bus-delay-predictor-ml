"""
Regional Bus Delay Prediction API

Vancouver全域やMetro Vancouverの地域別遅延情報を返すAPI
実際のMetro Vancouver地域境界データ（23自治体）を使用
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).parent))
from src.data_connection import DatabaseConnector


# =====================================
# 1. 地域管理クラス（データベースベース）
# =====================================

class RegionManager:
    """地域境界管理（PostgreSQLベース）"""

    def __init__(self, db_connector: DatabaseConnector):
        self.db_connector = db_connector
        self._regions_cache = None

    def load_regions(self) -> pd.DataFrame:
        """
        データベースから地域情報をロード

        Returns:
            region_id, region_name, region_type等を含むDataFrame
        """
        if self._regions_cache is not None:
            return self._regions_cache

        query = """
        SELECT
            region_id,
            region_name,
            region_type,
            center_lat,
            center_lon,
            area_km2,
            population
        FROM gtfs_static.regions
        ORDER BY region_name
        """

        self._regions_cache = self.db_connector.read_sql(query)
        return self._regions_cache

    def get_region_info(self, region_id: str) -> Optional[Dict]:
        """
        特定地域の情報を取得

        Args:
            region_id: 地域ID（例: 'vancouver', 'burnaby'）

        Returns:
            地域情報の辞書、または None
        """
        regions = self.load_regions()
        region = regions[regions['region_id'] == region_id]

        if region.empty:
            return None

        return region.iloc[0].to_dict()

    def list_all_regions(self) -> List[Dict]:
        """
        全地域の一覧を取得

        Returns:
            地域情報のリスト
        """
        regions = self.load_regions()
        return regions.to_dict('records')

    def get_stops_in_region(self, region_id: str) -> pd.DataFrame:
        """
        指定地域内のバス停を取得

        Args:
            region_id: 地域ID

        Returns:
            地域内のバス停データ
        """
        query = f"""
        SELECT
            stop_id,
            stop_name,
            stop_lat,
            stop_lon
        FROM gtfs_static.stops_with_regions_mv
        WHERE region_id = '{region_id}'
        """

        return self.db_connector.read_sql(query)


# =====================================
# 2. 地域別遅延集約クラス
# =====================================

class RegionalDelayAggregator:
    """地域別の遅延データ集約"""

    def __init__(self, db_connector: DatabaseConnector, region_manager: RegionManager):
        self.db_connector = db_connector
        self.region_manager = region_manager

    def get_regional_delay_stats(
        self,
        region_id: str,
        lookback_hours: int = 168  # Default: 7 days
    ) -> pd.DataFrame:
        """
        地域別の遅延統計を取得（時間別）

        Args:
            region_id: 地域ID
            lookback_hours: 過去何時間分取得するか（デフォルト168時間=7日）

        Returns:
            時間帯別の遅延統計
        """
        # regional_delays_hourly_mv から取得
        query = f"""
        SELECT
            time_bucket,
            day_of_week,
            hour_of_day,
            trip_count,
            avg_delay_seconds / 60.0 as avg_delay_minutes,
            median_delay_seconds / 60.0 as median_delay_minutes,
            p25_delay_seconds / 60.0 as p25_delay_minutes,
            p75_delay_seconds / 60.0 as p75_delay_minutes,
            delay_stddev / 60.0 as delay_stddev_minutes,
            ontime,
            delay_1_to_5min,
            delay_5_to_10min,
            delay_over_10min,
            early_over_1min,
            weekend_ratio,
            peak_hour_ratio
        FROM gtfs_realtime.regional_delays_hourly_mv
        WHERE region_id = '{region_id}'
          AND time_bucket >= NOW() - INTERVAL '{lookback_hours} hours'
        ORDER BY time_bucket DESC
        """

        return self.db_connector.read_sql(query)

    def get_recent_status(self, region_id: str) -> Optional[Dict]:
        """
        地域の直近状況を取得（最新1時間）

        Args:
            region_id: 地域ID

        Returns:
            直近の遅延状況
        """
        query = f"""
        SELECT
            time_bucket,
            avg_delay_minutes,
            median_delay_minutes,
            delay_status,
            delay_over_5min_pct,
            trip_count
        FROM gtfs_realtime.regional_delays_recent_mv
        WHERE region_id = '{region_id}'
        ORDER BY time_bucket DESC
        LIMIT 1
        """

        result = self.db_connector.read_sql(query)

        if result.empty:
            return None

        return result.iloc[0].to_dict()


# =====================================
# 3. 地域別遅延予測API
# =====================================

class RegionalDelayPredictionAPI:
    """地域別バス遅延予測API"""

    def __init__(self):
        self.db_connector = DatabaseConnector()
        self.region_manager = RegionManager(self.db_connector)
        self.aggregator = RegionalDelayAggregator(self.db_connector, self.region_manager)

    def predict_regional_delay(
        self,
        region_id: str,
        forecast_hours: int = 3,
        lookback_days: int = 7
    ) -> Dict:
        """
        地域別の遅延予測

        Args:
            region_id: 地域ID (例: "vancouver", "burnaby", "richmond")
            forecast_hours: 予測時間数（デフォルト3時間）
            lookback_days: 過去データ参照日数

        Returns:
            地域別遅延予測結果
        """
        # 地域情報取得
        region = self.region_manager.get_region_info(region_id)
        if not region:
            available = [r['region_id'] for r in self.region_manager.list_all_regions()]
            raise ValueError(
                f"Unknown region: {region_id}. Available regions: {available}"
            )

        # 過去の遅延統計を取得
        lookback_hours = lookback_days * 24
        delay_stats = self.aggregator.get_regional_delay_stats(
            region_id,
            lookback_hours=lookback_hours
        )

        if delay_stats.empty:
            return {
                "region_id": region_id,
                "region_name": region['region_name'],
                "error": "No data available for this region",
                "predictions": []
            }

        # 簡易予測: 同じ曜日・時間帯の過去平均を使用
        current_time = datetime.now()
        predictions = []

        for hour_offset in range(1, forecast_hours + 1):
            forecast_time = current_time + timedelta(hours=hour_offset)

            # 同じ曜日・時間帯のデータでフィルタ
            forecast_dow = forecast_time.weekday()  # 0=Monday, 6=Sunday
            forecast_hour = forecast_time.hour

            # 過去の同じ時間帯のデータから予測
            similar_periods = delay_stats[
                delay_stats['hour_of_day'] == forecast_hour
            ]

            if not similar_periods.empty:
                avg_delay = similar_periods['avg_delay_minutes'].mean()
                median_delay = similar_periods['median_delay_minutes'].median()

                # 5分以上遅延の確率を計算
                total_trips = similar_periods['trip_count'].sum()
                delay_5min = similar_periods['delay_5_to_10min'].sum() + \
                            similar_periods['delay_over_10min'].sum()
                delay_5min_prob = (delay_5min / total_trips * 100) if total_trips > 0 else 0
            else:
                # データがない場合は全体平均
                avg_delay = delay_stats['avg_delay_minutes'].mean()
                median_delay = delay_stats['median_delay_minutes'].median()
                delay_5min_prob = 0

            predictions.append({
                "forecast_time": forecast_time.strftime("%Y-%m-%d %H:%M:%S"),
                "hour_of_day": forecast_hour,
                "day_of_week": forecast_dow,
                "avg_delay_minutes": round(float(avg_delay), 2),
                "median_delay_minutes": round(float(median_delay), 2),
                "probability_delay_over_5min": round(float(delay_5min_prob), 1),
                "status": self._classify_delay_status(avg_delay)
            })

        return {
            "region_id": region_id,
            "region_name": region['region_name'],
            "region_type": region.get('region_type'),
            "current_time": current_time.strftime("%Y-%m-%d %H:%M:%S"),
            "lookback_period_days": lookback_days,
            "predictions": predictions,
            "summary": {
                "avg_delay_next_3h": round(
                    np.mean([p['avg_delay_minutes'] for p in predictions]), 2
                ),
                "overall_status": self._classify_delay_status(
                    np.mean([p['avg_delay_minutes'] for p in predictions])
                )
            }
        }

    def get_all_regions_status(self, forecast_hours: int = 1) -> Dict:
        """
        全地域の遅延状況を取得

        Args:
            forecast_hours: 予測時間（デフォルト1時間後）

        Returns:
            全地域の遅延状況
        """
        results = []

        regions = self.region_manager.list_all_regions()

        for region in regions:
            region_id = region['region_id']

            try:
                # 直近の状況を取得
                recent_status = self.aggregator.get_recent_status(region_id)

                if recent_status:
                    results.append({
                        "region_id": region_id,
                        "region_name": region['region_name'],
                        "region_type": region.get('region_type'),
                        "status": recent_status['delay_status'],
                        "avg_delay_minutes": round(float(recent_status['avg_delay_minutes']), 2),
                        "last_updated": recent_status['time_bucket'].strftime("%Y-%m-%d %H:%M:%S"),
                        "trip_count": int(recent_status['trip_count'])
                    })
                else:
                    results.append({
                        "region_id": region_id,
                        "region_name": region['region_name'],
                        "region_type": region.get('region_type'),
                        "status": "no_data",
                        "avg_delay_minutes": None,
                        "last_updated": None,
                        "trip_count": 0
                    })
            except Exception as e:
                results.append({
                    "region_id": region_id,
                    "region_name": region['region_name'],
                    "region_type": region.get('region_type'),
                    "status": "error",
                    "error": str(e)
                })

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_regions": len(results),
            "regions": results
        }

    def get_regional_ranking(self) -> Dict:
        """
        地域別パフォーマンスランキングを取得

        Returns:
            地域別ランキング
        """
        query = """
        SELECT
            region_id,
            region_name,
            region_type,
            avg_delay_minutes,
            median_delay_minutes,
            ontime_rate_pct_7d,
            performance_rank,
            ontime_rank,
            performance_grade,
            active_routes,
            active_stops,
            total_trips
        FROM gtfs_realtime.regional_performance_ranking_mv
        ORDER BY performance_rank
        """

        df = self.db_connector.read_sql(query)

        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "period": "last_7_days",
            "rankings": df.to_dict('records')
        }

    @staticmethod
    def _classify_delay_status(avg_delay_minutes: float) -> str:
        """遅延状況を分類"""
        if avg_delay_minutes < 1:
            return "excellent"  # ほぼ定時
        elif avg_delay_minutes < 3:
            return "good"       # 軽微な遅延
        elif avg_delay_minutes < 5:
            return "moderate"   # 中程度の遅延
        elif avg_delay_minutes < 10:
            return "poor"       # 大きな遅延
        else:
            return "severe"     # 深刻な遅延


# =====================================
# 4. 使用例
# =====================================

def example_usage():
    """APIの使用例"""
    import json

    api = RegionalDelayPredictionAPI()

    # 例1: 利用可能な地域一覧
    print("=" * 70)
    print("Example 1: Available Regions")
    print("=" * 70)

    regions = api.region_manager.list_all_regions()
    for r in regions[:10]:  # 最初の10地域
        print(f"  {r['region_id']:25s} - {r['region_name']}")

    # 例2: Vancouver の3時間予測
    print("\n" + "=" * 70)
    print("Example 2: Vancouver - 3 Hour Forecast")
    print("=" * 70)

    result = api.predict_regional_delay(
        region_id="vancouver",
        forecast_hours=3,
        lookback_days=7
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 例3: 全地域の現在状況
    print("\n" + "=" * 70)
    print("Example 3: All Regions Status")
    print("=" * 70)

    all_regions = api.get_all_regions_status(forecast_hours=1)

    # 上位10地域のみ表示
    for region in all_regions['regions'][:10]:
        status = region.get('status', 'unknown')
        delay = region.get('avg_delay_minutes')
        delay_str = f"{delay:.1f}min" if delay else "N/A"
        print(f"  {region['region_name']:40s} → {status:10s} ({delay_str})")

    # 例4: 地域別パフォーマンスランキング
    print("\n" + "=" * 70)
    print("Example 4: Regional Performance Ranking (Top 10)")
    print("=" * 70)

    ranking = api.get_regional_ranking()

    print(f"Period: {ranking['period']}")
    print(f"Timestamp: {ranking['timestamp']}\n")

    for r in ranking['rankings'][:10]:
        print(f"{r['performance_rank']:2d}. {r['region_name']:40s} "
              f"Grade: {r['performance_grade']:2s}  "
              f"Avg Delay: {r['avg_delay_minutes']:.2f}min  "
              f"On-time: {r['ontime_rate_pct_7d']:.1f}%")


if __name__ == "__main__":
    example_usage()
