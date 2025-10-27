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
-- PROCEDURE 2: GTFS Static Views Refresh
-- =====================================================
-- Use: Refresh GTFS static materialized views
-- Should be run after loading new GTFS static data
-- =====================================================

CREATE OR REPLACE PROCEDURE gtfs_static.refresh_static_views()
LANGUAGE plpgsql
AS $$
DECLARE
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
    duration NUMERIC;
    row_cnt BIGINT;
BEGIN
    RAISE NOTICE 'Starting static views refresh at %', NOW();

    -- Refresh Active Service Dates MV
    start_time := clock_timestamp();
    BEGIN
        RAISE NOTICE 'Refreshing gtfs_active_service_dates_mv...';
        REFRESH MATERIALIZED VIEW CONCURRENTLY gtfs_static.gtfs_active_service_dates_mv;
        GET DIAGNOSTICS row_cnt = ROW_COUNT;
        end_time := clock_timestamp();
        duration := EXTRACT(EPOCH FROM (end_time - start_time));

        INSERT INTO gtfs_static.mv_refresh_log (mv_name, last_refresh, row_count, execution_time)
        VALUES ('gtfs_active_service_dates_mv', end_time, row_cnt, end_time - start_time)
        ON CONFLICT (mv_name, last_refresh) DO NOTHING;

        ANALYZE gtfs_static.gtfs_active_service_dates_mv;
        RAISE NOTICE 'Active Service Dates MV refreshed: % rows in % seconds', row_cnt, ROUND(duration, 2);
    EXCEPTION WHEN OTHERS THEN
        RAISE WARNING 'Failed to refresh gtfs_active_service_dates_mv: %', SQLERRM;
    END;

    -- Refresh Stops Enhanced MV
    start_time := clock_timestamp();
    BEGIN
        RAISE NOTICE 'Refreshing gtfs_stops_enhanced_mv...';
        REFRESH MATERIALIZED VIEW CONCURRENTLY gtfs_static.gtfs_stops_enhanced_mv;
        GET DIAGNOSTICS row_cnt = ROW_COUNT;
        end_time := clock_timestamp();
        duration := EXTRACT(EPOCH FROM (end_time - start_time));

        INSERT INTO gtfs_static.mv_refresh_log (mv_name, last_refresh, row_count, execution_time)
        VALUES ('gtfs_stops_enhanced_mv', end_time, row_cnt, end_time - start_time)
        ON CONFLICT (mv_name, last_refresh) DO NOTHING;

        ANALYZE gtfs_static.gtfs_stops_enhanced_mv;
        RAISE NOTICE 'Stops Enhanced MV refreshed: % rows in % seconds', row_cnt, ROUND(duration, 2);
    EXCEPTION WHEN OTHERS THEN
        RAISE WARNING 'Failed to refresh gtfs_stops_enhanced_mv: %', SQLERRM;
    END;

    RAISE NOTICE 'Static views refresh completed at %', NOW();
END;
$$;

-- =====================================================
-- Helper Functions
-- =====================================================

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
