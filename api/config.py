"""
GTFS Data Analysis Project Configuration

このモジュールは環境変数から設定を読み込み、データベース接続などの
設定情報を一元管理します。セキュリティのため、認証情報は環境変数で管理します。
"""

import os
from typing import Optional
from urllib.parse import urlparse


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


class AppConfig:
    """アプリケーション全体の設定クラス"""
    
    def __init__(self):
        # 環境設定
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        
        # データベース設定
        self.database = DatabaseConfig()
        
        # ログ設定
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
        # その他の設定
        self.data_dir = os.getenv("DATA_DIR", "/workspace/GTFS/data")
        self.temp_dir = os.getenv("TEMP_DIR", "/tmp")
    
    def is_production(self) -> bool:
        """本番環境かどうかを判定"""
        return self.environment.lower() == "production"
    
    def is_development(self) -> bool:
        """開発環境かどうかを判定"""
        return self.environment.lower() == "development"


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
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip().strip('"\'')
        return True
    except Exception as e:
        print(f"環境変数ファイル読み込みエラー: {e}")
        return False


# 環境変数ファイルの自動読み込み
env_file_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file_path):
    load_environment_from_file(env_file_path)

# グローバルな設定インスタンス（環境変数読み込み後に作成）
config = AppConfig()