"""
GTFS Batch Processing Configuration

このモジュールは環境変数から設定を読み込み、バッチジョブの
設定情報を一元管理します。セキュリティのため、認証情報は環境変数で管理します。

api/config.py と統一されたクラスベースの設計を採用しています。
"""

import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class DatabaseConfig:
    """データベース設定クラス"""

    def __init__(self):
        # 環境変数から設定を読み込み
        self.database_url = self._get_database_url()
        self.ssl_require = os.getenv("DATABASE_SSL_REQUIRE", "1") == "1"

        # 接続パラメータをパース
        self._parse_connection_url()

    def _get_database_url(self) -> str:
        """データベースURLを環境変数から取得"""
        # 優先順位：DATABASE_URL > POSTGRES_URL > デフォルト
        database_url = (
            os.getenv("DATABASE_URL") or
            os.getenv("POSTGRES_URL") or
            self._get_default_url()
        )

        # postgres:// を postgresql:// に変換（SQLAlchemy互換性のため）
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

        return database_url

    def _get_default_url(self) -> str:
        """個別の環境変数からデフォルトURLを構築"""
        # 個別の環境変数から構築
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "gtfs_db")
        username = os.getenv("DB_USER", "gtfs_user")
        password = os.getenv("DB_PASSWORD", "")

        if not password:
            raise ValueError(
                "データベース認証情報が設定されていません。"
                "DATABASE_URL または DB_PASSWORD 環境変数を設定してください。"
            )

        return f"postgresql://{username}:{password}@{host}:{port}/{database}"

    def _parse_connection_url(self):
        """接続URLをパースして個別のパラメータを設定"""
        result = urlparse(self.database_url)
        self.username = result.username
        self.password = result.password
        self.database = result.path[1:]  # 先頭の '/' を除去
        self.hostname = result.hostname
        self.port = result.port or 5432

    def get_psycopg2_params(self) -> dict:
        """psycopg2用の接続パラメータを取得"""
        params = {
            'database': self.database,
            'user': self.username,
            'password': self.password,
            'host': self.hostname,
            'port': self.port,
        }

        if self.ssl_require:
            params['sslmode'] = 'require'

        return params

    def get_sqlalchemy_connect_args(self) -> dict:
        """SQLAlchemy用の接続引数を取得"""
        if self.ssl_require:
            return {"sslmode": "require"}
        return {}


class TransLinkAPIConfig:
    """TransLink API設定クラス"""

    def __init__(self):
        self.api_key = os.getenv('TRANSLINK_API_KEY')
        self.base_url = os.getenv('TRANSLINK_API_BASE_URL', 'https://gtfsapi.translink.ca')

    def get_api_key(self) -> str:
        """
        TransLink APIキーを取得

        Returns:
            APIキー

        Raises:
            ValueError: 環境変数が設定されていない場合
        """
        if not self.api_key:
            raise ValueError(
                "TRANSLINK_API_KEY environment variable not set. "
                "Please obtain an API key from TransLink and configure it in .env file."
            )
        return self.api_key

    def get_static_url(self) -> str:
        """GTFS Static ダウンロードURLを取得"""
        return f"{self.base_url}/v3/gtfsstatic"

    def get_realtime_url(self) -> str:
        """
        GTFS Realtime フィードURLを取得

        Note:
            TransLinkのAPIは全フィードタイプで同じベースURLを使用し、
            feed_type は APIキーのクエリパラメータで指定します
        """
        return f"{self.base_url}/v3/gtfsrealtime"


class DirectoryConfig:
    """ディレクトリ設定クラス"""

    def __init__(self, project_root: Path):
        self.project_root = project_root

        # ログディレクトリ
        self.log_dir = project_root / 'batch' / 'logs'
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # ダウンロードディレクトリ（ルート）
        self.download_dir = project_root / 'batch' / 'downloads'
        self.download_dir.mkdir(parents=True, exist_ok=True)

        # 気候データダウンロードディレクトリ
        self.climate_download_dir = self.download_dir / 'climate'
        self.climate_download_dir.mkdir(parents=True, exist_ok=True)

        # GTFS Staticダウンロードディレクトリ
        self.gtfs_static_storage_dir = self.download_dir / 'gtfs_static'
        self.gtfs_static_storage_dir.mkdir(parents=True, exist_ok=True)

        # GTFS Realtimeダウンロードディレクトリ
        self.gtfs_rt_storage_dir = self.download_dir / 'gtfs_realtime'
        self.gtfs_rt_storage_dir.mkdir(parents=True, exist_ok=True)

        # モデルディレクトリ
        self.model_dir = project_root / 'files' / 'model'
        self.model_dir.mkdir(parents=True, exist_ok=True)

class GTFSRealtimeConfig:
    """GTFS Realtime設定クラス"""

    def __init__(self):
        self.cleanup_days = int(os.getenv('GTFS_RT_CLEANUP_DAYS', '7'))
        self.save_to_disk = os.getenv('GTFS_RT_SAVE_TO_DISK', '1') == '1'


class WeatherScraperConfig:
    """Weather Scraper設定クラス"""

    def __init__(self):
        self.url = os.getenv(
            'WEATHER_SCRAPER_URL',
            'https://vancouver.weatherstats.ca/download.html'
        )
        self.row_limit = int(os.getenv('WEATHER_SCRAPER_ROW_LIMIT', '336'))
        self.cleanup_days = int(os.getenv('WEATHER_FILE_CLEANUP_DAYS', '7'))


class PredictionConfig:
    """地域遅延予測設定クラス"""

    def __init__(self, model_dir: Path):
        self.model_dir = model_dir
        self.model_path = os.getenv(
            'PREDICTION_MODEL_PATH',
            str(model_dir / 'best_delay_model.h5')
        )
        self.input_timesteps = int(os.getenv('PREDICTION_INPUT_TIMESTEPS', '8'))
        self.output_timesteps = int(os.getenv('PREDICTION_OUTPUT_TIMESTEPS', '3'))

    def get_model_path(self, model_name: Optional[str] = None) -> Path:
        """
        予測モデルのパスを取得

        Args:
            model_name: モデルファイル名（Noneの場合はデフォルトモデル）

        Returns:
            モデルファイルのパス

        Raises:
            FileNotFoundError: モデルファイルが存在しない場合
        """
        if model_name:
            model_path = self.model_dir / model_name
        else:
            model_path = Path(self.model_path)

        if not model_path.exists():
            raise FileNotFoundError(
                f"Model file not found: {model_path}. "
                f"Please train a model first or specify correct model path."
            )

        return model_path


class LoggingConfig:
    """ログ設定クラス"""

    def __init__(self):
        self.level = os.getenv('LOG_LEVEL', 'INFO')
        self.format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    def get_level(self) -> str:
        """ログレベルを取得"""
        return self.level


class BatchConfig:
    """バッチジョブ全体の設定クラス"""

    def __init__(self):
        # プロジェクトルート
        self.project_root = Path(__file__).parent.parent.parent

        # 環境設定
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.debug = os.getenv("DEBUG", "False").lower() == "true"

        # 各種設定クラスのインスタンス化
        self.database = DatabaseConfig()
        self.translink_api = TransLinkAPIConfig()
        self.directories = DirectoryConfig(self.project_root)
        self.gtfs_realtime = GTFSRealtimeConfig()
        self.weather_scraper = WeatherScraperConfig()
        self.prediction = PredictionConfig(self.directories.model_dir)
        self.logging = LoggingConfig()

    def is_production(self) -> bool:
        """本番環境かどうかを判定"""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """開発環境かどうかを判定"""
        return self.environment.lower() == "development"

    def validate_configuration(self) -> bool:
        """
        設定の検証

        Returns:
            検証結果（True=正常、False=問題あり）
        """
        issues = []

        # データベースURL
        try:
            _ = self.database.database_url
        except ValueError as e:
            issues.append(f"Database configuration: {e}")

        # TransLink APIキー（警告のみ）
        if not self.translink_api.api_key:
            logger.warning(
                "TRANSLINK_API_KEY not set. "
                "GTFS fetch jobs will fail without API key."
            )

        # モデルファイル（警告のみ）
        try:
            self.prediction.get_model_path()
        except FileNotFoundError as e:
            logger.warning(f"Model file: {e}")

        # ディレクトリの作成確認
        for dir_name, dir_path in [
            ('log_dir', self.directories.log_dir),
            ('download_dir', self.directories.download_dir)
        ]:
            if not dir_path.exists():
                issues.append(f"Directory not created: {dir_name} ({dir_path})")

        if issues:
            for issue in issues:
                logger.error(issue)
            return False

        return True


def load_environment_from_file(env_file: str = ".env") -> bool:
    """
    .envファイルから環境変数を読み込む

    Args:
        env_file: 環境変数ファイルのパス

    Returns:
        読み込み成功可否
    """
    if not os.path.exists(env_file):
        return False

    try:
        with open(env_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip().strip('"\'')
        return True
    except Exception as e:
        logger.warning(f"環境変数ファイル読み込みエラー: {e}")
        return False


# 環境変数ファイルの自動読み込み
# プロジェクトルートの .env ファイルを探す
_project_root = Path(__file__).parent.parent.parent
_env_file_path = _project_root / ".env"
if _env_file_path.exists():
    load_environment_from_file(str(_env_file_path))

# グローバルな設定インスタンス（環境変数読み込み後に作成）
config = BatchConfig()
