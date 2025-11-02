-- ========================================
-- Route-based Data Retrieval Query
-- ========================================
WITH
    base_with_features AS (
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
            DATE_TRUNC(
                'hour',
                base.scheduled_arrival_time
            ) as datetime_60,
            base.arrival_delay,
            -- ====================================
            -- Phase 1-3: ルート遅延パターン（データリーク回避版）
            -- ====================================
            -- 過去1時間の同ルート平均遅延
            AVG(base.arrival_delay) OVER (
                PARTITION BY
                    base.route_id,
                    base.direction_id
                ORDER BY base.scheduled_arrival_time RANGE BETWEEN INTERVAL '60 minutes' PRECEDING
                    AND INTERVAL '1 minute' PRECEDING
            ) as route_delay_trend_60min,
            -- 過去7日間の同時刻帯平均（曜日パターン学習）
            AVG(base.arrival_delay) OVER (
                PARTITION BY
                    base.route_id,
                    base.direction_id,
                    base.hour_of_day
                ORDER BY base.scheduled_arrival_time ROWS BETWEEN 168 PRECEDING
                    AND 1 PRECEDING
            ) as route_hourly_delay_7d_avg,
            -- 過去3時間の標準偏差（変動性の指標）
            STDDEV(base.arrival_delay) OVER (
                PARTITION BY
                    base.route_id,
                    base.direction_id
                ORDER BY base.scheduled_arrival_time ROWS BETWEEN 3 PRECEDING
                    AND 1 PRECEDING
            ) as route_delay_volatility_3h,
            -- データリーク回避: 過去7日間の同時刻帯平均
            AVG(base.arrival_delay) OVER (
                PARTITION BY
                    base.route_id,
                    base.direction_id,
                    base.hour_of_day
                ORDER BY base.scheduled_arrival_time ROWS BETWEEN 168 PRECEDING
                    AND 1 PRECEDING
            ) as delay_mean_by_route_hour,
            -- データリーク回避: 過去7日間の同trip_headsign・同時刻帯平均
            AVG(base.arrival_delay) OVER (
                PARTITION BY
                    base.trip_id,
                    base.hour_of_day
                ORDER BY base.scheduled_arrival_time ROWS BETWEEN 168 PRECEDING
                    AND 1 PRECEDING
            ) as delay_mean_by_trip_headsign_hour
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
    bf.start_date,
    bf.scheduled_arrival_time,
    bf.actual_arrival_time,
    bf.datetime_60 as time_bucket,
    -- ====================================
    -- 目的変数
    -- ====================================
    bf.arrival_delay,
    -- ====================================
    -- Phase 1-3: ルート遅延パターン
    -- ====================================
    COALESCE(bf.route_delay_trend_60min, 0) as route_delay_trend_60min,
    COALESCE(
        bf.route_hourly_delay_7d_avg,
        0
    ) as route_hourly_delay_7d_avg,
    COALESCE(
        bf.route_delay_volatility_3h,
        0
    ) as route_delay_volatility_3h,
    COALESCE(
        bf.delay_mean_by_route_hour,
        0
    ) as delay_mean_by_route_hour,
    COALESCE(
        bf.delay_mean_by_trip_headsign_hour,
        0
    ) as delay_mean_by_trip_headsign_hour,
    -- ====================================
    -- 時間特徴（Phase 1-3改善版）
    -- ====================================
    -- 周期エンコーディング
    SIN(
        2 * PI() * bf.hour_of_day / 24
    ) as hour_sin,
    COS(
        2 * PI() * bf.hour_of_day / 24
    ) as hour_cos,
    SIN(2 * PI() * bf.day_of_week / 7) as day_sin,
    COS(2 * PI() * bf.day_of_week / 7) as day_cos,
    -- ラッシュアワー分類（朝=1, 夕=2, その他=0）
    CASE
        WHEN bf.hour_of_day BETWEEN 7 AND 9  THEN 1
        WHEN bf.hour_of_day BETWEEN 17 AND 19  THEN 2
        ELSE 0
    END as rush_hour_type,
    -- 学校通学時間帯（平日の8時、15-16時）
    CASE
        WHEN bf.day_of_week <= 5
        AND bf.hour_of_day IN (8, 15, 16) THEN 1
        ELSE 0
    END as school_commute_hour,
    -- 週末フラグ
    CASE
        WHEN bf.day_of_week IN (6, 7) THEN 1
        ELSE 0
    END as is_weekend,
    -- 月内の日（給料日効果など）
    EXTRACT(
        DAY
        FROM bf.start_date::date
    ) as day_of_month,
    -- 祝日フラグ（GTFSカレンダー例外を活用）
    CASE
        WHEN EXISTS (
            SELECT 1
            FROM gtfs_static.gtfs_calendar_dates
            WHERE
                date = bf.start_date::date
                AND exception_type = 1
        ) THEN 1
        ELSE 0
    END as is_holiday,
    -- ====================================
    -- 地理特徴
    -- ====================================
    se.distance_from_downtown_km,
    se.area_density_score,
    bf.stop_sequence,
    bf.direction_id,
    -- ====================================
    -- 天候特徴（Phase 1-3改善版）
    -- ====================================
    wh.humidex_v as humidex,
    wh.wind_speed,
    -- 季節性を除去した気温偏差
    wh.humidex_v - AVG(wh.humidex_v) OVER (
        ORDER BY wh.unixtime ROWS BETWEEN 168 PRECEDING
            AND CURRENT ROW
    ) as humidex_deviation_7d,
    -- 風速変化率
    wh.wind_speed - COALESCE(
        LAG(wh.wind_speed) OVER (
            ORDER BY wh.unixtime
        ),
        wh.wind_speed
    ) as wind_speed_change_1h,
    -- 雨天フラグ
    CASE
        WHEN wh.cloud_cover_8 > 3 THEN 1
        ELSE 0
    END as weather_rainy,
    -- ====================================
    -- Phase 4: アラート特徴量
    -- ====================================
    COALESCE(af.has_active_alert, 0) as has_active_alert,
    COALESCE(af.high_impact_alert_count, 0) as high_impact_alert_count,
    COALESCE(af.alert_police_activity, 0) as alert_police_activity,
    COALESCE(af.alert_construction, 0) as alert_construction,
    COALESCE(af.alert_technical_problem, 0) as alert_technical_problem,
    COALESCE(af.alert_effect_no_service, 0) as alert_effect_no_service,
    COALESCE(af.alert_effect_detour, 0) as alert_effect_detour,
    COALESCE(af.alert_severity_score, 0) as alert_severity_score,
    -- ====================================
    -- メタデータ（分析用）
    -- ====================================
    t.trip_headsign,
    se.stop_name
FROM
    base_with_features bf
    INNER JOIN gtfs_static.gtfs_trips_static t ON t.trip_id = bf.trip_id
    INNER JOIN gtfs_static.gtfs_stops_enhanced_mv se ON se.stop_id = bf.stop_id
    INNER JOIN climate.weather_hourly wh ON to_timestamp(wh.unixtime) = bf.datetime_60
    -- Phase 4: アラート特徴量をJOIN
    LEFT JOIN gtfs_realtime.gtfs_rt_alert_features_route_hour_v af ON af.route_id = bf.route_id
    AND af.alert_hour = bf.datetime_60
    -- ORDER BY RANDOM() LIMIT 100000
;