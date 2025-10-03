"""
FastAPI Application for GTFS Bus Delay Prediction

Vancouver transit bus delay prediction API using ConvLSTM models.
Provides both single-route predictions and regional delay aggregations.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
from datetime import datetime
import os
import pytz

# Set timezone to Vancouver
VANCOUVER_TZ = pytz.timezone('America/Vancouver')
os.environ['TZ'] = 'America/Vancouver'

# Import routers
from .routers import delay_prediction, regional_delay

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="GTFS Bus Delay Prediction API",
    description="""
    ## Vancouver Transit Bus Delay Prediction System

    This API provides real-time bus delay predictions for Vancouver transit using:
    - **Machine Learning**: Bidirectional ConvLSTM models
    - **Weather Integration**: Real-time weather data correlation
    - **Regional Analysis**: 23 Metro Vancouver municipalities

    ### Features
    - Single route 3-hour delay forecasts
    - Regional delay aggregations and predictions
    - Performance rankings across regions
    - Historical trend analysis

    ### Data Sources
    - GTFS Realtime feed data
    - Environment Canada weather data
    - Metro Vancouver regional boundaries

    ### Example Usage

    **Single Route Prediction:**
    ```python
    import requests

    response = requests.post(
        "http://localhost:8000/api/v1/predictions/route",
        json={
            "route_id": "6618",
            "direction_id": 0,
            "lookback_days": 7
        }
    )
    print(response.json())
    ```

    **Regional Prediction:**
    ```python
    response = requests.get(
        "http://localhost:8000/api/v1/regional/predict/vancouver?forecast_hours=3"
    )
    print(response.json())
    ```
    """,
    version="2.0.0",
    contact={
        "name": "GTFS Analysis Team",
        "email": "gtfs@example.com"
    },
    license_info={
        "name": "MIT License"
    }
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(
    delay_prediction.router,
    prefix="/api/v1/predictions",
    tags=["Delay Predictions"]
)

app.include_router(
    regional_delay.router,
    prefix="/api/v1/regional",
    tags=["Regional Analysis"]
)


@app.get("/", tags=["Root"])
async def root():
    """API root endpoint with service information."""
    return {
        "service": "GTFS Bus Delay Prediction API",
        "version": "2.0.0",
        "status": "operational",
        "timezone": "America/Vancouver",
        "timestamp": datetime.now(VANCOUVER_TZ).isoformat(),
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
            "health": "/health"
        },
        "api_v1": {
            "predictions": {
                "route_prediction": "POST /api/v1/predictions/route",
                "route_prediction_get": "GET /api/v1/predictions/route/{route_id}",
                "health": "GET /api/v1/predictions/health"
            },
            "regional": {
                "regional_prediction": "POST /api/v1/regional/predict",
                "regional_prediction_get": "GET /api/v1/regional/predict/{region_id}",
                "all_regions_status": "GET /api/v1/regional/status",
                "ranking": "GET /api/v1/regional/ranking",
                "list_regions": "GET /api/v1/regional/regions",
                "region_info": "GET /api/v1/regional/regions/{region_id}",
                "health": "GET /api/v1/regional/health"
            }
        }
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    try:
        return {
            "status": "healthy",
            "timezone": "America/Vancouver",
            "timestamp": datetime.now(VANCOUVER_TZ).isoformat(),
            "service": "gtfs-delay-prediction-api",
            "version": "2.0.0",
            "components": {
                "predictions": "Check /api/v1/predictions/health",
                "regional": "Check /api/v1/regional/health"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unavailable")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "timestamp": datetime.now(VANCOUVER_TZ).isoformat()
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
