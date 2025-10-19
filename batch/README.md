# GTFS Batch Processing

このディレクトリは、GTFS関連のバッチ処理をモジュール化し、一元管理するためのパッケージです。

> **📝 重要**: 2025年1月にリファクタリングを実施しました。詳細は [REFACTORING.md](REFACTORING.md) を参照してください。

## 🆕 新機能

- ✅ 共通基底クラスによる統一インターフェース
- ✅ APIキーの環境変数化（セキュリティ向上）
- ✅ 共通ユーティリティモジュール（コードの重複排除）
- ✅ 改善されたエラーハンドリング
- ✅ 型ヒントによる型安全性向上
- ✅ Realtime取得時のマテリアライズドビュー自動リフレッシュ 🆕

## 📁 ディレクトリ構造

```
batch/
├── __init__.py                    # パッケージ初期化
├── README.md                      # このドキュメント
├── REFACTORING.md                 # リファクタリングガイド 🆕
├── run.py                         # 統一CLIエントリーポイント ⭐
├── config/                        # 設定管理
│   ├── __init__.py
│   └── settings.py               # 環境変数・設定値（改善済み）
├── jobs/                          # ジョブ定義
│   ├── __init__.py
│   ├── base_job.py               # 基底クラス 🆕
│   ├── regional_delay_prediction.py  # 地域遅延予測ジョブ
│   ├── gtfs_realtime_load.py     # GTFS Realtimeフェッチジョブ
│   ├── gtfs_static_load.py       # GTFS Static読み込みジョブ（改善済み）
│   └── weather_scraper.py        # 気象データスクレイピングジョブ
├── utils/                         # 共通ユーティリティ 🆕
│   ├── __init__.py
│   ├── error_handler.py          # カスタムエラークラス
│   ├── file_utils.py             # ファイル操作
│   ├── db_utils.py               # データベース操作
│   └── mv_utils.py               # マテリアライズドビュー操作 🆕
├── controller/                    # コントローラー層（既存）
│   ├── fetch_gtfs_realtime.py
│   ├── load_gtfs_realtime.py
│   ├── load_gtfs_static.py
│   └── clean_climate_data.py
├── services/                      # サービス層（既存）
│   ├── feed_message_service.py
│   ├── trip_updates_service.py
│   ├── vehicle_positions_service.py
│   └── alerts_service.py
├── models/                        # モデル層（既存）
│   └── realtime/
├── schedulers/                    # スケジューラー設定
│   ├── cron_prediction.sh        # Cron: 地域遅延予測
│   ├── cron_fetch.sh             # Cron: GTFSフェッチ
│   ├── cron_static_load.sh       # Cron: GTFS Static読み込み
│   └── systemd/                  # Systemd Timer設定
│       ├── prediction.service
│       ├── prediction.timer
│       ├── fetch.service
│       ├── fetch.timer
│       ├── static-load.service
│       └── static-load.timer
├── logs/                          # ログ出力先（自動生成）
└── downloads/                     # ダウンロードファイル保存先 🆕
    ├── climate/                   # 気候データ
    ├── gtfs_static/               # GTFS Staticデータ
    └── gtfs_realtime/             # GTFS Realtimeデータ
```

## 🚀 クイックスタート

### 1. 環境設定

**重要**: APIキーはセキュリティのため環境変数で管理します。

```bash
# .envファイルに必要な環境変数を設定
cat >> .env << EOF
# 必須設定
DATABASE_URL=postgresql://user:password@localhost:5432/gtfs
TRANSLINK_API_KEY=your_api_key_here

# オプション設定
LOG_LEVEL=INFO
PREDICTION_MODEL_PATH=files/model/best_delay_model.h5
GTFS_RT_CLEANUP_DAYS=7
WEATHER_SCRAPER_ROW_LIMIT=40
EOF
```

または、システム環境変数として設定:

```bash
export TRANSLINK_API_KEY=your_api_key_here
export DATABASE_URL=postgresql://user:password@localhost:5432/gtfs
```

### 2. ジョブの実行

#### 統一CLIを使用（推奨）

```bash
# 地域遅延予測を実行
python batch/run.py predict

# GTFS Realtimeデータを取得
python batch/run.py load-realtime

# GTFS Staticデータを読み込み
python batch/run.py load-static

# dry-runモード（DBに保存せずテスト実行）
python batch/run.py predict --dry-run
python batch/run.py load-realtime --dry-run
python batch/run.py load-static --dry-run

# 詳細ログ
python batch/run.py predict --verbose
python batch/run.py load-realtime --verbose
python batch/run.py load-static --verbose
```

#### 個別に実行

```python
# Pythonから直接実行
from batch.jobs.regional_delay_prediction import RegionalDelayPredictionJob
from batch.jobs.gtfs_realtime_fetch import GTFSRealtimeFetchJob

# 地域遅延予測
job = RegionalDelayPredictionJob()
results = job.run()

# GTFSフェッチ
job = GTFSRealtimeFetchJob()
results = job.run()
```

## 📋 利用可能なジョブ

### 1. Regional Delay Prediction (地域遅延予測)

**目的**: Metro Vancouver地域内の全地域についてバス遅延を予測し、DBに保存

**実行方法**:
```bash
# 基本実行
python batch/run.py predict

# 特定の地域のみ
python batch/run.py predict --regions vancouver burnaby

# カスタムモデルを指定
python batch/run.py predict --model-path files/model/custom_model.h5

# ドライラン
python batch/run.py predict --dry-run
```

**処理内容**:
1. 地域ごとに過去8時間のデータを取得
2. ConvLSTMモデルで3時間先までの遅延を予測
3. 予測結果を`gtfs_realtime.regional_delay_predictions`に保存

**実行頻度推奨**: 1時間ごと

**関連テーブル**:
- 入力: `gtfs_realtime.gtfs_rt_analytics_mv`, `climate.weather_hourly`
- 出力: `gtfs_realtime.regional_delay_predictions`

### 2. GTFS Realtime load-realtime (GTFSリアルタイムデータ取得)

**目的**: TransLink APIからGTFS Realtimeデータを取得しDBに保存 + マテリアライズドビューを自動更新

**実行方法**:
```bash
# 基本実行（全フィード + MVリフレッシュ）
python batch/run.py load-realtime

# 特定のフィードのみ
python batch/run.py load-realtime --feeds trip_updates vehicle_positions

# MVリフレッシュをスキップ
python batch/run.py load-realtime --no-refresh-mv

# ディスクに保存しない
python batch/run.py load-realtime --no-save-disk

# クリーンアップなし
python batch/run.py load-realtime --no-cleanup

# ファイル保持期間を変更
python batch/run.py load-realtime --days-to-keep 14

# ドライラン
python batch/run.py load-realtime --dry-run
```

**処理内容**:
1. TransLink APIから3種類のフィード（trip_updates, vehicle_positions, alerts）を取得
2. Protobuf形式で検証
3. ディスクに保存（オプション）
4. データベースにパースして保存
5. **マテリアライズドビューをリフレッシュ（CONCURRENTLY、ブロックなし）** 🆕
6. 古いファイルをクリーンアップ

**マテリアライズドビューのリフレッシュ**:
- デフォルトで有効（`--no-refresh-mv`で無効化可能）
- ベースビュー（`gtfs_rt_base_mv`）のみをリフレッシュ（高速）
- `CONCURRENTLY`オプション使用でクエリをブロックしない
- リフレッシュ統計情報をログに出力

**実行頻度推奨**: 毎時2回（0分・30分）

**関連テーブル**:
- 出力: `gtfs_realtime.feed_messages`, `gtfs_realtime.trip_updates`, `gtfs_realtime.vehicle_positions`, `gtfs_realtime.alerts`
- リフレッシュ: `gtfs_realtime.gtfs_rt_base_mv` 🆕

### 3. GTFS Static Load (GTFS Staticデータ読み込み)

**目的**: TransLink APIからGTFS Static CSVファイルをダウンロードし、DBに読み込み

**重要**: このジョブはTransLink APIキーを使用してGTFS Staticデータをダウンロードします。
APIキーは環境変数 `TRANSLINK_API_KEY` で設定してください。

**実行方法**:
```bash
# 基本実行（APIからダウンロード - APIキー必須）
export TRANSLINK_API_KEY=your_api_key_here
python batch/run.py load-static

# 既存のディレクトリから読み込み（APIキー不要）
python batch/run.py load-static --gtfs-dir /path/to/gtfs/csv --no-download

# カスタムダウンロードURL（APIキー必須）
python batch/run.py load-static --download-url https://gtfsapi.translink.ca/v3/gtfsstatic

# ドライラン（ダウンロードのみ、DB保存なし）
python batch/run.py load-static --dry-run
```

**APIエンドポイント**:
- デフォルトURL: `https://gtfsapi.translink.ca/v3/gtfsstatic?apikey=YOUR_API_KEY`
- メソッド: GET
- 認証: APIキー（クエリパラメータ）
- レスポンス: ZIP形式（GTFS CSVファイルを含む）

**処理内容**:
1. TransLink APIからGTFS Static ZIPファイルをダウンロード（または既存ディレクトリを使用）
2. ZIPを解凍してCSVファイルを抽出
3. 各CSVファイルを前処理（日付フォーマット変換、時刻変換など）
4. 依存関係順にデータベースに読み込み
5. 重複チェックと新規レコードのみ挿入

**実行頻度推奨**: 週次または月次（GTFSスケジュール更新時）

**関連テーブル**:
- 出力: `gtfs_static.gtfs_agency`, `gtfs_static.gtfs_routes`, `gtfs_static.gtfs_stops`, `gtfs_static.gtfs_calendar`, `gtfs_static.gtfs_calendar_dates`, `gtfs_static.gtfs_trips_static`, `gtfs_static.gtfs_stop_times`, `gtfs_static.gtfs_shapes`, `gtfs_static.gtfs_feed_info`, `gtfs_static.gtfs_transfers`

## 🐳 Docker コンテナで実行

### Docker Compose を使用（推奨・最も簡単）

Dockerコンテナで実行すると、環境構築やスケジューラー設定が自動化されます。

#### 1. 環境変数の設定

`.env`ファイルに必要な環境変数を設定:

```bash
# .envファイルを作成
cat >> .env << EOF
# データベース設定
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
POSTGRES_DB=gtfs

# TransLink APIキー（必須）
TRANSLINK_API_KEY=your_api_key_here

# オプション設定
LOG_LEVEL=INFO
PREDICTION_MODEL_PATH=files/model/best_delay_model.h5
GTFS_RT_CLEANUP_DAYS=7
WEATHER_SCRAPER_ROW_LIMIT=40
EOF
```

#### 2. コンテナの起動

```bash
# 便利スクリプトを使用（推奨）
./run_batch.sh build   # イメージをビルド
./run_batch.sh start   # コンテナを起動

# または docker-compose を直接使用
docker-compose up -d batch
```

#### 3. 動作確認

```bash
# コンテナの状態確認
./run_batch.sh status

# ログを確認
./run_batch.sh logs

# cron ジョブの確認
./run_batch.sh cron-list
```

#### 4. 手動でジョブを実行

```bash
# 各種ジョブを手動実行
./run_batch.sh run-job load-realtime           # GTFS Realtime フェッチ
./run_batch.sh run-job predict         # 地域遅延予測
./run_batch.sh run-job scrape-weather  # 気象データスクレイピング
./run_batch.sh run-job load-static     # GTFS Static 読み込み

# dry-run モード
./run_batch.sh run-job load-realtime --dry-run
./run_batch.sh run-job predict --dry-run
```

#### 5. ログの確認

```bash
# 全ログを表示
./run_batch.sh logs

# 特定のジョブのログのみ表示
./run_batch.sh logs-fetch
./run_batch.sh logs-predict
./run_batch.sh logs-weather
./run_batch.sh logs-static

# コンテナ内のログファイルを直接確認
./run_batch.sh exec ls -la batch/logs/
./run_batch.sh exec tail -f batch/logs/cron_fetch.log
```

#### 6. コンテナ管理

```bash
# コンテナを停止
./run_batch.sh stop

# コンテナを再起動
./run_batch.sh restart

# コンテナ内でシェルを開く
./run_batch.sh shell

# コンテナ内でコマンドを実行
./run_batch.sh exec python batch/run.py --help

# コンテナを削除
./run_batch.sh clean

# 完全に再ビルド
./run_batch.sh rebuild
```

### Docker コンテナの cron スケジュール

コンテナ起動時に以下のcronジョブが自動設定されます:

- **GTFS Realtime Fetch**: 5分ごと (`*/5 * * * *`)
- **Regional Delay Prediction**: 毎時5分 (`5 * * * *`)
- **Weather Scraper**: 6時間ごと10分 (`10 */6 * * *`)
- **GTFS Static Load**: 毎週日曜日3:00 AM (`0 3 * * 0`)

スケジュールをカスタマイズする場合は、`Dockerfile.batch`を編集してリビルドしてください。

### Docker コンテナの構成

```yaml
# docker-compose.yml の batch サービス
services:
  batch:
    build:
      context: .
      dockerfile: Dockerfile.batch
    container_name: gtfs-batch
    environment:
      DATABASE_URL: postgresql://...
      TRANSLINK_API_KEY: ${TRANSLINK_API_KEY}
      ...
    volumes:
      - ./batch/logs:/app/batch/logs        # ログ永続化
      - ./files:/app/files                  # モデルファイル
      - ./GTFS-static:/app/GTFS-static      # GTFS Static データ
    depends_on:
      - postgres
    restart: unless-stopped
```

### Docker を使わない場合

## ⏰ スケジューラーのセットアップ

### 方法1: Cron（シンプル）

```bash
# Cronジョブを設定
crontab -e

# 以下を追加:
# 地域遅延予測（毎時0分）
0 * * * * /home/taita/repository/DataScience/class/GTFS/batch/schedulers/cron_prediction.sh

# GTFSフェッチ（5分ごと）
*/5 * * * * /home/taita/repository/DataScience/class/GTFS/batch/schedulers/cron_fetch.sh

# GTFS Static読み込み（毎週日曜日の午前3時）
0 3 * * 0 /home/taita/repository/DataScience/class/GTFS/batch/schedulers/cron_static_load.sh
```

### 方法2: Systemd Timer（推奨・本番環境向け）

#### 地域遅延予測

```bash
# サービスとタイマーをインストール
sudo cp batch/schedulers/systemd/prediction.* /etc/systemd/system/
sudo systemctl daemon-reload

# 有効化・起動
sudo systemctl enable prediction.timer
sudo systemctl start prediction.timer

# ステータス確認
systemctl status prediction.timer
```

#### GTFSフェッチ

```bash
# サービスとタイマーをインストール
sudo cp batch/schedulers/systemd/fetch.* /etc/systemd/system/
sudo systemctl daemon-reload

# 有効化・起動
sudo systemctl enable fetch.timer
sudo systemctl start fetch.timer

# ステータス確認
systemctl status fetch.timer
```

#### GTFS Static読み込み

```bash
# サービスとタイマーをインストール
sudo cp batch/schedulers/systemd/static-load.* /etc/systemd/system/
sudo systemctl daemon-reload

# 有効化・起動
sudo systemctl enable static-load.timer
sudo systemctl start static-load.timer

# ステータス確認
systemctl status static-load.timer
```

#### タイマーの確認・管理

```bash
# タイマー一覧表示
systemctl list-timers --all | grep -E "(prediction|fetch|static)"

# 次回実行時刻を確認
systemctl status prediction.timer
systemctl status fetch.timer
systemctl status static-load.timer

# 手動で即座に実行
sudo systemctl start prediction.service
sudo systemctl start fetch.service
sudo systemctl start static-load.service

# ログ確認
sudo journalctl -u prediction.service -f
sudo journalctl -u fetch.service -f
sudo journalctl -u static-load.service -f

# または、アプリケーションログを確認
tail -f batch/logs/regional_prediction_$(date +%Y%m%d).log
tail -f batch/logs/gtfs_fetch_$(date +%Y%m%d).log
tail -f batch/logs/gtfs_static_load_$(date +%Y%m%d).log

# タイマーを停止・無効化
sudo systemctl stop prediction.timer
sudo systemctl disable prediction.timer
```

## ⚙️ 設定

### 環境変数

`.env`ファイルまたはシステム環境変数で設定:

```bash
# ========================================
# 必須設定
# ========================================

# データベース接続
DATABASE_URL=postgresql://user:password@localhost:5432/gtfs
# または
POSTGRES_URL=postgresql://user:password@localhost:5432/gtfs

# TransLink APIキー（GTFSフェッチ・Static読み込み用）
TRANSLINK_API_KEY=your_api_key_here

# ========================================
# オプション設定
# ========================================

# TransLink API設定
TRANSLINK_API_BASE_URL=https://gtfsapi.translink.ca

# ストレージディレクトリ
REALTIME_STORAGE_DIR=/path/to/realtime/storage
STATIC_STORAGE_DIR=/path/to/static/storage

# GTFS Realtime設定
GTFS_RT_CLEANUP_DAYS=7

# Weather Scraper設定
WEATHER_SCRAPER_URL=https://vancouver.weatherstats.ca/download.html
WEATHER_SCRAPER_ROW_LIMIT=40
WEATHER_FILE_CLEANUP_DAYS=7

# 地域遅延予測設定
PREDICTION_MODEL_PATH=files/model/best_delay_model.h5
PREDICTION_INPUT_TIMESTEPS=8
PREDICTION_OUTPUT_TIMESTEPS=3

# ロギング設定
LOG_LEVEL=INFO
```

### 設定ファイル

[batch/config/settings.py](config/settings.py)で以下を管理:
- プロジェクトルート
- ログディレクトリ
- モデルディレクトリ
- データベースURL
- TransLink API設定
- GTFS Realtime設定
- 予測モデル設定
- ロギング設定

## 📊 実行結果の確認

### ログから確認

```bash
# 最新のログを表示
tail -100 batch/logs/regional_prediction_$(date +%Y%m%d).log
tail -100 batch/logs/gtfs_fetch_$(date +%Y%m%d).log
tail -100 batch/logs/gtfs_static_load_$(date +%Y%m%d).log

# エラーのみ抽出
grep -i error batch/logs/*.log

# 成功したジョブを確認
grep "completed successfully" batch/logs/*.log
```

### データベースから確認

#### 地域遅延予測

```sql
-- 最新の予測を確認
SELECT * FROM gtfs_realtime.regional_predictions_latest LIMIT 10;

-- 地域別の予測件数
SELECT region_id, COUNT(*) as count
FROM gtfs_realtime.regional_delay_predictions
WHERE prediction_created_at >= NOW() - INTERVAL '1 hour'
GROUP BY region_id;

-- 最新の予測バッチ
SELECT prediction_created_at, COUNT(*) as total_predictions
FROM gtfs_realtime.regional_delay_predictions
GROUP BY prediction_created_at
ORDER BY prediction_created_at DESC
LIMIT 10;
```

#### GTFSフェッチ

```sql
-- 最新のフィードメッセージ
SELECT id, feed_type, created_at, size_bytes
FROM gtfs_realtime.feed_messages
ORDER BY created_at DESC
LIMIT 10;

-- フィードタイプ別の取得件数（過去24時間）
SELECT feed_type, COUNT(*) as count
FROM gtfs_realtime.feed_messages
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY feed_type;
```

#### GTFS Static

```sql
-- 各テーブルのレコード数を確認
SELECT
    'gtfs_agency' as table_name,
    COUNT(*) as row_count
FROM gtfs_static.gtfs_agency
UNION ALL
SELECT 'gtfs_routes', COUNT(*) FROM gtfs_static.gtfs_routes
UNION ALL
SELECT 'gtfs_stops', COUNT(*) FROM gtfs_static.gtfs_stops
UNION ALL
SELECT 'gtfs_calendar', COUNT(*) FROM gtfs_static.gtfs_calendar
UNION ALL
SELECT 'gtfs_trips_static', COUNT(*) FROM gtfs_static.gtfs_trips_static
UNION ALL
SELECT 'gtfs_stop_times', COUNT(*) FROM gtfs_static.gtfs_stop_times;

-- 最新のフィード情報
SELECT * FROM gtfs_static.gtfs_feed_info;

-- ルート一覧
SELECT route_id, route_short_name, route_long_name
FROM gtfs_static.gtfs_routes
LIMIT 10;
```

## 🧹 メンテナンス

### ログのクリーンアップ

```bash
# 30日以上前のログを削除
find batch/logs/ -name "*.log" -mtime +30 -delete
```

### 古いデータの削除

```sql
-- 地域遅延予測（7日以上前）
DELETE FROM gtfs_realtime.regional_delay_predictions
WHERE prediction_created_at < NOW() - INTERVAL '7 days';

-- GTFSリアルタイムデータ（7日以上前）
DELETE FROM gtfs_realtime.feed_messages
WHERE created_at < NOW() - INTERVAL '7 days';
```

### 古いProtobufファイルの削除

```bash
# 手動で削除
find GTFS-api/proto/realtime_data/ -name "*.pb" -mtime +7 -delete

# またはジョブ実行時に自動削除（デフォルト）
python batch/run.py load-realtime  # --days-to-keep 7がデフォルト
```

## ⚠️ トラブルシューティング

### 1. モジュールが見つからないエラー

```bash
# プロジェクトルートから実行していることを確認
cd /path/to/GTFS
python batch/run.py predict
```

### 2. データベース接続エラー

```bash
# 環境変数の確認
python -c "import os; print(os.getenv('DATABASE_URL'))"

# PostgreSQL接続テスト
psql $DATABASE_URL -c "SELECT 1"
```

### 3. APIキーエラー（GTFSフェッチ）

```bash
# 環境変数の確認
python -c "import os; print(os.getenv('TRANSLINK_API_KEY'))"

# .envファイルの確認
grep TRANSLINK_API_KEY .env
```

### 4. モデルファイルが見つからない（地域遅延予測）

```bash
# モデルファイルの存在確認
ls -lh files/model/best_delay_model*.h5

# 明示的にパスを指定
python batch/run.py predict --model-path files/model/your_model.h5
```

### 5. メモリ不足エラー

```bash
# Systemd serviceファイルのMemoryMaxを増やす
sudo nano /etc/systemd/system/prediction.service
# MemoryMax=4G → MemoryMax=8G

sudo systemctl daemon-reload
sudo systemctl restart prediction.service
```

## 🔄 アップグレードガイド

### 2025年1月リファクタリング

**主な変更点**:
- ✅ APIキーのハードコード削除（環境変数化）
- ✅ 共通基底クラスの導入（`BaseJob`, `DatabaseJob`, etc.）
- ✅ 共通ユーティリティモジュールの追加（`batch/utils/`）
- ✅ 改善されたエラーハンドリングと型ヒント
- ✅ 統一されたインターフェース

詳細は [REFACTORING.md](REFACTORING.md) を参照してください。

### 旧scriptsフォルダからの移行

```bash
# 旧スクリプト（非推奨）
python scripts/batch_regional_delay_prediction.py
python scripts/batch_gtfs_realtime_fetch.py

# ↓ 新しいバッチシステム（推奨）
python batch/run.py predict
python batch/run.py load-realtime
```

**変更点**:
- ✅ 統一されたCLIエントリーポイント（`batch/run.py`）
- ✅ モジュール化されたジョブ（`batch/jobs/`）
- ✅ 集約された設定管理（`batch/config/`）
- ✅ ログの一元管理（`batch/logs/`）
- ✅ スケジューラーの統一（`batch/schedulers/`）
- ✅ 共通ユーティリティ（`batch/utils/`）

## 📈 パフォーマンス

### 地域遅延予測
- **実行時間**: 地域あたり5-15秒
- **メモリ使用量**: 2-4GB
- **推奨実行頻度**: 1時間ごと

### GTFSフェッチ
- **実行時間**: 20-40秒（3フィード）
- **メモリ使用量**: 500MB-1GB
- **推奨実行頻度**: 5-10分ごと

### GTFS Static読み込み
- **実行時間**: 2-10分（ダウンロード含む）
- **メモリ使用量**: 2-4GB（stop_timesが大きいため）
- **推奨実行頻度**: 週次または月次

## 📝 運用チェックリスト

- [ ] 環境変数（DATABASE_URL, TRANSLINK_API_KEY）が設定されている
- [ ] データベーステーブルが作成されている
- [ ] モデルファイルが存在する（地域遅延予測）
- [ ] ジョブが手動で正常に実行できる
- [ ] スケジューラー（Cron/Systemd）が設定されている
- [ ] ログファイルが生成されている
- [ ] データベースにデータが保存されている
- [ ] ログローテーション・データクリーンアップが設定されている

## 🔗 関連ドキュメント

- [REFACTORING.md](REFACTORING.md) - リファクタリングガイド 🆕
- [CLAUDE.md](../CLAUDE.md) - プロジェクト全体のドキュメント
- [DB/08_create_regional_predictions_table.sql](../DB/08_create_regional_predictions_table.sql) - 予測結果テーブル定義
- [GTFS-api/proto/README.md](../GTFS-api/proto/README.md) - GTFS Realtime APIの詳細
- [notebook/regional_delay_prediction.ipynb](../notebook/regional_delay_prediction.ipynb) - 予測ロジックの詳細

## 💡 ベストプラクティス

1. **dry-runモードで事前テスト**: 本番実行前に必ずdry-runで動作確認
2. **ログの定期確認**: エラーログを定期的にチェック
3. **データクリーンアップの設定**: ディスク容量を節約するため古いデータを削除
4. **監視の設定**: ジョブの成功/失敗をモニタリング
5. **バックアップ**: 重要な期間のデータはバックアップを推奨
