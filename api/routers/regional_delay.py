"""
Regional Delay Router

FastAPI router for regional bus delay predictions and analysis.
"""

from fastapi import APIRouter, HTTPException, status, Query
from typing import Optional, List
import logging
from datetime import datetime

from ..models import (
    RegionalPredictionRequest,
    RegionalPredictionResponse,
    AllRegionsResponse,
    RankingResponse,
    RegionsListResponse,
    RegionInfo,
    ErrorResponse
)
from ..regional_delay_api import RegionalDelayPredictionAPI

logger = logging.getLogger(__name__)

router = APIRouter()

# Global API instance (lazy initialization)
_api_instance: Optional[RegionalDelayPredictionAPI] = None


def get_api_instance():
    """Get or create RegionalDelayPredictionAPI instance."""
    global _api_instance
    if _api_instance is None:
        try:
            _api_instance = RegionalDelayPredictionAPI()
            logger.info("RegionalDelayPredictionAPI initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize RegionalDelayPredictionAPI: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to initialize regional service: {str(e)}"
            )
    return _api_instance


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

        api = get_api_instance()
        result = api.predict_regional_delay(
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
async def get_all_regions_status(
    forecast_hours: int = Query(1, ge=1, le=12)
):
    """
    Get current status for all regions.

    Returns delay status for all Metro Vancouver municipalities.
    """
    try:
        logger.info("Fetching status for all regions")

        api = get_api_instance()
        result = api.get_all_regions_status(forecast_hours=forecast_hours)

        logger.info(f"Retrieved status for {result['total_regions']} regions")

        return result

    except Exception as e:
        logger.error(f"Failed to fetch all regions status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch status: {str(e)}"
        )


@router.get(
    "/ranking",
    response_model=RankingResponse,
    status_code=status.HTTP_200_OK,
    summary="Get regional performance ranking",
    description="""
    Get performance ranking for all Metro Vancouver regions.

    Ranks regions by on-time performance and average delay.

    **Returns:**
    - Performance rank (1 = best)
    - On-time rate percentage
    - Average and median delay
    - Performance grade (A-F)
    - Number of routes, stops, and trips
    """
)
async def get_regional_ranking():
    """
    Get regional performance ranking.

    Ranks all regions by delay performance.
    """
    try:
        logger.info("Fetching regional performance ranking")

        api = get_api_instance()
        result = api.get_regional_ranking()

        logger.info(f"Retrieved ranking for {len(result['rankings'])} regions")

        return result

    except Exception as e:
        logger.error(f"Failed to fetch ranking: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch ranking: {str(e)}"
        )


@router.get(
    "/regions",
    response_model=RegionsListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all available regions",
    description="""
    Get list of all available Metro Vancouver regions.

    **Returns:**
    - Region ID and name
    - Region type (municipality, electoral area, etc.)
    - Geographic center coordinates
    - Area and population
    """
)
async def list_regions():
    """
    List all available regions.

    Returns information about all Metro Vancouver municipalities.
    """
    try:
        logger.info("Fetching regions list")

        api = get_api_instance()
        regions = api.region_manager.list_all_regions()

        result = {
            "total_regions": len(regions),
            "regions": regions
        }

        logger.info(f"Retrieved {len(regions)} regions")

        return result

    except Exception as e:
        logger.error(f"Failed to fetch regions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch regions: {str(e)}"
        )


@router.get(
    "/regions/{region_id}",
    response_model=RegionInfo,
    status_code=status.HTTP_200_OK,
    summary="Get region information",
    description="Get detailed information for a specific region",
    responses={
        200: {"description": "Region information"},
        404: {"model": ErrorResponse, "description": "Region not found"}
    }
)
async def get_region_info(region_id: str):
    """
    Get information for a specific region.

    Returns detailed information about the region.
    """
    try:
        logger.info(f"Fetching info for region {region_id}")

        api = get_api_instance()
        region = api.region_manager.get_region_info(region_id)

        if region is None:
            available = [r['region_id'] for r in api.region_manager.list_all_regions()]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Region '{region_id}' not found. Available regions: {available[:10]}..."
            )

        logger.info(f"Retrieved info for region {region_id}")

        return region

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch region info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch region info: {str(e)}"
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
        api = get_api_instance()
        db_ok = api.db_connector.test_connection()

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