"""
Plant Schemas
=============

Request/response schemas for plant-related endpoints.
"""

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.enums.common import ConditionProfileMode


class ObservationType(str, Enum):
    """Types of plant observations."""

    GENERAL = "general"
    HEALTH = "health"
    GROWTH = "growth"
    PEST = "pest"
    DISEASE = "disease"


class NutrientType(str, Enum):
    """Types of nutrients."""

    NITROGEN = "nitrogen"
    PHOSPHORUS = "phosphorus"
    POTASSIUM = "potassium"
    CALCIUM = "calcium"
    MAGNESIUM = "magnesium"
    CUSTOM = "custom"


class ApplicationType(str, Enum):
    """Types of nutrient application."""

    SINGLE = "single"
    BULK = "bulk"


class RecordHealthObservationRequest(BaseModel):
    """Request schema for recording plant health observation."""

    health_status: str = Field(..., description="Health status: healthy, stressed, diseased, etc.")
    symptoms: list[str] = Field(default_factory=list, description="List of observed symptoms")
    disease_type: str | None = Field(default=None, description="Type of disease if applicable")
    severity_level: int = Field(default=1, ge=1, le=5, description="Severity level 1-5")
    affected_parts: list[str] = Field(default_factory=list, description="Affected plant parts")
    treatment_applied: str | None = Field(default=None, description="Treatment applied if any")
    notes: str = Field(..., min_length=1, description="Observation notes (required)")
    image_path: str | None = Field(default=None, description="Path to uploaded image")
    growth_stage: str | None = Field(default=None, description="Current growth stage")

    @field_validator("symptoms", "affected_parts", mode="before")
    @classmethod
    def parse_list_field(cls, v):
        """Parse comma-separated strings to lists."""
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


class CreateObservationRequest(BaseModel):
    """Request schema for creating a plant observation."""

    plant_id: int = Field(..., gt=0, description="Plant ID")
    observation_type: ObservationType = Field(..., description="Type of observation")
    notes: str = Field(..., min_length=1, description="Observation notes")
    health_status: str | None = Field(default=None, description="Health status for health observations")
    severity_level: int | None = Field(default=None, ge=1, le=5, description="Severity level 1-5")
    symptoms: str | None = Field(default=None, description="Comma-separated symptoms")
    image_path: str | None = Field(default=None, description="Path to image")


class CreateNutrientRecordRequest(BaseModel):
    """Request schema for recording nutrient application."""

    application_type: ApplicationType = Field(..., description="single or bulk application")
    plant_id: int | None = Field(default=None, gt=0, description="Plant ID (required for single)")
    unit_id: int | None = Field(default=None, gt=0, description="Unit ID (required for bulk)")
    nutrient_type: NutrientType = Field(..., description="Type of nutrient")
    nutrient_name: str = Field(..., min_length=1, description="Product name")
    amount: float = Field(..., gt=0, description="Amount applied")
    unit: str = Field(default="ml", description="Unit: ml, g, tsp")
    notes: str | None = Field(default=None, description="Additional notes")

    @field_validator("application_type", mode="before")
    @classmethod
    def normalize_application_type(cls, v):
        """Normalize application type to enum."""
        if isinstance(v, str):
            return ApplicationType(v.lower())
        return v


class HarvestPlantRequest(BaseModel):
    """Request schema for harvesting a plant."""

    harvest_weight_grams: float = Field(..., gt=0, description="Weight in grams (required)")
    quality_rating: int = Field(..., ge=1, le=5, description="Quality 1-5 (required)")
    notes: str = Field(default="", description="Harvest notes")
    delete_plant_data: bool = Field(default=False, description="Delete plant data after harvest")


class UpdatePlantStageRequest(BaseModel):
    """Request schema for updating plant growth stage."""

    stage: str = Field(..., description="New growth stage")
    days_in_stage: int = Field(default=0, ge=0, description="Days in the new stage")
    notes: str | None = Field(default=None, description="Transition notes")
    reset_days: bool = Field(default=True, description="Reset days in stage counter")


class AddPlantToCrudRequest(BaseModel):
    """Request schema for creating a new plant via CRUD endpoint.

    Note: This differs from CreatePlantRequest in growth.py which uses
    species/variety/phase fields. This schema matches the CRUD endpoint's
    pot_size/medium/yield fields.
    """

    name: str = Field(..., min_length=1, description="Plant name")
    plant_type: str = Field(..., min_length=1, description="Plant type/species")
    current_stage: str | None = Field(default=None, description="Current growth stage")
    days_in_stage: int = Field(default=0, ge=0, description="Days in current stage")
    moisture_level: float = Field(default=0.0, ge=0, description="Moisture level")
    sensor_ids: list[int] | None = Field(default=None, description="Associated sensor IDs")
    pot_size_liters: float = Field(default=0.0, ge=0, description="Pot size in liters")
    pot_material: str = Field(default="plastic", description="Pot material")
    growing_medium: str = Field(default="soil", description="Growing medium type")
    medium_ph: float = Field(default=7.0, ge=0, le=14, description="Medium pH")
    strain_variety: str | None = Field(default=None, description="Strain or variety")
    expected_yield_grams: float = Field(default=0.0, ge=0, description="Expected yield in grams")
    light_distance_cm: float = Field(default=0.0, ge=0, description="Light distance in cm")
    condition_profile_id: str | None = Field(default=None, description="Condition profile id")
    condition_profile_mode: ConditionProfileMode | None = Field(
        default=None,
        description="Condition profile mode (active/template)",
    )
    condition_profile_name: str | None = Field(default=None, description="Condition profile name for clone")


class ModifyPlantCrudRequest(BaseModel):
    """Request schema for updating a plant via CRUD endpoint.

    Note: This differs from UpdatePlantRequest in growth.py which uses
    species/variety/phase fields. This schema matches the CRUD endpoint's
    pot_size/medium/yield fields.
    """

    name: str | None = Field(default=None, min_length=1, description="Plant name")
    plant_type: str | None = Field(default=None, description="Plant type/species")
    current_stage: str | None = Field(default=None, description="Current growth stage")
    days_in_stage: int | None = Field(default=None, ge=0, description="Days in current stage")
    pot_size_liters: float | None = Field(default=None, ge=0, description="Pot size in liters")
    medium_ph: float | None = Field(default=None, ge=0, le=14, description="Medium pH")
    strain_variety: str | None = Field(default=None, description="Strain or variety")
    expected_yield_grams: float | None = Field(default=None, ge=0, description="Expected yield")
    light_distance_cm: float | None = Field(default=None, ge=0, description="Light distance in cm")
    soil_moisture_threshold_override: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Target soil moisture (%)",
    )


class PlantDiagnosisRequest(BaseModel):
    """Request schema for plant problem diagnosis."""

    plant_id: int = Field(..., gt=0, description="Plant ID")
    symptoms: list[str] = Field(..., min_length=1, description="List of observed symptoms")
    affected_parts: list[str] = Field(default_factory=list, description="Affected plant parts")
    duration_days: int | None = Field(default=None, ge=0, description="How long symptoms observed")
    environmental_factors: dict | None = Field(default=None, description="Environmental conditions")

    @field_validator("symptoms", "affected_parts", mode="before")
    @classmethod
    def parse_list_field(cls, v):
        """Parse comma-separated strings to lists."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


# ============================================================================
# Journal Entry Schemas (Phase 7+)
# ============================================================================


class WateringMethod(str, Enum):
    """Watering methods."""

    MANUAL = "manual"
    AUTOMATIC = "automatic"
    DRIP = "drip"
    SPRAY = "spray"
    BOTTOM = "bottom"


class WateringSource(str, Enum):
    """Watering event sources."""

    USER = "user"
    SENSOR_TRIGGERED = "sensor_triggered"
    SCHEDULE = "schedule"
    SYSTEM = "system"


class WateringEntryRequest(BaseModel):
    """Request schema for recording a watering event."""

    amount_ml: float | None = Field(default=None, ge=0, description="Water amount in milliliters")
    method: WateringMethod = Field(default=WateringMethod.MANUAL, description="Watering method")
    source: WateringSource = Field(default=WateringSource.USER, description="Event source")
    ph_level: float | None = Field(default=None, ge=0, le=14, description="Water pH level")
    ec_level: float | None = Field(default=None, ge=0, description="Water EC level (mS/cm)")
    duration_seconds: int | None = Field(default=None, ge=0, description="Watering duration in seconds")
    notes: str = Field(default="", description="Additional notes")


class PruningEntryRequest(BaseModel):
    """Request schema for recording a pruning event."""

    pruning_type: str = Field(
        ..., min_length=1, description="Type: topping, lollipopping, defoliation, lst, scrog, trim"
    )
    parts_pruned: list[str] = Field(
        default_factory=list, description="Parts pruned: leaves, branches, fan_leaves, etc."
    )
    notes: str = Field(default="", description="Additional notes")

    @field_validator("parts_pruned", mode="before")
    @classmethod
    def parse_parts(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


class TransplantEntryRequest(BaseModel):
    """Request schema for recording a transplant event."""

    from_container: str = Field(..., min_length=1, description="Original container/pot")
    to_container: str = Field(..., min_length=1, description="New container/pot")
    new_soil_mix: str | None = Field(default=None, description="New growing medium")
    root_condition: str | None = Field(default=None, description="Root condition observation")
    notes: str = Field(default="", description="Additional notes")


class EnvironmentalAdjustmentRequest(BaseModel):
    """Request schema for recording an environmental adjustment."""

    parameter: str = Field(
        ..., min_length=1, description="Parameter adjusted: fan_speed, light_intensity, temperature_target, etc."
    )
    old_value: str = Field(..., description="Previous setting value")
    new_value: str = Field(..., description="New setting value")
    reason: str = Field(default="", description="Reason for the adjustment")
    notes: str = Field(default="", description="Additional notes")


class StageExtensionRequest(BaseModel):
    """Request schema for extending the current growth stage.

    Supports two input modes:
    - extend_days: Number of days to extend (max 5)
    - extend_until: Target date to extend to (max 5 days from now)
    At least one must be provided.
    """

    extend_days: int | None = Field(default=None, ge=1, le=5, description="Days to extend (max 5)")
    extend_until: date | None = Field(default=None, description="Extend until this date (max 5 days ahead)")
    reason: str = Field(default="", description="Reason for extension")

    @field_validator("extend_until", mode="before")
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v


class UpdateJournalEntryRequest(BaseModel):
    """Request schema for updating an existing journal entry."""

    notes: str | None = Field(default=None, description="Updated notes")
    health_status: str | None = Field(default=None, description="Updated health status")
    severity_level: int | None = Field(default=None, ge=1, le=5, description="Updated severity")


class JournalEntryResponse(BaseModel):
    """Response schema for a single journal entry."""

    entry_id: int
    plant_id: int
    unit_id: int | None = None
    entry_type: str
    observation_type: str | None = None
    health_status: str | None = None
    severity_level: int | None = None
    symptoms: list[str] | None = None
    disease_type: str | None = None
    affected_parts: list[str] | None = None
    growth_stage: str | None = None
    nutrient_type: str | None = None
    nutrient_name: str | None = None
    amount: float | None = None
    unit: str | None = None
    treatment_type: str | None = None
    treatment_name: str | None = None
    notes: str | None = None
    image_path: str | None = None
    user_id: int | None = None
    observation_date: str | None = None
    created_at: str | None = None
    extra_data: dict[str, Any] | None = None

    @field_validator("symptoms", "affected_parts", mode="before")
    @classmethod
    def parse_json_lists(cls, v):
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("extra_data", mode="before")
    @classmethod
    def parse_extra_data(cls, v):
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, ValueError):
                return None
        return v


class JournalSummaryResponse(BaseModel):
    """Response schema for a journal summary."""

    plant_id: int
    total_entries: int = 0
    entries_by_type: dict[str, int] = Field(default_factory=dict)
    last_watering: str | None = None
    last_observation: str | None = None
    last_nutrient: str | None = None
    health_trend: str | None = None
    watering_count_30d: int = 0
    observation_count_30d: int = 0
    stage_changes: list[dict[str, Any]] = Field(default_factory=list)


class PaginatedJournalResponse(BaseModel):
    """Response schema for paginated journal entries."""

    items: list[JournalEntryResponse]
    page: int = 1
    per_page: int = 20
    total_pages: int = 0
    total_count: int = 0
