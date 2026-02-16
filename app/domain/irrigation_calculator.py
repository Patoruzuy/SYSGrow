"""
Irrigation Calculator Domain Service
=====================================
Computes water volume and duration from plant/pump specifications.
Replaces all hardcoded irrigation defaults with data-driven calculations.

Usage:
    calculator = IrrigationCalculator(plant_view_service)
    result = calculator.calculate(plant_id=1, pump_flow_rate=3.5)

ML Integration:
    calculator = IrrigationCalculator(plant_view_service, ml_predictor=ml_service)
    result = calculator.calculate_with_ml(plant_id=1, pump_flow_rate=3.5)
"""

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Protocol

from app.constants import (
    GROWTH_STAGE_VOLUME_MULTIPLIERS,
    PUMP_CALIBRATION_DEFAULTS,
    REFERENCE_POT_SIZE_LITERS,
    GrowingMediumConfig,
)

if TYPE_CHECKING:
    from app.domain.plant_profile import PlantProfile
    from app.services.application.plant_service import PlantViewService

logger = logging.getLogger(__name__)


class MLPredictorProtocol(Protocol):
    """Protocol for ML prediction services."""

    def predict_water_volume(
        self,
        plant_id: int,
        environmental_data: dict[str, float],
    ) -> float | None:
        """Predict optimal water volume based on environmental conditions."""
        ...

    def get_adjustment_factor(
        self,
        plant_id: int,
        historical_feedback: list[dict[str, Any]],
    ) -> float:
        """Get adjustment factor based on historical feedback."""
        ...


@dataclass
class MLPrediction:
    """ML prediction result for irrigation."""

    predicted_volume_ml: float | None = None
    adjustment_factor: float = 1.0
    confidence: float = 0.0
    model_version: str = ""
    features_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "predicted_volume_ml": self.predicted_volume_ml,
            "adjustment_factor": self.adjustment_factor,
            "confidence": self.confidence,
            "model_version": self.model_version,
            "features_used": self.features_used,
        }


@dataclass
class IrrigationCalculation:
    """Result of irrigation calculation."""

    water_volume_ml: float
    duration_seconds: int
    flow_rate_ml_per_second: float
    confidence: float  # 0-1, based on calibration data availability
    reasoning: str

    # Input parameters (for debugging/logging)
    plant_id: int | None = None
    pot_size_liters: float = 0.0
    growing_medium: str = "soil"
    growth_stage: str = "vegetative"
    plant_type: str = "default"

    # ML integration fields
    ml_prediction: MLPrediction | None = None
    ml_adjusted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        result = {
            "water_volume_ml": round(self.water_volume_ml, 1),
            "duration_seconds": self.duration_seconds,
            "flow_rate_ml_per_second": round(self.flow_rate_ml_per_second, 3),
            "confidence": round(self.confidence, 2),
            "reasoning": self.reasoning,
            "inputs": {
                "plant_id": self.plant_id,
                "pot_size_liters": self.pot_size_liters,
                "growing_medium": self.growing_medium,
                "growth_stage": self.growth_stage,
                "plant_type": self.plant_type,
            },
            "ml_adjusted": self.ml_adjusted,
        }
        if self.ml_prediction:
            result["ml_prediction"] = self.ml_prediction.to_dict()
        return result


class IrrigationCalculator:
    """
    Calculates optimal irrigation parameters from plant and pump data.

    Water Volume Formula:
        base_ml = plant_type.amount_ml_per_plant (from PlantViewService)
        pot_factor = pot_size_liters / reference_pot_size (default 5L)
        medium_factor = GrowingMediumConfig.retention_coefficient[growing_medium]
        stage_factor = growth_stage_multipliers[current_stage]

        volume_ml = base_ml * pot_factor * medium_factor * stage_factor

    ML Integration:
        When an ML predictor is provided, the calculator can:
        1. Use ML predictions as the primary water volume source
        2. Apply ML adjustment factors to formula-based calculations
        3. Blend formula and ML predictions based on confidence

    Duration Formula:
        duration_seconds = volume_ml / flow_rate_ml_per_second
    """

    # Default water amount if not specified in plant data
    DEFAULT_BASE_ML = 100.0

    # ML blending threshold - use ML if confidence > this
    ML_CONFIDENCE_THRESHOLD = 0.7

    def __init__(
        self,
        plant_service: "PlantViewService",
        ml_predictor: MLPredictorProtocol | None = None,
        feedback_callback: Callable[[int, str, float], None] | None = None,
    ):
        """
        Initialize calculator with plant service for data access.

        Args:
            plant_service: PlantViewService for accessing plant and watering data
            ml_predictor: Optional ML service for predictions and adjustments
            feedback_callback: Optional callback for recording irrigation feedback
                              Signature: (plant_id, feedback_type, volume_ml) -> None
        """
        self._plant_service = plant_service
        self._ml_predictor = ml_predictor
        self._feedback_callback = feedback_callback

    def compute_water_volume(
        self,
        plant_id: int,
        pot_size_liters: float,
        growing_medium: str,
        growth_stage: str,
        plant_type: str,
    ) -> tuple[float, str]:
        """
        Compute required water volume in ml.

        Uses PlantViewService to get plant-type-specific watering data.

        Args:
            plant_id: Plant identifier
            pot_size_liters: Size of pot in liters
            growing_medium: Growing medium type (soil, coco, perlite, etc.)
            growth_stage: Current growth stage
            plant_type: Plant type for looking up watering schedule

        Returns:
            Tuple of (volume_ml, reasoning_string)
        """
        factors = []

        # Get base amount from plant type via PlantViewService
        watering_schedule = self._plant_service.plant_json_handler.get_watering_schedule(plant_type)
        base_ml = watering_schedule.get("amount_ml_per_plant", self.DEFAULT_BASE_ML)
        factors.append(f"base={base_ml}ml")

        # Pot size scaling (reference: 5L pot)
        pot_factor = 1.0
        if pot_size_liters > 0:
            pot_factor = pot_size_liters / REFERENCE_POT_SIZE_LITERS
            factors.append(f"pot_factor={pot_factor:.2f}")

        # Growing medium retention coefficient
        medium_config = GrowingMediumConfig.get(growing_medium)
        medium_factor = medium_config.retention_coefficient
        factors.append(f"medium_factor={medium_factor:.2f} ({medium_config.name})")

        # Growth stage multiplier
        stage_factor = GROWTH_STAGE_VOLUME_MULTIPLIERS.get(growth_stage.lower(), 1.0)
        factors.append(f"stage_factor={stage_factor:.2f} ({growth_stage})")

        # Calculate final volume
        volume_ml = base_ml * pot_factor * medium_factor * stage_factor
        reasoning = " × ".join(factors) + f" = {volume_ml:.1f}ml"

        return volume_ml, reasoning

    def compute_duration(
        self,
        volume_ml: float,
        flow_rate_ml_per_second: float,
        min_duration: int | None = None,
        max_duration: int | None = None,
    ) -> int:
        """
        Compute irrigation duration in seconds.

        Args:
            volume_ml: Required water volume
            flow_rate_ml_per_second: Pump flow rate (from calibration)
            min_duration: Safety minimum (default from constants)
            max_duration: Safety maximum (default from constants)

        Returns:
            Duration in seconds, clamped to safety bounds
        """
        if min_duration is None:
            min_duration = PUMP_CALIBRATION_DEFAULTS["min_duration_seconds"]
        if max_duration is None:
            max_duration = PUMP_CALIBRATION_DEFAULTS["max_duration_seconds"]

        if flow_rate_ml_per_second <= 0:
            logger.warning(
                "Invalid flow rate %.3f, using default duration",
                flow_rate_ml_per_second,
            )
            return PUMP_CALIBRATION_DEFAULTS["calibration_duration_seconds"]

        duration = int(volume_ml / flow_rate_ml_per_second)
        return max(min_duration, min(duration, max_duration))

    def calculate(
        self,
        plant_id: int,
        pump_flow_rate: float | None = None,
    ) -> IrrigationCalculation:
        """
        Full irrigation calculation for a plant.

        Fetches plant data via PlantViewService and computes volume + duration.

        Args:
            plant_id: Plant identifier
            pump_flow_rate: Calibrated flow rate in ml/s (None = uncalibrated)

        Returns:
            IrrigationCalculation with computed values
        """
        plant = self._plant_service.get_plant(plant_id)
        if not plant:
            logger.warning("Plant %s not found, returning defaults", plant_id)
            return IrrigationCalculation(
                water_volume_ml=self.DEFAULT_BASE_ML,
                duration_seconds=PUMP_CALIBRATION_DEFAULTS["calibration_duration_seconds"],
                flow_rate_ml_per_second=PUMP_CALIBRATION_DEFAULTS["default_flow_rate_ml_per_second"],
                confidence=0.1,
                reasoning="Plant not found, using defaults",
                plant_id=plant_id,
            )

        return self.calculate_for_plant(plant, pump_flow_rate)

    def calculate_for_plant(
        self,
        plant: "PlantProfile",
        pump_flow_rate: float | None = None,
    ) -> IrrigationCalculation:
        """
        Calculate irrigation for a PlantProfile instance.

        Args:
            plant: PlantProfile with plant data
            pump_flow_rate: Calibrated flow rate in ml/s (None = uncalibrated)

        Returns:
            IrrigationCalculation with computed values
        """
        # Extract plant parameters with safe defaults
        pot_size = plant.pot_size_liters if plant.pot_size_liters > 0 else REFERENCE_POT_SIZE_LITERS
        growing_medium = plant.growing_medium or "soil"
        growth_stage = plant.current_stage or "vegetative"
        plant_type = plant.plant_type or "default"

        # Compute water volume
        volume_ml, volume_reasoning = self.compute_water_volume(
            plant_id=plant.plant_id,
            pot_size_liters=pot_size,
            growing_medium=growing_medium,
            growth_stage=growth_stage,
            plant_type=plant_type,
        )

        # Use calibrated flow rate or default
        flow_rate = pump_flow_rate or PUMP_CALIBRATION_DEFAULTS["default_flow_rate_ml_per_second"]
        is_calibrated = pump_flow_rate is not None

        # Calculate confidence based on data quality
        confidence = self._calculate_confidence(
            has_calibrated_flow_rate=is_calibrated,
            has_pot_size=plant.pot_size_liters > 0,
            has_plant_type=bool(plant.plant_type),
        )

        # Compute duration
        duration = self.compute_duration(volume_ml, flow_rate)

        # Build reasoning string
        calibration_note = "calibrated" if is_calibrated else "estimated"
        reasoning = f"{volume_reasoning}; duration={duration}s at {flow_rate:.2f}ml/s ({calibration_note})"

        return IrrigationCalculation(
            water_volume_ml=volume_ml,
            duration_seconds=duration,
            flow_rate_ml_per_second=flow_rate,
            confidence=confidence,
            reasoning=reasoning,
            plant_id=plant.plant_id,
            pot_size_liters=pot_size,
            growing_medium=growing_medium,
            growth_stage=growth_stage,
            plant_type=plant_type,
        )

    def _calculate_confidence(
        self,
        has_calibrated_flow_rate: bool,
        has_pot_size: bool,
        has_plant_type: bool,
    ) -> float:
        """
        Calculate confidence score based on available data.

        Confidence breakdown:
        - Calibrated flow rate: 50%
        - Pot size specified: 25%
        - Plant type specified: 25%

        Args:
            has_calibrated_flow_rate: Pump has been calibrated
            has_pot_size: Pot size is specified (not default)
            has_plant_type: Plant type is specified (not default)

        Returns:
            Confidence score between 0.0 and 1.0
        """
        confidence = 0.0
        if has_calibrated_flow_rate:
            confidence += 0.50
        if has_pot_size:
            confidence += 0.25
        if has_plant_type:
            confidence += 0.25
        return confidence

    def estimate_moisture_increase(
        self,
        water_volume_ml: float,
        pot_size_liters: float,
        growing_medium: str,
    ) -> float:
        """
        Estimate soil moisture increase from watering.

        Simple model: % increase ≈ (water_ml / pot_volume_ml) × 100 × medium_factor

        Args:
            water_volume_ml: Volume of water to apply
            pot_size_liters: Pot size
            growing_medium: Growing medium type

        Returns:
            Estimated moisture percentage increase
        """
        if pot_size_liters <= 0:
            return 0.0

        pot_volume_ml = pot_size_liters * 1000  # Convert liters to ml
        medium_config = GrowingMediumConfig.get(growing_medium)

        # Base increase from water volume ratio
        base_increase = (water_volume_ml / pot_volume_ml) * 100

        # Adjust for medium retention (higher retention = more moisture retained)
        adjusted_increase = base_increase * medium_config.retention_coefficient

        return min(adjusted_increase, 50.0)  # Cap at 50% increase

    # =========================================================================
    # ML Integration Methods
    # =========================================================================

    def calculate_with_ml(
        self,
        plant_id: int,
        pump_flow_rate: float | None = None,
        environmental_data: dict[str, float] | None = None,
    ) -> IrrigationCalculation:
        """
        Calculate irrigation with ML enhancement.

        If an ML predictor is available and has sufficient confidence,
        uses ML predictions. Otherwise falls back to formula-based calculation.

        Args:
            plant_id: Plant identifier
            pump_flow_rate: Calibrated flow rate in ml/s (None = uncalibrated)
            environmental_data: Current environmental conditions (temp, humidity, etc.)

        Returns:
            IrrigationCalculation with ML prediction data if available
        """
        # Get base formula calculation
        base_result = self.calculate(plant_id, pump_flow_rate)

        # If no ML predictor, return base result
        if not self._ml_predictor:
            return base_result

        # Get ML prediction
        ml_prediction = self._get_ml_prediction(plant_id, environmental_data or {})

        if not ml_prediction:
            return base_result

        use_adjustment_only = (
            ml_prediction.predicted_volume_ml is None
            and ml_prediction.adjustment_factor != 1.0
            and ml_prediction.confidence > 0.0
        )

        if not use_adjustment_only and ml_prediction.confidence < self.ML_CONFIDENCE_THRESHOLD:
            # ML not confident enough, return formula-based with prediction data
            base_result.ml_prediction = ml_prediction
            return base_result

        # Apply ML adjustment or use ML prediction
        adjusted_volume = self._blend_with_ml(
            formula_volume=base_result.water_volume_ml,
            ml_prediction=ml_prediction,
        )

        # Recalculate duration with adjusted volume
        duration = self.compute_duration(adjusted_volume, base_result.flow_rate_ml_per_second)

        # Update result
        return IrrigationCalculation(
            water_volume_ml=adjusted_volume,
            duration_seconds=duration,
            flow_rate_ml_per_second=base_result.flow_rate_ml_per_second,
            confidence=min(base_result.confidence + 0.1, 1.0),  # ML boosts confidence
            reasoning=f"{base_result.reasoning}; ML adjusted ({ml_prediction.confidence:.0%} confidence)",
            plant_id=base_result.plant_id,
            pot_size_liters=base_result.pot_size_liters,
            growing_medium=base_result.growing_medium,
            growth_stage=base_result.growth_stage,
            plant_type=base_result.plant_type,
            ml_prediction=ml_prediction,
            ml_adjusted=True,
        )

    def _get_ml_prediction(
        self,
        plant_id: int,
        environmental_data: dict[str, float],
    ) -> MLPrediction | None:
        """
        Get ML prediction for irrigation volume.

        Args:
            plant_id: Plant identifier
            environmental_data: Current environmental conditions

        Returns:
            MLPrediction or None if prediction fails
        """
        if not self._ml_predictor:
            return None

        try:
            predicted_volume = self._ml_predictor.predict_water_volume(plant_id, environmental_data)

            # Phase 3.3: Get plant-specific historical feedback
            historical_feedback = []
            try:
                plant = self._plant_service.get_plant(plant_id)
                if plant and hasattr(plant, "unit_id") and hasattr(self._ml_predictor, "get_feedback_for_plant"):
                    # Pass plant_id for plant-specific learning (Phase 3)
                    historical_feedback = self._ml_predictor.get_feedback_for_plant(
                        unit_id=plant.unit_id,
                        limit=20,
                        plant_id=plant_id,  # Phase 3: Plant-specific learning
                    )
            except Exception as e:
                logger.debug(f"Could not fetch historical feedback for plant {plant_id}: {e}")

            # Phase 3.3: Get adjustment factor with plant-specific learning
            adjustment_factor = self._ml_predictor.get_adjustment_factor(plant_id, historical_feedback)

            # Calculate confidence based on whether we have ML prediction and feedback
            # Handle case where historical_feedback might be a Mock or other non-list type
            feedback_count = 0
            try:
                feedback_count = len(historical_feedback) if historical_feedback else 0
            except (TypeError, AttributeError):
                feedback_count = 0

            confidence = 0.0
            if predicted_volume is not None:
                confidence = 0.7  # Base confidence for ML prediction
                if feedback_count > 0:
                    # Boost confidence if we have feedback data
                    confidence = min(0.9, 0.7 + feedback_count * 0.01)
            elif adjustment_factor != 1.0 and feedback_count > 0:
                # Only have adjustment factor from feedback
                confidence = min(0.6, 0.4 + feedback_count * 0.01)

            return MLPrediction(
                predicted_volume_ml=predicted_volume,
                adjustment_factor=adjustment_factor,
                confidence=confidence,
                model_version="v2.0",  # Phase 2
                features_used=list(environmental_data.keys()) if environmental_data else [],
            )
        except Exception as e:
            logger.warning("ML prediction failed for plant %s: %s", plant_id, e)
            return None

    def _blend_with_ml(
        self,
        formula_volume: float,
        ml_prediction: MLPrediction,
    ) -> float:
        """
        Blend formula-based volume with ML prediction.

        Strategy:
        - If ML has a direct prediction, use weighted average
        - If ML only has adjustment factor, apply it to formula
        - Weight by ML confidence

        Args:
            formula_volume: Volume from formula calculation
            ml_prediction: ML prediction result

        Returns:
            Blended water volume in ml
        """
        if ml_prediction.predicted_volume_ml is not None:
            # Weighted blend of formula and ML prediction
            ml_volume = ml_prediction.predicted_volume_ml * ml_prediction.adjustment_factor
            ml_weight = ml_prediction.confidence
            formula_weight = 1.0 - ml_weight
            return formula_volume * formula_weight + ml_volume * ml_weight
        else:
            # Apply adjustment factor
            return formula_volume * ml_prediction.adjustment_factor

    def record_feedback(
        self,
        plant_id: int,
        feedback_type: str,
        volume_ml: float,
    ) -> None:
        """
        Record irrigation feedback for ML learning.

        Args:
            plant_id: Plant that was irrigated
            feedback_type: "too_little", "just_right", or "too_much"
            volume_ml: Volume that was delivered
        """
        if self._feedback_callback:
            try:
                self._feedback_callback(plant_id, feedback_type, volume_ml)
                logger.info(
                    "Recorded irrigation feedback for plant %s: %s (%.1f ml)", plant_id, feedback_type, volume_ml
                )
            except Exception as e:
                logger.error("Failed to record feedback: %s", e)

    def get_recommendations(
        self,
        plant_id: int,
        current_moisture: float,
        target_moisture: float | None = None,
    ) -> dict[str, Any]:
        """
        Get irrigation recommendations for a plant.

        Args:
            plant_id: Plant identifier
            current_moisture: Current soil moisture percentage
            target_moisture: Target moisture (uses medium default if not specified)

        Returns:
            Recommendation dict with action, urgency, and details
        """
        plant = self._plant_service.get_plant(plant_id)
        if not plant:
            return {
                "action": "unknown",
                "urgency": "low",
                "reason": "Plant not found",
            }

        growing_medium = plant.growing_medium or "soil"
        medium_config = GrowingMediumConfig.get(growing_medium)

        if target_moisture is None:
            target_moisture = (medium_config.recommended_moisture_min + medium_config.recommended_moisture_max) / 2

        moisture_deficit = target_moisture - current_moisture

        # Determine action and urgency
        if current_moisture < medium_config.recommended_moisture_min:
            urgency = "high" if moisture_deficit > 20 else "medium"
            return {
                "action": "water_now",
                "urgency": urgency,
                "reason": f"Moisture ({current_moisture:.0f}%) below minimum ({medium_config.recommended_moisture_min:.0f}%)",
                "target_moisture": target_moisture,
                "moisture_deficit": moisture_deficit,
            }
        elif current_moisture > medium_config.recommended_moisture_max:
            return {
                "action": "wait",
                "urgency": "low",
                "reason": f"Moisture ({current_moisture:.0f}%) above maximum ({medium_config.recommended_moisture_max:.0f}%)",
                "target_moisture": target_moisture,
                "moisture_surplus": current_moisture - medium_config.recommended_moisture_max,
            }
        else:
            return {
                "action": "monitor",
                "urgency": "low",
                "reason": f"Moisture ({current_moisture:.0f}%) within optimal range",
                "target_moisture": target_moisture,
                "in_range": True,
            }
