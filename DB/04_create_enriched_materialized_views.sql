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
    s.*,
    -- Region ID from spatial join with regions table
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