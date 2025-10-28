"""
Regional Delay Controller - API endpoints for regional delay predictions

This is the Controller layer that handles HTTP requests and responses.
Business logic is delegated to the Service layer.
"""

from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional
import logging

from ..models import (
    RegionalPredictionResponse,
    AllRegionsResponse,
    ErrorResponse
)
from ..database_connector import DatabaseConnector
from ..repositories import RegionalDelayRepository
from ..services import RegionalDelayService, DelayPredictService

logger = logging.getLogger(__name__)

router = APIRouter()

# Global service instances (lazy initialization)
_db_connector: Optional[DatabaseConnector] = None
_regional_delay_service: Optional[RegionalDelayService] = None
_delay_predict_service: Optional[DelayPredictService] = None


def _initialize_services():
    """Initialize service instances"""
    global _db_connector, _regional_delay_service, _delay_predict_service

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

    if _regional_delay_service is None:
        regional_delay_repository = RegionalDelayRepository(_db_connector)
        _regional_delay_service = RegionalDelayService(
            regional_delay_repository
        )
        logger.info("RegionalDelayService initialized successfully")

    if _delay_predict_service is None:
        delay_predict_repository = RegionalDelayRepository(_db_connector)
        _delay_predict_service = DelayPredictService(
            delay_predict_repository
        )
        logger.info("DelayPredictService initialized successfully")

def get_regional_delay_service() -> RegionalDelayService:
    """Get RegionalDelayService instance"""
    _initialize_services()
    return _regional_delay_service

def get_delay_predict_service() -> DelayPredictService:
    """Get DelayPredictService instance"""
    _initialize_services()
    return _delay_predict_service

# ==========================================
# Endpoints
# ==========================================

# @router.get(
#     "/predict/{region_id}",
#     response_model=RegionalPredictionResponse,
#     status_code=status.HTTP_200_OK,
#     summary="Get regional delay predictions per stop",
#     description="""
#     Get latest batch-predicted bus delays for all stops in a region.

#     **How it works:**
#     - Fetches latest predictions from batch processing job
#     - Batch job runs periodically using ConvLSTM model
#     - Returns predictions per stop with route and location information
#     - Forecasts available for next 1-3 hours

#     **Data source:** Pre-computed predictions from regional_delay_predictions table
#     """,
#     responses={
#         200: {"description": "Latest predictions with per-stop forecasts"},
#         404: {"model": ErrorResponse, "description": "Region not found or no predictions available"},
#         500: {"model": ErrorResponse, "description": "Internal server error"}
#     }
# )
# async def predict_regional_delay_get(
#     region_id: str,
#     forecast_hours: int = Query(
#         3,
#         ge=1,
#         le=3,
#         description="Number of hours to forecast (1-3)"
#     )
# ):
#     """
#     Get latest batch-predicted regional delays per stop.

#     Fetches pre-computed predictions from the batch processing job.
#     Predictions are updated periodically by the regional delay prediction batch job.

#     Args:
#         region_id: Region identifier (e.g., 'vancouver', 'burnaby')
#         forecast_hours: Number of hours to forecast (default: 3)

#     Returns:
#         Per-stop predictions with route, location, and hourly delay forecasts
#     """
#     try:
#         logger.info(f"Fetching predictions for region '{region_id}' for next {forecast_hours} hours")

#         service = get_delay_predict_service()
#         result = await service.predict_regional_delay(
#             region_id=region_id,
#             forecast_hours=forecast_hours
#         )

#         logger.info(f"Successfully fetched predictions for {result['total_stops']} stops")

#         return result

#     except Exception as e:
#         logger.error(f"Failed to fetch regional predictions: {e}", exc_info=True)
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to fetch predictions: {str(e)}"
#         )


@router.get(
    "/status",
    response_model=AllRegionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get all regions status",
    description="""
    Get current delay status for all Metro Vancouver regions.

    Returns the latest delay information for all 23 municipalities.

    **Returns:**
    - Current delay status for each region
    - Average delay in minutes
    - Number of trips
    - Last update timestamp
    """
)
async def get_all_regions_status():
    """
    Get current status for all regions.

    Returns delay status for all Metro Vancouver municipalities.
    """
    try:
        logger.info("Fetching status for all regions")

        service = get_regional_delay_service()
        result = service.get_all_regions_status()

        # logger.info(f"Retrieved status for {result['total_regions']} regions")

        return result

    except Exception as e:
        logger.error(f"Failed to fetch all regions status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch status: {str(e)}"
        )