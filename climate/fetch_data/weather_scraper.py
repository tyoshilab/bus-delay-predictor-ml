#!/usr/bin/env python3
"""
Vancouver Weather Data Scraper
バンクーバーの気象データを1時間ごとに自動取得するスクレイピングプログラム
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
import logging
import schedule
from playwright.async_api import async_playwright
import pandas as pd

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.data_connection.database_connector import DatabaseConnector

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/workspace/GTFS/climate/scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class VancouverWeatherScraper:
    """バンクーバー気象データスクレイピングクラス"""
    
    def __init__(self, download_dir="/workspace/GTFS/climate/downloads"):
        """
        初期化
        
        Args:
            download_dir (str): ダウンロードディレクトリパス
        """
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.base_url = "https://vancouver.weatherstats.ca/download.html"
        self.db_connector = None
        
    async def setup_browser(self):
        """ブラウザセットアップ"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=True,  # ヘッドレスモード
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
        self.downloaded_files = []
        self.page.on("download", self._handle_download)
        
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
            logger.info(f"ファイルダウンロード完了: {file_path}")
            
        except Exception as e:
            logger.error(f"ダウンロードエラー: {e}")
    
    async def scrape_hourly_data(self, row_limit=10000):
        """
        Climate Hourlyデータの取得
        
        Args:
            row_limit (int): 取得行数制限
            
        Returns:
            str: ダウンロードされたファイルパス
        """
        try:
            logger.info("バンクーバー気象データページにアクセス中...")
            await self.page.goto(self.base_url, wait_until="networkidle")
            
            # ページ読み込み完了を待機
            await self.page.wait_for_selector('form#form_download', timeout=10000)
            
            # Climate Hourlyオプションを選択
            logger.info("Climate Hourlyオプションを選択中...")
            await self.page.check('input[name="type"][value="hourly"]')
            
            # 行数制限を設定
            await self.page.fill('input[name="limit"]', str(row_limit))
            
            # ダウンロード開始前のファイル数を記録
            initial_file_count = len(self.downloaded_files)
            
            # ダウンロードボタンクリック
            logger.info("ダウンロード開始...")
            await self.page.click('input[name="submit"][value="Download"]')
            
            # ダウンロード完了まで待機（最大60秒）
            timeout = 60
            start_time = time.time()
            
            while len(self.downloaded_files) == initial_file_count:
                if time.time() - start_time > timeout:
                    raise TimeoutError("ダウンロードタイムアウト")
                await asyncio.sleep(1)
            
            downloaded_file = self.downloaded_files[-1]
            logger.info(f"ダウンロード完了: {downloaded_file}")
            
            return downloaded_file
            
        except Exception as e:
            logger.error(f"スクレイピングエラー: {e}")
            raise
    
    async def validate_downloaded_file(self, file_path):
        """
        ダウンロードファイルの検証
        
        Args:
            file_path (Path): ファイルパス
            
        Returns:
            bool: 検証結果
        """
        try:
            if not file_path.exists():
                logger.error(f"ファイルが存在しません: {file_path}")
                return False
                
            # ファイルサイズチェック
            file_size = file_path.stat().st_size
            if file_size < 1000:  # 1KB未満はエラーファイルとみなす
                logger.error(f"ファイルサイズが小さすぎます: {file_size} bytes")
                return False
            
            # CSV形式の基本チェック
            df = pd.read_csv(file_path, nrows=5)
            if df.empty:
                logger.error("CSVファイルが空です")
                return False
                
            logger.info(f"ファイル検証成功: {file_size} bytes, {len(df)} 行")
            return True
            
        except Exception as e:
            logger.error(f"ファイル検証エラー: {e}")
            return False
    
    async def load_to_database(self, file_path):
        """
        データベースへの自動ロード
        
        Args:
            file_path (Path): CSVファイルパス
        """
        try:
            if not self.db_connector:
                self.db_connector = DatabaseConnector()
            
            # load_weathers.pyの機能を使用してデータベースにロード
            from climate.load_weathers import load_weather_csv_to_table
            
            load_weather_csv_to_table(
                csv_path=str(file_path), 
                table_name='weather_hourly',
                db_connector=self.db_connector
            )
            
            logger.info(f"データベースロード完了: {file_path}")
            
        except Exception as e:
            logger.error(f"データベースロードエラー: {e}")
    
    async def cleanup_old_files(self, keep_days=7):
        """
        古いファイルの削除
        
        Args:
            keep_days (int): 保持日数
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=keep_days)
            deleted_count = 0
            
            for file_path in self.download_dir.glob("vancouver_weather_hourly_*.csv"):
                if file_path.stat().st_mtime < cutoff_time.timestamp():
                    file_path.unlink()
                    deleted_count += 1
                    
            if deleted_count > 0:
                logger.info(f"{deleted_count}個の古いファイルを削除しました")
                
        except Exception as e:
            logger.error(f"ファイル削除エラー: {e}")
    
    async def run_single_scrape(self, load_to_db=True):
        """
        単発スクレイピング実行
        
        Args:
            load_to_db (bool): データベースへの自動ロード
        """
        try:
            await self.setup_browser()
            
            # データ取得
            downloaded_file = await self.scrape_hourly_data(2)
            
            # ファイル検証
            if await self.validate_downloaded_file(downloaded_file):
                logger.info("データ取得成功")
                
                # データベースロード
                if load_to_db:
                    await self.load_to_database(downloaded_file)
                    
                # 古いファイル削除
                await self.cleanup_old_files()
                
            else:
                logger.error("データ取得失敗")
                
        except Exception as e:
            logger.error(f"スクレイピング実行エラー: {e}")
            
        finally:
            await self.cleanup_browser()
    
    async def cleanup_browser(self):
        """ブラウザクリーンアップ"""
        try:
            if hasattr(self, 'context'):
                await self.context.close()
            if hasattr(self, 'browser'):
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"ブラウザクリーンアップエラー: {e}")


class WeatherScraperScheduler:
    """スケジューラークラス"""
    
    def __init__(self):
        self.scraper = VancouverWeatherScraper()
        
    def schedule_hourly_scraping(self):
        """1時間ごとのスクレイピングをスケジュール"""
        logger.info("1時間ごとのスクレイピングスケジュールを開始...")
        
        # 毎時0分に実行
        schedule.every().hour.at(":00").do(self.run_scheduled_scrape)
        
        # 初回実行
        self.run_scheduled_scrape()
        
        # スケジュール実行ループ
        while True:
            schedule.run_pending()
            time.sleep(60)  # 1分ごとにチェック
    
    def run_scheduled_scrape(self):
        """スケジュール実行ラッパー"""
        try:
            logger.info("定期スクレイピング開始...")
            asyncio.run(self.scraper.run_single_scrape())
            logger.info("定期スクレイピング完了")
            
        except Exception as e:
            logger.error(f"定期スクレイピングエラー: {e}")


async def main():
    """メイン実行関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Vancouver Weather Data Scraper")
    parser.add_argument("--mode", choices=["single", "schedule"], default="single",
                       help="実行モード: single=単発実行, schedule=定期実行")
    parser.add_argument("--no-db", action="store_true", 
                       help="データベースロードをスキップ")
    
    args = parser.parse_args()
    
    if args.mode == "single":
        # 単発実行
        scraper = VancouverWeatherScraper()
        await scraper.run_single_scrape(load_to_db=not args.no_db)
        
    elif args.mode == "schedule":
        # 定期実行
        scheduler = WeatherScraperScheduler()
        scheduler.schedule_hourly_scraping()


if __name__ == "__main__":
    asyncio.run(main())