"""
Climate Optimizer Service
==========================
ML-first climate control optimiser for plant growth.

Priority chain:
  1. ML model from ``ModelRegistry`` (trained on user's historical data)
  2. ``ThresholdService.get_thresholds_for_period()`` (plants_info.json + profiles)
  3. Generic fallback thresholds

Integrations:
  - ``ThresholdService``      — single source of truth for thresholds
  - ``PlantJsonHandler``      — lighting schedules, alert thresholds, automation data
  - ``SunTimesService``       — photoperiod / day-night detection
  - ``PersonalizedLearning``  — user condition profiles
  - ``ModelRegistry``         — ML model artefacts (lazy-loaded)
  - ``UnitDimensions``        — unit volume / area for scaling recommendations

This service does NOT apply changes itself — it returns predictions and
recommendations.  The caller (``ContinuousMonitor`` or ``GrowthService``)
decides whether to propose them via the notification-driven approval pattern.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.unit_runtime import UnitDimensions
    from app.services.ai.model_registry import ModelRegistry
    from app.services.ai.personalized_learning import PersonalizedLearningService
    from app.services.application.threshold_service import ThresholdService
    from app.services.utilities.sun_times_service import SunTimesService
    from app.utils.plant_json_handler import PlantJsonHandler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ClimateConditions:
    """Predicted / recommended climate conditions for a unit."""

    temperature: float
    humidity: float
    soil_moisture: float
    lux: float = 0.0
    co2: float = 1000.0
    confidence: float = 1.0
    source: str = "threshold_service"  # "ml", "threshold_service", "generic"
    is_daytime: bool = True

    def to_dict(self) -> Dict[str, float]:
        return {
            "temperature": round(self.temperature, 2),
            "humidity": round(self.humidity, 2),
            "soil_moisture": round(self.soil_moisture, 2),
            "lux": round(self.lux, 2),
            "co2": round(self.co2, 2),
            "confidence": round(self.confidence, 2),
            "source": self.source,
            "is_daytime": self.is_daytime,
        }


@dataclass
class LightingRecommendation:
    """Recommended lighting for the current growth stage."""

    hours_per_day: float
    intensity_percent: float  # 0–100
    light_start: Optional[str] = None  # HH:MM
    light_end: Optional[str] = None    # HH:MM
    source: str = "plants_info"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hours_per_day": self.hours_per_day,
            "intensity_percent": self.intensity_percent,
            "light_start": self.light_start,
            "light_end": self.light_end,
            "source": self.source,
        }


@dataclass
class ClimateRecommendation:
    """Single actionable climate recommendation."""

    action: str
    priority: str  # "urgent", "high", "medium", "low"
    metric: str    # "temperature", "humidity", "lux", etc.
    current_value: Optional[float] = None
    target_value: Optional[float] = None
    rationale: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "priority": self.priority,
            "metric": self.metric,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "rationale": self.rationale,
        }


@dataclass
class ClimateAnalysis:
    """Comprehensive climate analysis result for a unit."""

    unit_id: int
    conditions: ClimateConditions
    lighting: Optional[LightingRecommendation] = None
    recommendations: List[ClimateRecommendation] = field(default_factory=list)
    dimension_notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "conditions": self.conditions.to_dict(),
            "lighting": self.lighting.to_dict() if self.lighting else None,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "dimension_notes": self.dimension_notes,
        }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ClimateOptimizer:
    """
    ML-first climate optimiser with ThresholdService / plants_info.json fallback.

    New design (Sprint 1 — A1 + A2 + A3):
      - ``predict_optimal()`` returns the best-available ``ClimateConditions``
        for a (plant_type, growth_stage, is_daytime, unit_dimensions) tuple.
      - ``get_lighting_recommendation()`` reads automation.lighting_schedule
        from ``plants_info.json`` via ``PlantJsonHandler``.
      - ``analyze()`` is a convenience method that bundles conditions, lighting,
        and dimension-aware recommendations into a single ``ClimateAnalysis``.
    """

    def __init__(
        self,
        threshold_service: Optional["ThresholdService"] = None,
        plant_handler: Optional["PlantJsonHandler"] = None,
        model_registry: Optional["ModelRegistry"] = None,
        sun_times_service: Optional["SunTimesService"] = None,
        personalized_learning: Optional["PersonalizedLearningService"] = None,
        # Legacy: analytics_repo kept for backward compat but no longer used
        analytics_repo: Optional[Any] = None,
    ):
        self.threshold_service = threshold_service
        self.plant_handler = plant_handler
        self.model_registry = model_registry
        self.sun_times_service = sun_times_service
        self.personalized_learning = personalized_learning

        # ML model (lazy-loaded)
        self._model: Optional[Any] = None
        self._model_loaded = False
        self._model_error: Optional[str] = None

    # ------------------------------------------------------------------
    # ML model management
    # ------------------------------------------------------------------

    def load_model(self) -> bool:
        """Load the ``climate_optimizer`` ML model from the registry."""
        if self._model_loaded:
            return True
        if not self.model_registry:
            self._model_error = "No model registry available"
            return False
        try:
            self._model = self.model_registry.load_model("climate_optimizer")
            if self._model:
                self._model_loaded = True
                self._model_error = None
                logger.info("Climate optimizer ML model loaded successfully")
                return True
            self._model_error = "climate_optimizer model not found in registry"
            logger.debug(self._model_error)
            return False
        except Exception as exc:
            self._model_error = f"Failed to load model: {exc}"
            logger.error(self._model_error, exc_info=True)
            return False

    def reload_model(self) -> bool:
        """Force-reload the ML model from the registry."""
        self._model_loaded = False
        self._model = None
        return self.load_model()

    def is_available(self) -> bool:
        """Return ``True`` if the ML model is ready for predictions."""
        return self._model_loaded or self.load_model()

    def get_status(self) -> Dict[str, Any]:
        return {
            "ml_available": self._model_loaded,
            "ml_error": self._model_error,
            "has_threshold_service": self.threshold_service is not None,
            "has_plant_handler": self.plant_handler is not None,
            "has_sun_times_service": self.sun_times_service is not None,
        }

    # ------------------------------------------------------------------
    # Core prediction
    # ------------------------------------------------------------------

    def predict_optimal(
        self,
        plant_type: str,
        growth_stage: str,
        *,
        is_daytime: bool = True,
        unit_dimensions: Optional["UnitDimensions"] = None,
        current_conditions: Optional[Dict[str, float]] = None,
        user_id: Optional[int] = None,
        profile_id: Optional[str] = None,
    ) -> ClimateConditions:
        """
        Return the best-available optimal conditions.

        Priority:
          1. ML model (if trained and loaded)
          2. ThresholdService.get_thresholds_for_period (plants_info.json + profiles + day/night)
          3. Generic fallback

        Args:
            plant_type: Common name (e.g. 'Tomatoes')
            growth_stage: Stage name (e.g. 'Vegetative')
            is_daytime: ``True`` during light-on period
            unit_dimensions: Physical dimensions of the growth unit
            current_conditions: Current sensor readings (optional, used by ML)
            user_id: Owner of the unit (for profile lookup)
            profile_id: Specific condition profile to apply

        Returns:
            ``ClimateConditions`` with temperature, humidity, soil_moisture,
            lux, co2, confidence, and source label.
        """

        # --- 1. Try ML model -----------------------------------------------
        ml_result = self._predict_with_ml(
            plant_type, growth_stage,
            is_daytime=is_daytime,
            unit_dimensions=unit_dimensions,
            current_conditions=current_conditions,
        )
        if ml_result is not None:
            return ml_result

        # --- 2. ThresholdService (plants_info.json + profiles + day/night) --
        ts_result = self._predict_with_threshold_service(
            plant_type, growth_stage,
            is_daytime=is_daytime,
            user_id=user_id,
            profile_id=profile_id,
        )
        if ts_result is not None:
            return ts_result

        # --- 3. Generic fallback --------------------------------------------
        logger.debug(
            "No ML model or ThresholdService available; returning generic fallback "
            "for %s/%s (daytime=%s)",
            plant_type, growth_stage, is_daytime,
        )
        return ClimateConditions(
            temperature=21.0 if not is_daytime else 24.0,
            humidity=60.0 if is_daytime else 65.0,
            soil_moisture=50.0,
            lux=10000.0 if is_daytime else 0.0,
            co2=1000.0,
            confidence=0.3,
            source="generic",
            is_daytime=is_daytime,
        )

    # --- 1. ML prediction ---------------------------------------------------

    def _predict_with_ml(
        self,
        plant_type: str,
        growth_stage: str,
        *,
        is_daytime: bool,
        unit_dimensions: Optional["UnitDimensions"],
        current_conditions: Optional[Dict[str, float]],
    ) -> Optional[ClimateConditions]:
        """Attempt prediction via the ML model.  Returns ``None`` on failure."""
        if not self.is_available() or self._model is None:
            return None
        try:
            # Build feature vector — details depend on the trained model.
            features: Dict[str, Any] = {
                "plant_type": plant_type,
                "growth_stage": growth_stage,
                "is_daytime": int(is_daytime),
            }
            if unit_dimensions:
                features["volume_m3"] = unit_dimensions.volume_m3
                features["area_m2"] = unit_dimensions.area_m2
            if current_conditions:
                features.update(current_conditions)

            prediction = self._model.predict([list(features.values())])
            if self._validate_prediction(prediction[0]):
                return ClimateConditions(
                    temperature=float(prediction[0][0]),
                    humidity=float(prediction[0][1]),
                    soil_moisture=float(prediction[0][2]),
                    lux=float(prediction[0][3]) if len(prediction[0]) > 3 else (10000.0 if is_daytime else 0.0),
                    co2=float(prediction[0][4]) if len(prediction[0]) > 4 else 1000.0,
                    confidence=0.9,
                    source="ml",
                    is_daytime=is_daytime,
                )
        except Exception as exc:
            logger.warning("ML prediction failed for %s/%s: %s", plant_type, growth_stage, exc)
        return None

    # --- 2. ThresholdService prediction ------------------------------------

    def _predict_with_threshold_service(
        self,
        plant_type: str,
        growth_stage: str,
        *,
        is_daytime: bool,
        user_id: Optional[int],
        profile_id: Optional[str],
    ) -> Optional[ClimateConditions]:
        """Use ThresholdService (plants_info.json + profiles + day/night)."""
        if not self.threshold_service:
            return None
        try:
            thresholds = self.threshold_service.get_thresholds_for_period(
                plant_type,
                growth_stage,
                is_daytime=is_daytime,
                user_id=user_id,
                profile_id=profile_id,
            )
            return ClimateConditions(
                temperature=thresholds.temperature,
                humidity=thresholds.humidity,
                soil_moisture=thresholds.soil_moisture,
                lux=thresholds.lux,
                co2=thresholds.co2,
                confidence=0.7,
                source="threshold_service",
                is_daytime=is_daytime,
            )
        except Exception as exc:
            logger.warning(
                "ThresholdService lookup failed for %s/%s: %s",
                plant_type, growth_stage, exc,
            )
        return None

    # ------------------------------------------------------------------
    # Lighting recommendation (from plants_info.json)
    # ------------------------------------------------------------------

    def get_lighting_recommendation(
        self,
        plant_type: str,
        growth_stage: str,
    ) -> Optional[LightingRecommendation]:
        """
        Look up the lighting schedule for *plant_type / growth_stage* from
        ``plants_info.json`` via ``PlantJsonHandler``.

        Returns ``None`` when no plant handler is configured or the plant /
        stage combination is not found.
        """
        if not self.plant_handler:
            return None
        try:
            stage_lighting = self.plant_handler.get_lighting_for_stage(
                plant_type, growth_stage,
            )
            if not stage_lighting:
                return None

            hours = float(stage_lighting.get("hours", stage_lighting.get("hours_per_day", 14)))
            intensity = float(stage_lighting.get("intensity", 80))

            # Optionally compute start/end from SunTimesService
            light_start: Optional[str] = None
            light_end: Optional[str] = None
            if self.sun_times_service:
                try:
                    start_t, end_t = self.sun_times_service.get_light_schedule_for_plant(
                        target_hours=hours,
                    )
                    light_start = start_t.strftime("%H:%M")
                    light_end = end_t.strftime("%H:%M")
                except Exception:
                    pass  # Non-critical; schedule calculation is best-effort

            return LightingRecommendation(
                hours_per_day=hours,
                intensity_percent=intensity,
                light_start=light_start,
                light_end=light_end,
                source="plants_info",
            )
        except Exception as exc:
            logger.warning("Lighting lookup failed for %s/%s: %s", plant_type, growth_stage, exc)
            return None

    # ------------------------------------------------------------------
    # Dimension-aware recommendations
    # ------------------------------------------------------------------

    def _dimension_recommendations(
        self,
        unit_dimensions: Optional["UnitDimensions"],
        conditions: ClimateConditions,
    ) -> List[ClimateRecommendation]:
        """Generate recommendations that factor in unit physical size."""
        recs: List[ClimateRecommendation] = []
        if not unit_dimensions:
            return recs

        vol = unit_dimensions.volume_m3
        area = unit_dimensions.area_m2

        # Small units (<0.5 m³) change temperature/humidity faster
        if vol < 0.5:
            recs.append(ClimateRecommendation(
                action="Small enclosure — use shorter ventilation bursts to avoid overshoot",
                priority="medium",
                metric="ventilation",
                rationale=f"Unit volume is only {vol:.2f} m³; air parameters change rapidly",
            ))

        # Large units (>2 m³) may need active air circulation
        if vol > 2.0:
            recs.append(ClimateRecommendation(
                action="Ensure circulation fans cover the full volume to avoid microclimates",
                priority="medium",
                metric="air_circulation",
                rationale=f"Unit volume is {vol:.2f} m³; dead-air pockets are likely without fans",
            ))

        # Light coverage check — if area > 1 m² and lux target is high
        if area > 1.0 and conditions.lux > 5000:
            recs.append(ClimateRecommendation(
                action=f"Verify light coverage uniformity over {area:.2f} m² — consider a second fixture",
                priority="low",
                metric="lux",
                target_value=conditions.lux,
                rationale="Large floor area may have uneven light distribution",
            ))

        return recs

    # ------------------------------------------------------------------
    # Deviation recommendations (current vs target)
    # ------------------------------------------------------------------

    def _deviation_recommendations(
        self,
        current_conditions: Optional[Dict[str, float]],
        target: ClimateConditions,
    ) -> List[ClimateRecommendation]:
        """Compare current sensor readings against targets and recommend actions."""
        recs: List[ClimateRecommendation] = []
        if not current_conditions:
            return recs

        # Temperature
        temp = current_conditions.get("temperature")
        if temp is not None:
            diff = temp - target.temperature
            if abs(diff) > 3.0:
                direction = "Decrease" if diff > 0 else "Increase"
                recs.append(ClimateRecommendation(
                    action=f"{direction} temperature by {abs(diff):.1f}°C",
                    priority="high" if abs(diff) > 5.0 else "medium",
                    metric="temperature",
                    current_value=temp,
                    target_value=target.temperature,
                    rationale=f"{'Night' if not target.is_daytime else 'Day'} target is {target.temperature:.1f}°C",
                ))

        # Humidity
        hum = current_conditions.get("humidity")
        if hum is not None:
            diff = hum - target.humidity
            if abs(diff) > 10.0:
                direction = "Reduce" if diff > 0 else "Increase"
                recs.append(ClimateRecommendation(
                    action=f"{direction} humidity by {abs(diff):.1f}%",
                    priority="high" if abs(diff) > 20.0 else "medium",
                    metric="humidity",
                    current_value=hum,
                    target_value=target.humidity,
                    rationale=f"{'Night' if not target.is_daytime else 'Day'} target is {target.humidity:.1f}%",
                ))

        # CO2
        co2 = current_conditions.get("co2")
        if co2 is not None:
            diff = co2 - target.co2
            if abs(diff) > 200:
                direction = "Reduce" if diff > 0 else "Increase"
                recs.append(ClimateRecommendation(
                    action=f"{direction} CO₂ by {abs(diff):.0f} ppm",
                    priority="medium",
                    metric="co2",
                    current_value=co2,
                    target_value=target.co2,
                ))

        return recs

    # ------------------------------------------------------------------
    # High-level convenience
    # ------------------------------------------------------------------

    def analyze(
        self,
        unit_id: int,
        plant_type: str,
        growth_stage: str,
        *,
        is_daytime: bool = True,
        unit_dimensions: Optional["UnitDimensions"] = None,
        current_conditions: Optional[Dict[str, float]] = None,
        user_id: Optional[int] = None,
        profile_id: Optional[str] = None,
    ) -> ClimateAnalysis:
        """
        One-call convenience that bundles:
          1. ``predict_optimal`` (target conditions)
          2. ``get_lighting_recommendation`` (from plants_info.json)
          3. Deviation recommendations (current vs target)
          4. Dimension-aware recommendations

        Use this from ``ContinuousMonitor._monitor_unit()`` or any caller
        that needs a full analysis.
        """
        conditions = self.predict_optimal(
            plant_type,
            growth_stage,
            is_daytime=is_daytime,
            unit_dimensions=unit_dimensions,
            current_conditions=current_conditions,
            user_id=user_id,
            profile_id=profile_id,
        )

        lighting = self.get_lighting_recommendation(plant_type, growth_stage)

        recommendations: List[ClimateRecommendation] = []
        recommendations.extend(
            self._deviation_recommendations(current_conditions, conditions)
        )
        dim_recs = self._dimension_recommendations(unit_dimensions, conditions)
        recommendations.extend(dim_recs)

        return ClimateAnalysis(
            unit_id=unit_id,
            conditions=conditions,
            lighting=lighting,
            recommendations=recommendations,
            dimension_notes=[r.action for r in dim_recs],
        )

    # ------------------------------------------------------------------
    # Legacy API shim (backward compatibility)
    # ------------------------------------------------------------------

    def predict_conditions(
        self,
        plant_stage: str,
        plant_type: Optional[str] = None,
        use_fallback: bool = True,
    ) -> Optional[ClimateConditions]:
        """
        **Deprecated** — kept for callers that still use the old signature.

        Delegates to ``predict_optimal()`` with default ``is_daytime=True``.
        """
        return self.predict_optimal(
            plant_type=plant_type or "Unknown",
            growth_stage=plant_stage,
            is_daytime=True,
        )

    def get_recommendations(self, unit_id: int) -> Dict[str, Any]:
        """
        **Deprecated** — legacy shim used by ContinuousMonitor.

        Returns a dict shaped like the old ``get_recommendations()`` output
        so existing callers keep working until ContinuousMonitor is upgraded
        (Sprint 2, A8).
        """
        return {
            "priority": "low",
            "actions": [],
            "watering": {
                "issue": "none",
                "severity": "ok",
                "message": "Use irrigation_predictor for watering analysis.",
                "recommendations": [],
            },
            "climate": {
                "temperature_diff": 0.0,
                "humidity_diff": 0.0,
                "soil_moisture_diff": 0.0,
                "status": "Climate analysis now via analyze(); legacy shim active.",
            },
        }

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_prediction(prediction) -> bool:
        """Validate ML output is within physically reasonable ranges."""
        if len(prediction) < 3:
            return False
        temp, humidity, moisture = prediction[0], prediction[1], prediction[2]
        return (
            10 <= temp <= 40
            and 20 <= humidity <= 100
            and 0 <= moisture <= 100
        )
