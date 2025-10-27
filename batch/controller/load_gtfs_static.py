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

controller_dir = os.path.dirname(os.path.abspath(__file__))
batch_dir = os.path.dirname(controller_dir)
project_root = os.path.dirname(batch_dir)

sys.path.insert(0, project_root)
from batch.config.database_connector import DatabaseConnector

# Create a global database connector instance
db_connector = DatabaseConnector()
engine = db_connector.engine

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Suppress SQLAlchemy verbose logging (no SQL queries in output)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)

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
        error_msg = str(e).split('\n')[0]  # Get only the first line of error
        logger.error(f"Error in conflict handling insert for {table_name}: {error_msg}")
        # Fallback to regular insert
        logger.info(f"Falling back to regular insert for {table_name}")
        try:
            df.to_sql(table_name, engine, if_exists='append', index=False, method='multi', schema=schema)
        except Exception as fallback_error:
            fallback_msg = str(fallback_error).split('\n')[0]
            logger.error(f"Fallback insert also failed: {fallback_msg}")
            raise

def load_csv_to_table(csv_path: str, table_name: str, engine, optional=False):
    """Load CSV file into database table."""
    try:
        if not os.path.exists(csv_path):
            if optional:
                logger.info(f"Optional file not found (skipping): {csv_path}")
            else:
                logger.warning(f"Required CSV file not found: {csv_path}")
            return False

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
            # GTFS Spec: Times >= 24:00:00 represent times on the following service day
            # Example: 25:35:00 = 1:35 AM on the day after the service date
            def convert_gtfs_time_with_offset(time_str):
                """
                Convert GTFS time to (time, day_offset) tuple.
                Returns: (time_string, day_offset) or (None, 0) for invalid input
                """
                if pd.isna(time_str) or time_str == '':
                    return None, 0
                try:
                    parts = time_str.split(':')
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])

                    # Calculate day offset (0 = same day, 1 = next day, etc.)
                    day_offset = hours // 24
                    hours = hours % 24

                    return f"{hours:02d}:{minutes:02d}:{seconds:02d}", day_offset
                except Exception as e:
                    logger.warning(f"Failed to parse time '{time_str}': {e}")
                    return None, 0

            if 'arrival_time' in df.columns:
                # Apply conversion and split into time and offset
                converted = df['arrival_time'].apply(convert_gtfs_time_with_offset)
                df['arrival_time'] = converted.apply(lambda x: x[0])
                df['arrival_day_offset'] = converted.apply(lambda x: x[1])

                # Log statistics
                next_day_arrivals = (df['arrival_day_offset'] > 0).sum()
                if next_day_arrivals > 0:
                    logger.info(f"Found {next_day_arrivals} arrival times on next day (originally >= 24:00:00)")

            if 'departure_time' in df.columns:
                # Apply conversion and split into time and offset
                converted = df['departure_time'].apply(convert_gtfs_time_with_offset)
                df['departure_time'] = converted.apply(lambda x: x[0])
                df['departure_day_offset'] = converted.apply(lambda x: x[1])

                # Log statistics
                next_day_departures = (df['departure_day_offset'] > 0).sum()
                if next_day_departures > 0:
                    logger.info(f"Found {next_day_departures} departure times on next day (originally >= 24:00:00)")
        
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
        return True

    except Exception as e:
        # Extract only the meaningful error message
        error_msg = str(e)
        if '\n' in error_msg:
            # For multi-line errors, get first and last meaningful lines
            lines = [l for l in error_msg.split('\n') if l.strip()]
            if len(lines) > 3:
                error_msg = f"{lines[0]} ... {lines[-1]}"
            else:
                error_msg = lines[0] if lines else str(e)

        logger.error(f"Error loading {csv_path}: {error_msg}")

        # Show detailed traceback only for debugging
        import traceback
        detailed_error = traceback.format_exc()
        # Save to file instead of printing
        error_log_path = f"/tmp/gtfs_load_error_{table_name}.log"
        with open(error_log_path, 'w') as f:
            f.write(detailed_error)
        logger.error(f"Detailed error saved to: {error_log_path}")

        return False

def main():
    """Main function to load all GTFS static data."""

    # Base directory for GTFS data
    gtfs_dir = "/app/batch/downloads/gtfs_static/download_1761561842"

    # Check if directory exists
    if not os.path.exists(gtfs_dir):
        logger.error(f"GTFS directory not found: {gtfs_dir}")
        logger.info("Checking available directories...")
        parent_dir = os.path.dirname(gtfs_dir)
        if os.path.exists(parent_dir):
            available_dirs = [d for d in os.listdir(parent_dir) if os.path.isdir(os.path.join(parent_dir, d))]
            logger.info(f"Available directories: {available_dirs}")
        sys.exit(1)

    logger.info(f"Loading GTFS data from: {gtfs_dir}")

    # Mapping of CSV files to database tables
    # Mark optional files (files that may not exist in all GTFS feeds)
    file_mappings = {
        # Required GTFS files
        'agency.txt': {'table': 'gtfs_agency', 'optional': False},
        'routes.txt': {'table': 'gtfs_routes', 'optional': False},
        'stops.txt': {'table': 'gtfs_stops', 'optional': False},
        'trips.txt': {'table': 'gtfs_trips_static', 'optional': False},
        'stop_times.txt': {'table': 'gtfs_stop_times', 'optional': False},
        # Conditionally required files
        'calendar.txt': {'table': 'gtfs_calendar', 'optional': True},  # or calendar_dates.txt
        'calendar_dates.txt': {'table': 'gtfs_calendar_dates', 'optional': True},
        # Optional files
        'feed_info.txt': {'table': 'gtfs_feed_info', 'optional': True},
        'shapes.txt': {'table': 'gtfs_shapes', 'optional': True},
        'transfers.txt': {'table': 'gtfs_transfers', 'optional': True},
        # Non-standard files (TransLink specific)
        'directions.txt': {'table': 'gtfs_directions', 'optional': True},
    }

    # Note: No longer clearing existing data since we now handle duplicates with ON CONFLICT
    logger.info("============================================================")
    logger.info("STEP 1: LOADING GTFS STATIC DATA")
    logger.info("============================================================")
    logger.info("Loading with duplicate handling enabled...")

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

    # Track load results
    load_results = {}

    for filename in load_order:
        if filename in file_mappings:
            csv_path = os.path.join(gtfs_dir, filename)
            table_name = file_mappings[filename]['table']
            optional = file_mappings[filename]['optional']

            logger.info(f"Loading {filename} -> {table_name} (optional={optional})...")
            success = load_csv_to_table(csv_path, table_name, engine, optional=optional)
            load_results[filename] = success
    
    # Show load results
    logger.info("")
    logger.info("============================================================")
    logger.info("STEP 2: LOAD RESULTS SUMMARY")
    logger.info("============================================================")
    success_count = sum(1 for v in load_results.values() if v)
    fail_count = sum(1 for v in load_results.values() if v is False)
    skip_count = sum(1 for v in load_results.values() if v is None)

    for filename, success in load_results.items():
        status = "✓ SUCCESS" if success else ("⚠ SKIPPED" if success is None else "✗ FAILED")
        logger.info(f"{filename:25} -> {status}")

    logger.info(f"\nTotal: {len(load_results)} files | Success: {success_count} | Failed: {fail_count} | Skipped: {skip_count}")

    # Show summary statistics
    logger.info("")
    logger.info("============================================================")
    logger.info("STEP 3: DATABASE TABLE STATISTICS")
    logger.info("============================================================")
    with engine.connect() as conn:
        for filename, file_info in file_mappings.items():
            table_name = file_info['table']
            try:
                result = conn.execute(text(f"SELECT COUNT(*) FROM gtfs_static.{table_name}"))
                count = result.fetchone()[0]
                status = "✓" if count > 0 else ("○" if file_info['optional'] else "✗")
                logger.info(f"{status} {table_name:30} {count:8,} rows")
            except Exception as e:
                logger.warning(f"✗ {table_name:30} ERROR: {str(e)}")

    # Refresh materialized views after loading static data
    logger.info("")
    logger.info("============================================================")
    logger.info("STEP 4: REFRESHING MATERIALIZED VIEWS")
    logger.info("============================================================")
    try:
        with engine.connect() as conn:
            logger.info("Calling gtfs_static.refresh_static_views()...")
            conn.execute(text("CALL gtfs_static.refresh_static_views();"))
            conn.commit()
        logger.info("✓ Materialized views refreshed successfully!")
    except Exception as e:
        logger.error(f"✗ Failed to refresh materialized views: {str(e)}")
        logger.warning("⚠ Continuing despite materialized view refresh failure...")

    logger.info("")
    logger.info("============================================================")
    logger.info("GTFS STATIC DATA LOAD COMPLETE")
    logger.info("============================================================")

if __name__ == "__main__":
    main()