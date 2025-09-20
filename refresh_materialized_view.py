#!/usr/bin/env python3
"""
Script to refresh materialized views in the database.
"""

from sqlalchemy import text
import logging
from src.data_connection import DatabaseConnector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting materialized views refresh...")
    db_connector = DatabaseConnector()
    
    # Refresh materialized views
    try:
        with db_connector.engine.connect() as conn:
            conn.execute(text("call gtfs_realtime.refresh_gtfs_views()"))
            conn.commit()
            logger.info("Materialized views refreshed successfully.")

    except Exception as e:
        logger.error(f"Error refreshing materialized views: {e}")

if __name__ == "__main__":
    main()