"""
AI / ML layer smoke tests.

Verifies that every public AI service class can be:
1. Imported without error
2. Instantiated (with mocks for required deps)
3. Basic attributes and methods exist

These are *smoke tests* — they prove the import graph is intact and that
constructors don't crash, but don't exercise real ML inference.
"""

from __future__ import annotations

import importlib
from unittest.mock import MagicMock

import pytest

# ========================== Module import checks ============================


AI_MODULES = [
    "app.services.ai.ab_testing",
    "app.services.ai.automated_retraining",
    "app.services.ai.bayesian_threshold",
    "app.services.ai.climate_optimizer",
    "app.services.ai.continuous_monitor",
    "app.services.ai.disease_predictor",
    "app.services.ai.drift_detector",
    "app.services.ai.environmental_health_scorer",
    "app.services.ai.feature_engineering",
    "app.services.ai.irrigation_predictor",
    "app.services.ai.llm_advisor",
    "app.services.ai.llm_backends",
    "app.services.ai.ml_readiness_monitor",
    "app.services.ai.ml_trainer",
    "app.services.ai.model_registry",
    "app.services.ai.personalized_learning",
    "app.services.ai.plant_growth_predictor",
    "app.services.ai.plant_health_monitor",
    "app.services.ai.plant_health_scorer",
    "app.services.ai.recommendation_provider",
    "app.services.ai.training_data_collector",
]


@pytest.mark.parametrize("module_name", AI_MODULES)
def test_module_imports(module_name: str):
    """Every AI module should import without raising."""
    mod = importlib.import_module(module_name)
    assert mod is not None


def test_barrel_import():
    """The barrel __init__.py should re-export all public symbols."""
    import app.services.ai as ai

    # Spot-check a representative symbol from each category
    assert hasattr(ai, "ModelRegistry")
    assert hasattr(ai, "IrrigationPredictor")
    assert hasattr(ai, "ClimateOptimizer")
    assert hasattr(ai, "DiseasePredictor")
    assert hasattr(ai, "PlantHealthScorer")
    assert hasattr(ai, "BayesianThresholdAdjuster")
    assert hasattr(ai, "FeatureEngineer")
    assert hasattr(ai, "PredictionConfidence")
    assert hasattr(ai, "LLMAdvisorService")
    assert hasattr(ai, "ABTestingService")


# ========================== Zero-arg instantiation ==========================


class TestZeroArgServices:
    """Services whose constructors accept all-optional parameters."""

    def test_climate_optimizer(self):
        from app.services.ai.climate_optimizer import ClimateOptimizer

        svc = ClimateOptimizer()
        assert svc.threshold_service is None
        assert svc._model is None

    def test_plant_health_scorer(self):
        from app.services.ai.plant_health_scorer import PlantHealthScorer

        svc = PlantHealthScorer()
        assert svc is not None

    def test_bayesian_threshold_adjuster(self):
        from app.services.ai.bayesian_threshold import BayesianThresholdAdjuster

        svc = BayesianThresholdAdjuster()
        assert svc is not None

    def test_environmental_health_scorer(self):
        from app.services.ai.environmental_health_scorer import EnvironmentalLeafHealthScorer

        svc = EnvironmentalLeafHealthScorer()
        assert svc.threshold_service is None

    def test_plant_growth_predictor(self):
        from app.services.ai.plant_growth_predictor import PlantGrowthPredictor

        svc = PlantGrowthPredictor()
        assert svc.enable_validation is True

    def test_model_registry(self, tmp_path):
        from app.services.ai.model_registry import ModelRegistry

        reg = ModelRegistry(base_path=tmp_path / "models")
        assert reg.base_path.exists()

    def test_rule_based_recommendation_provider(self):
        from app.services.ai.recommendation_provider import RuleBasedRecommendationProvider

        svc = RuleBasedRecommendationProvider()
        assert svc.is_available is True
        assert svc.provider_name == "rule_based"

    def test_llm_advisor_no_backend(self):
        from app.services.ai.llm_advisor import LLMAdvisorService

        svc = LLMAdvisorService()
        assert svc.is_available is False
        assert svc.provider_name == "none"

    def test_feature_engineer(self):
        from app.services.ai.feature_engineering import FeatureEngineer

        eng = FeatureEngineer()
        assert eng is not None

    def test_environmental_feature_extractor(self):
        from app.services.ai.feature_engineering import EnvironmentalFeatureExtractor

        ext = EnvironmentalFeatureExtractor()
        assert ext is not None

    def test_plant_health_feature_extractor(self):
        from app.services.ai.feature_engineering import PlantHealthFeatureExtractor

        ext = PlantHealthFeatureExtractor()
        assert ext is not None


# ========================== Mock-arg instantiation ==========================


class TestMockArgServices:
    """Services requiring at least one mandatory dependency (mocked)."""

    def test_irrigation_predictor(self):
        from app.services.ai.irrigation_predictor import IrrigationPredictor

        svc = IrrigationPredictor(irrigation_ml_repo=MagicMock())
        assert svc is not None

    def test_disease_predictor(self):
        from app.services.ai.disease_predictor import DiseasePredictor

        svc = DiseasePredictor(repo_health=MagicMock())
        assert svc.model_loaded is False

    def test_ml_trainer(self):
        from app.services.ai.ml_trainer import MLTrainerService

        svc = MLTrainerService(
            training_data_repo=MagicMock(),
            model_registry=MagicMock(),
        )
        assert svc is not None

    def test_drift_detector(self):
        from app.services.ai.drift_detector import ModelDriftDetectorService

        svc = ModelDriftDetectorService(
            model_registry=MagicMock(),
            training_data_repo=MagicMock(),
        )
        assert svc is not None

    def test_ab_testing_service(self):
        from app.services.ai.ab_testing import ABTestingService

        svc = ABTestingService(model_registry=MagicMock())
        assert svc is not None

    def test_training_data_collector(self, tmp_path):
        from app.services.ai.training_data_collector import TrainingDataCollector

        svc = TrainingDataCollector(
            training_data_repo=MagicMock(),
            feature_engineer=MagicMock(),
            storage_path=tmp_path / "training",
        )
        assert svc is not None


# ========================== Domain dataclass checks =========================


class TestDomainDataclasses:
    """Key domain value objects used across the AI layer."""

    def test_prediction_confidence_enum(self):
        from app.domain.irrigation import PredictionConfidence

        assert PredictionConfidence.HIGH is not None
        assert PredictionConfidence.LOW is not None

    def test_climate_conditions_dataclass(self):
        from app.services.ai.climate_optimizer import ClimateConditions

        cc = ClimateConditions(temperature=22.0, humidity=55.0, soil_moisture=70.0, lux=5000.0)
        assert cc.temperature == 22.0
        assert cc.soil_moisture == 70.0

    def test_disease_risk_dataclass(self):
        from app.services.ai.disease_predictor import DiseaseRisk, DiseaseType, RiskLevel

        dr = DiseaseRisk(
            disease_type=DiseaseType.FUNGAL,
            risk_level=RiskLevel.LOW,
            confidence=0.8,
            risk_score=10.0,
            contributing_factors=[],
            recommendations=[],
        )
        assert dr.risk_score == 10.0

    def test_growth_stage_is_plant_stage_alias(self):
        from app.enums import PlantStage
        from app.services.ai.plant_growth_predictor import GrowthStage

        # GrowthStage is an alias for PlantStage enum
        assert GrowthStage is PlantStage
        assert GrowthStage.VEGETATIVE is not None

    def test_recommendation_context(self):
        from app.services.ai.recommendation_provider import RecommendationContext

        ctx = RecommendationContext(
            plant_id=1,
            unit_id=1,
            plant_type="Tomato",
            growth_stage="vegetative",
        )
        assert ctx.plant_type == "Tomato"
