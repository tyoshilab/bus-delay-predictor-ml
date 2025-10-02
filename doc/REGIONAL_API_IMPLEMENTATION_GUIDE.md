# 地域別遅延予測API 実装ガイド

**目的:** Vancouver全域やBC州の地域（Downtown, Richmond, Burnaby, Surrey等）のざっくりとした遅延情報を返すAPIを実装

**作成日:** 2025-10-01
**対象:** バス停やルート単位ではなく、地域単位での遅延集約

---

## 📋 実装可否

### ✅ **実装可能です**

既存のデータから以下が確認済み：
- ✅ GTFSの`stops`テーブルに緯度経度データ（`stop_lat`, `stop_lon`）が存在
- ✅ バンクーバー広域（Richmond, Burnaby, Surrey等）をカバー
- ✅ `gtfs_rt_analytics_mv`に遅延データが集約済み
- ✅ 座標範囲: 緯度49.15〜49.35°N、経度-123.26〜-122.70°W

---

## 🗂️ 必要なデータ

### 1. **地域境界データ（Region Boundaries）**

#### オプションA: オープンデータソース（推奨）

**推奨データソース:**
```
1. Metro Vancouver Open Data Portal
   URL: http://www.metrovancouver.org/data
   形式: GeoJSON, Shapefile
   内容: 自治体境界、地区境界

2. Statistics Canada Boundary Files
   URL: https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/
   形式: Shapefile
   内容: Census subdivisions (CSDs) - 自治体境界

3. BC Geographic Data Catalogue
   URL: https://catalogue.data.gov.bc.ca/
   形式: GeoJSON, KML, Shapefile
   内容: Regional districts, municipalities

4. TransLink Open Data（推奨！）
   URL: https://www.translink.ca/about-us/doing-business-with-translink/app-developer-resources
   形式: GeoJSON
   内容: Transit service areas, zones
```

#### オプションB: 簡易実装（境界ボックス定義）

提供済みの`DB/09_create_region_boundaries.sql`には、以下の地域が定義済み：

| Region ID | Region Name | Type | Area (km²) |
|-----------|-------------|------|------------|
| downtown_vancouver | Downtown Vancouver | neighborhood | - |
| vancouver_west | West Vancouver & UBC | neighborhood | - |
| vancouver_east | East Vancouver | neighborhood | - |
| richmond | Richmond | municipality | 129.27 |
| burnaby | Burnaby | municipality | 98.60 |
| surrey | Surrey | municipality | 316.41 |
| tri_cities | Tri-Cities (Coquitlam, Port Moody, Port Coquitlam) | municipality | 152.30 |
| new_westminster | New Westminster | municipality | 15.62 |
| north_vancouver | North Vancouver | municipality | 185.00 |

**注意:** これらは簡易的な矩形（bounding box）です。本番環境では正確なポリゴンデータの使用を推奨。

### 2. **PostGIS拡張**

地理空間データ処理に必要：
```sql
CREATE EXTENSION IF NOT EXISTS postgis;
```

### 3. **既存データの活用**

- `gtfs_static.gtfs_stops` → バス停座標
- `gtfs_realtime.gtfs_rt_analytics_mv` → 遅延データ（過去データ）
- `stops.geojson` → バス停位置の可視化（既に生成済み）

---

## 🚀 実装手順

### Phase 1: データベースセットアップ（30分）

#### 1.1 地域境界テーブル作成
```bash
# PostGIS拡張確認
psql -d <database> -c "CREATE EXTENSION IF NOT EXISTS postgis;"

# 地域境界テーブルとマッピング
psql -d <database> -f DB/09_create_region_boundaries.sql
```

**実行内容:**
- `gtfs_static.regions` テーブル作成
- Metro Vancouverの9地域を登録
- `gtfs_stops` テーブルに `region_id` カラム追加
- バス停と地域の自動マッピング（PostGIS `ST_Within`）
- `stops_with_regions_mv` マテリアライズドビュー作成

**期待される出力:**
```
===== Region Mapping Summary =====
Total stops: 8,523
Mapped stops: 7,891 (92.6%)
Unmapped stops: 632 (7.4%)
==================================
```

#### 1.2 地域別遅延集約ビュー作成
```bash
psql -d <database> -f DB/10_create_regional_delay_views.sql
```

**作成されるビュー:**
1. `regional_delays_hourly_mv` - 時間単位集約（過去90日）
2. `regional_delays_daily_mv` - 日次サマリ（過去90日）
3. `regional_delays_recent_mv` - リアルタイム状況（直近24時間）
4. `regional_performance_ranking_mv` - パフォーマンスランキング（過去7日）

#### 1.3 確認クエリ
```sql
-- 地域別バス停数
SELECT region_name, COUNT(*) as stop_count
FROM gtfs_static.stops_with_regions_mv
WHERE region_id IS NOT NULL
GROUP BY region_name
ORDER BY stop_count DESC;

-- 地域別遅延サマリ（直近24時間）
SELECT * FROM gtfs_realtime.regional_delays_recent_mv
ORDER BY time_bucket DESC
LIMIT 10;

-- パフォーマンスランキング
SELECT region_name, performance_grade, avg_delay_minutes, ontime_rate_pct_7d
FROM gtfs_realtime.regional_performance_ranking_mv
ORDER BY performance_rank;
```

### Phase 2: APIコード実装（1時間）

#### 2.1 基本的な使用方法

```python
# regional_delay_api_proposal.py を使用
from regional_delay_api_proposal import RegionalDelayPredictionAPI

# API初期化
api = RegionalDelayPredictionAPI()

# 例1: Downtown Vancouverの3時間予測
result = api.predict_regional_delay(
    region_id="downtown_vancouver",
    forecast_hours=3,
    lookback_days=7
)

print(f"Region: {result['region_name']}")
print(f"Current Time: {result['current_time']}")
print("\nPredictions:")
for pred in result['predictions']:
    print(f"  {pred['forecast_time']}: {pred['avg_delay_minutes']:.2f} min ({pred['status']})")

# 例2: 全地域の現在状況
all_regions = api.get_all_regions_status(forecast_hours=1)

for region in all_regions['regions']:
    print(f"{region['region_name']:30s} → {region['status']:10s} ({region['avg_delay_minutes']:.1f} min)")
```

#### 2.2 期待される出力

```json
{
  "region_id": "downtown_vancouver",
  "region_name": "Downtown Vancouver",
  "current_time": "2025-10-01 14:30:00",
  "lookback_period_days": 7,
  "total_stops_in_region": 1234,
  "predictions": [
    {
      "forecast_time": "2025-10-01 15:00:00",
      "avg_delay_minutes": 2.3,
      "median_delay_minutes": 1.8,
      "probability_delay_over_5min": 18.5,
      "status": "good"
    },
    {
      "forecast_time": "2025-10-01 16:00:00",
      "avg_delay_minutes": 3.1,
      "median_delay_minutes": 2.5,
      "probability_delay_over_5min": 22.3,
      "status": "moderate"
    },
    {
      "forecast_time": "2025-10-01 17:00:00",
      "avg_delay_minutes": 4.2,
      "median_delay_minutes": 3.6,
      "probability_delay_over_5min": 31.2,
      "status": "moderate"
    }
  ],
  "summary": {
    "avg_delay_next_3h": 3.2,
    "overall_status": "moderate"
  }
}
```

### Phase 3: REST API化（オプション・1時間）

#### 3.1 FastAPIでのエンドポイント実装

```python
# regional_delay_rest_api.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from regional_delay_api_proposal import RegionalDelayPredictionAPI
from typing import Optional

app = FastAPI(title="Regional Bus Delay Prediction API")

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API初期化
delay_api = RegionalDelayPredictionAPI()

@app.get("/")
def root():
    """APIルート"""
    return {
        "name": "Regional Bus Delay Prediction API",
        "version": "1.0.0",
        "endpoints": {
            "/regions": "利用可能な地域一覧",
            "/regions/{region_id}/predict": "地域別遅延予測",
            "/regions/all/status": "全地域の現在状況"
        }
    }

@app.get("/regions")
def list_regions():
    """利用可能な地域一覧"""
    return {
        "regions": [
            {"id": k, "name": v.name, "type": v.municipalities}
            for k, v in delay_api.region_manager.regions.items()
        ]
    }

@app.get("/regions/{region_id}/predict")
def predict_delay(
    region_id: str,
    forecast_hours: Optional[int] = 3,
    lookback_days: Optional[int] = 7
):
    """地域別遅延予測"""
    try:
        result = delay_api.predict_regional_delay(
            region_id=region_id,
            forecast_hours=forecast_hours,
            lookback_days=lookback_days
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/regions/all/status")
def all_regions_status(forecast_hours: Optional[int] = 1):
    """全地域の現在状況"""
    return delay_api.get_all_regions_status(forecast_hours)

# 起動
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

#### 3.2 API起動
```bash
# FastAPIインストール（必要に応じて）
pip install fastapi uvicorn

# API起動
python regional_delay_rest_api.py

# テスト
curl http://localhost:8000/regions
curl http://localhost:8000/regions/downtown_vancouver/predict?forecast_hours=3
curl http://localhost:8000/regions/all/status
```

---

## 📊 データ更新・保守

### 定期リフレッシュスケジュール

```bash
# crontab設定例
# 地域別ビューを1時間ごとにリフレッシュ
0 * * * * psql -d <database> -c "CALL gtfs_realtime.refresh_regional_views('recent');"

# hourlyビューを2時間ごとにリフレッシュ
0 */2 * * * psql -d <database> -c "CALL gtfs_realtime.refresh_regional_views('hourly');"

# dailyビューを毎日2時にリフレッシュ
0 2 * * * psql -d <database> -c "CALL gtfs_realtime.refresh_regional_views('daily');"

# rankingビューを毎日3時にリフレッシュ
0 3 * * * psql -d <database> -c "CALL gtfs_realtime.refresh_regional_views('ranking');"
```

### Pythonスクリプトでのリフレッシュ
```python
# refresh_regional_views.py
from src.data_connection import DatabaseConnector

def refresh_views():
    db = DatabaseConnector()
    with db.get_connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("CALL gtfs_realtime.refresh_regional_views('all')")
    print("Regional views refreshed successfully")

if __name__ == "__main__":
    refresh_views()
```

---

## 🔍 予測精度の向上方法

### 1. **機械学習モデルの統合**

現在の簡易予測（過去平均）から、既存の ConvLSTM モデルを地域別に適用：

```python
# regional_predictor.py に追加
from src.model_training import DelayPredictionModel

class MLBasedRegionalPredictor:
    def __init__(self, model_path: str):
        self.model = DelayPredictionModel.load_model(model_path)

    def predict_regional_delay_ml(self, region_id: str):
        # 1. 地域内の全ルートのデータを集約
        # 2. 地域レベルの特徴量エンジニアリング
        # 3. モデルで予測
        # 4. 地域全体の予測値として返す
        pass
```

### 2. **天候データの統合**

既存の `weather_data_retriever.py` を活用：

```python
# 地域別に天候情報を追加
weather_data = weather_retriever.get_weather_data()
# 予測時に天候を考慮（雨の日は遅延増加など）
```

### 3. **イベント・工事情報の統合**

外部データソースの追加：
- TransLink Service Alerts API
- City of Vancouver Construction Projects
- 大規模イベント情報（スポーツ、コンサート等）

---

## 📈 パフォーマンス最適化

### クエリ最適化

```sql
-- 地域別集約クエリの最適化例
EXPLAIN ANALYZE
SELECT region_id, AVG(arrival_delay)
FROM gtfs_realtime.regional_delays_recent_mv
WHERE time_bucket >= NOW() - INTERVAL '3 hours'
GROUP BY region_id;
```

### キャッシング戦略

```python
# Redis/Memcachedでのキャッシング
import redis
from datetime import timedelta

cache = redis.Redis(host='localhost', port=6379)

def get_regional_prediction_cached(region_id: str):
    cache_key = f"region_delay:{region_id}"
    cached = cache.get(cache_key)

    if cached:
        return json.loads(cached)

    # キャッシュがない場合は予測実行
    result = api.predict_regional_delay(region_id)

    # 15分間キャッシュ
    cache.setex(cache_key, timedelta(minutes=15), json.dumps(result))

    return result
```

---

## 🧪 テスト方法

### 単体テスト

```python
# tests/test_regional_api.py
import unittest
from regional_delay_api_proposal import RegionalDelayPredictionAPI, RegionManager

class TestRegionalAPI(unittest.TestCase):
    def setUp(self):
        self.api = RegionalDelayPredictionAPI()

    def test_region_list(self):
        regions = self.api.region_manager.regions
        self.assertGreater(len(regions), 0)
        self.assertIn('downtown_vancouver', regions)

    def test_predict_delay(self):
        result = self.api.predict_regional_delay('downtown_vancouver', forecast_hours=1)
        self.assertEqual(result['region_id'], 'downtown_vancouver')
        self.assertIn('predictions', result)
        self.assertEqual(len(result['predictions']), 1)

    def test_invalid_region(self):
        with self.assertRaises(ValueError):
            self.api.predict_regional_delay('invalid_region')

if __name__ == '__main__':
    unittest.main()
```

### 統合テスト

```bash
# APIサーバーを起動してテスト
python regional_delay_rest_api.py &

# cURLでテスト
curl -X GET "http://localhost:8000/regions/richmond/predict?forecast_hours=3"

# 期待: 200 OK + JSON レスポンス
```

---

## 📝 API仕様書（OpenAPI/Swagger）

FastAPIは自動的にSwagger UIを生成：

```
http://localhost:8000/docs
```

---

## 🎯 次のステップ

### フェーズ1（完了）
- [x] データ構造調査
- [x] 実装可否判定
- [x] SQLスクリプト作成
- [x] Pythonコード実装

### フェーズ2（推奨）
1. **正確な地域境界データの取得**
   - TransLink/Metro Vancouverから公式データ取得
   - GeoJSONまたはShapefileをPostGISにインポート

2. **REST API化**
   - FastAPIでのエンドポイント実装
   - 認証・レート制限の追加
   - API documentation

3. **機械学習モデルの統合**
   - 既存ConvLSTMモデルの地域別適用
   - 天候・イベントデータの統合

### フェーズ3（将来）
1. **ダッシュボード作成**
   - React/Vue.jsでのフロントエンド
   - Mapboxでの地図可視化
   - リアルタイム更新（WebSocket）

2. **アラート機能**
   - 遅延が閾値を超えたら通知
   - Email/SMS/Slack integration

3. **モバイルアプリ連携**
   - API経由でのモバイルアプリ統合

---

## 📚 参考資料

### データソース
- [TransLink Open Data](https://www.translink.ca/about-us/doing-business-with-translink/app-developer-resources)
- [Metro Vancouver Open Data](http://www.metrovancouver.org/data)
- [BC Data Catalogue](https://catalogue.data.gov.bc.ca/)
- [Statistics Canada Boundary Files](https://www12.statcan.gc.ca/census-recensement/2021/geo/sip-pis/boundary-limites/)

### 技術ドキュメント
- [PostGIS Documentation](https://postgis.net/documentation/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [GTFS Realtime Reference](https://developers.google.com/transit/gtfs-realtime)

---

**作成者:** GTFS Analysis Team
**最終更新:** 2025-10-01
