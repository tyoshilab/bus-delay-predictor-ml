"""
Delay Predict Service - Fetch and transform batch prediction results
"""

import logging
from typing import Dict, List
from datetime import datetime
import pandas as pd

from ..repositories.regional_delay_repository import RegionalDelayRepository

logger = logging.getLogger(__name__)


class DelayPredictService:
    """Regional delay prediction business logic"""

    def __init__(
        self,
        regional_delay_repository: RegionalDelayRepository
    ):
        self.delay_repository = regional_delay_repository
        logger.info("DelayPredictService initialized (batch data mode)")

    async def predict_regional_delay(
        self,
        region_id: str,
        forecast_hours: int = 3
    ) -> Dict:
        """
        Get predictions for specific regions

        Args:
            region_id: Region ID
            forecast_hours: Number of forecast hours (1-3)

        Returns:
            Stop-level prediction data
        """
        # Get the latest prediction data created by the batch job
        predictions_df = self.delay_repository.find_latest_predictions(
            region_id, forecast_hours
        )

        if predictions_df is None or predictions_df.empty:
            logger.warning(f"No predictions found for region: {region_id}")
            return {
                "region_id": region_id,
                "current_time": datetime.now().isoformat(),
                "forecast_hours": forecast_hours,
                "total_stops": 0,
                "predictions": []
            }

        # Group and transform the data by stop
        predictions = self._transform_to_stop_predictions(predictions_df)

        # Get the maximum value of prediction_created_at (latest batch execution time)
        latest_batch_time = predictions_df['prediction_created_at'].max()

        return {
            "region_id": region_id,
            "current_time": latest_batch_time.isoformat() if pd.notna(latest_batch_time) else datetime.now().isoformat(),
            "forecast_hours": forecast_hours,
            "total_stops": len(predictions),
            "predictions": predictions
        }

    def _transform_to_stop_predictions(
        self,
        predictions_df: pd.DataFrame
    ) -> List[Dict]:
        """
        Transform prediction data to stop-level format

        Args:
            predictions_df: DataFrame of prediction data

        Returns:
            List of stop-level predictions
        """
        # Group by route_id, direction_id, stop_id
        grouped = predictions_df.groupby(
            ['route_id', 'direction_id', 'stop_id'],
            as_index=False
        )

        stop_predictions = []

        for (route_id, direction_id, stop_id), group in grouped:
            first_row = group.iloc[0]

            group_sorted = group.sort_values('prediction_hour_offset')

            hour_predictions = []
            for _, row in group_sorted.iterrows():
                hour_predictions.append({
                    "time": row['prediction_target_time'].strftime("%Y-%m-%d %H:%M:%S")
                    if pd.notna(row['prediction_target_time']) else None,
                    "delay_seconds": float(row['predicted_delay_seconds'])
                    if pd.notna(row['predicted_delay_seconds']) else 0.0,
                    "delay_minutes": float(row['predicted_delay_minutes'])
                    if pd.notna(row['predicted_delay_minutes']) else 0.0
                })

            stop_predictions.append({
                "stop_id": str(stop_id),
                "stop_name": first_row['stop_name']
                if pd.notna(first_row.get('stop_name')) else None,
                "stop_lat": float(first_row['stop_lat'])
                if pd.notna(first_row.get('stop_lat')) else None,
                "stop_lon": float(first_row['stop_lon'])
                if pd.notna(first_row.get('stop_lon')) else None,
                "route_id": str(route_id),
                "direction_id": int(direction_id),
                "hour_predictions": hour_predictions
            })

        logger.info(f"Transformed {len(stop_predictions)} stop predictions")
        return stop_predictions