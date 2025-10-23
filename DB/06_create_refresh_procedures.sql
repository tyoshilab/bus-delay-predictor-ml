-- =====================================================
-- Materialized View Refresh Procedures
-- Purpose: Intelligent refresh strategies for layered MVs
-- =====================================================
-- Created: 2025-10-01
-- Version: 2.0
-- =====================================================

-- =====================================================
-- PROCEDURE 1: Based View Refresh
-- =====================================================
-- Use: Refresh base GTFS Realtime MV
-- =====================================================

CREATE OR REPLACE PROCEDURE gtfs_realtime.refresh_gtfs_views_staged()
LANGUAGE plpgsql
AS $$
DECLARE
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
    duration NUMERIC;
    row_cnt BIGINT;
BEGIN
    RAISE NOTICE 'Starting staged refresh at %', NOW();

    -- Refresh Base MV
    start_time := clock_timestamp();
    UPDATE gtfs_realtime.mv_refresh_log
    SET status = 'in_progress', updated_at = NOW()
    WHERE view_name = 'gtfs_rt_base_mv';

    BEGIN
        SET work_mem = '128MB';
        REFRESH MATERIALIZED VIEW gtfs_realtime.gtfs_rt_base_mv;
        RESET work_mem;
        GET DIAGNOSTICS row_cnt = ROW_COUNT;
        end_time := clock_timestamp();
        duration := EXTRACT(EPOCH FROM (end_time - start_time));

        UPDATE gtfs_realtime.mv_refresh_log
        SET last_refresh_time = end_time,
            refresh_duration_seconds = duration,
            rows_affected = row_cnt,
            status = 'success',
            error_message = NULL,
            updated_at = NOW()
        WHERE view_name = 'gtfs_rt_base_mv';

        ANALYZE gtfs_realtime.gtfs_rt_base_mv;
        RAISE NOTICE 'Base MV refreshed: % rows in % seconds', row_cnt, ROUND(duration, 2);
    EXCEPTION WHEN OTHERS THEN
        UPDATE gtfs_realtime.mv_refresh_log
        SET status = 'failed', error_message = SQLERRM, updated_at = NOW()
        WHERE view_name = 'gtfs_rt_base_mv';
        RAISE;
    END;
    RAISE NOTICE 'Staged refresh completed at %', NOW();
END;
$$;

-- =====================================================
-- PROCEDURE 5: Archive Old Data (Modified for ML)
-- =====================================================
-- Use: Archive old data from MVs while keeping base data for model training
-- Duration: Varies
-- Strategy: Only clean MVs, NOT base tables (preserve training data)
-- =====================================================

CREATE OR REPLACE PROCEDURE gtfs_realtime.archive_old_gtfs_mv_data(
    mv_retention_days INTEGER DEFAULT 90
)
LANGUAGE plpgsql
AS $$
DECLARE
    cutoff_date TEXT;
    archived_count BIGINT := 0;
BEGIN
    cutoff_date := to_char(CURRENT_DATE - mv_retention_days, 'YYYYMMDD');

    RAISE NOTICE 'Archiving MV data older than % (% days retention)', cutoff_date, mv_retention_days;
    RAISE NOTICE 'NOTE: Base tables are preserved for ML model training';

    -- Strategy: Recreate MVs with date filter instead of deleting base data
    -- This keeps all historical data in base tables for model training

    -- Drop and recreate analytics MV with date filter
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
        WHERE start_date >= cutoff_date  -- Only keep recent data in MV
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
        HAVING COUNT(*) >= 5
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
        rhs.delay_mean_by_route_hour,
        rhs.travel_mean_by_route_hour,
        EXTRACT(HOUR FROM f.actual_arrival_time)::INTEGER as hour_of_day,
        SIN(2 * PI() * EXTRACT(HOUR FROM f.actual_arrival_time) / 24) as hour_sin,
        COS(2 * PI() * EXTRACT(HOUR FROM f.actual_arrival_time) / 24) as hour_cos,
        SIN(2 * PI() * f.day_of_week / 7) as day_sin,
        COS(2 * PI() * f.day_of_week / 7) as day_cos,
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
       OR f.travel_time_raw_seconds IS NULL;

    -- Recreate indexes
    CREATE INDEX idx_gtfs_rt_analytics_mv_route_date
    ON gtfs_realtime.gtfs_rt_analytics_mv (route_id, start_date);

    CREATE INDEX idx_gtfs_rt_analytics_mv_datetime_60
    ON gtfs_realtime.gtfs_rt_analytics_mv (datetime_60);

    CREATE INDEX idx_gtfs_rt_analytics_mv_query_optimization
    ON gtfs_realtime.gtfs_rt_analytics_mv (route_id, start_date, trip_id, stop_sequence);

    CREATE INDEX idx_gtfs_rt_analytics_mv_sort_optimization
    ON gtfs_realtime.gtfs_rt_analytics_mv (route_id, direction_id, start_date, trip_id, stop_sequence);

    GET DIAGNOSTICS archived_count = ROW_COUNT;

    RAISE NOTICE 'Analytics MV now contains % rows (data >= %)', archived_count, cutoff_date;
    RAISE NOTICE 'Base tables remain unchanged - all historical data preserved for ML training';

    -- Update refresh log
    UPDATE gtfs_realtime.mv_refresh_log
    SET last_refresh_time = NOW(),
        rows_affected = archived_count,
        status = 'success',
        updated_at = NOW()
    WHERE view_name = 'gtfs_rt_analytics_mv';

    -- Analyze
    ANALYZE gtfs_realtime.gtfs_rt_analytics_mv;

    RAISE NOTICE 'Archive completed at %', NOW();
END;
$$;

-- =====================================================
-- Helper Functions
-- =====================================================

-- Check if refresh is needed based on data freshness
CREATE OR REPLACE FUNCTION gtfs_realtime.is_refresh_needed(
    view_name TEXT,
    max_age_minutes INTEGER DEFAULT 60
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    last_refresh TIMESTAMPTZ;
    age_minutes NUMERIC;
BEGIN
    SELECT last_refresh_time INTO last_refresh
    FROM gtfs_realtime.mv_refresh_log
    WHERE mv_refresh_log.view_name = is_refresh_needed.view_name
      AND status = 'success';

    IF last_refresh IS NULL THEN
        RETURN TRUE;
    END IF;

    age_minutes := EXTRACT(EPOCH FROM (NOW() - last_refresh)) / 60;

    RETURN age_minutes > max_age_minutes;
END;
$$;

-- Get refresh status summary
CREATE OR REPLACE FUNCTION gtfs_realtime.get_refresh_status()
RETURNS TABLE (
    view_name TEXT,
    last_refresh TIMESTAMPTZ,
    age_minutes NUMERIC,
    status TEXT,
    rows BIGINT,
    size TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        log.view_name,
        log.last_refresh_time,
        ROUND(EXTRACT(EPOCH FROM (NOW() - log.last_refresh_time)) / 60, 1) as age_minutes,
        log.status,
        log.rows_affected,
        CASE
            WHEN log.view_name = 'gtfs_rt_base_mv' THEN
                pg_size_pretty(pg_total_relation_size('gtfs_realtime.gtfs_rt_base_mv'))
        END as size
    FROM gtfs_realtime.mv_refresh_log log
    ORDER BY log.view_name;
END;
$$;
