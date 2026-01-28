"""
Growth Schemas
==============

Pydantic models for growth unit and plant request/response validation.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, AliasChoices
from app.enums import (
    LocationType,
    PlantStage,
    GrowthPhase,
    ScheduleType,
    ScheduleState,
    PhotoperiodSource,
    ConditionProfileMode,
)


# ============================================================================
# Schedule Schemas (v3 - Unified Scheduling)
# ============================================================================

class PhotoperiodConfigSchema(BaseModel):
    """Photoperiod configuration for light schedules."""
    source: PhotoperiodSource = Field(
        default=PhotoperiodSource.SCHEDULE,
        description="How to determine day/night"
    )
    sensor_threshold: float = Field(
        default=100.0,
        ge=0,
        description="Lux threshold for day/night detection"
    )
    sensor_tolerance: float = Field(
        default=10.0,
        ge=0,
        description="Lux tolerance around threshold to avoid rapid toggling"
    )
    prefer_sensor: bool = Field(
        default=False,
        description="Prefer sensor over schedule when available"
    )
    min_light_hours: Optional[float] = Field(
        default=None,
        ge=0,
        le=24,
        description="Minimum light hours to maintain"
    )
    max_light_hours: Optional[float] = Field(
        default=None,
        ge=0,
        le=24,
        description="Maximum light hours allowed"
    )

    @field_validator("source", mode="before")
    @classmethod
    def normalize_source(cls, v):
        if isinstance(v, str):
            return PhotoperiodSource(v.lower())
        return v


class ScheduleCreateSchema(BaseModel):
    """Schema for creating a new schedule."""
    name: str = Field(..., min_length=1, max_length=100, description="Schedule name")
    device_type: str = Field(..., min_length=1, max_length=50, description="Device type (light, fan, pump, etc.)")
    actuator_id: Optional[int] = Field(default=None, description="Link to specific actuator")
    schedule_type: ScheduleType = Field(default=ScheduleType.SIMPLE, description="Schedule type")
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="Start time HH:MM")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$", description="End time HH:MM")
    interval_minutes: Optional[int] = Field(
        default=None, ge=1, description="Interval minutes for repeating schedules"
    )
    duration_minutes: Optional[int] = Field(
        default=None, ge=1, description="Duration minutes for repeating schedules"
    )
    days_of_week: List[int] = Field(
        default=[0, 1, 2, 3, 4, 5, 6],
        description="Days of week (0=Monday, 6=Sunday)"
    )
    enabled: bool = Field(default=True, description="Whether schedule is active")
    state_when_active: ScheduleState = Field(default=ScheduleState.ON, description="State when active")
    value: Optional[float] = Field(default=None, ge=0, le=100, description="Value for dimmers (0-100)")
    photoperiod: Optional[PhotoperiodConfigSchema] = Field(default=None, description="Photoperiod config for lights")
    priority: int = Field(default=0, ge=0, description="Priority (higher wins in conflicts)")

    @field_validator("schedule_type", mode="before")
    @classmethod
    def normalize_schedule_type(cls, v):
        if isinstance(v, str):
            return ScheduleType(v.lower())
        return v

    @field_validator("state_when_active", mode="before")
    @classmethod
    def normalize_state(cls, v):
        if isinstance(v, str):
            return ScheduleState(v.lower())
        return v

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v):
        if not all(0 <= d <= 6 for d in v):
            raise ValueError("Days must be 0-6 (Monday-Sunday)")
        return sorted(set(v))

    @model_validator(mode="after")
    def validate_interval(self):
        if self.schedule_type == ScheduleType.INTERVAL:
            if self.interval_minutes is None or self.duration_minutes is None:
                raise ValueError("Interval schedules require interval_minutes and duration_minutes")
            if self.duration_minutes > self.interval_minutes:
                raise ValueError("duration_minutes must be <= interval_minutes")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Morning Light",
                "device_type": "light",
                "schedule_type": "photoperiod",
                "start_time": "08:00",
                "end_time": "20:00",
                "days_of_week": [0, 1, 2, 3, 4, 5, 6],
                "enabled": True,
                "state_when_active": "on",
                "priority": 0,
            }
        }
    )


class ScheduleUpdateSchema(BaseModel):
    """Schema for updating an existing schedule (all fields optional)."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    device_type: Optional[str] = Field(default=None, min_length=1, max_length=50)
    actuator_id: Optional[int] = None
    schedule_type: Optional[ScheduleType] = None
    start_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    interval_minutes: Optional[int] = Field(default=None, ge=1)
    duration_minutes: Optional[int] = Field(default=None, ge=1)
    days_of_week: Optional[List[int]] = None
    enabled: Optional[bool] = None
    state_when_active: Optional[ScheduleState] = None
    value: Optional[float] = Field(default=None, ge=0, le=100)
    photoperiod: Optional[PhotoperiodConfigSchema] = None
    priority: Optional[int] = Field(default=None, ge=0)

    @field_validator("schedule_type", mode="before")
    @classmethod
    def normalize_schedule_type(cls, v):
        if isinstance(v, str):
            return ScheduleType(v.lower())
        return v

    @field_validator("state_when_active", mode="before")
    @classmethod
    def normalize_state(cls, v):
        if isinstance(v, str):
            return ScheduleState(v.lower())
        return v

    @field_validator("days_of_week")
    @classmethod
    def validate_days(cls, v):
        if v is not None and not all(0 <= d <= 6 for d in v):
            raise ValueError("Days must be 0-6 (Monday-Sunday)")
        return sorted(set(v)) if v else v

    @model_validator(mode="after")
    def validate_interval(self):
        if self.schedule_type == ScheduleType.INTERVAL:
            if self.interval_minutes is None or self.duration_minutes is None:
                raise ValueError("Interval schedules require interval_minutes and duration_minutes")
            if self.duration_minutes > self.interval_minutes:
                raise ValueError("duration_minutes must be <= interval_minutes")
        return self


class ScheduleResponseSchema(BaseModel):
    """Response schema for a schedule."""
    schedule_id: int
    unit_id: int
    name: str
    device_type: str
    actuator_id: Optional[int]
    schedule_type: str
    start_time: str
    end_time: str
    interval_minutes: Optional[int]
    duration_minutes: Optional[int]
    days_of_week: List[int]
    enabled: bool
    state_when_active: str
    value: Optional[float]
    photoperiod: Optional[Dict[str, Any]]
    priority: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ScheduleListResponseSchema(BaseModel):
    """Response schema for list of schedules."""
    schedules: List[ScheduleResponseSchema]
    count: int
    unit_id: int


class ScheduleSummarySchema(BaseModel):
    """Summary of schedules for a unit."""
    unit_id: int
    total_schedules: int
    enabled_schedules: int
    by_device_type: Dict[str, Dict[str, int]]
    light_hours: float


# ============================================================================
# Growth Unit Schemas
# ============================================================================

class ThresholdSettings(BaseModel):
    """Threshold settings for environmental controls"""
    min_temp: Optional[float] = Field(default=None, description="Minimum temperature (°C)")
    max_temp: Optional[float] = Field(default=None, description="Maximum temperature (°C)")
    min_humidity: Optional[float] = Field(default=None, ge=0, le=100, description="Minimum humidity (%)")
    max_humidity: Optional[float] = Field(default=None, ge=0, le=100, description="Maximum humidity (%)")
    min_light: Optional[float] = Field(default=None, ge=0, description="Minimum light (lux)")
    max_light: Optional[float] = Field(default=None, ge=0, description="Maximum light (lux)")
    min_soil_moisture: Optional[float] = Field(default=None, ge=0, le=100, description="Minimum soil moisture (%)")
    max_soil_moisture: Optional[float] = Field(default=None, ge=0, le=100, description="Maximum soil moisture (%)")
    
    @model_validator(mode="after")
    def validate_ranges(self):
        """Ensure max values are greater than min values when both provided."""
        if self.max_temp is not None and self.min_temp is not None and self.max_temp <= self.min_temp:
            raise ValueError("max_temp must be greater than min_temp")
        if self.max_humidity is not None and self.min_humidity is not None and self.max_humidity <= self.min_humidity:
            raise ValueError("max_humidity must be greater than min_humidity")
        return self
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "min_temp": 18.0,
                "max_temp": 28.0,
                "min_humidity": 40.0,
                "max_humidity": 70.0,
                "min_light": 10000.0,
                "max_light": 50000.0,
                "min_soil_moisture": 30.0,
                "max_soil_moisture": 60.0,
            }
        }
    )


class UnitThresholdUpdate(BaseModel):
    """
    Simple threshold update payload used by the legacy growth API.

    Maps directly onto UnitSettings.temperature_threshold and humidity_threshold.
    """

    temperature_threshold: float = Field(..., description="Target temperature (°C)")
    humidity_threshold: float = Field(..., ge=0, le=100, description="Target humidity (%)")
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "temperature_threshold": 24.0,
                "humidity_threshold": 50.0,
            }
        }
    )


class UnitThresholdUpdateV2(BaseModel):
    """Extended threshold update payload for v2 endpoints."""

    temperature_threshold: float = Field(..., description="Target temperature (°C)")
    humidity_threshold: float = Field(..., ge=0, le=100, description="Target humidity (%)")
    co2_threshold: Optional[float] = Field(default=None, ge=0, le=5000, description="Target CO₂ (ppm)")
    voc_threshold: Optional[float] = Field(default=None, ge=0, le=10000, description="Target VOC (ppb)")
    lux_threshold: Optional[float] = Field(
        default=None,
        ge=0,
        le=100000,
        description="Target light intensity (lux)",
        validation_alias=AliasChoices("lux_threshold", "lux_threshold"),
    )
    air_quality_threshold: Optional[float] = Field(
        default=None,
        ge=0,
        le=500,
        description="Target Air Quality Index",
        validation_alias=AliasChoices("air_quality_threshold", "aqi_threshold")
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "temperature_threshold": 24.0,
                "humidity_threshold": 50.0,
                "co2_threshold": 1000.0,
                "voc_threshold": 1000.0,
                "lux_threshold": 10000.0,
                "air_quality_threshold": 100.0,
            }
        }
    )


class CreateGrowthUnitRequest(BaseModel):
    """Request model for creating a new growth unit"""
    name: str = Field(..., min_length=1, max_length=100, description="Growth unit name")
    location: LocationType = Field(..., description="Location type")
    timezone: Optional[str] = Field(default=None, max_length=100, description="Unit timezone (IANA)")
    description: Optional[str] = Field(default=None, max_length=500, description="Unit description")
    area_size: Optional[float] = Field(default=None, gt=0, description="Area size (square meters)")
    thresholds: Optional[ThresholdSettings] = Field(default=None, description="Environmental thresholds")
    condition_profile_id: Optional[str] = Field(default=None, description="Condition profile id")
    condition_profile_mode: Optional[ConditionProfileMode] = Field(
        default=None,
        description="Condition profile mode (active/template)",
    )
    condition_profile_name: Optional[str] = Field(default=None, description="Condition profile name for clone")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Indoor Grow Tent 1",
                "location": "Indoor",
                "description": "4x4 grow tent with LED lighting",
                "area_size": 1.5,
                "thresholds": {
                    "min_temp": 20.0,
                    "max_temp": 28.0,
                    "min_humidity": 40.0,
                    "max_humidity": 60.0,
                },
            }
        }
    )


class UnitDimensionsSchema(BaseModel):
    """Dimensions payload used when creating/updating a growth unit."""

    width: float = Field(..., gt=0, description="Width in centimeters")
    height: float = Field(..., gt=0, description="Height in centimeters")
    depth: float = Field(..., gt=0, description="Depth in centimeters")


class DeviceScheduleInput(BaseModel):
    """Schedule payload for a single device type (used in create/update unit)."""

    start_time: str = Field(..., description="Start time in HH:MM (24h)")
    end_time: str = Field(..., description="End time in HH:MM (24h)")
    enabled: bool = Field(default=True, description="Whether this schedule is active")


class CreateUnitPayload(BaseModel):
    """
    API payload for creating a growth unit via /api/v1/growth/units.

    This mirrors the current frontend payload shape (see docs/api/FRONTEND_TEMPLATE_UPDATES.md).
    """

    name: str = Field(..., min_length=1, max_length=100)
    location: str = Field(default="Indoor", min_length=1, max_length=100)
    timezone: Optional[str] = Field(default=None, max_length=100)
    dimensions: Optional[UnitDimensionsSchema] = None
    device_schedules: Optional[Dict[str, DeviceScheduleInput]] = None
    camera_enabled: bool = False
    custom_image: Optional[str] = None
    condition_profile_id: Optional[str] = None
    condition_profile_mode: Optional[ConditionProfileMode] = None
    condition_profile_name: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Indoor Grow Tent 1",
                "location": "Indoor",
                "dimensions": {"width": 120.0, "height": 200.0, "depth": 60.0},
                "device_schedules": {
                    "light": {"start_time": "08:00", "end_time": "20:00", "enabled": True}
                },
                "camera_enabled": True,
                "custom_image": "/static/images/tent.png",
            }
        }
    )


class UpdateUnitPayload(BaseModel):
    """Partial update payload for /api/v1/growth/units/<id>."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    location: Optional[str] = Field(default=None, min_length=1, max_length=100)
    timezone: Optional[str] = Field(default=None, max_length=100)
    dimensions: Optional[UnitDimensionsSchema] = None
    device_schedules: Optional[Dict[str, DeviceScheduleInput]] = None
    camera_enabled: Optional[bool] = None
    custom_image: Optional[str] = None


class UpdateGrowthUnitRequest(BaseModel):
    """Request model for updating an existing growth unit"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    location: Optional[LocationType] = Field(default=None)
    timezone: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)
    area_size: Optional[float] = Field(default=None, gt=0)
    thresholds: Optional[ThresholdSettings] = Field(default=None)
    active: Optional[bool] = Field(default=None)
    # Note: light_mode removed - use PhotoperiodSource in schedule's photoperiod config instead
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Unit Name",
                "description": "Updated description",
                "active": True,
            }
        }
    )


class GrowthUnitResponse(BaseModel):
    """Response model for growth unit data"""
    id: int
    name: str
    location: str
    description: Optional[str]
    area_size: Optional[float]
    active: bool
    user_id: int
    timezone: Optional[str] = None
    thresholds: Optional[dict]
    plant_count: int = 0
    device_count: int = 0
    camera_enabled: bool = False
    camera_active: bool = False
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Indoor Grow Tent 1",
                "location": "Indoor",
                "description": "4x4 grow tent with LED lighting",
                "area_size": 1.5,
                "active": True,
                "user_id": 1,
                "plant_count": 3,
                "device_count": 5,
                "thresholds": {
                    "min_temp": 20.0,
                    "max_temp": 28.0,
                    "min_humidity": 40.0,
                    "max_humidity": 60.0,
                },
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-15T10:30:00",
            }
        }
    )


# ============================================================================
# Plant Schemas
# ============================================================================

class CreatePlantRequest(BaseModel):
    """Request model for creating a new plant"""
    name: str = Field(..., min_length=1, max_length=100, description="Plant name")
    species: str = Field(..., min_length=1, max_length=100, description="Plant species")
    variety: Optional[str] = Field(default=None, max_length=100, description="Plant variety/strain")
    unit_id: int = Field(..., gt=0, description="Associated growth unit ID")
    stage: PlantStage = Field(default=PlantStage.SEED, description="Current plant stage")
    phase: GrowthPhase = Field(default=GrowthPhase.GERMINATION, description="Current growth phase")
    planted_date: Optional[date] = Field(default=None, description="Date planted")
    expected_harvest_date: Optional[date] = Field(default=None, description="Expected harvest date")
    
    @model_validator(mode="after")
    def validate_harvest_date(self):
        """Ensure harvest date is after planted date"""
        if self.expected_harvest_date is not None and self.planted_date is not None:
            if self.expected_harvest_date <= self.planted_date:
                raise ValueError("expected_harvest_date must be after planted_date")
        return self
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Tomato Plant 1",
                "species": "Solanum lycopersicum",
                "variety": "Cherokee Purple",
                "unit_id": 1,
                "stage": "Seedling",
                "phase": "Early Growth",
                "planted_date": "2024-01-15",
                "expected_harvest_date": "2024-04-15",
            }
        }
    )


class UpdatePlantRequest(BaseModel):
    """Request model for updating an existing plant"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    species: Optional[str] = Field(default=None, min_length=1, max_length=100)
    variety: Optional[str] = Field(default=None, max_length=100)
    stage: Optional[PlantStage] = Field(default=None)
    phase: Optional[GrowthPhase] = Field(default=None)
    planted_date: Optional[date] = Field(default=None)
    expected_harvest_date: Optional[date] = Field(default=None)
    actual_harvest_date: Optional[date] = Field(default=None)
    notes: Optional[str] = Field(default=None, max_length=1000)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stage": "Vegetative",
                "phase": "Rapid Growth",
                "notes": "Plant showing strong growth",
            }
        }
    )


class PlantResponse(BaseModel):
    """Response model for plant data"""
    id: int
    name: str
    species: str
    variety: Optional[str]
    unit_id: int
    stage: str
    phase: str
    planted_date: Optional[date]
    expected_harvest_date: Optional[date]
    actual_harvest_date: Optional[date]
    notes: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]
    
