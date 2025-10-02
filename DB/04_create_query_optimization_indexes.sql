-- Active: 1754501684937@@localhost@5432@postgres
-- =====================================================
-- Query Optimization Indexes for GTFS Realtime
-- Purpose: Optimize gtfs_data_retriever.py queries
-- =====================================================

-- 1. Materialized View用の複合インデックス（最重要）
-- gtfs_data_retriever.pyのクエリに最適化
CREATE INDEX IF NOT EXISTS idx_gtfs_rt_mv_query_optimization
ON gtfs_realtime.gtfs_rt_stop_time_updates_mv
(route_id, start_date, trip_id, stop_sequence)
WHERE arrival_delay IS NOT NULL;

-- 2. route_id + start_date でのフィルタリング用
CREATE INDEX IF NOT EXISTS idx_gtfs_rt_mv_route_date
ON gtfs_realtime.gtfs_rt_stop_time_updates_mv
(route_id, start_date)
INCLUDE (arrival_delay, stop_sequence);

-- 3. arrival_delay範囲検索用（部分インデックス）
CREATE INDEX IF NOT EXISTS idx_gtfs_rt_mv_arrival_delay
ON gtfs_realtime.gtfs_rt_stop_time_updates_mv
(arrival_delay)
WHERE arrival_delay BETWEEN -3600 AND 3600;

-- 4. ソート最適化用
CREATE INDEX IF NOT EXISTS idx_gtfs_rt_mv_sort_optimization
ON gtfs_realtime.gtfs_rt_stop_time_updates_mv
(route_id, direction_id, start_date, trip_id, stop_sequence);

-- 5. JOIN最適化用インデックス
-- trip_descriptors: route_id検索の高速化
CREATE INDEX IF NOT EXISTS idx_trip_descriptors_route_direction
ON gtfs_realtime.gtfs_rt_trip_descriptors(route_id, direction_id, start_date);

-- stop_time_updates: JOIN最適化
CREATE INDEX IF NOT EXISTS idx_stop_time_updates_trip_update
ON gtfs_realtime.gtfs_rt_stop_time_updates(trip_update_id, stop_sequence);

-- trip_updates: JOIN最適化
CREATE INDEX IF NOT EXISTS idx_trip_updates_descriptor
ON gtfs_realtime.gtfs_rt_trip_updates(trip_descriptor_id);