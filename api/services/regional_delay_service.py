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
    """Regional delay prediction business logic"""

    def __init__(
        self,
        regional_delay_repository: RegionalDelayRepository
    ):
        self.delay_repository = regional_delay_repository

    def predict_regional_delay(
        self,
        region_id: str,
        forecast_hours: int = 3,
        lookback_days: int = 7
    ) -> Dict:
        """
        Predict regional delays

        Args:
            region_id: Region identifier
            forecast_hours: Number of hours to forecast
            lookback_days: Number of days of historical data to use

        Returns:
            Prediction results with forecasts and summary

        Raises:
            ValueError: If region not found or no data available
        """
        # Validate region exists
        region = self.region_service.get_region_by_id(region_id)
        if not region:
            available = self.region_service.get_available_region_ids()
            raise ValueError(
                f"Unknown region: {region_id}. Available regions: {available}"
            )

        # Get historical delay statistics
        lookback_hours = lookback_days * 24
        delay_stats = self.delay_repository.find_delay_stats(
            region_id,
            lookback_hours=lookback_hours
        )

        if delay_stats.empty:
            return {
                "region_id": region_id,
                "region_name": region['region_name'],
                "error": "No data available for this region",
                "predictions": []
            }

        # Generate predictions
        predictions = self._generate_predictions(
            delay_stats,
            forecast_hours
        )

        return {
            "region_id": region_id,
            "region_name": region['region_name'],
            "region_type": region.get('region_type'),
            "current_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "lookback_period_days": lookback_days,
            "predictions": predictions,
            "summary": self._calculate_summary(predictions)
        }

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

    def _generate_predictions(
        self,
        delay_stats: pd.DataFrame,
        forecast_hours: int
    ) -> List[Dict]:
        """
        Generate predictions based on historical patterns

        Args:
            delay_stats: Historical delay statistics
            forecast_hours: Number of hours to forecast

        Returns:
            List of prediction dictionaries
        """
        current_time = datetime.now()
        predictions = []

        for hour_offset in range(1, forecast_hours + 1):
            forecast_time = current_time + timedelta(hours=hour_offset)
            forecast_hour = forecast_time.hour
            forecast_dow = forecast_time.weekday()

            # Filter similar time periods
            similar_periods = delay_stats[
                delay_stats['hour_of_day'] == forecast_hour
            ]

            if not similar_periods.empty:
                avg_delay = similar_periods['avg_delay_minutes'].mean()
                median_delay = similar_periods['median_delay_minutes'].median()

                # Calculate probability of >5 min delay
                total_trips = similar_periods['trip_count'].sum()
                delay_5min = (
                    similar_periods['delay_5_to_10min'].sum() +
                    similar_periods['delay_over_10min'].sum()
                )
                delay_5min_prob = (delay_5min / total_trips * 100) if total_trips > 0 else 0
            else:
                # Use overall average if no similar periods
                avg_delay = delay_stats['avg_delay_minutes'].mean()
                median_delay = delay_stats['median_delay_minutes'].median()
                delay_5min_prob = 0

            predictions.append({
                "forecast_time": forecast_time.strftime("%Y-%m-%d %H:%M:%S"),
                "hour_of_day": forecast_hour,
                "day_of_week": forecast_dow,
                "avg_delay_minutes": round(float(avg_delay), 2),
                "median_delay_minutes": round(float(median_delay), 2),
                "probability_delay_over_5min": round(float(delay_5min_prob), 1),
                "status": self._classify_delay_status(avg_delay)
            })

        return predictions

    def _calculate_summary(self, predictions: List[Dict]) -> Dict:
        """
        Calculate summary statistics from predictions

        Args:
            predictions: List of prediction dictionaries

        Returns:
            Summary statistics dictionary
        """
        avg_delays = [p['avg_delay_minutes'] for p in predictions]
        avg_delay_next_3h = np.mean(avg_delays)

        return {
            "avg_delay_next_3h": round(float(avg_delay_next_3h), 2),
            "overall_status": self._classify_delay_status(avg_delay_next_3h)
        }

    @staticmethod
    def _classify_delay_status(avg_delay_minutes: float) -> str:
        """
        Classify delay status based on average delay

        Args:
            avg_delay_minutes: Average delay in minutes

        Returns:
            Status string: excellent, good, moderate, poor, or severe
        """
        if avg_delay_minutes < 1:
            return "excellent"
        elif avg_delay_minutes < 3:
            return "good"
        elif avg_delay_minutes < 5:
            return "moderate"
        elif avg_delay_minutes < 10:
            return "poor"
        else:
            return "severe"

    @staticmethod
    def _create_no_data_status(region: Dict) -> Dict:
        """Create status dictionary for regions with no data"""
        return {
            "region_id": region['region_id'],
            "region_name": region['region_name'],
            "region_type": region.get('region_type'),
            "status": "no_data",
            "avg_delay_minutes": None,
            "last_updated": None,
            "trip_count": 0,
            "center_lat": None,
            "center_lon": None
        }

    @staticmethod
    def _create_error_status(region: Dict) -> Dict:
        """Create status dictionary for regions with errors"""
        return {
            "region_id": region['region_id'],
            "region_name": region['region_name'],
            "region_type": region.get('region_type'),
            "status": "error",
            "avg_delay_minutes": None,
            "last_updated": None,
            "trip_count": 0,
            "center_lat": None,
            "center_lon": None
        }
