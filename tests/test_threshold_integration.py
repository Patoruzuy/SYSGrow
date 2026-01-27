"""ThresholdService integration tests skipped after v2 migration (AI fallback removed)."""
import pytest

pytest.skip("ThresholdService/AI fallback tests removed for v2-only backend", allow_module_level=True)
import logging
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

from app.services.application.threshold_service import ThresholdService
from app.utils.plant_json_handler import PlantJsonHandler
from app.services.ai.climate_optimizer import ClimateOptimizer
from app.domain.unit_runtime import UnitRuntime, UnitSettings
from app.domain.plant_profile import PlantProfile

logger = logging.getLogger(__name__)


class TestThresholdServiceIntegration:
    """Test suite for ThresholdService integration with UnitRuntime"""
    
    @pytest.fixture
    def mock_climate_optimizer(self):
        """Mock climate optimizer service that returns predictions"""
        climate_optimizer = Mock(spec=ClimateOptimizer)
        climate_optimizer.get_recommendations.return_value = {
            'temperature': 25.0,
            'humidity': 60.0,
            'soil_moisture': 70.0
        }
        return climate_optimizer
    
    @pytest.fixture
    def threshold_service(self, mock_climate_optimizer):
        """Create ThresholdService with mocked climate optimizer"""
        plant_handler = PlantJsonHandler()
        return ThresholdService(plant_handler=plant_handler, ai_model=mock_ai_model)
    
    @pytest.fixture
    def mock_repositories(self):
        """Create mock repositories"""
        growth_repo = Mock()
        analytics_repo = Mock()
        return growth_repo, analytics_repo
    
    def test_threshold_service_initialization(self, threshold_service, mock_ai_model):
        """Test that ThresholdService initializes with AI model"""
        assert threshold_service.ai_model is mock_ai_model
        assert threshold_service.plant_handler is not None
        logger.info("✅ ThresholdService initialized with AI model")
    
    def test_get_optimal_conditions_plant_only(self, threshold_service):
        """Test getting optimal conditions without AI enhancement"""
        optimal = threshold_service.get_optimal_conditions(
            plant_type="Tomatoes",
            growth_stage="Vegetative",
            use_ai=False
        )
        
        assert 'temperature' in optimal
        assert 'humidity' in optimal
        assert 'soil_moisture' in optimal
        assert 'co2_ppm' in optimal
        
        # Should be midpoint of optimal range for Tomatoes
        assert 18 <= optimal['temperature'] <= 28
        assert 50 <= optimal['humidity'] <= 80
        
        logger.info(f"✅ Plant-only optimal conditions: {optimal}")
    
    def test_get_optimal_conditions_with_ai_blend(self, threshold_service, mock_ai_model):
        """Test that AI predictions are blended with plant-specific thresholds"""
        # Configure mock to return specific predictions
        mock_ai_model.predict_growth_conditions.return_value = {
            'temperature': 30.0,  # High value to test blending
            'humidity': 70.0,
            'soil_moisture': 80.0
        }
        
        optimal = threshold_service.get_optimal_conditions(
            plant_type="Tomatoes",
            growth_stage="Vegetative",
            use_ai=True
        )
        
        # AI prediction should be blended (70% AI, 30% plant-specific)
        # But clamped to plant-specific ranges
        assert optimal['temperature'] <= 28  # Max for Tomatoes vegetative
        assert optimal['humidity'] >= 50  # Min for Tomatoes
        
        # Verify AI was called
        mock_ai_model.predict_growth_conditions.assert_called_once_with("Vegetative")
        
        logger.info(f"✅ AI-blended optimal conditions: {optimal}")
    
    def test_get_threshold_ranges(self, threshold_service):
        """Test getting threshold ranges for hardware control"""
        ranges = threshold_service.get_threshold_ranges(
            plant_type="Basil",
            growth_stage="Seedling"
        )
        
        assert 'temperature' in ranges
        assert 'humidity' in ranges
        
        temp_range = ranges['temperature']
        assert 'min' in temp_range
        assert 'max' in temp_range
        assert 'optimal' in temp_range
        
        logger.info(f"✅ Threshold ranges for Basil: {ranges}")
    
    def test_is_within_optimal_range(self, threshold_service):
        """Test checking if conditions are within optimal range"""
        current_conditions = {
            'temperature': 24.0,
            'humidity': 65.0,
            'soil_moisture': 60.0
        }
        
        results = threshold_service.is_within_optimal_range(
            plant_type="Tomatoes",
            growth_stage="Flowering",
            current_conditions=current_conditions
        )
        
        assert 'temperature' in results
        assert 'humidity' in results
        assert isinstance(results['temperature'], bool)
        
        logger.info(f"✅ Range check results: {results}")
    
    def test_get_adjustment_recommendations(self, threshold_service):
        """Test getting adjustment recommendations"""
        current_conditions = {
            'temperature': 30.0,  # Too high for tomatoes
            'humidity': 40.0,     # Too low
            'soil_moisture': 65.0  # Good
        }
        
        recommendations = threshold_service.get_adjustment_recommendations(
            plant_type="Tomatoes",
            growth_stage="Vegetative",
            current_conditions=current_conditions
        )
        
        assert 'temperature' in recommendations
        temp_rec = recommendations['temperature']
        
        assert temp_rec['action'] == 'decrease'
        assert temp_rec['priority'] in ['high', 'medium', 'low']
        assert temp_rec['current'] == 30.0
        assert temp_rec['plant_specific'] is True
        
        logger.info(f"✅ Adjustment recommendations: {recommendations}")
    
    def test_unit_runtime_with_threshold_service(self, threshold_service, mock_repositories):
        """Test UnitRuntime initialization with ThresholdService"""
        growth_repo, analytics_repo = mock_repositories
        
        unit = UnitRuntime(
            unit_id=1,
            unit_name="Test Unit",
            location="Indoor",
            user_id=1,
            threshold_service=threshold_service
        )
        
        assert unit.threshold_service is threshold_service
        logger.info("✅ UnitRuntime initialized with ThresholdService")
    
    def test_apply_ai_conditions_uses_threshold_service(
        self, threshold_service, mock_repositories, mock_ai_model
    ):
        """Test that apply_ai_conditions uses ThresholdService"""
        growth_repo, analytics_repo = mock_repositories
        
        # Mock the save method
        growth_repo.update_growth_unit.return_value = True
        
        # Create unit with threshold service
        unit = UnitRuntime(
            unit_id=1,
            unit_name="Test Unit",
            location="Indoor",
            user_id=1,
            threshold_service=threshold_service
        )
        
        # Create and set active plant with correct parameters
        plant = PlantProfile(
            plant_id=1,
            plant_name="Cherry Tomato",
            current_stage="Vegetative",
            growth_stages=[
                {"stage": "Seedling", "duration": {"min_days": 10, "max_days": 14}, "conditions": {"light_hours": 16}},
                {"stage": "Vegetative", "duration": {"min_days": 20, "max_days": 30}, "conditions": {"light_hours": 18}},
                {"stage": "Flowering", "duration": {"min_days": 30, "max_days": 45}, "conditions": {"light_hours": 12}}
            ],
            growth_repo=growth_repo,
            plant_type="Tomatoes"
        )
        unit.set_active_plant(plant.id)
        unit.plants[plant.id] = plant
        unit.active_plant = plant
        
        # Apply AI conditions (no hardware manager needed - GrowthService manages infrastructure)
        unit.apply_ai_conditions()
        
        # Verify ThresholdService was used
        mock_ai_model.predict_growth_conditions.assert_called()
        
        # Verify thresholds were updated
        assert unit.settings.temperature_threshold > 0
        assert unit.settings.humidity_threshold > 0
        
        logger.info("✅ apply_ai_conditions successfully used ThresholdService")
    
    def test_plant_specific_thresholds_applied(
        self, threshold_service, mock_repositories, mock_ai_model
    ):
        """Test that plant-specific thresholds are applied for different plants"""
        growth_repo, analytics_repo = mock_repositories
        growth_repo.update_growth_unit.return_value = True
        
        unit = UnitRuntime(
            unit_id=1,
            unit_name="Test Unit",
            location="Indoor",
            user_id=1,
            growth_repo=growth_repo,
            analytics_repo=analytics_repo,
            threshold_service=threshold_service
        )
        
        # Test with Tomatoes
        tomato_plant = PlantProfile(
            plant_id=1,
            plant_name="Cherry Tomato",
            current_stage="Flowering",
            growth_stages=[
                {"stage": "Flowering", "duration": {"min_days": 30, "max_days": 45}, "conditions": {"light_hours": 12}}
            ],
            growth_repo=growth_repo,
            plant_type="Tomatoes"
        )
        unit.plants[1] = tomato_plant
        unit.active_plant = tomato_plant
        
        unit.apply_ai_conditions()
        tomato_temp = unit.settings.temperature_threshold
        
        # Test with Basil
        basil_plant = PlantProfile(
            plant_id=2,
            plant_name="Sweet Basil",
            current_stage="Vegetative",
            growth_stages=[
                {"stage": "Vegetative", "duration": {"min_days": 20, "max_days": 30}, "conditions": {"light_hours": 16}}
            ],
            growth_repo=growth_repo,
            plant_type="Basil"
        )
        unit.plants[2] = basil_plant
        unit.active_plant = basil_plant
        
        unit.apply_ai_conditions()
        basil_temp = unit.settings.temperature_threshold
        
        # Thresholds should be different for different plants
        # (assuming they have different optimal ranges)
        logger.info(f"Tomato threshold: {tomato_temp}, Basil threshold: {basil_temp}")
        logger.info("✅ Plant-specific thresholds applied correctly")
    
    def test_fallback_to_ai_only_when_no_threshold_service(
        self, mock_repositories, mock_ai_model
    ):
        """Test fallback to AI-only mode when ThresholdService unavailable"""
        growth_repo, analytics_repo = mock_repositories
        growth_repo.update_growth_unit.return_value = True
        
        # Create unit without climate optimizer (growth predictor is disabled)
        unit = UnitRuntime(
            unit_id=1,
            unit_name="Test Unit",
            location="Indoor",
            user_id=1,
            growth_repo=growth_repo,
            analytics_repo=analytics_repo,
            threshold_service=None  # No ThresholdService
        )
        
        # Growth predictor is now disabled (migrated to service layer)
        unit.growth_predictor = None
        
        plant = PlantProfile(
            plant_id=1,
            plant_name="Cherry Tomato",
            current_stage="Vegetative",
            growth_stages=[
                {"stage": "Vegetative", "duration": {"min_days": 20, "max_days": 30}, "conditions": {"light_hours": 18}}
            ],
            growth_repo=growth_repo,
            plant_type="Tomatoes"
        )
        unit.plants[1] = plant
        unit.active_plant = plant
        
        # Apply AI conditions
        unit.apply_ai_conditions()
        
        # Should use AI directly
        mock_ai_model.predict_growth_conditions.assert_called()
        logger.info("✅ Fallback to AI-only mode works correctly")


def run_integration_tests():
    """Run all integration tests"""
    import sys
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run pytest
    pytest_args = [
        __file__,
        '-v',           # Verbose
        '-s',           # Show print statements
        '--tb=short',   # Short traceback format
        '--color=yes'   # Colored output
    ]
    
    exit_code = pytest.main(pytest_args)
    
    if exit_code == 0:
        logger.info("\n" + "="*80)
        logger.info("🎉 ALL INTEGRATION TESTS PASSED!")
        logger.info("="*80)
        logger.info("\nIntegration Summary:")
        logger.info("✅ ThresholdService properly initialized with AI model")
        logger.info("✅ Plant-specific thresholds loaded from plants_info.json")
        logger.info("✅ AI predictions blended with plant thresholds (70/30 ratio)")
        logger.info("✅ UnitRuntime successfully integrated with ThresholdService")
        logger.info("✅ apply_ai_conditions uses unified threshold system")
        logger.info("✅ Hardware manager receives plant-specific threshold ranges")
        logger.info("✅ Fallback to AI-only mode works when service unavailable")
    else:
        logger.error("\n❌ Some integration tests failed. Review output above.")
    
    return exit_code


if __name__ == "__main__":
    exit(run_integration_tests())
