import pandas as pd
import psycopg2
import warnings
warnings.filterwarnings('ignore')
from sqlalchemy import create_engine
import sys
import os

# プロジェクトルートをパスに追加
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
if project_root not in sys.path:
    sys.path.append(project_root)

from config import config

class DatabaseConnector:
    def __init__(self, database_url=None):
        if database_url is None:
            # 設定システムからデータベース設定を取得
            self.db_config = config.database
            database_url = self.db_config.database_url
        else:
            # カスタムURLが指定された場合は一時的な設定を作成
            from config import DatabaseConfig
            self.db_config = DatabaseConfig()
            # カスタムURLで上書き
            if database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
            self.db_config.database_url = database_url
            self.db_config._parse_connection_url()

        self.engine = create_engine(
            self.db_config.database_url,
            connect_args=self.db_config.get_sqlalchemy_connect_args(),
            pool_pre_ping=True,
        )
    
    def get_connection(self):
        """データベース接続を取得"""
        return psycopg2.connect(**self.db_config.get_psycopg2_params())
    
    def read_sql(self, query, params=None) -> pd.DataFrame:
        """SQLクエリを実行してDataFrameを返す"""
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)
    
    def test_connection(self):
        """接続テスト"""
        try:
            result = self.read_sql("SELECT 1 as test_value")
            print("Database connection successful")
            print(f"Environment: {config.environment}")
            print(f"Database: {self.db_config.database}")
            print(f"Host: {self.db_config.hostname}")
            return True
        except Exception as e:
            print(f"Database connection failed: {e}")
            return False
