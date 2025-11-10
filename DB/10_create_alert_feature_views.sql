-- ============================================================================
-- GTFS Realtime Alert Feature Views
-- ============================================================================
-- Purpose: アラート情報をSQL上で効率的に取得するためのView/Materialized View
-- GTFS Realtime Service Alerts仕様準拠
-- https://gtfs.org/documentation/realtime/examples/service-alerts/
-- ============================================================================

-- ============================================================================
-- 1. アラート基本情報View
-- ============================================================================
-- アラートの全情報を統合したView（informed_entity, active_period, text含む）

CREATE OR REPLACE VIEW gtfs_realtime.gtfs_rt_alerts_detail AS
WITH alert_periods AS (
    SELECT
        alert_id,
        MIN(period_time) as period_start,
        MAX(period_time) as period_end
    FROM gtfs_realtime.gtfs_rt_alert_active_periods
    GROUP BY alert_id
),
alert_header AS (
    SELECT
        alert_id,
        text as header_text
    FROM gtfs_realtime.gtfs_rt_alert_text
    WHERE text_type = 'header'
        AND (language = 'en' OR language IS NULL)
),
alert_description AS (
    SELECT
        alert_id,
        text as description_text
    FROM gtfs_realtime.gtfs_rt_alert_text
    WHERE text_type = 'description'
        AND (language = 'en' OR language IS NULL)
),
alert_url AS (
    SELECT
        alert_id,
        text as url
    FROM gtfs_realtime.gtfs_rt_alert_text
    WHERE text_type = 'url'
        AND (language = 'en' OR language IS NULL)
)
SELECT DISTINCT
    a.alert_id,
    a.cause,
    a.effect,
    a.severity_level,
    ie.route_id,
    ie.stop_id,
    ie.agency_id,
    ie.route_type,
    h.header_text,
    d.description_text,
    u.url,
    to_timestamp(ap.period_start) as active_period_start,
    to_timestamp(ap.period_end) as active_period_end,
    a.created_at
FROM gtfs_realtime.gtfs_rt_alerts a
LEFT JOIN gtfs_realtime.gtfs_rt_alert_informed_entities ie
    ON a.alert_id = ie.alert_id
LEFT JOIN alert_periods ap
    ON a.alert_id = ap.alert_id
LEFT JOIN alert_header h
    ON a.alert_id = h.alert_id
LEFT JOIN alert_description d
    ON a.alert_id = d.alert_id
LEFT JOIN alert_url u
    ON a.alert_id = u.alert_id;

COMMENT ON VIEW gtfs_realtime.gtfs_rt_alerts_detail IS
'アラートの全情報を統合したView（informed_entity, active_period, text含む）';

-- ============================================================================
-- 2. Route + Hour 単位のアラート特徴量 Materialized View
-- ============================================================================
-- Route-based シーケンス作成用
-- route_id + 時刻 でグループ化したアラート統計

CREATE OR REPLACE VIEW gtfs_realtime.gtfs_rt_alert_features_route_hour_v AS
SELECT
    ad.route_id,
    DATE_TRUNC('hour', ad.active_period_start) as alert_hour,
    -- 基本統計
    CASE WHEN COUNT(DISTINCT ad.alert_id) > 0 THEN 1 ELSE 0 END as has_active_alert,
    -- 高影響アラート数（NO_SERVICE=1, DETOUR=4）
    COUNT(DISTINCT ad.alert_id) FILTER (WHERE ad.effect::INTEGER IN (1, 4)) as high_impact_alert_count,
    -- 原因別アラート（バンクーバー特有）
    COUNT(DISTINCT ad.alert_id) FILTER (WHERE ad.cause::INTEGER = 10) as alert_police_activity,
    COUNT(DISTINCT ad.alert_id) FILTER (WHERE ad.cause::INTEGER = 9) as alert_construction,
    COUNT(DISTINCT ad.alert_id) FILTER (WHERE ad.cause::INTEGER = 2) as alert_technical_problem,
    -- 影響別アラート
    COUNT(DISTINCT ad.alert_id) FILTER (WHERE ad.effect::INTEGER = 1) as alert_effect_no_service,
    COUNT(DISTINCT ad.alert_id) FILTER (WHERE ad.effect::INTEGER = 4) as alert_effect_detour,
    -- 重症度スコア（影響度に基づく重み付け）
    COALESCE(SUM(
        CASE ad.effect::INTEGER
            WHEN 1 THEN 10  -- NO_SERVICE
            WHEN 3 THEN 8   -- SIGNIFICANT_DELAYS
            WHEN 4 THEN 7   -- DETOUR
            WHEN 6 THEN 5   -- MODIFIED_SERVICE
            WHEN 9 THEN 4   -- STOP_MOVED
            WHEN 2 THEN 3   -- REDUCED_SERVICE
            ELSE 1
        END
    ), 0) as alert_severity_score
FROM gtfs_realtime.gtfs_rt_alerts_detail ad
WHERE ad.route_id IS NOT NULL
    AND ad.active_period_start IS NOT NULL
GROUP BY ad.route_id, DATE_TRUNC('hour', ad.active_period_start);

-- インデックス作成（JOINパフォーマンス向上）
CREATE INDEX IF NOT EXISTS idx_alert_features_route_hour
    ON gtfs_realtime.gtfs_rt_alert_features_route_hour_mv (route_id, alert_hour);

COMMENT ON MATERIALIZED VIEW gtfs_realtime.gtfs_rt_alert_features_route_hour_mv IS
'Route + Hour単位のアラート特徴量（Route-based シーケンス作成用）';

-- ============================================================================
-- 3. 自動リフレッシュ用関数（オプション）
-- ============================================================================
-- アラート特徴量MVを手動リフレッシュする関数

CREATE OR REPLACE FUNCTION gtfs_realtime.refresh_alert_features_mv()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY gtfs_realtime.gtfs_rt_alert_features_route_hour_mv;
    RAISE NOTICE 'Alert features materialized view refreshed successfully';
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION gtfs_realtime.refresh_alert_features_mv() IS
'アラート特徴量MVを手動リフレッシュ（CONCURRENTLY使用でロックなし）';

