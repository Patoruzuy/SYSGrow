"""
Bayesian Threshold Adjustment Service
======================================
Intelligent Bayesian learning for optimal soil moisture thresholds.

Uses conjugate prior (Normal-Normal) for efficient online updates:
- Prior: Plant type default threshold with high uncertainty
- Likelihood: User feedback (too_little/just_right/too_much)
- Posterior: Updated belief about optimal threshold

Benefits over fixed ±5% adjustments:
- Adjustments shrink as confidence grows
- Accounts for user consistency (noisy vs reliable feedback)
- Handles conflicting feedback gracefully
- Converges to optimal value over time
- Provides uncertainty estimates for decision making

Author: SYSGrow Team
Date: January 2026
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from app.utils.time import iso_now, utc_now
from app.constants import (
    IRRIGATION_THRESHOLDS,
    GROWTH_STAGE_MOISTURE_ADJUSTMENTS,
    BAYESIAN_DEFAULTS,
)

if TYPE_CHECKING:
    from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository
    from infrastructure.database.repositories.irrigation_workflow import IrrigationWorkflowRepository
    from app.services.application.threshold_service import ThresholdService

logger = logging.getLogger(__name__)


@dataclass
class ThresholdBelief:
    """
    Bayesian belief about optimal soil moisture threshold.
    
    Represents a Normal distribution N(mean, variance) over the optimal threshold.
    """
    
    mean: float              # Posterior mean (best estimate)
    variance: float          # Posterior variance (uncertainty)
    sample_count: int        # Number of feedback samples seen
    last_updated: str        # ISO timestamp of last update
    
    # Optional metadata
    plant_type: Optional[str] = None
    growth_stage: Optional[str] = None
    
    @property
    def confidence(self) -> float:
        """
        Confidence score based on sample count.
        
        Returns:
            0.0-1.0 confidence score (max at 50 samples)
        """
        return min(1.0, self.sample_count / 50)
    
    @property
    def std_dev(self) -> float:
        """Standard deviation of belief (uncertainty)."""
        return math.sqrt(self.variance) if self.variance > 0 else 0.0
    
    @property
    def precision(self) -> float:
        """Precision (inverse variance) - used in Bayesian updates."""
        return 1.0 / self.variance if self.variance > 0 else float('inf')
    
    def credible_interval(self, coverage: float = 0.95) -> Tuple[float, float]:
        """
        Calculate credible interval for the threshold.
        
        Args:
            coverage: Coverage probability (default 95%)
            
        Returns:
            (lower, upper) bounds
        """
        # Use Normal approximation
        # For 95% CI: mean ± 1.96 * std_dev
        z_score = {
            0.90: 1.645,
            0.95: 1.96,
            0.99: 2.576,
        }.get(coverage, 1.96)
        
        margin = z_score * self.std_dev
        return (self.mean - margin, self.mean + margin)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "mean": round(self.mean, 2),
            "variance": round(self.variance, 4),
            "sample_count": self.sample_count,
            "last_updated": self.last_updated,
            "plant_type": self.plant_type,
            "growth_stage": self.growth_stage,
            "confidence": round(self.confidence, 3),
            "std_dev": round(self.std_dev, 2),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ThresholdBelief":
        """Create from dictionary."""
        return cls(
            mean=data["mean"],
            variance=data["variance"],
            sample_count=data.get("sample_count", 0),
            last_updated=data.get("last_updated", iso_now()),
            plant_type=data.get("plant_type"),
            growth_stage=data.get("growth_stage"),
        )


@dataclass
class AdjustmentResult:
    """Result of a threshold adjustment computation."""
    
    recommended_threshold: float
    adjustment_amount: float
    direction: str  # "increase", "decrease", "maintain"
    confidence: float
    uncertainty: float
    reasoning: str
    belief: ThresholdBelief
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "recommended_threshold": round(self.recommended_threshold, 1),
            "adjustment_amount": round(self.adjustment_amount, 1),
            "direction": self.direction,
            "confidence": round(self.confidence, 3),
            "uncertainty": round(self.uncertainty, 2),
            "reasoning": self.reasoning,
            "belief": self.belief.to_dict(),
        }


class BayesianThresholdAdjuster:
    """
    Bayesian approach to learning optimal soil moisture thresholds.
    
    Uses conjugate Normal-Normal prior for efficient online updates:
    
    Model:
        θ ~ N(μ₀, σ₀²)           # Prior belief about optimal threshold
        x | θ ~ N(θ, σ²)         # Observation (user feedback)
        θ | x ~ N(μₙ, σₙ²)       # Posterior belief
    
    Where:
        σₙ² = 1 / (1/σ₀² + 1/σ²)
        μₙ = σₙ² * (μ₀/σ₀² + x/σ²)
    
    The observation x is derived from user feedback:
        - "too_little": x = current_threshold + estimated_adjustment
        - "too_much": x = current_threshold - estimated_adjustment
        - "just_right": x = current_threshold (reinforces current value)
    """
    
    def __init__(
        self,
        irrigation_ml_repo: Optional["IrrigationMLRepository"] = None,
        workflow_repo: Optional["IrrigationWorkflowRepository"] = None,
        threshold_service: Optional["ThresholdService"] = None,
        default_prior_variance: Optional[float] = None,
        min_variance: Optional[float] = None,
        base_observation_variance: Optional[float] = None,
    ):
        """
        Initialize Bayesian adjuster.
        
        Args:
            irrigation_ml_repo: Repository for ML data access
            workflow_repo: Repository for workflow data access
            threshold_service: ThresholdService for real plant-specific thresholds
            default_prior_variance: Initial variance (uncertainty) for prior
            min_variance: Minimum variance to prevent overconfidence
            base_observation_variance: Base variance for observations
        """
        self._ml_repo = irrigation_ml_repo
        self._workflow_repo = workflow_repo
        self._threshold_service = threshold_service
        self._default_prior_variance = default_prior_variance or BAYESIAN_DEFAULTS["prior_variance"]
        self._min_variance = min_variance or BAYESIAN_DEFAULTS["min_variance"]
        self._base_observation_variance = base_observation_variance or BAYESIAN_DEFAULTS["observation_variance"]
        
        # In-memory belief cache: (unit_id, user_id, belief_key) -> ThresholdBelief
        self._beliefs: Dict[Tuple[int, int, str], ThresholdBelief] = {}

    @staticmethod
    def _belief_key(
        plant_type: str,
        growth_stage: str,
        plant_variety: Optional[str] = None,
        strain_variety: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> str:
        parts = [
            (plant_type or "default").strip().lower(),
            (growth_stage or "vegetative").strip().lower(),
        ]
        if plant_variety:
            parts.append(f"variety:{plant_variety.strip().lower()}")
        if strain_variety:
            parts.append(f"strain:{strain_variety.strip().lower()}")
        if pot_size_liters is not None:
            parts.append(f"pot:{round(float(pot_size_liters), 2)}")
        return "|".join(parts)
    
    def get_prior(
        self,
        plant_type: str,
        growth_stage: str,
        *,
        user_id: Optional[int] = None,
        plant_variety: Optional[str] = None,
        strain_variety: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> ThresholdBelief:
        """
        Get prior belief for a plant type and growth stage.
        
        Uses ThresholdService for real plant-specific data when available,
        falls back to hardcoded defaults otherwise.
        
        Args:
            plant_type: Plant type name
            growth_stage: Current growth stage
            
        Returns:
            Prior ThresholdBelief
        """
        prior_mean = self._get_threshold_from_service(
            plant_type,
            growth_stage,
            user_id=user_id,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )
        
        return ThresholdBelief(
            mean=prior_mean,
            variance=self._default_prior_variance,
            sample_count=0,
            last_updated=iso_now(),
            plant_type=plant_type,
            growth_stage=growth_stage,
        )

    def _get_threshold_from_service(
        self,
        plant_type: str,
        growth_stage: str,
        *,
        user_id: Optional[int] = None,
        plant_variety: Optional[str] = None,
        strain_variety: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> float:
        """
        Get soil moisture threshold from ThresholdService or fallback.
        
        Args:
            plant_type: Plant type name
            growth_stage: Current growth stage
            
        Returns:
            Soil moisture threshold value
        """
        # Try to get real threshold from ThresholdService
        if self._threshold_service:
            try:
                thresholds = self._threshold_service.get_thresholds(
                    plant_type,
                    growth_stage,
                    user_id=user_id,
                    plant_variety=plant_variety,
                    strain_variety=strain_variety,
                    pot_size_liters=pot_size_liters,
                )
                if thresholds and thresholds.soil_moisture:
                    logger.debug(
                        f"Using ThresholdService data for {plant_type}/{growth_stage}: "
                        f"soil_moisture={thresholds.soil_moisture}%"
                    )
                    return thresholds.soil_moisture
            except Exception as e:
                logger.warning(f"Failed to get threshold from service: {e}")
        
        # Fallback to constants
        base_threshold = IRRIGATION_THRESHOLDS.get(
            plant_type.lower(),
            IRRIGATION_THRESHOLDS["default"],
        )
        
        stage_adjustment = GROWTH_STAGE_MOISTURE_ADJUSTMENTS.get(growth_stage, 0.0)
        fallback_value = base_threshold + stage_adjustment
        
        logger.debug(
            f"Using fallback threshold for {plant_type}/{growth_stage}: {fallback_value}%"
        )
        return fallback_value
    
    def get_belief(
        self,
        unit_id: int,
        user_id: int,
        plant_type: str = "default",
        growth_stage: str = "Vegetative",
        *,
        plant_variety: Optional[str] = None,
        strain_variety: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> ThresholdBelief:
        """
        Get current belief about optimal threshold for a unit/user.
        
        Loads from cache or database, or creates prior if not exists.
        
        Args:
            unit_id: Grow unit ID
            user_id: User ID
            plant_type: Plant type name
            growth_stage: Current growth stage
            
        Returns:
            Current ThresholdBelief
        """
        belief_key = self._belief_key(
            plant_type,
            growth_stage,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )
        cache_key = (unit_id, user_id, belief_key)
        
        # Check cache first
        if cache_key in self._beliefs:
            return self._beliefs[cache_key]
        
        # Try to load from database
        if self._workflow_repo:
            try:
                pref = self._workflow_repo.get_user_preference(user_id, unit_id)
                if pref and pref.get("threshold_belief_json"):
                    belief_payload = json.loads(pref["threshold_belief_json"])
                    belief_data = None
                    if isinstance(belief_payload, dict) and "mean" in belief_payload:
                        # Legacy single-belief format
                        belief_data = belief_payload
                    elif isinstance(belief_payload, dict):
                        belief_data = belief_payload.get(belief_key) or belief_payload.get("default")
                    if belief_data:
                        belief = ThresholdBelief.from_dict(belief_data)
                        self._beliefs[cache_key] = belief
                        return belief
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"Failed to load belief from DB: {e}")
        
        # Create prior from plant type
        prior = self.get_prior(
            plant_type,
            growth_stage,
            user_id=user_id,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )
        self._beliefs[cache_key] = prior
        return prior
    
    def update_from_feedback(
        self,
        unit_id: int,
        user_id: int,
        feedback: str,
        current_threshold: float,
        soil_moisture_at_request: float,
        plant_type: str = "default",
        growth_stage: str = "Vegetative",
        *,
        plant_variety: Optional[str] = None,
        strain_variety: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> AdjustmentResult:
        """
        Update belief based on user feedback.
        
        This is the core Bayesian update method that adjusts our belief
        about the optimal threshold based on user feedback.
        
        Args:
            unit_id: Grow unit ID
            user_id: User ID
            feedback: One of "too_little", "just_right", "too_much"
            current_threshold: The threshold that was used
            soil_moisture_at_request: Soil moisture when irrigation was triggered
            plant_type: Plant type name
            growth_stage: Current growth stage
            
        Returns:
            AdjustmentResult with new recommended threshold
        """
        # Get current belief
        belief = self.get_belief(
            unit_id,
            user_id,
            plant_type,
            growth_stage,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )
        
        # Convert feedback to observation
        adjustment_magnitude = self._estimate_adjustment_magnitude(belief)
        
        if feedback == "too_little":
            # User wants more water -> threshold should be HIGHER
            # (trigger irrigation sooner, at higher moisture)
            observed_optimal = current_threshold + adjustment_magnitude
            direction = "increase"
        elif feedback == "too_much":
            # User wants less water -> threshold should be LOWER
            # (trigger irrigation later, at lower moisture)
            observed_optimal = current_threshold - adjustment_magnitude
            direction = "decrease"
        else:  # just_right
            # Current threshold is good - reinforce it
            observed_optimal = current_threshold
            direction = "maintain"
        
        # Calculate observation variance based on user consistency
        user_consistency = self._calculate_user_consistency(user_id, unit_id)
        observation_variance = self._get_observation_variance(user_consistency)
        
        # Bayesian update (Normal-Normal conjugate)
        prior_precision = belief.precision
        observation_precision = 1.0 / observation_variance
        
        posterior_precision = prior_precision + observation_precision
        posterior_variance = max(self._min_variance, 1.0 / posterior_precision)
        
        posterior_mean = (
            prior_precision * belief.mean + 
            observation_precision * observed_optimal
        ) / posterior_precision
        
        # Clamp to reasonable range
        posterior_mean = max(20.0, min(80.0, posterior_mean))
        
        # Create updated belief
        new_belief = ThresholdBelief(
            mean=posterior_mean,
            variance=posterior_variance,
            sample_count=belief.sample_count + 1,
            last_updated=iso_now(),
            plant_type=plant_type,
            growth_stage=growth_stage,
        )
        
        # Cache and persist
        belief_key = self._belief_key(
            plant_type,
            growth_stage,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )
        self._beliefs[(unit_id, user_id, belief_key)] = new_belief
        self._persist_belief(unit_id, user_id, new_belief, belief_key=belief_key)
        
        # Calculate adjustment from current
        adjustment_amount = posterior_mean - current_threshold
        
        # Generate reasoning
        if abs(adjustment_amount) < 1.0:
            reasoning = f"Threshold optimal (confidence: {new_belief.confidence:.0%})"
            direction = "maintain"
        elif feedback == "just_right":
            reasoning = f"Reinforced current threshold (confidence: {new_belief.confidence:.0%})"
        else:
            reasoning = (
                f"Adjusted based on '{feedback}' feedback: "
                f"{current_threshold:.1f}% → {posterior_mean:.1f}% "
                f"(confidence: {new_belief.confidence:.0%})"
            )
        
        logger.info(
            f"Bayesian threshold update for unit {unit_id}: "
            f"{belief.mean:.1f}% → {posterior_mean:.1f}% "
            f"(feedback: {feedback}, samples: {new_belief.sample_count})"
        )
        
        return AdjustmentResult(
            recommended_threshold=posterior_mean,
            adjustment_amount=abs(adjustment_amount),
            direction=direction if abs(adjustment_amount) >= 1.0 else "maintain",
            confidence=new_belief.confidence,
            uncertainty=new_belief.std_dev,
            reasoning=reasoning,
            belief=new_belief,
        )
    
    def get_recommended_threshold(
        self,
        unit_id: int,
        user_id: int,
        current_threshold: float,
        plant_type: str = "default",
        growth_stage: str = "Vegetative",
        *,
        plant_variety: Optional[str] = None,
        strain_variety: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> AdjustmentResult:
        """
        Get recommended threshold based on current belief.
        
        Does not update belief - use for read-only recommendations.
        
        Args:
            unit_id: Grow unit ID
            user_id: User ID
            current_threshold: Current threshold setting
            plant_type: Plant type name
            growth_stage: Current growth stage
            
        Returns:
            AdjustmentResult with recommendation
        """
        belief = self.get_belief(
            unit_id,
            user_id,
            plant_type,
            growth_stage,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )
        
        adjustment_amount = belief.mean - current_threshold
        
        if abs(adjustment_amount) < 1.0:
            direction = "maintain"
            reasoning = "Current threshold is optimal"
        elif adjustment_amount > 0:
            direction = "increase"
            reasoning = f"Recommend increasing threshold to {belief.mean:.1f}%"
        else:
            direction = "decrease"
            reasoning = f"Recommend decreasing threshold to {belief.mean:.1f}%"
        
        return AdjustmentResult(
            recommended_threshold=belief.mean,
            adjustment_amount=abs(adjustment_amount),
            direction=direction,
            confidence=belief.confidence,
            uncertainty=belief.std_dev,
            reasoning=reasoning,
            belief=belief,
        )
    
    def calculate_adaptive_adjustment(
        self,
        unit_id: int,
        user_id: int,
        feedback: str,
        current_threshold: float,
    ) -> float:
        """
        Calculate adaptive adjustment amount based on confidence.
        
        Low confidence -> larger adjustments (explore)
        High confidence -> smaller adjustments (exploit)
        
        This is the replacement for fixed ±5% adjustments.
        
        Args:
            unit_id: Grow unit ID
            user_id: User ID
            feedback: Feedback type
            current_threshold: Current threshold
            
        Returns:
            Signed adjustment amount (positive = increase, negative = decrease)
        """
        belief = self.get_belief(unit_id, user_id)
        
        # Base adjustment scales with uncertainty
        base_adjustment = self._estimate_adjustment_magnitude(belief)
        
        if feedback == "too_little":
            return base_adjustment
        elif feedback == "too_much":
            return -base_adjustment
        else:  # just_right
            return 0.0
    
    def _estimate_adjustment_magnitude(self, belief: ThresholdBelief) -> float:
        """
        Estimate adjustment magnitude based on current confidence.
        
        Implements explore-exploit tradeoff:
        - Low confidence (few samples) -> larger adjustments
        - High confidence (many samples) -> smaller adjustments
        
        Args:
            belief: Current threshold belief
            
        Returns:
            Adjustment magnitude (always positive)
        """
        # Maximum adjustment when uncertain, minimum when confident
        max_adjustment = 8.0  # Maximum adjustment %
        min_adjustment = 2.0  # Minimum adjustment %
        
        # Confidence-based scaling
        # confidence = 0 -> max_adjustment
        # confidence = 1 -> min_adjustment
        adjustment = max_adjustment - (belief.confidence * (max_adjustment - min_adjustment))
        
        # Also scale by uncertainty (std_dev)
        # Higher uncertainty -> slightly larger adjustment
        uncertainty_factor = min(1.5, 1.0 + (belief.std_dev / 20.0))
        
        return adjustment * uncertainty_factor
    
    def _calculate_user_consistency(
        self,
        user_id: int,
        unit_id: int,
    ) -> float:
        """
        Calculate how consistent user feedback is.
        
        Consistent users get higher weight in updates.
        
        Returns:
            0.0 = very inconsistent (noisy feedback)
            1.0 = very consistent (reliable feedback)
        """
        if not self._workflow_repo:
            return 0.5  # Default to moderate consistency
        
        try:
            pref = self._workflow_repo.get_user_preference(user_id, unit_id)
            if not pref:
                return 0.5
            
            total_feedback = pref.get("moisture_feedback_count", 0)
            if total_feedback < 5:
                return 0.5  # Not enough data
            
            too_little = pref.get("too_little_feedback_count", 0)
            just_right = pref.get("just_right_feedback_count", 0)
            too_much = pref.get("too_much_feedback_count", 0)
            
            # High just_right rate = consistent (threshold is calibrated)
            just_right_rate = just_right / total_feedback if total_feedback > 0 else 0
            
            # If user alternates between too_little and too_much, they're inconsistent
            extreme_feedback = too_little + too_much
            if extreme_feedback > 0:
                balance = abs(too_little - too_much) / extreme_feedback
            else:
                balance = 1.0  # No extreme feedback is good
            
            # Combine factors
            consistency = (just_right_rate * 0.6 + balance * 0.4)
            
            return max(0.2, min(1.0, consistency))
            
        except Exception as e:
            logger.warning(f"Failed to calculate user consistency: {e}")
            return 0.5
    
    def _get_observation_variance(self, user_consistency: float) -> float:
        """
        Get observation variance based on user consistency.
        
        Consistent users have lower variance (more trusted).
        Inconsistent users have higher variance (less trusted).
        
        Args:
            user_consistency: 0.0 to 1.0 consistency score
            
        Returns:
            Observation variance for Bayesian update
        """
        # High consistency -> low variance -> high weight
        # Low consistency -> high variance -> low weight
        
        # Variance ranges from base*0.5 (very consistent) to base*2 (very inconsistent)
        variance_multiplier = 2.5 - (user_consistency * 2.0)  # 0.5 to 2.5
        
        return self._base_observation_variance * variance_multiplier
    
    def _persist_belief(
        self,
        unit_id: int,
        user_id: int,
        belief: ThresholdBelief,
        *,
        belief_key: Optional[str] = None,
    ) -> bool:
        """
        Persist belief to database.
        
        Stores as JSON in IrrigationUserPreference.threshold_belief_json
        """
        if not self._workflow_repo:
            return False
        
        try:
            belief_key = belief_key or self._belief_key(
                belief.plant_type or "default",
                belief.growth_stage or "vegetative",
            )
            existing = {}
            try:
                pref = self._workflow_repo.get_user_preference(user_id, unit_id)
                if pref and pref.get("threshold_belief_json"):
                    existing = json.loads(pref["threshold_belief_json"]) or {}
            except (json.JSONDecodeError, TypeError):
                existing = {}

            if isinstance(existing, dict) and "mean" in existing:
                existing = {"default": existing}

            if not isinstance(existing, dict):
                existing = {}

            existing[belief_key] = belief.to_dict()
            belief_json = json.dumps(existing)
            
            # Update the preference record
            # Note: This requires a new column in IrrigationUserPreference
            # For now, we store in preferred_moisture_threshold field
            # TODO: Add threshold_belief_json column in migration
            
            return self._workflow_repo.update_threshold_belief(
                user_id=user_id,
                unit_id=unit_id,
                threshold_mean=belief.mean,
                threshold_variance=belief.variance,
                sample_count=belief.sample_count,
                belief_json=belief_json,
            )
        except Exception as e:
            logger.error(f"Failed to persist belief: {e}")
            return False
    
    def reset_belief(
        self,
        unit_id: int,
        user_id: int,
        plant_type: str = "default",
        growth_stage: str = "Vegetative",
    ) -> ThresholdBelief:
        """
        Reset belief to prior for a unit/user.
        
        Useful when user wants to start fresh or plant changes.
        """
        belief_key = self._belief_key(plant_type, growth_stage)
        cache_key = (unit_id, user_id, belief_key)
        
        prior = self.get_prior(plant_type, growth_stage, user_id=user_id)
        self._beliefs[cache_key] = prior
        self._persist_belief(unit_id, user_id, prior, belief_key=belief_key)
        
        logger.info(f"Reset threshold belief for unit {unit_id}, user {user_id}")
        return prior
    
    def get_statistics(
        self,
        unit_id: int,
        user_id: int,
        plant_type: str = "default",
        growth_stage: str = "Vegetative",
        *,
        plant_variety: Optional[str] = None,
        strain_variety: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Get statistics about the threshold learning for a unit/user.
        """
        belief = self.get_belief(
            unit_id,
            user_id,
            plant_type,
            growth_stage,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )
        
        lower, upper = belief.credible_interval(0.95)
        
        return {
            "current_estimate": round(belief.mean, 1),
            "uncertainty": round(belief.std_dev, 2),
            "confidence": round(belief.confidence, 2),
            "sample_count": belief.sample_count,
            "credible_interval_95": {
                "lower": round(lower, 1),
                "upper": round(upper, 1),
            },
            "last_updated": belief.last_updated,
            "plant_type": belief.plant_type,
            "growth_stage": belief.growth_stage,
        }
