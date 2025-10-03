-- =====================================================
-- Database Configuration
-- =====================================================
-- Purpose: データベースの基本設定
-- Usage: psql -d <database> -f DB/00_configure_database.sql
-- =====================================================

-- タイムゾーンをVancouverに設定
ALTER DATABASE postgres SET timezone TO 'America/Vancouver';

-- 設定確認
SELECT
    current_setting('timezone') as current_timezone,
    NOW() as local_time,
    NOW() AT TIME ZONE 'UTC' as utc_time;

COMMENT ON DATABASE postgres IS 'GTFS Bus Delay Prediction System - Timezone: America/Vancouver';