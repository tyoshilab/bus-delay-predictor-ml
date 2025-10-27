-- =====================================================
-- Regional Delay Predictions Storage Table
-- =====================================================
--
-- Purpose: Store machine learning predictions for regional bus delays
--
-- Prerequisites:
--   1. DB/07_create_regional_delay_views.sql executed
--   2. gtfs_static.regions table exists
--
-- Usage:
--   psql -d <database> -f DB/08_create_regional_predictions_table.sql
-- =====================================================

-- =====================================================
-- 1. Regional Delay Predictions Table
-- =====================================================
DROP TABLE IF EXISTS gtfs_realtime.regional_delay_predictions;

CREATE TABLE IF NOT EXISTS gtfs_realtime.regional_delay_predictions (
    prediction_id BIGSERIAL PRIMARY KEY,
    -- メタデータ
    region_id VARCHAR(50) NOT NULL,
    route_id VARCHAR(20) NOT NULL,
    direction_id INTEGER NOT NULL,
    stop_id VARCHAR(20) NOT NULL,
    stop_sequence INTEGER,
    -- 予測基準時刻
    prediction_created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- 予測対象時刻（1時間後、2時間後、3時間後）
    prediction_target_time TIMESTAMP WITH TIME ZONE NOT NULL,
    prediction_hour_offset INTEGER NOT NULL CHECK (prediction_hour_offset BETWEEN 1 AND 3),
    -- 予測結果
    predicted_delay_seconds NUMERIC(10, 2) NOT NULL,
    predicted_delay_minutes NUMERIC(8, 2) NOT NULL,
    -- モデル情報
    model_version VARCHAR(100),
    model_path TEXT,
    -- 入力データ期間
    input_data_start TIMESTAMP WITH TIME ZONE,
    input_data_end TIMESTAMP WITH TIME ZONE,
    -- バス停情報（キャッシュ）
    stop_name VARCHAR(255),
    stop_lat NUMERIC(10, 6),
    stop_lon NUMERIC(11, 6),
    -- データ品質
    sequence_count INTEGER,  -- 使用したシーケンス数
    confidence_score NUMERIC(5, 4),  -- 信頼度スコア（オプション）
    -- パフォーマンス追跡
    prediction_execution_time_ms INTEGER,  -- 予測実行時間（ミリ秒）
    -- データ管理
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    -- 制約
    CONSTRAINT fk_region FOREIGN KEY (region_id)
        REFERENCES gtfs_static.regions(region_id) ON DELETE CASCADE,
    CONSTRAINT check_hour_offset CHECK (prediction_hour_offset IN (1, 2, 3))
);

-- =====================================================
-- 2. Indexes for Performance
-- =====================================================

-- 複合インデックス：最新予測取得用
CREATE INDEX IF NOT EXISTS idx_regional_predictions_latest
    ON gtfs_realtime.regional_delay_predictions(
        route_id, stop_id, stop_sequence, direction_id,
        prediction_created_at DESC
    );

COMMENT ON TABLE gtfs_realtime.regional_delay_predictions
    IS '地域別バス遅延予測結果（ConvLSTMモデル、3時間先まで予測）';

COMMENT ON COLUMN gtfs_realtime.regional_delay_predictions.prediction_hour_offset
    IS '予測時間オフセット（1=1時間後、2=2時間後、3=3時間後）';

COMMENT ON COLUMN gtfs_realtime.regional_delay_predictions.confidence_score
    IS '予測信頼度スコア（0.0-1.0、将来の拡張用）';

-- =====================================================
-- 3. Latest Predictions View (for API)
-- =====================================================
drop view if exists gtfs_realtime.regional_predictions_latest;
CREATE OR REPLACE VIEW gtfs_realtime.regional_predictions_latest AS
WITH latest_batch AS (
    SELECT route_id, stop_id, stop_sequence, direction_id, MAX(prediction_created_at) as latest_time
    FROM gtfs_realtime.regional_delay_predictions
    GROUP BY route_id, stop_id, stop_sequence, direction_id
)
SELECT
    p.prediction_id,
    p.region_id,
    p.route_id,
    p.direction_id,
    p.stop_id,
    p.stop_name,
    p.stop_sequence,
    p.prediction_target_time,
    p.predicted_delay_seconds,
    p.predicted_delay_minutes
FROM gtfs_realtime.regional_delay_predictions p
INNER JOIN latest_batch lb
    ON p.stop_id = lb.stop_id
    AND p.route_id = lb.route_id
    AND p.stop_sequence = lb.stop_sequence
    AND p.direction_id = lb.direction_id
    AND p.prediction_created_at = lb.latest_time
ORDER BY p.region_id, p.route_id, p.direction_id, p.stop_id, p.prediction_hour_offset;

COMMENT ON VIEW gtfs_realtime.regional_predictions_latest
    IS '各地域の最新予測バッチのみを表示（API用）';