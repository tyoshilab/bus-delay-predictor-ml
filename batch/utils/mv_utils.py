#!/usr/bin/env python3
"""
Materialized View Utilities

マテリアライズドビューのリフレッシュ用ユーティリティ
"""

import logging
from typing import Optional, Literal

logger = logging.getLogger(__name__)


def refresh_materialized_views(
    connection,
    view_type: Literal['all', 'base', 'enriched', 'analytics'] = 'base',
    concurrent: bool = False  # Changed from True to False to save memory
) -> bool:
    """
    マテリアライズドビューをリフレッシュ
    
    Args:
        connection: psycopg2 connection object
        view_type: リフレッシュするビューのタイプ
            - 'all': すべてのビュー（段階的にリフレッシュ）
            - 'base': ベースビューのみ（GTFS Realtime用、高速）
            - 'enriched': enrichedビューまで
            - 'analytics': analyticsビューまで
        concurrent: CONCURRENTLYオプションを使用するか（ベースビューのみ）
    
    Returns:
        成功したかどうか
    """
    try:
        with connection.cursor() as cur:
            if view_type == 'base' and concurrent:
                # ベースビューのみを並列リフレッシュ（ブロックなし、高速）
                logger.info("Refreshing base materialized view (CONCURRENTLY)...")
                cur.execute("CALL gtfs_realtime.refresh_gtfs_views_base_concurrent();")
                logger.info("✓ Base view refreshed successfully (non-blocking)")
            else:
                # 段階的リフレッシュ（ステージングテーブル使用）
                logger.info(f"Refreshing materialized views (type: {view_type})...")
                cur.execute(f"CALL gtfs_realtime.refresh_gtfs_views_staged('{view_type}');")
                logger.info(f"✓ Views refreshed successfully (type: {view_type})")
            
            connection.commit()
            return True
            
    except Exception as e:
        logger.error(f"✗ Failed to refresh materialized views: {e}", exc_info=True)
        connection.rollback()
        return False


def get_refresh_status(connection) -> Optional[dict]:
    """
    マテリアライズドビューのリフレッシュ状態を取得
    
    Args:
        connection: psycopg2 connection object
    
    Returns:
        リフレッシュ状態の辞書（失敗時はNone）
    """
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT * FROM gtfs_realtime.get_refresh_status();")
            columns = [desc[0] for desc in cur.description]
            results = cur.fetchall()
            
            status = []
            for row in results:
                status.append(dict(zip(columns, row)))
            
            return status
            
    except Exception as e:
        logger.error(f"Failed to get refresh status: {e}", exc_info=True)
        return None


def log_refresh_statistics(connection):
    """
    マテリアライズドビューの統計情報をログに出力
    
    Args:
        connection: psycopg2 connection object
    """
    try:
        with connection.cursor() as cur:
            # 統計情報取得
            cur.execute("SELECT * FROM gtfs_realtime.mv_statistics;")
            columns = [desc[0] for desc in cur.description]
            results = cur.fetchall()
            
            logger.info("Materialized View Statistics:")
            logger.info("-" * 80)
            for row in results:
                stats = dict(zip(columns, row))
                logger.info(
                    f"  {stats.get('view_name', 'N/A')}: "
                    f"{stats.get('row_count', 0):,} rows, "
                    f"size: {stats.get('total_size', 'N/A')}"
                )
            logger.info("-" * 80)
            
    except Exception as e:
        logger.warning(f"Could not retrieve MV statistics: {e}")
