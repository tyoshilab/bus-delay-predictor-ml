"""
Stop Prediction Controller - API endpoints for stop-level predictions

This controller handles HTTP requests for stop arrival predictions with delay forecasts.
"""

from fastapi import APIRouter, HTTPException, status, Path
from typing import Optional
import logging

from ..models import (
    StopPredictionsResponse,
    RouteStopPredictionsResponse,
    ErrorResponse
)
from ..database_connector import DatabaseConnector
from ..repositories.delay_prediction_repository import DelayPredictionRepository
from ..services import StopPredictionService

logger = logging.getLogger(__name__)

router = APIRouter()

# Global service instances (lazy initialization)
_db_connector: Optional[DatabaseConnector] = None
_stop_prediction_service: Optional[StopPredictionService] = None


def _initialize_services():
    """Initialize service instances"""
    global _db_connector, _stop_prediction_service

    if _db_connector is None:
        try:
            _db_connector = DatabaseConnector()
            logger.info("DatabaseConnector initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DatabaseConnector: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to initialize database connection: {str(e)}"
            )

    if _stop_prediction_service is None:
        delay_prediction_repository = DelayPredictionRepository(_db_connector)
        _stop_prediction_service = StopPredictionService(
            delay_prediction_repository
        )
        logger.info("StopPredictionService initialized successfully")


def get_stop_prediction_service() -> StopPredictionService:
    """Get StopPredictionService instance"""
    _initialize_services()
    return _stop_prediction_service


# ==========================================
# Endpoints
# ==========================================

@router.get(
    "/{stop_id}/predictions",
    response_model=StopPredictionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get upcoming arrivals with predictions for a stop",
    description="""
    Get all upcoming bus arrivals at a specific stop with delay predictions.

    **How it works:**
    - Fetches scheduled arrivals from GTFS static timetable
    - Joins with real-time delay predictions from the batch processing job
    - Returns next arrivals with predicted delays

    **Use case:**
    Perfect for displaying real-time arrival information at bus stops,
    showing both scheduled times and expected delays.

    **Data source:**
    - GTFS static timetable (gtfs_stop_times)
    - Regional delay predictions (regional_delay_predictions)
    """,
    responses={
        200: {"description": "Upcoming arrivals with predictions"},
        404: {"model": ErrorResponse, "description": "Stop not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_stop_predictions(
    stop_id: str = Path(..., description="Stop ID (e.g., '12345')")
):
    """
    Get upcoming arrivals with delay predictions for a stop.

    Fetches the next scheduled arrivals at this stop and joins them
    with machine learning predictions for expected delays.

    Args:
        stop_id: Stop identifier

    Returns:
        List of upcoming arrivals with route info, scheduled times, and predicted delays
    """
    try:
        logger.info(f"Fetching predictions for stop: {stop_id}")

        service = get_stop_prediction_service()
        result = await service.get_stop_predictions(stop_id)

        logger.info(f"Successfully fetched {result['total_arrivals']} arrivals for stop {stop_id}")

        return result

    except Exception as e:
        logger.error(f"Failed to fetch stop predictions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch predictions: {str(e)}"
        )


@router.get(
    "/{stop_id}/routes/{route_id}/predictions",
    response_model=RouteStopPredictionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get arrivals with predictions for a specific route at a stop",
    description="""
    Get upcoming arrivals for a specific route at a stop with delay predictions.

    **How it works:**
    - Filters arrivals by route_id
    - Fetches scheduled arrivals from GTFS static timetable
    - Joins with real-time delay predictions
    - Returns route-specific arrivals with predicted delays

    **Use case:**
    Ideal for route-specific information displays or when users
    are tracking a particular bus line at a stop.

    **Data source:**
    - GTFS static timetable (gtfs_stop_times)
    - Regional delay predictions (regional_delay_predictions)
    """,
    responses={
        200: {"description": "Route-specific arrivals with predictions"},
        404: {"model": ErrorResponse, "description": "Stop or route not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_route_stop_predictions(
    stop_id: str = Path(..., description="Stop ID (e.g., '12345')"),
    route_id: str = Path(..., description="Route ID (e.g., '6618')")
):
    """
    Get arrivals with predictions for a specific route at a stop.

    Fetches upcoming arrivals for a particular route at this stop,
    joined with machine learning predictions for expected delays.

    Args:
        stop_id: Stop identifier
        route_id: Route identifier

    Returns:
        List of route-specific arrivals with scheduled times and predicted delays
    """
    try:
        logger.info(f"Fetching predictions for stop: {stop_id}, route: {route_id}")

        service = get_stop_prediction_service()
        result = await service.get_route_stop_predictions(stop_id, route_id)

        logger.info(
            f"Successfully fetched {result['total_arrivals']} arrivals "
            f"for stop {stop_id}, route {route_id}"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to fetch route-stop predictions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch predictions: {str(e)}"
        )