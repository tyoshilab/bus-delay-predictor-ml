"""
File Utilities

ファイル操作に関する共通ユーティリティ
"""

import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


def cleanup_old_files(
    directory: Path,
    pattern: str = '*',
    days_to_keep: int = 7,
    recursive: bool = False
) -> int:
    """
    古いファイルをクリーンアップ

    Args:
        directory: 対象ディレクトリ
        pattern: ファイルパターン（globパターン）
        days_to_keep: 保持日数
        recursive: サブディレクトリも対象にするか

    Returns:
        削除されたファイル数
    """
    if not directory.exists():
        logger.warning(f"Directory does not exist: {directory}")
        return 0

    try:
        cutoff_time = datetime.now() - timedelta(days=days_to_keep)
        deleted_count = 0

        glob_method = directory.rglob if recursive else directory.glob

        for file_path in glob_method(pattern):
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug(f"Deleted old file: {file_path}")

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old files from {directory}")

        return deleted_count

    except Exception as e:
        logger.error(f"File cleanup error in {directory}: {e}")
        return 0


def validate_file(
    file_path: Path,
    min_size_bytes: int = 100,
    max_size_bytes: Optional[int] = None,
    check_exists: bool = True
) -> bool:
    """
    ファイルを検証

    Args:
        file_path: ファイルパス
        min_size_bytes: 最小ファイルサイズ（バイト）
        max_size_bytes: 最大ファイルサイズ（バイト、Noneの場合は無制限）
        check_exists: ファイルの存在チェックを行うか

    Returns:
        検証結果（True=正常、False=問題あり）
    """
    try:
        # 存在チェック
        if check_exists and not file_path.exists():
            logger.error(f"File does not exist: {file_path}")
            return False

        # サイズチェック
        file_size = file_path.stat().st_size

        if file_size < min_size_bytes:
            logger.error(
                f"File size too small: {file_size} bytes "
                f"(minimum: {min_size_bytes} bytes) - {file_path}"
            )
            return False

        if max_size_bytes and file_size > max_size_bytes:
            logger.error(
                f"File size too large: {file_size} bytes "
                f"(maximum: {max_size_bytes} bytes) - {file_path}"
            )
            return False

        logger.debug(f"File validation passed: {file_path} ({file_size} bytes)")
        return True

    except Exception as e:
        logger.error(f"File validation error for {file_path}: {e}")
        return False


def ensure_directory(directory: Path, create: bool = True) -> bool:
    """
    ディレクトリの存在を確認し、必要に応じて作成

    Args:
        directory: ディレクトリパス
        create: 存在しない場合に作成するか

    Returns:
        ディレクトリが使用可能かどうか
    """
    try:
        if directory.exists():
            if not directory.is_dir():
                logger.error(f"Path exists but is not a directory: {directory}")
                return False
            return True

        if create:
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created directory: {directory}")
            return True

        logger.error(f"Directory does not exist: {directory}")
        return False

    except Exception as e:
        logger.error(f"Error ensuring directory {directory}: {e}")
        return False
