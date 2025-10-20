#!/usr/bin/env python3
"""
Batch Job Runner

GTFSバッチジョブの統一エントリーポイント

Usage:
    # 地域遅延予測を実行
    python batch/run.py predict

    # GTFS Realtimeデータを取得
    python batch/run.py load-realtime

    # dry-runモード
    python batch/run.py predict --dry-run
    python batch/run.py load-realtime --dry-run

    # 詳細ログ
    python batch/run.py predict --verbose
"""

import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Lazy imports - only import job modules when needed to avoid dependency issues
from batch.config.settings import config


def setup_logging(verbose: bool = False, job_name: str = "batch"):
    """ロギングを設定"""
    level = logging.DEBUG if verbose else config.logging.get_level()

    # ログファイル名
    log_file = config.directories.log_dir / f"{job_name}_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=level,
        format=config.logging.format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file)
        ]
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized (level={logging.getLevelName(level)})")
    logger.info(f"Log file: {log_file}")

    return logger


def run_prediction_job(args):
    """地域遅延予測ジョブを実行"""
    logger = setup_logging(args.verbose, "regional_prediction")

    try:
        from batch.jobs.regional_delay_prediction import RegionalDelayPredictionJob

        job = RegionalDelayPredictionJob(
            model_path=args.model_path if hasattr(args, 'model_path') else None
        )

        results = job.execute(
            regions=args.regions if hasattr(args, 'regions') else None,
            dry_run=args.dry_run
        )

        # 成功判定
        if results.get('status') == 'success' and results.get('total_predictions', 0) > 0:
            logger.info(f"\n✅ Regional delay prediction completed successfully!")
            logger.info(f"  Total predictions: {results['total_predictions']}")
            logger.info(f"  Total regions: {results['total_regions']}")
            logger.info(f"  Execution time: {results['execution_time_seconds']:.2f}s")
            return 0
        elif results.get('status') == 'success':
            logger.warning("\n⚠️  No predictions generated")
            return 1
        else:
            logger.error("\n❌ Job failed")
            return 1

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Job interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"\n❌ Job failed: {e}", exc_info=True)
        return 1


def run_fetch_job(args):
    """GTFS Realtimeフェッチジョブを実行"""
    logger = setup_logging(args.verbose, "gtfs_fetch")

    try:
        from batch.jobs.gtfs_realtime_load import GTFSRealtimeFetchJob

        job = GTFSRealtimeFetchJob(
            api_key=args.api_key if hasattr(args, 'api_key') else None,
            save_to_disk=not args.no_save_disk if hasattr(args, 'no_save_disk') else True,
            cleanup_old_files_flag=not args.no_cleanup if hasattr(args, 'no_cleanup') else True,
            days_to_keep=args.days_to_keep if hasattr(args, 'days_to_keep') else 7,
            refresh_mv=not args.no_refresh_mv if hasattr(args, 'no_refresh_mv') else True
        )

        results = job.run(
            feeds=args.feeds if hasattr(args, 'feeds') else None,
            dry_run=args.dry_run
        )

        # 成功判定
        if results['summary']['failed_fetches'] == 0:
            logger.info("\n✅ GTFS fetch completed successfully!")
            return 0
        else:
            logger.warning(
                f"\n⚠️  GTFS fetch completed with {results['summary']['failed_fetches']} failures"
            )
            return 1

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Job interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"\n❌ Job failed: {e}", exc_info=True)
        return 1


def run_static_load_job(args):
    """GTFS Static読み込みジョブを実行"""
    logger = setup_logging(args.verbose, "gtfs_static_load")

    try:
        from batch.jobs.gtfs_static_load import GTFSStaticLoadJob

        job = GTFSStaticLoadJob(
            gtfs_dir=Path(args.gtfs_dir) if hasattr(args, 'gtfs_dir') and args.gtfs_dir else None
        )

        results = job.run(
            download=args.download if hasattr(args, 'download') else True,
            dry_run=args.dry_run
        )

        # 成功判定
        if results['summary']['failed_loads'] == 0:
            logger.info("\n✅ GTFS static load completed successfully!")
            return 0
        else:
            logger.warning(
                f"\n⚠️  GTFS static load completed with {results['summary']['failed_loads']} failures"
            )
            return 1

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Job interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"\n❌ Job failed: {e}", exc_info=True)
        return 1


def run_weather_scraper_job(args):
    """気象データスクレイピングジョブを実行"""
    logger = setup_logging(args.verbose, "weather_scraper")

    try:
        from batch.jobs.weather_scraper import WeatherScraperJob

        job = WeatherScraperJob(
            download_dir=Path(args.download_dir) if hasattr(args, 'download_dir') and args.download_dir else None,
            row_limit=args.row_limit if hasattr(args, 'row_limit') else None
        )

        results = job.run(
            load_to_db=not args.no_db if hasattr(args, 'no_db') else True,
            dry_run=args.dry_run
        )

        # 成功判定
        if results.get('success', False):
            logger.info("\n✅ Weather scraper completed successfully!")
            logger.info(f"  Inserted records: {results.get('inserted_records', 0)}")
            return 0
        else:
            logger.warning("\n⚠️  Weather scraper completed with errors")
            return 1

    except KeyboardInterrupt:
        logger.warning("\n⚠️  Job interrupted by user")
        return 1

    except Exception as e:
        logger.error(f"\n❌ Job failed: {e}", exc_info=True)
        return 1


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description='GTFS Batch Job Runner',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest='command', help='Job to run')

    # ===== 地域遅延予測ジョブ =====
    predict_parser = subparsers.add_parser(
        'predict',
        help='Run regional delay prediction job'
    )
    predict_parser.add_argument(
        '--model-path',
        type=str,
        help='Path to trained model (default: from config)'
    )
    predict_parser.add_argument(
        '--regions',
        nargs='+',
        help='Specific regions to predict (default: all regions)'
    )
    predict_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Run without saving to database'
    )
    predict_parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    # ===== GTFS Realtimeフェッチジョブ =====
    fetch_parser = subparsers.add_parser(
        'load-realtime',
        help='Run GTFS realtime fetch job'
    )
    fetch_parser.add_argument(
        '--api-key',
        type=str,
        help='TransLink API key (default: from config)'
    )
    fetch_parser.add_argument(
        '--feeds',
        nargs='+',
        choices=['trip_updates', 'vehicle_positions', 'alerts'],
        help='Specific feeds to fetch (default: all)'
    )
    fetch_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Fetch without loading to database'
    )
    fetch_parser.add_argument(
        '--no-save-disk',
        action='store_true',
        help='Do not save protobuf files to disk'
    )
    fetch_parser.add_argument(
        '--no-cleanup',
        action='store_true',
        help='Do not cleanup old files'
    )
    fetch_parser.add_argument(
        '--days-to-keep',
        type=int,
        default=7,
        help='Number of days to keep old files (default: 7)'
    )
    fetch_parser.add_argument(
        '--no-refresh-mv',
        action='store_true',
        help='Do not refresh materialized views after loading'
    )
    fetch_parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    # ===== GTFS Static読み込みジョブ =====
    static_parser = subparsers.add_parser(
        'load-static',
        help='Run GTFS static data load job'
    )
    static_parser.add_argument(
        '--gtfs-dir',
        type=str,
        help='Directory containing GTFS CSV files (if not downloading)'
    )
    static_parser.add_argument(
        '--api-key',
        type=str,
        help='TransLink API key (for download)'
    )
    static_parser.add_argument(
        '--download-url',
        type=str,
        help='Custom download URL (default: TransLink API)'
    )
    static_parser.add_argument(
        '--no-download',
        dest='download',
        action='store_false',
        help='Use existing directory instead of downloading'
    )
    static_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Download/process without loading to database'
    )
    static_parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    # ===== 気象データスクレイピングジョブ =====
    weather_parser = subparsers.add_parser(
        'scrape-weather',
        help='Run weather data scraping job'
    )
    weather_parser.add_argument(
        '--download-dir',
        type=str,
        help='Download directory for CSV files (default: batch/downloads)'
    )
    weather_parser.add_argument(
        '--row-limit',
        type=int,
        default=None,
        help='Number of rows to fetch (default: unlimited, fetches all available data)'
    )
    weather_parser.add_argument(
        '--no-db',
        action='store_true',
        help='Skip database load'
    )
    weather_parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Scrape without loading to database'
    )
    weather_parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    args = parser.parse_args()

    # コマンドが指定されていない場合
    if not args.command:
        parser.print_help()
        sys.exit(1)

    # ログディレクトリ作成
    config.directories.log_dir.mkdir(parents=True, exist_ok=True)

    # ジョブ実行
    if args.command == 'predict':
        sys.exit(run_prediction_job(args))
    elif args.command == 'load-realtime':
        sys.exit(run_fetch_job(args))
    elif args.command == 'load-static':
        sys.exit(run_static_load_job(args))
    elif args.command == 'scrape-weather':
        sys.exit(run_weather_scraper_job(args))
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
