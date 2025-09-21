"""
GTFSデータ取得クラス
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

class GTFSDataRetriever:
    """GTFSデータ取得用クラス"""
    
    def __init__(self, db_connector):
        """
        Args:
            db_connector (DatabaseConnector): データベース接続オブジェクト
        """
        self.db_connector = db_connector
    
    def get_gtfs_data(self, route_id=['6612'], start_date='20250818'):
        """
        バンクーバー遅延予測用GTFSデータを取得
        
        Args:
            route_id (str or list): 路線ID（単一文字列または複数IDのリスト）
            start_date (str): 開始日 (YYYYMMDD形式)
            
        Returns:
            pd.DataFrame: GTFSデータ
        """
        # route_idの正規化（文字列の場合はリストに変換）
        if isinstance(route_id, str):
            route_id_list = [route_id]
        else:
            route_id_list = route_id
        
        # IN句用のプレースホルダー作成
        route_placeholders = ', '.join(['%(route_id_{})s'.format(i) for i in range(len(route_id_list))])
        
        gtfs_query = f"""
        WITH base_data AS (
            SELECT 
                actual_arrival_time as datetime, 
                EXTRACT(isodow FROM start_date::date) as day_of_week,
                stop_sequence as line_direction_link_order,
                trip_id,
                stop_id,
                start_date,
                route_id,
                direction_id,
                
                -- 区間所要時間計算（基本的な外れ値除去付き）
                CASE  
                    WHEN LAG(actual_arrival_time) OVER (PARTITION BY start_date, route_id, trip_id ORDER BY stop_sequence) IS NOT NULL
                    THEN EXTRACT(EPOCH FROM (actual_arrival_time - LAG(actual_arrival_time) OVER (PARTITION BY start_date, route_id, trip_id ORDER BY stop_sequence)))
                    ELSE NULL
                END as travel_time_raw_seconds,
                
                -- 遅延時間（予測目標）: 正=遅延、負=早着
                arrival_delay,
                
                -- 基本的な時間特徴量をSQL側で生成
                EXTRACT(hour FROM actual_arrival_time) as hour_of_day,
                DATE_TRUNC('hour', actual_arrival_time) as datetime_60,
                
                -- 時間帯カテゴリの基本分類
                CASE 
                    WHEN EXTRACT(hour FROM actual_arrival_time) BETWEEN 0 AND 4 THEN 6  -- Late Night
                    WHEN EXTRACT(hour FROM actual_arrival_time) BETWEEN 5 AND 7 THEN 1  -- Morning Peak
                    WHEN EXTRACT(hour FROM actual_arrival_time) BETWEEN 8 AND 11 THEN 2  -- Daytime
                    WHEN EXTRACT(hour FROM actual_arrival_time) BETWEEN 12 AND 15 THEN 3  -- Evening
                    WHEN EXTRACT(hour FROM actual_arrival_time) BETWEEN 16 AND 18 THEN 4  -- Night Peak
                    ELSE 5  -- Midnight
                END as time_period_basic
                
            FROM gtfs_realtime.gtfs_rt_stop_time_updates_mv
            WHERE route_id IN ({route_placeholders})
              AND start_date >= %(start_date)s
              -- SQL側で明らかな異常値を事前除去
              AND arrival_delay IS NOT NULL
              AND arrival_delay BETWEEN -3600 AND 3600  -- ±1時間以内の遅延のみ
        ),
        filtered_data AS (
            SELECT *,
                -- フィルタ後の移動時間
                CASE 
                    WHEN travel_time_raw_seconds IS NOT NULL 
                         AND travel_time_raw_seconds BETWEEN 10 AND 3600  -- 10秒〜1時間
                    THEN travel_time_raw_seconds
                    ELSE NULL
                END as travel_time_duration
            FROM base_data
        )
        SELECT *
        FROM filtered_data
        WHERE travel_time_duration IS NOT NULL OR travel_time_raw_seconds IS NULL
        ORDER BY route_id, direction_id, start_date, trip_id, line_direction_link_order
        """
        
        # パラメータ辞書の構築
        params = {'start_date': start_date}
        for i, rid in enumerate(route_id_list):
            params[f'route_id_{i}'] = rid
        
        route_ids_str = ', '.join(route_id_list)
        print(f"Retrieving Vancouver delay prediction GTFS data for routes: {route_ids_str}...")
        
        gtfs_data = self.db_connector.read_sql(gtfs_query, params=params)
        
        # タイムゾーン変換
        gtfs_data['datetime'] = gtfs_data['datetime'].dt.tz_convert('America/Vancouver')
        gtfs_data['datetime_60'] = gtfs_data['datetime_60'].dt.tz_convert('America/Vancouver')
        
        return gtfs_data
