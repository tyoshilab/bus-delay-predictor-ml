#!/usr/bin/env python3
"""
GTFS Static Load Job のテスト例

このスクリプトはGTFS Static Load Jobの動作をテストするためのサンプルです。
"""

import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from batch.jobs.gtfs_static_load import GTFSStaticLoadJob
from batch.config.settings import get_translink_api_key
import logging

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def test_api_key_check():
    """APIキーの確認テスト"""
    print("=" * 60)
    print("TEST 1: APIキーの確認")
    print("=" * 60)

    try:
        api_key = get_translink_api_key()
        print(f"✓ APIキーが設定されています: {api_key[:8]}...")
        return True
    except ValueError as e:
        print(f"✗ APIキーが設定されていません: {e}")
        print("\n解決方法:")
        print("  export TRANSLINK_API_KEY=your_api_key_here")
        print("  または .env ファイルに設定してください")
        return False


def test_job_initialization():
    """ジョブの初期化テスト"""
    print("=" * 60)
    print("TEST 2: ジョブの初期化")
    print("=" * 60)

    try:
        job = GTFSStaticLoadJob()
        print(f"✓ ジョブが正常に初期化されました")
        print(f"  - API URL: {job.download_url}")
        print(f"  - Schema: {job.schema}")
        return True
    except ValueError as e:
        print(f"✗ ジョブの初期化に失敗: {e}")
        return False
    except Exception as e:
        print(f"✗ 予期しないエラー: {e}")
        return False


def test_dry_run_download():
    """ドライランでのダウンロードテスト"""
    print("=" * 60)
    print("TEST 3: ドライラン（ダウンロードのみ、DB保存なし）")
    print("=" * 60)

    try:
        job = GTFSStaticLoadJob()
        print("ダウンロードを開始します（dry-runモード）...")
        results = job.run(download=True, dry_run=True)

        if results['success']:
            print(f"✓ ドライランが成功しました")
            print(f"  - ダウンロードしたファイル数: {len(list(job.gtfs_dir.glob('*.txt')))}")
            print(f"  - 保存場所: {job.gtfs_dir}")
            return True
        else:
            print(f"✗ ドライランが失敗しました")
            return False

    except Exception as e:
        print(f"✗ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_load_from_directory():
    """既存ディレクトリからの読み込みテスト"""
    print("=" * 60)
    print("TEST 4: 既存ディレクトリからの読み込み（APIキー不要）")
    print("=" * 60)

    # まずテスト用のディレクトリを探す
    from batch.config.settings import GTFS_STATIC_STORAGE_DIR

    # 最新のダウンロードディレクトリを探す
    download_dirs = sorted(GTFS_STATIC_STORAGE_DIR.glob('download_*'))

    if not download_dirs:
        print("✗ テスト用のダウンロードディレクトリが見つかりません")
        print("  まずTEST 3を実行してダウンロードしてください")
        return False

    test_dir = download_dirs[-1]
    print(f"テストディレクトリ: {test_dir}")

    try:
        job = GTFSStaticLoadJob(gtfs_dir=test_dir)
        print("既存ディレクトリからの読み込みをテストします（dry-runモード）...")
        results = job.run(download=False, dry_run=True)

        if results['success']:
            print(f"✓ 既存ディレクトリからの読み込みが成功しました")
            return True
        else:
            print(f"✗ 読み込みが失敗しました")
            return False

    except Exception as e:
        print(f"✗ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メインテスト実行"""
    print("=" * 60)
    print("GTFS Static Load Job テストスイート")
    print("=" * 60)

    results = {}

    # TEST 1: APIキーの確認
    results['api_key'] = test_api_key_check()

    if not results['api_key']:
        print("=" * 60)
        print("APIキーが設定されていないため、残りのテストをスキップします")
        print("=" * 60)
        return

    # TEST 2: ジョブの初期化
    results['initialization'] = test_job_initialization()

    if not results['initialization']:
        print("\n初期化に失敗したため、残りのテストをスキップします")
        return

    # TEST 3: ドライランダウンロード
    print("\nTEST 3を実行しますか？（ダウンロードが発生します）")
    response = input("実行する場合は 'y' を入力: ").strip().lower()

    if response == 'y':
        results['dry_run'] = test_dry_run_download()
    else:
        print("TEST 3をスキップしました")
        results['dry_run'] = None

    # TEST 4: 既存ディレクトリからの読み込み
    if results.get('dry_run'):
        print("\nTEST 4を実行しますか？（既存ディレクトリからの読み込み）")
        response = input("実行する場合は 'y' を入力: ").strip().lower()

        if response == 'y':
            results['load_from_dir'] = test_load_from_directory()
        else:
            print("TEST 4をスキップしました")
            results['load_from_dir'] = None

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


if __name__ == '__main__':
    main()
