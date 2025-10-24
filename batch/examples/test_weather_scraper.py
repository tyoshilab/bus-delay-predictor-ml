#!/usr/bin/env python3
"""
Weather Scraper Job のテスト例

このスクリプトはWeather Scraper Jobの動作をテストするためのサンプルです。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from batch.jobs.weather_scraper import WeatherScraperJob
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_job_initialization():
    """ジョブの初期化テスト"""
    print("=" * 60)
    print("TEST 1: ジョブの初期化")
    print("=" * 60)

    try:
        job = WeatherScraperJob()
        print(f"✓ ジョブが正常に初期化されました")
        print(f"  - URL: {job.base_url}")
        print(f"  - Download dir: {job.download_dir}")
        print(f"  - Auto calculate rows: {job.auto_calculate_rows}")
        return True
    except Exception as e:
        print(f"✗ ジョブの初期化に失敗: {e}")
        return False


def test_row_calculation():
    """行数計算のテスト"""
    print("=" * 60)
    print("TEST 2: 必要行数の自動計算")
    print("=" * 60)

    try:
        job = WeatherScraperJob()
        required_rows = job.calculate_required_rows()
        print(f"✓ 行数計算が成功しました: {required_rows} rows")
        return True
    except Exception as e:
        print(f"✗ 行数計算に失敗: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_dry_run():
    """ドライランテスト"""
    print("=" * 60)
    print("TEST 3: ドライラン（スクレイピングのみ、DB保存なし）")
    print("=" * 60)

    print("\nこのテストは実際にWebサイトをスクレイピングします。")
    print("Playwrightがインストールされていない場合は失敗します。")
    response = input("実行しますか？ (y/N): ").strip().lower()

    if response != 'y':
        print("テストをスキップしました")
        return None

    try:
        job = WeatherScraperJob(row_limit=5)  # 少量のデータで試す
        print("スクレイピングを開始します...")
        results = job.run(load_to_db=False, dry_run=True)

        if results.get('success'):
            print(f"✓ ドライランが成功しました")
            print(f"  - Downloaded file: {results.get('downloaded_file')}")
            print(f"  - Calculated rows: {results.get('calculated_rows')}")
            return True
        else:
            print(f"✗ ドライランが失敗しました")
            return False

    except Exception as e:
        print(f"✗ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メインテスト実行"""
    print("=" * 60)
    print("Weather Scraper Job テストスイート")
    print("=" * 60)

    results = {}

    # TEST 1: ジョブの初期化
    results['initialization'] = test_job_initialization()

    if not results['initialization']:
        print("\n初期化に失敗したため、残りのテストをスキップします")
        return

    # TEST 2: 行数計算
    results['row_calculation'] = test_row_calculation()

    # TEST 3: ドライラン（オプション）
    results['dry_run'] = test_dry_run()

    # 結果サマリ
    print("=" * 60)
    print("テスト結果サマリ")
    print("=" * 60)

    for test_name, result in results.items():
        if result is True:
            status = "✓ PASSED"
        elif result is False:
            status = "✗ FAILED"
        else:
            status = "- SKIPPED"

        print(f"{test_name:20s}: {status}")

    print("=" * 60)

    # 使用方法の説明
    print("=" * 60)
    print("使用方法")
    print("=" * 60)
    print("""
# 基本実行（行数自動計算、DB保存あり）
python batch/run.py scrape-weather

# 行数を指定して実行
python batch/run.py scrape-weather --row-limit 24

# ドライラン（DB保存なし）
python batch/run.py scrape-weather --dry-run

# DB保存をスキップ
python batch/run.py scrape-weather --no-db

# ダウンロードディレクトリを指定
python batch/run.py scrape-weather --download-dir /custom/path
    """)


if __name__ == '__main__':
    main()
