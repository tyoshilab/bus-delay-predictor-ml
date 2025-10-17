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

        # Add timezone to connect_args
        connect_args = self.db_config.get_sqlalchemy_connect_args()
        connect_args['options'] = '-c timezone=America/Vancouver'

        # 接続プーリングの最適化
        self.engine = create_engine(
            self.db_config.database_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_size=5,                    # プールサイズを5に設定
            max_overflow=10,                # 最大オーバーフロー接続数
            pool_recycle=3600,              # 1時間で接続をリサイクル
            pool_timeout=30,                # 接続取得タイムアウト
            echo_pool=False                 # プールのデバッグログを無効化
        )

        # 接続パラメータの最適化
        self._conn_params = self.db_config.get_psycopg2_params()
        self._conn_params['connect_timeout'] = 10  # 接続タイムアウト10秒
        self._conn_params['keepalives'] = 1        # キープアライブ有効
        self._conn_params['keepalives_idle'] = 30  # アイドル30秒後にキープアライブ
        self._conn_params['keepalives_interval'] = 10  # 10秒間隔でキープアライブ
        self._conn_params['keepalives_count'] = 5   # 5回失敗で接続切断

        # 接続キャッシュ（再利用）
        self._cached_conn = None

    def get_connection(self):
        """データベース接続を取得（キャッシュ再利用）"""
        # キャッシュされた接続が有効なら再利用
        if self._cached_conn is not None:
            try:
                # 接続が生きているか確認
                cursor = self._cached_conn.cursor()
                cursor.execute('SELECT 1')
                cursor.close()
                return self._cached_conn
            except:
                # 接続が切れていたら破棄
                try:
                    self._cached_conn.close()
                except:
                    pass
                self._cached_conn = None

        # 新しい接続を作成してキャッシュ
        self._cached_conn = psycopg2.connect(**self._conn_params)
        # デフォルトでautocommitをTrueに設定
        self._cached_conn.autocommit = True
        return self._cached_conn

    def close_connection(self):
        """キャッシュされた接続を明示的に閉じる"""
        if self._cached_conn is not None:
            try:
                self._cached_conn.close()
            except:
                pass
            self._cached_conn = None
    
    def read_sql(self, query, params=None, parse_dates=None, convert_tz=True, debug=False,
                 use_server_cursor=False, chunksize=None) -> pd.DataFrame:
        """
        SQLクエリを実行してDataFrameを返す

        Args:
            query: SQLクエリ文字列
            params: パラメータ辞書
            parse_dates: パースする日時カラムのリスト（Noneの場合は自動検出）
            convert_tz: タイムゾーン変換を行うか（デフォルト: True）
            debug: デバッグ情報を表示するか（デフォルト: False）
            use_server_cursor: サーバーサイドカーソルを使用（大量データ時に高速化）
            chunksize: チャンクサイズ（use_server_cursor=True時に有効）
        """
        import time

        start_time = time.time()

        if debug:
            print(f"    - Getting connection... ", end='')
            conn_start = time.time()

        # キャッシュされた接続を再利用（withを使わない）
        conn = self.get_connection()

        if debug:
            conn_time = time.time() - conn_start
            print(f"done ({conn_time:.2f}s)")
            print(f"    - Executing query (server_cursor={use_server_cursor})... ", end='')
            query_start = time.time()

        # サーバーサイドカーソルを使う場合
        if use_server_cursor:
            # チャンクサイズのデフォルト設定
            if chunksize is None:
                chunksize = 50000  # 5万行ずつ取得

            # サーバーサイドカーソルで分割取得
            cursor_name = f'server_cursor_{int(time.time() * 1000000)}'

            # トランザクション開始（サーバーサイドカーソルに必須）
            conn.autocommit = False

            try:
                # カーソルを作成
                cursor = conn.cursor(name=cursor_name)

                # パラメータ化クエリを実行
                if params:
                    # psycopg2の名前付きパラメータ形式に変換
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                # チャンクごとにデータを取得
                chunks = []
                chunk_count = 0
                total_rows = 0
                columns = None

                while True:
                    rows = cursor.fetchmany(chunksize)
                    if not rows:
                        break

                    # 最初のチャンクで列名を取得
                    if columns is None:
                        columns = [desc[0] for desc in cursor.description]

                    chunk_df = pd.DataFrame(rows, columns=columns)
                    chunks.append(chunk_df)
                    chunk_count += 1
                    total_rows += len(rows)

                    if debug and chunk_count % 5 == 0:
                        print(f"\n      Fetched {total_rows:,} rows... ", end='')

                # カーソルを閉じる
                cursor.close()

                # トランザクションをコミット
                conn.commit()

                # 全チャンクを結合
                if chunks:
                    df = pd.concat(chunks, ignore_index=True)
                else:
                    df = pd.DataFrame(columns=columns)

                # parse_dates処理
                if parse_dates:
                    for col in parse_dates:
                        if col in df.columns:
                            df[col] = pd.to_datetime(df[col])

            except Exception as e:
                # エラー時はロールバック
                conn.rollback()
                raise e
            finally:
                # autocommitを戻す
                conn.autocommit = True
        else:
            # 通常のread_sql_query
            df = pd.read_sql_query(query, conn, params=params, parse_dates=parse_dates)

        if debug:
            query_time = time.time() - query_start
            print(f"done ({query_time:.2f}s)")
            print(f"    - Rows fetched: {len(df):,}, Memory: {df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")

        # 接続を閉じない（キャッシュして再利用）

        # タイムゾーン変換（オプション）
        if convert_tz:
            if debug:
                print(f"    - Converting timezone... ", end='')
                tz_start = time.time()

            datetime_cols = df.select_dtypes(include=['datetime64']).columns
            for col in datetime_cols:
                if df[col].dt.tz is None:
                    df[col] = df[col].dt.tz_localize('UTC').dt.tz_convert('America/Vancouver')

            if debug:
                tz_time = time.time() - tz_start
                print(f"done ({tz_time:.2f}s)")

        if debug:
            total_time = time.time() - start_time
            print(f"    - Total read_sql time: {total_time:.2f}s")

        return df
    
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
