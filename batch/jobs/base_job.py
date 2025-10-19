#!/usr/bin/env python3
"""
Base Job Class

全てのバッチジョブの基底クラス
共通の機能とインターフェースを提供
"""

import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class BaseJob(ABC):
    """バッチジョブの基底クラス"""

    def __init__(self, job_name: Optional[str] = None):
        """
        初期化

        Args:
            job_name: ジョブ名（Noneの場合はクラス名を使用）
        """
        self.job_name = job_name or self.__class__.__name__
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.logger = logging.getLogger(self.job_name)

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        ジョブの実際の処理を実装（サブクラスで必ず実装）

        Args:
            **kwargs: ジョブ固有のパラメータ

        Returns:
            実行結果のサマリ
        """
        pass

    def run(self, dry_run: bool = False, **kwargs) -> Dict[str, Any]:
        """
        ジョブを実行（共通処理）

        Args:
            dry_run: Trueの場合、DBに保存せず処理のみ実行
            **kwargs: ジョブ固有のパラメータ

        Returns:
            実行結果のサマリ
        """
        self.start_time = time.time()
        self.logger.info("=" * 80)
        self.logger.info(f"Starting {self.job_name}")
        self.logger.info(f"Dry run mode: {dry_run}")
        self.logger.info(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info("=" * 80)

        results = {
            'job_name': self.job_name,
            'dry_run': dry_run,
            'success': False,
            'start_time': self.start_time,
            'end_time': None,
            'duration_seconds': None,
            'error': None
        }

        try:
            # サブクラスで実装された処理を実行
            execution_results = self.execute(dry_run=dry_run, **kwargs)
            results.update(execution_results)
            results['success'] = True

        except KeyboardInterrupt:
            self.logger.warning("\n⚠️  Job interrupted by user")
            results['error'] = "Interrupted by user"
            results['success'] = False

        except Exception as e:
            self.logger.error(f"\n❌ Job failed: {e}", exc_info=True)
            results['error'] = str(e)
            results['success'] = False
            raise

        finally:
            self.end_time = time.time()
            results['end_time'] = self.end_time
            results['duration_seconds'] = self.end_time - self.start_time

            self._print_summary(results)

        return results

    def _print_summary(self, results: Dict[str, Any]):
        """実行サマリを表示"""
        self.logger.info("=" * 80)
        self.logger.info(f"{self.job_name} Completed!")
        self.logger.info("=" * 80)

        duration = results.get('duration_seconds', 0)
        self.logger.info(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.logger.info(f"Duration: {duration:.2f}s")
        self.logger.info(f"Success: {results['success']}")

        if results.get('error'):
            self.logger.error(f"Error: {results['error']}")

        # ジョブ固有のサマリを表示
        self._print_job_specific_summary(results)

    def _print_job_specific_summary(self, results: Dict[str, Any]):
        """
        ジョブ固有のサマリ表示（オーバーライド可能）

        Args:
            results: 実行結果
        """
        pass

    def validate_prerequisites(self) -> bool:
        """
        ジョブ実行前の前提条件チェック（オーバーライド可能）

        Returns:
            検証結果（True=正常、False=問題あり）
        """
        return True


class DataProcessingJob(BaseJob):
    """データ処理ジョブの基底クラス"""

    def __init__(self, job_name: Optional[str] = None):
        super().__init__(job_name)
        self.processed_count = 0
        self.failed_count = 0
        self.skipped_count = 0

    def _print_job_specific_summary(self, results: Dict[str, Any]):
        """データ処理ジョブのサマリ表示"""
        summary = results.get('summary', {})

        self.logger.info("\nProcessing Summary:")
        self.logger.info(f"  Processed: {summary.get('processed_count', 0)}")
        self.logger.info(f"  Failed: {summary.get('failed_count', 0)}")
        self.logger.info(f"  Skipped: {summary.get('skipped_count', 0)}")


class DatabaseJob(BaseJob):
    """データベース操作ジョブの基底クラス"""

    def __init__(self, job_name: Optional[str] = None):
        super().__init__(job_name)
        self.inserted_records = 0
        self.updated_records = 0
        self.deleted_records = 0

    def _print_job_specific_summary(self, results: Dict[str, Any]):
        """データベースジョブのサマリ表示"""
        summary = results.get('summary', {})

        self.logger.info("\nDatabase Operations:")
        self.logger.info(f"  Inserted: {summary.get('inserted_records', 0)}")
        self.logger.info(f"  Updated: {summary.get('updated_records', 0)}")
        self.logger.info(f"  Deleted: {summary.get('deleted_records', 0)}")


class ScraperJob(DataProcessingJob):
    """スクレイピングジョブの基底クラス"""

    def __init__(self, job_name: Optional[str] = None, download_dir: Optional[Path] = None):
        super().__init__(job_name)
        self.download_dir = download_dir
        self.downloaded_files = []

    def cleanup_old_files(self, days_to_keep: int = 7):
        """
        古いファイルをクリーンアップ（共通処理）

        Args:
            days_to_keep: 保持日数
        """
        if not self.download_dir or not self.download_dir.exists():
            return

        try:
            from datetime import timedelta
            cutoff_time = datetime.now() - timedelta(days=days_to_keep)
            deleted_count = 0

            for file_path in self.download_dir.glob('*'):
                if file_path.is_file() and file_path.stat().st_mtime < cutoff_time.timestamp():
                    file_path.unlink()
                    deleted_count += 1

            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old files")

        except Exception as e:
            self.logger.error(f"File cleanup error: {e}")
