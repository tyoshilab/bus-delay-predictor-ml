"""
Regional Delay Controller - API endpoints for regional delay predictions

This is the Controller layer that handles HTTP requests and responses.
Business logic is delegated to the Service layer.
"""

from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional
import logging
from datetime import datetime

from ..models import (
    RegionalPredictionRequest,
    RegionalPredictionResponse,
    AllRegionsResponse,
    ErrorResponse
)
from ..database_connector import DatabaseConnector
from ..repositories import RegionalDelayRepository
from ..services import RegionalDelayService

logger = logging.getLogger(__name__)

router = APIRouter()

# Global service instances (lazy initialization)
_db_connector: Optional[DatabaseConnector] = None
_regional_delay_service: Optional[RegionalDelayService] = None


def _initialize_services():
    """Initialize service instances"""
    global _db_connector, _regional_delay_service

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

def get_regional_delay_service() -> RegionalDelayService:
    """Get RegionalDelayService instance"""
    _initialize_services()
    return _regional_delay_service


# ==========================================
# Endpoints
# ==========================================

@router.post(
    "/predict",
    response_model=RegionalPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict regional delays",
    description="""
    Predict bus delays for a specific Metro Vancouver region.

    Uses historical patterns from the same time of day and week.

    **Parameters:**
    - **region_id**: Region identifier (e.g., 'vancouver', 'burnaby')
    - **forecast_hours**: Hours to forecast (1-12, default: 3)
    - **lookback_days**: Days of historical data (1-30, default: 7)

    **Returns:**
    - Hourly forecasts for the specified period
    - Summary statistics and delay status
    """,
    responses={
        200: {"description": "Successful prediction"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Region not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def predict_regional_delay(request: RegionalPredictionRequest):
    """
    Predict delays for a specific region.

    Returns hourly forecasts based on historical patterns.
    """
    try:
        logger.info(
            f"Predicting regional delay for {request.region_id}, "
            f"{request.forecast_hours} hours"
        )

        service = get_regional_delay_service()
        result = service.predict_regional_delay(
            region_id=request.region_id,
            forecast_hours=request.forecast_hours,
            lookback_days=request.lookback_days
        )

        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result["error"]
            )

        logger.info(
            f"Prediction successful for region {request.region_id}: "
            f"{len(result['predictions'])} timesteps"
        )

        return result

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Regional prediction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


@router.get(
    "/predict/{region_id}",
    response_model=RegionalPredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict regional delays (GET method)",
    description="Predict bus delays for a region using GET method",
    responses={
        200: {"description": "Successful prediction"},
        404: {"model": ErrorResponse, "description": "Region not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def predict_regional_delay_get(
    region_id: str,
    forecast_hours: int = Query(3, ge=1, le=12),
    lookback_days: int = Query(7, ge=1, le=30)
):
    """
    Predict regional delays using GET method.

    Simpler endpoint for GET requests.
    """
    request = RegionalPredictionRequest(
        region_id=region_id,
        forecast_hours=forecast_hours,
        lookback_days=lookback_days
    )
    return await predict_regional_delay(request)


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

@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check for regional service",
    description="Check if the regional delay service is operational"
)
async def regional_health_check():
    """
    Health check for regional delay service.

    Verifies database connectivity and service status.
    """
    try:
        _initialize_services()
        db_ok = _db_connector.test_connection()

        return {
            "status": "healthy" if db_ok else "degraded",
            "service": "regional-delay",
            "database_connected": db_ok,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Regional service is not healthy"
        )