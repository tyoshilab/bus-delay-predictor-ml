"""
Stop Prediction Service - Business logic for stop-level predictions

This service handles stop-level arrival predictions with delay forecasts.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
import pandas as pd
import pytz

from ..repositories.delay_prediction_repository import DelayPredictionRepository

logger = logging.getLogger(__name__)

VANCOUVER_TZ = pytz.timezone('America/Vancouver')


class StopPredictionService:
    """Service for stop-level delay predictions."""

    def __init__(self, delay_prediction_repository: DelayPredictionRepository):
        """
        Initialize StopPredictionService.

        Args:
            delay_prediction_repository: Repository for delay prediction data access
        """
        self.repository = delay_prediction_repository
        logger.info("StopPredictionService initialized")

    async def get_stop_predictions(self, stop_id: str) -> Dict[str, Any]:
        """
        Get predictions for all upcoming arrivals at a stop.

        Args:
            stop_id: Stop ID

        Returns:
            Dictionary containing stop_id, current_time, total_arrivals, and arrivals list
        """
        logger.info(f"Fetching predictions for stop: {stop_id}")

        # Get predictions from repository
        df = self.repository.find_predictions_by_stop(stop_id)

        if df is None or df.empty:
            logger.warning(f"No predictions found for stop: {stop_id}")
            return {
                "stop_id": stop_id,
                "current_time": datetime.now(VANCOUVER_TZ).isoformat(),
                "total_arrivals": 0,
                "arrivals": []
            }

        # Convert DataFrame to list of dictionaries
        arrivals = []
        for _, row in df.iterrows():
            arrival = {
                "route_id": str(row.get("route_id", "")),
                "trip_id": str(row.get("trip_id", "")),
                "trip_headsign": row.get("trip_headsign"),
                "direction_id": int(row.get("direction_id", 0)),
                "stop_sequence": int(row.get("stop_sequence")) if pd.notna(row.get("stop_sequence")) else None,
                "arrival_time": str(row.get("arrival_time", "")),
                "prediction_target_time": str(row.get("prediction_target_time")) if pd.notna(row.get("prediction_target_time")) else None,
                "predicted_delay_seconds": float(row.get("predicted_delay_seconds")) if pd.notna(row.get("predicted_delay_seconds")) else None,
                "service_id": str(row.get("service_id")) if pd.notna(row.get("service_id")) else None,
                "next_arrival_time": str(row.get("next_arrival_time")) if pd.notna(row.get("next_arrival_time")) else None
            }
            arrivals.append(arrival)

        logger.info(f"Found {len(arrivals)} upcoming arrivals for stop {stop_id}")

        return {
            "stop_id": stop_id,
            "current_time": datetime.now(VANCOUVER_TZ).isoformat(),
            "total_arrivals": len(arrivals),
            "arrivals": arrivals
        }

    async def get_route_stop_predictions(self, stop_id: str, route_id: str) -> Dict[str, Any]:
        """
        Get predictions for a specific route at a stop.

        Args:
            stop_id: Stop ID
            route_id: Route ID

        Returns:
            Dictionary containing stop_id, route_id, current_time, total_arrivals, and arrivals list
        """
        logger.info(f"Fetching predictions for stop: {stop_id}, route: {route_id}")

        # Get predictions from repository
        df = self.repository.find_arrival_time_and_predictions(stop_id, route_id)

        if df is None or df.empty:
            logger.warning(f"No predictions found for stop: {stop_id}, route: {route_id}")
            return {
                "stop_id": stop_id,
                "route_id": route_id,
                "current_time": datetime.now(VANCOUVER_TZ).isoformat(),
                "total_arrivals": 0,
                "arrivals": []
            }

        # Convert DataFrame to list of dictionaries
        arrivals = []
        for _, row in df.iterrows():
            arrival = {
                "route_id": str(row.get("route_id", "")),
                "trip_id": str(row.get("trip_id", "")),
                "stop_id": str(row.get("stop_id", "")),
                "direction_id": int(row.get("direction_id", 0)),
                "stop_sequence": int(row.get("stop_sequence")) if pd.notna(row.get("stop_sequence")) else None,
                "trip_headsign": row.get("trip_headsign"),
                "arrival_time": str(row.get("arrival_time", "")),
                "prediction_target_time": str(row.get("prediction_target_time")) if pd.notna(row.get("prediction_target_time")) else None,
                "predicted_delay_seconds": float(row.get("predicted_delay_seconds")) if pd.notna(row.get("predicted_delay_seconds")) else None
            }
            arrivals.append(arrival)

        logger.info(f"Found {len(arrivals)} upcoming arrivals for stop {stop_id}, route {route_id}")

        return {
            "stop_id": stop_id,
            "route_id": route_id,
            "current_time": datetime.now(VANCOUVER_TZ).isoformat(),
            "total_arrivals": len(arrivals),
            "arrivals": arrivals
        }
