import pandas as pd
import psycopg2
import warnings
warnings.filterwarnings('ignore')
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import sys
import os
from urllib.parse import urlparse

# SQLAlchemy Base for ORM models
Base = declarative_base()

class DatabaseConnector:
    def __init__(self, database_url=None):
        # 環境変数からデータベースURLを取得
        if database_url is None:
            database_url = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL')

        if database_url is None:
            raise ValueError("DATABASE_URL or POSTGRES_URL environment variable is required")

        # postgres:// を postgresql:// に変換
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)

        # URLをパース
        parsed = urlparse(database_url)
        self.hostname = parsed.hostname
        self.port = parsed.port or 5432
        self.database = parsed.path.lstrip('/')
        self.username = parsed.username
        self.password = parsed.password

        # データベースURLを保存
        self.database_url = database_url

        # Add timezone to connect_args
        connect_args = {
            'options': '-c timezone=America/Vancouver'
        }

        self.engine = create_engine(
            self.database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
        )

        # Create SessionLocal for ORM operations
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def get_connection(self):
        """データベース接続を取得"""
        return psycopg2.connect(
            host=self.hostname,
            port=self.port,
            database=self.database,
            user=self.username,
            password=self.password,
            options='-c timezone=America/Vancouver'
        )
    
    def read_sql(self, query, params=None) -> pd.DataFrame:
        """SQLクエリを実行してDataFrameを返す"""
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)
        # PostgreSQLは接続時にtimezone=America/Vancouverを設定しているため、
        # 返されるtimestampはすでにPacific Timeです。
        # pandasはこれをtimezone-naiveとして読み込むので、正しいタイムゾーンを明示的に設定します。
        for col in df.select_dtypes(include=['datetime64']).columns:
            df[col] = df[col].dt.tz_localize('America/Vancouver')
        return df
    
    def insert_dataframe(self, df: pd.DataFrame, table_name: str, if_exists: str = 'append', schema: str = None):
        """DataFrameをテーブルに挿入"""
        df.to_sql(table_name, self.engine, if_exists=if_exists, index=False, schema=schema)

    def get_session(self):
        """新しいORMセッションを取得"""
        return self.SessionLocal()

    def test_connection(self):
        """接続テスト"""
        try:
            result = self.read_sql("SELECT 1 as test_value")
            print("Database connection successful")
            print(f"Database: {self.database}")
            print(f"Host: {self.hostname}")
            return True
        except Exception as e:
            print(f"Database connection failed: {e}")
            return False
