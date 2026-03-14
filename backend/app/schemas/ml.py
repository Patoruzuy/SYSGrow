"""
ML/AI Schemas
=============

Request/response schemas for ML/AI prediction and retraining endpoints.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from enum import Enum


class ScheduleType(str, Enum):
    """Retraining schedule types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    ON_DRIFT = "on_drift"


class ModelType(str, Enum):
    """ML model types."""
    CLIMATE = "climate"
    DISEASE = "disease"
    GROWTH = "growth"
    IRRIGATION = "irrigation"


class DiseaseRiskRequest(BaseModel):
    """Request schema for disease risk prediction."""
    unit_id: int = Field(..., gt=0, description="Growth unit ID")
    plant_type: str = Field(default="unknown", description="Plant type/species")
    growth_stage: str = Field(default="vegetative", description="Current growth stage")
    current_conditions: Optional[Dict[str, Any]] = Field(
        default=None, 
        description="Current environmental conditions"
    )


class GrowthComparisonRequest(BaseModel):
    """Request schema for growth stage comparison."""
    stage: str = Field(..., description="Growth stage to compare")
    actual_conditions: Dict[str, float] = Field(
        ..., 
        description="Actual environmental conditions"
    )
    plant_type: Optional[str] = Field(default=None, description="Plant type for comparison")


class GrowthTransitionRequest(BaseModel):
    """Request schema for growth transition analysis."""
    plant_id: int = Field(..., gt=0, description="Plant ID")
    target_stage: str = Field(..., description="Target growth stage")
    current_conditions: Optional[Dict[str, float]] = Field(
        default=None,
        description="Current environmental conditions"
    )


class HealthObservationRequest(BaseModel):
    """Request schema for recording ML health observation."""
    plant_id: int = Field(..., gt=0, description="Plant ID")
    health_status: str = Field(..., description="Observed health status")
    symptoms: List[str] = Field(default_factory=list, description="Observed symptoms")
    severity_level: int = Field(default=1, ge=1, le=5, description="Severity 1-5")
    notes: Optional[str] = Field(default=None, description="Observation notes")

    @field_validator("symptoms", mode="before")
    @classmethod
    def parse_symptoms(cls, v):
        """Parse comma-separated symptoms to list."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


class EnvironmentConditions(BaseModel):
    """Environmental conditions for simulations."""
    temperature: Optional[float] = Field(default=None, description="Temperature °C")
    humidity: Optional[float] = Field(default=None, ge=0, le=100, description="Humidity %")
    light_hours: Optional[float] = Field(default=None, ge=0, le=24, description="Light hours per day")
    co2: Optional[float] = Field(default=None, ge=0, description="CO2 level ppm")
    soil_moisture: Optional[float] = Field(default=None, ge=0, le=100, description="Soil moisture %")


class WhatIfSimulationRequest(BaseModel):
    """Request schema for what-if environmental simulation."""
    unit_id: Optional[int] = Field(default=None, gt=0, description="Growth unit ID for context")
    current: EnvironmentConditions = Field(..., description="Current environmental conditions")
    simulated: EnvironmentConditions = Field(..., description="Simulated environmental conditions")


class RetrainingJobRequest(BaseModel):
    """Request schema for creating a retraining job."""
    model_type: str = Field(..., description="Model type: climate, disease, growth, irrigation")
    schedule_type: ScheduleType = Field(..., description="Schedule: daily, weekly, monthly, on_drift")
    schedule_time: Optional[str] = Field(
        default=None, 
        pattern=r"^\d{2}:\d{2}$",
        description="Time of day for scheduled training (HH:MM)"
    )
    schedule_day: Optional[int] = Field(
        default=None, 
        ge=0, 
        le=31,
        description="Day of week (0-6) or month (1-31)"
    )
    min_samples: Optional[int] = Field(
        default=None, 
        ge=1,
        description="Minimum samples required for training"
    )
    drift_threshold: Optional[float] = Field(
        default=None, 
        ge=0, 
        le=1,
        description="Drift threshold to trigger retraining (0-1)"
    )
    performance_threshold: Optional[float] = Field(
        default=None, 
        ge=0, 
        le=1,
        description="Performance threshold (0-1)"
    )
    enabled: bool = Field(default=True, description="Enable the job")

    @field_validator("schedule_type", mode="before")
    @classmethod
    def normalize_schedule_type(cls, v):
        """Normalize schedule type string to enum."""
        if isinstance(v, str):
            return ScheduleType(v.lower())
        return v


class ModelCompareRequest(BaseModel):
    """Request schema for comparing model versions."""
    model_names: List[str] = Field(
        ..., 
        min_length=2, 
        max_length=5,
        description="Model names to compare (2-5)"
    )
    metric: str = Field(default="accuracy", description="Metric to compare")


class ModelActivateRequest(BaseModel):
    """Request schema for activating a model version."""
    version: str = Field(..., description="Model version to activate")
    reason: Optional[str] = Field(default=None, description="Reason for activation")


class RootCauseAnalysisRequest(BaseModel):
    """Request schema for root cause analysis of alert clusters."""
    clusters: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        description="Alert clusters to analyze"
    )
