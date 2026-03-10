"""
Plant Journal Domain Entity
===========================
Domain entity for plant health observations stored in the plant journal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.enums.common import DiseaseType, PlantHealthStatus
from app.utils.time import coerce_datetime, iso_now

# Alias used throughout health-related flows.
HealthStatus = PlantHealthStatus


def _normalize_string_list(value: object, field_name: str) -> list[str]:
    """Validate list-like inputs and normalize string entries."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list of strings")

    normalized: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{field_name} must contain only strings")
        cleaned = item.strip()
        if cleaned:
            normalized.append(cleaned)
    return normalized


@dataclass(slots=True)
class PlantHealthObservationEntity:
    """Domain entity for a health observation entry in the plant journal."""

    unit_id: int
    health_status: HealthStatus
    symptoms: list[str]
    severity_level: int
    affected_parts: list[str] = field(default_factory=list)
    environmental_factors: dict[str, Any] = field(default_factory=dict)
    notes: str = ""
    plant_id: int | None = None
    disease_type: DiseaseType | None = None
    treatment_applied: str | None = None
    plant_type: str | None = None
    growth_stage: str | None = None
    image_path: str | None = None
    user_id: int | None = None
    observation_date: datetime | None = None

    def __post_init__(self) -> None:
        if isinstance(self.health_status, str):
            self.health_status = HealthStatus(self.health_status)
        if isinstance(self.disease_type, str):
            self.disease_type = DiseaseType(self.disease_type)
        parsed_observation_date = coerce_datetime(
            self.observation_date if self.observation_date is not None else iso_now()
        )
        if parsed_observation_date is None:
            raise ValueError("observation_date must be a valid ISO-8601 datetime")
        self.observation_date = parsed_observation_date

        self.severity_level = int(self.severity_level)
        if self.severity_level < 1 or self.severity_level > 5:
            raise ValueError("severity_level must be between 1 and 5")

        self.symptoms = _normalize_string_list(self.symptoms, "symptoms")
        self.affected_parts = _normalize_string_list(self.affected_parts, "affected_parts")
        self.environmental_factors = dict(self.environmental_factors or {})

    def to_service_kwargs(self) -> dict[str, Any]:
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
