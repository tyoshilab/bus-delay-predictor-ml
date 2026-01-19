import os
from typing import Optional
from urllib.parse import urlparse


class DatabaseConfig:
    def __init__(self):
        self.database_url = self._get_database_url()
        self.ssl_require = os.getenv("DATABASE_SSL_REQUIRE", "1") == "1"
        
        self._parse_connection_url()
    
    def _get_database_url(self) -> str:
        database_url = (
            os.getenv("DATABASE_URL") or
            self._get_default_url()
        )
        
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
            
        return database_url
    
    def _get_default_url(self) -> str:
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
        result = urlparse(self.database_url)
        self.username = result.username
        self.password = result.password
        self.database = result.path[1:]  # 先頭の '/' を除去
        self.hostname = result.hostname
        self.port = result.port or 5432
    
    def get_psycopg2_params(self) -> dict:
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
        if self.ssl_require:
            return {"sslmode": "require"}
        return {}


class AppConfig:
    def __init__(self):
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.debug = os.getenv("DEBUG", "False").lower() == "true"
        
        self.database = DatabaseConfig()
        
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
        self.data_dir = os.getenv("DATA_DIR", "/workspace/GTFS/data")
        self.temp_dir = os.getenv("TEMP_DIR", "/tmp")
    
    def is_production(self) -> bool:
        return self.environment.lower() == "production"
    
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


def load_environment_from_file(env_file: str = ".env") -> bool:
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


env_file_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file_path):
    load_environment_from_file(env_file_path)

config = AppConfig()