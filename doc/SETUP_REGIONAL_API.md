# Metro Vancouver 地域別遅延API セットアップガイド

**最終更新:** 2025-10-01
**対象:** Metro Vancouver 23地域の遅延情報API
**データソース:** 実際のMetro Vancouver境界データ（GeoJSON）

---

## 📊 含まれるデータ

このプロジェクトには、Metro Vancouverの公式地域境界データが含まれています：

### データファイル
- `metro_vancouver_region_boundaries.geojson` (686KB) - 23地域のポリゴン境界
- `metro_vancouver_region_boundaries.csv` - 地域名と中心座標

### 対象地域（23自治体）

| # | Region ID | Region Name | Type |
|---|-----------|-------------|------|
| 1 | bowen_island | Bowen Island Municipality | municipality |
| 2 | burnaby | City of Burnaby | city |
| 3 | coquitlam | City of Coquitlam | city |
| 4 | delta | City of Delta | city |
| 5 | langley | City of Langley | city |
| 6 | maple_ridge | City of Maple Ridge | city |
| 7 | new_westminster | City of New Westminster | city |
| 8 | north_vancouver | City of North Vancouver | city |
| 9 | pitt_meadows | City of Pitt Meadows | city |
| 10 | port_coquitlam | City of Port Coquitlam | city |
| 11 | port_moody | City of Port Moody | city |
| 12 | richmond | City of Richmond | city |
| 13 | surrey | City of Surrey | city |
| 14 | vancouver | City of Vancouver | city |
| 15 | white_rock | City of White Rock | city |
| 16 | north_vancouver (district) | District of North Vancouver | district |
| 17 | west_vancouver | District of West Vancouver | district |
| 18 | electoral_area_a | Electoral Area A | electoral_area |
| 19 | langley (township) | Township of Langley | township |
| 20 | tsawwassen_first_nation | Tsawwassen First Nation | first_nation |
| 21 | anmore | Village of Anmore | village |
| 22 | belcarra | Village of Belcarra | village |
| 23 | lions_bay | Village of Lions Bay | village |

---

## 🚀 セットアップ手順

### ステップ 1: 地域データのインポート（10分）

```bash
# 1. インポートスクリプトを実行（ドライラン）
python import_metro_vancouver_regions.py --dry-run

# 2. 問題なければ本番実行
python import_metro_vancouver_regions.py
```

**実行内容:**
- ✅ PostGIS拡張を有効化
- ✅ `gtfs_static.regions` テーブル作成
- ✅ 23地域のポリゴンをインポート
- ✅ `gtfs_stops` に `region_id` カラム追加
- ✅ バス停を地域に自動マッピング（PostGIS `ST_Within`）

**期待される出力:**
```
Loading region data...
Loaded 23 regions

Creating database schema...
✓ Schema created

Inserting regions...
   1. bowen_island                   (Bowen Island Municipality)
   2. burnaby                         (City of Burnaby)
   3. coquitlam                       (City of Coquitlam)
   ...
  23. lions_bay                       (Village of Lions Bay)

✓ Inserted 23 regions

Adding region_id column to gtfs_stops...
✓ Added region_id column to gtfs_stops

Mapping stops to regions...
✓ Mapping completed
  Total stops: 8,523
  Mapped stops: 7,891 (92.6%)
  Unmapped stops: 632 (7.4%)

✓ Created materialized view

======================================================================
Region-Stop Mapping Summary
======================================================================
       region_id                    region_name region_type  stop_count
        vancouver            City of Vancouver        city        3245
          burnaby              City of Burnaby        city        1523
          surrey                 City of Surrey        city        1245
        richmond               City of Richmond        city         892
...

Total regions: 23
Total stops across all regions: 7,891

======================================================================
✓ Import completed successfully!
======================================================================
```

### ステップ 2: 地域別遅延ビューの作成（20分）

```bash
# 地域別遅延集約ビューを作成
psql -d <database> -f DB/10_create_regional_delay_views.sql
```

**作成されるマテリアライズドビュー:**

1. **`regional_delays_hourly_mv`** - 時間単位集約（過去90日）
   - 各地域の1時間ごとの遅延統計
   - 平均遅延、中央値、標準偏差
   - 遅延レベル別カウント

2. **`regional_delays_daily_mv`** - 日次サマリ（過去90日）
   - 日別の遅延サマリ
   - 定時率、遅延率

3. **`regional_delays_recent_mv`** - リアルタイム（直近24時間）
   - 最新の遅延状況
   - APIで使用

4. **`regional_performance_ranking_mv`** - パフォーマンスランキング（過去7日）
   - 地域別ランキング
   - パフォーマンスグレード（A+, A, B, C, D）

**期待される出力:**
```
✓ Regional delay views created successfully!

Available materialized views:
  - gtfs_realtime.regional_delays_hourly_mv (hourly aggregation)
  - gtfs_realtime.regional_delays_daily_mv (daily summary)
  - gtfs_realtime.regional_delays_recent_mv (last 24 hours)
  - gtfs_realtime.regional_performance_ranking_mv (7-day ranking)
```

### ステップ 3: APIのテスト（5分）

```bash
# 地域別遅延APIを実行
python regional_delay_api.py
```

**期待される出力:**
```
======================================================================
Example 1: Available Regions
======================================================================
  bowen_island              - Bowen Island Municipality
  burnaby                   - City of Burnaby
  coquitlam                 - City of Coquitlam
  ...

======================================================================
Example 2: Vancouver - 3 Hour Forecast
======================================================================
{
  "region_id": "vancouver",
  "region_name": "City of Vancouver",
  "region_type": "city",
  "current_time": "2025-10-01 14:30:00",
  "lookback_period_days": 7,
  "predictions": [
    {
      "forecast_time": "2025-10-01 15:00:00",
      "hour_of_day": 15,
      "day_of_week": 2,
      "avg_delay_minutes": 2.3,
      "median_delay_minutes": 1.8,
      "probability_delay_over_5min": 18.5,
      "status": "good"
    },
    ...
  ],
  "summary": {
    "avg_delay_next_3h": 3.2,
    "overall_status": "moderate"
  }
}

======================================================================
Example 3: All Regions Status
======================================================================
  City of Vancouver                        → good       (2.3min)
  City of Burnaby                          → moderate   (3.1min)
  City of Richmond                         → good       (2.7min)
  City of Surrey                           → moderate   (3.5min)
  ...
```

---

## 📖 API使用方法

### Python API

```python
from regional_delay_api import RegionalDelayPredictionAPI

# API初期化
api = RegionalDelayPredictionAPI()

# 1. 利用可能な地域一覧
regions = api.region_manager.list_all_regions()
for r in regions:
    print(f"{r['region_id']}: {r['region_name']}")

# 2. Vancouver の3時間予測
result = api.predict_regional_delay(
    region_id="vancouver",
    forecast_hours=3,
    lookback_days=7
)
print(result)

# 3. 全地域の現在状況
all_status = api.get_all_regions_status()
print(all_status)

# 4. 地域別パフォーマンスランキング
ranking = api.get_regional_ranking()
print(ranking)
```

### REST API（オプション）

FastAPIでREST APIを作成する場合：

```python
# regional_delay_rest_api.py
from fastapi import FastAPI
from regional_delay_api import RegionalDelayPredictionAPI

app = FastAPI()
api = RegionalDelayPredictionAPI()

@app.get("/regions")
def list_regions():
    return api.region_manager.list_all_regions()

@app.get("/regions/{region_id}/predict")
def predict_delay(region_id: str, forecast_hours: int = 3):
    return api.predict_regional_delay(region_id, forecast_hours)

@app.get("/regions/all/status")
def all_regions_status():
    return api.get_all_regions_status()

@app.get("/regions/ranking")
def get_ranking():
    return api.get_regional_ranking()
```

起動:
```bash
pip install fastapi uvicorn
python regional_delay_rest_api.py

# テスト
curl http://localhost:8000/regions
curl http://localhost:8000/regions/vancouver/predict?forecast_hours=3
curl http://localhost:8000/regions/all/status
curl http://localhost:8000/regions/ranking
```

---

## 🔄 データ保守

### マテリアライズドビューのリフレッシュ

```bash
# Pythonスクリプトで
python << EOF
from src.data_connection import DatabaseConnector
db = DatabaseConnector()
with db.get_connection() as conn:
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("CALL gtfs_realtime.refresh_regional_views('all')")
print("Regional views refreshed")
EOF
```

または直接SQL:
```sql
-- 全ビューをリフレッシュ
CALL gtfs_realtime.refresh_regional_views('all');

-- 個別にリフレッシュ
CALL gtfs_realtime.refresh_regional_views('recent');
CALL gtfs_realtime.refresh_regional_views('hourly');
CALL gtfs_realtime.refresh_regional_views('daily');
CALL gtfs_realtime.refresh_regional_views('ranking');
```

### 定期実行スケジュール（cron）

```bash
# crontab -e

# 直近データを1時間ごとにリフレッシュ
0 * * * * psql -d <database> -c "CALL gtfs_realtime.refresh_regional_views('recent');"

# hourlyビューを2時間ごとに
0 */2 * * * psql -d <database> -c "CALL gtfs_realtime.refresh_regional_views('hourly');"

# dailyビューを毎日2時に
0 2 * * * psql -d <database> -c "CALL gtfs_realtime.refresh_regional_views('daily');"

# rankingビューを毎日3時に
0 3 * * * psql -d <database> -c "CALL gtfs_realtime.refresh_regional_views('ranking');"
```

---

## 🎯 提供されるファイル

### データファイル
- `metro_vancouver_region_boundaries.geojson` - 23地域のポリゴン境界
- `metro_vancouver_region_boundaries.csv` - 地域名と座標

### Pythonスクリプト
- `import_metro_vancouver_regions.py` - 地域データインポートツール
- `regional_delay_api.py` - メインAPI（データベースベース）
- `regional_delay_api_proposal.py` - 提案版（ハードコード版、参考用）

### SQLスクリプト
- `DB/09_create_region_boundaries.sql` - 地域テーブル作成（参考用・簡易版）
- `DB/10_create_regional_delay_views.sql` - 地域別遅延集約ビュー

### ドキュメント
- `REGIONAL_API_IMPLEMENTATION_GUIDE.md` - 詳細実装ガイド
- `SETUP_REGIONAL_API.md` - このファイル（簡易セットアップガイド）

---

## ❓ トラブルシューティング

### Q1: インポート時に "region already exists" エラー

```sql
-- 既存データを削除して再実行
DROP TABLE IF EXISTS gtfs_static.regions CASCADE;
python import_metro_vancouver_regions.py
```

### Q2: バス停がマッピングされない（0%）

PostGISがインストールされているか確認:
```sql
SELECT PostGIS_Full_Version();
```

インストールされていない場合:
```sql
CREATE EXTENSION postgis;
```

### Q3: ビューが空（データがない）

Analytics MVにデータが存在するか確認:
```sql
SELECT COUNT(*) FROM gtfs_realtime.gtfs_rt_analytics_mv;
```

0の場合は、まずAnalytics MVをリフレッシュ:
```sql
REFRESH MATERIALIZED VIEW gtfs_realtime.gtfs_rt_analytics_mv;
```

---

**作成者:** GTFS Analysis Team
**最終更新:** 2025-10-01
