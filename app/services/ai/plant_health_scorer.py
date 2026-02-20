"""
Plant Health Scorer
====================
Per-plant health scoring service that combines plant-specific metrics
(soil moisture, pH, EC) with unit-level environmental data (temperature,
humidity, VPD) to produce comprehensive health scores.

Integrates with:
- EnvironmentalLeafHealthScorer (environmental component scoring)
- DiseasePredictor (disease risk assessment)
- ThresholdService (plant-specific optimal ranges)
- PlantService (plant profiles and sensor associations)

This service is the primary entry point for per-plant health assessments.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.enums import RiskLevel
from app.utils.time import utc_now

if TYPE_CHECKING:
    from app.services.ai.disease_predictor import DiseasePredictor
    from app.services.ai.environmental_health_scorer import EnvironmentalLeafHealthScorer
    from app.services.ai.feature_engineering import PlantHealthFeatureExtractor
    from app.services.ai.model_registry import ModelRegistry
    from app.services.application.plant_service import PlantViewService
    from app.services.application.threshold_service import ThresholdService
    from infrastructure.database.repositories.analytics import AnalyticsRepository

logger = logging.getLogger(__name__)


@dataclass
class PlantHealthScore:
    """Comprehensive per-plant health assessment."""

    plant_id: int
    unit_id: int
    timestamp: datetime

    # Overall health score (0-100)
    overall_score: float

    # Component scores (0-100)
    soil_moisture_score: float
    ph_score: float
    ec_score: float
    temperature_score: float
    humidity_score: float
    vpd_score: float

    # Status classifications
    health_status: str  # healthy, stressed, critical
    disease_risk: str  # low, moderate, high
    nutrient_status: str  # optimal, deficient, excess

    # Actionable guidance
    recommendations: list[str] = field(default_factory=list)
    urgent_actions: list[str] = field(default_factory=list)

    # Data quality
    data_completeness: float = 1.0  # 0.0-1.0

    # Optional: raw values used
    raw_values: dict[str, float | None] = field(default_factory=dict)

    # Metric availability (ok, estimated, n/a)
    metric_status: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "plant_id": self.plant_id,
            "unit_id": self.unit_id,
            "timestamp": self.timestamp.isoformat(),
            "overall_score": round(self.overall_score, 1),
            "component_scores": {
                "soil_moisture": round(self.soil_moisture_score, 1),
                "ph": round(self.ph_score, 1),
                "ec": round(self.ec_score, 1),
                "temperature": round(self.temperature_score, 1),
                "humidity": round(self.humidity_score, 1),
                "vpd": round(self.vpd_score, 1),
            },
            "health_status": self.health_status,
            "disease_risk": self.disease_risk,
            "nutrient_status": self.nutrient_status,
            "recommendations": self.recommendations,
            "urgent_actions": self.urgent_actions,
            "data_completeness": round(self.data_completeness, 2),
            "raw_values": self.raw_values,
            "metric_status": self.metric_status,
        }


class PlantHealthScorer:
    """
    Calculate per-plant health scores by combining plant-specific metrics
    with unit-level environmental data.

    Scoring weights:
    - Soil Moisture: 25% (from PlantReadings or PlantProfile)
    - pH: 15% (from PlantReadings)
    - EC (nutrients): 10% (from PlantReadings)
    - Temperature: 20% (from unit SensorReadings)
    - Humidity: 15% (from unit SensorReadings)
    - VPD: 15% (calculated from temp/humidity)
    """

    # Scoring weights
    WEIGHTS = {
        "soil_moisture": 0.25,
        "ph": 0.15,
        "ec": 0.10,
        "temperature": 0.20,
        "humidity": 0.15,
        "vpd": 0.15,
    }

    # Default thresholds (overridden by ThresholdService)
    DEFAULT_THRESHOLDS = {
        "soil_moisture": {"optimal": 60.0, "tolerance": 15.0, "min": 30.0, "max": 85.0},
        "ph": {"optimal": 6.5, "tolerance": 0.5, "min": 5.5, "max": 7.5},
        "ec": {"optimal": 1.5, "tolerance": 0.5, "min": 0.5, "max": 3.0},
        "temperature": {"optimal": 24.0, "tolerance": 3.0, "min": 15.0, "max": 32.0},
        "humidity": {"optimal": 60.0, "tolerance": 10.0, "min": 40.0, "max": 80.0},
        "vpd": {"optimal": 1.0, "tolerance": 0.3, "min": 0.5, "max": 1.5},
    }

    # Health status thresholds
    STATUS_THRESHOLDS = {
        "critical": 40.0,
        "stressed": 65.0,
        "healthy": 100.0,
    }

    # ML model names
    MODEL_NAME_REGRESSOR = "plant_health_regressor"
    MODEL_NAME_CLASSIFIER = "plant_health_classifier"
    MIN_ML_CONFIDENCE = 0.6

    def __init__(
        self,
        analytics_repo: "AnalyticsRepository" | None = None,
        threshold_service: "ThresholdService" | None = None,
        disease_predictor: "DiseasePredictor" | None = None,
        environmental_scorer: "EnvironmentalLeafHealthScorer" | None = None,
        plant_service: "PlantViewService" | None = None,
        model_registry: "ModelRegistry" | None = None,
        feature_extractor: "PlantHealthFeatureExtractor" | None = None,
    ):
        """
        Initialize the plant health scorer.

        Args:
            analytics_repo: For fetching sensor data
            threshold_service: For plant-specific thresholds
            disease_predictor: For disease risk assessment
            environmental_scorer: For environmental health scoring
            plant_service: For plant profile access
            model_registry: For loading trained ML models
            feature_extractor: For extracting ML features
        """
        self.analytics_repo = analytics_repo
        self.threshold_service = threshold_service
        self.disease_predictor = disease_predictor
        self.environmental_scorer = environmental_scorer
        self.plant_service = plant_service
        self.model_registry = model_registry
        self.feature_extractor = feature_extractor

        # ML model state (loaded lazily)
        self._regressor_model = None
        self._classifier_model = None
        self._regressor_scaler = None
        self._classifier_scaler = None
        self._label_encoder = None
        self._models_loaded = False

    def load_models(self) -> bool:
        """
        Load trained ML models from registry.

        Returns:
            True if at least one model was loaded successfully
        """
        if not self.model_registry:
            return False

        loaded = False

        try:
            # Load regressor
            regressor_data = self.model_registry.load_model(self.MODEL_NAME_REGRESSOR)
            if regressor_data:
                self._regressor_model = regressor_data.get("model")
                artifacts = regressor_data.get("artifacts", {})
                self._regressor_scaler = artifacts.get("scaler")
                logger.info("Loaded plant health regressor model")
                loaded = True
        except Exception as e:
            logger.warning("Could not load health regressor: %s", e)

        try:
            # Load classifier
            classifier_data = self.model_registry.load_model(self.MODEL_NAME_CLASSIFIER)
            if classifier_data:
                self._classifier_model = classifier_data.get("model")
                artifacts = classifier_data.get("artifacts", {})
                self._classifier_scaler = artifacts.get("scaler")
                self._label_encoder = artifacts.get("label_encoder")
                logger.info("Loaded plant health classifier model")
                loaded = True
        except Exception as e:
            logger.warning("Could not load health classifier: %s", e)

        self._models_loaded = loaded
        return loaded

    def has_ml_models(self) -> bool:
        """Check if ML models are available for prediction."""
        return self._regressor_model is not None or self._classifier_model is not None

    def _predict_with_ml(
        self,
        plant_id: int,
        unit_id: int,
        plant_info: dict[str, Any],
        plant_metrics: dict[str, float | None],
        env_metrics: dict[str, float | None],
        thresholds: dict[str, dict[str, float]],
    ) -> PlantHealthScore | None:
        """
        ML-based health prediction using ensemble of regressor and classifier.

        Args:
            plant_id: Plant ID
            unit_id: Unit ID
            plant_info: Plant profile info
            plant_metrics: Plant-specific metrics (soil_moisture, pH, EC)
            env_metrics: Environmental metrics (temperature, humidity, VPD)
            thresholds: Threshold configuration

        Returns:
            PlantHealthScore if ML prediction succeeds, None otherwise
        """
        if not self.feature_extractor:
            return None

        if not self._regressor_model and not self._classifier_model:
            # Try to load models if not loaded
            if not self._models_loaded:
                self.load_models()
            if not self._regressor_model and not self._classifier_model:
                return None

        try:
            import numpy as np

            from app.services.ai.feature_engineering import FeatureEngineer

            # Extract features
            features = self.feature_extractor.extract_features(
                plant_metrics=plant_metrics,
                env_metrics=env_metrics,
                plant_profile=plant_info,
                thresholds=thresholds,
            )

            # Build feature vector
            feature_names = FeatureEngineer.PLANT_HEALTH_FEATURES_V1
            X = np.array([[features.get(f, 0.0) for f in feature_names]])

            score_pred = None
            status_pred = None
            confidence = 0.8

            # Get regressor prediction
            if self._regressor_model and self._regressor_scaler:
                X_scaled = self._regressor_scaler.transform(X)
                score_pred = float(self._regressor_model.predict(X_scaled)[0])
                score_pred = max(0.0, min(100.0, score_pred))

            # Get classifier prediction
            if self._classifier_model and self._classifier_scaler:
                X_scaled = self._classifier_scaler.transform(X)
                status_idx = self._classifier_model.predict(X_scaled)[0]
                if self._label_encoder:
                    status_pred = self._label_encoder.inverse_transform([status_idx])[0]
                else:
                    status_pred = ["healthy", "stressed", "critical"][int(status_idx)]

                # Get confidence
                if hasattr(self._classifier_model, "predict_proba"):
                    proba = self._classifier_model.predict_proba(X_scaled)[0]
                    confidence = float(np.max(proba))

            # Combine predictions using ensemble strategy
            if score_pred is not None and status_pred is not None:
                # Status to score mapping
                status_score_map = {"healthy": 85.0, "stressed": 50.0, "critical": 20.0}
                status_score = status_score_map.get(status_pred, 50.0)

                # Weighted average: 60% regressor, 40% classifier (weighted by confidence)
                final_score = (score_pred * 0.6) + (status_score * 0.4 * confidence)
                health_status = status_pred
            elif score_pred is not None:
                final_score = score_pred
                health_status = self._determine_health_status(score_pred)
            elif status_pred is not None:
                status_score_map = {"healthy": 85.0, "stressed": 50.0, "critical": 20.0}
                final_score = status_score_map.get(status_pred, 50.0)
                health_status = status_pred
            else:
                return None

            # Calculate component scores from features (deviations)
            def deviation_to_score(deviation: float, scale: float = 20.0) -> float:
                """Convert deviation to 0-100 score (lower deviation = higher score)."""
                return max(0.0, min(100.0, 100.0 - abs(deviation) * scale))

            # Generate ML-informed recommendations
            recommendations = self._generate_ml_recommendations(features, final_score, health_status)
            urgent_actions = self._identify_ml_urgent_actions(features, final_score)

            return PlantHealthScore(
                plant_id=plant_id,
                unit_id=unit_id,
                timestamp=utc_now(),
                overall_score=final_score,
                soil_moisture_score=deviation_to_score(features.get("soil_moisture_deviation", 0)),
                ph_score=deviation_to_score(features.get("ph_deviation", 0), 30.0),
                ec_score=deviation_to_score(features.get("ec_deviation", 0), 30.0),
                temperature_score=deviation_to_score(features.get("temperature_deviation", 0), 10.0),
                humidity_score=deviation_to_score(features.get("humidity_deviation", 0), 5.0),
                vpd_score=deviation_to_score(features.get("vpd_deviation", 0), 50.0),
                health_status=health_status,
                disease_risk=self._get_disease_risk_level(unit_id, env_metrics),
                nutrient_status=self._determine_nutrient_status(plant_metrics.get("ec"), plant_metrics.get("ph")),
                recommendations=recommendations,
                urgent_actions=urgent_actions,
                data_completeness=confidence,
                raw_values={**plant_metrics, **env_metrics},
                metric_status={"prediction_source": "ml"},
            )

        except Exception as e:
            logger.warning("ML prediction failed: %s", e)
            return None

    def _generate_ml_recommendations(
        self,
        features: dict[str, float],
        score: float,
        status: str,
    ) -> list[str]:
        """Generate recommendations based on ML features."""
        recommendations = []

        # Check feature deviations for specific recommendations
        if features.get("soil_moisture_deviation", 0) < -10:
            recommendations.append("Increase watering - soil moisture below optimal")
        elif features.get("soil_moisture_deviation", 0) > 10:
            recommendations.append("Reduce watering - soil moisture above optimal")

        if features.get("temperature_deviation", 0) > 3:
            recommendations.append("Reduce temperature - above optimal range")
        elif features.get("temperature_deviation", 0) < -3:
            recommendations.append("Increase temperature - below optimal range")

        if features.get("humidity_deviation", 0) > 10:
            recommendations.append("Increase ventilation - humidity too high")
        elif features.get("humidity_deviation", 0) < -10:
            recommendations.append("Increase humidity - air too dry")

        if features.get("vpd_deviation", 0) > 0.3:
            recommendations.append("Adjust VPD - outside optimal range for plant health")

        if features.get("consecutive_stress_hours", 0) > 6:
            recommendations.append("Address prolonged stress conditions")

        if not recommendations:
            if status == "healthy":
                recommendations.append("Continue current care routine")
            else:
                recommendations.append("Monitor conditions closely")

        return recommendations[:5]  # Limit to 5 recommendations

    def _identify_ml_urgent_actions(
        self,
        features: dict[str, float],
        score: float,
    ) -> list[str]:
        """Identify urgent actions based on ML features."""
        urgent = []

        if score < 40:
            urgent.append("Critical health score - immediate attention required")

        if features.get("hours_below_moisture_threshold", 0) > 12:
            urgent.append("Water immediately - prolonged moisture deficiency")

        if features.get("hours_above_temp_threshold", 0) > 6:
            urgent.append("Cool environment - prolonged heat stress")

        if features.get("consecutive_stress_hours", 0) > 12:
            urgent.append("Address stress factors immediately")

        return urgent

    def _get_disease_risk_level(
        self,
        unit_id: int,
        env_metrics: dict[str, float | None],
    ) -> str:
        """Get disease risk level."""
        if self.disease_predictor:
            try:
                risk = self.disease_predictor.assess_risk(unit_id)
                if isinstance(risk, dict):
                    return risk.get("risk_level", "low")
                return str(risk) if risk else "low"
            except Exception:
                pass

        # Simple rule-based fallback
        humidity = env_metrics.get("humidity")
        if humidity and humidity > 80:
            return "moderate"
        return "low"

    def score_plant_health(
        self,
        plant_id: int,
        unit_id: int | None = None,
    ) -> PlantHealthScore:
        """
        Calculate comprehensive health score for a single plant.

        Args:
            plant_id: Plant ID to score
            unit_id: Optional unit ID (resolved from plant if not provided)

        Returns:
            PlantHealthScore with all metrics and recommendations
        """
        try:
            # Get plant profile and unit_id
            plant_info = self._get_plant_info(plant_id)
            if not unit_id:
                unit_id = plant_info.get("unit_id", 0)

            plant_type = plant_info.get("plant_type")
            growth_stage = plant_info.get("current_stage")

            # Get thresholds for this plant type
            thresholds = self._get_thresholds(plant_type, growth_stage)

            # Collect all metrics
            plant_metrics, plant_status = self._get_plant_metrics(plant_id, plant_info)
            env_metrics = self._get_environmental_metrics(unit_id)
            metric_status = dict(plant_status)

            # Try ML prediction first if models are available
            if self.feature_extractor and (self._regressor_model or self._classifier_model or not self._models_loaded):
                ml_result = self._predict_with_ml(
                    plant_id=plant_id,
                    unit_id=unit_id,
                    plant_info=plant_info,
                    plant_metrics=plant_metrics,
                    env_metrics=env_metrics,
                    thresholds=thresholds,
                )
                if ml_result and ml_result.data_completeness >= self.MIN_ML_CONFIDENCE:
                    return ml_result

            # Fall back to rule-based scoring

            # Calculate component scores
            scores = {}
            raw_values = {}
            available_components = 0
            total_components = len(self.WEIGHTS)

            # Score plant-specific metrics
            for metric in ["soil_moisture", "ph", "ec"]:
                value = plant_metrics.get(metric)
                raw_values[metric] = value
                if value is not None:
                    scores[metric] = self._calculate_metric_score(
                        value, thresholds.get(metric, self.DEFAULT_THRESHOLDS[metric])
                    )
                    if metric_status.get(metric) != "n/a":
                        available_components += 1
                else:
                    scores[metric] = 50.0  # Default to neutral

            # Score environmental metrics
            for metric in ["temperature", "humidity", "vpd"]:
                value = env_metrics.get(metric)
                raw_values[metric] = value
                if value is not None:
                    scores[metric] = self._calculate_metric_score(
                        value, thresholds.get(metric, self.DEFAULT_THRESHOLDS[metric])
                    )
                    metric_status[metric] = "ok"
                    available_components += 1
                else:
                    scores[metric] = 50.0  # Default to neutral
                    metric_status[metric] = "n/a"

            # Calculate overall score (weighted average)
            overall_score = sum(scores[m] * self.WEIGHTS[m] for m in self.WEIGHTS)

            # Calculate data completeness
            data_completeness = available_components / total_components

            # Determine health status
            health_status = self._determine_health_status(overall_score)

            # Get disease risk
            disease_risk = self._get_disease_risk(unit_id, env_metrics)

            # Determine nutrient status
            nutrient_status = self._determine_nutrient_status(plant_metrics.get("ec"), plant_metrics.get("ph"))

            # Generate recommendations and urgent actions
            recommendations, urgent_actions = self._generate_recommendations(
                scores, raw_values, thresholds, health_status
            )
            missing_metrics = [m for m, status in metric_status.items() if status == "n/a"]
            if missing_metrics:
                recommendations.append(f"No sensor data configured for: {', '.join(sorted(missing_metrics))} (N/A)")

            return PlantHealthScore(
                plant_id=plant_id,
                unit_id=unit_id,
                timestamp=utc_now(),
                overall_score=overall_score,
                soil_moisture_score=scores["soil_moisture"],
                ph_score=scores["ph"],
                ec_score=scores["ec"],
                temperature_score=scores["temperature"],
                humidity_score=scores["humidity"],
                vpd_score=scores["vpd"],
                health_status=health_status,
                disease_risk=disease_risk,
                nutrient_status=nutrient_status,
                recommendations=recommendations,
                urgent_actions=urgent_actions,
                data_completeness=data_completeness,
                raw_values=raw_values,
                metric_status=metric_status,
            )

        except Exception as e:
            logger.error("Failed to score plant %s: %s", plant_id, e, exc_info=True)
            return self._get_default_score(plant_id, unit_id or 0)

    def score_plants_in_unit(self, unit_id: int) -> list[PlantHealthScore]:
        """
        Calculate health scores for all plants in a unit.

        Args:
            unit_id: Growth unit ID

        Returns:
            List of PlantHealthScore for each plant in the unit
        """
        scores = []

        try:
            # Get plants in unit
            plants = self._get_plants_in_unit(unit_id)

            # Pre-fetch environmental data (shared across all plants)
            self._get_environmental_metrics(unit_id)

            for plant in plants:
                plant_id = plant.get("plant_id")
                if plant_id:
                    score = self.score_plant_health(plant_id, unit_id)
                    scores.append(score)

        except Exception as e:
            logger.error("Failed to score plants in unit %s: %s", unit_id, e, exc_info=True)

        return scores

    def get_plants_needing_attention(
        self,
        unit_id: int | None = None,
        score_threshold: float = 65.0,
    ) -> list[dict[str, Any]]:
        """
        Get plants that need attention based on health score.

        Args:
            unit_id: Optional unit filter
            score_threshold: Score below which plants need attention

        Returns:
            List of plants needing attention with their scores
        """
        attention_needed = []

        try:
            if unit_id:
                scores = self.score_plants_in_unit(unit_id)
            else:
                # Get all active units and score all plants
                scores = []
                if self.analytics_repo:
                    unit_ids = self.analytics_repo.get_active_units()
                    for uid in unit_ids:
                        scores.extend(self.score_plants_in_unit(uid))

            for score in scores:
                if score.overall_score < score_threshold:
                    attention_needed.append(
                        {
                            "plant_id": score.plant_id,
                            "unit_id": score.unit_id,
                            "overall_score": round(score.overall_score, 1),
                            "health_status": score.health_status,
                            "urgent_actions": score.urgent_actions,
                            "top_issues": self._identify_top_issues(score),
                        }
                    )

            # Sort by score (lowest first)
            attention_needed.sort(key=lambda x: x["overall_score"])

        except Exception as e:
            logger.error("Failed to get plants needing attention: %s", e, exc_info=True)

        return attention_needed

    def _get_plant_info(self, plant_id: int) -> dict[str, Any]:
        """Get plant information from PlantService or repository."""
        # Try PlantService first (in-memory, fast)
        if self.plant_service:
            try:
                plant = self.plant_service.get_plant(plant_id)
                if plant:
                    return {
                        "plant_id": plant.plant_id,
                        "plant_type": plant.plant_type,
                        "current_stage": plant.current_stage,
                        "unit_id": plant.unit_id,
                        "moisture_level": plant.moisture_level,
                        "sensor_id": getattr(plant, "sensor_id", None),
                    }
            except Exception as e:
                logger.debug("PlantService lookup failed: %s", e)

        # Fallback to repository
        if self.analytics_repo:
            try:
                info = self.analytics_repo.get_plant_info(plant_id)
                if info:
                    return info
            except Exception as e:
                logger.debug("Repository lookup failed: %s", e)

        return {"plant_id": plant_id, "unit_id": 0}

    def _get_plants_in_unit(self, unit_id: int) -> list[dict[str, Any]]:
        """Get all plants in a unit."""
        if self.plant_service:
            try:
                plants = self.plant_service.list_plants(unit_id)
                return [
                    {
                        "plant_id": p.plant_id,
                        "plant_type": p.plant_type,
                        "current_stage": p.current_stage,
                        "moisture_level": p.moisture_level,
                    }
                    for p in plants
                ]
            except Exception as e:
                logger.debug("PlantService list_plants failed: %s", e)

        return []

    def _get_plant_metrics(
        self, plant_id: int, plant_info: dict[str, Any]
    ) -> tuple[dict[str, float | None], dict[str, str]]:
        """
        Get plant-specific metrics (soil_moisture, pH, EC).

        Strategy:
        1. Prefer latest PlantReadings per metric (including zero values).
        2. Fallback to PlantProfile.moisture_level if a sensor is configured.
        """
        metrics: dict[str, float | None] = {
            "soil_moisture": None,
            "ph": None,
            "ec": None,
        }
        status: dict[str, str] = {k: "n/a" for k in metrics}

        sensor_id = plant_info.get("sensor_id")
        if isinstance(sensor_id, (list, tuple, set)):
            has_sensor = len(sensor_id) > 0
        else:
            has_sensor = sensor_id is not None
        readings: list[dict[str, Any]] = []

        if self.analytics_repo:
            try:
                readings = self.analytics_repo.get_latest_plant_readings(plant_id, limit=10) or []
            except Exception as exc:
                logger.debug("Failed to get plant readings: %s", exc)

        if readings:
            for metric in metrics:
                for row in readings:
                    if row.get(metric) is not None:
                        try:
                            metrics[metric] = float(row[metric])
                            status[metric] = "ok"
                        except (TypeError, ValueError):
                            pass
                        break

        # Fallback to PlantProfile moisture level when a sensor is configured.
        if metrics["soil_moisture"] is None:
            moisture = plant_info.get("moisture_level")
            if has_sensor and moisture is not None:
                try:
                    metrics["soil_moisture"] = float(moisture)
                    status["soil_moisture"] = "estimated"
                except (TypeError, ValueError):
                    pass

        return metrics, status

    def _get_environmental_metrics(self, unit_id: int) -> dict[str, float | None]:
        """
        Get environmental metrics from unit sensors.

        Returns temperature, humidity, and calculated VPD.
        """
        metrics = {
            "temperature": None,
            "humidity": None,
            "vpd": None,
        }

        if not self.analytics_repo:
            return metrics

        try:
            reading = self.analytics_repo.get_latest_sensor_readings(unit_id=unit_id)
            if not reading:
                return metrics

            temp = reading.get("temperature")
            humidity = reading.get("humidity")

            if temp is not None:
                metrics["temperature"] = float(temp)
            if humidity is not None:
                metrics["humidity"] = float(humidity)

            # Get VPD if present, or calculate
            vpd = reading.get("vpd")
            if vpd is not None:
                metrics["vpd"] = float(vpd)
            elif temp is not None and humidity is not None:
                metrics["vpd"] = self._calculate_vpd(temp, humidity)

        except Exception as e:
            logger.debug("Failed to get environmental metrics: %s", e)

        return metrics

    def _calculate_vpd(self, temperature: float, humidity: float) -> float:
        """Calculate Vapor Pressure Deficit (kPa)."""
        # Saturation vapor pressure (Tetens formula)
        svp = 0.6108 * (10 ** ((7.5 * temperature) / (237.3 + temperature)))
        # Actual vapor pressure
        avp = svp * (humidity / 100)
        # VPD
        return svp - avp

    def _get_thresholds(
        self,
        plant_type: str | None,
        growth_stage: str | None,
    ) -> dict[str, dict[str, float]]:
        """Get thresholds from ThresholdService or defaults."""
        if self.threshold_service and plant_type:
            try:
                thresholds_obj = self.threshold_service.get_thresholds(plant_type, growth_stage)
                return {
                    "temperature": {
                        "optimal": thresholds_obj.temperature,
                        "tolerance": 3.0,
                        "min": thresholds_obj.temperature - 8,
                        "max": thresholds_obj.temperature + 8,
                    },
                    "humidity": {
                        "optimal": thresholds_obj.humidity,
                        "tolerance": 10.0,
                        "min": thresholds_obj.humidity - 25,
                        "max": thresholds_obj.humidity + 20,
                    },
                    "soil_moisture": {
                        "optimal": thresholds_obj.soil_moisture,
                        "tolerance": 15.0,
                        "min": thresholds_obj.soil_moisture - 30,
                        "max": thresholds_obj.soil_moisture + 25,
                    },
                    "ph": self.DEFAULT_THRESHOLDS["ph"],
                    "ec": self.DEFAULT_THRESHOLDS["ec"],
                    "vpd": self.DEFAULT_THRESHOLDS["vpd"],
                }
            except Exception as e:
                logger.debug("Failed to get thresholds: %s", e)

        return self.DEFAULT_THRESHOLDS

    def _calculate_metric_score(
        self,
        value: float,
        threshold: dict[str, float],
    ) -> float:
        """
        Calculate score (0-100) for a metric based on thresholds.

        Uses a bell curve centered on optimal value.
        """
        optimal = threshold.get("optimal", 50.0)
        tolerance = threshold.get("tolerance", 10.0)
        min_val = threshold.get("min", optimal - 30)
        max_val = threshold.get("max", optimal + 30)

        # Out of bounds check
        if value < min_val or value > max_val:
            return 10.0  # Critical

        # Calculate deviation from optimal
        deviation = abs(value - optimal)

        if deviation <= tolerance:
            return 100.0  # Perfect
        elif deviation <= tolerance * 2:
            return 80.0  # Good
        elif deviation <= tolerance * 3:
            return 60.0  # Moderate stress
        elif deviation <= tolerance * 4:
            return 40.0  # Significant stress
        else:
            return 20.0  # Severe stress

    def _determine_health_status(self, overall_score: float) -> str:
        """Determine health status based on overall score."""
        if overall_score < self.STATUS_THRESHOLDS["critical"]:
            return "critical"
        elif overall_score < self.STATUS_THRESHOLDS["stressed"]:
            return "stressed"
        else:
            return "healthy"

    def _get_disease_risk(
        self,
        unit_id: int,
        env_metrics: dict[str, float | None],
    ) -> str:
        """Get disease risk level."""
        # Use disease predictor if available
        if self.disease_predictor:
            try:
                # Create conditions dict for predictor
                conditions = {
                    "temperature": env_metrics.get("temperature", 22.0),
                    "humidity": env_metrics.get("humidity", 60.0),
                }
                risk = self.disease_predictor.predict_risk(unit_id, conditions)
                if risk:
                    return risk.level.value
            except Exception as e:
                logger.debug("Disease predictor failed: %s", e)

        # Fallback to simple humidity-based assessment
        humidity = env_metrics.get("humidity")
        if humidity is not None:
            if humidity > 85:
                return RiskLevel.HIGH.value
            elif humidity > 75:
                return RiskLevel.MODERATE.value
            elif humidity < 35:
                return RiskLevel.LOW.value

        return RiskLevel.MINIMAL.value

    def _determine_nutrient_status(
        self,
        ec: float | None,
        ph: float | None,
    ) -> str:
        """Determine nutrient status from EC and pH."""
        if ec is None and ph is None:
            return "unknown"

        t = self.RECOMMENDATION_THRESHOLDS

        # EC-based assessment
        if ec is not None:
            if ec < t["ec_low"]:
                return "deficient"
            elif ec > t["ec_urgent_high"]:
                return "excess"

        # pH affects nutrient availability
        if ph is not None and (ph < t["ph_urgent_low"] or ph > t["ph_urgent_high"]):
            return "locked_out"  # Nutrients unavailable at extreme pH

        return "optimal"

    # ==================== Recommendation Thresholds (audit item #17) ====================
    # Extracted from _generate_recommendations so they can be overridden or configured.
    # All thresholds are documented with units and rationale.
    RECOMMENDATION_THRESHOLDS: dict[str, Any] = {
        # Soil moisture (%)
        "moisture_critical": 30,  # Below this → urgent "water immediately"
        "moisture_low_offset": 15,  # optimal − offset → "consider watering"
        "moisture_high_offset": 20,  # optimal + offset → "reduce watering"
        # pH (dimensionless, 0-14)
        "ph_urgent_low": 5.5,  # Below → "too acidic"
        "ph_urgent_high": 7.5,  # Above → "too alkaline"
        "ph_monitor_low": 6.0,  # Below → "monitor pH"
        "ph_monitor_high": 7.0,  # Above → "monitor pH"
        # Temperature (°C)
        "temp_urgent_low": 15,  # Below → "too cold"
        "temp_urgent_high": 32,  # Above → "too hot"
        "temp_deviation": 5,  # abs(temp − optimal) > this → recommendation
        # Humidity (%)
        "humidity_urgent_high": 85,  # Above → fungal risk
        "humidity_low": 35,  # Below → "increase humidity"
        "humidity_slightly_high": 75,  # Above → "monitor humidity"
        # VPD (kPa)
        "vpd_low": 0.4,  # Below → "increase VPD"
        "vpd_high": 1.6,  # Above → "decrease VPD"
        # EC (mS/cm)
        "ec_low": 0.8,  # Below → "increase nutrients"
        "ec_urgent_high": 2.5,  # Above → "flush – toxicity risk"
    }

    def _generate_recommendations(
        self,
        scores: dict[str, float],
        raw_values: dict[str, float | None],
        thresholds: dict[str, dict[str, float]],
        health_status: str,
    ) -> tuple[list[str], list[str]]:
        """Generate recommendations and urgent actions."""
        recommendations = []
        urgent_actions = []
        t = self.RECOMMENDATION_THRESHOLDS

        # Soil moisture
        moisture = raw_values.get("soil_moisture")
        scores.get("soil_moisture", 50)
        if moisture is not None:
            optimal = thresholds.get("soil_moisture", {}).get("optimal", 60)
            if moisture < optimal - t["moisture_low_offset"]:
                if moisture < t["moisture_critical"]:
                    urgent_actions.append(f"Water immediately - soil moisture critically low ({moisture:.0f}%)")
                else:
                    recommendations.append(f"Consider watering - soil moisture low ({moisture:.0f}%)")
            elif moisture > optimal + t["moisture_high_offset"]:
                recommendations.append(f"Reduce watering - soil too wet ({moisture:.0f}%)")

        # pH
        ph = raw_values.get("ph")
        if ph is not None:
            if ph < t["ph_urgent_low"]:
                urgent_actions.append(f"Raise pH - too acidic ({ph:.1f})")
            elif ph > t["ph_urgent_high"]:
                urgent_actions.append(f"Lower pH - too alkaline ({ph:.1f})")
            elif ph < t["ph_monitor_low"] or ph > t["ph_monitor_high"]:
                recommendations.append(f"Monitor pH levels ({ph:.1f})")

        # Temperature
        temp = raw_values.get("temperature")
        scores.get("temperature", 50)
        if temp is not None:
            optimal = thresholds.get("temperature", {}).get("optimal", 24)
            if temp < t["temp_urgent_low"]:
                urgent_actions.append(f"Increase temperature - too cold ({temp:.1f}C)")
            elif temp > t["temp_urgent_high"]:
                urgent_actions.append(f"Decrease temperature - too hot ({temp:.1f}C)")
            elif abs(temp - optimal) > t["temp_deviation"]:
                direction = "increase" if temp < optimal else "decrease"
                recommendations.append(f"Consider {direction}ing temperature to {optimal}C")

        # Humidity
        humidity = raw_values.get("humidity")
        if humidity is not None:
            if humidity > t["humidity_urgent_high"]:
                urgent_actions.append(f"Reduce humidity - fungal risk high ({humidity:.0f}%)")
            elif humidity < t["humidity_low"]:
                recommendations.append(f"Increase humidity ({humidity:.0f}%)")
            elif humidity > t["humidity_slightly_high"]:
                recommendations.append(f"Monitor humidity - slightly high ({humidity:.0f}%)")

        # VPD
        vpd = raw_values.get("vpd")
        if vpd is not None:
            if vpd < t["vpd_low"]:
                recommendations.append("Increase VPD - improve air circulation")
            elif vpd > t["vpd_high"]:
                recommendations.append("Decrease VPD - increase humidity or lower temperature")

        # EC
        ec = raw_values.get("ec")
        if ec is not None:
            if ec < t["ec_low"]:
                recommendations.append(f"Increase nutrient concentration (EC: {ec:.2f})")
            elif ec > t["ec_urgent_high"]:
                urgent_actions.append(f"Flush with clean water - nutrient toxicity risk (EC: {ec:.2f})")

        # General status-based recommendations
        if health_status == "critical" and not urgent_actions:
            urgent_actions.append("Plant requires immediate attention")
        elif health_status == "stressed" and not recommendations:
            recommendations.append("Monitor plant closely for changes")
        elif health_status == "healthy" and not recommendations:
            recommendations.append("Continue current care routine")

        return recommendations, urgent_actions

    def _identify_top_issues(self, score: PlantHealthScore) -> list[str]:
        """Identify the top issues from a health score."""
        issues = []

        component_scores = {
            "Soil Moisture": score.soil_moisture_score,
            "pH": score.ph_score,
            "EC/Nutrients": score.ec_score,
            "Temperature": score.temperature_score,
            "Humidity": score.humidity_score,
            "VPD": score.vpd_score,
        }

        # Find low-scoring components
        for name, value in component_scores.items():
            if value < 50:
                issues.append(f"Critical {name}")
            elif value < 70:
                issues.append(f"Low {name}")

        return issues[:3]  # Top 3 issues

    def _get_default_score(self, plant_id: int, unit_id: int) -> PlantHealthScore:
        """Return default score when calculation fails."""
        return PlantHealthScore(
            plant_id=plant_id,
            unit_id=unit_id,
            timestamp=utc_now(),
            overall_score=50.0,
            soil_moisture_score=50.0,
            ph_score=50.0,
            ec_score=50.0,
            temperature_score=50.0,
            humidity_score=50.0,
            vpd_score=50.0,
            health_status="unknown",
            disease_risk="unknown",
            nutrient_status="unknown",
            recommendations=["Unable to calculate health score - insufficient data"],
            urgent_actions=[],
            data_completeness=0.0,
            raw_values={},
            metric_status={
                "soil_moisture": "n/a",
                "ph": "n/a",
                "ec": "n/a",
                "temperature": "n/a",
                "humidity": "n/a",
                "vpd": "n/a",
            },
        )
