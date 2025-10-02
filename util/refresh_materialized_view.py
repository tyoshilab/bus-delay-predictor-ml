#!/usr/bin/env python3
"""
Script to refresh materialized views in the database.
"""

import logging
from src.data_connection import DatabaseConnector

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting materialized views refresh...")
    db_connector = DatabaseConnector()
    # Show summary statistics
    with db_connector.get_connection() as conn:
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("call gtfs_realtime.refresh_gtfs_views()")
            logger.info("Materialized views refreshed successfully.")

        except Exception as e:
            logger.error(f"Error refreshing views: {e}")

if __name__ == "__main__":
    main()