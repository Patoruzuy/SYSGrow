"""
Recommendation Provider Interface
=================================
Abstract interface for plant health recommendation providers.

Supports pluggable backends:
- **RuleBasedRecommendationProvider** (default, uses SYMPTOM_DATABASE)
- **LLMRecommendationProvider** — delegates to any :class:`LLMBackend`
  (OpenAI ChatGPT, Anthropic Claude, or local EXAONE 4.0 1.2B).
  Falls back to rule-based when the backend is unavailable.

The provider interface allows for easy swapping of recommendation
engines without changing the consumer code.
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.domain.plant_symptoms import (
    SYMPTOM_DATABASE as _SYMPTOM_DB,
    TREATMENT_MAP as _TREATMENT_DB,
)

if TYPE_CHECKING:
    from app.domain.irrigation import IrrigationPrediction
    from app.services.ai.llm_backends import LLMBackend
    from app.services.application.threshold_service import ThresholdService

logger = logging.getLogger(__name__)


@dataclass
class RecommendationContext:
    """Context for generating recommendations."""

    plant_id: int
    unit_id: int
    plant_type: str | None = None
    growth_stage: str | None = None
    symptoms: list[str] = field(default_factory=list)
    health_status: str | None = None
    severity_level: int = 1
    environmental_data: dict[str, float] | None = None
    recent_observations: list[dict] | None = None
    nutrient_history: list[dict] | None = None
    irrigation_prediction: "IrrigationPrediction" | None = None


@dataclass
class Recommendation:
    """A single recommendation."""

    action: str  # What to do
    priority: str  # "urgent", "high", "medium", "low"
    category: str  # "watering", "nutrition", "environment", "pest", "disease"
    confidence: float  # 0.0 - 1.0
    rationale: str | None = None  # Why this is recommended
    source: str = "rule_based"  # "rule_based", "ml", "llm"

    def to_dict(self) -> dict[str, Any]:
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
    def get_recommendations(self, context: RecommendationContext) -> list[Recommendation]:
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
        self, symptoms: list[str], context: RecommendationContext | None = None
    ) -> list[Recommendation]:
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

    # Symptom & treatment knowledge — imported from single source of truth.
    SYMPTOM_DATABASE = _SYMPTOM_DB
    TREATMENT_MAP = _TREATMENT_DB

    def __init__(
        self,
        threshold_service: "ThresholdService" | None = None,
    ):
        self.threshold_service = threshold_service

    @property
    def provider_name(self) -> str:
        return "rule_based"

    @property
    def is_available(self) -> bool:
        return True  # Always available

    def get_recommendations(self, context: RecommendationContext) -> list[Recommendation]:
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
                        recommendations.append(
                            Recommendation(
                                action=f"Investigate {cause.replace('_', ' ')}",
                                priority="high" if context.severity_level >= 3 else "medium",
                                category="diagnosis",
                                confidence=0.6,
                                rationale=f"Symptom '{symptom}' is often caused by {cause.replace('_', ' ')}",
                                source="rule_based",
                            )
                        )

            # Add treatment recommendations
            treatment_recs = self.get_treatment_suggestions(context.symptoms, context)
            recommendations.extend(treatment_recs)

        # Add environmental recommendations if data available
        if context.environmental_data:
            env_recs = self._check_environmental_conditions(context)
            recommendations.extend(env_recs)

        # If no recommendations, add general guidance
        if not recommendations:
            if context.health_status == "healthy":
                recommendations.append(
                    Recommendation(
                        action="Continue current care routine",
                        priority="low",
                        category="maintenance",
                        confidence=0.8,
                        rationale="No issues detected",
                        source="rule_based",
                    )
                )
            else:
                recommendations.append(
                    Recommendation(
                        action="Monitor plant closely for changes",
                        priority="medium",
                        category="monitoring",
                        confidence=0.7,
                        rationale="Status requires attention",
                        source="rule_based",
                    )
                )

        return recommendations[:6]  # Limit to top 6 recommendations

    def get_treatment_suggestions(
        self, symptoms: list[str], context: RecommendationContext | None = None
    ) -> list[Recommendation]:
        """Get treatment suggestions for specific symptoms."""
        suggestions = []

        for symptom in symptoms:
            symptom_lower = symptom.lower().replace(" ", "_")
            if symptom_lower in self.TREATMENT_MAP:
                treatments = self.TREATMENT_MAP[symptom_lower]
                for idx, treatment in enumerate(treatments[:3]):  # Top 3 treatments
                    suggestions.append(
                        Recommendation(
                            action=treatment,
                            priority="high" if idx == 0 else "medium",
                            category="treatment",
                            confidence=0.7 - (idx * 0.1),  # First is most confident
                            rationale=f"Recommended treatment for {symptom.replace('_', ' ')}",
                            source="rule_based",
                        )
                    )

        return suggestions

    def _get_irrigation_recommendations(self, context: RecommendationContext) -> list[Recommendation]:
        """Generate irrigation recommendations from ML predictions if available."""
        recommendations: list[Recommendation] = []
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
                recommendations.append(
                    Recommendation(
                        action=f"Adjust soil moisture threshold to {float(optimal):.1f}%",
                        priority="high" if amount >= 5.0 else "medium",
                        category="watering",
                        confidence=min(1.0, confidence),
                        rationale=f"Model suggests {direction} by {amount:.1f}%",
                        source="ml",
                    )
                )

        response = _get(prediction, "user_response")
        if response:
            most_likely = _get(response, "most_likely")
            cancel_prob = float(_get(response, "cancel_probability", 0.0) or 0.0)
            delay_prob = float(_get(response, "delay_probability", 0.0) or 0.0)
            confidence = float(_get(response, "confidence", 0.0) or 0.0)
            if most_likely == "cancel" and cancel_prob > 0.3:
                recommendations.append(
                    Recommendation(
                        action="Review irrigation settings to reduce cancellations",
                        priority="medium",
                        category="watering",
                        confidence=min(1.0, max(confidence, cancel_prob)),
                        rationale=f"Cancel probability is {cancel_prob:.2f}",
                        source="ml",
                    )
                )
            elif most_likely == "delay" and delay_prob > 0.4:
                recommendations.append(
                    Recommendation(
                        action="Adjust irrigation timing to match user preferences",
                        priority="medium",
                        category="watering",
                        confidence=min(1.0, max(confidence, delay_prob)),
                        rationale=f"Delay probability is {delay_prob:.2f}",
                        source="ml",
                    )
                )

        duration = _get(prediction, "duration")
        if duration:
            recommended = _get(duration, "recommended_seconds")
            current_default = _get(duration, "current_default_seconds")
            confidence = float(_get(duration, "confidence", 0.0) or 0.0)
            if recommended is not None and current_default is not None:
                diff = abs(int(recommended) - int(current_default))
                if diff > 30 and confidence > 0.5:
                    direction = "Increase" if int(recommended) > int(current_default) else "Reduce"
                    recommendations.append(
                        Recommendation(
                            action=f"{direction} irrigation duration to {int(recommended)}s",
                            priority="high" if diff >= 60 else "medium",
                            category="watering",
                            confidence=min(1.0, confidence),
                            rationale=f"Recommended change is {diff}s",
                            source="ml",
                        )
                    )

        timing = _get(prediction, "timing")
        if timing:
            preferred_time = _get(timing, "preferred_time")
            avoid_times = _get(timing, "avoid_times") or []
            confidence = float(_get(timing, "confidence", 0.0) or 0.0)
            if preferred_time and avoid_times and confidence > 0.5:
                avoid_preview = ", ".join(list(avoid_times)[:3])
                recommendations.append(
                    Recommendation(
                        action=f"Schedule irrigation near {preferred_time} and avoid {avoid_preview}",
                        priority="medium",
                        category="watering",
                        confidence=min(1.0, confidence),
                        rationale="Timing model suggests preferred hours",
                        source="ml",
                    )
                )

        next_irrigation = _get(prediction, "next_irrigation")
        if next_irrigation:
            predicted_time = _get(next_irrigation, "predicted_time")
            hours_until = _get(next_irrigation, "hours_until_threshold")
            confidence = float(_get(next_irrigation, "confidence", 0.0) or 0.0)
            if predicted_time and confidence > 0.5:
                eta = f"{float(hours_until):.1f}h" if hours_until is not None else "soon"
                recommendations.append(
                    Recommendation(
                        action=f"Next irrigation expected in {eta} (around {predicted_time})",
                        priority="low",
                        category="watering",
                        confidence=min(1.0, confidence),
                        rationale="Dry-down model projection",
                        source="ml",
                    )
                )

        return recommendations

    def _check_environmental_conditions(self, context: RecommendationContext) -> list[Recommendation]:
        """Check environmental conditions against ThresholdService ranges.

        Uses ``ThresholdService.get_threshold_ranges()`` for plant-specific
        min/max/optimal values when available, otherwise falls back to safe
        generic limits.
        """
        recommendations: list[Recommendation] = []
        env = context.environmental_data or {}

        # Resolve ranges from ThresholdService (plant-aware) or generic
        ranges = self._get_env_ranges(context.plant_type, context.growth_stage)

        # Temperature checks
        temp = env.get("temperature")
        if temp is not None:
            temp_range = ranges.get("temperature", {})
            temp_max = temp_range.get("max", 32.0)
            temp_min = temp_range.get("min", 15.0)
            if temp > temp_max:
                recommendations.append(
                    Recommendation(
                        action="Reduce temperature - risk of heat stress",
                        priority="high",
                        category="environment",
                        confidence=0.8,
                        rationale=f"Temperature ({temp}°C) exceeds max ({temp_max}°C)",
                        source="rule_based",
                    )
                )
            elif temp < temp_min:
                recommendations.append(
                    Recommendation(
                        action="Increase temperature - risk of cold stress",
                        priority="high",
                        category="environment",
                        confidence=0.8,
                        rationale=f"Temperature ({temp}°C) below min ({temp_min}°C)",
                        source="rule_based",
                    )
                )

        # Humidity checks
        humidity = env.get("humidity")
        if humidity is not None:
            hum_range = ranges.get("humidity", {})
            hum_max = hum_range.get("max", 80.0)
            hum_min = hum_range.get("min", 30.0)
            if humidity > hum_max:
                recommendations.append(
                    Recommendation(
                        action="Reduce humidity to prevent fungal issues",
                        priority="medium",
                        category="environment",
                        confidence=0.7,
                        rationale=f"Humidity ({humidity}%) exceeds max ({hum_max}%)",
                        source="rule_based",
                    )
                )
            elif humidity < hum_min:
                recommendations.append(
                    Recommendation(
                        action="Increase humidity to prevent leaf damage",
                        priority="medium",
                        category="environment",
                        confidence=0.7,
                        rationale=f"Humidity ({humidity}%) below min ({hum_min}%)",
                        source="rule_based",
                    )
                )

        # Soil moisture checks
        soil_moisture = env.get("soil_moisture")
        if soil_moisture is not None:
            sm_range = ranges.get("soil_moisture", {})
            sm_max = sm_range.get("max", 85.0)
            sm_min = sm_range.get("min", 25.0)
            if soil_moisture < sm_min:
                recommendations.append(
                    Recommendation(
                        action="Water immediately - soil is very dry",
                        priority="urgent",
                        category="watering",
                        confidence=0.9,
                        rationale=f"Soil moisture ({soil_moisture}%) below min ({sm_min}%)",
                        source="rule_based",
                    )
                )
            elif soil_moisture > sm_max:
                recommendations.append(
                    Recommendation(
                        action="Reduce watering - risk of root rot",
                        priority="high",
                        category="watering",
                        confidence=0.8,
                        rationale=f"Soil moisture ({soil_moisture}%) exceeds max ({sm_max}%)",
                        source="rule_based",
                    )
                )

        return recommendations

    def _get_env_ranges(
        self,
        plant_type: str | None,
        growth_stage: str | None,
    ) -> dict[str, dict[str, float]]:
        """Resolve environmental ranges from ThresholdService or generic fallback."""
        if self.threshold_service and plant_type:
            try:
                return self.threshold_service.get_threshold_ranges(
                    plant_type,
                    growth_stage,
                )
            except Exception as exc:
                logger.debug("ThresholdService lookup failed: %s", exc)
        # Generic safe limits when no ThresholdService or plant_type
        return {
            "temperature": {"min": 15.0, "max": 32.0, "optimal": 24.0},
            "humidity": {"min": 30.0, "max": 80.0, "optimal": 60.0},
            "soil_moisture": {"min": 25.0, "max": 85.0, "optimal": 55.0},
            "co2": {"min": 400.0, "max": 2000.0, "optimal": 1000.0},
        }


class LLMRecommendationProvider(RecommendationProvider):
    """
    LLM-powered recommendation provider.

    Delegates to any :class:`LLMBackend` (OpenAI, Anthropic, or a local
    model such as EXAONE 4.0 1.2B).  Falls back to the supplied
    *fallback_provider* (usually rule-based) when the backend is
    unavailable or returns an unparseable response.

    Parameters
    ----------
    backend:
        An initialised :class:`LLMBackend`.  Pass ``None`` to create the
        provider in fallback-only mode (useful during container wiring
        before the backend is ready).
    fallback_provider:
        Provider to use when the LLM is unavailable.  Defaults to a fresh
        :class:`RuleBasedRecommendationProvider`.
    max_tokens:
        Token budget for recommendation generation.
    temperature:
        Sampling temperature (lower → more deterministic).
    """

    # -- System prompt for recommendation generation ------------------------

    _SYSTEM_PROMPT = """\
You are **SYSGrow Recommender** — an AI plant-health advisor embedded in a \
smart agriculture monitoring system.

Analyze the provided context (plant type, growth stage, symptoms, sensor \
data) and produce **up to 5** actionable care recommendations.

Response format — a JSON array of objects:
[
  {
    "action": "<short imperative sentence>",
    "priority": "urgent" | "high" | "medium" | "low",
    "category": "watering" | "nutrition" | "environment" | "pest" | "disease" | "maintenance" | "diagnosis",
    "confidence": <float 0.0-1.0>,
    "rationale": "<one-line reason>"
  }
]

Rules:
• Be concise and specific — growers need actionable steps, not generic advice.
• Order by priority descending.
• If sensor data shows an urgent condition (e.g. very low soil moisture), \
  flag it as "urgent".
• Confidence should reflect how sure you are given the available data.

Respond ONLY with a valid JSON array. No markdown fences."""

    def __init__(
        self,
        backend: "LLMBackend" | None = None,
        fallback_provider: RecommendationProvider | None = None,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ):
        self._backend = backend
        self._fallback = fallback_provider or RuleBasedRecommendationProvider()
        self._max_tokens = max_tokens
        self._temperature = temperature

    # -- ABC ----------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        if self._backend is not None:
            return f"llm:{self._backend.name}"
        return "llm:fallback"

    @property
    def is_available(self) -> bool:
        return self._backend is not None and self._backend.is_available

    # -- public API ---------------------------------------------------------

    def get_recommendations(
        self,
        context: RecommendationContext,
    ) -> list[Recommendation]:
        """Generate LLM-powered recommendations, falling back to rules."""
        if not self.is_available:
            logger.debug("LLM backend not available — using fallback provider")
            return self._fallback.get_recommendations(context)

        user_prompt = self._build_recommendation_prompt(context)

        try:
            response = self._backend.generate(  # type: ignore[union-attr]
                system_prompt=self._SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                json_mode=True,
            )
            recommendations = self._parse_recommendations(response.text)
            if recommendations:
                logger.debug(
                    "LLM produced %d recommendations (%.0f ms)",
                    len(recommendations),
                    response.latency_ms,
                )
                return recommendations
        except Exception as exc:
            logger.warning("LLM recommendation failed: %s — using fallback", exc)

        return self._fallback.get_recommendations(context)

    def get_treatment_suggestions(
        self,
        symptoms: list[str],
        context: RecommendationContext | None = None,
    ) -> list[Recommendation]:
        """Get LLM-powered treatment suggestions for specific symptoms."""
        if not self.is_available:
            return self._fallback.get_treatment_suggestions(symptoms, context)

        symptom_text = ", ".join(symptoms) if symptoms else "none"
        plant_info = ""
        if context and context.plant_type:
            plant_info = f"Plant: {context.plant_type}"
            if context.growth_stage:
                plant_info += f" (stage: {context.growth_stage})"
            plant_info += "\n"

        user_prompt = (
            f"{plant_info}Symptoms observed: {symptom_text}\n\nSuggest specific treatments for these symptoms."
        )

        try:
            response = self._backend.generate(  # type: ignore[union-attr]
                system_prompt=self._SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                json_mode=True,
            )
            recommendations = self._parse_recommendations(response.text)
            if recommendations:
                # Tag them as treatments
                for rec in recommendations:
                    if rec.category == "maintenance":
                        rec.category = "treatment"
                return recommendations
        except Exception as exc:
            logger.warning("LLM treatment suggestion failed: %s", exc)

        return self._fallback.get_treatment_suggestions(symptoms, context)

    # -- prompt building ----------------------------------------------------

    def _build_recommendation_prompt(self, ctx: RecommendationContext) -> str:
        """Build a rich user prompt from :class:`RecommendationContext`."""
        parts: list[str] = []

        if ctx.plant_type:
            stage = ctx.growth_stage or "unknown"
            parts.append(f"Plant: {ctx.plant_type} (growth stage: {stage})")

        if ctx.health_status:
            parts.append(f"Health status: {ctx.health_status}")

        if ctx.severity_level and ctx.severity_level > 1:
            parts.append(f"Severity level: {ctx.severity_level}/5")

        if ctx.symptoms:
            parts.append(f"Symptoms: {', '.join(ctx.symptoms)}")

        if ctx.environmental_data:
            env_lines = [f"  {key}: {val}" for key, val in ctx.environmental_data.items()]
            parts.append("Current sensor readings:\n" + "\n".join(env_lines))

        if ctx.recent_observations:
            obs_summary = "; ".join(str(o.get("summary", o)) for o in ctx.recent_observations[:3])
            parts.append(f"Recent observations: {obs_summary}")

        if ctx.irrigation_prediction:
            parts.append("(Irrigation ML model predictions are also available)")

        if not parts:
            parts.append("No specific context available — provide general care guidance.")

        return "\n".join(parts)

    # -- response parsing ---------------------------------------------------

    def _parse_recommendations(self, text: str) -> list[Recommendation]:
        """Parse the LLM's JSON response into :class:`Recommendation` objects."""
        cleaned = text.strip()
        # Strip markdown fences if present
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM returned non-JSON response")
            return self._parse_freeform(cleaned)

        # Accept both a top-level array and {"recommendations": [...]}
        items: list[dict[str, Any]] = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("recommendations", [])
            if not items and "action" in data:
                items = [data]

        recommendations: list[Recommendation] = []
        valid_priorities = {"urgent", "high", "medium", "low"}
        for item in items[:5]:
            if not isinstance(item, dict) or "action" not in item:
                continue
            priority = str(item.get("priority", "medium")).lower()
            if priority not in valid_priorities:
                priority = "medium"
            recommendations.append(
                Recommendation(
                    action=str(item["action"]),
                    priority=priority,
                    category=str(item.get("category", "general")),
                    confidence=min(1.0, max(0.0, float(item.get("confidence", 0.7)))),
                    rationale=item.get("rationale"),
                    source="llm",
                )
            )

        return recommendations

    @staticmethod
    def _parse_freeform(text: str) -> list[Recommendation]:
        """Last-resort: extract numbered lines from plain text."""
        recommendations: list[Recommendation] = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if line and line[0].isdigit():
                action = line.lstrip("0123456789.) ").strip()
                if not action:
                    continue
                parts = action.split(" - ", 1)
                recommendations.append(
                    Recommendation(
                        action=parts[0],
                        priority="medium",
                        category="general",
                        confidence=0.5,
                        rationale=parts[1] if len(parts) > 1 else None,
                        source="llm",
                    )
                )
        return recommendations[:5]
