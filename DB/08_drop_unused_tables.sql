-- =====================================================
-- Drop Unused GTFS Realtime Tables
-- =====================================================
-- Purpose: Remove Alert and Vehicle Position related tables
--          to reduce database storage usage
--
-- Tables to be dropped:
--   - Alert system (4 tables): ~15-20% storage reduction
--   - Vehicle positions (1 table): ~5-10% storage reduction
--
-- Impact Analysis:
--   - API: No impact (not used)
--   - ML Model Training: No impact (not used)
--   - Data Pipeline: No impact (not used)
--
-- Execution:
--   psql -d <database> -f DB/08_drop_unused_tables.sql
-- =====================================================

-- =====================================================
-- Step 1: Verify table usage (informational queries)
-- =====================================================

-- Check table sizes before deletion
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename) - pg_relation_size(schemaname||'.'||tablename)) AS index_size
FROM pg_tables
WHERE schemaname = 'gtfs_realtime'
  AND tablename IN (
    'gtfs_rt_alerts',
    'gtfs_rt_alert_text',
    'gtfs_rt_alert_active_periods',
    'gtfs_rt_alert_informed_entities',
    'gtfs_rt_vehicle_positions'
  )
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check row counts
SELECT 'gtfs_rt_alerts' as table_name, COUNT(*) as row_count FROM gtfs_realtime.gtfs_rt_alerts
UNION ALL
SELECT 'gtfs_rt_alert_text', COUNT(*) FROM gtfs_realtime.gtfs_rt_alert_text
UNION ALL
SELECT 'gtfs_rt_alert_active_periods', COUNT(*) FROM gtfs_realtime.gtfs_rt_alert_active_periods
UNION ALL
SELECT 'gtfs_rt_alert_informed_entities', COUNT(*) FROM gtfs_realtime.gtfs_rt_alert_informed_entities
UNION ALL
SELECT 'gtfs_rt_vehicle_positions', COUNT(*) FROM gtfs_realtime.gtfs_rt_vehicle_positions;

-- =====================================================
-- Step 2: Drop tables in correct order (respecting FK constraints)
-- =====================================================

BEGIN;

-- Alert system: Drop child tables first (have FK to gtfs_rt_alerts)
-- Relationship: alert_text -> alerts, alert_active_periods -> alerts, alert_informed_entities -> alerts

DROP TABLE IF EXISTS gtfs_realtime.gtfs_rt_alert_text CASCADE;
RAISE NOTICE 'Dropped: gtfs_rt_alert_text';

DROP TABLE IF EXISTS gtfs_realtime.gtfs_rt_alert_active_periods CASCADE;
RAISE NOTICE 'Dropped: gtfs_rt_alert_active_periods';

DROP TABLE IF EXISTS gtfs_realtime.gtfs_rt_alert_informed_entities CASCADE;
RAISE NOTICE 'Dropped: gtfs_rt_alert_informed_entities';

-- Drop parent alert table
-- Relationship: alerts -> feed_entities (FK: feed_entity_id)
DROP TABLE IF EXISTS gtfs_realtime.gtfs_rt_alerts CASCADE;
RAISE NOTICE 'Dropped: gtfs_rt_alerts';

-- Vehicle positions
-- Relationship: vehicle_positions -> feed_entities, trip_descriptors, vehicle_descriptors
-- Note: vehicle_descriptors table is still used by trip_updates, so we keep it
DROP TABLE IF EXISTS gtfs_realtime.gtfs_rt_vehicle_positions CASCADE;
RAISE NOTICE 'Dropped: gtfs_rt_vehicle_positions';

COMMIT;

-- =====================================================
-- Step 3: Clean up orphaned feed_entities (optional)
-- =====================================================
-- Remove feed_entities that were only used by alerts/vehicle_positions
-- WARNING: Only run if you're sure these entities are not referenced elsewhere

-- Uncomment to execute:
-- BEGIN;
--
-- DELETE FROM gtfs_realtime.gtfs_rt_feed_entities
-- WHERE entity_type IN ('alert', 'vehicle')
--   AND NOT EXISTS (
--     SELECT 1 FROM gtfs_realtime.gtfs_rt_trip_updates tu
--     WHERE tu.feed_entity_id = gtfs_rt_feed_entities.id
--   );
--
-- COMMIT;

-- =====================================================
-- Step 4: Vacuum to reclaim disk space
-- =====================================================

-- Light vacuum (non-blocking)
VACUUM ANALYZE gtfs_realtime.gtfs_rt_feed_entities;

-- For immediate disk space recovery, run VACUUM FULL (blocks table access):
-- WARNING: This will lock the table. Run during maintenance window.
-- VACUUM FULL gtfs_realtime.gtfs_rt_feed_entities;

-- =====================================================
-- Step 5: Verify deletion
-- =====================================================

-- Check remaining tables
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size
FROM pg_tables
WHERE schemaname = 'gtfs_realtime'
  AND tablename LIKE 'gtfs_rt_%'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Total storage saved
SELECT
    'Total Realtime Schema Size' as description,
    pg_size_pretty(SUM(pg_total_relation_size(schemaname||'.'||tablename))) AS size
FROM pg_tables
WHERE schemaname = 'gtfs_realtime';

-- =====================================================
-- Rollback Plan (if needed)
-- =====================================================
-- To restore these tables, re-run:
--   psql -d <database> -f DB/02_create_gtfs_realtime_tables_optimized.sql
--
-- Then reload data from your GTFS-RT feed archive (if available)
-- =====================================================

RAISE NOTICE '========================================';
RAISE NOTICE 'Unused tables successfully dropped';
RAISE NOTICE 'Next steps:';
RAISE NOTICE '  1. Monitor application for any errors';
RAISE NOTICE '  2. Run VACUUM FULL during maintenance window';
RAISE NOTICE '  3. Update monitoring dashboards if needed';
RAISE NOTICE '========================================';