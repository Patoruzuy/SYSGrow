"""
Irrigation Predictor Service
=============================
ML-based irrigation optimization using historical data and user behavior patterns.

Provides predictions for:
- Optimal soil moisture threshold (learned from user feedback)
- User response probability (approve/delay/cancel)
- Optimal irrigation duration (learned from before/after moisture)
- Preferred irrigation time (learned from user patterns)

Author: SYSGrow Team
Date: January 2026
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from app.domain.irrigation import (
    MoistureDeclinePrediction,
    PredictionConfidence,
    UserResponsePrediction,
    ThresholdPrediction,
    DurationPrediction,
    TimingPrediction,
    IrrigationPrediction,
)
from app.utils.time import utc_now
from app.constants import (
    IRRIGATION_THRESHOLDS,
    IRRIGATION_DURATIONS,
    GROWTH_STAGE_MOISTURE_ADJUSTMENTS,
)

if TYPE_CHECKING:
    from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository
    from app.services.ai.model_registry import ModelRegistry
    from app.services.ai.feature_engineering import FeatureEngineer
    from app.services.ai.recommendation_provider import RecommendationProvider

logger = logging.getLogger(__name__)


class IrrigationPredictor:
    """
    ML-based irrigation optimization predictor.
    
    Uses historical data and user behavior patterns to provide
    predictions for irrigation optimization. Initially rule-based
    with Bayesian updates, can be enhanced with trained ML models.
    """
    
    def __init__(
        self,
        irrigation_ml_repo: "IrrigationMLRepository",
        model_registry: Optional["ModelRegistry"] = None,
        feature_engineer: Optional["FeatureEngineer"] = None,
        recommendation_provider: Optional["RecommendationProvider"] = None,
    ):
        """
        Initialize irrigation predictor.
        
        Args:
            irrigation_ml_repo: Repository for irrigation ML data
            model_registry: Optional model registry for trained models
            feature_engineer: Optional feature engineering service
        """
        self._repo = irrigation_ml_repo
        self._model_registry = model_registry
        self._feature_engineer = feature_engineer
        self._recommendation_provider = recommendation_provider

        if self._recommendation_provider is None:
            try:
                from app.services.ai.recommendation_provider import RuleBasedRecommendationProvider

                self._recommendation_provider = RuleBasedRecommendationProvider()
            except Exception as exc:
                logger.debug("Recommendation provider not available: %s", exc)
                self._recommendation_provider = None
        
        # Cached models (loaded on demand)
        self._threshold_model = None
        self._response_model = None
        self._duration_model = None
        self._timing_model = None
        self._model_bundles: Dict[str, Dict[str, Any]] = {}
        
        # Bayesian priors (updated from data)
        self._threshold_priors: Dict[str, Dict[str, float]] = {}
        self._response_priors: Dict[int, Dict[str, float]] = {}
        
        self._models_loaded = False
    
    def load_models(self) -> bool:
        """
        Load prediction models from registry.
        
        Returns:
            True if models loaded successfully
        """
        try:
            logger.info("Loading irrigation prediction models...")
            
            if self._model_registry:
                self._model_bundles = {}
                model_specs = {
                    "threshold_optimizer": ("irrigation_threshold", "regression"),
                    "response_predictor": ("irrigation_response", "classification"),
                    "duration_optimizer": ("irrigation_duration", "regression"),
                    "timing_predictor": ("irrigation_timing", "classification"),
                }

                for key, (model_name, kind) in model_specs.items():
                    model = self._model_registry.load_model(model_name)
                    if model is None:
                        continue

                    scaler = self._model_registry.load_artifact(model_name, "scaler")
                    label_encoder = None
                    if kind == "classification":
                        label_encoder = self._model_registry.load_artifact(model_name, "label_encoder")

                    metadata = self._model_registry.get_metadata(model_name)
                    features = list(metadata.features) if metadata and metadata.features else []

                    self._model_bundles[key] = {
                        "model": model,
                        "scaler": scaler,
                        "label_encoder": label_encoder,
                        "metadata": metadata,
                        "features": features,
                        "kind": kind,
                        "model_name": model_name,
                    }

                    if key == "threshold_optimizer":
                        self._threshold_model = model
                    elif key == "response_predictor":
                        self._response_model = model
                    elif key == "duration_optimizer":
                        self._duration_model = model
                    elif key == "timing_predictor":
                        self._timing_model = model

                loaded = len(self._model_bundles)
                logger.info(f"Loaded {loaded}/4 trained ML models")
            
            self._models_loaded = True
            logger.info("✅ Irrigation prediction models ready")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load irrigation models: {e}", exc_info=True)
            self._models_loaded = False
            return False

    @staticmethod
    def _coerce_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return float(default)
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    def _get_model_metrics(self, model_key: str) -> Dict[str, float]:
        bundle = self._model_bundles.get(model_key)
        metadata = bundle.get("metadata") if bundle else None
        metrics = metadata.metrics if metadata and getattr(metadata, "metrics", None) else {}
        if not isinstance(metrics, dict):
            return {}
        return {
            key: self._coerce_float(value, default=0.0)
            for key, value in metrics.items()
        }

    def _passes_gate(self, model_key: str) -> Tuple[bool, float, Dict[str, float]]:
        metrics = self._get_model_metrics(model_key)
        if not metrics:
            return False, 0.0, {}

        if model_key == "response_predictor":
            macro_f1 = metrics.get("macro_f1")
            balanced_acc = metrics.get("balanced_accuracy")
            if macro_f1 is None or balanced_acc is None:
                return False, 0.0, metrics
            passed = macro_f1 >= 0.55 and balanced_acc >= 0.55
            return passed, max(0.0, min(1.0, macro_f1)), metrics

        if model_key == "timing_predictor":
            top3 = metrics.get("top3_accuracy")
            mrr = metrics.get("mrr")
            if top3 is None or mrr is None:
                return False, 0.0, metrics
            passed = top3 >= 0.60 and mrr >= 0.55
            return passed, max(0.0, min(1.0, top3)), metrics

        if model_key == "threshold_optimizer":
            mae = metrics.get("mae")
            r2 = metrics.get("test_score") if "test_score" in metrics else metrics.get("r2")
            passed = (mae is not None and mae <= 4.0) or (r2 is not None and r2 >= 0.55)
            confidence = r2 if r2 is not None else 0.0
            if confidence < 0.0:
                confidence = 0.0
            if confidence == 0.0 and mae is not None:
                confidence = max(0.0, min(1.0, 1.0 - (mae / 100.0)))
            return passed, confidence, metrics

        if model_key == "duration_optimizer":
            mae = metrics.get("mae")
            mape = metrics.get("mape")
            if mae is None or mape is None:
                return False, 0.0, metrics
            passed = mae <= 25.0 and mape <= 0.40
            confidence = max(0.0, min(1.0, 1.0 - mape))
            return passed, confidence, metrics

        return False, 0.0, metrics

    def _get_model_features(self, model_key: str) -> List[str]:
        bundle = self._model_bundles.get(model_key)
        if bundle and bundle.get("features"):
            return list(bundle.get("features") or [])
        if self._feature_engineer and hasattr(self._feature_engineer, "get_irrigation_model_features"):
            try:
                return self._feature_engineer.get_irrigation_model_features(model_key)
            except Exception:
                pass
        return self._default_irrigation_features(model_key)

    @staticmethod
    def _default_irrigation_features(model_key: str) -> List[str]:
        defaults = {
            "threshold_optimizer": [
                "temperature_at_detection",
                "humidity_at_detection",
                "soil_moisture_detected",
                "hours_since_last_irrigation",
                "plant_stage_vegetative",
                "plant_stage_flowering",
                "plant_stage_fruiting",
                "user_consistency_score",
                "current_threshold",
            ],
            "response_predictor": [
                "hour_of_day",
                "day_of_week",
                "is_weekend",
                "soil_moisture_detected",
                "temperature_at_detection",
                "humidity_at_detection",
                "hours_since_last_irrigation",
            ],
            "duration_optimizer": [
                "soil_moisture_detected",
                "target_moisture",
                "temperature_at_detection",
                "humidity_at_detection",
                "avg_previous_duration",
            ],
            "timing_predictor": [
                "hour_of_day",
                "day_of_week",
                "is_weekend",
                "soil_moisture_detected",
                "temperature_at_detection",
                "humidity_at_detection",
                "hours_since_last_irrigation",
            ],
        }
        return list(defaults.get(model_key, []))

    def _align_features(self, feature_values: Dict[str, Any], expected: List[str]) -> List[float]:
        row: List[float] = []
        for feature in expected:
            value = feature_values.get(feature)
            row.append(self._coerce_float(value, default=0.0))
        return row

    def _compute_hours_since_last_irrigation(
        self,
        irrigation_history: List[Dict[str, Any]],
        now: Optional[datetime] = None,
    ) -> Optional[float]:
        if not irrigation_history:
            return None

        from app.utils.time import coerce_datetime, utc_now

        current_time = now or utc_now()
        latest_time: Optional[datetime] = None

        for record in irrigation_history:
            for key in ("executed_at_utc", "executed_at", "triggered_at_utc", "detected_at", "created_at_utc"):
                raw = record.get(key)
                if raw:
                    parsed = coerce_datetime(raw)
                    if parsed:
                        latest_time = parsed
                        break
            if latest_time is not None:
                break

        if latest_time is None:
            return None

        return max(0.0, (current_time - latest_time).total_seconds() / 3600.0)

    def _compute_avg_previous_duration(
        self,
        irrigation_history: List[Dict[str, Any]],
        fallback_seconds: int,
    ) -> float:
        durations: List[float] = []
        for record in irrigation_history or []:
            duration = record.get("actual_duration_s") or record.get("execution_duration_seconds")
            if duration is None:
                continue
            try:
                durations.append(float(duration))
            except (TypeError, ValueError):
                continue
        if durations:
            return sum(durations) / len(durations)
        return float(fallback_seconds)

    def _normalize_growth_stage(self, growth_stage: Optional[str]) -> str:
        if not growth_stage:
            return "Vegetative"
        value = str(growth_stage).strip().lower()
        if value.startswith("veg"):
            return "Vegetative"
        if value.startswith("flow"):
            return "Flowering"
        if value.startswith("fruit"):
            return "Fruiting"
        return growth_stage.title()

    def _build_feature_context(
        self,
        feature_context: Optional[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        if not feature_context:
            return {}, [], {}, {}
        return (
            feature_context.get("current_conditions") or {},
            feature_context.get("irrigation_history") or [],
            feature_context.get("user_preferences") or {},
            feature_context.get("plant_info") or {},
        )
    
    def predict_threshold(
        self,
        unit_id: int,
        plant_type: str,
        growth_stage: str,
        current_threshold: float,
        *,
        feature_context: Optional[Dict[str, Any]] = None,
    ) -> ThresholdPrediction:
        """
        Predict optimal soil moisture threshold.
        
        Uses Bayesian updating based on:
        - Plant type defaults
        - User feedback history (too_little/just_right/too_much)
        - Growth stage adjustments
        
        Args:
            unit_id: Grow unit ID
            plant_type: Plant type name
            growth_stage: Current growth stage
            current_threshold: Current threshold setting
            
        Returns:
            ThresholdPrediction with optimal threshold
        """
        try:
            use_ml, confidence_metric, metrics = self._passes_gate("threshold_optimizer")
            if use_ml:
                bundle = self._model_bundles.get("threshold_optimizer", {})
                current_conditions, irrigation_history, user_preferences, plant_info = self._build_feature_context(
                    feature_context
                )
                now = utc_now()
                hours_since = (
                    current_conditions.get("hours_since_last_irrigation")
                    or self._compute_hours_since_last_irrigation(irrigation_history, now=now)
                    or 0.0
                )
                stage = self._normalize_growth_stage(
                    growth_stage or plant_info.get("growth_stage")  # type: ignore[arg-type]
                )
                feature_values = {
                    "temperature_at_detection": current_conditions.get("temperature"),
                    "humidity_at_detection": current_conditions.get("humidity"),
                    "soil_moisture_detected": current_conditions.get("soil_moisture"),
                    "hours_since_last_irrigation": hours_since,
                    "plant_stage_vegetative": 1.0 if stage == "Vegetative" else 0.0,
                    "plant_stage_flowering": 1.0 if stage == "Flowering" else 0.0,
                    "plant_stage_fruiting": 1.0 if stage == "Fruiting" else 0.0,
                    "user_consistency_score": user_preferences.get("user_consistency_score", 0.7),
                    "current_threshold": current_threshold,
                }

                expected_features = self._get_model_features("threshold_optimizer")
                row = self._align_features(feature_values, expected_features)
                if bundle.get("scaler") is not None:
                    row = bundle["scaler"].transform([row])[0].tolist()
                prediction = bundle["model"].predict([row])[0]
                optimal = max(20.0, min(80.0, float(prediction)))

                mae = metrics.get("mae")
                r2 = metrics.get("test_score") if metrics.get("test_score") is not None else metrics.get("r2")
                metric_note = []
                if mae is not None:
                    metric_note.append(f"mae={mae:.2f}")
                if r2 is not None:
                    metric_note.append(f"r2={r2:.2f}")

                return ThresholdPrediction(
                    optimal_threshold=round(optimal, 1),
                    current_threshold=current_threshold,
                    adjustment_direction=self._get_direction(current_threshold, optimal),
                    adjustment_amount=round(abs(optimal - current_threshold), 1),
                    confidence=float(confidence_metric),
                    reasoning=(
                        "ML model prediction"
                        + (f" ({', '.join(metric_note)})" if metric_note else "")
                    ),
                )

            # Get training data for threshold optimization
            training_data = self._repo.get_training_data_for_model(
                "threshold_optimizer",
                unit_id=unit_id,
                limit=100,
            )
            
            # Start with plant type default
            base_threshold = IRRIGATION_THRESHOLDS.get(
                plant_type.lower(),
                IRRIGATION_THRESHOLDS["default"],
            )
            
            # Apply growth stage adjustment from shared constants
            stage_adj = GROWTH_STAGE_MOISTURE_ADJUSTMENTS.get(growth_stage, 0.0)
            
            if not training_data:
                # No training data - use defaults
                optimal = base_threshold + stage_adj
                return ThresholdPrediction(
                    optimal_threshold=optimal,
                    current_threshold=current_threshold,
                    adjustment_direction=self._get_direction(current_threshold, optimal),
                    adjustment_amount=abs(optimal - current_threshold),
                    confidence=0.3,  # Low confidence without data
                    reasoning="Using plant type defaults (no feedback data yet)",
                )
            
            # Bayesian update from timing feedback
            # Count timing feedback types
            triggered_early = sum(
                1 for d in training_data if d.get("feedback_response") == "triggered_too_early"
            )
            triggered_late = sum(
                1 for d in training_data if d.get("feedback_response") == "triggered_too_late"
            )
            total = triggered_early + triggered_late
            
            if total == 0:
                optimal = base_threshold + stage_adj
                return ThresholdPrediction(
                    optimal_threshold=optimal,
                    current_threshold=current_threshold,
                    adjustment_direction=self._get_direction(current_threshold, optimal),
                    adjustment_amount=abs(optimal - current_threshold),
                    confidence=0.3,
                    reasoning="Using plant type defaults (no timing feedback)",
                )
            
            # Calculate weighted adjustment
            # triggered_too_late -> increase threshold (trigger earlier)
            # triggered_too_early -> decrease threshold (trigger later)
            adjustment_weight = (triggered_late - triggered_early) / total
            max_adjustment = 10.0  # Maximum adjustment per cycle
            
            feedback_adjustment = adjustment_weight * max_adjustment
            
            optimal = current_threshold + feedback_adjustment + (stage_adj * 0.3)
            
            # Clamp to reasonable range
            optimal = max(20.0, min(80.0, optimal))
            
            # Calculate confidence based on data quantity and consistency
            data_confidence = min(1.0, total / 30)  # Max confidence at 30 samples
            confidence = data_confidence
            
            # Determine reasoning
            if abs(feedback_adjustment) < 1.0:
                reasoning = f"Current threshold is well-calibrated ({total} timing feedback)"
            elif feedback_adjustment > 0:
                reasoning = f"Increasing threshold based on {triggered_late} late trigger feedbacks"
            else:
                reasoning = f"Decreasing threshold based on {triggered_early} early trigger feedbacks"
            
            return ThresholdPrediction(
                optimal_threshold=round(optimal, 1),
                current_threshold=current_threshold,
                adjustment_direction=self._get_direction(current_threshold, optimal),
                adjustment_amount=round(abs(optimal - current_threshold), 1),
                confidence=confidence,
                reasoning=reasoning,
            )
            
        except Exception as e:
            logger.error(f"Threshold prediction failed: {e}", exc_info=True)
            return ThresholdPrediction(
                optimal_threshold=current_threshold,
                current_threshold=current_threshold,
                adjustment_direction="maintain",
                adjustment_amount=0.0,
                confidence=0.0,
                reasoning=f"Prediction failed: {str(e)}",
            )
    
    def predict_user_response(
        self,
        unit_id: int,
        current_moisture: float,
        threshold: float,
        hour_of_day: int,
        day_of_week: int,
        *,
        feature_context: Optional[Dict[str, Any]] = None,
    ) -> UserResponsePrediction:
        """
        Predict probability of user response types.
        
        Uses historical response patterns to predict likely user action.
        
        Args:
            unit_id: Grow unit ID
            current_moisture: Current soil moisture
            threshold: Threshold that triggered detection
            hour_of_day: Hour (0-23)
            day_of_week: Day (0=Monday, 6=Sunday)
            
        Returns:
            UserResponsePrediction with probabilities
        """
        try:
            use_ml, confidence_metric, metrics = self._passes_gate("response_predictor")
            if use_ml:
                bundle = self._model_bundles.get("response_predictor", {})
                current_conditions, irrigation_history, _, _ = self._build_feature_context(
                    feature_context
                )
                now = utc_now()
                hours_since = (
                    current_conditions.get("hours_since_last_irrigation")
                    or self._compute_hours_since_last_irrigation(irrigation_history, now=now)
                    or 0.0
                )

                feature_values = {
                    "hour_of_day": hour_of_day,
                    "day_of_week": day_of_week,
                    "is_weekend": 1 if day_of_week >= 5 else 0,
                    "soil_moisture_detected": current_moisture,
                    "temperature_at_detection": current_conditions.get("temperature"),
                    "humidity_at_detection": current_conditions.get("humidity"),
                    "hours_since_last_irrigation": hours_since,
                }

                expected_features = self._get_model_features("response_predictor")
                row = self._align_features(feature_values, expected_features)
                if bundle.get("scaler") is not None:
                    row = bundle["scaler"].transform([row])[0].tolist()

                model = bundle.get("model")
                proba = model.predict_proba([row])[0] if hasattr(model, "predict_proba") else None
                if proba is None:
                    pred = model.predict([row])[0]
                    proba = [0.0] * len(set([pred]))

                labels: List[str] = []
                label_encoder = bundle.get("label_encoder")
                metadata = bundle.get("metadata")
                if label_encoder is not None:
                    try:
                        labels = [str(lbl) for lbl in label_encoder.inverse_transform(range(len(proba)))]
                    except Exception:
                        labels = []
                if not labels and metadata and getattr(metadata, "parameters", None):
                    labels = [str(v) for v in metadata.parameters.get("class_names", [])]
                if not labels:
                    labels = ["approve", "delay", "cancel"][: len(proba)]

                probabilities = dict(zip(labels, proba))
                approve_prob = float(probabilities.get("approve", 0.0))
                delay_prob = float(probabilities.get("delay", 0.0))
                cancel_prob = float(probabilities.get("cancel", 0.0))

                most_likely = max(probabilities, key=probabilities.get) if probabilities else "approve"
                max_prob = float(max(proba)) if proba is not None and len(proba) > 0 else 0.0
                confidence = min(1.0, max_prob * max(0.5, confidence_metric))

                return UserResponsePrediction(
                    approve_probability=approve_prob,
                    delay_probability=delay_prob,
                    cancel_probability=cancel_prob,
                    most_likely=most_likely,
                    confidence=confidence,
                )

            # Get response history
            training_data = self._repo.get_training_data_for_model(
                "response_predictor",
                unit_id=unit_id,
                limit=100,
            )
            
            if not training_data:
                # Default: assume user approves most of the time
                return UserResponsePrediction(
                    approve_probability=0.7,
                    delay_probability=0.2,
                    cancel_probability=0.1,
                    most_likely="approve",
                    confidence=0.3,
                )
            
            # Count responses
            approve_count = sum(1 for d in training_data if d.get("user_response") == "approve")
            delay_count = sum(1 for d in training_data if d.get("user_response") == "delay")
            cancel_count = sum(1 for d in training_data if d.get("user_response") == "cancel")
            total = approve_count + delay_count + cancel_count
            
            if total == 0:
                return UserResponsePrediction(
                    approve_probability=0.7,
                    delay_probability=0.2,
                    cancel_probability=0.1,
                    most_likely="approve",
                    confidence=0.3,
                )
            
            # Base probabilities from history
            base_approve = approve_count / total
            base_delay = delay_count / total
            base_cancel = cancel_count / total
            
            # Time-of-day adjustments
            # Users often delay during work hours, cancel late at night
            is_work_hours = 9 <= hour_of_day <= 17
            is_late_night = hour_of_day >= 22 or hour_of_day <= 6
            is_weekend = day_of_week >= 5
            
            time_adjust_delay = 0.1 if is_work_hours and not is_weekend else 0.0
            time_adjust_cancel = 0.1 if is_late_night else 0.0
            
            # Moisture urgency adjustment
            # Lower moisture = more urgent = higher approve rate
            moisture_ratio = current_moisture / threshold if threshold > 0 else 1.0
            urgency_adjust = max(0, (0.8 - moisture_ratio) * 0.2)  # Up to 0.2 boost
            
            # Apply adjustments
            approve_prob = base_approve + urgency_adjust - time_adjust_delay - time_adjust_cancel
            delay_prob = base_delay + time_adjust_delay
            cancel_prob = base_cancel + time_adjust_cancel
            
            # Normalize
            total_prob = approve_prob + delay_prob + cancel_prob
            if total_prob > 0:
                approve_prob /= total_prob
                delay_prob /= total_prob
                cancel_prob /= total_prob
            
            # Determine most likely
            probs = {"approve": approve_prob, "delay": delay_prob, "cancel": cancel_prob}
            most_likely = max(probs, key=probs.get)
            
            # Confidence based on data quantity
            confidence = min(1.0, total / 20) * max(probs.values())
            
            return UserResponsePrediction(
                approve_probability=approve_prob,
                delay_probability=delay_prob,
                cancel_probability=cancel_prob,
                most_likely=most_likely,
                confidence=confidence,
            )
            
        except Exception as e:
            logger.error(f"Response prediction failed: {e}", exc_info=True)
            return UserResponsePrediction(
                approve_probability=0.5,
                delay_probability=0.3,
                cancel_probability=0.2,
                most_likely="approve",
                confidence=0.0,
            )
    
    def predict_duration(
        self,
        unit_id: int,
        current_moisture: float,
        target_moisture: float,
        current_default_seconds: int = 120,
        soil_type: Optional[str] = None,
        *,
        feature_context: Optional[Dict[str, Any]] = None,
    ) -> DurationPrediction:
        """
        Predict optimal irrigation duration.
        
        Learns from historical irrigation events with before/after moisture.
        
        Args:
            unit_id: Grow unit ID
            current_moisture: Current soil moisture
            target_moisture: Target moisture after irrigation
            current_default_seconds: Current default duration
            soil_type: Optional soil type for adjustment
            
        Returns:
            DurationPrediction with recommended duration
        """
        try:
            use_ml, confidence_metric, metrics = self._passes_gate("duration_optimizer")
            if use_ml:
                bundle = self._model_bundles.get("duration_optimizer", {})
                current_conditions, irrigation_history, _, _ = self._build_feature_context(
                    feature_context
                )
                avg_prev = self._compute_avg_previous_duration(
                    irrigation_history,
                    fallback_seconds=current_default_seconds,
                )

                feature_values = {
                    "soil_moisture_detected": current_moisture,
                    "target_moisture": target_moisture,
                    "temperature_at_detection": current_conditions.get("temperature"),
                    "humidity_at_detection": current_conditions.get("humidity"),
                    "avg_previous_duration": avg_prev,
                }
                expected_features = self._get_model_features("duration_optimizer")
                row = self._align_features(feature_values, expected_features)
                if bundle.get("scaler") is not None:
                    row = bundle["scaler"].transform([row])[0].tolist()
                prediction = bundle["model"].predict([row])[0]

                recommended_seconds = int(max(30, min(600, float(prediction))))
                expected_increase = max(0.0, float(target_moisture) - float(current_moisture))

                mae = metrics.get("mae")
                mape = metrics.get("mape")
                metric_note = []
                if mae is not None:
                    metric_note.append(f"mae={mae:.1f}s")
                if mape is not None:
                    metric_note.append(f"mape={mape:.2f}")

                return DurationPrediction(
                    recommended_seconds=recommended_seconds,
                    current_default_seconds=current_default_seconds,
                    expected_moisture_increase=round(expected_increase, 1),
                    confidence=float(confidence_metric),
                    reasoning=(
                        "ML model prediction"
                        + (f" ({', '.join(metric_note)})" if metric_note else "")
                    ),
                )

            # Get duration history
            training_data = self._repo.get_training_data_for_model(
                "duration_optimizer",
                unit_id=unit_id,
                limit=50,
            )
            
            # Start with soil type default
            base_duration = IRRIGATION_DURATIONS.get(
                (soil_type or "").lower(),
                IRRIGATION_DURATIONS["default"],
            )
            
            if not training_data:
                return DurationPrediction(
                    recommended_seconds=base_duration,
                    current_default_seconds=current_default_seconds,
                    expected_moisture_increase=15.0,  # Estimate
                    confidence=0.3,
                    reasoning="Using soil type defaults (no historical data)",
                )
            
            # Calculate moisture increase per second from history
            moisture_per_second_samples = []
            
            for record in training_data:
                before = record.get("soil_moisture_detected")
                after = record.get("soil_moisture_after")
                duration = record.get("execution_duration_seconds")
                
                if all(v is not None for v in [before, after, duration]) and duration > 0:
                    increase = after - before
                    if increase > 0:
                        rate = increase / duration
                        moisture_per_second_samples.append(rate)
            
            if not moisture_per_second_samples:
                return DurationPrediction(
                    recommended_seconds=base_duration,
                    current_default_seconds=current_default_seconds,
                    expected_moisture_increase=15.0,
                    confidence=0.3,
                    reasoning="Using defaults (insufficient data for rate calculation)",
                )
            
            # Calculate average moisture increase rate
            avg_rate = sum(moisture_per_second_samples) / len(moisture_per_second_samples)
            
            # Calculate required duration
            moisture_deficit = target_moisture - current_moisture
            if moisture_deficit <= 0:
                return DurationPrediction(
                    recommended_seconds=0,
                    current_default_seconds=current_default_seconds,
                    expected_moisture_increase=0.0,
                    confidence=0.8,
                    reasoning="No irrigation needed - current moisture above target",
                )
            
            recommended_seconds = int(moisture_deficit / avg_rate) if avg_rate > 0 else base_duration
            
            # Clamp to reasonable range
            recommended_seconds = max(30, min(600, recommended_seconds))
            
            # Calculate expected increase with recommended duration
            expected_increase = recommended_seconds * avg_rate
            
            # Confidence based on data consistency
            if len(moisture_per_second_samples) >= 10:
                import statistics
                std_dev = statistics.stdev(moisture_per_second_samples)
                mean = statistics.mean(moisture_per_second_samples)
                cv = std_dev / mean if mean > 0 else 1.0  # Coefficient of variation
                confidence = min(1.0, max(0.3, 1.0 - cv))
            else:
                confidence = 0.4 + (len(moisture_per_second_samples) * 0.05)
            
            return DurationPrediction(
                recommended_seconds=recommended_seconds,
                current_default_seconds=current_default_seconds,
                expected_moisture_increase=round(expected_increase, 1),
                confidence=min(1.0, confidence),
                reasoning=f"Based on {len(moisture_per_second_samples)} historical irrigations "
                         f"(avg {avg_rate:.3f}% per second)",
            )
            
        except Exception as e:
            logger.error(f"Duration prediction failed: {e}", exc_info=True)
            return DurationPrediction(
                recommended_seconds=current_default_seconds,
                current_default_seconds=current_default_seconds,
                expected_moisture_increase=15.0,
                confidence=0.0,
                reasoning=f"Prediction failed: {str(e)}",
            )
    
    def predict_timing(
        self,
        unit_id: int,
        day_of_week: int,
        *,
        feature_context: Optional[Dict[str, Any]] = None,
    ) -> TimingPrediction:
        """
        Predict user's preferred irrigation time.
        
        Learns from approval/delay patterns to find optimal timing.
        
        Args:
            unit_id: Grow unit ID
            day_of_week: Day (0=Monday, 6=Sunday)
            
        Returns:
            TimingPrediction with preferred time
        """
        try:
            use_ml, confidence_metric, metrics = self._passes_gate("timing_predictor")
            if use_ml:
                bundle = self._model_bundles.get("timing_predictor", {})
                current_conditions, irrigation_history, _, _ = self._build_feature_context(
                    feature_context
                )
                now = utc_now()
                hours_since = (
                    current_conditions.get("hours_since_last_irrigation")
                    or self._compute_hours_since_last_irrigation(irrigation_history, now=now)
                    or 0.0
                )

                feature_values = {
                    "hour_of_day": now.hour,
                    "day_of_week": day_of_week,
                    "is_weekend": 1 if day_of_week >= 5 else 0,
                    "soil_moisture_detected": current_conditions.get("soil_moisture"),
                    "temperature_at_detection": current_conditions.get("temperature"),
                    "humidity_at_detection": current_conditions.get("humidity"),
                    "hours_since_last_irrigation": hours_since,
                }

                expected_features = self._get_model_features("timing_predictor")
                row = self._align_features(feature_values, expected_features)
                if bundle.get("scaler") is not None:
                    row = bundle["scaler"].transform([row])[0].tolist()

                model = bundle.get("model")
                proba = model.predict_proba([row])[0] if hasattr(model, "predict_proba") else None
                if proba is None:
                    pred = model.predict([row])[0]
                    proba = [0.0] * len(set([pred]))

                labels: List[str] = []
                label_encoder = bundle.get("label_encoder")
                metadata = bundle.get("metadata")
                if label_encoder is not None:
                    try:
                        labels = [str(lbl) for lbl in label_encoder.inverse_transform(range(len(proba)))]
                    except Exception:
                        labels = []
                if not labels and hasattr(model, "classes_"):
                    labels = [str(lbl) for lbl in model.classes_]
                if not labels and metadata and getattr(metadata, "parameters", None):
                    labels = [str(v) for v in metadata.parameters.get("class_names", [])]

                # Map probabilities to hours
                hour_probs: Dict[int, float] = {}
                for idx, prob in enumerate(proba):
                    try:
                        hour_val = int(float(labels[idx])) if idx < len(labels) else idx
                    except (TypeError, ValueError):
                        hour_val = idx
                    hour_probs[hour_val] = float(prob)

                if not hour_probs:
                    hour_probs = {now.hour: 1.0}

                preferred_hour = max(hour_probs, key=hour_probs.get)
                max_prob = max(hour_probs.values()) if hour_probs else 0.0

                avoid_hours = [
                    hour for hour, _ in sorted(hour_probs.items(), key=lambda item: item[1])[:3]
                ]
                avoid_times = [f"{hour:02d}:00" for hour in avoid_hours]

                metric_note = []
                if metrics.get("top3_accuracy") is not None:
                    metric_note.append(f"top3={metrics.get('top3_accuracy'):.2f}")
                if metrics.get("mrr") is not None:
                    metric_note.append(f"mrr={metrics.get('mrr'):.2f}")

                confidence = min(1.0, max_prob * max(0.5, confidence_metric))

                return TimingPrediction(
                    preferred_time=f"{preferred_hour:02d}:00",
                    preferred_hour=int(preferred_hour),
                    preferred_minute=0,
                    avoid_times=avoid_times,
                    confidence=confidence,
                    reasoning=(
                        "ML model prediction"
                        + (f" ({', '.join(metric_note)})" if metric_note else "")
                    ),
                )

            metric_note = []
            if metrics.get("top3_accuracy") is not None:
                metric_note.append(f"top3={metrics.get('top3_accuracy'):.2f}")
            if metrics.get("mrr") is not None:
                metric_note.append(f"mrr={metrics.get('mrr'):.2f}")

            return TimingPrediction(
                preferred_time="00:00",
                preferred_hour=0,
                preferred_minute=0,
                avoid_times=[],
                confidence=0.0,
                reasoning=(
                    "ML timing model unavailable or below accuracy thresholds"
                    + (f" ({', '.join(metric_note)})" if metric_note else "")
                ),
            )
            
        except Exception as e:
            logger.error(f"Timing prediction failed: {e}", exc_info=True)
            return TimingPrediction(
                preferred_time="09:00",
                preferred_hour=9,
                preferred_minute=0,
                avoid_times=[],
                confidence=0.0,
                reasoning=f"Prediction failed: {str(e)}",
            )
    
    def get_comprehensive_prediction(
        self,
        unit_id: int,
        plant_type: str,
        growth_stage: str,
        current_conditions: Dict[str, float],
        current_threshold: float,
        current_default_duration: int = 120,
        enabled_models: Optional[List[str]] = None,
        plant_id: Optional[int] = None,
        feature_context: Optional[Dict[str, Any]] = None,
    ) -> IrrigationPrediction:
        """
        Get comprehensive irrigation prediction.
        
        Combines all prediction models for a complete recommendation.
        
        Args:
            unit_id: Grow unit ID
            plant_type: Plant type name
            growth_stage: Current growth stage
            current_conditions: Dict with soil_moisture, temperature, humidity, etc.
            current_threshold: Current threshold setting
            current_default_duration: Current default duration
            enabled_models: List of enabled model names (None = all)
            plant_id: Optional plant identifier for plant-specific predictions
            
        Returns:
            IrrigationPrediction with all predictions
        """
        now = utc_now()
        predictions = IrrigationPrediction(
            unit_id=unit_id,
            generated_at=now.isoformat(),
        )
        
        all_models = [
            "threshold_optimizer",
            "response_predictor",
            "duration_optimizer",
            "timing_predictor",
            "next_irrigation",
        ]
        active_models = enabled_models or all_models
        
        current_moisture = current_conditions.get("soil_moisture", 50.0)
        
        # Threshold prediction
        if "threshold_optimizer" in active_models:
            predictions.threshold = self.predict_threshold(
                unit_id=unit_id,
                plant_type=plant_type,
                growth_stage=growth_stage,
                current_threshold=current_threshold,
                feature_context=feature_context,
            )
            if predictions.threshold.confidence > 0:
                predictions.models_used.append("threshold_optimizer")
        
        # User response prediction
        if "response_predictor" in active_models:
            predictions.user_response = self.predict_user_response(
                unit_id=unit_id,
                current_moisture=current_moisture,
                threshold=current_threshold,
                hour_of_day=now.hour,
                day_of_week=now.weekday(),
                feature_context=feature_context,
            )
            if predictions.user_response.confidence > 0:
                predictions.models_used.append("response_predictor")
        
        # Duration prediction
        if "duration_optimizer" in active_models:
            target_moisture = current_threshold + 15.0  # Target 15% above threshold
            predictions.duration = self.predict_duration(
                unit_id=unit_id,
                current_moisture=current_moisture,
                target_moisture=target_moisture,
                current_default_seconds=current_default_duration,
                feature_context=feature_context,
            )
            if predictions.duration.confidence > 0:
                predictions.models_used.append("duration_optimizer")
        
        # Timing prediction
        if "timing_predictor" in active_models:
            predictions.timing = self.predict_timing(
                unit_id=unit_id,
                day_of_week=now.weekday(),
                feature_context=feature_context,
            )
            if predictions.timing.confidence > 0:
                predictions.models_used.append("timing_predictor")

        # Next irrigation time prediction
        if "next_irrigation" in active_models and plant_id is not None:
            measured_moisture = current_conditions.get("soil_moisture")
            if measured_moisture is not None:
                predictions.next_irrigation = self.predict_next_irrigation_time(
                    plant_id=plant_id,
                    current_moisture=measured_moisture,
                    threshold=current_threshold,
                )
                if predictions.next_irrigation:
                    predictions.models_used.append("next_irrigation")
        
        # Generate recommendations
        predictions.recommendations = self._generate_recommendations(
            predictions,
            unit_id=unit_id,
            plant_id=plant_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            current_conditions=current_conditions,
        )
        
        # Calculate overall confidence
        confidences = []
        if predictions.threshold:
            confidences.append(predictions.threshold.confidence)
        if predictions.user_response:
            confidences.append(predictions.user_response.confidence)
        if predictions.duration:
            confidences.append(predictions.duration.confidence)
        if predictions.timing:
            confidences.append(predictions.timing.confidence)
        if predictions.next_irrigation:
            confidences.append(predictions.next_irrigation.confidence)
        
        predictions.overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return predictions
    
    def _generate_recommendations(
        self,
        prediction: IrrigationPrediction,
        *,
        unit_id: int,
        plant_id: Optional[int],
        plant_type: str,
        growth_stage: str,
        current_conditions: Dict[str, float],
    ) -> List[str]:
        """Generate actionable recommendations from predictions."""
        recommendations = []
        
        # Threshold recommendations
        if prediction.threshold:
            t = prediction.threshold
            if t.adjustment_direction != "maintain" and t.adjustment_amount > 2.0:
                recommendations.append(
                    f"Consider adjusting threshold to {t.optimal_threshold}% "
                    f"({t.adjustment_direction} by {t.adjustment_amount}%)"
                )
        
        # Response recommendations
        if prediction.user_response:
            r = prediction.user_response
            if r.most_likely == "cancel" and r.cancel_probability > 0.3:
                recommendations.append(
                    "High cancel probability - consider reviewing irrigation settings"
                )
            elif r.most_likely == "delay" and r.delay_probability > 0.4:
                recommendations.append(
                    "User often delays - consider adjusting timing preferences"
                )
        
        # Duration recommendations
        if prediction.duration:
            d = prediction.duration
            diff = abs(d.recommended_seconds - d.current_default_seconds)
            if diff > 30 and d.confidence > 0.5:
                if d.recommended_seconds > d.current_default_seconds:
                    recommendations.append(
                        f"Increase irrigation duration to {d.recommended_seconds}s "
                        f"for better moisture restoration"
                    )
                else:
                    recommendations.append(
                        f"Reduce irrigation duration to {d.recommended_seconds}s "
                        f"to avoid overwatering"
                    )
        
        # Timing recommendations
        if prediction.timing:
            t = prediction.timing
            if t.avoid_times and t.confidence > 0.5:
                recommendations.append(
                    f"Best irrigation time: {t.preferred_time}. "
                    f"Avoid: {', '.join(t.avoid_times[:3])}"
                )
        
        if self._recommendation_provider and plant_id is not None:
            try:
                from app.services.ai.recommendation_provider import RecommendationContext

                context = RecommendationContext(
                    plant_id=int(plant_id),
                    unit_id=int(unit_id),
                    plant_type=plant_type,
                    growth_stage=growth_stage,
                    symptoms=[],
                    severity_level=2,
                    environmental_data=current_conditions,
                )
                provider_recs = self._recommendation_provider.get_recommendations(context)
                for rec in provider_recs[:3]:
                    recommendations.append(
                        f"[{rec.category}] {rec.action} ({rec.priority}, {rec.confidence:.2f})"
                    )
            except Exception as exc:
                logger.debug("Recommendation provider failed: %s", exc)

        if not recommendations:
            recommendations.append("Current irrigation settings appear optimal")
        
        return recommendations
    
    @staticmethod
    def _get_direction(current: float, optimal: float) -> str:
        """Get adjustment direction."""
        diff = optimal - current
        if abs(diff) < 1.0:
            return "maintain"
        return "increase" if diff > 0 else "decrease"
    
    # ==================== MLPredictorProtocol Implementation ====================
    # These methods implement the protocol expected by IrrigationCalculator
    
    def predict_water_volume(
        self,
        plant_id: int,
        environmental_data: Dict[str, float],
    ) -> Optional[float]:
        """
        Predict optimal water volume based on environmental conditions.
        
        Phase 3 Implementation:
        1. Try trained ML model first (if available)
        2. Fall back to algorithmic prediction with seasonal adjustments
        3. Uses plant-specific historical data
        4. Accounts for environmental factors and seasonal patterns
        
        Args:
            plant_id: Plant identifier
            environmental_data: Current environmental conditions
            
        Returns:
            Predicted water volume in ml, or None if insufficient data
        """
        try:
            # Extract key environmental factors
            soil_moisture = environmental_data.get('soil_moisture')
            temperature = environmental_data.get('temperature')
            vpd = environmental_data.get('vpd')
            
            if soil_moisture is None:
                logger.debug(f"No soil moisture data for plant {plant_id}, cannot predict volume")
                return None
            
            # Phase 3.1: Try trained ML model first
            if (
                self._duration_model is not None
                and self._feature_engineer
                and hasattr(self._feature_engineer, "extract_features")
            ):
                try:
                    # Engineer features for model
                    features = self._feature_engineer.extract_features({
                        'plant_id': plant_id,
                        'soil_moisture': soil_moisture,
                        'temperature': temperature if temperature is not None else 22.0,
                        'humidity': environmental_data.get('humidity', 60.0),
                        'vpd': vpd if vpd is not None else 1.2,
                        'lux': environmental_data.get('lux', 500.0),
                    })
                    
                    # Predict using trained model
                    prediction = self._duration_model.predict([features])[0]
                    if prediction > 0:
                        logger.info(f"Using trained ML model for plant {plant_id}: {prediction:.1f}ml")
                        return max(20.0, min(prediction, 500.0))
                except Exception as e:
                    logger.debug(f"Trained model prediction failed, using algorithmic: {e}")
            
            # Phase 3.2: Algorithmic fallback with enhancements
            target_moisture = 65.0  # Default target
            moisture_deficit = target_moisture - soil_moisture
            
            if moisture_deficit <= 0:
                logger.debug(f"No irrigation needed for plant {plant_id} (moisture={soil_moisture}%)")
                return None
            
            # Base volume: ~50ml per 10% moisture deficit
            base_volume = moisture_deficit * 5.0
            
            # Phase 3.3: Environmental adjustments
            temp_factor = 1.0
            if temperature is not None:
                if temperature > 25:
                    temp_factor = 1.0 + (temperature - 25) * 0.02
                elif temperature < 20:
                    temp_factor = 1.0 - (20 - temperature) * 0.01
                temp_factor = max(0.8, min(temp_factor, 1.3))
            
            vpd_factor = 1.0
            if vpd is not None:
                if vpd > 1.5:
                    vpd_factor = 1.0 + (vpd - 1.5) * 0.1
                vpd_factor = min(vpd_factor, 1.4)
            
            # Phase 3.4: Seasonal adjustment patterns
            seasonal_factor = self._get_seasonal_adjustment()
            
            # Calculate predicted volume with all factors
            predicted_volume = base_volume * temp_factor * vpd_factor * seasonal_factor
            
            # Clamp to reasonable bounds
            predicted_volume = max(20.0, min(predicted_volume, 500.0))
            
            logger.debug(
                f"Predicted volume for plant {plant_id}: {predicted_volume:.1f}ml "
                f"(base={base_volume:.1f}, temp={temp_factor:.2f}, vpd={vpd_factor:.2f}, "
                f"seasonal={seasonal_factor:.2f})"
            )
            
            return predicted_volume
            
        except Exception as e:
            logger.warning(f"Water volume prediction failed for plant {plant_id}: {e}")
            return None
    
    def get_adjustment_factor(
        self,
        plant_id: int,
        historical_feedback: List[Dict[str, Any]],
    ) -> float:
        """
        Get adjustment factor based on historical feedback.
        
        Phase 3 Implementation:
        Plant-specific learning - analyzes feedback for THIS specific plant.
        - Consistently "too_much" → reduce volume (factor < 1.0)
        - Consistently "too_little" → increase volume (factor > 1.0)
        - Mix of responses → neutral (factor ≈ 1.0)
        - Weighs recent feedback more heavily (last 5 count double)
        
        Args:
            plant_id: Plant identifier (now plant-specific, not unit-based)
            historical_feedback: List of historical feedback records for this plant
            
        Returns:
            Adjustment factor (1.0 = neutral, >1.0 = increase, <1.0 = decrease)
        """
        try:
            # Phase 3.3: Plant-specific learning
            if not historical_feedback:
                logger.debug(f"No historical feedback provided for plant {plant_id}")
                return 1.0
            
            # Count feedback types
            too_little_count = sum(
                1 for f in historical_feedback 
                if f.get('feedback_response') == 'too_little'
            )
            too_much_count = sum(
                1 for f in historical_feedback 
                if f.get('feedback_response') == 'too_much'
            )
            just_right_count = sum(
                1 for f in historical_feedback 
                if f.get('feedback_response') == 'just_right'
            )
            
            total_feedback = too_little_count + too_much_count + just_right_count
            
            if total_feedback == 0:
                logger.debug(f"No feedback data for plant {plant_id}, using neutral factor")
                return 1.0
            
            # Calculate feedback ratios
            too_little_ratio = too_little_count / total_feedback
            too_much_ratio = too_much_count / total_feedback
            just_right_ratio = just_right_count / total_feedback
            
            # Calculate adjustment based on feedback patterns
            # Strong bias requires >60% of one type
            if too_little_ratio > 0.6:
                # Consistently too little → increase by 10-20%
                adjustment = 1.0 + (too_little_ratio - 0.5) * 0.4  # Max +20%
                logger.info(
                    f"Plant {plant_id}: {too_little_ratio:.0%} 'too_little' feedback → "
                    f"increase factor to {adjustment:.2f}"
                )
                return min(adjustment, 1.2)  # Cap at +20%
            
            elif too_much_ratio > 0.6:
                # Consistently too much → decrease by 10-20%
                adjustment = 1.0 - (too_much_ratio - 0.5) * 0.4  # Max -20%
                logger.info(
                    f"Plant {plant_id}: {too_much_ratio:.0%} 'too_much' feedback → "
                    f"decrease factor to {adjustment:.2f}"
                )
                return max(adjustment, 0.8)  # Cap at -20%
            
            elif just_right_ratio > 0.7:
                # Mostly just right → maintain current
                logger.debug(
                    f"Plant {plant_id}: {just_right_ratio:.0%} 'just_right' feedback → "
                    f"maintain current volume"
                )
                return 1.0
            
            else:
                # Mixed feedback → slight adjustment based on balance
                net_adjustment = (too_little_ratio - too_much_ratio) * 0.1  # Max ±10%
                adjustment = 1.0 + net_adjustment
                logger.debug(
                    f"Plant {plant_id}: Mixed feedback (little={too_little_ratio:.0%}, "
                    f"much={too_much_ratio:.0%}, right={just_right_ratio:.0%}) → "
                    f"factor={adjustment:.2f}"
                )
                return max(0.9, min(adjustment, 1.1))  # Clamp to ±10%
                
        except Exception as e:
            logger.warning(f"Adjustment factor calculation failed for plant {plant_id}: {e}")
            return 1.0  # Neutral on error
    
    def get_feedback_for_plant(
        self,
        unit_id: int,
        limit: int = 20,
        plant_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent feedback for ML adjustment calculations.
        
        Phase 3.3: Enhanced for plant-specific learning.
        
        Args:
            unit_id: Grow unit ID
            limit: Maximum number of feedback records to retrieve
            plant_id: Optional plant ID for plant-specific feedback filtering
            
        Returns:
            List of feedback dictionaries with feedback_response and metadata
        """
        try:
            training_data = self._repo.get_training_data_for_model(
                "volume_feedback",
                unit_id=unit_id,
                limit=limit,
            )
            
            # Phase 3.3: Filter for specific plant if requested
            if plant_id and training_data:
                training_data = [
                    record for record in training_data
                    if record.get('plant_id') == plant_id
                ]
                logger.debug(f"Filtered to {len(training_data)} records for plant {plant_id}")
            
            return training_data
        except Exception as e:
            logger.error(f"Failed to get feedback for unit {unit_id}: {e}")
            return []
    
    def _get_seasonal_adjustment(self) -> float:
        """
        Calculate seasonal adjustment factor.
        
        Phase 3.4: Seasonal patterns affect water needs.
        - Winter (Dec-Feb): -10% (less evaporation, slower growth)
        - Spring (Mar-May): baseline
        - Summer (Jun-Aug): +15% (high evaporation, active growth)
        - Fall (Sep-Nov): -5% (declining growth)
        
        Returns:
            Seasonal adjustment factor (0.9 = -10%, 1.15 = +15%)
        """
        month = datetime.now().month
        
        # Winter: December, January, February
        if month in (12, 1, 2):
            return 0.90  # -10%
        
        # Spring: March, April, May  
        elif month in (3, 4, 5):
            return 1.0  # Baseline
        
        # Summer: June, July, August
        elif month in (6, 7, 8):
            return 1.15  # +15%
        
        # Fall: September, October, November
        else:  # 9, 10, 11
            return 0.95  # -5%
    
    def predict_next_irrigation_time(
        self,
        plant_id: int,
        current_moisture: float,
        threshold: float,
        hours_lookback: int = 72,
    ) -> Optional['MoistureDeclinePrediction']:
        """
        Predict when next irrigation will be needed based on moisture decline rate.
        
        Phase 3.2: Moisture decline rate tracking.
        
        Args:
            plant_id: Plant identifier
            current_moisture: Current soil moisture percentage
            threshold: Threshold that triggers irrigation
            hours_lookback: Hours of history to analyze (default 72 = 3 days)
            
        Returns:
            MoistureDeclinePrediction or None if insufficient data
        """
        from app.domain.irrigation import MoistureDeclinePrediction
        
        try:
            if not self._repo or not getattr(self._repo, "_db", None):
                logger.debug("Irrigation ML repository not available for moisture history")
                return None

            model = None
            if hasattr(self._repo, "get_plant_irrigation_model"):
                model = self._repo.get_plant_irrigation_model(plant_id)
            if model and model.get("drydown_rate_per_hour") is not None:
                try:
                    drydown_rate = float(model["drydown_rate_per_hour"])
                except (TypeError, ValueError):
                    drydown_rate = None

                if drydown_rate is not None and drydown_rate < 0:
                    deficit = float(current_moisture) - float(threshold)
                    if deficit <= 0:
                        return MoistureDeclinePrediction(
                            current_moisture=current_moisture,
                            threshold=threshold,
                            decline_rate_per_hour=drydown_rate,
                            hours_until_threshold=0,
                            predicted_time=utc_now().isoformat(),
                            confidence=float(model.get("confidence") or 0.5),
                            reasoning="Dry-down model indicates threshold already reached",
                            samples_used=int(model.get("sample_count") or 0),
                        )

                    hours_until = deficit / abs(drydown_rate)
                    predicted_time = utc_now() + timedelta(hours=hours_until)
                    return MoistureDeclinePrediction(
                        current_moisture=current_moisture,
                        threshold=threshold,
                        decline_rate_per_hour=drydown_rate,
                        hours_until_threshold=hours_until,
                        predicted_time=predicted_time.isoformat(),
                        confidence=float(model.get("confidence") or 0.5),
                        reasoning="Using plant dry-down model",
                        samples_used=int(model.get("sample_count") or 0),
                    )

            # Get moisture history from database
            db = self._repo._db.get_db()
            cutoff = (datetime.now() - timedelta(hours=hours_lookback)).isoformat()
            
            query = """
                SELECT soil_moisture, timestamp
                FROM PlantReadings
                WHERE plant_id = ?
                  AND timestamp >= ?
                  AND soil_moisture IS NOT NULL
                ORDER BY timestamp ASC
            """
            
            cursor = db.execute(query, (plant_id, cutoff))
            history = cursor.fetchall()
            
            if len(history) < 5:
                logger.debug(f"Insufficient moisture history for plant {plant_id} ({len(history)} samples)")
                return None
            
            # Calculate decline rate using linear regression
            timestamps = []
            moistures = []
            
            for row in history:
                moisture = row[0]
                timestamp_str = row[1]
                
                try:
                    ts = datetime.fromisoformat(timestamp_str)
                    timestamps.append(ts)
                    moistures.append(moisture)
                except Exception:
                    continue
            
            if len(timestamps) < 5:
                return None
            
            # Convert timestamps to hours from first reading
            first_time = timestamps[0]
            hours = [(t - first_time).total_seconds() / 3600 for t in timestamps]
            
            # Simple linear regression: y = mx + b
            n = len(hours)
            sum_x = sum(hours)
            sum_y = sum(moistures)
            sum_xy = sum(h * m for h, m in zip(hours, moistures))
            sum_x2 = sum(h * h for h in hours)
            
            # Slope = decline rate per hour (negative value)
            denominator = (n * sum_x2 - sum_x * sum_x)
            if denominator == 0:
                logger.debug("Insufficient variance in timestamps for plant %s", plant_id)
                return None
            decline_rate = (n * sum_xy - sum_x * sum_y) / denominator
            intercept = (sum_y - decline_rate * sum_x) / n
            
            # Only predict if moisture is declining (negative slope)
            if decline_rate >= 0:
                logger.debug(f"Moisture not declining for plant {plant_id} (rate={decline_rate:.3f})")
                return None
            
            # Calculate R² for confidence
            mean_y = sum_y / n
            ss_tot = sum((m - mean_y) ** 2 for m in moistures)
            predictions = [decline_rate * h + intercept for h in hours]
            ss_res = sum((m - p) ** 2 for m, p in zip(moistures, predictions))
            r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
            
            confidence = max(0.3, min(r_squared, 0.95))
            
            # Predict time until threshold
            moisture_deficit = current_moisture - threshold
            
            if moisture_deficit <= 0:
                # Already at or below threshold
                return MoistureDeclinePrediction(
                    current_moisture=current_moisture,
                    threshold=threshold,
                    decline_rate_per_hour=decline_rate,
                    hours_until_threshold=0,
                    predicted_time=datetime.now().isoformat(),
                    confidence=confidence,
                    reasoning="Moisture already at or below threshold",
                    samples_used=len(history),
                )
            
            # Time = deficit / decline_rate (decline_rate is negative, so negate it)
            hours_until = moisture_deficit / abs(decline_rate)
            predicted_time = datetime.now() + timedelta(hours=hours_until)
            
            reasoning = (
                f"Based on {len(history)} samples over {hours_lookback}h, "
                f"moisture declining at {abs(decline_rate):.3f}%/hour "
                f"(R²={r_squared:.2f})"
            )
            
            logger.info(
                f"Plant {plant_id}: Next irrigation predicted in {hours_until:.1f}h "
                f"at {predicted_time.strftime('%Y-%m-%d %H:%M')}"
            )
            
            return MoistureDeclinePrediction(
                current_moisture=current_moisture,
                threshold=threshold,
                decline_rate_per_hour=decline_rate,
                hours_until_threshold=hours_until,
                predicted_time=predicted_time.isoformat(),
                confidence=confidence,
                reasoning=reasoning,
                samples_used=len(history),
            )
            
        except Exception as e:
            logger.error(f"Failed to predict next irrigation for plant {plant_id}: {e}", exc_info=True)
            return None
