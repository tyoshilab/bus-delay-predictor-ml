"""
Delay Prediction Router

FastAPI router for single-route bus delay predictions.
"""

from fastapi import APIRouter, HTTPException, status
from typing import Optional
import logging
from datetime import datetime

from ..models import (
    RoutePredictionRequest,
    RoutePredictionResponse,
    ErrorResponse
)
from ..predict_delay_api import DelayPredictionAPI, predict_route_delay

logger = logging.getLogger(__name__)

router = APIRouter()

# Global API instance (lazy initialization)
_api_instance: Optional[DelayPredictionAPI] = None


def get_api_instance():
    """Get or create DelayPredictionAPI instance."""
    global _api_instance
    if _api_instance is None:
        try:
            _api_instance = DelayPredictionAPI(
                model_path='files/model/best_delay_model.h5'
            )
            logger.info("DelayPredictionAPI initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DelayPredictionAPI: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to initialize prediction service: {str(e)}"
            )
    return _api_instance


@router.post(
    "/route",
    response_model=RoutePredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict delay for a specific route",
    description="""
    Predict bus arrival delays for the next 3 hours for a specific route and direction.

    Uses a trained ConvLSTM model with weather data integration.

    **Parameters:**
    - **route_id**: GTFS route ID (e.g., '6618')
    - **direction_id**: Direction (0 or 1)
    - **lookback_days**: Days of historical data to use (default: 7)

    **Returns:**
    - Predictions for next 3 hours (hourly intervals)
    - Each prediction includes delay in seconds and minutes
    """,
    responses={
        200: {"description": "Successful prediction"},
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Route or data not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "Service unavailable"}
    }
)
async def predict_route_delay_endpoint(request: RoutePredictionRequest):
    """
    Predict delay for a specific route and direction.

    Returns delay predictions for the next 3 hours.
    """
    try:
        logger.info(
            f"Predicting delay for route {request.route_id}, "
            f"direction {request.direction_id}"
        )

        # Get prediction using the standalone function
        result = predict_route_delay(
            route_id=request.route_id,
            direction_id=request.direction_id,
            model_path='files/model/best_delay_model.h5',
            lookback_days=request.lookback_days
        )

        logger.info(
            f"Prediction successful for route {request.route_id}: "
            f"{len(result['predictions'])} timesteps"
        )

        return result

    except ValueError as e:
        logger.warning(f"Validation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Prediction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


@router.get(
    "/route/{route_id}",
    response_model=RoutePredictionResponse,
    status_code=status.HTTP_200_OK,
    summary="Predict delay for a route (GET method)",
    description="""
    Predict bus arrival delays using GET method.

    **Parameters:**
    - **route_id**: GTFS route ID (e.g., '6618')
    - **direction_id**: Direction (0 or 1, default: 0)
    - **lookback_days**: Days of historical data (default: 7)
    """,
    responses={
        200: {"description": "Successful prediction"},
        404: {"model": ErrorResponse, "description": "Route or data not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def predict_route_delay_get(
    route_id: str,
    direction_id: int = 0,
    lookback_days: int = 7
):
    """
    Predict delay for a specific route (GET endpoint).

    Alternative endpoint using GET method for simpler integration.
    """
    request = RoutePredictionRequest(
        route_id=route_id,
        direction_id=direction_id,
        lookback_days=lookback_days
    )
    return await predict_route_delay_endpoint(request)


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check for prediction service",
    description="Check if the prediction model and service are operational"
)
async def prediction_health_check():
    """
    Health check for the delay prediction service.

    Verifies model is loaded and service is operational.
    """
    try:
        api = get_api_instance()
        return {
            "status": "healthy",
            "service": "delay-prediction",
            "model_loaded": api.model is not None,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prediction service is not healthy"
        )