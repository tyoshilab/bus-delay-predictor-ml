"""
Regional Delay Service - Business logic for regional delay predictions
"""

from typing import Dict, List
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import logging

from ..repositories.regional_delay_repository import RegionalDelayRepository

logger = logging.getLogger(__name__)

class RegionalDelayService:
    """Regional delay status business logic"""

    def __init__(
        self,
        regional_delay_repository: RegionalDelayRepository
    ):
        self.delay_repository = regional_delay_repository

    def get_all_regions_status(self) -> Dict:
        """
        Get status for all regions

        Args:
            forecast_hours: Number of hours to forecast (currently not used)

        Returns:
            Status information for all regions
        """
        try:
            recent_status = self.delay_repository.find_recent_status()

            # Filter out rows with NULL region_id
            recent_status = recent_status.dropna(subset=['region_id'])
            
            logger.info(f"Retrieved status for {len(recent_status)} regions")

            return {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_regions": len(recent_status),
                "regions": recent_status.to_dict('records')
            }
        
        except Exception as e:
            logger.error(f"Error getting status for region: {e}")
            return {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_regions": 0,
                "regions": [],
                "error": str(e)
            }
