#!/usr/bin/env python3
"""
Weather Scraper Test Script
スクレイピング機能のテスト用スクリプト
"""

import asyncio
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from climate.weather_scraper import VancouverWeatherScraper

async def test_scraper():
    """スクレイパーのテスト実行"""
    print("=== Vancouver Weather Scraper テスト ===")
    
    scraper = VancouverWeatherScraper()
    
    try:
        # ブラウザセットアップ
        print("1. ブラウザセットアップ中...")
        await scraper.setup_browser()
        print("✅ ブラウザセットアップ完了")
        
        # データ取得テスト
        print("2. データ取得テスト中...")
        downloaded_file = await scraper.scrape_hourly_data(row_limit=100)  # テスト用に少なめ
        print(f"✅ ダウンロード完了: {downloaded_file}")
        
        # ファイル検証
        print("3. ファイル検証中...")
        is_valid = await scraper.validate_downloaded_file(downloaded_file)
        if is_valid:
            print("✅ ファイル検証成功")
        else:
            print("❌ ファイル検証失敗")
            
        # ファイル内容の確認
        print("4. ファイル内容確認...")
        import pandas as pd
        df = pd.read_csv(downloaded_file, nrows=5)
        print(f"取得データサンプル:")
        print(df.head())
        print(f"列名: {list(df.columns)}")
        
    except Exception as e:
        print(f"❌ テストエラー: {e}")
        
    finally:
        # クリーンアップ
        print("5. クリーンアップ中...")
        await scraper.cleanup_browser()
        print("✅ テスト完了")

if __name__ == "__main__":
    asyncio.run(test_scraper())