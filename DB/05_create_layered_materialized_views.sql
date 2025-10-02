-- =====================================================
-- Layered Materialized Views for GTFS Realtime
-- Purpose: 3-tier architecture for optimal performance
-- =====================================================
-- Created: 2025-10-01
-- Version: 2.0
-- =====================================================

-- =====================================================
-- LAYER 1: Base Realtime Data (gtfs_rt_base_mv)
-- =====================================================
-- Purpose: Fast-changing realtime data only
-- Refresh: High frequency (every 15-30 minutes)
-- Size: Large but focused on realtime tables only
-- =====================================================

DROP MATERIALIZED VIEW IF EXISTS gtfs_realtime.gtfs_rt_base_mv CASCADE;

CREATE MATERIALIZED VIEW gtfs_realtime.gtfs_rt_base_mv AS
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
    to_timestamp(fh.timestamp_seconds) as update_time
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
  AND stu.arrival_time IS NOT NULL;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_gtfs_rt_base_mv_unique
ON gtfs_realtime.gtfs_rt_base_mv (trip_id, stop_sequence, start_date);

-- Performance indexes
CREATE INDEX idx_gtfs_rt_base_mv_route_date
ON gtfs_realtime.gtfs_rt_base_mv (route_id, start_date);

CREATE INDEX idx_gtfs_rt_base_mv_date
ON gtfs_realtime.gtfs_rt_base_mv (start_date);

ANALYZE gtfs_realtime.gtfs_rt_base_mv;

-- =====================================================
-- LAYER 2: Enriched with Static Data (gtfs_rt_enriched_mv)
-- =====================================================
-- Purpose: Join with slowly-changing static GTFS data
-- Refresh: Medium frequency (every 1-2 hours or when static data changes)
-- Size: Similar to Layer 1 but with additional columns
-- =====================================================

DROP MATERIALIZED VIEW IF EXISTS gtfs_realtime.gtfs_rt_enriched_mv CASCADE;

CREATE MATERIALIZED VIEW gtfs_realtime.gtfs_rt_enriched_mv AS
SELECT
    base.id,
    base.route_id,
    base.trip_id,
    base.start_date,
    base.direction_id,
    base.stop_id,
    base.stop_sequence,
    base.actual_arrival_time,
    base.arrival_delay,
    base.update_time,
    -- Static data enrichment
    r.route_short_name,
    t.trip_headsign,
    s.stop_name,
    st.arrival_time as scheduled_arrival_time,
    -- Derived time features
    EXTRACT(isodow FROM base.start_date::date) as day_of_week,
    DATE_TRUNC('hour', base.actual_arrival_time) as datetime_60
FROM gtfs_realtime.gtfs_rt_base_mv base
INNER JOIN gtfs_static.gtfs_routes r
    ON r.route_id = base.route_id
INNER JOIN gtfs_static.gtfs_trips_static t
    ON t.trip_id = base.trip_id
INNER JOIN gtfs_static.gtfs_stops s
    ON s.stop_id = base.stop_id
INNER JOIN gtfs_static.gtfs_stop_times st
    ON st.trip_id = base.trip_id
    AND st.stop_id = base.stop_id;

-- Performance indexes
CREATE INDEX idx_gtfs_rt_enriched_mv_route_date
ON gtfs_realtime.gtfs_rt_enriched_mv (route_id, start_date);

CREATE INDEX idx_gtfs_rt_enriched_mv_datetime_60
ON gtfs_realtime.gtfs_rt_enriched_mv (datetime_60);

CREATE INDEX idx_gtfs_rt_enriched_mv_query_optimization
ON gtfs_realtime.gtfs_rt_enriched_mv (route_id, start_date, trip_id, stop_sequence);

ANALYZE gtfs_realtime.gtfs_rt_enriched_mv;

-- =====================================================
-- LAYER 3: Analytics-Ready Data (gtfs_rt_analytics_mv)
-- =====================================================
-- Purpose: Fully processed data with all features for ML/analytics
-- Refresh: Low frequency (nightly batch or on-demand)
-- Size: Larger due to additional computed columns
-- =====================================================

DROP MATERIALIZED VIEW IF EXISTS gtfs_realtime.gtfs_rt_analytics_mv CASCADE;

CREATE MATERIALIZED VIEW gtfs_realtime.gtfs_rt_analytics_mv AS
WITH travel_time_calc AS (
    SELECT
        *,
        EXTRACT(EPOCH FROM (
            actual_arrival_time - LAG(actual_arrival_time)
            OVER (PARTITION BY start_date, route_id, trip_id ORDER BY stop_sequence)
        )) as travel_time_raw_seconds
    FROM gtfs_realtime.gtfs_rt_enriched_mv
),
filtered AS (
    SELECT *,
        CASE
            WHEN travel_time_raw_seconds BETWEEN 10 AND 3600
            THEN travel_time_raw_seconds
            ELSE NULL
        END as travel_time_duration
    FROM travel_time_calc
),
route_hour_stats AS (
    SELECT
        route_id,
        direction_id,
        EXTRACT(HOUR FROM actual_arrival_time) as hour_of_day,
        AVG(arrival_delay) as delay_mean_by_route_hour,
        AVG(travel_time_duration) as travel_mean_by_route_hour,
        COUNT(*) as sample_count
    FROM filtered
    WHERE travel_time_duration IS NOT NULL
    GROUP BY route_id, direction_id, EXTRACT(HOUR FROM actual_arrival_time)
    HAVING COUNT(*) >= 5  -- Minimum sample size for statistical validity
)
SELECT
    f.id,
    f.route_id,
    f.trip_id,
    f.start_date,
    f.direction_id,
    f.stop_id,
    f.stop_sequence,
    f.actual_arrival_time,
    f.datetime_60,
    f.arrival_delay,
    f.travel_time_raw_seconds,
    f.travel_time_duration,
    f.route_short_name,
    f.trip_headsign,
    f.stop_name,
    f.scheduled_arrival_time,
    f.day_of_week,
    -- Statistical features (previously computed in Python)
    rhs.delay_mean_by_route_hour,
    rhs.travel_mean_by_route_hour,
    -- Time-based features (previously computed in Python)
    EXTRACT(HOUR FROM f.actual_arrival_time)::INTEGER as hour_of_day,
    SIN(2 * PI() * EXTRACT(HOUR FROM f.actual_arrival_time) / 24) as hour_sin,
    COS(2 * PI() * EXTRACT(HOUR FROM f.actual_arrival_time) / 24) as hour_cos,
    SIN(2 * PI() * f.day_of_week / 7) as day_sin,
    COS(2 * PI() * f.day_of_week / 7) as day_cos,
    -- Categorical time features
    CASE WHEN EXTRACT(HOUR FROM f.actual_arrival_time) IN (7, 8, 17, 18) THEN 1 ELSE 0 END as is_peak_hour,
    CASE WHEN f.day_of_week IN (6, 7) THEN 1 ELSE 0 END as is_weekend,
    CASE
        WHEN EXTRACT(HOUR FROM f.actual_arrival_time) BETWEEN 0 AND 5 THEN 'Late_Night'
        WHEN EXTRACT(HOUR FROM f.actual_arrival_time) BETWEEN 6 AND 8 THEN 'Morning'
        WHEN EXTRACT(HOUR FROM f.actual_arrival_time) BETWEEN 9 AND 11 THEN 'Midday'
        WHEN EXTRACT(HOUR FROM f.actual_arrival_time) BETWEEN 12 AND 16 THEN 'Afternoon'
        WHEN EXTRACT(HOUR FROM f.actual_arrival_time) BETWEEN 17 AND 19 THEN 'Evening'
        ELSE 'Night'
    END as time_period_basic
FROM filtered f
LEFT JOIN route_hour_stats rhs
    ON f.route_id = rhs.route_id
    AND f.direction_id = rhs.direction_id
    AND EXTRACT(HOUR FROM f.actual_arrival_time) = rhs.hour_of_day
WHERE f.travel_time_duration IS NOT NULL
   OR f.travel_time_raw_seconds IS NULL;  -- Keep first stop of each trip

-- Performance indexes
CREATE INDEX idx_gtfs_rt_analytics_mv_route_date
ON gtfs_realtime.gtfs_rt_analytics_mv (route_id, start_date);

CREATE INDEX idx_gtfs_rt_analytics_mv_datetime_60
ON gtfs_realtime.gtfs_rt_analytics_mv (datetime_60);

CREATE INDEX idx_gtfs_rt_analytics_mv_query_optimization
ON gtfs_realtime.gtfs_rt_analytics_mv (route_id, start_date, trip_id, stop_sequence);

CREATE INDEX idx_gtfs_rt_analytics_mv_sort_optimization
ON gtfs_realtime.gtfs_rt_analytics_mv (route_id, direction_id, start_date, trip_id, stop_sequence);

ANALYZE gtfs_realtime.gtfs_rt_analytics_mv;

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
    ('gtfs_rt_base_mv', NOW(), 'success'),
    ('gtfs_rt_enriched_mv', NOW(), 'success'),
    ('gtfs_rt_analytics_mv', NOW(), 'success')
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
FROM gtfs_realtime.gtfs_rt_base_mv
UNION ALL
SELECT
    'gtfs_rt_enriched_mv' as view_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT route_id) as unique_routes,
    COUNT(DISTINCT start_date) as unique_dates,
    MIN(start_date) as earliest_date,
    MAX(start_date) as latest_date,
    pg_size_pretty(pg_total_relation_size('gtfs_realtime.gtfs_rt_enriched_mv')) as total_size
FROM gtfs_realtime.gtfs_rt_enriched_mv
UNION ALL
SELECT
    'gtfs_rt_analytics_mv' as view_name,
    COUNT(*) as row_count,
    COUNT(DISTINCT route_id) as unique_routes,
    COUNT(DISTINCT start_date) as unique_dates,
    MIN(start_date) as earliest_date,
    MAX(start_date) as latest_date,
    pg_size_pretty(pg_total_relation_size('gtfs_realtime.gtfs_rt_analytics_mv')) as total_size
FROM gtfs_realtime.gtfs_rt_analytics_mv;

-- =====================================================
-- Verification queries
-- =====================================================

-- Check all views were created successfully
SELECT
    schemaname,
    matviewname,
    hasindexes,
    ispopulated
FROM pg_matviews
WHERE schemaname = 'gtfs_realtime'
  AND matviewname LIKE 'gtfs_rt_%_mv'
ORDER BY matviewname;

-- View statistics
SELECT * FROM gtfs_realtime.mv_statistics;

-- Check refresh log
SELECT * FROM gtfs_realtime.mv_refresh_log ORDER BY view_name;