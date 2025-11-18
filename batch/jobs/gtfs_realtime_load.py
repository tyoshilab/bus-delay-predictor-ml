#!/usr/bin/env python3
"""
GTFS Realtime Data Fetch Job

TransLink APIからGTFS Realtimeデータを取得し、
データベースに保存します。
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from batch.controller.fetch_gtfs_realtime import GTFSRealtimeFetcher
from batch.controller.load_gtfs_realtime import GTFSRealtimeLoader

from batch.config.settings import config
from batch.jobs.base_job import DatabaseJob
from batch.utils.file_utils import cleanup_old_files
from batch.utils.error_handler import APIError, DatabaseError
from batch.utils.mv_utils import refresh_materialized_views, log_refresh_statistics, refresh_alert_feature_views

logger = logging.getLogger(__name__)


class GTFSRealtimeFetchJob(DatabaseJob):
    """GTFS Realtimeデータ取得ジョブ"""

    # 利用可能なフィード
    AVAILABLE_FEEDS = ['trip_updates', 'vehicle_positions', 'alerts']

    def __init__(
        self,
        api_key: Optional[str] = None,
        save_to_disk: bool = True,
        cleanup_old_files_flag: bool = True,
        days_to_keep: Optional[int] = None,
        refresh_mv: bool = True
    ):
        """
        初期化

        Args:
            api_key: TransLink APIキー（Noneの場合は設定から取得）
            save_to_disk: ディスクに保存するか
            cleanup_old_files_flag: 古いファイルをクリーンアップするか
            days_to_keep: ファイル保持日数（Noneの場合は設定から取得）
            refresh_mv: マテリアライズドビューをリフレッシュするか
        """
        # 基底クラスの初期化
        super().__init__(job_name="GTFSRealtimeFetchJob")

        # APIキーの取得
        try:
            self.api_key = api_key or config.translink_api.get_api_key()
        except ValueError as e:
            raise APIError(
                "API key is required for fetching GTFS Realtime data. "
                "Please set TRANSLINK_API_KEY environment variable."
            ) from e

        self.save_to_disk = save_to_disk
        self.cleanup_old_files_flag = cleanup_old_files_flag
        self.days_to_keep = days_to_keep if days_to_keep is not None else config.gtfs_realtime.cleanup_days
        self.refresh_mv = refresh_mv

        # Fetcherとloader初期化
        self.fetcher = GTFSRealtimeFetcher(api_key=self.api_key)
        self.fetcher.storage_dir = config.directories.gtfs_rt_storage_dir
        self.loader = GTFSRealtimeLoader()

        self.logger.info("GTFSRealtimeFetchJob initialized")
        self.logger.info(f"  - API key: {self.api_key[:8]}..." if len(self.api_key) > 8 else "  - API key configured")
        self.logger.info(f"  - Storage dir: {config.directories.gtfs_rt_storage_dir}")
        self.logger.info(f"  - Save to disk: {self.save_to_disk}")
        self.logger.info(f"  - Refresh MV: {self.refresh_mv}")

    def fetch_feeds(
        self,
        feeds: Optional[List[str]] = None,
        validate: bool = True
    ) -> Dict[str, Tuple[Optional[bytes], Optional[Path]]]:
        """
        フィードを取得

        Args:
            feeds: 取得するフィードのリスト（Noneの場合は全フィード）
            validate: Protobufバリデーションを実行するか

        Returns:
            フィード名 -> (データ, ファイルパス)のマッピング
        """
        if feeds is None:
            feeds = self.AVAILABLE_FEEDS

        self.logger.info(f"Fetching {len(feeds)} feeds: {', '.join(feeds)}")

        # 一時的にフィードを制限
        original_feeds = self.fetcher.feeds.copy()
        if set(feeds) != set(self.AVAILABLE_FEEDS):
            self.fetcher.feeds = {k: v for k, v in original_feeds.items() if k in feeds}

        try:
            results = self.fetcher.fetch_all_feeds(
                save_to_disk=self.save_to_disk,
                validate=validate
            )
            return results
        finally:
            # フィード設定を復元
            self.fetcher.feeds = original_feeds

    def load_to_database(
        self,
        fetch_results: Dict[str, Tuple[Optional[bytes], Optional[Path]]]
    ) -> Dict[str, Optional[int]]:
        """
        取得したデータをデータベースに保存

        Args:
            fetch_results: fetch_feeds()の結果

        Returns:
            フィード名 -> feed_message_idのマッピング
        """
        load_results = {}

        self.logger.info("Connecting to database...")
        self.loader.connect_db()

        try:
            for feed_type, (data, filepath) in fetch_results.items():
                if data is None:
                    self.logger.warning(f"Skipping {feed_type} - no data fetched")
                    load_results[feed_type] = None
                    continue

                self.logger.info(f"Loading {feed_type} to database...")

                try:
                    # データから直接ロード
                    feed_msg_id = self.loader.load_feed_data(data, feed_type)

                    if feed_msg_id:
                        self.logger.info(
                            f"✓ Successfully loaded {feed_type} "
                            f"(feed_msg_id: {feed_msg_id})"
                        )
                        load_results[feed_type] = feed_msg_id
                    else:
                        self.logger.error(f"✗ Failed to load {feed_type}")
                        load_results[feed_type] = None

                except Exception as e:
                    self.logger.error(f"✗ Error loading {feed_type}: {e}", exc_info=True)
                    load_results[feed_type] = None

        finally:
            self.loader.close_db()
            self.logger.info("Database connection closed")

        return load_results

    def cleanup_old_data(self):
        """古いファイルをクリーンアップ"""
        if not self.cleanup_old_files_flag:
            self.logger.info("Cleanup disabled, skipping...")
            return

        self.logger.info(f"Cleaning up files older than {self.days_to_keep} days...")
        try:
            # 共通ユーティリティを使用
            cleanup_old_files(
                config.directories.gtfs_rt_storage_dir,
                pattern='*.pb',
                days_to_keep=self.days_to_keep,
                recursive=True
            )
            self.logger.info("Cleanup completed")
        except Exception as e:
            self.logger.error(f"Cleanup failed: {e}", exc_info=True)

    def execute(
        self,
        feeds: Optional[List[str]] = None,
        dry_run: bool = False,
        **kwargs
    ) -> Dict[str, Any]:
        """
        ジョブの実際の処理を実装

        Args:
            feeds: 処理するフィードのリスト（Noneの場合は全フィード）
            dry_run: Trueの場合、DBに保存せず取得のみ実行
            **kwargs: その他のパラメータ

        Returns:
            実行結果のサマリ
        """
        # フィードリスト取得
        if feeds is None:
            feeds = self.AVAILABLE_FEEDS

        self.logger.info(f"Processing feeds: {', '.join(feeds)}")

        # 結果格納
        results = {
            'fetch_results': {},
            'load_results': {},
            'summary': {
                'total_feeds': len(feeds),
                'successful_fetches': 0,
                'successful_loads': 0,
                'failed_fetches': 0,
                'failed_loads': 0,
                'inserted_records': 0,
                'updated_records': 0,
                'deleted_records': 0
            }
        }

        # ステップ1: フィード取得
        self.logger.info("=" * 60)
        self.logger.info("STEP 1: FETCHING REALTIME DATA")
        self.logger.info("=" * 60)

        fetch_results = self.fetch_feeds(feeds=feeds, validate=True)
        results['fetch_results'] = fetch_results

        # 成功・失敗カウント
        for feed_type, (data, filepath) in fetch_results.items():
            if data is not None:
                results['summary']['successful_fetches'] += 1
            else:
                results['summary']['failed_fetches'] += 1

        # ステップ2: データベース保存（dry_runでない場合）
        if not dry_run and results['summary']['successful_fetches'] > 0:
            self.logger.info("=" * 60)
            self.logger.info("STEP 2: LOADING TO DATABASE")
            self.logger.info("=" * 60)

            load_results = self.load_to_database(fetch_results)
            results['load_results'] = load_results

            # 成功・失敗カウント
            for feed_type, feed_msg_id in load_results.items():
                if feed_msg_id is not None:
                    results['summary']['successful_loads'] += 1
                else:
                    results['summary']['failed_loads'] += 1
        else:
            if dry_run:
                self.logger.info("\n[DRY RUN] Skipping database load")
            results['load_results'] = {feed: None for feed in feeds}

        # ステップ3: マテリアライズドビューのリフレッシュ
        # if self.refresh_mv and not dry_run and results['summary']['successful_loads'] > 0:
        #     self.logger.info("=" * 60)
        #     self.logger.info("STEP 3: REFRESHING MATERIALIZED VIEWS")
        #     self.logger.info("=" * 60)

        #     try:
        #         # データベース接続を取得してMVをリフレッシュ
        #         from batch.config.database_connector import DatabaseConnector
        #         db_connector = DatabaseConnector()

        #         with db_connector.get_connection() as conn:
        #             # 1. 通常のMVをリフレッシュ
        #             refresh_success = refresh_materialized_views(
        #                 conn
        #             )

        #             if refresh_success:
        #                 results['summary']['mv_refreshed'] = True
        #                 # 統計情報をログに出力
        #                 log_refresh_statistics(conn)
        #             else:
        #                 results['summary']['mv_refreshed'] = False
        #                 self.logger.warning("Materialized view refresh failed, but job continues")

        #             # 2. アラート特徴量MVをリフレッシュ
        #             alert_mv_success = refresh_alert_feature_views(conn)
        #             results['summary']['alert_mv_refreshed'] = alert_mv_success

        #     except Exception as e:
        #         self.logger.error(f"Error refreshing materialized views: {e}", exc_info=True)
        #         results['summary']['mv_refreshed'] = False
        #         results['summary']['alert_mv_refreshed'] = False
        #         # MVリフレッシュの失敗はジョブ全体の失敗にしない
        #         self.logger.warning("Materialized view refresh failed, but job continues")
        # else:
        #     results['summary']['mv_refreshed'] = False
        #     if dry_run:
        #         self.logger.info("\n[DRY RUN] Skipping materialized view refresh")

        # ステップ4: クリーンアップ
        if self.cleanup_old_files_flag and self.save_to_disk:
            self.logger.info("=" * 60)
            self.logger.info("STEP 4: CLEANING UP OLD FILES")
            self.logger.info("=" * 60)
            self.cleanup_old_data()

        # 挿入レコード数を設定
        results['summary']['inserted_records'] = results['summary']['successful_loads']
        self.inserted_records = results['summary']['successful_loads']

        # 詳細結果をログに追加
        results['detailed_results'] = []
        for feed_type in feeds:
            fetch_data, fetch_path = fetch_results.get(feed_type, (None, None))
            fetch_status = "success" if fetch_data is not None else "failed"

            detail = {
                'feed_type': feed_type,
                'fetch_status': fetch_status
            }

            if not dry_run:
                load_id = results['load_results'].get(feed_type)
                detail['load_status'] = "success" if load_id is not None else "failed"
                detail['feed_message_id'] = load_id

            results['detailed_results'].append(detail)

        return results

    def _print_job_specific_summary(self, results: Dict[str, Any]):
        """ジョブ固有のサマリ表示"""
        summary = results.get('summary', {})

        self.logger.info(f"Feeds processed: {summary.get('total_feeds', 0)}")
        self.logger.info(f"Successful fetches: {summary.get('successful_fetches', 0)}")
        self.logger.info(f"Failed fetches: {summary.get('failed_fetches', 0)}")
        self.logger.info(f"Successful loads: {summary.get('successful_loads', 0)}")
        self.logger.info(f"Failed loads: {summary.get('failed_loads', 0)}")

        # MVリフレッシュ結果
        mv_refreshed = summary.get('mv_refreshed', False)
        mv_status = "✓ Yes" if mv_refreshed else "✗ No"
        self.logger.info(f"Materialized view refreshed: {mv_status}")

        # 詳細結果
        if 'detailed_results' in results:
            self.logger.info("\nDetailed Results:")
            for detail in results['detailed_results']:
                feed_type = detail['feed_type']
                fetch_status = "✓" if detail['fetch_status'] == 'success' else "✗"

                if 'load_status' in detail:
                    load_status = "✓" if detail['load_status'] == 'success' else "✗"
                    feed_id = detail.get('feed_message_id', 'N/A')
                    self.logger.info(
                        f"  {feed_type}: Fetch={fetch_status}, "
                        f"Load={load_status} (ID: {feed_id})"
                    )
                else:
                    self.logger.info(f"  {feed_type}: Fetch={fetch_status}")
