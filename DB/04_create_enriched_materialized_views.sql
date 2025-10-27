-- Active: 1760926936747@@interchange.proxy.rlwy.net@49078@railway
-- =============================================================================
-- Enhanced Stops Materialized View with Geographic Features
-- =============================================================================
-- Purpose: Pre-compute geographic features for stops to improve analytics performance
-- Features:
--   - Distance from downtown Vancouver (49.2827, -123.1207)
--   - Trigonometric encodings for latitude/longitude (for ML models)
--   - Relative coordinates from downtown
-- Refresh: Should be refreshed when gtfs_stops data changes (infrequent)
-- =============================================================================

CREATE MATERIALIZED VIEW gtfs_static.gtfs_stops_enhanced_mv AS
SELECT
    s.stop_id,
    s.stop_code,
    s.stop_name,
    s.stop_desc,
    s.stop_lat,
    s.stop_lon,
    s.zone_id,
    s.stop_url,
    s.location_type,
    s.parent_station,
    s.wheelchair_boarding,
    -- Region info from spatial join with regions table (replaces s.region_id)
    r.region_id,
    r.region_name,
    r.region_type,
    -- ダウンタウンバンクーバーからの距離 (Haversine formula)
    -- Downtown Vancouver: 49.2827°N, 123.1207°W
    ROUND(
        (6371 * ACOS(
            LEAST(1.0, GREATEST(-1.0,
                SIN(RADIANS(49.2827)) * SIN(RADIANS(s.stop_lat)) +
                COS(RADIANS(49.2827)) * COS(RADIANS(s.stop_lat)) *
                COS(RADIANS(s.stop_lon - (-123.1207)))
            ))
        ))::NUMERIC,
        2
    ) AS distance_from_downtown_km,
    -- 緯度の三角関数エンコーディング（周期性を保持）
    ROUND(SIN(RADIANS(s.stop_lat))::NUMERIC, 6) AS lat_sin,
    ROUND(COS(RADIANS(s.stop_lat))::NUMERIC, 6) AS lat_cos,
    -- 経度の三角関数エンコーディング（周期性を保持）
    ROUND(SIN(RADIANS(s.stop_lon))::NUMERIC, 6) AS lon_sin,
    ROUND(COS(RADIANS(s.stop_lon))::NUMERIC, 6) AS lon_cos,
    -- ダウンタウンからの相対座標
    ROUND((s.stop_lat - 49.2827)::NUMERIC, 6) AS lat_relative,
    ROUND((s.stop_lon - (-123.1207))::NUMERIC, 6) AS lon_relative,
    -- ゾーン分類
    CASE
        WHEN r.region_id IN ('vancouver', 'burnaby', 'new_westminster')
            AND 6371 * ACOS(
            LEAST(1.0, GREATEST(-1.0,
                SIN(RADIANS(49.2827)) * SIN(RADIANS(s.stop_lat)) +
                COS(RADIANS(49.2827)) * COS(RADIANS(s.stop_lat)) *
                COS(RADIANS(s.stop_lon - (-123.1207)))
            ))
        ) <= 5 THEN 5
        WHEN r.region_id IN ('vancouver', 'burnaby', 'richmond', 'new_westminster', 'north_vancouver_city', 'north_vancouver_district')
             THEN 4
        WHEN r.region_id IN ('surrey', 'coquitlam', 'port_coquitlam', 'port_moody', 'west_vancouver', 'delta')
             THEN 3
        WHEN r.region_id IN ('langley_city', 'langley_township', 'maple_ridge', 'pitt_meadows', 'white_rock')
             THEN 2
        WHEN r.region_id IN ('lions_bay', 'belcarra', 'anmore', 'bowen_island')
             THEN 1
        ELSE 0
    END AS area_density_score
FROM gtfs_static.gtfs_stops s
LEFT JOIN gtfs_static.regions r
    ON ST_Contains(r.boundary, ST_SetSRID(ST_MakePoint(s.stop_lon::DOUBLE PRECISION, s.stop_lat::DOUBLE PRECISION), 4326));

-- =============================================================================
-- Indexes for Enhanced Stops MV
-- =============================================================================

-- Primary lookup index
CREATE UNIQUE INDEX IF NOT EXISTS idx_stops_enhanced_stop_id
ON gtfs_static.gtfs_stops_enhanced_mv (stop_id);

-- Geographic search indexes
CREATE INDEX IF NOT EXISTS idx_stops_enhanced_distance
ON gtfs_static.gtfs_stops_enhanced_mv (distance_from_downtown_km);

-- Region index
CREATE INDEX IF NOT EXISTS idx_stops_enhanced_region_id
ON gtfs_static.gtfs_stops_enhanced_mv (region_id);

-- Common join patterns
CREATE INDEX IF NOT EXISTS idx_stops_enhanced_stop_name
ON gtfs_static.gtfs_stops_enhanced_mv (stop_name);

-- =============================================================================
-- Refresh Function
-- =============================================================================

CREATE OR REPLACE FUNCTION gtfs_static.refresh_stops_enhanced_mv()
RETURNS TABLE(
    status TEXT,
    rows_affected BIGINT,
    execution_time INTERVAL
) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    row_count BIGINT;
BEGIN
    start_time := clock_timestamp();
    
    REFRESH MATERIALIZED VIEW CONCURRENTLY gtfs_static.gtfs_stops_enhanced_mv;
    
    GET DIAGNOSTICS row_count = ROW_COUNT;
    end_time := clock_timestamp();
    
    -- Log the refresh
    INSERT INTO gtfs_static.mv_refresh_log (mv_name, last_refresh, row_count, execution_time)
    VALUES ('gtfs_stops_enhanced_mv', end_time, row_count, end_time - start_time);
    
    RETURN QUERY SELECT 
        'SUCCESS'::TEXT,
        row_count,
        end_time - start_time;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Refresh Log Table (create if not exists)
-- =============================================================================

CREATE TABLE IF NOT EXISTS gtfs_static.mv_refresh_log (
    id SERIAL PRIMARY KEY,
    mv_name TEXT NOT NULL,
    last_refresh TIMESTAMP NOT NULL DEFAULT NOW(),
    row_count BIGINT,
    execution_time INTERVAL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mv_refresh_log_mv_name 
ON gtfs_static.mv_refresh_log (mv_name, last_refresh DESC);

-- =============================================================================
-- Initial refresh
-- =============================================================================

REFRESH MATERIALIZED VIEW gtfs_static.gtfs_stops_enhanced_mv;
ANALYZE gtfs_static.gtfs_stops_enhanced_mv;

-- Display creation summary
SELECT
    'gtfs_stops_enhanced_mv' AS materialized_view,
    COUNT(*) AS total_stops,
    pg_size_pretty(pg_total_relation_size('gtfs_static.gtfs_stops_enhanced_mv')) AS size,
    'Created successfully' AS status
FROM gtfs_static.gtfs_stops_enhanced_mv;

-- =============================================================================
-- Active Service Dates Materialized View
-- =============================================================================
-- Purpose: Pre-compute active service_ids for each date to optimize calendar lookups
-- Features:
--   - Combines calendar.txt weekly patterns with calendar_dates.txt exceptions
--   - Handles exception_type correctly (1=add, 2=remove)
--   - Includes service_id validation against start_date/end_date
-- Performance: Eliminates need for complex calendar logic in real-time queries
-- Refresh: Should be refreshed daily or when GTFS static data updates
-- =============================================================================

CREATE MATERIALIZED VIEW gtfs_static.gtfs_active_service_dates_mv AS
WITH date_series AS (
    -- Generate date series from earliest start_date to latest end_date + 1 year
    SELECT generate_series(
        (SELECT MIN(start_date) FROM gtfs_static.gtfs_calendar),
        (SELECT MAX(end_date) FROM gtfs_static.gtfs_calendar) + INTERVAL '1 year',
        '1 day'::interval
    )::date AS service_date
),
calendar_services AS (
    -- Get service_ids active on each date based on calendar.txt
    SELECT
        ds.service_date,
        c.service_id
    FROM date_series ds
    CROSS JOIN gtfs_static.gtfs_calendar c
    WHERE ds.service_date BETWEEN c.start_date AND c.end_date
      AND (
          (EXTRACT(DOW FROM ds.service_date) = 0 AND c.sunday = 1) OR
          (EXTRACT(DOW FROM ds.service_date) = 1 AND c.monday = 1) OR
          (EXTRACT(DOW FROM ds.service_date) = 2 AND c.tuesday = 1) OR
          (EXTRACT(DOW FROM ds.service_date) = 3 AND c.wednesday = 1) OR
          (EXTRACT(DOW FROM ds.service_date) = 4 AND c.thursday = 1) OR
          (EXTRACT(DOW FROM ds.service_date) = 5 AND c.friday = 1) OR
          (EXTRACT(DOW FROM ds.service_date) = 6 AND c.saturday = 1)
      )
),
added_services AS (
    -- Get service_ids explicitly added via calendar_dates.txt
    SELECT
        date AS service_date,
        service_id
    FROM gtfs_static.gtfs_calendar_dates
    WHERE exception_type = 1
),
removed_services AS (
    -- Get service_ids explicitly removed via calendar_dates.txt
    SELECT
        date AS service_date,
        service_id
    FROM gtfs_static.gtfs_calendar_dates
    WHERE exception_type = 2
),
combined_services AS (
    -- Combine calendar services with added services
    SELECT service_date, service_id FROM calendar_services
    UNION
    SELECT service_date, service_id FROM added_services
)
-- Final result: active services excluding removed ones
SELECT
    cs.service_date,
    cs.service_id,
    -- Add day of week for easier filtering
    EXTRACT(DOW FROM cs.service_date)::INTEGER AS day_of_week,
    -- Add day name for debugging
    TO_CHAR(cs.service_date, 'Day') AS day_name,
    -- Add flags for weekend/weekday
    CASE
        WHEN EXTRACT(DOW FROM cs.service_date) IN (0, 6) THEN true
        ELSE false
    END AS is_weekend
FROM combined_services cs
WHERE NOT EXISTS (
    -- Exclude services that are removed on this date
    SELECT 1
    FROM removed_services rs
    WHERE rs.service_date = cs.service_date
      AND rs.service_id = cs.service_id
)
ORDER BY cs.service_date, cs.service_id;

-- =============================================================================
-- Indexes for Active Service Dates MV
-- =============================================================================

-- Primary lookup index for date + service_id
CREATE UNIQUE INDEX IF NOT EXISTS idx_active_service_dates_date_service
ON gtfs_static.gtfs_active_service_dates_mv (service_date, service_id);

-- Index for date-only lookups (most common use case)
CREATE INDEX IF NOT EXISTS idx_active_service_dates_date
ON gtfs_static.gtfs_active_service_dates_mv (service_date);

-- Index for service_id lookups
CREATE INDEX IF NOT EXISTS idx_active_service_dates_service_id
ON gtfs_static.gtfs_active_service_dates_mv (service_id);

-- Index for weekend queries
CREATE INDEX IF NOT EXISTS idx_active_service_dates_weekend
ON gtfs_static.gtfs_active_service_dates_mv (is_weekend, service_date);

-- =============================================================================
-- Refresh Function for Active Service Dates MV
-- =============================================================================

CREATE OR REPLACE FUNCTION gtfs_static.refresh_active_service_dates_mv()
RETURNS TABLE(
    status TEXT,
    rows_affected BIGINT,
    execution_time INTERVAL
) AS $$
DECLARE
    start_time TIMESTAMP;
    end_time TIMESTAMP;
    row_count BIGINT;
BEGIN
    start_time := clock_timestamp();

    REFRESH MATERIALIZED VIEW CONCURRENTLY gtfs_static.gtfs_active_service_dates_mv;

    GET DIAGNOSTICS row_count = ROW_COUNT;
    end_time := clock_timestamp();

    -- Log the refresh
    INSERT INTO gtfs_static.mv_refresh_log (mv_name, last_refresh, row_count, execution_time)
    VALUES ('gtfs_active_service_dates_mv', end_time, row_count, end_time - start_time);

    RETURN QUERY SELECT
        'SUCCESS'::TEXT,
        row_count,
        end_time - start_time;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Initial refresh
-- =============================================================================

REFRESH MATERIALIZED VIEW gtfs_static.gtfs_active_service_dates_mv;
ANALYZE gtfs_static.gtfs_active_service_dates_mv;

-- Display creation summary
SELECT
    'gtfs_active_service_dates_mv' AS materialized_view,
    COUNT(*) AS total_service_dates,
    COUNT(DISTINCT service_date) AS unique_dates,
    COUNT(DISTINCT service_id) AS unique_services,
    MIN(service_date) AS earliest_date,
    MAX(service_date) AS latest_date,
    pg_size_pretty(pg_total_relation_size('gtfs_static.gtfs_active_service_dates_mv')) AS size,
    'Created successfully' AS status
FROM gtfs_static.gtfs_active_service_dates_mv;