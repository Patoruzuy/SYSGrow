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
"""

from app.services.ai.ab_testing import ABTest, ABTestingService, TestStatus
from app.services.ai.automated_retraining import (
    AutomatedRetrainingService,
    RetrainingEvent,
    RetrainingJob,
    RetrainingStatus,
    RetrainingTrigger,
)
from app.services.ai.bayesian_threshold import (
    AdjustmentResult,
    BayesianThresholdAdjuster,
    ThresholdBelief,
)
from app.services.ai.climate_optimizer import (
    ClimateAnalysis,
    ClimateConditions,
    ClimateOptimizer,
    ClimateRecommendation,
    LightingRecommendation,
)
from app.services.ai.continuous_monitor import ContinuousMonitoringService
from app.services.ai.disease_predictor import DiseasePredictor, DiseaseRisk, DiseaseType, RiskLevel
from app.services.ai.drift_detector import DriftMetrics, ModelDriftDetectorService
from app.services.ai.environmental_health_scorer import (
    EnvironmentalLeafHealthScorer,
    LeafHealthScore,
)
from app.services.ai.feature_engineering import (
    PLANT_HEALTH_FEATURES_V1,
    EnvironmentalFeatureExtractor,
    FeatureEngineer,
    FeatureSet,
    PlantHealthFeatureExtractor,
)
from app.services.ai.irrigation_predictor import (
    DurationPrediction,
    IrrigationPrediction,
    IrrigationPredictor,
    PredictionConfidence,
    ThresholdPrediction,
    TimingPrediction,
    UserResponsePrediction,
)
from app.services.ai.llm_advisor import (
    DecisionQuery,
    DecisionResponse,
    LLMAdvisorService,
)
from app.services.ai.llm_backends import (
    AnthropicBackend,
    LLMBackend,
    LLMResponse,
    LocalTransformersBackend,
    OpenAIBackend,
    create_backend,
)
from app.services.ai.ml_readiness_monitor import (
    IrrigationMLReadiness,
    MLReadinessMonitorService,
    ModelReadinessStatus,
)
from app.services.ai.ml_trainer import MLTrainerService, TrainingMetrics
from app.services.ai.model_registry import ModelMetadata, ModelRegistry, ModelStatus
from app.services.ai.personalized_learning import PersonalizedLearningService
from app.services.ai.plant_growth_predictor import GrowthConditions, GrowthStage, PlantGrowthPredictor, StageTransition
from app.services.ai.plant_health_monitor import (
    EnvironmentalCorrelation,
    HealthStatus,
    PlantHealthMonitor,
    PlantHealthObservation,
)
from app.services.ai.plant_health_scorer import (
    PlantHealthScore,
    PlantHealthScorer,
)
from app.services.ai.recommendation_provider import (
    LLMRecommendationProvider,
    Recommendation,
    RecommendationContext,
    RecommendationProvider,
    RuleBasedRecommendationProvider,
)

__all__ = [
    # Model Management
    "ModelRegistry",
    "ModelMetadata",
    "ModelStatus",
    # Disease Prediction
    "DiseasePredictor",
    "DiseaseRisk",
    "DiseaseType",
    "RiskLevel",
    # Health Monitoring
    "PlantHealthMonitor",
    "PlantHealthObservation",
    "HealthStatus",
    "EnvironmentalCorrelation",
    # Climate Optimization
    "ClimateOptimizer",
    "ClimateConditions",
    "ClimateAnalysis",
    "ClimateRecommendation",
    "LightingRecommendation",
    # ML Training
    "MLTrainerService",
    "TrainingMetrics",
    # Drift Detection
    "ModelDriftDetectorService",
    "DriftMetrics",
    # A/B Testing
    "ABTestingService",
    "ABTest",
    "TestStatus",
    # Feature Engineering
    "FeatureEngineer",
    "FeatureSet",
    "EnvironmentalFeatureExtractor",
    "PlantHealthFeatureExtractor",
    "PLANT_HEALTH_FEATURES_V1",
    # Growth Prediction
    "PlantGrowthPredictor",
    "GrowthStage",
    "GrowthConditions",
    "StageTransition",
    # Automated Retraining
    "AutomatedRetrainingService",
    "RetrainingJob",
    "RetrainingEvent",
    "RetrainingTrigger",
    "RetrainingStatus",
    # Continuous Monitoring
    "ContinuousMonitoringService",
    # Personalized Learning
    "PersonalizedLearningService",
    # ML Readiness Monitoring
    "MLReadinessMonitorService",
    "ModelReadinessStatus",
    "IrrigationMLReadiness",
    # Irrigation Prediction
    "IrrigationPredictor",
    "IrrigationPrediction",
    "ThresholdPrediction",
    "DurationPrediction",
    "TimingPrediction",
    "UserResponsePrediction",
    "PredictionConfidence",
    # Bayesian Threshold Learning
    "BayesianThresholdAdjuster",
    "ThresholdBelief",
    "AdjustmentResult",
    # Environmental Health Scoring
    "EnvironmentalLeafHealthScorer",
    "LeafHealthScore",
    # Plant Health Scoring
    "PlantHealthScorer",
    "PlantHealthScore",
    # Recommendation Providers
    "RecommendationProvider",
    "RuleBasedRecommendationProvider",
    "LLMRecommendationProvider",
    "RecommendationContext",
    "Recommendation",
    # LLM Backends
    "LLMBackend",
    "LLMResponse",
    "OpenAIBackend",
    "AnthropicBackend",
    "LocalTransformersBackend",
    "create_backend",
    # LLM Advisor (Decision Maker)
    "LLMAdvisorService",
    "DecisionQuery",
    "DecisionResponse",
]
