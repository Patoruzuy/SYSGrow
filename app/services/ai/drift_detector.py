"""
Model Drift Detection Service
==============================
Monitors ML model performance and detects degradation over time.

Provides:
- Performance tracking
- Drift detection
- Retraining recommendations
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.utils.time import iso_now

# ML libraries lazy loaded in methods for faster startup
# import numpy as np

if TYPE_CHECKING:
    from app.services.ai.model_registry import ModelRegistry
    from infrastructure.database.repositories.ai import AITrainingDataRepository

logger = logging.getLogger(__name__)


@dataclass
class DriftMetrics:
    """Model drift detection metrics."""

    model_name: str
    timestamp: datetime
    prediction_accuracy: float
    mean_confidence: float
    prediction_count: int
    error_rate: float
    drift_score: float
    recommendation: str  # 'ok', 'monitor', 'retrain'
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "timestamp": self.timestamp.isoformat(),
            "prediction_accuracy": round(self.prediction_accuracy, 4),
            "mean_confidence": round(self.mean_confidence, 4),
            "prediction_count": self.prediction_count,
            "error_rate": round(self.error_rate, 4),
            "drift_score": round(self.drift_score, 4),
            "recommendation": self.recommendation,
            "details": self.details,
        }


class ModelDriftDetectorService:
    """
    Service for detecting model performance drift.

    Monitors model predictions and performance over time to detect
    degradation that may require retraining.

    Supports database persistence for metrics across restarts.
    """

    def __init__(
        self,
        model_registry: ModelRegistry,
        training_data_repo: AITrainingDataRepository,
        ai_health_repo: Any | None = None,
    ):
        """
        Initialize drift detector service.

        Args:
            model_registry: Model registry for accessing models
            training_data_repo: Repository for training data access
            ai_health_repo: Optional AI health repository for drift metric persistence
        """
        self.model_registry = model_registry
        self.training_data_repo = training_data_repo
        self.ai_health_repo = ai_health_repo
        self.logger = logging.getLogger(__name__)

        # Drift thresholds
        self.accuracy_threshold = 0.10  # 10% drop triggers warning
        self.error_rate_threshold = 0.20  # 20% error rate triggers warning
        self.confidence_threshold = 0.60  # Below 60% confidence triggers warning

        # Metrics history (in-memory cache)
        self.metrics_history: dict[str, deque] = {}
        self.max_history_size = 1000

    def track_prediction(
        self, model_name: str, prediction: Any, actual: Any | None = None, confidence: float | None = None
    ) -> None:
        """
        Track a model prediction for drift analysis.

        Args:
            model_name: Name of the model
            prediction: Model prediction
            actual: Actual value (if available)
            confidence: Prediction confidence score
        """
        try:
            if model_name not in self.metrics_history:
                self.metrics_history[model_name] = deque(maxlen=self.max_history_size)

            # Calculate error if actual value is available
            error = None
            if actual is not None:
                if isinstance(prediction, (int, float)) and isinstance(actual, (int, float)):
                    error = abs(prediction - actual)
                else:
                    error = 0 if prediction == actual else 1

            record = {
                "timestamp": datetime.now(),
                "prediction": prediction,
                "actual": actual,
                "confidence": confidence,
                "error": error,
            }

            self.metrics_history[model_name].append(record)

            # Persist to database
            if self.ai_health_repo:
                self.ai_health_repo.save_drift_metric(
                    model_name=model_name,
                    prediction=prediction,
                    actual=actual,
                    confidence=confidence,
                    error=error,
                )

        except Exception as e:
            self.logger.error("Error tracking prediction: %s", e)

    def check_drift(self, model_name: str, window_size: int = 100) -> DriftMetrics:
        """
        Check for model drift.

        Args:
            model_name: Name of the model to check
            window_size: Number of recent predictions to analyze

        Returns:
            DriftMetrics with drift analysis
        """
        try:
            if model_name not in self.metrics_history:
                return DriftMetrics(
                    model_name=model_name,
                    timestamp=datetime.now(),
                    prediction_accuracy=1.0,
                    mean_confidence=1.0,
                    prediction_count=0,
                    error_rate=0.0,
                    drift_score=0.0,
                    recommendation="ok",
                    details={"message": "No prediction history available"},
                )

            # Get recent predictions
            history = list(self.metrics_history[model_name])
            if len(history) > window_size:
                history = history[-window_size:]

            if not history:
                return DriftMetrics(
                    model_name=model_name,
                    timestamp=datetime.now(),
                    prediction_accuracy=1.0,
                    mean_confidence=1.0,
                    prediction_count=0,
                    error_rate=0.0,
                    drift_score=0.0,
                    recommendation="ok",
                    details={"message": "No predictions in window"},
                )

            # Lazy load numpy for statistics
            import numpy as np

            # Calculate metrics
            predictions_with_actual = [r for r in history if r["actual"] is not None]
            predictions_with_confidence = [r for r in history if r["confidence"] is not None]

            # Accuracy
            accuracy = 1.0
            if predictions_with_actual:
                correct = sum(1 for r in predictions_with_actual if r["error"] is not None and r["error"] < 0.1)
                accuracy = correct / len(predictions_with_actual)

            # Mean confidence
            mean_confidence = 1.0
            if predictions_with_confidence:
                mean_confidence = np.mean([r["confidence"] for r in predictions_with_confidence])

            # Error rate
            error_rate = 0.0
            if predictions_with_actual:
                errors = [r["error"] for r in predictions_with_actual if r["error"] is not None]
                if errors:
                    error_rate = np.mean([1 if e > 0.1 else 0 for e in errors])

            # Calculate drift score (weighted combination)
            accuracy_score = 1.0 - accuracy
            confidence_score = 1.0 - mean_confidence
            drift_score = accuracy_score * 0.5 + confidence_score * 0.3 + error_rate * 0.2

            # Determine recommendation
            recommendation = "ok"
            details = {}

            if drift_score > 0.3 or error_rate > self.error_rate_threshold:
                recommendation = "retrain"
                details["reason"] = "High drift score or error rate detected"
            elif drift_score > 0.15 or mean_confidence < self.confidence_threshold:
                recommendation = "monitor"
                details["reason"] = "Moderate drift or low confidence detected"

            # Get baseline metrics from model metadata
            metadata = self.model_registry.get_metadata(model_name)
            if metadata:
                baseline_accuracy = metadata.metrics.get("test_score", 1.0)
                if accuracy < baseline_accuracy - self.accuracy_threshold:
                    recommendation = "retrain"
                    details["accuracy_drop"] = baseline_accuracy - accuracy

            return DriftMetrics(
                model_name=model_name,
                timestamp=datetime.now(),
                prediction_accuracy=accuracy,
                mean_confidence=mean_confidence,
                prediction_count=len(history),
                error_rate=error_rate,
                drift_score=drift_score,
                recommendation=recommendation,
                details=details,
            )

        except Exception as e:
            self.logger.error("Error checking drift for %s: %s", model_name, e, exc_info=True)
            return DriftMetrics(
                model_name=model_name,
                timestamp=datetime.now(),
                prediction_accuracy=0.0,
                mean_confidence=0.0,
                prediction_count=0,
                error_rate=1.0,
                drift_score=1.0,
                recommendation="monitor",
                details={"error": str(e)},
            )

    def check_all_models(self) -> list[DriftMetrics]:
        """
        Check drift for all models.

        Returns:
            List of DriftMetrics for all tracked models
        """
        results = []

        # Get all models from registry
        models = self.model_registry.list_models()

        for model_name in models:
            drift_metrics = self.check_drift(model_name)
            results.append(drift_metrics)

        return results

    def get_retraining_recommendations(self) -> list[str]:
        """
        Get list of models that need retraining.

        Returns:
            List of model names that should be retrained
        """
        drift_results = self.check_all_models()
        return [metrics.model_name for metrics in drift_results if metrics.recommendation == "retrain"]

    def get_drift_summary(self) -> dict[str, Any]:
        """
        Get summary of drift status across all models.

        Returns:
            Summary dictionary with drift statistics
        """
        drift_results = self.check_all_models()

        if not drift_results:
            return {
                "total_models": 0,
                "models_ok": 0,
                "models_monitoring": 0,
                "models_need_retraining": 0,
                "models": [],
            }

        ok_count = sum(1 for m in drift_results if m.recommendation == "ok")
        monitor_count = sum(1 for m in drift_results if m.recommendation == "monitor")
        retrain_count = sum(1 for m in drift_results if m.recommendation == "retrain")

        return {
            "total_models": len(drift_results),
            "models_ok": ok_count,
            "models_monitoring": monitor_count,
            "models_need_retraining": retrain_count,
            "models": [m.to_dict() for m in drift_results],
            "timestamp": iso_now(),
        }

    def clear_history(self, model_name: str | None = None) -> None:
        """
        Clear prediction history.

        Args:
            model_name: Model name to clear (clears all if None)
        """
        if model_name:
            if model_name in self.metrics_history:
                self.metrics_history[model_name].clear()
        else:
            self.metrics_history.clear()
