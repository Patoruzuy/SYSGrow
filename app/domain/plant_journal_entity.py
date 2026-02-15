"""
Plant Journal Domain Entity
===========================
Domain entity for plant health observations stored in the plant journal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.enums.common import DiseaseType, PlantHealthStatus
from app.utils.time import iso_now

# Alias used throughout health-related flows.
HealthStatus = PlantHealthStatus


@dataclass(slots=True)
class PlantHealthObservationEntity:
    """Domain entity for a health observation entry in the plant journal."""

    unit_id: int
    health_status: HealthStatus
    symptoms: List[str]
    severity_level: int
    affected_parts: List[str] = field(default_factory=list)
    environmental_factors: Dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    plant_id: Optional[int] = None
    disease_type: Optional[DiseaseType] = None
    treatment_applied: Optional[str] = None
    plant_type: Optional[str] = None
    growth_stage: Optional[str] = None
    image_path: Optional[str] = None
    user_id: Optional[int] = None
    observation_date: Optional[datetime] = None

    def __post_init__(self) -> None:
        if isinstance(self.health_status, str):
            self.health_status = HealthStatus(self.health_status)
        if isinstance(self.disease_type, str):
            self.disease_type = DiseaseType(self.disease_type)
        if isinstance(self.observation_date, str):
            self.observation_date = datetime.fromisoformat(self.observation_date)
        if self.observation_date is None:
            self.observation_date = datetime.fromisoformat(iso_now())

        self.severity_level = int(self.severity_level)
        if self.severity_level < 1 or self.severity_level > 5:
            raise ValueError("severity_level must be between 1 and 5")

        self.symptoms = list(self.symptoms or [])
        self.affected_parts = list(self.affected_parts or [])
        self.environmental_factors = dict(self.environmental_factors or {})

    def to_service_kwargs(self) -> Dict[str, Any]:
        """Map this entity to PlantJournalService.record_health_observation kwargs."""
        return {
            "plant_id": self.plant_id or 0,
            "unit_id": self.unit_id,
            "health_status": self.health_status.value,
            "symptoms": self.symptoms,
            "severity_level": self.severity_level,
            "disease_type": self.disease_type.value if self.disease_type else None,
            "affected_parts": self.affected_parts,
            "environmental_factors": self.environmental_factors,
            "treatment_applied": self.treatment_applied,
            "plant_type": self.plant_type,
            "growth_stage": self.growth_stage,
            "notes": self.notes,
            "image_path": self.image_path,
            "user_id": self.user_id,
            "observation_date": self.observation_date.isoformat() if self.observation_date else None,
        }

