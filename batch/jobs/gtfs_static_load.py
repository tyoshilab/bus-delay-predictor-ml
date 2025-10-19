#!/usr/bin/env python3
"""
GTFS Static Data Load Job

GTFS Static CSVファイルをダウンロードし、PostgreSQLデータベースに読み込みます。
"""

import sys
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import time
import pandas as pd
import requests
import zipfile
import io

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import from GTFS-api (hyphenated folder name)
from batch.config.database_connector import DatabaseConnector
from batch.config.settings import config
from batch.jobs.base_job import DatabaseJob
from batch.utils import insert_with_conflict_handling
from batch.utils.error_handler import APIError, DataProcessingError

logger = logging.getLogger(__name__)


class GTFSStaticLoadJob(DatabaseJob):
    """GTFS Staticデータ読み込みジョブ"""

    # CSVファイルとテーブルのマッピング
    FILE_TABLE_MAPPING = {
        'agency.txt': 'gtfs_agency',
        'routes.txt': 'gtfs_routes',
        'stops.txt': 'gtfs_stops',
        'calendar.txt': 'gtfs_calendar',
        'calendar_dates.txt': 'gtfs_calendar_dates',
        'directions.txt': 'gtfs_directions',
        'trips.txt': 'gtfs_trips_static',
        'stop_times.txt': 'gtfs_stop_times',
        'shapes.txt': 'gtfs_shapes',
        'feed_info.txt': 'gtfs_feed_info',
        'transfers.txt': 'gtfs_transfers'
    }

    # 読み込み順序（依存関係順）
    LOAD_ORDER = [
        'agency.txt',
        'routes.txt',
        'stops.txt',
        'calendar.txt',
        'calendar_dates.txt',
        'feed_info.txt',
        'shapes.txt',
        'directions.txt',
        'trips.txt',
        'stop_times.txt',
        'transfers.txt'
    ]

    def __init__(
        self,
        gtfs_dir: Optional[Path] = None,
        schema: str = 'gtfs_static'
    ):
        """
        初期化

        Args:
            gtfs_dir: GTFSファイルのディレクトリ（Noneの場合は自動ダウンロード）
            download_url: GTFSファイルのダウンロードURL
            schema: データベーススキーマ名
        """
        super().__init__(job_name="GTFSStaticLoadJob")

        self.gtfs_dir = gtfs_dir

        self.download_url = "https://gtfs-static.translink.ca/gtfs/google_transit.zip"
        self.schema = schema

        # データベース接続
        self.db_connector = DatabaseConnector()
        self.engine = self.db_connector.engine

        self.logger.info("GTFSStaticLoadJob initialized successfully")

    def download_gtfs_static(self, output_dir: Path) -> Path:
        """
        TransLink APIからGTFS Staticファイルをダウンロード

        Args:
            output_dir: 出力ディレクトリ

        Returns:
            解凍されたファイルのディレクトリ

        Raises:
            APIError: ダウンロードに失敗した場合
        """

        self.logger.info("Downloading GTFS Static data from TransLink API...")
        self.logger.info(f"API Endpoint: {self.download_url}")

        try:
            # APIリクエスト（APIキーをクエリパラメータとして付与）
            headers = {
                'User-Agent': 'GTFS-Static-Loader/2.0',
                'Accept': 'application/zip, application/octet-stream'
            }

            self.logger.info(f"Sending GET request with API key parameter...")
            response = requests.get(
                self.download_url,
                headers=headers,
                timeout=300,  # 5分
                allow_redirects=True
            )

            self.logger.info(f"Response status: {response.status_code}")

            if response.status_code != 200:
                error_msg = f"Download failed: HTTP {response.status_code}"
                try:
                    # レスポンスボディを取得（最大500文字）
                    error_detail = response.text[:500]
                    if error_detail:
                        error_msg += f"\nResponse: {error_detail}"
                except:
                    pass

                if response.status_code == 401:
                    error_msg += "\nHint: Check if your TRANSLINK_API_KEY is valid"
                elif response.status_code == 403:
                    error_msg += "\nHint: API key may not have permission to access GTFS Static data"

                raise APIError(error_msg)

            # Content-Typeの確認
            content_type = response.headers.get('Content-Type', '')
            self.logger.info(f"Content-Type: {content_type}")
            self.logger.info(f"Downloaded {len(response.content):,} bytes")

            # ZIPファイルの検証と解凍
            output_dir.mkdir(parents=True, exist_ok=True)

            try:
                with zipfile.ZipFile(io.BytesIO(response.content)) as zip_ref:
                    # ZIPファイル内のファイル一覧を確認
                    zip_files = zip_ref.namelist()
                    self.logger.info(f"ZIP contains {len(zip_files)} files")

                    # 解凍
                    zip_ref.extractall(output_dir)

            except zipfile.BadZipFile as e:
                raise APIError(
                    f"Downloaded file is not a valid ZIP archive. "
                    f"Content-Type: {content_type}, Size: {len(response.content)} bytes"
                ) from e

            self.logger.info(f"Extracted to: {output_dir}")

            # 解凍されたTXTファイル一覧を確認
            txt_files = list(output_dir.glob('*.txt'))
            self.logger.info(f"Found {len(txt_files)} GTFS .txt files")

            if len(txt_files) == 0:
                self.logger.warning("No .txt files found in extracted archive")
                # 全ファイルを表示
                all_files = list(output_dir.glob('*'))
                self.logger.info(f"All extracted files: {[f.name for f in all_files]}")

            return output_dir

        except APIError:
            raise
        except requests.RequestException as e:
            self.logger.error(f"Network error during download: {e}")
            raise APIError(f"Network error: {e}") from e
        except Exception as e:
            self.logger.error(f"Unexpected error during download: {e}")
            raise APIError(f"Download error: {e}") from e


    def preprocess_dataframe(self, df: pd.DataFrame, filename: str) -> pd.DataFrame:
        """ファイルタイプに応じたデータ前処理"""
        # Calendar: 日付フォーマット変換
        if 'calendar' in filename and 'calendar_dates' not in filename:
            if 'start_date' in df.columns:
                df['start_date'] = pd.to_datetime(df['start_date'], format='%Y%m%d')
            if 'end_date' in df.columns:
                df['end_date'] = pd.to_datetime(df['end_date'], format='%Y%m%d')

        # Calendar Dates: 日付フォーマット変換
        if 'calendar_dates' in filename:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')

        # Feed Info: 日付フォーマット変換
        if 'feed_info' in filename:
            if 'feed_start_date' in df.columns:
                df['feed_start_date'] = pd.to_datetime(df['feed_start_date'], format='%Y%m%d')
            if 'feed_end_date' in df.columns:
                df['feed_end_date'] = pd.to_datetime(df['feed_end_date'], format='%Y%m%d')

        # Stop Times: GTFS時刻フォーマット変換（24:00:00以降の処理）
        if 'stop_times' in filename:
            def convert_gtfs_time(time_str):
                if pd.isna(time_str) or time_str == '':
                    return None
                try:
                    parts = time_str.split(':')
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])

                    # 24時間以降は翌日扱い
                    if hours >= 24:
                        hours = hours - 24

                    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                except:
                    return None

            if 'arrival_time' in df.columns:
                df['arrival_time'] = df['arrival_time'].apply(convert_gtfs_time)
            if 'departure_time' in df.columns:
                df['departure_time'] = df['departure_time'].apply(convert_gtfs_time)

        return df

    def load_csv_to_table(self, csv_path: Path, table_name: str) -> int:
        """
        CSVファイルをテーブルに読み込み

        Args:
            csv_path: CSVファイルのパス
            table_name: テーブル名

        Returns:
            挿入されたレコード数

        Raises:
            DataProcessingError: データ処理に失敗した場合
        """
        try:
            if not csv_path.exists():
                self.logger.warning(f"CSV file not found: {csv_path}")
                return 0

            # CSVを読み込み
            df = pd.read_csv(csv_path)
            self.logger.info(f"Loading {len(df)} rows from {csv_path.name} into {table_name}")

            # 前処理
            df = self.preprocess_dataframe(df, csv_path.name)

            # チャンク処理（stop_timesは大きいため）
            chunk_size = 50000 if 'stop_times' in csv_path.name else None
            total_inserted = 0

            if chunk_size and len(df) > chunk_size:
                self.logger.info(f"Loading large file in chunks of {chunk_size} rows...")
                for i in range(0, len(df), chunk_size):
                    chunk = df[i:i+chunk_size]
                    inserted = insert_with_conflict_handling(
                        chunk, table_name, self.engine, self.schema, batch_size=5000
                    )
                    total_inserted += inserted
                    self.logger.info(
                        f"Processed chunk {i//chunk_size + 1}: "
                        f"rows {i+1} to {min(i+chunk_size, len(df))}"
                    )
            else:
                total_inserted = insert_with_conflict_handling(
                    df, table_name, self.engine, self.schema, batch_size=5000
                )

            self.logger.info(
                f"Successfully processed {len(df)} rows for {table_name} "
                f"({total_inserted} new records inserted)"
            )
            self.inserted_records += total_inserted
            return total_inserted

        except Exception as e:
            self.logger.error(f"Error loading {csv_path}: {e}")
            raise DataProcessingError(f"Failed to load {csv_path.name}") from e

    def get_table_summary(self) -> Dict[str, int]:
        """テーブルのサマリを取得"""
        from sqlalchemy import text
        summary = {}
        try:
            with self.engine.connect() as conn:
                for table_name in self.FILE_TABLE_MAPPING.values():
                    result = conn.execute(text(f"SELECT COUNT(*) FROM {self.schema}.{table_name}"))
                    count = result.fetchone()[0]
                    summary[table_name] = count
        except Exception as e:
            self.logger.error(f"Error getting table summary: {e}")

        return summary

    def execute(self, download: bool = True, dry_run: bool = False, **kwargs) -> Dict[str, Any]:
        """
        ジョブの実際の処理を実装

        Args:
            download: TransLink APIからダウンロードするか
            dry_run: Trueの場合、DBに保存せず処理のみ実行
            **kwargs: その他のパラメータ

        Returns:
            実行結果のサマリ
        """
        results = {
            'loaded_tables': {},
            'summary': {
                'total_files': 0,
                'successful_loads': 0,
                'failed_loads': 0,
                'inserted_records': 0,
                'updated_records': 0,
                'deleted_records': 0
            }
        }

        # ステップ1: GTFSファイルの取得
        if download:
            self.logger.info("=" * 60)
            self.logger.info("STEP 1: DOWNLOADING GTFS STATIC DATA")
            self.logger.info("=" * 60)

            temp_dir = config.directories.gtfs_static_storage_dir / f'download_{int(time.time())}'
            self.gtfs_dir = self.download_gtfs_static(temp_dir)
        else:
            if not self.gtfs_dir:
                raise ValueError("gtfs_dir must be specified when download=False")
            self.logger.info(f"Using existing GTFS directory: {self.gtfs_dir}")

        # ステップ2: データベースに読み込み
        if not dry_run:
            self.logger.info("=" * 60)
            self.logger.info("STEP 2: LOADING TO DATABASE")
            self.logger.info("=" * 60)

            for filename in self.LOAD_ORDER:
                if filename in self.FILE_TABLE_MAPPING:
                    csv_path = self.gtfs_dir / filename
                    table_name = self.FILE_TABLE_MAPPING[filename]

                    results['summary']['total_files'] += 1

                    try:
                        self.logger.info(
                            f"\n[{results['summary']['total_files']}/{len(self.LOAD_ORDER)}] "
                            f"Processing {filename}"
                        )
                        self.load_csv_to_table(csv_path, table_name)
                        results['loaded_tables'][table_name] = 'success'
                        results['summary']['successful_loads'] += 1
                    except Exception as e:
                        self.logger.error(f"Failed to load {filename}: {e}")
                        results['loaded_tables'][table_name] = 'failed'
                        results['summary']['failed_loads'] += 1
        else:
            self.logger.info("\n[DRY RUN] Skipping database load")

        # ステップ3: サマリ表示
        if not dry_run:
            self.logger.info("=" * 60)
            self.logger.info("STEP 3: SUMMARY")
            self.logger.info("=" * 60)

            table_summary = self.get_table_summary()
            results['table_counts'] = table_summary

            for table_name, count in table_summary.items():
                status = results['loaded_tables'].get(table_name, 'N/A')
                self.logger.info(f"{table_name}: {count} rows (status: {status})")

        # サマリを設定
        results['summary']['inserted_records'] = self.inserted_records

        return results

    def _print_job_specific_summary(self, results: Dict[str, Any]):
        """ジョブ固有のサマリ表示"""
        summary = results.get('summary', {})

        self.logger.info(f"Files processed: {summary.get('total_files', 0)}")
        self.logger.info(f"Successful loads: {summary.get('successful_loads', 0)}")
        self.logger.info(f"Failed loads: {summary.get('failed_loads', 0)}")
        self.logger.info(f"Records inserted: {summary.get('inserted_records', 0)}")
