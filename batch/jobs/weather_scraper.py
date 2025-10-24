#!/usr/bin/env python3
"""
Weather Data Scraper Job

Vancouver気象データをスクレイピングし、クリーニングしてデータベースに保存します。
既存データを確認し、不足期間を自動計算して取得します。
"""

import sys
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import time
from datetime import datetime, timedelta
import asyncio
import pandas as pd
from playwright.async_api import async_playwright

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from batch.config.database_connector import DatabaseConnector
from batch.controller.clean_climate_data import ClimateDataCleaner
from batch.config.settings import config
from batch.jobs.base_job import ScraperJob
from batch.utils.file_utils import validate_file, cleanup_old_files

logger = logging.getLogger(__name__)


class WeatherScraperJob(ScraperJob):
    """気象データスクレイピングジョブ"""

    def __init__(
        self,
        download_dir: Optional[Path] = None,
        base_url: Optional[str] = None,
        row_limit: Optional[int] = None,
        auto_calculate_rows: bool = True
    ):
        """
        初期化

        Args:
            download_dir: ダウンロードディレクトリ（Noneの場合は設定から取得）
            base_url: スクレイピング対象URL（Noneの場合は設定から取得）
            row_limit: 取得行数制限（Noneの場合は自動計算）
            auto_calculate_rows: DBの最新データから自動計算するか
        """
        # 基底クラスの初期化
        super().__init__(
            job_name="WeatherScraperJob",
            download_dir=download_dir or config.directories.climate_download_dir
        )

        # 設定
        self.base_url = base_url or config.weather_scraper.url
        self.row_limit = row_limit
        self.auto_calculate_rows = auto_calculate_rows

        # データベース接続
        self.db_connector = None

        # Playwright関連
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

        self.logger.info(f"WeatherScraperJob initialized")
        self.logger.info(f"  - URL: {self.base_url}")
        self.logger.info(f"  - Download dir: {self.download_dir}")
        self.logger.info(f"  - Auto calculate rows: {self.auto_calculate_rows}")

    def get_latest_weather_data_time(self) -> Optional[datetime]:
        """
        データベースから最新の気象データ時刻を取得

        Returns:
            最新のデータ時刻（unixtimeから変換）
        """
        try:
            if not self.db_connector:
                self.db_connector = DatabaseConnector()

            query = """
                SELECT MAX(unixtime) as latest_unixtime
                FROM climate.weather_hourly
            """

            result = self.db_connector.read_sql(query)

            if result is not None and not result.empty:
                latest_unixtime = result['latest_unixtime'].iloc[0]
                if pd.notna(latest_unixtime):
                    latest_time = datetime.fromtimestamp(int(latest_unixtime))
                    self.logger.info(f"Latest weather data in DB: {latest_time}")
                    return latest_time

            self.logger.info("No weather data found in DB")
            return None

        except Exception as e:
            self.logger.error(f"Error getting latest weather data time: {e}")
            return None

    def calculate_required_rows(
        self,
        latest_time: Optional[datetime] = None,
        current_time: Optional[datetime] = None
    ) -> int:
        """
        必要な取得行数を計算

        Args:
            latest_time: DBの最新データ時刻（Noneの場合は自動取得）
            current_time: 現在時刻（Noneの場合はdatetime.now()）

        Returns:
            必要な行数
        """
        if current_time is None:
            current_time = datetime.now()

        # 現在の時刻を1時間前に丸める（不完全な時間帯を除外）
        # 例: 12:30の場合、11:00までのデータを取得
        complete_hour = current_time.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)

        if latest_time is None:
            latest_time = self.get_latest_weather_data_time()

        if latest_time is None:
            # DBにデータがない場合はデフォルト値（48時間分）
            required_rows = config.weather_scraper.row_limit
            self.logger.info(f"No existing data, using default: {required_rows} rows")
        else:
            # 最新データの次の時刻から完全な時刻までの時間数を計算
            next_hour = latest_time + timedelta(hours=1)
            hours_diff = (complete_hour - next_hour).total_seconds() / 3600

            if hours_diff <= 0:
                # 既にデータが最新の場合
                required_rows = 1
                self.logger.info("Data is up to date, fetching minimum rows")
            else:
                # 不足している時間数 + バッファ（数行）
                required_rows = int(hours_diff) + 5
                self.logger.info(
                    f"Missing data from {next_hour} to {complete_hour} "
                    f"({int(hours_diff)} hours) - fetching {required_rows} rows"
                )

        # 最小値と最大値の制限
        required_rows = max(1, min(required_rows, 1000))

        return required_rows

    async def setup_browser(self):
        """ブラウザセットアップ"""
        try:
            self.logger.info("Setting up browser...")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled'
                ]
            )

            # ブラウザコンテキスト作成（ダウンロード設定付き）
            self.context = await self.browser.new_context(
                accept_downloads=True,
                user_agent='Mozilla/5.0 (Linux; x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            )

            self.page = await self.context.new_page()

            # ダウンロードイベントの監視
            self.page.on("download", self._handle_download)

            self.logger.info("Browser setup completed")

        except Exception as e:
            self.logger.error(f"Failed to setup browser: {e}")
            raise

    async def _handle_download(self, download):
        """ダウンロードイベントハンドラ"""
        try:
            # ファイル名生成（タイムスタンプ付き）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"vancouver_weather_hourly_{timestamp}.csv"
            file_path = self.download_dir / filename

            # ファイル保存
            await download.save_as(file_path)
            self.downloaded_files.append(file_path)
            self.logger.info(f"File downloaded: {file_path}")

        except Exception as e:
            self.logger.error(f"Download error: {e}")

    async def scrape_hourly_data(self, row_limit: int) -> Optional[Path]:
        """
        Climate Hourlyデータの取得

        Args:
            row_limit: 取得行数

        Returns:
            ダウンロードされたファイルパス
        """
        try:
            self.logger.info(f"Accessing weather data page: {self.base_url}")
            await self.page.goto(self.base_url, wait_until="networkidle")

            # ページ読み込み完了を待機
            await self.page.wait_for_selector('form#form_download', timeout=10000)

            # Climate Hourlyオプションを選択
            self.logger.info("Selecting Climate Hourly option...")
            await self.page.check('input[name="type"][value="hourly"]')

            # 行数制限を設定
            self.logger.info(f"Setting row limit to: {row_limit}")
            await self.page.fill('input[name="limit"]', str(row_limit))

            # ダウンロード開始前のファイル数を記録
            initial_file_count = len(self.downloaded_files)

            # ダウンロードボタンクリック
            self.logger.info("Starting download...")
            await self.page.click('input[name="submit"][value="Download"]')

            # ダウンロード完了まで待機（最大60秒）
            timeout = 60
            start_time = time.time()

            while len(self.downloaded_files) == initial_file_count:
                if time.time() - start_time > timeout:
                    raise TimeoutError("Download timeout")
                await asyncio.sleep(1)

            downloaded_file = self.downloaded_files[-1]
            self.logger.info(f"Download completed: {downloaded_file}")

            return downloaded_file

        except Exception as e:
            self.logger.error(f"Scraping error: {e}")
            raise

    def filter_incomplete_hour_data(
        self,
        df: pd.DataFrame,
        current_time: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        不完全な時間帯のデータを除外

        Args:
            df: 気象データのDataFrame（unixtimeカラムを含む）
            current_time: 現在時刻（Noneの場合はdatetime.now()）

        Returns:
            フィルタリング済みのDataFrame
        """
        if df.empty or 'unixtime' not in df.columns:
            return df

        if current_time is None:
            current_time = datetime.now()

        # 現在の時刻を1時間前に丸める（完全な時刻）
        # 例: 12:30の場合、11:00までのデータのみ保持
        complete_hour = current_time.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        complete_hour_unix = int(complete_hour.timestamp())

        original_count = len(df)

        # unixtimeが完全な時刻以下のデータのみ保持
        df_filtered = df[df['unixtime'] <= complete_hour_unix].copy()

        filtered_count = len(df_filtered)
        removed_count = original_count - filtered_count

        if removed_count > 0:
            self.logger.info(
                f"Filtered out {removed_count} incomplete hour records "
                f"(keeping data up to {complete_hour})"
            )
        else:
            self.logger.info("No incomplete hour data to filter")

        return df_filtered

    async def validate_downloaded_file(self, file_path: Path) -> bool:
        """
        ダウンロードファイルの検証

        Args:
            file_path: ファイルパス

        Returns:
            検証結果
        """
        try:
            if not file_path.exists():
                self.logger.error(f"File does not exist: {file_path}")
                return False

            # ファイルサイズチェック
            file_size = file_path.stat().st_size

            # CSV形式の基本チェック
            df = pd.read_csv(file_path, nrows=5)
            if df.empty:
                self.logger.error("CSV file is empty")
                return False

            self.logger.info(f"File validation successful: {file_size} bytes")
            return True

        except Exception as e:
            self.logger.error(f"File validation error: {e}")
            return False

    async def clean_weather_data(self, file_path: Path) -> Optional[Path]:
        """
        気象データのクリーニング（不完全データの除外を含む）

        Args:
            file_path: 元のCSVファイルパス

        Returns:
            クリーニング済みCSVファイルパス
        """
        try:
            self.logger.info(f"Cleaning weather data: {file_path}")

            # クリーニング済みファイルのパスを生成
            cleaned_file = file_path.parent / f"{file_path.stem}_cleaned.csv"

            # ClimateDataCleanerを使用してクリーニング
            cleaner = ClimateDataCleaner(
                input_file=str(file_path),
                output_file=str(cleaned_file)
            )

            if not cleaner.run():
                self.logger.error("Data cleaning failed")
                return None

            # クリーニング済みデータを読み込んで不完全時刻を除外
            self.logger.info("Filtering out incomplete hour data...")
            df_cleaned = pd.read_csv(cleaned_file)

            df_filtered = self.filter_incomplete_hour_data(df_cleaned)

            if df_filtered.empty:
                self.logger.warning("All data filtered out (no complete hours available)")
                return None

            # フィルタリング済みデータを上書き保存
            df_filtered.to_csv(cleaned_file, index=False)

            self.logger.info(
                f"Data cleaning completed: {cleaned_file} "
                f"({len(df_filtered)} valid records)"
            )

            return cleaned_file

        except Exception as e:
            self.logger.error(f"Data cleaning error: {e}")
            return None

    async def load_to_database(self, file_path: Path) -> int:
        """
        データベースへの自動ロード（クリーニング済みデータ）

        Args:
            file_path: CSVファイルパス（元ファイル）

        Returns:
            挿入されたレコード数
        """
        try:
            if not self.db_connector:
                self.db_connector = DatabaseConnector()

            # 1. データクリーニング
            cleaned_file = await self.clean_weather_data(file_path)

            if cleaned_file is None:
                self.logger.error("Data cleaning failed, skipping database load")
                return 0

            # 2. クリーニング済みデータをデータベースにロード
            from batch.controller.load_weathers import load_weather_csv_to_table

            inserted_count = load_weather_csv_to_table(
                csv_path=str(cleaned_file),
                table_name='weather_hourly',
                db_connector=self.db_connector
            )

            self.logger.info(f"Database load completed: {inserted_count} records inserted")

            return inserted_count

        except Exception as e:
            self.logger.error(f"Database load error: {e}")
            raise

    async def cleanup_old_files_async(self, keep_days: Optional[int] = None):
        """
        古いファイルの削除（非同期版）

        Args:
            keep_days: 保持日数（Noneの場合は設定から取得）
        """
        if keep_days is None:
            keep_days = config.weather_scraper.cleanup_days

        # 基底クラスのcleanup_old_filesメソッドを使用
        patterns = [
            "vancouver_weather_hourly_*.csv",
            "vancouver_weather_hourly_*_cleaned.csv"
        ]

        for pattern in patterns:
            cleanup_old_files(
                self.download_dir,
                pattern=pattern,
                days_to_keep=keep_days
            )

    async def cleanup_browser(self):
        """ブラウザクリーンアップ"""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self.logger.info("Browser cleanup completed")
        except Exception as e:
            self.logger.error(f"Browser cleanup error: {e}")

    async def execute_async(
        self,
        load_to_db: bool = True,
        dry_run: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        ジョブの実際の処理を実装（非同期版）

        Args:
            load_to_db: データベースへの自動ロード
            dry_run: Trueの場合、DBに保存せずスクレイピングのみ実行
            **kwargs: その他のパラメータ

        Returns:
            実行結果のサマリ
        """
        results = {
            'downloaded_file': None,
            'cleaned_file': None,
            'loaded_to_db': False,
            'inserted_records': 0,
            'calculated_rows': None,
            'summary': {
                'processed_count': 0,
                'failed_count': 0,
                'skipped_count': 0
            }
        }

        try:
            # ステップ0: 必要行数の計算
            if self.row_limit is None and self.auto_calculate_rows:
                self.logger.info("=" * 60)
                self.logger.info("STEP 0: CALCULATING REQUIRED ROWS")
                self.logger.info("=" * 60)
                self.row_limit = self.calculate_required_rows()
                results['calculated_rows'] = self.row_limit
            else:
                if self.row_limit is None:
                    self.row_limit = 40  # デフォルト値
                self.logger.info(f"Using specified row limit: {self.row_limit}")

            # ステップ1: ブラウザセットアップ
            self.logger.info("=" * 60)
            self.logger.info("STEP 1: BROWSER SETUP")
            self.logger.info("=" * 60)
            await self.setup_browser()

            # ステップ2: データスクレイピング
            self.logger.info("=" * 60)
            self.logger.info("STEP 2: SCRAPING WEATHER DATA")
            self.logger.info("=" * 60)
            downloaded_file = await self.scrape_hourly_data(self.row_limit)
            results['downloaded_file'] = str(downloaded_file)

            # ステップ3: ファイル検証
            self.logger.info("=" * 60)
            self.logger.info("STEP 3: VALIDATING DOWNLOADED FILE")
            self.logger.info("=" * 60)
            if not await self.validate_downloaded_file(downloaded_file):
                self.logger.error("File validation failed")
                results['summary']['success'] = False
                return results

            # ステップ4: データベースロード（dry_runでない場合）
            if load_to_db and not dry_run:
                self.logger.info("=" * 60)
                self.logger.info("STEP 4: CLEANING AND LOADING TO DATABASE")
                self.logger.info("=" * 60)
                inserted_count = await self.load_to_database(downloaded_file)
                results['loaded_to_db'] = True
                results['inserted_records'] = inserted_count
            else:
                if dry_run:
                    self.logger.info("\n[DRY RUN] Skipping database load")
                    # dry-runでもクリーニングは実行してレコード数を表示
                    cleaned_file = await self.clean_weather_data(downloaded_file)
                    if cleaned_file:
                        df = pd.read_csv(cleaned_file)
                        self.logger.info(f"[DRY RUN] Would insert {len(df)} records")
                else:
                    self.logger.info("Database load disabled")

            # ステップ5: クリーンアップ
            self.logger.info("=" * 60)
            self.logger.info("STEP 5: CLEANING UP OLD FILES")
            self.logger.info("=" * 60)
            await self.cleanup_old_files_async()

            # 処理カウントを設定
            results['summary']['processed_count'] = 1 if results['downloaded_file'] else 0
            if results.get('inserted_records') and results['inserted_records'] > 0:
                self.processed_count = results['inserted_records']
                self.inserted_records = results['inserted_records']

        finally:
            await self.cleanup_browser()

        return results

    def execute(self, load_to_db: bool = True, dry_run: bool = False, **kwargs) -> Dict[str, Any]:
        """
        ジョブの実際の処理を実装（同期ラッパー）

        Args:
            load_to_db: データベースへの自動ロード
            dry_run: Trueの場合、DBに保存せずスクレイピングのみ実行
            **kwargs: その他のパラメータ

        Returns:
            実行結果のサマリ
        """
        return asyncio.run(self.execute_async(load_to_db=load_to_db, dry_run=dry_run, **kwargs))

    def _print_job_specific_summary(self, results: Dict[str, Any]):
        """ジョブ固有のサマリ表示"""
        summary = results.get('summary', {})

        self.logger.info(f"Calculated rows: {results.get('calculated_rows', 'N/A')}")
        self.logger.info(f"Downloaded file: {results.get('downloaded_file', 'N/A')}")
        self.logger.info(f"Loaded to DB: {results.get('loaded_to_db', False)}")
        self.logger.info(f"Inserted records: {results.get('inserted_records', 0)}")
        self.logger.info(f"Processed: {summary.get('processed_count', 0)}")


# 後方互換性のため残す（非推奨）
class WeatherScraperJobWrapper:
    """
    同期インターフェースを提供するラッパー

    Note: このクラスは後方互換性のために残されています。
    新しいコードでは WeatherScraperJob を直接使用してください。
    """

    def __init__(self, **kwargs):
        self.job = WeatherScraperJob(**kwargs)

    def run(self, load_to_db: bool = True, dry_run: bool = False) -> dict:
        """同期的に実行"""
        import warnings
        warnings.warn(
            "WeatherScraperJobWrapper is deprecated. Use WeatherScraperJob.run() instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return self.job.run(load_to_db=load_to_db, dry_run=dry_run)
