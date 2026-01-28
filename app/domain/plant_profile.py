"""
PlantProfile - Thin data model for plant state
==============================================

Holds plant state (stage, moisture, sensors) as data only. All behavior
(DB writes, events, stage transitions) lives in services.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import logging

from app.enums.common import ConditionProfileMode

logger = logging.getLogger(__name__)


def _normalize_stages(growth_stages: Any, current_stage: str) -> List[Dict[str, Any]]:
    """Ensure at least one stage and normalize legacy shapes."""
    try:
        stages = growth_stages or []
        if isinstance(stages, dict):
            candidate = stages.get("growth_stage") or stages.get("stages") or []
            stages = candidate if isinstance(candidate, list) else []
        if not stages:
            fallback_name = current_stage or "Unknown"
            return [
                {
                    "stage": fallback_name,
                    "conditions": {"hours_per_day": 12},
                    "duration": {"min_days": 0, "max_days": 0},
                }
            ]
        return stages
    except Exception:
        fallback_name = current_stage or "Unknown"
        return [
            {
                "stage": fallback_name,
                "conditions": {"hours_per_day": 12},
                "duration": {"min_days": 0, "max_days": 0},
            }
        ]


def _compute_stage_meta(stages: List[Dict[str, Any]]) -> tuple[Dict[str, int], Dict[str, float]]:
    durations: Dict[str, Dict[str, int]] = {}
    lighting: Dict[str, float] = {}
    for stage in stages:
        name = stage.get("stage", "Unknown")
        duration = stage.get("duration", {}) or {}
        durations[name] = {
            "min_days": duration.get("min_days", 0),
            "max_days": duration.get("max_days", 0),
        }
        lighting[name] = stage.get("conditions", {}).get("hours_per_day", 12)
    return durations, lighting


@dataclass
class PlantProfile:
    """Thin plant state container."""

    plant_id: int
    plant_name: str
    plant_species: Optional[str] = None
    plant_type: Optional[str] = None # This is common name/type, e.g., "tomato", "lettuce"
    plant_variety: Optional[str] = None
    current_stage: str = "Unknown"
    growth_stages: List[Dict[str, Any]] = field(default_factory=list)
    gdd_base_temp_c: Optional[float] = None
    current_stage_index: int = 0
    days_in_stage: int = 0
    sensor_id: Optional[int] = None
    moisture_level: float = 0.0
    days_left: int = 0
    stage_durations: Dict[str, Dict[str, int]] = field(default_factory=dict)
    stage_lighting_hours: Dict[str, float] = field(default_factory=dict)
    # Full lighting schedule from automation config: {stage: {hours, intensity}}
    lighting_schedule: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    pot_size_liters: float = 0.0
    pot_material: str = "plastic"
    growing_medium: str = "soil"
    medium_ph: float = 7.0
    strain_variety: Optional[str] = None
    expected_yield_grams: float = 0.0
    light_distance_cm: float = 0.0
    soil_moisture_threshold_override: Optional[float] = None
    condition_profile_id: Optional[str] = None
    condition_profile_mode: Optional[ConditionProfileMode] = None
    
    def __post_init__(self) -> None:
        self._recompute_metadata()

    def refresh_growth_metadata(self) -> None:
        """Recompute stage metadata after updating `growth_stages`/`current_stage`."""
        self._recompute_metadata()

    def _recompute_metadata(self) -> None:
        self.days_in_stage = max(0, self.days_in_stage)
        self.growth_stages = _normalize_stages(self.growth_stages, self.current_stage)

        # Align index with current_stage for correct stage math.
        if self.current_stage:
            target = str(self.current_stage).strip().lower()
            matched = False
            for idx, stage in enumerate(self.growth_stages):
                if str(stage.get("stage", "")).strip().lower() == target:
                    self.current_stage_index = idx
                    self.current_stage = stage.get("stage", self.current_stage)
                    matched = True
                    break
            if not matched:
                self.current_stage_index = 0
                self.current_stage = self.growth_stages[0].get("stage", self.current_stage)
        else:
            self.current_stage = self.get_current_stage_name()

        self.stage_durations, self.stage_lighting_hours = _compute_stage_meta(self.growth_stages)
        self.days_left = self._compute_days_left()

    @property
    def id(self) -> int:
        """Compatibility alias for older code expecting `plant.id`."""
        return self.plant_id

    @property
    def days_in_current_stage(self) -> int:
        """Compatibility alias for older code expecting `days_in_current_stage`."""
        return self.days_in_stage

    @days_in_current_stage.setter
    def days_in_current_stage(self, value: int) -> None:
        self.days_in_stage = max(0, int(value))

    # -------------------------- Mutators --------------------------
    def set_stage(self, new_stage: str, days_in_stage: int = 0) -> None:
        """Update stage locally (service persists/events)."""
        self.current_stage = new_stage
        self.days_in_stage = max(0, days_in_stage)
        # Adjust index if the stage exists in growth_stages
        for idx, stage in enumerate(self.growth_stages):
            if stage.get("stage") == new_stage:
                self.current_stage_index = idx
                break
        self.days_left = self._compute_days_left()

    def set_moisture_level(self, moisture_level: float) -> None:
        """Update moisture level locally with basic validation."""
        if moisture_level < 0 or moisture_level > 100:
            raise ValueError(f"Moisture level {moisture_level} is outside the valid range (0-100).")
        self.moisture_level = moisture_level

    def link_sensor(self, sensor_id: Optional[int]) -> None:
        """Link/unlink a sensor."""
        self.sensor_id = sensor_id

    def get_sensor_id(self) -> Optional[int]:
        """Return linked sensor id."""
        return self.sensor_id

    def get_moisture_level(self) -> float:
        """Return current moisture level."""
        return self.moisture_level
    
    def get_threshold_overrides(self) -> Dict[str, float]:
        """Return threshold overrides as unit settings keys."""
        overrides = {
            "soil_moisture_threshold": self.soil_moisture_threshold_override,
        }
        return {key: value for key, value in overrides.items() if value is not None}

    def set_threshold_overrides(self, overrides: Dict[str, Any]) -> None:
        """Update override fields from threshold settings keys."""
        mapping = {
            "soil_moisture_threshold": "soil_moisture_threshold_override",
        }
        for threshold_key, field_name in mapping.items():
            if threshold_key not in overrides:
                continue
            value = overrides.get(threshold_key)
            if value is None:
                continue
            try:
                setattr(self, field_name, float(value))
            except (TypeError, ValueError):
                logger.debug("Skipping invalid override %s=%s", threshold_key, value)

    def increase_days_in_stage(self):
        """Increases the days in the current stage by 1."""
        self.days_in_stage += 1
        self._update_day_left()

    def decrease_days_in_stage(self):
        """Decreases the days in the current stage by 1."""
        if self.days_in_stage > 0:
            self.days_in_stage -= 1
            self._update_day_left()

    # -------------------------- Helpers ---------------------------
    def get_current_stage_name(self) -> str:
        if not self.growth_stages:
            return self.current_stage or "Unknown"
        if self.current_stage_index < 0 or self.current_stage_index >= len(self.growth_stages):
            return self.growth_stages[0].get("stage", self.current_stage or "Unknown")
        return self.growth_stages[self.current_stage_index].get("stage", self.current_stage or "Unknown")

    def get_current_lighting(self) -> Optional[Dict[str, Any]]:
        """
        Get lighting settings (hours, intensity) for the current growth stage.
        
        Uses the lighting_schedule from automation config, with fallback to
        stage_lighting_hours for backward compatibility.
        
        Returns:
            Dict with 'hours' and 'intensity' keys, or None if not available.
            Example: {"hours": 16, "intensity": 80}
        """
        stage_name = self.get_current_stage_name().strip().lower()
        
        # Try lighting_schedule from automation config first
        if self.lighting_schedule:
            # Direct match
            if stage_name in self.lighting_schedule:
                return dict(self.lighting_schedule[stage_name])
            
            # Common stage name mappings
            stage_mappings = {
                "germination": "seedling",
                "veg": "vegetative", 
                "flower": "flowering",
                "bloom": "flowering",
                "fruit": "fruiting",
                "fruit development": "fruiting",
                "harvest": "fruiting",
            }
            mapped = stage_mappings.get(stage_name)
            if mapped and mapped in self.lighting_schedule:
                return dict(self.lighting_schedule[mapped])
        
        # Fallback to stage_lighting_hours (hours only, no intensity)
        hours = self.stage_lighting_hours.get(self.get_current_stage_name())
        if hours is not None:
            return {"hours": hours, "intensity": None}
        
        return None

    def get_lighting_for_stage(self, stage: str) -> Optional[Dict[str, Any]]:
        """
        Get lighting settings for a specific stage.
        
        Args:
            stage: Growth stage name (e.g., "vegetative", "flowering")
            
        Returns:
            Dict with 'hours' and 'intensity' keys, or None if not available.
        """
        stage_lower = stage.strip().lower()
        
        if self.lighting_schedule:
            if stage_lower in self.lighting_schedule:
                return dict(self.lighting_schedule[stage_lower])
            
            # Common stage name mappings
            stage_mappings = {
                "germination": "seedling",
                "veg": "vegetative",
                "flower": "flowering",
                "bloom": "flowering", 
                "fruit": "fruiting",
                "fruit development": "fruiting",
                "harvest": "fruiting",
            }
            mapped = stage_mappings.get(stage_lower)
            if mapped and mapped in self.lighting_schedule:
                return dict(self.lighting_schedule[mapped])
        
        return None

    def grow(self) -> None:
        """Increment days in stage and advance locally when max_days reached."""
        self.days_in_stage += 1
        stage_name = self.get_current_stage_name()
        max_days = self.stage_durations.get(stage_name, {}).get("max_days", 0)
        self.days_left = self._compute_days_left()
        if max_days and self.days_in_stage >= max_days:
            self._advance_stage()

    def _compute_days_left(self) -> int:
        stage_name = self.get_current_stage_name()
        if stage_name in self.stage_durations:
            max_days = self.stage_durations[stage_name]["max_days"]
            return max(max_days - self.days_in_stage, 0)
        return 0

    def _update_days_left(self):
        """
        Update the days left in the current stage of the plant.
        """
        stage_name = self.get_current_stage_index()
        stage_duration = self.stage_durations.get(stage_name, 0)
        self.days_left = max(stage_duration - self.days_in_stage, 0)

    def _advance_stage(self) -> None:
        """Move to the next stage locally."""
        if self.current_stage_index < len(self.growth_stages) - 1:
            self.current_stage_index += 1
            self.current_stage = self.get_current_stage_name()
            self.days_in_stage = 0
            self.days_left = self._compute_days_left()

    # -------------------------- Serialization ---------------------
    def to_dict(self) -> Dict[str, Any]:
        """Serialize plant state for runtime/API use."""
        return {
            "plant_id": self.plant_id,
            "plant_name": self.plant_name,
            "plant_species": self.plant_species or "unknown",
            "plant_type": self.plant_type or "unknown",
            "plant_variety": self.plant_variety or "unknown",
            "gdd_base_temp_c": self.gdd_base_temp_c,
            "current_stage": self.current_stage,
            "current_stage_index": self.current_stage_index,
            "days_in_stage": self.days_in_stage,
            "days_left": self.days_left,
            "sensor_id": self.sensor_id,
            "moisture_level": self.moisture_level,
            "total_stages": len(self.growth_stages),
            "is_mature": self.current_stage_index >= len(self.growth_stages) - 1,
            "growth_stages": self.growth_stages,
            "pot_size_liters": self.pot_size_liters,
            "pot_material": self.pot_material,
            "growing_medium": self.growing_medium,
            "medium_ph": self.medium_ph,
            "strain_variety": self.strain_variety,
            "expected_yield_grams": self.expected_yield_grams,
            "light_distance_cm": self.light_distance_cm,
            "soil_moisture_threshold_override": self.soil_moisture_threshold_override,
            "condition_profile_id": self.condition_profile_id,
            "condition_profile_mode": str(self.condition_profile_mode) if self.condition_profile_mode else None,
        }

    def get_status(self) -> Dict[str, Any]:
        """Detailed status including stage metadata."""
        status = self.to_dict()
        current_stage_name = self.get_current_stage_name()
        status["stage_info"] = {
            "name": current_stage_name,
            "min_days": self.stage_durations.get(current_stage_name, {}).get("min_days", 0),
            "max_days": self.stage_durations.get(current_stage_name, {}).get("max_days", 0),
            "conditions": next(
                (stage.get("conditions", {}) for stage in self.growth_stages if stage.get("stage") == current_stage_name),
                {},
            ),
            "light_hours": self.stage_lighting_hours.get(current_stage_name, 12),
        }
        if self.days_in_stage > self.stage_durations.get(current_stage_name, {}).get("max_days", 0):
            status["warning"] = "overdue_for_transition"
        elif self.days_in_stage >= self.stage_durations.get(current_stage_name, {}).get("min_days", 0):
            status["warning"] = "ready_for_transition"
        return status

    # -------------------------- Repr ------------------------------
    def __repr__(self) -> str:
        return (
            f"<PlantProfile id={self.plant_id} name='{self.plant_name}' "
            f"stage='{self.current_stage}' days={self.days_in_stage}/{self.days_left}>"
        )

    def __str__(self) -> str:
        return f"{self.plant_name} ({self.current_stage}, day {self.days_in_stage})"
