-- =====================================================
-- Regional Delay Aggregation Views
-- =====================================================
--
-- Purpose: 地域別の遅延統計マテリアライズドビューを作成
--
-- Prerequisites:
--   1. DB/09_create_region_boundaries.sql executed
--   2. gtfs_realtime.gtfs_rt_analytics_mv exists
--   3. gtfs_static.regions table populated
--
-- Usage:
--   psql -d <database> -f DB/10_create_regional_delay_views.sql
-- =====================================================

-- =====================================================
-- 1. 地域別遅延統計MV（時間単位集約）
-- =====================================================

DROP MATERIALIZED VIEW IF EXISTS gtfs_realtime.regional_delays_hourly_mv CASCADE;

CREATE MATERIALIZED VIEW gtfs_realtime.regional_delays_hourly_mv AS
SELECT
    r.region_id,
    r.region_name,
    r.region_type,
    DATE_TRUNC('hour', a.datetime_60) as time_bucket,
    EXTRACT(DOW FROM a.datetime_60) as day_of_week,
    EXTRACT(HOUR FROM a.datetime_60) as hour_of_day,
    -- Trip統計
    COUNT(DISTINCT a.trip_id) as trip_count,
    COUNT(DISTINCT a.route_id) as route_count,
    COUNT(DISTINCT a.stop_id) as stop_count,
    -- 遅延統計（秒単位）
    AVG(a.arrival_delay) as avg_delay_seconds,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.arrival_delay) as median_delay_seconds,
    PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY a.arrival_delay) as p25_delay_seconds,
    PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY a.arrival_delay) as p75_delay_seconds,
    MIN(a.arrival_delay) as min_delay_seconds,
    MAX(a.arrival_delay) as max_delay_seconds,
    STDDEV(a.arrival_delay) as delay_stddev,
    -- 遅延レベル別カウント
    COUNT(CASE WHEN a.arrival_delay < -60 THEN 1 END) as early_over_1min,
    COUNT(CASE WHEN a.arrival_delay BETWEEN -60 AND 60 THEN 1 END) as ontime,
    COUNT(CASE WHEN a.arrival_delay > 60 AND a.arrival_delay <= 300 THEN 1 END) as delay_1_to_5min,
    COUNT(CASE WHEN a.arrival_delay > 300 AND a.arrival_delay <= 600 THEN 1 END) as delay_5_to_10min,
    COUNT(CASE WHEN a.arrival_delay > 600 THEN 1 END) as delay_over_10min,
    -- 運行時間統計
    AVG(a.travel_time_duration) as avg_travel_time,
    -- 時間帯・天候特徴（型に関係なく動作）
    AVG(a.is_weekend::integer) as weekend_ratio,
    AVG(a.is_peak_hour::integer) as peak_hour_ratio,
    -- データ品質
    COUNT(*) as total_records,
    MIN(a.start_date) as earliest_date,
    MAX(a.start_date) as latest_date
FROM gtfs_realtime.gtfs_rt_analytics_mv a
JOIN gtfs_static.gtfs_stops s ON a.stop_id = s.stop_id
JOIN gtfs_static.regions r ON s.region_id = r.region_id
WHERE a.arrival_delay IS NOT NULL
  AND a.start_date::TIMESTAMP >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY
    r.region_id,
    r.region_name,
    r.region_type,
    datetime_60,
    day_of_week,
    hour_of_day;

-- インデックス作成
CREATE INDEX idx_regional_delays_hourly_time
    ON gtfs_realtime.regional_delays_hourly_mv(time_bucket DESC);

CREATE INDEX idx_regional_delays_hourly_region
    ON gtfs_realtime.regional_delays_hourly_mv(region_id, time_bucket DESC);

CREATE INDEX idx_regional_delays_hourly_dow_hour
    ON gtfs_realtime.regional_delays_hourly_mv(region_id, day_of_week, hour_of_day);

COMMENT ON MATERIALIZED VIEW gtfs_realtime.regional_delays_hourly_mv
    IS '地域別・時間別の遅延統計（過去90日分）';

-- =====================================================
-- 2. 地域別デイリーサマリMV
-- =====================================================

DROP MATERIALIZED VIEW IF EXISTS gtfs_realtime.regional_delays_daily_mv CASCADE;

CREATE MATERIALIZED VIEW gtfs_realtime.regional_delays_daily_mv AS
SELECT
    r.region_id,
    r.region_name,
    r.region_type,
    a.start_date::date as date,
    EXTRACT(DOW FROM a.start_date::date) as day_of_week,
    -- Trip統計
    COUNT(DISTINCT a.trip_id) as trip_count,
    COUNT(DISTINCT a.route_id) as route_count,
    -- 遅延統計
    AVG(a.arrival_delay) / 60.0 as avg_delay_minutes,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.arrival_delay) / 60.0 as median_delay_minutes,
    STDDEV(a.arrival_delay) / 60.0 as delay_stddev_minutes,
    -- 定時率（±1分以内）
    ROUND(
        COUNT(CASE WHEN ABS(a.arrival_delay) <= 60 THEN 1 END)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100,
        2
    ) as ontime_rate_pct,
    -- 遅延率（5分以上）
    ROUND(
        COUNT(CASE WHEN a.arrival_delay > 300 THEN 1 END)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100,
        2
    ) as delay_over_5min_pct,
    -- 平均運行時間
    AVG(a.travel_time_duration) / 60.0 as avg_travel_time_minutes,

    COUNT(*) as total_records

FROM gtfs_realtime.gtfs_rt_analytics_mv a
JOIN gtfs_static.gtfs_stops s ON a.stop_id = s.stop_id
JOIN gtfs_static.regions r ON s.region_id = r.region_id
WHERE a.arrival_delay IS NOT NULL
  AND a.start_date::TIMESTAMP >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY
    r.region_id,
    r.region_name,
    r.region_type,
    date,
    day_of_week;

-- インデックス作成
CREATE INDEX idx_regional_delays_daily_date
    ON gtfs_realtime.regional_delays_daily_mv(date DESC);

CREATE INDEX idx_regional_delays_daily_region
    ON gtfs_realtime.regional_delays_daily_mv(region_id, date DESC);

COMMENT ON MATERIALIZED VIEW gtfs_realtime.regional_delays_daily_mv
    IS '地域別デイリー遅延サマリ（過去90日分）';

-- =====================================================
-- 3. 地域別リアルタイム状況ビュー（直近24時間）
-- =====================================================

DROP MATERIALIZED VIEW IF EXISTS gtfs_realtime.regional_delays_recent_mv CASCADE;

CREATE MATERIALIZED VIEW gtfs_realtime.regional_delays_recent_mv AS
SELECT
    r.region_id,
    r.region_name,
    DATE_TRUNC('hour', a.datetime_60) as time_bucket,
    -- 簡易統計
    COUNT(DISTINCT a.trip_id) as trip_count,
    AVG(a.arrival_delay) / 60.0 as avg_delay_minutes,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.arrival_delay) / 60.0 as median_delay_minutes,
    -- 遅延分類
    CASE
        WHEN AVG(a.arrival_delay) < 60 THEN 'excellent'
        WHEN AVG(a.arrival_delay) < 180 THEN 'good'
        WHEN AVG(a.arrival_delay) < 300 THEN 'moderate'
        WHEN AVG(a.arrival_delay) < 600 THEN 'poor'
        ELSE 'severe'
    END as delay_status,
    -- 遅延発生率
    ROUND(
        COUNT(CASE WHEN a.arrival_delay > 300 THEN 1 END)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100,
        1
    ) as delay_over_5min_pct,

    MAX(a.datetime_60) as latest_update

FROM gtfs_realtime.gtfs_rt_analytics_mv a
JOIN gtfs_static.gtfs_stops s ON a.stop_id = s.stop_id
JOIN gtfs_static.regions r ON s.region_id = r.region_id
WHERE a.datetime_60 >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
  AND a.arrival_delay IS NOT NULL
GROUP BY
    r.region_id,
    r.region_name,
    time_bucket
ORDER BY time_bucket DESC;

-- インデックス作成
CREATE INDEX idx_regional_delays_recent_time
    ON gtfs_realtime.regional_delays_recent_mv(time_bucket DESC);

CREATE INDEX idx_regional_delays_recent_region
    ON gtfs_realtime.regional_delays_recent_mv(region_id);

COMMENT ON MATERIALIZED VIEW gtfs_realtime.regional_delays_recent_mv
    IS '地域別リアルタイム遅延状況（直近24時間）';

-- =====================================================
-- 4. 地域パフォーマンスランキングビュー
-- =====================================================

DROP MATERIALIZED VIEW IF EXISTS gtfs_realtime.regional_performance_ranking_mv CASCADE;

CREATE MATERIALIZED VIEW gtfs_realtime.regional_performance_ranking_mv AS
WITH regional_stats AS (
    SELECT
        r.region_id,
        r.region_name,
        r.region_type,
        r.area_km2,
        -- 過去7日間の統計
        AVG(a.arrival_delay) / 60.0 as avg_delay_minutes_7d,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY a.arrival_delay) / 60.0 as median_delay_minutes_7d,
        -- 定時率
        ROUND(
            COUNT(CASE WHEN ABS(a.arrival_delay) <= 60 THEN 1 END)::NUMERIC /
            NULLIF(COUNT(*), 0) * 100,
            2
        ) as ontime_rate_pct_7d,
        -- サービスカバレッジ
        COUNT(DISTINCT a.route_id) as active_routes,
        COUNT(DISTINCT s.stop_id) as active_stops,
        COUNT(DISTINCT a.trip_id) as total_trips,

        COUNT(*) as total_records
    FROM gtfs_realtime.gtfs_rt_analytics_mv a
    JOIN gtfs_static.gtfs_stops s ON a.stop_id = s.stop_id
    JOIN gtfs_static.regions r ON s.region_id = r.region_id
    WHERE a.arrival_delay IS NOT NULL
      AND a.start_date::TIMESTAMP >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY r.region_id, r.region_name, r.region_type, r.area_km2
)
SELECT
    region_id,
    region_name,
    region_type,
    -- 遅延パフォーマンス
    ROUND(avg_delay_minutes_7d::numeric, 2) as avg_delay_minutes,
    ROUND(median_delay_minutes_7d::numeric, 2) as median_delay_minutes,
    ontime_rate_pct_7d,
    -- ランキング
    RANK() OVER (ORDER BY avg_delay_minutes_7d ASC) as performance_rank,
    RANK() OVER (ORDER BY ontime_rate_pct_7d DESC) as ontime_rank,
    -- サービス指標
    active_routes,
    active_stops,
    total_trips,
    ROUND(active_stops::NUMERIC / NULLIF(area_km2, 0), 2) as stops_per_km2,
    -- パフォーマンス評価
    CASE
        WHEN avg_delay_minutes_7d < 1 THEN 'A+'
        WHEN avg_delay_minutes_7d < 2 THEN 'A'
        WHEN avg_delay_minutes_7d < 3 THEN 'B'
        WHEN avg_delay_minutes_7d < 5 THEN 'C'
        ELSE 'D'
    END as performance_grade

FROM regional_stats
ORDER BY avg_delay_minutes_7d ASC;

COMMENT ON MATERIALIZED VIEW gtfs_realtime.regional_performance_ranking_mv
    IS '地域別パフォーマンスランキング（過去7日間）';

-- =====================================================
-- 5. リフレッシュ用プロシージャ
-- =====================================================

CREATE OR REPLACE PROCEDURE gtfs_realtime.refresh_regional_views(
    view_name TEXT DEFAULT 'all'
)
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE NOTICE 'Refreshing regional delay views...';

    IF view_name IN ('all', 'hourly') THEN
        RAISE NOTICE '  - Refreshing regional_delays_hourly_mv...';
        REFRESH MATERIALIZED VIEW CONCURRENTLY gtfs_realtime.regional_delays_hourly_mv;
    END IF;

    IF view_name IN ('all', 'daily') THEN
        RAISE NOTICE '  - Refreshing regional_delays_daily_mv...';
        REFRESH MATERIALIZED VIEW CONCURRENTLY gtfs_realtime.regional_delays_daily_mv;
    END IF;

    IF view_name IN ('all', 'recent') THEN
        RAISE NOTICE '  - Refreshing regional_delays_recent_mv...';
        REFRESH MATERIALIZED VIEW CONCURRENTLY gtfs_realtime.regional_delays_recent_mv;
    END IF;

    IF view_name IN ('all', 'ranking') THEN
        RAISE NOTICE '  - Refreshing regional_performance_ranking_mv...';
        REFRESH MATERIALIZED VIEW CONCURRENTLY gtfs_realtime.regional_performance_ranking_mv;
    END IF;

    RAISE NOTICE 'Regional views refresh completed at %', NOW();
END;
$$;

COMMENT ON PROCEDURE gtfs_realtime.refresh_regional_views IS '地域別ビューのリフレッシュ（all/hourly/daily/recent/ranking）';

-- =====================================================
-- 6. 統計表示用関数
-- =====================================================

CREATE OR REPLACE FUNCTION gtfs_realtime.get_regional_stats_summary()
RETURNS TABLE (
    view_name TEXT,
    row_count BIGINT,
    last_updated TIMESTAMP,
    data_range_days INTEGER,
    size_mb NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        'regional_delays_hourly_mv'::TEXT,
        COUNT(*)::BIGINT,
        MAX(time_bucket)::TIMESTAMP,
        (MAX(time_bucket)::DATE - MIN(time_bucket)::DATE)::INTEGER,
        ROUND(pg_total_relation_size('gtfs_realtime.regional_delays_hourly_mv') / 1024.0 / 1024.0, 2)
    FROM gtfs_realtime.regional_delays_hourly_mv

    UNION ALL

    SELECT
        'regional_delays_daily_mv'::TEXT,
        COUNT(*)::BIGINT,
        MAX(date)::TIMESTAMP,
        (MAX(date) - MIN(date))::INTEGER,
        ROUND(pg_total_relation_size('gtfs_realtime.regional_delays_daily_mv') / 1024.0 / 1024.0, 2)
    FROM gtfs_realtime.regional_delays_daily_mv

    UNION ALL

    SELECT
        'regional_delays_recent_mv'::TEXT,
        COUNT(*)::BIGINT,
        MAX(time_bucket)::TIMESTAMP,
        NULL,
        ROUND(pg_total_relation_size('gtfs_realtime.regional_delays_recent_mv') / 1024.0 / 1024.0, 2)
    FROM gtfs_realtime.regional_delays_recent_mv

    UNION ALL

    SELECT
        'regional_performance_ranking_mv'::TEXT,
        COUNT(*)::BIGINT,
        NULL,
        7,
        ROUND(pg_total_relation_size('gtfs_realtime.regional_performance_ranking_mv') / 1024.0 / 1024.0, 2)
    FROM gtfs_realtime.regional_performance_ranking_mv;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 7. 初回リフレッシュと統計表示
-- =====================================================

-- 初回リフレッシュ
CALL gtfs_realtime.refresh_regional_views('all');

-- 統計表示
SELECT * FROM gtfs_realtime.get_regional_stats_summary();

-- 地域別サンプルデータ表示
SELECT
    region_name,
    TO_CHAR(time_bucket, 'YYYY-MM-DD HH24:00') as hour,
    trip_count,
    ROUND(avg_delay_minutes, 2) as avg_delay_minutes,
    delay_status
FROM gtfs_realtime.regional_delays_recent_mv
ORDER BY time_bucket DESC
LIMIT 10;