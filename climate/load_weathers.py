#!/usr/bin/env python3
"""
Weather Data Loader
Loads Vancouver weather CSV data into PostgreSQL database.
"""

import os
import sys
import pandas as pd
import logging

# Add parent directory to path to import DatabaseConnector
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.data_connection.database_connector import DatabaseConnector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_weather_csv_to_table(csv_path: str, table_name: str, db_connector: DatabaseConnector):
    """Load weather CSV file into database table, avoiding duplicates."""
    try:
        if not os.path.exists(csv_path):
            logger.warning(f"CSV file not found: {csv_path}")
            return
        
        # Read CSV with pandas
        df = pd.read_csv(csv_path)
        logger.info(f"Processing {len(df)} rows from {csv_path}")
        
        # Convert date_time_local to proper datetime format
        if 'date_time_local' in df.columns:
            # Remove timezone info and convert to datetime
            df['date_time_local'] = pd.to_datetime(df['date_time_local'].str.replace(' PDT', '').str.replace(' PST', ''))
        
        # Convert unixtime to proper datetime format
        # if 'unixtime' in df.columns:
        #     df['datetime_utc'] = pd.to_datetime(df['unixtime'], unit='s')
        
        # Handle any null values in numeric columns
        numeric_columns = [
            'pressure_station', 'pressure_sea', 'wind_dir_10s', 'wind_speed',
            'relative_humidity', 'dew_point', 'temperature', 'visibility',
            'cloud_cover_8', 'max_air_temp_pst1hr', 'min_air_temp_pst1hr', 'humidex_v'
        ]
        
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Check for existing data to avoid duplicates
        try:
            # Get existing timestamps using DatabaseConnector
            existing_data = db_connector.read_sql(f"SELECT DISTINCT date_time_local FROM climate.{table_name}")
            existing_timestamps = set(existing_data['date_time_local'].tolist())
            
            # Filter out rows that already exist
            if existing_timestamps:
                initial_count = len(df)
                df = df[~df['date_time_local'].isin(existing_timestamps)]
                filtered_count = len(df)
                logger.info(f"Filtered out {initial_count - filtered_count} duplicate rows, {filtered_count} new rows to insert")
            else:
                logger.info(f"No existing data found, inserting all {len(df)} rows")
                
        except Exception as e:
            logger.warning(f"Could not check for existing data (table may not exist): {e}")
            logger.info(f"Proceeding to insert all {len(df)} rows")
        
        # Only load if there are new rows
        if len(df) > 0:
            # Load data into database using raw connection
            with db_connector.engine.connect() as conn:
                df.to_sql(table_name, conn, if_exists='append', index=False, method='multi', schema='climate')
            logger.info(f"Successfully loaded {len(df)} new rows into {table_name}")
        else:
            logger.info("No new data to load")
        
    except Exception as e:
        logger.error(f"Error loading {csv_path}: {str(e)}")

def main():
    """Main function to load weather data incrementally."""
    
    # Path to weather CSV file
    weather_csv = "/workspace/GTFS/climate/weatherstats_vancouver_hourly_filled.csv"
    table_name = 'weather_hourly'
    
    logger.info("Starting incremental weather data loading...")
    
    # Initialize database connector
    db_connector = DatabaseConnector()
    
    # Test connection first
    if not db_connector.test_connection():
        logger.error("Failed to connect to database. Exiting.")
        return
    
    # Load weather data (with duplicate detection)
    load_weather_csv_to_table(weather_csv, table_name, db_connector)
    
    logger.info("Weather data loading completed!")
    
    # Show summary statistics
    try:
        # Get row count
        count_result = db_connector.read_sql(f"SELECT COUNT(*) as count FROM climate.{table_name}")
        count = count_result['count'].iloc[0]
        logger.info(f"climate.{table_name}: {count} rows")
        
        # Show date range
        date_range_result = db_connector.read_sql(f"SELECT MIN(date_time_local) as min_date, MAX(date_time_local) as max_date FROM climate.{table_name}")
        min_date = date_range_result['min_date'].iloc[0]
        max_date = date_range_result['max_date'].iloc[0]
        logger.info(f"Date range: {min_date} to {max_date}")
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")

if __name__ == "__main__":
    main()