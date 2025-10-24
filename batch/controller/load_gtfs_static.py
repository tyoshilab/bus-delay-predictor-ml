#!/usr/bin/env python3
"""
GTFS Static Data Loader
Loads GTFS CSV files from proto/static directory into PostgreSQL database.
"""

import os
import sys
import pandas as pd
import psycopg2
from sqlalchemy import text, MetaData, Table
from datetime import datetime
import logging

# Add parent directory to path to import config
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, project_root)
from batch.config.database_connector import DatabaseConnector

# Create a global database connector instance
db_connector = DatabaseConnector()
engine = db_connector.engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_primary_key_columns(engine, table_name, schema='gtfs_static'):
    """Get primary key columns for a table."""
    try:
        metadata = MetaData()
        table = Table(table_name, metadata, autoload_with=engine, schema=schema)
        pk_columns = [col.name for col in table.primary_key.columns]
        return pk_columns
    except Exception as e:
        logger.warning(f"Could not get primary key for {schema}.{table_name}: {e}")
        return []

def get_existing_pk_values(engine, table_name, pk_columns, schema='gtfs_static'):
    """Get existing primary key values from the database."""
    try:
        if not pk_columns:
            return set()
        
        # Build SELECT query for primary key columns
        pk_select = ', '.join([f'"{col}"' for col in pk_columns])
        query = f"SELECT {pk_select} FROM {schema}.{table_name}"
        
        with engine.connect() as conn:
            result = conn.execute(text(query))
            existing_pks = set()
            
            for row in result:
                if len(pk_columns) == 1:
                    # Single column primary key
                    existing_pks.add(row[0])
                else:
                    # Composite primary key - create tuple
                    existing_pks.add(tuple(row))
            
            return existing_pks
    
    except Exception as e:
        logger.warning(f"Could not get existing PKs for {schema}.{table_name}: {e}")
        return set()

def filter_new_records(df, existing_pks, pk_columns):
    """Filter DataFrame to only include records that don't exist in the database."""
    if not pk_columns or not existing_pks:
        return df
    
    try:
        if len(pk_columns) == 1:
            # Single column primary key
            pk_col = pk_columns[0]
            if pk_col in df.columns:
                mask = ~df[pk_col].isin(existing_pks)
                filtered_df = df[mask]
            else:
                filtered_df = df
        else:
            # Composite primary key
            # Create tuples for comparison
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

def insert_with_conflict_handling(df, table_name, engine, schema='gtfs_static'):
    """Insert data with conflict handling using pre-filtering and ON CONFLICT DO NOTHING."""
    try:
        # Get primary key columns
        pk_columns = get_primary_key_columns(engine, table_name, schema)
        
        if not pk_columns:
            logger.warning(f"No primary key found for {table_name}, using regular insert")
            df.to_sql(table_name, engine, if_exists='append', index=False, method='multi', schema=schema)
            return
        
        logger.info(f"Using conflict handling for {table_name} with PK: {pk_columns}")
        
        # Get existing primary key values from database
        existing_pks = get_existing_pk_values(engine, table_name, pk_columns, schema)
        logger.info(f"Found {len(existing_pks)} existing records in {table_name}")
        
        # Filter DataFrame to only include new records
        filtered_df = filter_new_records(df, existing_pks, pk_columns)
        
        if len(filtered_df) == 0:
            logger.info(f"No new records to insert for {table_name}")
            return
        
        # Use to_sql for bulk insert since we've already filtered out duplicates
        batch_size = 5000
        total_records = len(filtered_df)
        
        if total_records <= batch_size:
            # Small dataset - insert all at once
            logger.info(f"Inserting {total_records} new records using to_sql")
            filtered_df.to_sql(table_name, engine, if_exists='append', index=False, method='multi', schema=schema)
        else:
            # Large dataset - insert in batches
            logger.info(f"Inserting {total_records} new records in batches of {batch_size}")
            for i in range(0, total_records, batch_size):
                batch_df = filtered_df.iloc[i:i+batch_size]
                batch_df.to_sql(table_name, engine, if_exists='append', index=False, method='multi', schema=schema)
                logger.info(f"Batch {i//batch_size + 1}: {len(batch_df)} records inserted")
        
        logger.info(f"Total for {table_name}: {total_records} new records inserted")
        
    except Exception as e:
        logger.error(f"Error in conflict handling insert for {table_name}: {str(e)}")
        # Fallback to regular insert
        logger.info(f"Falling back to regular insert for {table_name}")
        df.to_sql(table_name, engine, if_exists='append', index=False, method='multi', schema=schema)

def load_csv_to_table(csv_path: str, table_name: str, engine):
    """Load CSV file into database table."""
    try:
        if not os.path.exists(csv_path):
            logger.warning(f"CSV file not found: {csv_path}")
            return
        
        # Read CSV with pandas
        df = pd.read_csv(csv_path)
        logger.info(f"Loading {len(df)} rows from {csv_path} into {table_name}")
        
        # Special handling for different file types
        if 'calendar' in csv_path:
            # Convert date columns from YYYYMMDD to proper date format
            if 'start_date' in df.columns:
                df['start_date'] = pd.to_datetime(df['start_date'], format='%Y%m%d')
            if 'end_date' in df.columns:
                df['end_date'] = pd.to_datetime(df['end_date'], format='%Y%m%d')
        
        if 'calendar_dates' in csv_path:
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
        
        if 'feed_info' in csv_path:
            # Convert date columns from YYYYMMDD to proper date format
            if 'feed_start_date' in df.columns:
                df['feed_start_date'] = pd.to_datetime(df['feed_start_date'], format='%Y%m%d')
            if 'feed_end_date' in df.columns:
                df['feed_end_date'] = pd.to_datetime(df['feed_end_date'], format='%Y%m%d')
        
        if 'stop_times' in csv_path:
            # Handle GTFS time format (HH:MM:SS) which can exceed 23:59:59
            # Convert times > 24:00:00 to next day equivalent for PostgreSQL
            def convert_gtfs_time(time_str):
                if pd.isna(time_str) or time_str == '':
                    return None
                try:
                    parts = time_str.split(':')
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])
                    
                    # Convert hours >= 24 to proper time format
                    if hours >= 24:
                        hours = hours - 24
                    
                    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                except:
                    return None
            
            if 'arrival_time' in df.columns:
                df['arrival_time'] = df['arrival_time'].apply(convert_gtfs_time)
            if 'departure_time' in df.columns:
                df['departure_time'] = df['departure_time'].apply(convert_gtfs_time)
        
        # Load data into database with conflict handling
        chunk_size = 50000 if 'stop_times' in csv_path else None
        if chunk_size and len(df) > chunk_size:
            logger.info(f"Loading large file in chunks of {chunk_size} rows...")
            for i in range(0, len(df), chunk_size):
                chunk = df[i:i+chunk_size]
                insert_with_conflict_handling(chunk, table_name, engine)
                logger.info(f"Processed chunk {i//chunk_size + 1}: rows {i+1} to {min(i+chunk_size, len(df))}")
        else:
            insert_with_conflict_handling(df, table_name, engine)
        
        logger.info(f"Successfully processed {len(df)} rows for {table_name}")
        
    except Exception as e:
        logger.error(f"Error loading {csv_path}: {str(e)}")

def main():
    """Main function to load all GTFS static data."""
    
    # Base directory for GTFS data
    gtfs_dir = "/app/proto/static/google_transit_20250912"
    
    # Mapping of CSV files to database tables
    file_mappings = {
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
    
    # Note: No longer clearing existing data since we now handle duplicates with ON CONFLICT
    logger.info("Loading GTFS static data with duplicate handling...")
    
    # Load data files in dependency order
    load_order = [
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
    
    for filename in load_order:
        if filename in file_mappings:
            csv_path = os.path.join(gtfs_dir, filename)
            table_name = file_mappings[filename]
            load_csv_to_table(csv_path, table_name, engine)
    
    logger.info("GTFS static data loading completed!")
    
    # Show summary statistics
    with engine.connect() as conn:
        for table_name in file_mappings.values():
            result = conn.execute(text(f"SELECT COUNT(*) FROM gtfs_static.{table_name}"))
            count = result.fetchone()[0]
            logger.info(f"gtfs_static.{table_name}: {count} rows")

if __name__ == "__main__":
    main()