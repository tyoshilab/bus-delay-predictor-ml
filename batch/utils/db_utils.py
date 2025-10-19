"""
Database Utilities

データベース操作に関する共通ユーティリティ
"""

import logging
from typing import List, Set, Optional
import pandas as pd
from sqlalchemy import text, MetaData, Table, Engine

logger = logging.getLogger(__name__)


def get_primary_key_columns(engine: Engine, table_name: str, schema: str = 'public') -> List[str]:
    """
    テーブルの主キーカラムを取得

    Args:
        engine: SQLAlchemyエンジン
        table_name: テーブル名
        schema: スキーマ名

    Returns:
        主キーカラムのリスト
    """
    try:
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=engine, schema=schema)
        pk_columns = [col.name for col in table.primary_key.columns]
        logger.debug(f"Primary key columns for {schema}.{table_name}: {pk_columns}")
        return pk_columns
    except Exception as e:
        logger.warning(f"Could not get primary key for {schema}.{table_name}: {e}")
        return []


def get_existing_pk_values(
    engine: Engine,
    table_name: str,
    pk_columns: List[str],
    schema: str = 'public'
) -> Set:
    """
    データベースから既存の主キー値を取得

    Args:
        engine: SQLAlchemyエンジン
        table_name: テーブル名
        pk_columns: 主キーカラムのリスト
        schema: スキーマ名

    Returns:
        既存の主キー値のセット
    """
    try:
        if not pk_columns:
            return set()

        pk_select = ', '.join([f'"{col}"' for col in pk_columns])
        query = f"SELECT {pk_select} FROM {schema}.{table_name}"

        with engine.connect() as conn:
            result = conn.execute(text(query))
            existing_pks = set()

            for row in result:
                if len(pk_columns) == 1:
                    existing_pks.add(row[0])
                else:
                    existing_pks.add(tuple(row))

            logger.debug(f"Found {len(existing_pks)} existing records in {schema}.{table_name}")
            return existing_pks

    except Exception as e:
        logger.warning(f"Could not get existing PKs for {schema}.{table_name}: {e}")
        return set()


def filter_new_records(
    df: pd.DataFrame,
    existing_pks: Set,
    pk_columns: List[str]
) -> pd.DataFrame:
    """
    新規レコードのみにフィルタリング

    Args:
        df: データフレーム
        existing_pks: 既存の主キー値のセット
        pk_columns: 主キーカラムのリスト

    Returns:
        新規レコードのみのデータフレーム
    """
    if not pk_columns or not existing_pks:
        return df

    try:
        if len(pk_columns) == 1:
            pk_col = pk_columns[0]
            if pk_col in df.columns:
                mask = ~df[pk_col].isin(existing_pks)
                filtered_df = df[mask]
            else:
                logger.warning(f"Primary key column '{pk_col}' not found in dataframe")
                filtered_df = df
        else:
            def create_pk_tuple(row):
                return tuple(row[col] for col in pk_columns if col in df.columns)

            df_pk_tuples = df.apply(create_pk_tuple, axis=1)
            mask = ~df_pk_tuples.isin(existing_pks)
            filtered_df = df[mask]

        logger.info(f"Filtered {len(df)} rows to {len(filtered_df)} new records")
        return filtered_df

    except Exception as e:
        logger.warning(f"Error filtering records: {e}")
        return df


def insert_with_conflict_handling(
    df: pd.DataFrame,
    table_name: str,
    engine: Engine,
    schema: str = 'public',
    batch_size: int = 5000
) -> int:
    """
    重複を避けて挿入（既存レコードをスキップ）

    Args:
        df: 挿入するデータフレーム
        table_name: テーブル名
        engine: SQLAlchemyエンジン
        schema: スキーマ名
        batch_size: バッチサイズ

    Returns:
        挿入されたレコード数
    """
    try:
        if df.empty:
            logger.info(f"No records to insert for {schema}.{table_name}")
            return 0

        # 主キーを取得
        pk_columns = get_primary_key_columns(engine, table_name, schema)

        if not pk_columns:
            logger.warning(f"No primary key found for {table_name}, using regular insert")
            df.to_sql(
                table_name,
                engine,
                if_exists='append',
                index=False,
                method='multi',
                schema=schema
            )
            return len(df)

        logger.info(f"Using conflict handling for {table_name} with PK: {pk_columns}")

        # 既存の主キー値を取得
        existing_pks = get_existing_pk_values(engine, table_name, pk_columns, schema)

        # 新規レコードのみにフィルタリング
        filtered_df = filter_new_records(df, existing_pks, pk_columns)

        if len(filtered_df) == 0:
            logger.info(f"No new records to insert for {table_name}")
            return 0

        # バッチ挿入
        total_records = len(filtered_df)

        if total_records <= batch_size:
            logger.info(f"Inserting {total_records} new records into {schema}.{table_name}")
            filtered_df.to_sql(
                table_name,
                engine,
                if_exists='append',
                index=False,
                method='multi',
                schema=schema
            )
        else:
            logger.info(
                f"Inserting {total_records} new records into {schema}.{table_name} "
                f"in batches of {batch_size}"
            )
            for i in range(0, total_records, batch_size):
                batch_df = filtered_df.iloc[i:i+batch_size]
                batch_df.to_sql(
                    table_name,
                    engine,
                    if_exists='append',
                    index=False,
                    method='multi',
                    schema=schema
                )
                logger.info(f"Batch {i//batch_size + 1}: {len(batch_df)} records inserted")

        logger.info(f"Total for {schema}.{table_name}: {total_records} new records inserted")
        return total_records

    except Exception as e:
        logger.error(f"Error in conflict handling insert for {schema}.{table_name}: {e}")
        raise
