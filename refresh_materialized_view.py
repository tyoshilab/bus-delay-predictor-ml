#!/usr/bin/env python3
"""
Script to refresh materialized views in the database.
"""

from sqlalchemy import text
import logging
from config.database import engine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting materialized views refresh...")
    
    # Show summary statistics
    with engine.connect() as conn:
        try:
            conn.execute(text(f"call refresh_gtfs_views()"))
            logger.info("Materialized views refreshed successfully.")

        except Exception as e:
            logger.error(f"Error getting statistics: {e}")

if __name__ == "__main__":
    main()