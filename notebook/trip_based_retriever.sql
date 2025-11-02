-- ========================================
-- Trip-based Data Retrieval Query
-- ========================================
WITH base_with_features AS (
    SELECT
        base.route_id,
        base.trip_id,
        base.direction_id,
        base.stop_id,
        base.stop_sequence,
        base.start_date,
        base.scheduled_arrival_time,
        base.actual_arrival_time,
        base.day_of_week,
        base.hour_of_day,
        DATE_TRUNC('hour', base.scheduled_arrival_time) as datetime_60,
        base.arrival_delay,
        -- ====================================
        -- 🚀 最重要: 上流停留所の遅延
        -- ====================================
        LAG(base.arrival_delay, 1) OVER (
            PARTITION BY base.trip_id, base.start_date
            ORDER BY base.stop_sequence
        ) as prev_stop_delay,
        LAG(base.arrival_delay, 2) OVER (
            PARTITION BY base.trip_id, base.start_date
            ORDER BY base.stop_sequence
        ) as prev_2_stop_delay,
        -- ====================================
        -- ルート遅延パターン（データリーク回避版）
        -- ====================================
        -- 過去1時間の同ルート平均遅延
        AVG(base.arrival_delay) OVER (
            PARTITION BY base.route_id, base.direction_id
            ORDER BY base.scheduled_arrival_time
            RANGE BETWEEN INTERVAL '60 minutes' PRECEDING AND INTERVAL '1 minute' PRECEDING
        ) as route_delay_trend_60min,
        -- 過去7日間の同時刻帯平均（曜日パターン学習）
        AVG(base.arrival_delay) OVER (
            PARTITION BY base.route_id, base.direction_id, base.hour_of_day
            ORDER BY base.scheduled_arrival_time
            ROWS BETWEEN 168 PRECEDING AND 1 PRECEDING
        ) as route_hourly_delay_7d_avg,
        -- 過去3時間の標準偏差（変動性の指標）
        STDDEV(base.arrival_delay) OVER (
            PARTITION BY base.route_id, base.direction_id
            ORDER BY base.scheduled_arrival_time
            ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING
        ) as route_delay_volatility_3h
    FROM gtfs_realtime.gtfs_rt_base_v2_mv base
)
SELECT
    -- ====================================
    -- メタデータ（SequenceCreatorで使用）
    -- ====================================
    bf.route_id,
    bf.trip_id,
    bf.direction_id,
    bf.stop_id,
    bf.stop_sequence,
    bf.start_date,
    bf.scheduled_arrival_time,
    bf.actual_arrival_time,
    bf.datetime_60 as time_bucket,  -- SequenceCreatorがこれでソート
    -- ====================================
    -- 目的変数
    -- ====================================
    bf.arrival_delay,
    -- ====================================
    -- 🚀 新規特徴量: 上流停留所遅延
    -- ====================================
    COALESCE(bf.prev_stop_delay, 0) as prev_stop_delay,
    COALESCE(bf.prev_2_stop_delay, 0) as prev_2_stop_delay,
    -- ====================================
    -- 🚀 改善版: ルート遅延パターン
    -- ====================================
    COALESCE(bf.route_delay_trend_60min, 0) as route_delay_trend_60min,
    COALESCE(bf.route_hourly_delay_7d_avg, 0) as route_hourly_delay_7d_avg,
    COALESCE(bf.route_delay_volatility_3h, 0) as route_delay_volatility_3h,
    -- ====================================
    -- 時間特徴（改善版）
    -- ====================================
    -- 周期エンコーディング
    SIN(2 * PI() * bf.hour_of_day / 24) as hour_sin,
    COS(2 * PI() * bf.hour_of_day / 24) as hour_cos,
    SIN(2 * PI() * bf.day_of_week / 7) as day_sin,
    COS(2 * PI() * bf.day_of_week / 7) as day_cos,
    -- ラッシュアワー分類（朝=1, 夕=2, その他=0）
    CASE
        WHEN bf.hour_of_day BETWEEN 7 AND 9 THEN 1
        WHEN bf.hour_of_day BETWEEN 17 AND 19 THEN 2
        ELSE 0
    END as rush_hour_type,
    -- 学校通学時間帯（平日の8時、15-16時）
    CASE
        WHEN bf.day_of_week <= 5
             AND bf.hour_of_day IN (8, 15, 16) THEN 1
        ELSE 0
    END as school_commute_hour,
    -- 週末フラグ
    CASE WHEN bf.day_of_week IN (6, 7) THEN 1 ELSE 0 END as is_weekend,
    -- 月内の日（給料日効果など）
    EXTRACT(DAY FROM bf.start_date::date) as day_of_month,
    -- 祝日フラグ（GTFSカレンダー例外を活用）
    CASE
        WHEN EXISTS (
            SELECT 1 FROM gtfs_static.gtfs_calendar_dates
            WHERE date = bf.start_date::date AND exception_type = 1
        ) THEN 1
        ELSE 0
    END as is_holiday,
    -- ====================================
    -- 地理特徴
    -- ====================================
    se.distance_from_downtown_km,
    se.area_density_score,
    bf.stop_sequence,  -- トリップ内での位置
    bf.direction_id,   -- 方向
    -- ====================================
    -- 🚀 改善版: 天候特徴
    -- ====================================
    wh.humidex_v as humidex,
    wh.wind_speed,
    -- 季節性を除去した気温偏差（start_dateとの相関-0.75を解消）
    wh.humidex_v - AVG(wh.humidex_v) OVER (
        ORDER BY wh.unixtime
        ROWS BETWEEN 168 PRECEDING AND CURRENT ROW
    ) as humidex_deviation_7d,
    -- 風速変化率
    wh.wind_speed - COALESCE(
        LAG(wh.wind_speed) OVER (ORDER BY wh.unixtime),
        wh.wind_speed
    ) as wind_speed_change_1h,
    -- 雨天フラグ（既存）
    CASE
        WHEN wh.cloud_cover_8 > 6 THEN 1
        ELSE 0
    END as weather_rainy,
    -- ====================================
    -- 🚀 新規: アラート特徴量（Phase 4）
    -- ====================================
    -- 基本アラート情報（MVから取得）
    COALESCE(alerts.has_active_alert, 0) as has_active_alert,
    COALESCE(alerts.high_impact_alert_count, 0) as high_impact_alert_count,
    -- 原因別アラート（上位3つ）
    COALESCE(alerts.alert_police_activity, 0) as alert_police_activity,
    COALESCE(alerts.alert_construction, 0) as alert_construction,
    COALESCE(alerts.alert_technical_problem, 0) as alert_technical_problem,
    -- 影響別アラート（遅延に直結）
    COALESCE(alerts.alert_effect_no_service, 0) as alert_effect_no_service,
    COALESCE(alerts.alert_effect_detour, 0) as alert_effect_detour,
    COALESCE(alerts.alert_severity_score, 0) as alert_severity_score,
    -- ====================================
    -- メタデータ（分析用）
    -- ====================================
    t.trip_headsign,
    se.stop_name
FROM base_with_features bf
INNER JOIN gtfs_static.gtfs_trips_static t
    ON t.trip_id = bf.trip_id
INNER JOIN gtfs_static.gtfs_stops_enhanced_mv se
    ON se.stop_id = bf.stop_id
INNER JOIN climate.weather_hourly wh
    ON to_timestamp(wh.unixtime) = bf.datetime_60
-- ====================================
-- アラート特徴量JOIN（マテリアライズドビュー使用）
-- ====================================
-- インラインサブクエリの代わりにMVを使用（パフォーマンス向上）
LEFT JOIN gtfs_realtime.gtfs_rt_alert_features_route_hour_v alerts
    ON alerts.route_id = bf.route_id
    AND alerts.alert_hour = bf.datetime_60
-- 上流遅延データの品質確保のため stop_sequence >= 6 に変更
-- Non-zero率: 44.5% (seq>=4) → 期待65%+ (seq>=6)
WHERE bf.stop_sequence >= 6
    AND bf.prev_stop_delay IS NOT NULL  -- NULL除外でデータ品質向上
-- ORDER BY RANDOM() LIMIT 100000
;
