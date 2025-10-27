"""
Pydantic models for API request/response validation
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime


# ==========================================
# Request Models
# ==========================================

class RoutePredictionRequest(BaseModel):
    """Request model for single route delay prediction."""
    route_id: str = Field(..., description="Route ID (e.g., '6618')")
    direction_id: int = Field(0, ge=0, le=1, description="Direction ID (0 or 1)")
    lookback_days: int = Field(7, ge=1, le=30, description="Days of historical data to use")

    class Config:
        schema_extra = {
            "example": {
                "route_id": "6618",
                "direction_id": 0,
                "lookback_days": 7
            }
        }


class RegionalPredictionRequest(BaseModel):
    """Request model for regional delay prediction."""
    region_id: str = Field(..., description="Region ID (e.g., 'vancouver', 'burnaby')")
    forecast_hours: int = Field(3, ge=1, le=12, description="Hours to forecast")
    lookback_days: int = Field(7, ge=1, le=30, description="Days of historical data to use")

    class Config:
        schema_extra = {
            "example": {
                "region_id": "vancouver",
                "forecast_hours": 3,
                "lookback_days": 7
            }
        }


# ==========================================
# Response Models
# ==========================================

class DelayPrediction(BaseModel):
    """Individual delay prediction for a time slot."""
    time: str = Field(..., description="Prediction timestamp")
    delay_seconds: float = Field(..., description="Predicted delay in seconds")
    delay_minutes: float = Field(..., description="Predicted delay in minutes")

    class Config:
        schema_extra = {
            "example": {
                "time": "2025-10-01 14:00:00",
                "delay_seconds": 120.5,
                "delay_minutes": 2.01
            }
        }


class RoutePredictionResponse(BaseModel):
    """Response model for route delay prediction."""
    route_id: str = Field(..., description="Route ID")
    direction_id: int = Field(..., description="Direction ID")
    current_time: str = Field(..., description="Current timestamp")
    latest_data_time: str = Field(..., description="Latest data timestamp")
    predictions: List[DelayPrediction] = Field(..., description="List of predictions")

    class Config:
        schema_extra = {
            "example": {
                "route_id": "6618",
                "direction_id": 0,
                "current_time": "2025-10-01 13:00:00",
                "latest_data_time": "2025-10-01 12:00:00",
                "predictions": [
                    {
                        "time": "2025-10-01 14:00:00",
                        "delay_seconds": 120.5,
                        "delay_minutes": 2.01
                    }
                ]
            }
        }


class StopPrediction(BaseModel):
    """Prediction for a single stop."""
    stop_id: str = Field(..., description="Stop ID")
    stop_name: Optional[str] = Field(None, description="Stop name")
    stop_lat: Optional[float] = Field(None, description="Stop latitude")
    stop_lon: Optional[float] = Field(None, description="Stop longitude")
    route_id: str = Field(..., description="Route ID")
    direction_id: int = Field(..., description="Direction ID")
    hour_predictions: List[DelayPrediction] = Field(..., description="Hourly predictions for next 3 hours")

    class Config:
        schema_extra = {
            "example": {
                "stop_id": "12345",
                "stop_name": "Main St @ 1st Ave",
                "stop_lat": 49.2827,
                "stop_lon": -123.1207,
                "route_id": "6618",
                "direction_id": 0,
                "hour_predictions": [
                    {"time": "2025-10-01 14:00:00", "delay_seconds": 120.5, "delay_minutes": 2.01},
                    {"time": "2025-10-01 15:00:00", "delay_seconds": 135.0, "delay_minutes": 2.25},
                    {"time": "2025-10-01 16:00:00", "delay_seconds": 150.0, "delay_minutes": 2.50}
                ]
            }
        }


class RegionalPredictionResponse(BaseModel):
    """Response model for regional delay prediction."""
    region_id: str = Field(..., description="Region ID")
    current_time: str = Field(..., description="Current timestamp")
    forecast_hours: int = Field(..., description="Number of forecast hours")
    total_stops: int = Field(..., description="Total number of stops with predictions")
    predictions: List[StopPrediction] = Field(..., description="Per-stop predictions")

    class Config:
        schema_extra = {
            "example": {
                "region_id": "vancouver",
                "current_time": "2025-10-01 13:00:00",
                "forecast_hours": 3,
                "total_stops": 150,
                "predictions": [
                    {
                        "stop_id": "12345",
                        "stop_name": "Main St @ 1st Ave",
                        "stop_lat": 49.2827,
                        "stop_lon": -123.1207,
                        "route_id": "6618",
                        "direction_id": 0,
                        "hour_predictions": [
                            {"time": "2025-10-01 14:00:00", "delay_seconds": 120.5, "delay_minutes": 2.01}
                        ]
                    }
                ]
            }
        }


class RegionStatus(BaseModel):
    """Status for a single region."""
    region_id: str = Field(..., description="Region ID")
    center_lat: Optional[float] = Field(None, description="Center latitude")
    center_lon: Optional[float] = Field(None, description="Center longitude")
    avg_delay_minutes: Optional[float] = Field(None, description="Average delay in minutes")


class AllRegionsResponse(BaseModel):
    """Response model for all regions status."""
    timestamp: str = Field(..., description="Response timestamp")
    total_regions: int = Field(..., description="Total number of regions")
    regions: List[RegionStatus] = Field(..., description="List of region statuses")


class RegionRanking(BaseModel):
    """Regional performance ranking."""
    region_id: str = Field(..., description="Region ID")
    region_name: str = Field(..., description="Region name")
    region_type: Optional[str] = Field(None, description="Region type")
    avg_delay_minutes: float = Field(..., description="Average delay in minutes")
    median_delay_minutes: float = Field(..., description="Median delay in minutes")
    ontime_rate_pct_7d: float = Field(..., description="On-time rate % (last 7 days)")
    performance_rank: int = Field(..., description="Performance rank")
    ontime_rank: int = Field(..., description="On-time rank")
    performance_grade: str = Field(..., description="Performance grade")
    active_routes: int = Field(..., description="Number of active routes")
    active_stops: int = Field(..., description="Number of active stops")
    total_trips: int = Field(..., description="Total trips")


class RankingResponse(BaseModel):
    """Response model for regional ranking."""
    timestamp: str = Field(..., description="Response timestamp")
    period: str = Field(..., description="Analysis period")
    rankings: List[RegionRanking] = Field(..., description="Regional rankings")


class RegionInfo(BaseModel):
    """Region information."""
    region_id: str = Field(..., description="Region ID")
    region_name: str = Field(..., description="Region name")
    region_type: Optional[str] = Field(None, description="Region type")
    center_lat: Optional[float] = Field(None, description="Center latitude")
    center_lon: Optional[float] = Field(None, description="Center longitude")
    area_km2: Optional[float] = Field(None, description="Area in km²")
    population: Optional[int] = Field(None, description="Population")


class RegionsListResponse(BaseModel):
    """Response model for regions list."""
    total_regions: int = Field(..., description="Total number of regions")
    regions: List[RegionInfo] = Field(..., description="List of regions")


# ==========================================
# Error Response Models
# ==========================================

# ==========================================
# Stop Prediction Models
# ==========================================

class StopArrivalPrediction(BaseModel):
    """Arrival time and prediction for a stop."""
    route_id: str = Field(..., description="Route ID")
    trip_id: str = Field(..., description="Trip ID")
    trip_headsign: Optional[str] = Field(None, description="Trip headsign")
    direction_id: int = Field(..., description="Direction ID")
    stop_sequence: Optional[int] = Field(None, description="Stop sequence in route")
    arrival_time: str = Field(..., description="Scheduled arrival time")
    prediction_target_time: Optional[str] = Field(None, description="Prediction target time")
    predicted_delay_seconds: Optional[float] = Field(None, description="Predicted delay in seconds")
    service_id: Optional[str] = Field(None, description="Service ID")
    next_arrival_time: Optional[str] = Field(None, description="Next arrival time")

    class Config:
        schema_extra = {
            "example": {
                "route_id": "6618",
                "trip_id": "12345",
                "trip_headsign": "Downtown",
                "direction_id": 0,
                "stop_sequence": 5,
                "arrival_time": "14:30:00",
                "prediction_target_time": "2025-10-26 14:00:00-07",
                "predicted_delay_seconds": 120.5
            }
        }


class StopPredictionsResponse(BaseModel):
    """Response model for stop predictions."""
    stop_id: str = Field(..., description="Stop ID")
    current_time: str = Field(..., description="Current timestamp")
    total_arrivals: int = Field(..., description="Total number of upcoming arrivals")
    arrivals: List[StopArrivalPrediction] = Field(..., description="List of upcoming arrivals with predictions")

    class Config:
        schema_extra = {
            "example": {
                "stop_id": "12345",
                "current_time": "2025-10-26 13:00:00",
                "total_arrivals": 5,
                "arrivals": [
                    {
                        "route_id": "6618",
                        "trip_id": "12345",
                        "trip_headsign": "Downtown",
                        "direction_id": 0,
                        "stop_sequence": 5,
                        "arrival_time": "14:30:00",
                        "prediction_target_time": "2025-10-26 14:00:00-07",
                        "predicted_delay_seconds": 120.5
                    }
                ]
            }
        }


class RouteStopArrival(BaseModel):
    """Arrival and prediction for a specific route and stop."""
    route_id: str = Field(..., description="Route ID")
    trip_id: str = Field(..., description="Trip ID")
    stop_id: str = Field(..., description="Stop ID")
    direction_id: int = Field(..., description="Direction ID")
    stop_sequence: Optional[int] = Field(None, description="Stop sequence")
    trip_headsign: Optional[str] = Field(None, description="Trip headsign")
    arrival_time: str = Field(..., description="Scheduled arrival time")
    prediction_target_time: Optional[str] = Field(None, description="Prediction target time")
    predicted_delay_seconds: Optional[float] = Field(None, description="Predicted delay in seconds")

    class Config:
        schema_extra = {
            "example": {
                "route_id": "6618",
                "trip_id": "12345",
                "stop_id": "12345",
                "direction_id": 0,
                "stop_sequence": 5,
                "trip_headsign": "Downtown",
                "arrival_time": "14:30:00",
                "prediction_target_time": "2025-10-26 14:00:00-07",
                "predicted_delay_seconds": 120.5
            }
        }


class RouteStopPredictionsResponse(BaseModel):
    """Response model for route-specific stop predictions."""
    stop_id: str = Field(..., description="Stop ID")
    route_id: str = Field(..., description="Route ID")
    current_time: str = Field(..., description="Current timestamp")
    total_arrivals: int = Field(..., description="Total number of upcoming arrivals")
    arrivals: List[RouteStopArrival] = Field(..., description="List of upcoming arrivals with predictions")

    class Config:
        schema_extra = {
            "example": {
                "stop_id": "12345",
                "route_id": "6618",
                "current_time": "2025-10-26 13:00:00",
                "total_arrivals": 3,
                "arrivals": [
                    {
                        "route_id": "6618",
                        "trip_id": "12345",
                        "stop_id": "12345",
                        "direction_id": 0,
                        "stop_sequence": 5,
                        "trip_headsign": "Downtown",
                        "arrival_time": "14:30:00",
                        "prediction_target_time": "2025-10-26 14:00:00-07",
                        "predicted_delay_seconds": 120.5
                    }
                ]
            }
        }


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    timestamp: str = Field(..., description="Error timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")

    class Config:
        schema_extra = {
            "example": {
                "error": "ValidationError",
                "message": "Invalid route_id format",
                "timestamp": "2025-10-01T13:00:00",
                "details": {"route_id": "Route not found in database"}
            }
        }