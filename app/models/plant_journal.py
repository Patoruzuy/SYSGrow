"""
Pydantic Models for Plant Journal
=================================
Defines data structures for journal entries, including observations,
nutrient applications, and treatments.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from app.utils.time import iso_now
from app.services.ai.plant_health_monitor import HealthStatus, DiseaseType


class PlantHealthObservationModel(BaseModel):
    """Pydantic model for a plant health observation."""

    unit_id: int
    plant_id: Optional[int] = None
    health_status: HealthStatus
    symptoms: List[str]
    disease_type: Optional[DiseaseType] = None
    severity_level: int = Field(..., ge=1, le=5)  # 1-5 scale
    affected_parts: List[str]
    environmental_factors: Dict[str, Any]
    treatment_applied: Optional[str] = None
    notes: str
    plant_type: Optional[str] = None
    growth_stage: Optional[str] = None
    image_path: Optional[str] = None
    user_id: Optional[int] = None
    observation_date: datetime = Field(default_factory=lambda: datetime.fromisoformat(iso_now()))

    class Config:
        use_enum_values = True
