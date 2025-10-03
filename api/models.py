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


class RegionalForecast(BaseModel):
    """Individual regional forecast."""
    forecast_time: str = Field(..., description="Forecast timestamp")
    hour_of_day: int = Field(..., description="Hour of day (0-23)")
    day_of_week: int = Field(..., description="Day of week (0=Monday, 6=Sunday)")
    avg_delay_minutes: float = Field(..., description="Average delay in minutes")
    median_delay_minutes: float = Field(..., description="Median delay in minutes")
    probability_delay_over_5min: float = Field(..., description="Probability of >5min delay (%)")
    status: str = Field(..., description="Delay status: excellent, good, moderate, poor, severe")


class RegionalPredictionSummary(BaseModel):
    """Summary statistics for regional prediction."""
    avg_delay_next_3h: float = Field(..., description="Average delay for next 3 hours")
    overall_status: str = Field(..., description="Overall delay status")


class RegionalPredictionResponse(BaseModel):
    """Response model for regional delay prediction."""
    region_id: str = Field(..., description="Region ID")
    region_name: str = Field(..., description="Region name")
    region_type: Optional[str] = Field(None, description="Region type")
    current_time: str = Field(..., description="Current timestamp")
    lookback_period_days: int = Field(..., description="Lookback period in days")
    predictions: List[RegionalForecast] = Field(..., description="Forecast predictions")
    summary: RegionalPredictionSummary = Field(..., description="Summary statistics")


class RegionStatus(BaseModel):
    """Status for a single region."""
    region_id: str = Field(..., description="Region ID")
    region_name: str = Field(..., description="Region name")
    region_type: Optional[str] = Field(None, description="Region type")
    status: str = Field(..., description="Current delay status")
    avg_delay_minutes: Optional[float] = Field(None, description="Average delay in minutes")
    last_updated: Optional[str] = Field(None, description="Last update timestamp")
    trip_count: int = Field(..., description="Number of trips")
    center_lat: Optional[float] = Field(None, description="Center latitude")
    center_lon: Optional[float] = Field(None, description="Center longitude")


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