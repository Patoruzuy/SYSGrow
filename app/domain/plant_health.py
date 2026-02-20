"""
Plant Health Domain Objects
=============================
Dataclasses for plant health monitoring.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.enums.common import DiseaseType, PlantHealthStatus
from app.utils.time import iso_now


@dataclass
class PlantHealthObservation:
    """Plant health observation data."""

    unit_id: int
    plant_id: int | None
    health_status: PlantHealthStatus
    symptoms: list[str]
    disease_type: DiseaseType | None
    severity_level: int  # 1-5 scale
    affected_parts: list[str]
    environmental_factors: dict[str, Any]
    treatment_applied: str | None
    notes: str
    plant_type: str | None = None
    growth_stage: str | None = None
    image_path: str | None = None
    user_id: int | None = None
    observation_date: datetime | None = None

    def __post_init__(self):
        if self.observation_date is None:
            self.observation_date = datetime.fromisoformat(iso_now())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "unit_id": self.unit_id,
            "plant_id": self.plant_id,
            "health_status": self.health_status.value if self.health_status else None,
            "symptoms": self.symptoms,
            "disease_type": self.disease_type.value if self.disease_type else None,
            "severity_level": self.severity_level,
            "affected_parts": self.affected_parts,
            "environmental_factors": self.environmental_factors,
            "treatment_applied": self.treatment_applied,
            "notes": self.notes,
            "plant_type": self.plant_type,
            "growth_stage": self.growth_stage,
            "image_path": self.image_path,
            "user_id": self.user_id,
            "observation_date": self.observation_date.isoformat() if self.observation_date else None,
        }


@dataclass
class EnvironmentalCorrelation:
    """Environmental factor correlation with plant health."""

    factor_name: str
    correlation_strength: float  # -1 to 1
    confidence_level: float  # 0 to 1
    recommended_range: tuple[float, float]
    current_value: float
    trend: str  # 'improving', 'worsening', 'stable'

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "factor_name": self.factor_name,
            "correlation_strength": round(self.correlation_strength, 3),
            "confidence_level": round(self.confidence_level, 3),
            "recommended_range": list(self.recommended_range),
            "current_value": self.current_value,
            "trend": self.trend,
        }
