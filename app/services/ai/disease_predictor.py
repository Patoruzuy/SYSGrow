"""
Disease Prediction Service
===========================
Predicts disease risk based on environmental patterns and historical observations.

Refactored to use repository pattern with dependency injection.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from app.enums import DiseaseType, RiskLevel
from app.utils.time import utc_now

if TYPE_CHECKING:
    from app.services.ai.model_registry import ModelRegistry
    from app.services.ai.personalized_learning import PersonalizedLearningService
    from infrastructure.database.repositories.ai import AIHealthDataRepository

logger = logging.getLogger(__name__)


@dataclass
class DiseaseRisk:
    """
    Disease risk assessment result.

    Attributes:
        disease_type: Type of disease
        risk_level: Overall risk level
        confidence: Confidence score (0-1)
        risk_score: Numeric risk score (0-100)
        contributing_factors: List of factors increasing risk
        recommendations: List of recommended actions
        predicted_onset_days: Days until likely symptom onset (if high risk)
    """

    disease_type: DiseaseType
    risk_level: RiskLevel
    confidence: float
    risk_score: float
    contributing_factors: list[dict[str, Any]]
    recommendations: list[str]
    predicted_onset_days: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "disease_type": self.disease_type.value,
            "risk_level": self.risk_level.value,
            "confidence": round(self.confidence, 3),
            "risk_score": round(self.risk_score, 1),
            "contributing_factors": self.contributing_factors,
            "recommendations": self.recommendations,
            "predicted_onset_days": self.predicted_onset_days,
        }


class DiseasePredictor:
    """
    Disease prediction service using environmental patterns and historical data.

    Initially uses rule-based logic, enhanced with ML models via ModelRegistry.
    """

    def __init__(
        self,
        repo_health: "AIHealthDataRepository",
        model_registry: "ModelRegistry" | None = None,
        personalized_learning: "PersonalizedLearningService" | None = None,
    ):
        """
        Initialize disease predictor.

        Args:
            repo_health: AI health data repository
            model_registry: Optional model registry for ML models
            personalized_learning: Optional personalized learning service for user-specific adjustments
        """
        self.repo_health = repo_health
        self.model_registry = model_registry
        self.personalized_learning = personalized_learning
        self.model_loaded = False
        self.ml_model = None
        self.ml_scaler = None
        self.ml_feature_columns = None
        self.ml_disease_types = None
        self.risk_thresholds = self._load_risk_thresholds()
        self.historical_stats: dict[str, Any] | None = None

    def load_models(self) -> bool:
        """
        Load disease prediction model.

        Loads trained ML model from registry if available, otherwise uses rule-based prediction.

        Returns:
            True if loaded successfully
        """
        try:
            logger.info("Loading disease prediction model...")

            # Load historical disease statistics
            stats = self.repo_health.get_disease_statistics(days=180)
            self.historical_stats = stats

            # Load ML model if available
            if self.model_registry:
                # Try to load trained disease classifier
                model_data = self.model_registry.load_model("disease_classifier")
                if model_data and isinstance(model_data, dict):
                    self.ml_model = model_data.get("model")
                    self.ml_scaler = model_data.get("scaler")
                    self.ml_feature_columns = model_data.get("feature_columns")
                    self.ml_disease_types = model_data.get("disease_types", [])
                    if self.ml_model:
                        logger.info(
                            f"Loaded ML disease classifier: {len(self.ml_disease_types)} disease types, "
                            f"accuracy={model_data.get('accuracy', 'N/A')}"
                        )
                    else:
                        logger.info("No valid ML model in data, using rule-based prediction")
                else:
                    logger.info("No ML model available, using rule-based prediction")

            self.model_loaded = True
            logger.info("✅ Disease prediction model loaded successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to load disease prediction model: {e}", exc_info=True)
            self.model_loaded = False
            return False

    def predict_disease_risk(
        self,
        unit_id: int,
        plant_type: str,
        growth_stage: str,
        current_conditions: dict[str, float] | None = None,
    ) -> list[DiseaseRisk]:
        """
        Predict disease risks for a plant.

        Args:
            unit_id: Unit ID
            plant_type: Plant type (e.g., 'tomato')
            growth_stage: Current growth stage
            current_conditions: Current environmental conditions

        Returns:
            List of disease risk assessments, sorted by risk score
        """
        if not self.model_loaded:
            logger.warning("Disease prediction model not loaded, auto-loading...")
            self.load_model()

        try:
            risks = []

            # Get recent sensor data
            end_dt = utc_now()
            start_dt = end_dt - timedelta(hours=72)
            end_date = end_dt.isoformat()
            start_date = start_dt.isoformat()

            sensor_df = self.repo_health.get_sensor_time_series(unit_id, start_date, end_date, interval_hours=1)

            if sensor_df.empty:
                logger.warning(f"No sensor data for unit {unit_id}")
                return []

            # Calculate environmental features
            if current_conditions is None:
                current_conditions = {
                    "temperature": (sensor_df["temperature"].iloc[-1] if "temperature" in sensor_df else 0),
                    "humidity": (sensor_df["humidity"].iloc[-1] if "humidity" in sensor_df else 0),
                    "soil_moisture": (sensor_df["soil_moisture"].iloc[-1] if "soil_moisture" in sensor_df else 0),
                }

            # Get historical disease patterns from user's profile
            history_multipliers = self._get_historical_risk_multipliers(unit_id, plant_type)

            # Try ML-based prediction first if available
            ml_risks = self._predict_with_ml(sensor_df, current_conditions, growth_stage)
            if ml_risks:
                # Apply history multipliers to ML predictions
                for risk in ml_risks:
                    disease_key = risk.disease_type.value.split("_")[0]  # Extract base type
                    if disease_key in history_multipliers:
                        risk = self._apply_history_multiplier(
                            risk, history_multipliers[disease_key], "Previous issues in your environment"
                        )
                    risks.append(risk)
                # Still run rule-based to catch things ML might miss
                # but don't add duplicates

            # Assess different disease risks using rules
            fungal_risk = self._assess_fungal_risk(sensor_df, current_conditions, plant_type)
            if fungal_risk and not any(r.disease_type == DiseaseType.FUNGAL for r in risks):
                # Apply historical multiplier if user has had fungal issues before
                if "fungal" in history_multipliers:
                    fungal_risk = self._apply_history_multiplier(
                        fungal_risk, history_multipliers["fungal"], "Previous fungal issues in your environment"
                    )
                risks.append(fungal_risk)

            bacterial_risk = self._assess_bacterial_risk(sensor_df, current_conditions, plant_type)
            if bacterial_risk and not any(r.disease_type == DiseaseType.BACTERIAL for r in risks):
                if "bacterial" in history_multipliers:
                    bacterial_risk = self._apply_history_multiplier(
                        bacterial_risk,
                        history_multipliers["bacterial"],
                        "Previous bacterial issues in your environment",
                    )
                risks.append(bacterial_risk)

            pest_risk = self._assess_pest_risk(sensor_df, current_conditions, growth_stage)
            if pest_risk and not any(r.disease_type == DiseaseType.PEST for r in risks):
                if "pest" in history_multipliers:
                    pest_risk = self._apply_history_multiplier(
                        pest_risk, history_multipliers["pest"], "Previous pest issues in your environment"
                    )
                risks.append(pest_risk)

            nutrient_risk = self._assess_nutrient_risk(sensor_df, current_conditions, plant_type)
            if nutrient_risk and not any(r.disease_type == DiseaseType.NUTRIENT_DEFICIENCY for r in risks):
                if "nutrient" in history_multipliers:
                    nutrient_risk = self._apply_history_multiplier(
                        nutrient_risk, history_multipliers["nutrient"], "Previous nutrient issues in your environment"
                    )
                risks.append(nutrient_risk)

            # Sort by risk score descending
            risks.sort(key=lambda r: r.risk_score, reverse=True)

            return risks

        except Exception as e:
            logger.error(f"Error predicting disease risk: {e}", exc_info=True)
            return []

    def _predict_with_ml(
        self,
        sensor_df,
        current_conditions: dict[str, float],
        growth_stage: str,
    ) -> list[DiseaseRisk]:
        """
        Make disease predictions using the trained ML model.

        Args:
            sensor_df: Recent sensor data DataFrame
            current_conditions: Current environmental conditions
            growth_stage: Current plant growth stage

        Returns:
            List of DiseaseRisk predictions from ML model, empty if no model available
        """
        import numpy as np

        if self.ml_model is None or self.ml_scaler is None:
            return []

        try:
            # Calculate features matching the training format
            growth_stage_map = {
                "seedling": 1,
                "vegetative": 2,
                "flowering": 3,
                "fruiting": 4,
                "harvest": 5,
                "dormant": 0,
            }

            # Calculate 72h averages from sensor data
            avg_temp_72h = (
                sensor_df["temperature"].mean()
                if "temperature" in sensor_df
                else current_conditions.get("temperature", 22)
            )
            avg_humidity_72h = (
                sensor_df["humidity"].mean() if "humidity" in sensor_df else current_conditions.get("humidity", 60)
            )
            avg_soil_72h = (
                sensor_df["soil_moisture"].mean()
                if "soil_moisture" in sensor_df
                else current_conditions.get("soil_moisture", 50)
            )
            humidity_variance = sensor_df["humidity"].std() if "humidity" in sensor_df else 5.0

            # Calculate VPD if not provided
            vpd = current_conditions.get("vpd")
            if vpd is None:
                temp = current_conditions.get("temperature", 22)
                rh = current_conditions.get("humidity", 60)
                # Simple VPD calculation
                svp = 0.6108 * np.exp((17.27 * temp) / (temp + 237.3))
                vpd = svp * (1 - rh / 100)

            # Build feature vector matching training format
            features = np.array(
                [
                    [
                        current_conditions.get("temperature", 22),
                        current_conditions.get("humidity", 60),
                        current_conditions.get("soil_moisture", 50),
                        vpd,
                        avg_temp_72h,
                        avg_humidity_72h,
                        avg_soil_72h,
                        humidity_variance,
                        growth_stage_map.get(growth_stage.lower(), 2),
                        15,  # Default days in stage
                    ]
                ]
            )

            # Scale features
            features_scaled = self.ml_scaler.transform(features)

            # Get prediction and probability
            prediction = self.ml_model.predict(features_scaled)[0]

            # Only return if prediction is not "healthy"
            if prediction == "healthy":
                return []

            # Get probability scores if available
            try:
                probabilities = self.ml_model.predict_proba(features_scaled)[0]
                classes = self.ml_model.classes_
                prob_dict = dict(zip(classes, probabilities))
                confidence = prob_dict.get(prediction, 0.5)
            except Exception:
                confidence = 0.6  # Default confidence for models without predict_proba

            # Convert prediction to DiseaseRisk
            risk_score = confidence * 100

            # Map disease type string to DiseaseType enum
            disease_type_map = {
                "fungal": DiseaseType.FUNGAL,
                "bacterial": DiseaseType.BACTERIAL,
                "pest": DiseaseType.PEST,
                "nutrient": DiseaseType.NUTRIENT_DEFICIENCY,
                "nutrient_deficiency": DiseaseType.NUTRIENT_DEFICIENCY,
                "viral": DiseaseType.VIRAL,
                "environmental": DiseaseType.ENVIRONMENTAL_STRESS,
            }

            disease_type = disease_type_map.get(prediction.lower(), DiseaseType.ENVIRONMENTAL_STRESS)

            # Determine risk level from score
            if risk_score >= 80:
                risk_level = RiskLevel.CRITICAL
            elif risk_score >= 60:
                risk_level = RiskLevel.HIGH
            elif risk_score >= 40:
                risk_level = RiskLevel.MODERATE
            else:
                risk_level = RiskLevel.LOW

            disease_risk = DiseaseRisk(
                disease_type=disease_type,
                risk_level=risk_level,
                confidence=confidence,
                risk_score=risk_score,
                contributing_factors=[
                    {
                        "factor": "ml_prediction",
                        "value": prediction,
                        "confidence": round(confidence, 3),
                        "impact": "high",
                    }
                ],
                recommendations=self._get_recommendations_for_disease(disease_type),
            )

            logger.debug(f"ML disease prediction: {prediction} with confidence {confidence:.3f}")
            return [disease_risk]

        except Exception as e:
            logger.warning(f"ML disease prediction failed, falling back to rules: {e}")
            return []

    def _get_recommendations_for_disease(self, disease_type: DiseaseType) -> list[str]:
        """Get standard recommendations for a disease type."""
        recommendations = {
            DiseaseType.FUNGAL: [
                "Improve air circulation around plants",
                "Reduce humidity if possible",
                "Avoid overhead watering",
                "Apply preventive fungicide treatment",
            ],
            DiseaseType.BACTERIAL: [
                "Remove infected plant material",
                "Avoid working with wet plants",
                "Improve drainage",
                "Apply copper-based treatment if appropriate",
            ],
            DiseaseType.PEST: [
                "Inspect plants thoroughly for pests",
                "Apply appropriate insecticide or use biological controls",
                "Quarantine affected plants",
                "Improve environmental conditions to reduce stress",
            ],
            DiseaseType.NUTRIENT_DEFICIENCY: [
                "Check soil pH levels",
                "Apply balanced fertilizer",
                "Review watering practices",
                "Consider foliar feeding for quick correction",
            ],
            DiseaseType.VIRAL: [
                "Remove and destroy infected plants",
                "Control insect vectors",
                "Disinfect tools between plants",
                "Use virus-resistant varieties",
            ],
            DiseaseType.ENVIRONMENTAL_STRESS: [
                "Review and adjust environmental conditions",
                "Check for temperature or light stress",
                "Ensure proper watering schedule",
                "Reduce any recent environmental changes",
            ],
        }
        return recommendations.get(disease_type, ["Monitor plant health closely"])

    def _assess_fungal_risk(
        self, sensor_df, current_conditions: dict[str, float], plant_type: str
    ) -> DiseaseRisk | None:
        """Assess fungal disease risk based on humidity and temperature patterns."""
        try:
            # High humidity + moderate temps = fungal risk
            avg_humidity = sensor_df["humidity"].mean() if "humidity" in sensor_df else 0
            avg_temp = sensor_df["temperature"].mean() if "temperature" in sensor_df else 0

            current_humidity = current_conditions.get("humidity", 0)
            current_temp = current_conditions.get("temperature", 0)

            risk_score = 0
            factors = []

            # High sustained humidity (>80%)
            if avg_humidity > 80:
                risk_score += 30
                factors.append(
                    {
                        "factor": "high_sustained_humidity",
                        "value": round(avg_humidity, 1),
                        "threshold": 80,
                        "impact": "high",
                    }
                )

            # Current very high humidity (>90%)
            if current_humidity > 90:
                risk_score += 25
                factors.append(
                    {
                        "factor": "very_high_current_humidity",
                        "value": round(current_humidity, 1),
                        "threshold": 90,
                        "impact": "critical",
                    }
                )

            # Moderate temperature range (15-25°C) ideal for many fungi
            if 15 <= avg_temp <= 25:
                risk_score += 20
                factors.append(
                    {
                        "factor": "optimal_fungal_temp_range",
                        "value": round(avg_temp, 1),
                        "range": "15-25°C",
                        "impact": "moderate",
                    }
                )

            # Poor air circulation indicator (very stable humidity)
            humidity_std = sensor_df["humidity"].std() if "humidity" in sensor_df else 10
            if humidity_std < 3:
                risk_score += 15
                factors.append(
                    {
                        "factor": "poor_air_circulation",
                        "value": round(humidity_std, 1),
                        "threshold": "<3",
                        "impact": "moderate",
                    }
                )

            if risk_score < 20:
                risk_level = RiskLevel.LOW
            elif risk_score < 50:
                risk_level = RiskLevel.MODERATE
            elif risk_score < 70:
                risk_level = RiskLevel.HIGH
            else:
                risk_level = RiskLevel.CRITICAL

            recommendations = self._get_fungal_recommendations(risk_level, factors)
            confidence = min(len(factors) * 0.2, 0.9)  # More factors = higher confidence

            predicted_onset = None
            if risk_score >= 70:
                predicted_onset = 3  # 3-5 days for critical
            elif risk_score >= 50:
                predicted_onset = 7  # 7-10 days for high

            return DiseaseRisk(
                disease_type=DiseaseType.FUNGAL,
                risk_level=risk_level,
                confidence=confidence,
                risk_score=risk_score,
                contributing_factors=factors,
                recommendations=recommendations,
                predicted_onset_days=predicted_onset,
            )

        except Exception as e:
            logger.warning(f"Error assessing fungal risk: {e}")
            return None

    def _assess_bacterial_risk(
        self, sensor_df, current_conditions: dict[str, float], plant_type: str
    ) -> DiseaseRisk | None:
        """Assess bacterial disease risk."""
        try:
            avg_temp = sensor_df["temperature"].mean() if "temperature" in sensor_df else 0
            avg_humidity = sensor_df["humidity"].mean() if "humidity" in sensor_df else 0

            risk_score = 0
            factors = []

            # Warm + wet = bacterial risk
            if avg_temp > 25 and avg_humidity > 75:
                risk_score += 40
                factors.append(
                    {
                        "factor": "warm_wet_conditions",
                        "temp": round(avg_temp, 1),
                        "humidity": round(avg_humidity, 1),
                        "impact": "high",
                    }
                )

            # Very warm temperatures (>30°C)
            if avg_temp > 30:
                risk_score += 25
                factors.append(
                    {
                        "factor": "very_high_temperature",
                        "value": round(avg_temp, 1),
                        "threshold": 30,
                        "impact": "moderate",
                    }
                )

            risk_level = self._score_to_risk_level(risk_score)
            recommendations = self._get_bacterial_recommendations(risk_level, factors)
            confidence = min(len(factors) * 0.25, 0.8)

            return DiseaseRisk(
                disease_type=DiseaseType.BACTERIAL,
                risk_level=risk_level,
                confidence=confidence,
                risk_score=risk_score,
                contributing_factors=factors,
                recommendations=recommendations,
            )

        except Exception as e:
            logger.warning(f"Error assessing bacterial risk: {e}")
            return None

    def _assess_pest_risk(
        self, sensor_df, current_conditions: dict[str, float], growth_stage: str
    ) -> DiseaseRisk | None:
        """Assess pest infestation risk."""
        try:
            avg_temp = sensor_df["temperature"].mean() if "temperature" in sensor_df else 0

            risk_score = 0
            factors = []

            # Optimal pest breeding temperature
            if 20 <= avg_temp <= 28:
                risk_score += 30
                factors.append(
                    {
                        "factor": "optimal_pest_temp",
                        "value": round(avg_temp, 1),
                        "range": "20-28°C",
                        "impact": "moderate",
                    }
                )

            # Vulnerable growth stages
            if growth_stage in ["vegetative", "flowering"]:
                risk_score += 20
                factors.append(
                    {
                        "factor": "vulnerable_growth_stage",
                        "stage": growth_stage,
                        "impact": "moderate",
                    }
                )

            risk_level = self._score_to_risk_level(risk_score)
            recommendations = self._get_pest_recommendations(risk_level, factors)
            confidence = 0.6  # Lower confidence without pest traps/monitoring

            return DiseaseRisk(
                disease_type=DiseaseType.PEST,
                risk_level=risk_level,
                confidence=confidence,
                risk_score=risk_score,
                contributing_factors=factors,
                recommendations=recommendations,
            )

        except Exception as e:
            logger.warning(f"Error assessing pest risk: {e}")
            return None

    def _assess_nutrient_risk(
        self, sensor_df, current_conditions: dict[str, float], plant_type: str
    ) -> DiseaseRisk | None:
        """Assess nutrient deficiency risk."""
        try:
            avg_moisture = sensor_df["soil_moisture"].mean() if "soil_moisture" in sensor_df else 0

            risk_score = 0
            factors = []

            # Very low soil moisture can indicate nutrient lockout
            if avg_moisture < 30:
                risk_score += 25
                factors.append(
                    {
                        "factor": "low_soil_moisture",
                        "value": round(avg_moisture, 1),
                        "threshold": 30,
                        "impact": "moderate",
                    }
                )

            # Very high moisture can also cause nutrient issues
            if avg_moisture > 80:
                risk_score += 20
                factors.append(
                    {
                        "factor": "waterlogged_soil",
                        "value": round(avg_moisture, 1),
                        "threshold": 80,
                        "impact": "moderate",
                    }
                )

            if risk_score < 15:
                return None  # Don't report low nutrient risks

            risk_level = self._score_to_risk_level(risk_score)
            recommendations = self._get_nutrient_recommendations(risk_level, factors)
            confidence = 0.5  # Low confidence without soil testing

            return DiseaseRisk(
                disease_type=DiseaseType.NUTRIENT_DEFICIENCY,
                risk_level=risk_level,
                confidence=confidence,
                risk_score=risk_score,
                contributing_factors=factors,
                recommendations=recommendations,
            )

        except Exception as e:
            logger.warning(f"Error assessing nutrient risk: {e}")
            return None

    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Convert risk score to risk level."""
        if score < 20:
            return RiskLevel.LOW
        elif score < 50:
            return RiskLevel.MODERATE
        elif score < 70:
            return RiskLevel.HIGH
        else:
            return RiskLevel.CRITICAL

    def _get_fungal_recommendations(self, risk_level: RiskLevel, factors: list) -> list[str]:
        """Get recommendations for fungal disease prevention."""
        recs = []

        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recs.append("🚨 Reduce humidity immediately - target 60-70%")
            recs.append("Increase air circulation with fans")
            recs.append("Inspect plants closely for early fungal signs (spots, mold)")
            recs.append("Consider preventative fungicide application")
            recs.append("Remove any affected leaves to prevent spread")
        elif risk_level == RiskLevel.MODERATE:
            recs.append("Monitor humidity levels closely")
            recs.append("Ensure good air circulation around plants")
            recs.append("Avoid overhead watering or leaf wetting")
            recs.append("Inspect plants daily for symptoms")
        else:
            recs.append("Continue current environmental management")
            recs.append("Maintain humidity below 75%")

        return recs

    def _get_bacterial_recommendations(self, risk_level: RiskLevel, factors: list) -> list[str]:
        """Get recommendations for bacterial disease prevention."""
        recs = []

        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recs.append("🚨 Lower temperature if possible - target 20-24°C")
            recs.append("Reduce humidity to <70%")
            recs.append("Sanitize all tools and equipment")
            recs.append("Avoid plant handling when conditions are wet")
            recs.append("Inspect for water-soaked lesions or wilting")
        elif risk_level == RiskLevel.MODERATE:
            recs.append("Monitor temperature and humidity")
            recs.append("Ensure proper plant spacing")
            recs.append("Practice good sanitation")

        return recs

    def _get_pest_recommendations(self, risk_level: RiskLevel, factors: list) -> list[str]:
        """Get recommendations for pest management."""
        recs = []

        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recs.append("🚨 Conduct thorough pest inspection (check undersides of leaves)")
            recs.append("Install sticky traps to monitor pest populations")
            recs.append("Consider biological controls or organic pesticides")
            recs.append("Quarantine any suspicious plants")
        elif risk_level == RiskLevel.MODERATE:
            recs.append("Regular visual inspections for pests")
            recs.append("Monitor for pest indicators (webbing, holes, eggs)")
            recs.append("Maintain optimal growing conditions to strengthen plants")

        return recs

    def _get_nutrient_recommendations(self, risk_level: RiskLevel, factors: list) -> list[str]:
        """Get recommendations for nutrient management."""
        recs = []

        if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            recs.append("🚨 Check soil moisture and adjust watering")
            recs.append("Test soil pH and nutrient levels")
            recs.append("Look for visual deficiency symptoms (yellowing, stunting)")
            recs.append("Consider fertigation or foliar feeding")
        elif risk_level == RiskLevel.MODERATE:
            recs.append("Monitor plant growth and coloration")
            recs.append("Maintain consistent soil moisture")
            recs.append("Follow regular fertilization schedule")

        return recs

    def _load_risk_thresholds(self) -> dict[str, Any]:
        """Load disease risk thresholds."""
        return {
            "fungal": {
                "humidity_high": 80,
                "humidity_critical": 90,
                "temp_optimal_min": 15,
                "temp_optimal_max": 25,
            },
            "bacterial": {"temp_high": 25, "temp_critical": 30, "humidity_min": 75},
            "pest": {"temp_optimal_min": 20, "temp_optimal_max": 28},
            "nutrient": {"moisture_low": 30, "moisture_high": 80},
        }

    def _get_historical_risk_multipliers(self, unit_id: int, plant_type: str) -> dict[str, float]:
        """
        Get historical disease risk multipliers from user's environment profile.

        If user has experienced certain disease issues before in their environment,
        we increase the risk score for those disease types.

        Args:
            unit_id: Unit ID
            plant_type: Plant type

        Returns:
            Dict mapping disease type to risk multiplier (e.g., {"fungal": 1.3})
        """
        if not self.personalized_learning:
            return {}

        try:
            profile = self.personalized_learning.get_profile(unit_id)
            if not profile:
                return {}

            multipliers = {}

            # Check challenge areas for disease-related issues
            for challenge in profile.challenge_areas:
                challenge_lower = challenge.lower()
                if "fungal" in challenge_lower or "mold" in challenge_lower or "mildew" in challenge_lower:
                    multipliers["fungal"] = 1.3
                elif "bacterial" in challenge_lower or "rot" in challenge_lower:
                    multipliers["bacterial"] = 1.3
                elif "pest" in challenge_lower or "insect" in challenge_lower or "bug" in challenge_lower:
                    multipliers["pest"] = 1.3
                elif "nutrient" in challenge_lower or "deficiency" in challenge_lower:
                    multipliers["nutrient"] = 1.3

            if multipliers:
                logger.debug(f"Applied historical risk multipliers for unit {unit_id}: {multipliers}")

            return multipliers

        except Exception as e:
            logger.warning(f"Error getting historical risk multipliers: {e}")
            return {}

    def _apply_history_multiplier(self, risk: DiseaseRisk, multiplier: float, reason: str) -> DiseaseRisk:
        """
        Apply a historical multiplier to a disease risk assessment.

        Args:
            risk: Original DiseaseRisk
            multiplier: Risk score multiplier
            reason: Reason for the multiplier

        Returns:
            New DiseaseRisk with adjusted score
        """
        new_score = min(risk.risk_score * multiplier, 100)

        # Add historical factor to contributing factors
        new_factors = list(risk.contributing_factors)
        new_factors.append(
            {"factor": "historical_pattern", "description": reason, "multiplier": multiplier, "impact": "moderate"}
        )

        # Recalculate risk level based on new score
        new_risk_level = self._score_to_risk_level(new_score)

        return DiseaseRisk(
            disease_type=risk.disease_type,
            risk_level=new_risk_level,
            confidence=risk.confidence,
            risk_score=new_score,
            contributing_factors=new_factors,
            recommendations=risk.recommendations,
            predicted_onset_days=risk.predicted_onset_days,
        )

    def is_available(self) -> bool:
        """Check if model is available for predictions."""
        return self.model_loaded
