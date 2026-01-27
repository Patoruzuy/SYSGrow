"""
Plant Health Monitor Service
==============================
Tracks plant health, detects diseases, and correlates with environmental conditions.

Refactored to use repository pattern with dependency injection.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING, Any
from app.utils.time import iso_now
from app.enums import DiseaseType, PlantHealthStatus
from app.domain.plant_health import PlantHealthObservation, EnvironmentalCorrelation

if TYPE_CHECKING:
    from infrastructure.database.repositories.ai import AIHealthDataRepository
    from app.services.application.threshold_service import ThresholdService
    from app.services.application.plant_journal_service import PlantJournalService
    from app.services.ai.recommendation_provider import RecommendationProvider

logger = logging.getLogger(__name__)

# Alias for backward compatibility
HealthStatus = PlantHealthStatus


class PlantHealthMonitor:
    """
    Plant health monitoring service.

    Monitors plant health and correlates issues with environmental conditions
    using plant-specific thresholds.

    Bidirectional Dependencies:
        - journal_service: Set by ContainerBuilder for recording observations
        - threshold_service: Set by ContainerBuilder for optimal conditions
    """

    # Symptom database mapping symptoms to causes
    SYMPTOM_DATABASE = {
        "yellowing_leaves": {
            "likely_causes": ["overwatering", "nitrogen_deficiency", "root_rot"],
            "environmental_factors": ["soil_moisture", "drainage", "nutrition"],
        },
        "brown_spots": {
            "likely_causes": ["fungal_infection", "bacterial_spot", "nutrient_burn"],
            "environmental_factors": ["humidity", "air_circulation", "nutrition"],
        },
        "wilting": {
            "likely_causes": ["underwatering", "root_damage", "heat_stress"],
            "environmental_factors": ["soil_moisture", "temperature", "humidity"],
        },
        "stunted_growth": {
            "likely_causes": ["poor_lighting", "nutrient_deficiency", "root_bound"],
            "environmental_factors": ["lux", "nutrition", "space"],
        },
        "leaf_curl": {
            "likely_causes": ["heat_stress", "pest_damage", "overwatering"],
            "environmental_factors": ["temperature", "humidity", "soil_moisture"],
        },
        "white_powdery_coating": {
            "likely_causes": ["powdery_mildew", "high_humidity"],
            "environmental_factors": ["humidity", "air_circulation", "temperature"],
        },
        "webbing_on_leaves": {
            "likely_causes": ["spider_mites", "low_humidity"],
            "environmental_factors": ["humidity", "temperature", "air_circulation"],
        },
        "holes_in_leaves": {
            "likely_causes": ["caterpillars", "beetles", "slugs"],
            "environmental_factors": ["pest_control", "cleanliness"],
        },
    }

    # Treatment recommendations by symptom
    TREATMENT_MAP = {
        "yellowing_leaves": [
            "Check drainage and reduce watering if overwatered",
            "Apply nitrogen fertilizer if deficiency suspected",
            "Inspect roots for rot and trim if necessary",
        ],
        "brown_spots": [
            "Improve air circulation",
            "Reduce humidity if too high",
            "Apply fungicide if fungal infection suspected",
            "Isolate plant to prevent spread",
        ],
        "wilting": [
            "Check soil moisture and water if dry",
            "Reduce temperature if heat stress suspected",
            "Inspect roots for damage",
        ],
        "white_powdery_coating": [
            "Reduce humidity",
            "Improve air circulation",
            "Apply fungicide for powdery mildew",
            "Remove affected leaves",
        ],
        "webbing_on_leaves": [
            "Increase humidity",
            "Apply miticide for spider mites",
            "Improve air circulation",
            "Regularly mist leaves",
        ],
    }

    def __init__(
        self,
        repo_health: "AIHealthDataRepository",
        journal_service: Optional["PlantJournalService"] = None,
        threshold_service: Optional["ThresholdService"] = None,
    ):
        """
        Initialize plant health monitor.

        Args:
            repo_health: AI health data repository (for AI-specific correlation data)
            journal_service: Plant journal service for recording observations
            threshold_service: Optional threshold service for plant-specific thresholds
        """
        self.repo_health = repo_health
        self.journal_service = journal_service
        self.threshold_service = threshold_service

    def record_observation(
        self, observation: PlantHealthObservation
    ) -> Optional[int]:
        """
        Record a plant health observation.
        
        Uses PlantJournalService as single source of truth, then performs AI analysis.
        
        Args:
            observation: Health observation to record
            
        Returns:
            observation_id if successful, None otherwise
        """
        try:
            if not self.journal_service:
                logger.warning("No journal service configured, cannot record observation")
                return None

            # Delegate to PlantJournalService for storage with ALL fields
            entry_id = self.journal_service.record_health_observation(
                plant_id=observation.plant_id or 0,
                unit_id=observation.unit_id,
                health_status=observation.health_status.value,
                symptoms=observation.symptoms,
                severity_level=observation.severity_level,
                disease_type=observation.disease_type.value if observation.disease_type else None,
                affected_parts=observation.affected_parts,
                environmental_factors=observation.environmental_factors,
                treatment_applied=observation.treatment_applied,
                plant_type=observation.plant_type,
                growth_stage=observation.growth_stage,
                notes=observation.notes,
                image_path=observation.image_path,
                user_id=observation.user_id,
                observation_date=observation.observation_date.isoformat() if observation.observation_date else None
            )

            if entry_id:
                # Perform AI-specific analysis
                self.analyze_environmental_correlation(observation)
                logger.info(f"Recorded health observation via journal: {entry_id}")

            return entry_id

        except Exception as e:
            logger.error(f"Failed to record health observation: {e}", exc_info=True)
            return None

    def analyze_environmental_correlation(
        self, observation: PlantHealthObservation
    ) -> List[EnvironmentalCorrelation]:
        """
        Analyze correlation between plant health issues and environmental conditions.
        
        Args:
            observation: Health observation to analyze
            
            Returns:
                    List[EnvironmentalCorrelation]: a list of EnvironmentalCorrelation dataclass
                    instances describing how each environmental factor relates to the
                    reported plant health. Each EnvironmentalCorrelation contains:

                        - factor_name (str): the name of the environmental factor (e.g.
                            "temperature", "humidity", "soil_moisture").
                        - correlation_strength (float): a value in [0.0, 1.0] that quantifies
                            how strongly deviations from the recommended range are associated
                            with the observed health issue. 0.0 means no correlation; 1.0
                            indicates a strong correlation.
                        - confidence_level (float): a value in [0.0, 1.0] representing the
                            confidence of the association, increased when the factor is known
                            to be related to the observed symptoms.
                        - recommended_range (Tuple[float, float]): the optimal range for the
                            factor (lower_bound, upper_bound) used to compute deviation.
                        - current_value (float): the averaged recent measured value for the
                            factor from sensors.
                        - trend (str): one of 'improving', 'worsening', or 'stable', indicating
                            the short-term direction of the factor based on recent readings.

            Notes:
                    The method also persists the computed correlations to a local
                    JSONL file for ML training and debugging purposes.
            """
        correlations = []

        try:
            # Get environmental thresholds (plant-specific if available)
            thresholds = self._get_thresholds(observation)

            # Get recent environmental data
            env_data = self._get_recent_environmental_data(observation.unit_id)

            if not env_data:
                logger.warning(f"No environmental data for unit {observation.unit_id}")
                return correlations

            # Analyze each environmental factor
            for factor, current_value in env_data.items():
                if factor in thresholds:
                    threshold = thresholds[factor]
                    optimal_range = threshold.get("optimal_range", (0, 100))

                    # Calculate correlation strength
                    if optimal_range[0] <= current_value <= optimal_range[1]:
                        correlation_strength = 0.0
                    else:
                        # Calculate deviation from optimal
                        if current_value < optimal_range[0]:
                            deviation = (optimal_range[0] - current_value) / optimal_range[0]
                        else:
                            deviation = (current_value - optimal_range[1]) / optimal_range[1]

                        correlation_strength = min(
                            1.0, deviation * (observation.severity_level / 5.0)
                        )

                    correlation = EnvironmentalCorrelation(
                        factor_name=factor,
                        correlation_strength=correlation_strength,
                        confidence_level=self._calculate_confidence(
                            factor, observation.symptoms
                        ),
                        recommended_range=optimal_range,
                        current_value=current_value,
                        trend=self._analyze_trend(observation.unit_id, factor),
                    )

                    correlations.append(correlation)

            # Store correlations for ML training
            self._store_correlations(observation, correlations)

        except Exception as e:
            logger.error(f"Failed to analyze environmental correlation: {e}", exc_info=True)

        return correlations

    def get_health_recommendations(
        self,
        unit_id: int,
        plant_type: Optional[str] = None,
        growth_stage: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get health recommendations based on recent observations.
        
        Args:
            unit_id: Unit ID
            plant_type: Optional plant type
            growth_stage: Optional growth stage
            
        Returns:
            Dictionary with health status, recommendations, and trends
        """
        try:
            # Get recent observations
            recent_observations = self.repo_health.get_recent_observations(
                unit_id, limit=20, days=7
            )

            if not recent_observations:
                return {"status": "healthy", "recommendations": []}

            # Parse JSON fields
            for obs in recent_observations:
                if isinstance(obs.get("symptoms"), str):
                    obs["symptoms"] = json.loads(obs["symptoms"])
                if isinstance(obs.get("affected_parts"), str):
                    obs["affected_parts"] = json.loads(obs["affected_parts"])
                if isinstance(obs.get("environmental_factors"), str):
                    obs["environmental_factors"] = json.loads(obs["environmental_factors"])

            # Analyze symptom patterns
            symptom_counts = {}
            for obs in recent_observations:
                for symptom in obs.get("symptoms", []):
                    symptom_counts[symptom] = symptom_counts.get(symptom, 0) + 1

            # Generate recommendations
            recommendations = []
            for symptom, count in symptom_counts.items():
                if count >= 2 and symptom in self.SYMPTOM_DATABASE:
                    symptom_info = self.SYMPTOM_DATABASE[symptom]
                    recommendations.append({
                        "issue": symptom,
                        "frequency": count,
                        "likely_causes": symptom_info["likely_causes"],
                        "recommended_actions": self.TREATMENT_MAP.get(
                            symptom, ["Consult plant care specialist"]
                        ),
                    })

            # Get environmental recommendations
            env_data = self._get_recent_environmental_data(unit_id)
            env_recommendations = self._analyze_environmental_issues(
                env_data, plant_type, growth_stage
            )

            return {
                "status": recent_observations[0]["health_status"],
                "plant_type": plant_type,
                "growth_stage": growth_stage,
                "symptom_recommendations": recommendations,
                "environmental_recommendations": env_recommendations,
                "trend": self._analyze_health_trend(unit_id),
            }

        except Exception as e:
            logger.error(f"Failed to get health recommendations: {e}", exc_info=True)
            return {"status": "unknown", "recommendations": []}

    def _get_thresholds(self, observation: PlantHealthObservation) -> Dict[str, Dict[str, Any]]:
        """Get environmental thresholds for observation."""
        if self.threshold_service and observation.plant_type:
            thresholds_obj = self.threshold_service.get_thresholds(
                observation.plant_type, observation.growth_stage
            )
            return thresholds_obj.to_dict()
        
        # Generic fallback thresholds
        return {
            "temperature": {"optimal_range": (20, 25)},
            "humidity": {"optimal_range": (50, 70)},
            "soil_moisture": {"optimal_range": (60, 80)},
        }

    def _get_recent_environmental_data(
        self, unit_id: int, hours: int = 24
    ) -> Dict[str, float]:
        """Get recent environmental data averages."""
        try:
            end_time = iso_now()
            start_time = (datetime.fromisoformat(end_time) - timedelta(hours=hours)).isoformat()

            metrics = ["temperature", "humidity", "voc", "co2", "lux"]
            result = {}

            for metric in metrics:
                readings = self.repo_health.get_sensor_readings_for_period(
                    unit_id, start_time, end_time, metric
                )
                if readings:
                    avg = sum(r[1] for r in readings if r[1] is not None) / len(readings)
                    result[metric] = avg
                else:
                    result[metric] = 0.0

            return result

        except Exception as e:
            logger.error(f"Failed to get environmental data: {e}", exc_info=True)
            return {}

    def _calculate_confidence(self, factor: str, symptoms: List[str]) -> float:
        """Calculate confidence level for environmental factor correlation."""
        confidence = 0.5

        for symptom in symptoms:
            if symptom in self.SYMPTOM_DATABASE:
                if factor in self.SYMPTOM_DATABASE[symptom]["environmental_factors"]:
                    confidence += 0.2

        return min(1.0, confidence)

    def _analyze_trend(self, unit_id: int, factor: str, hours: int = 72) -> str:
        """Analyze trend for an environmental factor."""
        try:
            end_time = iso_now()
            start_time = (datetime.fromisoformat(end_time) - timedelta(hours=hours)).isoformat()

            readings = self.repo_health.get_sensor_readings_for_period(
                unit_id, start_time, end_time, factor
            )

            if len(readings) < 2:
                return "stable"

            quarter_size = len(readings) // 4
            if quarter_size == 0:
                return "stable"

            first_avg = sum(r[1] for r in readings[:quarter_size] if r[1]) / quarter_size
            last_avg = sum(r[1] for r in readings[-quarter_size:] if r[1]) / quarter_size

            change_percent = ((last_avg - first_avg) / first_avg * 100) if first_avg > 0 else 0

            if change_percent > 5:
                return "worsening" if factor in ["temperature", "humidity"] and change_percent > 10 else "improving"
            elif change_percent < -5:
                return "improving" if factor in ["temperature", "humidity"] and change_percent < -10 else "worsening"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"Failed to analyze trend: {e}", exc_info=True)
            return "stable"

    def _store_correlations(
        self, observation: PlantHealthObservation, correlations: List[EnvironmentalCorrelation]
    ):
        """Store environmental correlations for ML training via repository."""
        try:
            if not self.repo_health:
                logger.warning("No repository available for correlation storage")
                return

            correlation_dicts = [
                {
                    "factor_name": corr.factor_name,
                    "correlation_strength": corr.correlation_strength,
                    "confidence_level": corr.confidence_level,
                    "recommended_range": list(corr.recommended_range),
                    "current_value": corr.current_value,
                    "trend": corr.trend,
                }
                for corr in correlations
            ]

            self.repo_health.save_environmental_correlation(
                unit_id=observation.unit_id,
                health_status=observation.health_status.value,
                severity=observation.severity_level,
                correlations=correlation_dicts,
                observation_date=observation.observation_date.isoformat() if observation.observation_date else None,
            )

        except Exception as e:
            logger.error(f"Failed to store correlations: {e}", exc_info=True)

    def _analyze_environmental_issues(
        self, env_data: Dict[str, float], plant_type: Optional[str], growth_stage: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Analyze environmental conditions and provide recommendations."""
        recommendations = []

        if self.threshold_service and plant_type:
            thresholds_obj = self.threshold_service.get_thresholds(plant_type, growth_stage)
        else:
            thresholds_obj = self.threshold_service.generic_thresholds if self.threshold_service else None

        if not thresholds_obj:
            return recommendations

        for factor, value in env_data.items():
            optimal_value = getattr(thresholds_obj, factor, None)
            if optimal_value is not None:
                tolerance = optimal_value * 0.1
                optimal_range = (optimal_value - tolerance, optimal_value + tolerance)

                if value < optimal_range[0]:
                    recommendations.append({
                        "factor": factor,
                        "issue": f"{factor} too low",
                        "current_value": value,
                        "recommended_range": optimal_range,
                        "action": f"Increase {factor}",
                        "plant_specific": plant_type is not None,
                    })
                elif value > optimal_range[1]:
                    recommendations.append({
                        "factor": factor,
                        "issue": f"{factor} too high",
                        "current_value": value,
                        "recommended_range": optimal_range,
                        "action": f"Decrease {factor}",
                        "plant_specific": plant_type is not None,
                    })

        return recommendations

    def _analyze_health_trend(self, unit_id: int, days: int = 30) -> str:
        """Analyze health trend over time."""
        try:
            observations = self.repo_health.get_recent_observations(unit_id, limit=10, days=days)

            if len(observations) < 2:
                return "insufficient_data"

            recent_severities = [obs["severity_level"] for obs in observations[:5]]
            older_severities = [obs["severity_level"] for obs in observations[5:10]]

            if not older_severities:
                return "insufficient_data"

            recent_avg = sum(recent_severities) / len(recent_severities)
            older_avg = sum(older_severities) / len(older_severities)

            if recent_avg < older_avg - 0.5:
                return "improving"
            elif recent_avg > older_avg + 0.5:
                return "declining"
            else:
                return "stable"

        except Exception as e:
            logger.error(f"Failed to analyze health trend: {e}", exc_info=True)
            return "unknown"
