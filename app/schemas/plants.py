"""
Plant Schemas
=============

Request/response schemas for plant-related endpoints.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Any
from enum import Enum


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
    symptoms: List[str] = Field(default_factory=list, description="List of observed symptoms")
    disease_type: Optional[str] = Field(default=None, description="Type of disease if applicable")
    severity_level: int = Field(default=1, ge=1, le=5, description="Severity level 1-5")
    affected_parts: List[str] = Field(default_factory=list, description="Affected plant parts")
    treatment_applied: Optional[str] = Field(default=None, description="Treatment applied if any")
    notes: str = Field(..., min_length=1, description="Observation notes (required)")
    image_path: Optional[str] = Field(default=None, description="Path to uploaded image")
    growth_stage: Optional[str] = Field(default=None, description="Current growth stage")

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
    health_status: Optional[str] = Field(default=None, description="Health status for health observations")
    severity_level: Optional[int] = Field(default=None, ge=1, le=5, description="Severity level 1-5")
    symptoms: Optional[str] = Field(default=None, description="Comma-separated symptoms")
    image_path: Optional[str] = Field(default=None, description="Path to image")


class CreateNutrientRecordRequest(BaseModel):
    """Request schema for recording nutrient application."""
    application_type: ApplicationType = Field(..., description="single or bulk application")
    plant_id: Optional[int] = Field(default=None, gt=0, description="Plant ID (required for single)")
    unit_id: Optional[int] = Field(default=None, gt=0, description="Unit ID (required for bulk)")
    nutrient_type: NutrientType = Field(..., description="Type of nutrient")
    nutrient_name: str = Field(..., min_length=1, description="Product name")
    amount: float = Field(..., gt=0, description="Amount applied")
    unit: str = Field(default="ml", description="Unit: ml, g, tsp")
    notes: Optional[str] = Field(default=None, description="Additional notes")

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
    notes: Optional[str] = Field(default=None, description="Transition notes")
    reset_days: bool = Field(default=True, description="Reset days in stage counter")


class AddPlantToCrudRequest(BaseModel):
    """Request schema for creating a new plant via CRUD endpoint.
    
    Note: This differs from CreatePlantRequest in growth.py which uses
    species/variety/phase fields. This schema matches the CRUD endpoint's
    pot_size/medium/yield fields.
    """
    name: str = Field(..., min_length=1, description="Plant name")
    plant_type: str = Field(..., min_length=1, description="Plant type/species")
    current_stage: Optional[str] = Field(default=None, description="Current growth stage")
    days_in_stage: int = Field(default=0, ge=0, description="Days in current stage")
    moisture_level: float = Field(default=0.0, ge=0, description="Moisture level")
    sensor_ids: Optional[List[int]] = Field(default=None, description="Associated sensor IDs")
    pot_size_liters: float = Field(default=0.0, ge=0, description="Pot size in liters")
    pot_material: str = Field(default="plastic", description="Pot material")
    growing_medium: str = Field(default="soil", description="Growing medium type")
    medium_ph: float = Field(default=7.0, ge=0, le=14, description="Medium pH")
    strain_variety: Optional[str] = Field(default=None, description="Strain or variety")
    expected_yield_grams: float = Field(default=0.0, ge=0, description="Expected yield in grams")
    light_distance_cm: float = Field(default=0.0, ge=0, description="Light distance in cm")


class ModifyPlantCrudRequest(BaseModel):
    """Request schema for updating a plant via CRUD endpoint.
    
    Note: This differs from UpdatePlantRequest in growth.py which uses
    species/variety/phase fields. This schema matches the CRUD endpoint's
    pot_size/medium/yield fields.
    """
    name: Optional[str] = Field(default=None, min_length=1, description="Plant name")
    plant_type: Optional[str] = Field(default=None, description="Plant type/species")
    current_stage: Optional[str] = Field(default=None, description="Current growth stage")
    days_in_stage: Optional[int] = Field(default=None, ge=0, description="Days in current stage")
    pot_size_liters: Optional[float] = Field(default=None, ge=0, description="Pot size in liters")
    medium_ph: Optional[float] = Field(default=None, ge=0, le=14, description="Medium pH")
    strain_variety: Optional[str] = Field(default=None, description="Strain or variety")
    expected_yield_grams: Optional[float] = Field(default=None, ge=0, description="Expected yield")
    light_distance_cm: Optional[float] = Field(default=None, ge=0, description="Light distance in cm")
    soil_moisture_threshold_override: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Target soil moisture (%)",
    )


class PlantDiagnosisRequest(BaseModel):
    """Request schema for plant problem diagnosis."""
    plant_id: int = Field(..., gt=0, description="Plant ID")
    symptoms: List[str] = Field(..., min_length=1, description="List of observed symptoms")
    affected_parts: List[str] = Field(default_factory=list, description="Affected plant parts")
    duration_days: Optional[int] = Field(default=None, ge=0, description="How long symptoms observed")
    environmental_factors: Optional[dict] = Field(default=None, description="Environmental conditions")

    @field_validator("symptoms", "affected_parts", mode="before")
    @classmethod
    def parse_list_field(cls, v):
        """Parse comma-separated strings to lists."""
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []
