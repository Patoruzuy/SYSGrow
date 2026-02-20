"""
AI Services
===========
Machine learning and AI services for plant growth optimization.

Services:
- ModelRegistry: ML model versioning and lifecycle management
- DiseasePredictor: Disease risk prediction
- PlantHealthMonitor: Plant health tracking
- ClimateOptimizer: Climate control optimization
- MLTrainer: Model training and retraining orchestration
- ModelDriftDetector: Model performance monitoring
- ABTesting: A/B testing for model deployment

All public symbols are importable via ``from app.services.ai import X``.
Imports are **lazy** — each submodule is loaded only when one of its
symbols is first accessed, keeping cold-start fast on constrained
devices (Raspberry Pi).
"""

from __future__ import annotations

import importlib
from typing import Any

# ── Symbol → submodule mapping ──────────────────────────────────────
# Keys are public symbol names; values are the dotted submodule path.
_LAZY_IMPORTS: dict[str, str] = {
    # ab_testing
    "ABTest": "app.services.ai.ab_testing",
    "ABTestingService": "app.services.ai.ab_testing",
    "TestStatus": "app.services.ai.ab_testing",
    # automated_retraining
    "AutomatedRetrainingService": "app.services.ai.automated_retraining",
    "RetrainingEvent": "app.services.ai.automated_retraining",
    "RetrainingJob": "app.services.ai.automated_retraining",
    "RetrainingStatus": "app.services.ai.automated_retraining",
    "RetrainingTrigger": "app.services.ai.automated_retraining",
    # bayesian_threshold
    "AdjustmentResult": "app.services.ai.bayesian_threshold",
    "BayesianThresholdAdjuster": "app.services.ai.bayesian_threshold",
    "ThresholdBelief": "app.services.ai.bayesian_threshold",
    # climate_optimizer
    "ClimateAnalysis": "app.services.ai.climate_optimizer",
    "ClimateConditions": "app.services.ai.climate_optimizer",
    "ClimateOptimizer": "app.services.ai.climate_optimizer",
    "ClimateRecommendation": "app.services.ai.climate_optimizer",
    "LightingRecommendation": "app.services.ai.climate_optimizer",
    # continuous_monitor
    "ContinuousMonitoringService": "app.services.ai.continuous_monitor",
    # disease_predictor
    "DiseasePredictor": "app.services.ai.disease_predictor",
    "DiseaseRisk": "app.services.ai.disease_predictor",
    "DiseaseType": "app.services.ai.disease_predictor",
    "RiskLevel": "app.services.ai.disease_predictor",
    # drift_detector
    "DriftMetrics": "app.services.ai.drift_detector",
    "ModelDriftDetectorService": "app.services.ai.drift_detector",
    # environmental_health_scorer
    "EnvironmentalLeafHealthScorer": "app.services.ai.environmental_health_scorer",
    "LeafHealthScore": "app.services.ai.environmental_health_scorer",
    # feature_engineering
    "EnvironmentalFeatureExtractor": "app.services.ai.feature_engineering",
    "FeatureEngineer": "app.services.ai.feature_engineering",
    "FeatureSet": "app.services.ai.feature_engineering",
    "PLANT_HEALTH_FEATURES_V1": "app.services.ai.feature_engineering",
    "PlantHealthFeatureExtractor": "app.services.ai.feature_engineering",
    # irrigation_predictor
    "DurationPrediction": "app.services.ai.irrigation_predictor",
    "IrrigationPrediction": "app.services.ai.irrigation_predictor",
    "IrrigationPredictor": "app.services.ai.irrigation_predictor",
    "ThresholdPrediction": "app.services.ai.irrigation_predictor",
    "TimingPrediction": "app.services.ai.irrigation_predictor",
    "UserResponsePrediction": "app.services.ai.irrigation_predictor",
    # domain (re-exported for convenience)
    "PredictionConfidence": "app.domain.irrigation",
    # llm_advisor
    "DecisionQuery": "app.services.ai.llm_advisor",
    "DecisionResponse": "app.services.ai.llm_advisor",
    "LLMAdvisorService": "app.services.ai.llm_advisor",
    # llm_backends
    "AnthropicBackend": "app.services.ai.llm_backends",
    "LLMBackend": "app.services.ai.llm_backends",
    "LLMResponse": "app.services.ai.llm_backends",
    "LocalTransformersBackend": "app.services.ai.llm_backends",
    "OpenAIBackend": "app.services.ai.llm_backends",
    "create_backend": "app.services.ai.llm_backends",
    # ml_readiness_monitor
    "IrrigationMLReadiness": "app.services.ai.ml_readiness_monitor",
    "MLReadinessMonitorService": "app.services.ai.ml_readiness_monitor",
    "ModelReadinessStatus": "app.services.ai.ml_readiness_monitor",
    # ml_trainer
    "MLTrainerService": "app.services.ai.ml_trainer",
    "TrainingMetrics": "app.services.ai.ml_trainer",
    # model_registry
    "ModelMetadata": "app.services.ai.model_registry",
    "ModelRegistry": "app.services.ai.model_registry",
    "ModelStatus": "app.services.ai.model_registry",
    # personalized_learning
    "PersonalizedLearningService": "app.services.ai.personalized_learning",
    # plant_growth_predictor
    "GrowthConditions": "app.services.ai.plant_growth_predictor",
    "GrowthStage": "app.services.ai.plant_growth_predictor",
    "PlantGrowthPredictor": "app.services.ai.plant_growth_predictor",
    "StageTransition": "app.services.ai.plant_growth_predictor",
    # plant_health_monitor
    "EnvironmentalCorrelation": "app.services.ai.plant_health_monitor",
    "HealthStatus": "app.services.ai.plant_health_monitor",
    "PlantHealthMonitor": "app.services.ai.plant_health_monitor",
    "PlantHealthObservation": "app.services.ai.plant_health_monitor",
    # plant_health_scorer
    "PlantHealthScore": "app.services.ai.plant_health_scorer",
    "PlantHealthScorer": "app.services.ai.plant_health_scorer",
    # recommendation_provider
    "LLMRecommendationProvider": "app.services.ai.recommendation_provider",
    "Recommendation": "app.services.ai.recommendation_provider",
    "RecommendationContext": "app.services.ai.recommendation_provider",
    "RecommendationProvider": "app.services.ai.recommendation_provider",
    "RuleBasedRecommendationProvider": "app.services.ai.recommendation_provider",
}

__all__ = list(_LAZY_IMPORTS.keys())


def __getattr__(name: str) -> Any:
    """Lazy-load symbols on first access.

    This avoids importing all 14 AI submodules at ``import app.services.ai``
    time, which is significant on resource-constrained devices.
    """
    module_path = _LAZY_IMPORTS.get(name)
    if module_path is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(module_path)
    value = getattr(module, name)
    # Cache on the module so subsequent accesses skip __getattr__
    globals()[name] = value
    return value
