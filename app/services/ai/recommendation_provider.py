"""
Recommendation Provider Interface
=================================
Abstract interface for plant health recommendation providers.

Supports pluggable backends:
- RuleBasedRecommendationProvider (default, uses SYMPTOM_DATABASE)
- LLMRecommendationProvider (future, EXAONE 4.0 1.2B or similar)

The provider interface allows for easy swapping of recommendation
engines without changing the consumer code.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from app.domain.irrigation import IrrigationPrediction

logger = logging.getLogger(__name__)


@dataclass
class RecommendationContext:
    """Context for generating recommendations."""

    plant_id: int
    unit_id: int
    plant_type: Optional[str] = None
    growth_stage: Optional[str] = None
    symptoms: List[str] = field(default_factory=list)
    health_status: Optional[str] = None
    severity_level: int = 1
    environmental_data: Optional[Dict[str, float]] = None
    recent_observations: Optional[List[Dict]] = None
    nutrient_history: Optional[List[Dict]] = None
    irrigation_prediction: Optional["IrrigationPrediction"] = None


@dataclass
class Recommendation:
    """A single recommendation."""

    action: str  # What to do
    priority: str  # "urgent", "high", "medium", "low"
    category: str  # "watering", "nutrition", "environment", "pest", "disease"
    confidence: float  # 0.0 - 1.0
    rationale: Optional[str] = None  # Why this is recommended
    source: str = "rule_based"  # "rule_based", "ml", "llm"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action,
            "priority": self.priority,
            "category": self.category,
            "confidence": round(self.confidence, 2),
            "rationale": self.rationale,
            "source": self.source,
        }


class RecommendationProvider(ABC):
    """
    Abstract base class for recommendation providers.

    Implementations can use rules, ML models, or LLMs to generate
    plant care recommendations based on context.
    """

    @abstractmethod
    def get_recommendations(
        self,
        context: RecommendationContext
    ) -> List[Recommendation]:
        """
        Generate recommendations based on context.

        Args:
            context: RecommendationContext with plant state

        Returns:
            List of Recommendation objects
        """
        pass

    @abstractmethod
    def get_treatment_suggestions(
        self,
        symptoms: List[str],
        context: Optional[RecommendationContext] = None
    ) -> List[Recommendation]:
        """
        Get treatment suggestions for specific symptoms.

        Args:
            symptoms: List of observed symptoms
            context: Optional additional context

        Returns:
            List of treatment Recommendation objects
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return provider identifier."""
        pass

    @property
    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is available/ready."""
        pass


class RuleBasedRecommendationProvider(RecommendationProvider):
    """
    Rule-based recommendation provider using predefined symptom database.

    This is the default provider that works without ML models or external APIs.
    Uses SYMPTOM_DATABASE and TREATMENT_MAP for rule-based recommendations.
    """

    # Symptom database with likely causes and environmental factors
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
        "drooping_leaves": {
            "likely_causes": ["underwatering", "overwatering", "temperature_stress"],
            "environmental_factors": ["soil_moisture", "temperature", "root_health"],
        },
        "pale_leaves": {
            "likely_causes": ["iron_deficiency", "low_light", "nutrient_lockout"],
            "environmental_factors": ["nutrition", "lux", "ph"],
        },
        "crispy_leaf_edges": {
            "likely_causes": ["low_humidity", "salt_buildup", "underwatering"],
            "environmental_factors": ["humidity", "nutrition", "soil_moisture"],
        },
        "black_spots": {
            "likely_causes": ["fungal_disease", "overwatering", "poor_drainage"],
            "environmental_factors": ["humidity", "drainage", "air_circulation"],
        },
    }

    # Treatment recommendations mapped to symptoms
    TREATMENT_MAP = {
        "yellowing_leaves": [
            "Check drainage and reduce watering if overwatered",
            "Apply nitrogen fertilizer if deficiency suspected",
            "Inspect roots for rot and trim if necessary",
            "Ensure proper light levels for photosynthesis",
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
            "Provide shade during peak sun hours",
        ],
        "white_powdery_coating": [
            "Reduce humidity below 60%",
            "Improve air circulation with fans",
            "Apply fungicide for powdery mildew",
            "Remove and dispose of affected leaves",
        ],
        "webbing_on_leaves": [
            "Increase humidity to discourage spider mites",
            "Apply miticide or neem oil treatment",
            "Improve air circulation",
            "Regularly mist leaves with water",
        ],
        "stunted_growth": [
            "Increase light intensity or duration",
            "Check and adjust nutrient levels",
            "Repot if plant is root-bound",
            "Ensure temperature is within optimal range",
        ],
        "leaf_curl": [
            "Check for pest infestation",
            "Reduce temperature if heat stressed",
            "Adjust watering schedule",
            "Check for herbicide drift",
        ],
        "holes_in_leaves": [
            "Inspect for caterpillars and remove manually",
            "Apply organic pest control (BT spray)",
            "Set up slug traps if slugs suspected",
            "Improve garden cleanliness",
        ],
        "drooping_leaves": [
            "Check soil moisture - water if dry",
            "Reduce watering if soil is soggy",
            "Provide temperature stability",
            "Check for root health issues",
        ],
        "pale_leaves": [
            "Apply iron supplement or chelated micronutrients",
            "Increase light exposure",
            "Check and adjust pH levels",
            "Ensure balanced nutrient solution",
        ],
        "crispy_leaf_edges": [
            "Increase humidity with humidifier or misting",
            "Flush soil to remove salt buildup",
            "Increase watering frequency slightly",
            "Move away from heat sources",
        ],
        "black_spots": [
            "Remove affected leaves immediately",
            "Reduce watering frequency",
            "Improve drainage in container",
            "Apply copper-based fungicide",
        ],
    }

    def __init__(self):
        pass

    @property
    def provider_name(self) -> str:
        return "rule_based"

    @property
    def is_available(self) -> bool:
        return True  # Always available

    def get_recommendations(
        self,
        context: RecommendationContext
    ) -> List[Recommendation]:
        """Generate rule-based recommendations from symptoms and context."""
        recommendations = []

        if context.irrigation_prediction:
            recommendations.extend(self._get_irrigation_recommendations(context))

        if context.symptoms:
            # Analyze each symptom
            for symptom in context.symptoms:
                symptom_lower = symptom.lower().replace(" ", "_")
                if symptom_lower in self.SYMPTOM_DATABASE:
                    symptom_info = self.SYMPTOM_DATABASE[symptom_lower]

                    # Add diagnosis recommendations
                    for cause in symptom_info["likely_causes"][:2]:  # Top 2 causes
                        recommendations.append(Recommendation(
                            action=f"Investigate {cause.replace('_', ' ')}",
                            priority="high" if context.severity_level >= 3 else "medium",
                            category="diagnosis",
                            confidence=0.6,
                            rationale=f"Symptom '{symptom}' is often caused by {cause.replace('_', ' ')}",
                            source="rule_based"
                        ))

            # Add treatment recommendations
            treatment_recs = self.get_treatment_suggestions(
                context.symptoms, context
            )
            recommendations.extend(treatment_recs)

        # Add environmental recommendations if data available
        if context.environmental_data:
            env_recs = self._check_environmental_conditions(context)
            recommendations.extend(env_recs)

        # If no recommendations, add general guidance
        if not recommendations:
            if context.health_status == "healthy":
                recommendations.append(Recommendation(
                    action="Continue current care routine",
                    priority="low",
                    category="maintenance",
                    confidence=0.8,
                    rationale="No issues detected",
                    source="rule_based"
                ))
            else:
                recommendations.append(Recommendation(
                    action="Monitor plant closely for changes",
                    priority="medium",
                    category="monitoring",
                    confidence=0.7,
                    rationale="Status requires attention",
                    source="rule_based"
                ))

        return recommendations[:6]  # Limit to top 6 recommendations

    def get_treatment_suggestions(
        self,
        symptoms: List[str],
        context: Optional[RecommendationContext] = None
    ) -> List[Recommendation]:
        """Get treatment suggestions for specific symptoms."""
        suggestions = []

        for symptom in symptoms:
            symptom_lower = symptom.lower().replace(" ", "_")
            if symptom_lower in self.TREATMENT_MAP:
                treatments = self.TREATMENT_MAP[symptom_lower]
                for idx, treatment in enumerate(treatments[:3]):  # Top 3 treatments
                    suggestions.append(Recommendation(
                        action=treatment,
                        priority="high" if idx == 0 else "medium",
                        category="treatment",
                        confidence=0.7 - (idx * 0.1),  # First is most confident
                        rationale=f"Recommended treatment for {symptom.replace('_', ' ')}",
                        source="rule_based"
                    ))

        return suggestions

    def _get_irrigation_recommendations(
        self,
        context: RecommendationContext
    ) -> List[Recommendation]:
        """Generate irrigation recommendations from ML predictions if available."""
        recommendations: List[Recommendation] = []
        prediction = context.irrigation_prediction
        if not prediction:
            return recommendations

        def _get(obj: Any, name: str, default: Any = None) -> Any:
            if obj is None:
                return default
            if isinstance(obj, dict):
                return obj.get(name, default)
            return getattr(obj, name, default)

        threshold = _get(prediction, "threshold")
        if threshold:
            direction = _get(threshold, "adjustment_direction")
            amount = float(_get(threshold, "adjustment_amount", 0.0) or 0.0)
            optimal = _get(threshold, "optimal_threshold")
            confidence = float(_get(threshold, "confidence", 0.0) or 0.0)
            if direction and direction != "maintain" and amount > 2.0 and optimal is not None:
                recommendations.append(Recommendation(
                    action=f"Adjust soil moisture threshold to {float(optimal):.1f}%",
                    priority="high" if amount >= 5.0 else "medium",
                    category="watering",
                    confidence=min(1.0, confidence),
                    rationale=f"Model suggests {direction} by {amount:.1f}%",
                    source="ml",
                ))

        response = _get(prediction, "user_response")
        if response:
            most_likely = _get(response, "most_likely")
            cancel_prob = float(_get(response, "cancel_probability", 0.0) or 0.0)
            delay_prob = float(_get(response, "delay_probability", 0.0) or 0.0)
            confidence = float(_get(response, "confidence", 0.0) or 0.0)
            if most_likely == "cancel" and cancel_prob > 0.3:
                recommendations.append(Recommendation(
                    action="Review irrigation settings to reduce cancellations",
                    priority="medium",
                    category="watering",
                    confidence=min(1.0, max(confidence, cancel_prob)),
                    rationale=f"Cancel probability is {cancel_prob:.2f}",
                    source="ml",
                ))
            elif most_likely == "delay" and delay_prob > 0.4:
                recommendations.append(Recommendation(
                    action="Adjust irrigation timing to match user preferences",
                    priority="medium",
                    category="watering",
                    confidence=min(1.0, max(confidence, delay_prob)),
                    rationale=f"Delay probability is {delay_prob:.2f}",
                    source="ml",
                ))

        duration = _get(prediction, "duration")
        if duration:
            recommended = _get(duration, "recommended_seconds")
            current_default = _get(duration, "current_default_seconds")
            confidence = float(_get(duration, "confidence", 0.0) or 0.0)
            if recommended is not None and current_default is not None:
                diff = abs(int(recommended) - int(current_default))
                if diff > 30 and confidence > 0.5:
                    direction = "Increase" if int(recommended) > int(current_default) else "Reduce"
                    recommendations.append(Recommendation(
                        action=f"{direction} irrigation duration to {int(recommended)}s",
                        priority="high" if diff >= 60 else "medium",
                        category="watering",
                        confidence=min(1.0, confidence),
                        rationale=f"Recommended change is {diff}s",
                        source="ml",
                    ))

        timing = _get(prediction, "timing")
        if timing:
            preferred_time = _get(timing, "preferred_time")
            avoid_times = _get(timing, "avoid_times") or []
            confidence = float(_get(timing, "confidence", 0.0) or 0.0)
            if preferred_time and avoid_times and confidence > 0.5:
                avoid_preview = ", ".join(list(avoid_times)[:3])
                recommendations.append(Recommendation(
                    action=f"Schedule irrigation near {preferred_time} and avoid {avoid_preview}",
                    priority="medium",
                    category="watering",
                    confidence=min(1.0, confidence),
                    rationale="Timing model suggests preferred hours",
                    source="ml",
                ))

        next_irrigation = _get(prediction, "next_irrigation")
        if next_irrigation:
            predicted_time = _get(next_irrigation, "predicted_time")
            hours_until = _get(next_irrigation, "hours_until_threshold")
            confidence = float(_get(next_irrigation, "confidence", 0.0) or 0.0)
            if predicted_time and confidence > 0.5:
                eta = (
                    f"{float(hours_until):.1f}h"
                    if hours_until is not None
                    else "soon"
                )
                recommendations.append(Recommendation(
                    action=f"Next irrigation expected in {eta} (around {predicted_time})",
                    priority="low",
                    category="watering",
                    confidence=min(1.0, confidence),
                    rationale="Dry-down model projection",
                    source="ml",
                ))

        return recommendations

    def _check_environmental_conditions(
        self,
        context: RecommendationContext
    ) -> List[Recommendation]:
        """Check environmental conditions and generate recommendations."""
        recommendations = []
        env = context.environmental_data or {}

        # Temperature checks
        temp = env.get("temperature")
        if temp is not None:
            if temp > 32:
                recommendations.append(Recommendation(
                    action="Reduce temperature - risk of heat stress",
                    priority="high",
                    category="environment",
                    confidence=0.8,
                    rationale=f"Temperature ({temp}°C) exceeds safe limit",
                    source="rule_based"
                ))
            elif temp < 15:
                recommendations.append(Recommendation(
                    action="Increase temperature - risk of cold stress",
                    priority="high",
                    category="environment",
                    confidence=0.8,
                    rationale=f"Temperature ({temp}°C) below optimal range",
                    source="rule_based"
                ))

        # Humidity checks
        humidity = env.get("humidity")
        if humidity is not None:
            if humidity > 80:
                recommendations.append(Recommendation(
                    action="Reduce humidity to prevent fungal issues",
                    priority="medium",
                    category="environment",
                    confidence=0.7,
                    rationale=f"Humidity ({humidity}%) is too high",
                    source="rule_based"
                ))
            elif humidity < 30:
                recommendations.append(Recommendation(
                    action="Increase humidity to prevent leaf damage",
                    priority="medium",
                    category="environment",
                    confidence=0.7,
                    rationale=f"Humidity ({humidity}%) is too low",
                    source="rule_based"
                ))

        # Soil moisture checks
        soil_moisture = env.get("soil_moisture")
        if soil_moisture is not None:
            if soil_moisture < 25:
                recommendations.append(Recommendation(
                    action="Water immediately - soil is very dry",
                    priority="urgent",
                    category="watering",
                    confidence=0.9,
                    rationale=f"Soil moisture ({soil_moisture}%) critically low",
                    source="rule_based"
                ))
            elif soil_moisture > 85:
                recommendations.append(Recommendation(
                    action="Reduce watering - risk of root rot",
                    priority="high",
                    category="watering",
                    confidence=0.8,
                    rationale=f"Soil moisture ({soil_moisture}%) too high",
                    source="rule_based"
                ))

        return recommendations


class LLMRecommendationProvider(RecommendationProvider):
    """
    LLM-based recommendation provider using local models.

    Designed for future integration with EXAONE 4.0 1.2B or similar
    small language models that can run on Raspberry Pi.

    Falls back to rule-based if LLM not available.

    Configuration via environment:
        - LLM_PROVIDER_ENABLED: "true" to enable
        - LLM_MODEL_PATH: Path to model weights
        - LLM_MAX_TOKENS: Max generation tokens (default 256)
    """

    def __init__(
        self,
        fallback_provider: Optional[RecommendationProvider] = None,
        model_path: Optional[str] = None,
        enabled: bool = False
    ):
        """
        Initialize LLM provider.

        Args:
            fallback_provider: Provider to use when LLM unavailable
            model_path: Path to LLM model weights
            enabled: Whether LLM is enabled
        """
        self._fallback = fallback_provider or RuleBasedRecommendationProvider()
        self._model_path = model_path
        self._enabled = enabled
        self._model = None
        self._tokenizer = None

    @property
    def provider_name(self) -> str:
        return "llm"

    @property
    def is_available(self) -> bool:
        if not self._enabled:
            return False
        return self._model is not None

    def load_model(self) -> bool:
        """
        Load LLM model.

        Future implementation for EXAONE 4.0 1.2B or similar:

        ```python
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self._tokenizer = AutoTokenizer.from_pretrained(self._model_path)
        self._model = AutoModelForCausalLM.from_pretrained(
            self._model_path,
            device_map="auto",
            torch_dtype=torch.float16  # For Raspberry Pi memory
        )
        return True
        ```

        Returns:
            True if model loaded successfully
        """
        if not self._enabled or not self._model_path:
            return False

        # Placeholder - model loading to be implemented when ready
        logger.info(f"LLM model loading not yet implemented (path: {self._model_path})")
        return False

    def get_recommendations(
        self,
        context: RecommendationContext
    ) -> List[Recommendation]:
        """Generate LLM-powered recommendations."""
        if not self.is_available:
            logger.debug("LLM not available, using fallback provider")
            return self._fallback.get_recommendations(context)

        # Future: LLM inference
        # prompt = self._build_prompt(context)
        # response = self._generate(prompt)
        # return self._parse_response(response)

        return self._fallback.get_recommendations(context)

    def get_treatment_suggestions(
        self,
        symptoms: List[str],
        context: Optional[RecommendationContext] = None
    ) -> List[Recommendation]:
        """Get LLM-powered treatment suggestions."""
        if not self.is_available:
            return self._fallback.get_treatment_suggestions(symptoms, context)

        # Future: LLM inference for treatments
        return self._fallback.get_treatment_suggestions(symptoms, context)

    def _build_prompt(self, context: RecommendationContext) -> str:
        """Build prompt for LLM inference."""
        symptoms_str = ", ".join(context.symptoms) if context.symptoms else "None observed"
        env_str = self._format_env_data(context.environmental_data)

        return f"""You are an expert plant health advisor.

Plant: {context.plant_type or 'Unknown'} (Stage: {context.growth_stage or 'Unknown'})
Symptoms: {symptoms_str}
Health Status: {context.health_status or 'Unknown'}
Severity: {context.severity_level}/5

Environmental Data:
{env_str}

Provide 3 specific, actionable recommendations. Be concise.
Format: 1. [action] - [brief rationale]
"""

    def _format_env_data(self, env_data: Optional[Dict[str, float]]) -> str:
        """Format environmental data for prompt."""
        if not env_data:
            return "Not available"
        return "\n".join(f"- {k}: {v}" for k, v in env_data.items())

    def _parse_response(self, response: str) -> List[Recommendation]:
        """Parse LLM response into Recommendation objects."""
        # Future: Parse LLM text output into structured recommendations
        recommendations = []

        # Simple parsing (to be enhanced)
        lines = response.strip().split("\n")
        for line in lines:
            if line.strip() and line[0].isdigit():
                # Remove numbering
                text = line.lstrip("0123456789. ").strip()
                if text:
                    # Split action and rationale if present
                    parts = text.split(" - ", 1)
                    action = parts[0]
                    rationale = parts[1] if len(parts) > 1 else None

                    recommendations.append(Recommendation(
                        action=action,
                        priority="medium",
                        category="general",
                        confidence=0.7,
                        rationale=rationale,
                        source="llm"
                    ))

        return recommendations[:5]  # Limit to 5
