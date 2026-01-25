"""
Climate Optimizer Service
==========================
AI-powered climate control model for plant growth optimization.

Provides ML model management with lazy loading, fallbacks, and predictions.
Refactored to use repository pattern with dependency injection.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Sequence, TYPE_CHECKING
from dataclasses import dataclass
from enum import Enum

# ML libraries lazy loaded in methods for faster startup
# import numpy as np

if TYPE_CHECKING:
    from infrastructure.database.repositories.analytics import AnalyticsRepository
    from app.services.ai.model_registry import ModelRegistry
    from app.services.ai.personalized_learning import PersonalizedLearningService

logger = logging.getLogger(__name__)


class ClimateIssue(Enum):
    """Climate control issue types."""

    NONE = "none"
    UNDERWATERING = "underwatering"
    OVERWATERING = "overwatering"
    TEMPERATURE_HIGH = "temperature_high"
    TEMPERATURE_LOW = "temperature_low"
    HUMIDITY_HIGH = "humidity_high"
    HUMIDITY_LOW = "humidity_low"


@dataclass
class ClimateConditions:
    """Predicted climate conditions."""

    temperature: float
    humidity: float
    soil_moisture: float
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for API responses."""
        return {
            "temperature": round(self.temperature, 2),
            "humidity": round(self.humidity, 2),
            "soil_moisture": round(self.soil_moisture, 2),
            "confidence": round(self.confidence, 2),
        }


@dataclass
class ClimateDifference:
    """Differences between predicted and actual climate."""

    temperature_diff: float
    humidity_diff: float
    soil_moisture_diff: float
    status: str = "OK"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "temperature_diff": round(self.temperature_diff, 2),
            "humidity_diff": round(self.humidity_diff, 2),
            "soil_moisture_diff": round(self.soil_moisture_diff, 2),
            "status": self.status,
        }


class ClimateOptimizer:
    """
    AI climate control optimizer for plant growth.

    Features:
    - ML model integration via ModelRegistry
    - Graceful fallback to default values
    - Watering issue detection
    - Climate control analysis
    - Comprehensive recommendations
    """

    # Default fallback conditions per growth stage
    DEFAULT_CONDITIONS = {
        "Germination": ClimateConditions(22.0, 70.0, 80.0, 0.5),
        "Seedling": ClimateConditions(23.0, 65.0, 75.0, 0.5),
        "Vegetative": ClimateConditions(24.0, 60.0, 70.0, 0.5),
        "Flowering": ClimateConditions(23.0, 55.0, 65.0, 0.5),
        "Fruiting": ClimateConditions(22.0, 50.0, 60.0, 0.5),
        "Harvest": ClimateConditions(21.0, 50.0, 55.0, 0.5),
    }

    # Thresholds for issue detection
    MOISTURE_THRESHOLD = 5.0  # % difference
    TEMPERATURE_THRESHOLD = 3.0  # °C difference
    HUMIDITY_THRESHOLD = 10.0  # % difference

    def __init__(
        self,
        analytics_repo: "AnalyticsRepository",
        model_registry: Optional["ModelRegistry"] = None,
        personalized_learning: Optional["PersonalizedLearningService"] = None,
    ):
        """
        Initialize climate optimizer.

        Args:
            analytics_repo: Analytics repository for sensor data access
            model_registry: Optional model registry for ML models
            personalized_learning: Optional personalized learning service for user-specific adjustments
        """
        self.analytics_repo = analytics_repo
        self.model_registry = model_registry
        self.personalized_learning = personalized_learning
        
        # Lazy-loaded model components
        self._model: Optional[Any] = None
        self._model_loaded = False
        self._model_error: Optional[str] = None

    def load_model(self) -> bool:
        """
        Load ML model from registry.

        Returns:
            True if loaded successfully, False otherwise
        """
        if self._model_loaded:
            return True

        if not self.model_registry:
            self._model_error = "No model registry available"
            logger.warning(self._model_error)
            return False

        try:
            self._model = self.model_registry.load_model("climate_optimizer")
            
            if self._model:
                self._model_loaded = True
                self._model_error = None
                logger.info("Climate optimizer model loaded successfully")
                return True
            else:
                self._model_error = "Climate optimizer model not found in registry"
                logger.warning(self._model_error)
                return False

        except Exception as e:
            self._model_error = f"Failed to load model: {str(e)}"
            logger.error(self._model_error, exc_info=True)
            return False

    def reload_model(self) -> bool:
        """
        Force reload of model from registry.

        Returns:
            True if reload successful, False otherwise
        """
        self._model_loaded = False
        self._model = None
        return self.load_model()

    def is_available(self) -> bool:
        """Check if ML model is available for predictions."""
        return self._model_loaded or self.load_model()

    def get_status(self) -> Dict[str, Any]:
        """
        Get model status information.

        Returns:
            Dict with model availability and error info
        """
        return {
            "available": self._model_loaded,
            "error": self._model_error,
            "fallback_active": not self._model_loaded,
        }

    def predict_conditions(
        self, plant_stage: str, plant_type: Optional[str] = None, use_fallback: bool = True
    ) -> Optional[ClimateConditions]:
        """
        Predict ideal environmental conditions for a growth stage.

        Args:
            plant_stage: Current growth stage (e.g., "Vegetative")
            plant_type: Optional plant type for specialized model selection
            use_fallback: If True, return default values when model unavailable

        Returns:
            ClimateConditions object with predictions, or None if unavailable
        """
        # Try plant-specific model first if plant_type provided
        if plant_type and self.model_registry:
            specialized_model_name = f"climate_optimizer_{plant_type.lower().replace(' ', '_')}"
            specialized_model = self._try_load_specialized_model(specialized_model_name)
            if specialized_model:
                try:
                    # Load optimal conditions from metadata
                    meta = self.model_registry.load_model(f"{specialized_model_name}_meta")
                    if meta and "optimal_conditions" in meta:
                        optimal = meta["optimal_conditions"]
                        logger.debug(f"Using specialized model for {plant_type}")
                        return ClimateConditions(
                            temperature=optimal.get("temperature", 24.0),
                            humidity=optimal.get("humidity", 60.0),
                            soil_moisture=self.DEFAULT_CONDITIONS.get(plant_stage, self.DEFAULT_CONDITIONS["Vegetative"]).soil_moisture,
                            confidence=0.9,  # High confidence for learned optimal
                        )
                except Exception as e:
                    logger.debug(f"Specialized model {specialized_model_name} failed: {e}")

        # Try to use general ML model
        if self.is_available() and self._model:
            try:
                # Make prediction (assuming model takes stage as input)
                # This is a simplified example - actual implementation depends on model
                prediction = self._model.predict([[plant_stage]])
                
                if self._validate_prediction(prediction[0]):
                    return ClimateConditions(
                        temperature=float(prediction[0][0]),
                        humidity=float(prediction[0][1]),
                        soil_moisture=float(prediction[0][2]),
                        confidence=1.0,
                    )

            except Exception as e:
                logger.error(f"Prediction error for stage {plant_stage}: {e}", exc_info=True)

        # Fallback to defaults
        if use_fallback:
            default = self.DEFAULT_CONDITIONS.get(
                plant_stage, self.DEFAULT_CONDITIONS.get("Vegetative")
            )
            logger.debug(f"Using fallback conditions for stage {plant_stage}")
            return default

        return None

    def _try_load_specialized_model(self, model_name: str) -> Optional[Any]:
        """Try to load a specialized plant-specific model."""
        if not self.model_registry:
            return None
        try:
            return self.model_registry.load_model(model_name)
        except Exception:
            return None

    def get_personalized_conditions(
        self,
        unit_id: int,
        plant_type: str,
        plant_stage: str,
        current_conditions: Dict[str, float]
    ) -> Optional[ClimateConditions]:
        """
        Get personalized climate conditions using user profile.
        
        Combines ML predictions with user-specific adjustments based on
        their environment, equipment, and historical success patterns.
        
        Args:
            unit_id: Unit ID
            plant_type: Plant type (e.g., 'tomato')
            plant_stage: Current growth stage
            current_conditions: Current sensor readings
            
        Returns:
            Personalized ClimateConditions, or base conditions if personalization unavailable
        """
        # Get base prediction
        base_conditions = self.predict_conditions(plant_stage, plant_type=plant_type)
        
        if not base_conditions:
            return None
        
        # If no personalized learning service, return base conditions
        if not self.personalized_learning:
            return base_conditions
        
        try:
            # Get personalized adjustments from user's profile
            personalized = self.personalized_learning.get_personalized_recommendations(
                unit_id=unit_id,
                plant_type=plant_type,
                growth_stage=plant_stage,
                current_conditions=current_conditions
            )
            
            if personalized:
                # Apply personalized adjustments to base conditions
                adjusted_temp = personalized.get('temperature', base_conditions.temperature)
                adjusted_humidity = personalized.get('humidity', base_conditions.humidity)
                adjusted_moisture = personalized.get('soil_moisture', base_conditions.soil_moisture)
                
                # Boost confidence when personalization is applied
                personalization_notes = personalized.get('personalization_notes', [])
                confidence_boost = min(len(personalization_notes) * 0.05, 0.2)  # Up to 20% boost
                
                personalized_conditions = ClimateConditions(
                    temperature=adjusted_temp,
                    humidity=adjusted_humidity,
                    soil_moisture=adjusted_moisture,
                    confidence=min(base_conditions.confidence + confidence_boost, 1.0)
                )
                
                if personalization_notes:
                    logger.debug(
                        f"Applied personalization for unit {unit_id}: {len(personalization_notes)} adjustments"
                    )
                
                return personalized_conditions
                
        except Exception as e:
            logger.warning(f"Error getting personalized conditions: {e}", exc_info=True)
        
        return base_conditions

    def detect_watering_issues(self, unit_id: int) -> Dict[str, Any]:
        """
        Analyze watering patterns and detect potential issues.

        Args:
            unit_id: The growth unit ID to analyze

        Returns:
            Dict with issue type, severity, message, and recommendations
        """
        try:
            # Fetch latest AI log for the unit
            latest_log = self.analytics_repo.get_latest_ai_log(unit_id)
            if not latest_log:
                return {
                    "issue": ClimateIssue.NONE.value,
                    "severity": "info",
                    "message": "No AI logs found for this unit.",
                    "recommendations": ["Start monitoring to collect baseline data"],
                }

            ai_moisture = latest_log.get("ai_soil_moisture", 0)
            actual_moisture = latest_log.get("actual_soil_moisture", 0)
            actuator_triggered = latest_log.get("actuator_triggered", False)

            moisture_diff = actual_moisture - ai_moisture

            # Analyze watering patterns
            if moisture_diff < -self.MOISTURE_THRESHOLD and not actuator_triggered:
                return {
                    "issue": ClimateIssue.UNDERWATERING.value,
                    "severity": "critical",
                    "message": f"Underwatering detected: Soil moisture ({actual_moisture}%) is {abs(moisture_diff):.1f}% below target ({ai_moisture}%), but irrigation did not activate.",
                    "actual": actual_moisture,
                    "predicted": ai_moisture,
                    "difference": moisture_diff,
                    "recommendations": [
                        "Check water pump functionality",
                        "Verify soil moisture sensor accuracy",
                        "Inspect irrigation lines for blockages",
                        "Review watering schedule settings",
                    ],
                }

            elif moisture_diff > self.MOISTURE_THRESHOLD and actuator_triggered:
                return {
                    "issue": ClimateIssue.OVERWATERING.value,
                    "severity": "warning",
                    "message": f"Overwatering detected: Soil moisture ({actual_moisture}%) is {moisture_diff:.1f}% above target ({ai_moisture}%), and irrigation was recently active.",
                    "actual": actual_moisture,
                    "predicted": ai_moisture,
                    "difference": moisture_diff,
                    "recommendations": [
                        "Reduce watering frequency",
                        "Check drainage system",
                        "Verify soil moisture sensor placement",
                        "Consider adjusting irrigation duration",
                    ],
                }

            elif moisture_diff > self.MOISTURE_THRESHOLD * 2:
                return {
                    "issue": ClimateIssue.OVERWATERING.value,
                    "severity": "warning",
                    "message": f"Excessive moisture detected: Soil moisture ({actual_moisture}%) is significantly above target ({ai_moisture}%).",
                    "actual": actual_moisture,
                    "predicted": ai_moisture,
                    "difference": moisture_diff,
                    "recommendations": [
                        "Improve drainage",
                        "Check for leaks",
                        "Reduce ambient humidity if possible",
                    ],
                }

            # No issues detected
            return {
                "issue": ClimateIssue.NONE.value,
                "severity": "ok",
                "message": "Watering system operating within normal parameters.",
                "actual": actual_moisture,
                "predicted": ai_moisture,
                "difference": moisture_diff,
                "recommendations": [],
            }

        except Exception as e:
            logger.error(f"Error detecting watering issues for unit {unit_id}: {e}", exc_info=True)
            return {
                "issue": "error",
                "severity": "error",
                "message": f"Failed to analyze watering: {str(e)}",
                "recommendations": ["Check system logs for details"],
            }

    def analyze_climate_control(self, unit_id: int) -> ClimateDifference:
        """
        Comprehensive climate control analysis comparing predictions with actual data.

        Args:
            unit_id: The growth unit ID to analyze

        Returns:
            ClimateDifference object with detailed comparison data
        """
        try:
            latest_log = self.analytics_repo.get_latest_ai_log(unit_id)
            if not latest_log:
                return ClimateDifference(
                    temperature_diff=0.0,
                    humidity_diff=0.0,
                    soil_moisture_diff=0.0,
                    status="No AI logs found for this unit",
                )

            # Calculate differences
            temp_diff = latest_log.get("actual_temperature", 0) - latest_log.get("ai_temperature", 0)
            humidity_diff = latest_log.get("actual_humidity", 0) - latest_log.get("ai_humidity", 0)
            moisture_diff = latest_log.get("actual_soil_moisture", 0) - latest_log.get("ai_soil_moisture", 0)

            # Determine overall status
            status = self._evaluate_climate_status(temp_diff, humidity_diff, moisture_diff)

            return ClimateDifference(
                temperature_diff=temp_diff,
                humidity_diff=humidity_diff,
                soil_moisture_diff=moisture_diff,
                status=status,
            )

        except Exception as e:
            logger.error(f"Error analyzing climate control for unit {unit_id}: {e}", exc_info=True)
            return ClimateDifference(
                temperature_diff=0.0,
                humidity_diff=0.0,
                soil_moisture_diff=0.0,
                status=f"Analysis error: {str(e)}",
            )

    def get_recommendations(self, unit_id: int) -> Dict[str, Any]:
        """
        Get comprehensive recommendations based on climate analysis.

        Args:
            unit_id: The growth unit ID

        Returns:
            Dict with prioritized recommendations and actions
        """
        watering = self.detect_watering_issues(unit_id)
        climate = self.analyze_climate_control(unit_id)

        recommendations = {
            "priority": "low",
            "actions": [],
            "watering": watering,
            "climate": climate.to_dict(),
        }

        # Determine priority based on issues
        if watering["severity"] == "critical":
            recommendations["priority"] = "critical"
            recommendations["actions"].extend(watering["recommendations"])
        elif watering["severity"] == "warning":
            recommendations["priority"] = "high"
            recommendations["actions"].extend(watering["recommendations"])

        # Add climate-specific recommendations
        if abs(climate.temperature_diff) > self.TEMPERATURE_THRESHOLD:
            recommendations["actions"].append(
                f"Adjust heating/cooling - temperature is {climate.temperature_diff:+.1f}°C from target"
            )

        if abs(climate.humidity_diff) > self.HUMIDITY_THRESHOLD:
            recommendations["actions"].append(
                f"Adjust humidifier/dehumidifier - humidity is {climate.humidity_diff:+.1f}% from target"
            )

        return recommendations

    def _validate_prediction(self, prediction: Sequence) -> bool:
        """
        Validate that predictions are within reasonable ranges.

        Args:
            prediction: Array/sequence with [temperature, humidity, soil_moisture]

        Returns:
            True if valid, False otherwise
        """
        if len(prediction) < 3:
            return False

        temp, humidity, moisture = prediction[0], prediction[1], prediction[2]

        # Reasonable ranges for plant growth
        return (
            10 <= temp <= 40  # Temperature in °C
            and 20 <= humidity <= 100  # Humidity %
            and 30 <= moisture <= 100  # Soil moisture %
        )

    def _evaluate_climate_status(
        self, temp_diff: float, humidity_diff: float, moisture_diff: float
    ) -> str:
        """
        Evaluate overall climate control status based on differences.

        Args:
            temp_diff: Temperature difference (actual - predicted)
            humidity_diff: Humidity difference (actual - predicted)
            moisture_diff: Moisture difference (actual - predicted)

        Returns:
            Status message describing climate control performance
        """
        issues = []

        if abs(temp_diff) > self.TEMPERATURE_THRESHOLD:
            issues.append(f"Temperature off by {abs(temp_diff):.1f}°C")

        if abs(humidity_diff) > self.HUMIDITY_THRESHOLD:
            issues.append(f"Humidity off by {abs(humidity_diff):.1f}%")

        if abs(moisture_diff) > self.MOISTURE_THRESHOLD:
            issues.append(f"Soil moisture off by {abs(moisture_diff):.1f}%")

        if not issues:
            return "Climate control operating optimally"
        elif len(issues) == 1:
            return f"Minor deviation: {issues[0]}"
        else:
            return f"Multiple deviations detected: {', '.join(issues)}"
