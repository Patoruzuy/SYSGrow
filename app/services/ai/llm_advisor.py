"""
LLM Advisor Service — Plant Care Decision Maker
=================================================
High-level advisory service that wraps an :class:`LLMBackend` and provides
structured plant care decisions, diagnoses, and care plan generation.

This is the **"decision maker"** component — it goes beyond the
:class:`RecommendationProvider` interface (which focuses on a fixed list of
recommendations) and answers free-form questions about a grower's unit.

Usage
-----
::

    advisor = LLMAdvisorService(backend=my_backend)
    response = advisor.ask(
        DecisionQuery(
            question="Should I water my basil now?",
            plant_type="basil",
            growth_stage="vegetative",
            environmental_data={"soil_moisture": 28.0, "temperature": 26.0},
        )
    )
    print(response.answer, response.confidence)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.ai.llm_backends import LLMBackend

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class DecisionQuery:
    """Everything the advisor needs to answer a grower's question."""

    question: str
    unit_id: int | None = None
    plant_type: str | None = None
    growth_stage: str | None = None
    environmental_data: dict[str, float] | None = None
    recent_symptoms: list[str] | None = None
    health_status: str | None = None
    additional_context: str | None = None


@dataclass
class DecisionResponse:
    """Structured answer from the advisor."""

    answer: str
    confidence: float = 0.0
    reasoning: str = ""
    suggested_actions: list[str] = field(default_factory=list)
    source: str = "llm"  # "llm" or "unavailable"
    usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "confidence": round(self.confidence, 2),
            "reasoning": self.reasoning,
            "suggested_actions": self.suggested_actions,
            "source": self.source,
            "latency_ms": round(self.latency_ms, 1),
        }


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_ADVISOR_SYSTEM_PROMPT = """\
You are **SYSGrow Advisor** — an AI plant-care decision assistant embedded \
in a smart agriculture monitoring system.

Your role:
• Help growers make data-driven decisions about watering, nutrition, \
  environment control, pest management, and harvest timing.
• Base your answers on the sensor data and observations provided.
• When data is insufficient, say so honestly and suggest what to measure.
• Be concise and practical — growers need actionable answers, not essays.

Response format (JSON):
{
  "answer": "<direct answer to the question>",
  "confidence": <0.0-1.0>,
  "reasoning": "<brief supporting rationale>",
  "suggested_actions": ["<action 1>", "<action 2>", ...]
}

Respond ONLY with valid JSON. No markdown fences."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class LLMAdvisorService:
    """
    High-level advisory service for plant-care decisions.

    Falls back gracefully when no backend is available — returns an
    ``"unavailable"`` response instead of raising.

    Parameters
    ----------
    backend:
        An initialised :class:`LLMBackend`.  ``None`` means the advisor
        will always return an "unavailable" response.
    max_tokens:
        Default token budget for answers.
    temperature:
        Default sampling temperature.
    """

    def __init__(
        self,
        backend: "LLMBackend" | None = None,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ):
        self._backend = backend
        self._max_tokens = max_tokens
        self._temperature = temperature

    # -- public API ---------------------------------------------------------

    @property
    def is_available(self) -> bool:
        """``True`` when the backing LLM is ready."""
        return self._backend is not None and self._backend.is_available

    @property
    def provider_name(self) -> str:
        """Name of the active backend, or ``"none"``."""
        if self._backend is not None:
            return self._backend.name
        return "none"

    def ask(self, query: DecisionQuery) -> DecisionResponse:
        """
        Ask the advisor a free-form question.

        Parameters
        ----------
        query:
            A :class:`DecisionQuery` with the question and all available
            context.

        Returns
        -------
        DecisionResponse — always returned, never raises.
        """
        if not self.is_available:
            return DecisionResponse(
                answer=(
                    "LLM advisor is not currently available. "
                    "Please check your LLM configuration in environment variables."
                ),
                confidence=0.0,
                source="unavailable",
            )

        user_prompt = self._build_user_prompt(query)

        try:
            llm_response = self._backend.generate(  # type: ignore[union-attr]
                system_prompt=_ADVISOR_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                json_mode=True,
            )
            return self._parse_response(llm_response.text, llm_response)
        except Exception as exc:
            logger.error("LLM advisor error: %s", exc, exc_info=True)
            return DecisionResponse(
                answer=f"Sorry, the advisor encountered an error: {exc}",
                confidence=0.0,
                source="llm",
            )

    def diagnose(
        self,
        symptoms: list[str],
        plant_type: str | None = None,
        environmental_data: dict[str, float] | None = None,
    ) -> DecisionResponse:
        """
        Convenience: ask the LLM to diagnose plant symptoms.
        """
        symptom_text = ", ".join(symptoms) if symptoms else "none reported"
        return self.ask(
            DecisionQuery(
                question=(f"Diagnose the following symptoms and suggest treatments: {symptom_text}"),
                plant_type=plant_type,
                recent_symptoms=symptoms,
                environmental_data=environmental_data,
            )
        )

    def should_irrigate(
        self,
        plant_type: str | None = None,
        growth_stage: str | None = None,
        environmental_data: dict[str, float] | None = None,
        additional_context: str | None = None,
    ) -> DecisionResponse:
        """
        Convenience: ask whether the grower should irrigate now.
        """
        return self.ask(
            DecisionQuery(
                question="Based on the current sensor data, should I irrigate now?",
                plant_type=plant_type,
                growth_stage=growth_stage,
                environmental_data=environmental_data,
                additional_context=additional_context,
            )
        )

    def care_plan(
        self,
        plant_type: str,
        growth_stage: str | None = None,
        environmental_data: dict[str, float] | None = None,
        health_status: str | None = None,
    ) -> DecisionResponse:
        """
        Convenience: generate a short-term care plan for a unit.
        """
        return self.ask(
            DecisionQuery(
                question=(
                    "Generate a concise 7-day care plan covering watering, nutrition, and environment adjustments."
                ),
                plant_type=plant_type,
                growth_stage=growth_stage,
                environmental_data=environmental_data,
                health_status=health_status,
            )
        )

    # -- internal -----------------------------------------------------------

    def _build_user_prompt(self, query: DecisionQuery) -> str:
        """Format a :class:`DecisionQuery` into a textual prompt."""
        parts: list[str] = []

        if query.plant_type:
            stage = query.growth_stage or "unknown"
            parts.append(f"Plant: {query.plant_type} (stage: {stage})")

        if query.health_status:
            parts.append(f"Health status: {query.health_status}")

        if query.recent_symptoms:
            parts.append(f"Symptoms: {', '.join(query.recent_symptoms)}")

        if query.environmental_data:
            env_lines = [f"  {k}: {v}" for k, v in query.environmental_data.items()]
            parts.append("Sensor data:\n" + "\n".join(env_lines))

        if query.additional_context:
            parts.append(f"Context: {query.additional_context}")

        parts.append(f"Question: {query.question}")
        return "\n".join(parts)

    def _parse_response(self, text: str, llm_response: Any) -> DecisionResponse:
        """Parse the LLM's JSON text into a :class:`DecisionResponse`."""
        # Strip markdown fences if present
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            # Remove first and last fence lines
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("LLM response was not valid JSON, using raw text")
            return DecisionResponse(
                answer=text.strip(),
                confidence=0.5,
                reasoning="(response was not structured JSON)",
                source="llm",
                usage=getattr(llm_response, "usage", {}),
                latency_ms=getattr(llm_response, "latency_ms", 0.0),
            )

        return DecisionResponse(
            answer=data.get("answer", text.strip()),
            confidence=float(data.get("confidence", 0.7)),
            reasoning=data.get("reasoning", ""),
            suggested_actions=data.get("suggested_actions", []),
            source="llm",
            usage=getattr(llm_response, "usage", {}),
            latency_ms=getattr(llm_response, "latency_ms", 0.0),
        )
