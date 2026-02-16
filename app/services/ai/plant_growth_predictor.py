"""
Plant Growth Predictor Service
===============================
AI-powered prediction of optimal growth conditions for different plant stages.

Features:
- Stage-specific environmental predictions
- ML model integration with science-based fallbacks
- Growth stage transition analysis
- Repository-based data access

Author: SYSGrow Team
Date: December 2025
"""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional

from app.enums import PlantStage

# ML libraries lazy loaded in methods for faster startup
# import numpy as np

if TYPE_CHECKING:
    from app.services.ai.model_registry import ModelRegistry
    from app.services.application.threshold_service import ThresholdService

logger = logging.getLogger(__name__)

# Alias for backward compatibility
GrowthStage = PlantStage


@dataclass
class GrowthConditions:
    """Optimal environmental conditions for plant growth."""

    temperature: float  # °C
    humidity: float  # %
    soil_moisture: float  # %
    lighting_hours: float  # hours/day
    confidence: float  # 0.0-1.0
    stage: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "temperature": self.temperature,
            "humidity": self.humidity,
            "soil_moisture": self.soil_moisture,
            "lighting_hours": self.lighting_hours,
            "confidence": self.confidence,
            "stage": self.stage,
        }

    def get_recommendation(self) -> str:
        """Get human-readable recommendation."""
        return (
            f"{self.stage} stage: Maintain {self.temperature}°C, "
            f"{self.humidity}% humidity, {self.soil_moisture}% soil moisture, "
            f"{self.lighting_hours}h light/day"
        )


@dataclass
class StageTransition:
    """Analysis of growth stage transition readiness."""

    from_stage: str
    to_stage: str
    ready: bool
    conditions_met: dict[str, bool]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "from_stage": self.from_stage,
            "to_stage": self.to_stage,
            "ready": self.ready,
            "conditions_met": self.conditions_met,
            "recommendations": self.recommendations,
        }


class PlantGrowthPredictor:
    """
    Enterprise-grade AI predictor for optimal plant growth conditions.

    Features:
    - Lazy loading with automatic model discovery from registry
    - Graceful fallback to scientifically-validated defaults
    - Stage-specific predictions with confidence scores
    - Validation of predictions against known ranges
    - Growth stage transition analysis
    - Comprehensive error handling and logging

    Usage:
        predictor = PlantGrowthPredictor(model_registry=container.model_registry)
        conditions = predictor.predict_growth_conditions("Vegetative")
        if conditions:
            print(f"Target: {conditions.temperature}°C")
    """

    # Science-backed default conditions for each growth stage
    DEFAULT_CONDITIONS = {
        "Germination": GrowthConditions(22.0, 75.0, 85.0, 18.0, 0.5, "Germination"),
        "Seedling": GrowthConditions(23.0, 70.0, 80.0, 16.0, 0.5, "Seedling"),
        "Vegetative": GrowthConditions(25.0, 65.0, 75.0, 18.0, 0.5, "Vegetative"),
        "Flowering": GrowthConditions(24.0, 60.0, 70.0, 12.0, 0.5, "Flowering"),
        "Fruiting": GrowthConditions(23.0, 55.0, 65.0, 12.0, 0.5, "Fruiting"),
        "Harvest": GrowthConditions(21.0, 50.0, 60.0, 10.0, 0.5, "Harvest"),
    }

    # Validation ranges for predictions
    VALID_RANGES = {
        "temperature": (10.0, 40.0),  # °C
        "humidity": (20.0, 100.0),  # %
        "soil_moisture": (30.0, 100.0),  # %
        "lighting_hours": (8.0, 24.0),  # hours/day
    }

    # Minimum days required in each stage before transition
    STAGE_MIN_DAYS = {
        "Germination": 5,
        "Seedling": 14,
        "Vegetative": 21,
        "Flowering": 28,
        "Fruiting": 21,
        "Harvest": 1,
    }

    def __init__(
        self,
        model_registry: Optional["ModelRegistry"] = None,
        enable_validation: bool = True,
        threshold_service: Optional["ThresholdService"] = None,
    ):
        """
        Initialize plant growth predictor.

        Args:
            model_registry: Optional ModelRegistry for ML model access
            enable_validation: If True, validate predictions against known ranges
            threshold_service: Optional ThresholdService for plant-specific defaults
        """
        self.model_registry = model_registry
        self.enable_validation = enable_validation
        self.threshold_service = threshold_service

        # Lazy-loaded components
        self._model: Any | None = None
        self._stage_encoder: Any | None = None
        self._model_loaded = False
        self._model_error: str | None = None

        logger.info("PlantGrowthPredictor initialized")

    def _load_models(self) -> bool:
        """
        Load ML models from ModelRegistry.

        Returns:
            True if models loaded successfully, False otherwise
        """
        if self._model_loaded:
            return True

        if not self.model_registry:
            self._model_error = "No model registry available"
            logger.debug("No model registry - using fallback conditions")
            return False

        try:
            # Try to load growth stage predictor model
            model_info = self.model_registry.get_model(model_type="growth_stage", version="latest")

            if not model_info:
                self._model_error = "Growth stage model not found in registry"
                logger.debug(f"{self._model_error}. Using fallback conditions.")
                return False

            # Load the model
            self._model = self.model_registry.load_model_artifact(model_type="growth_stage", version=model_info.version)

            # Load encoder if available
            try:
                self._stage_encoder = self.model_registry.load_model_artifact(
                    model_type="growth_stage_encoder", version=model_info.version
                )
            except Exception:
                logger.debug("Stage encoder not found, will use direct encoding")
                self._stage_encoder = None

            self._model_loaded = True
            self._model_error = None
            logger.info(f"Growth stage model loaded: {model_info.version}")
            return True

        except Exception as e:
            self._model_error = f"Failed to load growth models: {e!s}"
            logger.debug(self._model_error)
            return False

    def reload_models(self) -> bool:
        """
        Force reload models from registry.

        Returns:
            True if reload successful, False otherwise
        """
        self._model_loaded = False
        self._model = None
        self._stage_encoder = None
        logger.info("Reloading plant growth models from registry...")
        return self._load_models()

    def is_available(self) -> bool:
        """Check if ML models are available for predictions."""
        return self._model_loaded or self._load_models()

    def get_status(self) -> dict[str, Any]:
        """
        Get predictor status and configuration.

        Returns:
            Dict with availability, error info, and configuration
        """
        return {
            "available": self._model_loaded,
            "model_registry_available": self.model_registry is not None,
            "error": self._model_error,
            "fallback_active": not self._model_loaded,
            "validation_enabled": self.enable_validation,
            "supported_stages": [stage.value for stage in GrowthStage],
        }

    def predict_growth_conditions(
        self,
        stage_name: str,
        use_fallback: bool = True,
        days_in_stage: int | None = None,
    ) -> GrowthConditions | None:
        """
        Predict optimal environmental conditions for a given growth stage.

        Args:
            stage_name: Growth stage (e.g., "Germination", "Vegetative")
            use_fallback: If True, return defaults when model unavailable
            days_in_stage: Optional days in current stage for stage-specific tuning

        Returns:
            GrowthConditions object with predictions, or None if unavailable
        """
        # Attempt ML prediction
        if self._load_models():
            try:
                import numpy as np  # Lazy load

                # Encode stage
                if self._stage_encoder:
                    encoded_stage = self._stage_encoder.transform([stage_name])[0]
                else:
                    # Direct encoding: map stage to index
                    stage_map = {stage.value: idx for idx, stage in enumerate(GrowthStage)}
                    encoded_stage = stage_map.get(stage_name, 2)  # Default to Vegetative

                input_data = np.array([[encoded_stage]])

                # Make prediction
                prediction = self._model.predict(input_data)[0]

                # Validate prediction
                if self.enable_validation and not self._validate_prediction(prediction):
                    logger.warning(f"Invalid ML prediction for stage '{stage_name}', using fallback")
                else:
                    # Return ML prediction with high confidence
                    conditions = GrowthConditions(
                        temperature=float(prediction[0]),
                        humidity=float(prediction[1]),
                        soil_moisture=float(prediction[2]),
                        lighting_hours=float(prediction[3]),
                        confidence=0.95,
                        stage=stage_name,
                    )

                    # Apply stage-specific adjustments if days provided
                    if days_in_stage is not None:
                        conditions = self._adjust_for_stage_progress(conditions, days_in_stage)

                    logger.debug(f"ML prediction for '{stage_name}': {conditions.to_dict()}")
                    return conditions

            except Exception as e:
                logger.error(f"Prediction error for stage '{stage_name}': {e}", exc_info=True)

        # Fallback to defaults
        if use_fallback:
            # Prefer ThresholdService (profile-aware, plant-specific)
            ts_conditions = self._conditions_from_threshold_service(stage_name)
            if ts_conditions is not None:
                logger.debug(f"Using ThresholdService conditions for stage '{stage_name}'")
                return ts_conditions

            default = self.DEFAULT_CONDITIONS.get(stage_name)
            if default is None:
                # Try case-insensitive match
                for key, value in self.DEFAULT_CONDITIONS.items():
                    if key.lower() == stage_name.lower():
                        default = value
                        break
                else:
                    # Ultimate fallback
                    logger.warning(f"Unknown stage '{stage_name}', using Vegetative defaults")
                    default = self.DEFAULT_CONDITIONS["Vegetative"]

            logger.debug(f"Using default conditions for stage '{stage_name}'")
            return default

        return None

    def _validate_prediction(self, prediction) -> bool:
        """
        Validate ML predictions are within acceptable ranges.

        Args:
            prediction: Array with [temperature, humidity, soil_moisture, lighting_hours]

        Returns:
            True if all values are valid, False otherwise
        """
        if len(prediction) < 4:
            logger.warning("Prediction array has insufficient values")
            return False

        temp, humidity, moisture, light = prediction[:4]

        return (
            self.VALID_RANGES["temperature"][0] <= temp <= self.VALID_RANGES["temperature"][1]
            and self.VALID_RANGES["humidity"][0] <= humidity <= self.VALID_RANGES["humidity"][1]
            and self.VALID_RANGES["soil_moisture"][0] <= moisture <= self.VALID_RANGES["soil_moisture"][1]
            and self.VALID_RANGES["lighting_hours"][0] <= light <= self.VALID_RANGES["lighting_hours"][1]
        )

    # ------------------------------------------------------------------
    # ThresholdService integration (A9)
    # ------------------------------------------------------------------

    def _conditions_from_threshold_service(
        self,
        stage_name: str,
    ) -> GrowthConditions | None:
        """Try to build GrowthConditions from ThresholdService.

        Returns ``None`` when the service is unavailable or lacks data.
        """
        if not self.threshold_service:
            return None
        try:
            ranges = self.threshold_service.get_threshold_ranges(
                plant_type=None,  # generic
                growth_stage=stage_name,
            )
            if not ranges:
                return None

            temp = ranges.get("temperature", {})
            hum = ranges.get("humidity", {})
            sm = ranges.get("soil_moisture", {})

            # Need at least temperature to be useful
            if "optimal" not in temp:
                return None

            # Default lighting from DEFAULT_CONDITIONS if available
            default = self.DEFAULT_CONDITIONS.get(stage_name)
            lighting_hours = default.lighting_hours if default else 16.0

            return GrowthConditions(
                temperature=temp["optimal"],
                humidity=hum.get("optimal", 60.0),
                soil_moisture=sm.get("optimal", 70.0),
                lighting_hours=lighting_hours,
                confidence=0.7,
                growth_stage=stage_name,
            )
        except Exception as exc:
            logger.debug("ThresholdService lookup for growth predictor failed: %s", exc)
            return None

    def _adjust_for_stage_progress(self, conditions: GrowthConditions, days_in_stage: int) -> GrowthConditions:
        """
        Fine-tune conditions based on progression through growth stage.

        Early in stage: More conservative conditions
        Later in stage: Prepare for transition to next stage

        Args:
            conditions: Base conditions to adjust
            days_in_stage: Number of days in current stage

        Returns:
            Adjusted GrowthConditions
        """
        min_days = self.STAGE_MIN_DAYS.get(conditions.stage, 14)

        if days_in_stage < min_days * 0.3:
            # Early stage: slightly lower intensity
            conditions.lighting_hours *= 0.95
        elif days_in_stage > min_days * 1.5:
            # Late stage: prepare for transition
            conditions.lighting_hours *= 1.05

        return conditions

    def analyze_stage_transition(
        self,
        current_stage: str,
        days_in_stage: int,
        actual_conditions: dict[str, float],
    ) -> StageTransition:
        """
        Analyze if plant is ready to transition to next growth stage.

        Args:
            current_stage: Current growth stage
            days_in_stage: Days spent in current stage
            actual_conditions: Current environmental measurements

        Returns:
            StageTransition with readiness assessment and recommendations
        """
        # Determine next stage
        stage_sequence = list(GrowthStage)
        try:
            current_idx = next(i for i, s in enumerate(stage_sequence) if s.value == current_stage)
            next_stage = (
                stage_sequence[current_idx + 1].value if current_idx < len(stage_sequence) - 1 else current_stage
            )
        except (StopIteration, IndexError):
            next_stage = current_stage

        # Check minimum time requirement
        min_days = self.STAGE_MIN_DAYS.get(current_stage, 14)
        time_ready = days_in_stage >= min_days

        # Get optimal conditions for current stage
        optimal = self.predict_growth_conditions(current_stage, use_fallback=True)

        # Check environmental conditions
        conditions_met = {}
        recommendations = []

        if optimal:
            temp_diff = abs(actual_conditions.get("temperature", 0) - optimal.temperature)
            conditions_met["temperature"] = temp_diff < 3.0
            if not conditions_met["temperature"]:
                recommendations.append(
                    f"Adjust temperature to {optimal.temperature}°C (currently off by {temp_diff:.1f}°C)"
                )

            humidity_diff = abs(actual_conditions.get("humidity", 0) - optimal.humidity)
            conditions_met["humidity"] = humidity_diff < 10.0
            if not conditions_met["humidity"]:
                recommendations.append(
                    f"Adjust humidity to {optimal.humidity}% (currently off by {humidity_diff:.1f}%)"
                )

            moisture_diff = abs(actual_conditions.get("soil_moisture", 0) - optimal.soil_moisture)
            conditions_met["soil_moisture"] = moisture_diff < 10.0
            if not conditions_met["soil_moisture"]:
                recommendations.append(
                    f"Adjust soil moisture to {optimal.soil_moisture}% (currently off by {moisture_diff:.1f}%)"
                )

        conditions_met["time"] = time_ready
        if not time_ready:
            days_remaining = min_days - days_in_stage
            recommendations.append(f"Wait {days_remaining} more days before transitioning")

        # Overall readiness
        ready = all(conditions_met.values())

        if ready and next_stage != current_stage:
            recommendations.append(f"Plant is ready to transition to {next_stage} stage")

        return StageTransition(
            from_stage=current_stage,
            to_stage=next_stage,
            ready=ready,
            conditions_met=conditions_met,
            recommendations=recommendations,
        )

    def get_all_stage_conditions(self) -> dict[str, GrowthConditions]:
        """
        Get predicted conditions for all growth stages.

        Returns:
            Dict mapping stage names to their optimal conditions
        """
        results = {}
        for stage in GrowthStage:
            conditions = self.predict_growth_conditions(stage.value, use_fallback=True)
            if conditions:
                results[stage.value] = conditions
        return results

    def compare_conditions(self, actual: dict[str, float], stage: str) -> dict[str, Any]:
        """
        Compare actual conditions against optimal predictions.

        Args:
            actual: Current environmental measurements
            stage: Current growth stage

        Returns:
            Dict with comparison results and recommendations
        """
        optimal = self.predict_growth_conditions(stage, use_fallback=True)
        if not optimal:
            return {"error": "Could not determine optimal conditions"}

        comparison = {
            "stage": stage,
            "optimal": optimal.to_dict(),
            "actual": actual,
            "differences": {},
            "status": "optimal",
            "recommendations": [],
        }

        # Calculate differences
        for key in ["temperature", "humidity", "soil_moisture", "lighting_hours"]:
            optimal_val = getattr(optimal, key)
            actual_val = actual.get(key, 0)
            diff = actual_val - optimal_val
            comparison["differences"][key] = round(diff, 2)

            # Generate recommendations for significant deviations
            if key == "temperature" and abs(diff) > 2.0:
                comparison["status"] = "attention_needed"
                action = "Increase" if diff < 0 else "Decrease"
                comparison["recommendations"].append(
                    f"{action} temperature by {abs(diff):.1f}°C to reach optimal {optimal_val}°C"
                )
            elif key in ["humidity", "soil_moisture"] and abs(diff) > 8.0:
                comparison["status"] = "attention_needed"
                action = "Increase" if diff < 0 else "Decrease"
                comparison["recommendations"].append(
                    f"{action} {key.replace('_', ' ')} by {abs(diff):.1f}% to reach optimal {optimal_val}%"
                )
            elif key == "lighting_hours" and abs(diff) > 1.5:
                comparison["status"] = "attention_needed"
                action = "Increase" if diff < 0 else "Decrease"
                comparison["recommendations"].append(
                    f"{action} lighting by {abs(diff):.1f} hours to reach optimal {optimal_val}h/day"
                )

        return comparison
