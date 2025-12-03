-- =====================================================
-- Layered Materialized Views for GTFS Realtime
-- Purpose: 3-tier architecture for optimal performance
-- =====================================================
-- Created: 2025-10-01
-- Version: 2.1 (Optimized - removes redundant geographic calculations)
-- Changes:
--   - Enriched MV now uses gtfs_stops_enhanced_mv for pre-computed geo features
--   - Analytics MV removes all redundant geographic calculations
--   - Significant performance improvement in analytics MV creation
-- =====================================================

-- =====================================================
-- Base Realtime Data (gtfs_rt_base_mv)
-- =====================================================
-- Purpose: Fast-changing realtime data only
-- Refresh: High frequency (every 15-30 minutes)
-- Size: Large but focused on realtime tables only
-- =====================================================

DROP MATERIALIZED VIEW IF EXISTS gtfs_realtime.gtfs_rt_base_mv CASCADE;

CREATE MATERIALIZED VIEW gtfs_realtime.gtfs_rt_base_mv AS
WITH latest_updates AS (
    SELECT
        stu.id,
        td.route_id,
        td.trip_id,
        td.start_date,
        td.direction_id,
        stu.stop_id,
        stu.stop_sequence,
        to_timestamp(stu.arrival_time) as actual_arrival_time,
        stu.arrival_delay,
        to_timestamp(fh.timestamp_seconds) as update_time,
        ROW_NUMBER() OVER (
            PARTITION BY td.trip_id, stu.stop_sequence, td.start_date
            ORDER BY fh.timestamp_seconds DESC
        ) as rn
    FROM gtfs_realtime.gtfs_rt_stop_time_updates stu
    INNER JOIN gtfs_realtime.gtfs_rt_trip_updates tu
        ON stu.trip_update_id = tu.trip_update_id
    INNER JOIN gtfs_realtime.gtfs_rt_trip_descriptors td
        ON tu.trip_descriptor_id = td.trip_descriptor_id
    INNER JOIN gtfs_realtime.gtfs_rt_feed_entities fe
        ON tu.feed_entity_id = fe.id
    INNER JOIN gtfs_realtime.gtfs_rt_feed_messages fm
        ON fe.feed_message_id = fm.id
    INNER JOIN gtfs_realtime.gtfs_rt_feed_headers fh
        ON fm.id = fh.feed_message_id
    WHERE stu.arrival_delay BETWEEN -3600 AND 3600  -- Filter obvious outliers early
      AND stu.arrival_time IS NOT NULL
      AND to_timestamp(fh.timestamp_seconds) >= CURRENT_TIMESTAMP - INTERVAL '24 hours'  -- ← 24時間制限
)
SELECT
    id,
    route_id,
    trip_id,
    start_date,
    direction_id,
    stop_id,
    stop_sequence,
    actual_arrival_time,
    arrival_delay,
    update_time
FROM latest_updates
WHERE rn = 1;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_gtfs_rt_base_mv_unique
ON gtfs_realtime.gtfs_rt_base_mv (trip_id, stop_sequence, start_date);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_gtfs_rt_base_mv_route_date
ON gtfs_realtime.gtfs_rt_base_mv (route_id, start_date);

CREATE INDEX IF NOT EXISTS idx_gtfs_rt_base_mv_date
ON gtfs_realtime.gtfs_rt_base_mv (start_date);

ANALYZE gtfs_realtime.gtfs_rt_base_mv;

-- =====================================================
-- Base Realtime Data (gtfs_rt_base_v)
-- =====================================================
-- Purpose: View to aggregate raw realtime data with delay calculations
-- =====================================================

drop VIEW IF EXISTS gtfs_realtime.gtfs_rt_base_v;

CREATE or REPLACE VIEW gtfs_realtime.gtfs_rt_base_v AS
with tmp as (select 
    td.route_id, 
    td.trip_id, 
    td.start_date, 
    st.arrival_day_offset,
    td.direction_id, 
    st.stop_id, 
    st.stop_sequence,
    s.region_id,
    s.stop_lat,
    s.stop_lon,    
    gtfs_static.get_stop_actual_time(
        td.start_date::date,
        st.arrival_time,
        st.arrival_day_offset
    ) as scheduled_arrival_time,
    to_timestamp(vp.timestamp_seconds) as actual_arrival_time
    from gtfs_realtime.gtfs_rt_trip_descriptors td
    inner join gtfs_realtime.gtfs_rt_vehicle_positions vp using(trip_descriptor_id)
    inner join gtfs_static.gtfs_stop_times st
    on st.trip_id = td.trip_id and st.stop_sequence = vp.current_stop_sequence
    inner join gtfs_static.gtfs_stops_enhanced_mv s 
    on st.stop_id = s.stop_id
WHERE vp.timestamp_seconds >= EXTRACT(EPOCH FROM (current_timestamp - interval '2 hour'))::bigint
)
select 
    tmp.*
    , extract(EPOCH from tmp.actual_arrival_time - tmp.scheduled_arrival_time)::int as arrival_delay
    , DATE_TRUNC('hour', scheduled_arrival_time) as time_bucket
    , EXTRACT(HOUR FROM scheduled_arrival_time)::INTEGER as hour_of_day
    , EXTRACT(isodow FROM start_date::date) as day_of_week
from tmp;

-- =====================================================
-- Analytics-Ready Data view (gtfs_rt_analytics_mv)
-- =====================================================
-- Purpose: Fully processed data with all features for analytics
-- =====================================================

CREATE OR REPLACE VIEW gtfs_realtime.gtfs_rt_analytics_mv AS 
WITH enriched_data AS (
    SELECT
        base.id,
        base.route_id,
        base.trip_id,
        base.start_date,
        base.direction_id,
        base.stop_id,
        base.stop_sequence,
        base.actual_arrival_time,
        EXTRACT(HOUR FROM base.actual_arrival_time)::INTEGER as hour_of_day,
        SIN(2 * PI() * EXTRACT(HOUR FROM base.actual_arrival_time) / 24) as hour_sin,
        COS(2 * PI() * EXTRACT(HOUR FROM base.actual_arrival_time) / 24) as hour_cos,
        SIN(2 * PI() * EXTRACT(isodow FROM base.start_date::date) / 7) as day_sin,
        COS(2 * PI() * EXTRACT(isodow FROM base.start_date::date) / 7) as day_cos,
        CASE WHEN EXTRACT(HOUR FROM base.actual_arrival_time) IN (7, 8, 17, 18) THEN 1 ELSE 0 END as is_peak_hour,
        CASE WHEN EXTRACT(isodow FROM base.start_date::date) IN (6, 7) THEN 1 ELSE 0 END as is_weekend,
        base.arrival_delay,
        base.update_time,
        -- Static data enrichment
        r.route_short_name,
        t.trip_headsign,
        se.stop_name,
        se.stop_lat,
        se.stop_lon,
        se.region_id,
        st.arrival_time as scheduled_arrival_time,
        -- Derived time features
        EXTRACT(isodow FROM base.start_date::date) as day_of_week,
        DATE_TRUNC('hour', base.actual_arrival_time) as datetime_60,
        -- Pre-computed geographic features from enhanced stops MV
        se.distance_from_downtown_km,
        se.lat_sin,
        se.lat_cos,
        se.lon_sin,
        se.lon_cos,
        se.lat_relative,
        se.lon_relative,
        se.area_density_score
    FROM gtfs_realtime.gtfs_rt_base_mv base
    INNER JOIN gtfs_static.gtfs_routes r ON r.route_id = base.route_id
    INNER JOIN gtfs_static.gtfs_trips_static t ON t.trip_id = base.trip_id
    INNER JOIN gtfs_static.gtfs_stops_enhanced_mv se ON se.stop_id = base.stop_id
    INNER JOIN gtfs_static.gtfs_stop_times st ON st.trip_id = base.trip_id AND st.stop_id = base.stop_id
), 
route_hour_stats AS (
    SELECT enriched_data.route_id,
        enriched_data.direction_id,
        enriched_data.hour_of_day,
        avg(enriched_data.arrival_delay) AS delay_mean_by_route_hour,
        count(*) AS sample_count
    FROM enriched_data
    GROUP BY enriched_data.route_id, enriched_data.direction_id, enriched_data.hour_of_day
    HAVING (count(*) >= 5)
)
SELECT f.*,
    rhs.delay_mean_by_route_hour
FROM enriched_data f
LEFT JOIN route_hour_stats rhs 
ON f.route_id = rhs.route_id AND f.direction_id = rhs.direction_id AND f.hour_of_day = rhs.hour_of_day;


-- =====================================================
-- Metadata Table for Refresh Tracking
-- =====================================================

CREATE TABLE IF NOT EXISTS gtfs_realtime.mv_refresh_log (
    view_name TEXT PRIMARY KEY,
    last_refresh_time TIMESTAMPTZ,
    refresh_duration_seconds NUMERIC,
    rows_affected BIGINT,
    status TEXT,  -- 'success', 'failed', 'in_progress'
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize log entries
INSERT INTO gtfs_realtime.mv_refresh_log (view_name, last_refresh_time, status)
VALUES
    ('gtfs_rt_base_mv', NOW(), 'success')
ON CONFLICT (view_name) DO UPDATE
SET last_refresh_time = NOW(),
    status = 'success',
    updated_at = NOW();

-- =====================================================
-- Statistics Summary View
-- =====================================================

CREATE OR REPLACE VIEW gtfs_realtime.mv_statistics AS
SELECT
    'gtfs_rt_base_mv' as view_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT route_id) as unique_routes,
    COUNT(DISTINCT start_date) as unique_dates,
    MIN(start_date) as earliest_date,
    MAX(start_date) as latest_date,
    pg_size_pretty(pg_total_relation_size('gtfs_realtime.gtfs_rt_base_mv')) as total_size
FROM gtfs_realtime.gtfs_rt_base_mv;