"""
Health Schemas
==============

Pydantic models for health request/response validation.
"""

from pydantic import BaseModel, ConfigDict, Field


class SystemHealthResponse(BaseModel):
    """System health response schema."""

    health_score: float = Field(
        ..., ge=0, le=100, alias="healthScore", description="Overall system health score (0-100)"
    )
    cpu_usage: float = Field(..., ge=0, le=100, alias="cpuUsage", description="CPU usage percentage")
    memory_usage: float = Field(..., ge=0, le=100, alias="memoryUsage", description="Memory usage percentage")
    disk_usage: float = Field(..., ge=0, le=100, alias="diskUsage", description="Disk usage percentage")
    temperature_celsius: float = Field(..., alias="temperatureCelsius", description="System temperature in Celsius")
    uptime_seconds: int = Field(..., ge=0, alias="uptimeSeconds", description="System uptime in seconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "healthScore": 95.5,
                "cpuUsage": 45.3,
                "memoryUsage": 60.2,
                "diskUsage": 70.1,
                "temperatureCelsius": 55.0,
                "uptimeSeconds": 86400,
            }
        }
    )


class MetricDataPoint(BaseModel):
    """Data point for a health metric over time."""

    timestamp: str = Field(..., description="ISO 8601 timestamp of the data point")
    value: float = Field(..., description="Value of the metric at the given timestamp")
