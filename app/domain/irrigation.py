"""
Irrigation Prediction Domain Objects
=====================================
Dataclasses for ML-based irrigation predictions.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PredictionConfidence(str, Enum):
    """Confidence levels for predictions."""
    LOW = "low"          # < 50% confidence
    MEDIUM = "medium"    # 50-75% confidence
    HIGH = "high"        # > 75% confidence


@dataclass
class UserResponsePrediction:
    """Prediction of user response to irrigation request."""
    approve_probability: float
    delay_probability: float
    cancel_probability: float
    most_likely: str  # "approve", "delay", or "cancel"
    confidence: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "probabilities": {
                "approve": round(self.approve_probability, 3),
                "delay": round(self.delay_probability, 3),
                "cancel": round(self.cancel_probability, 3),
            },
            "most_likely": self.most_likely,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class ThresholdPrediction:
    """Prediction of optimal soil moisture threshold."""
    optimal_threshold: float
    current_threshold: float
    adjustment_direction: str  # "increase", "decrease", "maintain"
    adjustment_amount: float
    confidence: float
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "optimal_threshold": round(self.optimal_threshold, 1),
            "current_threshold": round(self.current_threshold, 1),
            "adjustment_direction": self.adjustment_direction,
            "adjustment_amount": round(self.adjustment_amount, 1),
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
        }


@dataclass
class DurationPrediction:
    """Prediction of optimal irrigation duration."""
    recommended_seconds: int
    current_default_seconds: int
    expected_moisture_increase: float
    confidence: float
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "recommended_seconds": self.recommended_seconds,
            "current_default_seconds": self.current_default_seconds,
            "expected_moisture_increase": round(self.expected_moisture_increase, 1),
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
        }


@dataclass
class TimingPrediction:
    """Prediction of preferred irrigation time."""
    preferred_time: str  # "HH:MM" format
    preferred_hour: int
    preferred_minute: int
    avoid_times: List[str]  # Times user typically delays/cancels
    confidence: float
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "preferred_time": self.preferred_time,
            "preferred_hour": self.preferred_hour,
            "preferred_minute": self.preferred_minute,
            "avoid_times": self.avoid_times,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
        }


@dataclass
class MoistureDeclinePrediction:
    """Prediction of when next irrigation will be needed."""
    current_moisture: float
    threshold: float
    decline_rate_per_hour: float
    hours_until_threshold: float
    predicted_time: str  # ISO format
    confidence: float
    reasoning: str
    samples_used: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "current_moisture": round(self.current_moisture, 1),
            "threshold": round(self.threshold, 1),
            "decline_rate_per_hour": round(self.decline_rate_per_hour, 3),
            "hours_until_threshold": round(self.hours_until_threshold, 1),
            "predicted_time": self.predicted_time,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning,
            "samples_used": self.samples_used,
        }


@dataclass
class IrrigationPrediction:
    """
    Comprehensive irrigation prediction result.

    Combines all prediction types into a single recommendation.
    """
    unit_id: int
    generated_at: str

    # Individual predictions
    threshold: Optional[ThresholdPrediction] = None
    user_response: Optional[UserResponsePrediction] = None
    duration: Optional[DurationPrediction] = None
    timing: Optional[TimingPrediction] = None
    next_irrigation: Optional[MoistureDeclinePrediction] = None

    # Overall recommendations
    recommendations: List[str] = field(default_factory=list)
    overall_confidence: float = 0.0
    models_used: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "unit_id": self.unit_id,
            "generated_at": self.generated_at,
            "threshold": self.threshold.to_dict() if self.threshold else None,
            "user_response": self.user_response.to_dict() if self.user_response else None,
            "duration": self.duration.to_dict() if self.duration else None,
            "timing": self.timing.to_dict() if self.timing else None,
            "next_irrigation": self.next_irrigation.to_dict() if self.next_irrigation else None,
            "recommendations": self.recommendations,
            "overall_confidence": round(self.overall_confidence, 3),
            "models_used": self.models_used,
        }
