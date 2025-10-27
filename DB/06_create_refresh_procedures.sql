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
