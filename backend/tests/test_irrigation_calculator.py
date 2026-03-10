"""
Irrigation Calculator Tests
===========================
Tests for IrrigationCalculator domain service.
"""

from dataclasses import dataclass
from unittest.mock import Mock

import pytest

from app.constants import (
    GROWTH_STAGE_VOLUME_MULTIPLIERS,
    PUMP_CALIBRATION_DEFAULTS,
    REFERENCE_POT_SIZE_LITERS,
    GrowingMediumConfig,
)
from app.domain.irrigation_calculator import (
    IrrigationCalculation,
    IrrigationCalculator,
    MLPrediction,
)


@dataclass
class MockPlantProfile:
    """Mock PlantProfile for testing."""

    plant_id: int = 1
    plant_name: str = "Test Plant"
    plant_type: str = "tomato"
    current_stage: str = "vegetative"
    pot_size_liters: float = 10.0
    growing_medium: str = "soil"
    unit_id: int = 1


@pytest.fixture
def mock_plant_service():
    """Create mock PlantViewService."""
    service = Mock()

    # Mock plant_json_handler
    service.plant_json_handler = Mock()
    service.plant_json_handler.get_watering_schedule.return_value = {
        "amount_ml_per_plant": 150.0,
        "frequency": "daily",
    }

    return service


@pytest.fixture
def calculator(mock_plant_service):
    """Create IrrigationCalculator with mocked dependencies."""
    return IrrigationCalculator(mock_plant_service)


class TestComputeWaterVolume:
    """Tests for compute_water_volume method."""

    def test_basic_calculation_with_defaults(self, calculator):
        """Test basic water volume calculation."""
        volume, reasoning = calculator.compute_water_volume(
            plant_id=1,
            pot_size_liters=REFERENCE_POT_SIZE_LITERS,  # 5L reference
            growing_medium="soil",
            growth_stage="vegetative",
            plant_type="tomato",
        )

        # Base 150ml * pot_factor 1.0 * soil_factor 1.0 * veg_factor 1.0
        assert volume == 150.0
        assert "base=150" in reasoning
        assert "pot_factor=1.00" in reasoning

    def test_larger_pot_increases_volume(self, calculator):
        """Test that larger pots get more water."""
        volume, reasoning = calculator.compute_water_volume(
            plant_id=1,
            pot_size_liters=10.0,  # 2x reference
            growing_medium="soil",
            growth_stage="vegetative",
            plant_type="tomato",
        )

        # Base 150ml * pot_factor 2.0 = 300ml
        assert volume == 300.0
        assert "pot_factor=2.00" in reasoning

    def test_coco_coir_medium_reduces_volume(self, calculator):
        """Test that coco coir reduces water due to lower retention."""
        volume, _ = calculator.compute_water_volume(
            plant_id=1,
            pot_size_liters=REFERENCE_POT_SIZE_LITERS,
            growing_medium="coco_coir",
            growth_stage="vegetative",
            plant_type="tomato",
        )

        # Coco has 0.8 retention coefficient
        expected = 150.0 * GrowingMediumConfig.COCO_COIR.retention_coefficient
        assert volume == expected

    def test_flowering_stage_increases_volume(self, calculator):
        """Test that flowering stage increases water needs."""
        volume, reasoning = calculator.compute_water_volume(
            plant_id=1,
            pot_size_liters=REFERENCE_POT_SIZE_LITERS,
            growing_medium="soil",
            growth_stage="flowering",
            plant_type="tomato",
        )

        stage_factor = GROWTH_STAGE_VOLUME_MULTIPLIERS.get("flowering", 1.0)
        expected = 150.0 * stage_factor
        assert volume == expected
        assert "flowering" in reasoning

    def test_zero_pot_size_uses_default_factor(self, calculator):
        """Test handling of zero pot size."""
        volume, _ = calculator.compute_water_volume(
            plant_id=1,
            pot_size_liters=0.0,
            growing_medium="soil",
            growth_stage="vegetative",
            plant_type="tomato",
        )

        # pot_factor should be 1.0 when pot_size is 0
        assert volume == 150.0

    def test_unknown_medium_defaults_to_soil(self, calculator):
        """Test that unknown medium defaults to soil properties."""
        volume, reasoning = calculator.compute_water_volume(
            plant_id=1,
            pot_size_liters=REFERENCE_POT_SIZE_LITERS,
            growing_medium="unknown_medium",
            growth_stage="vegetative",
            plant_type="tomato",
        )

        # Should use soil (retention=1.0)
        assert volume == 150.0
        assert "soil" in reasoning

    def test_unknown_stage_uses_default_multiplier(self, calculator):
        """Test that unknown growth stage uses 1.0 multiplier."""
        volume, _ = calculator.compute_water_volume(
            plant_id=1,
            pot_size_liters=REFERENCE_POT_SIZE_LITERS,
            growing_medium="soil",
            growth_stage="unknown_stage",
            plant_type="tomato",
        )

        # Unknown stage should use 1.0 multiplier
        assert volume == 150.0

    def test_combined_factors(self, calculator):
        """Test calculation with multiple factors applied."""
        volume, _ = calculator.compute_water_volume(
            plant_id=1,
            pot_size_liters=15.0,  # 3x reference
            growing_medium="coco_coir",  # 0.8 retention
            growth_stage="flowering",
            plant_type="tomato",
        )

        pot_factor = 15.0 / REFERENCE_POT_SIZE_LITERS  # 3.0
        medium_factor = GrowingMediumConfig.COCO_COIR.retention_coefficient  # 0.8
        stage_factor = GROWTH_STAGE_VOLUME_MULTIPLIERS.get("flowering", 1.0)
        expected = 150.0 * pot_factor * medium_factor * stage_factor

        assert abs(volume - expected) < 0.01


class TestComputeDuration:
    """Tests for compute_duration method."""

    def test_basic_duration_calculation(self, calculator):
        """Test basic duration calculation."""
        duration = calculator.compute_duration(
            volume_ml=100.0,
            flow_rate_ml_per_second=3.33,
        )

        # 100 / 3.33 ≈ 30 seconds
        assert duration == 30

    def test_respects_minimum_duration(self, calculator):
        """Test that minimum duration is enforced."""
        duration = calculator.compute_duration(
            volume_ml=10.0,
            flow_rate_ml_per_second=10.0,  # Would be 1 second
            min_duration=5,
        )

        assert duration == 5

    def test_respects_maximum_duration(self, calculator):
        """Test that maximum duration is enforced."""
        duration = calculator.compute_duration(
            volume_ml=10000.0,
            flow_rate_ml_per_second=1.0,  # Would be 10000 seconds
            max_duration=600,
        )

        assert duration == 600

    def test_zero_flow_rate_returns_default(self, calculator):
        """Test handling of zero flow rate."""
        duration = calculator.compute_duration(
            volume_ml=100.0,
            flow_rate_ml_per_second=0.0,
        )

        # Should return default calibration duration
        assert duration == PUMP_CALIBRATION_DEFAULTS["calibration_duration_seconds"]

    def test_negative_flow_rate_returns_default(self, calculator):
        """Test handling of negative flow rate."""
        duration = calculator.compute_duration(
            volume_ml=100.0,
            flow_rate_ml_per_second=-1.0,
        )

        assert duration == PUMP_CALIBRATION_DEFAULTS["calibration_duration_seconds"]


class TestCalculate:
    """Tests for calculate method (full calculation)."""

    def test_plant_not_found_returns_defaults(self, calculator, mock_plant_service):
        """Test behavior when plant is not found."""
        mock_plant_service.get_plant.return_value = None

        result = calculator.calculate(plant_id=999)

        assert result.water_volume_ml == IrrigationCalculator.DEFAULT_BASE_ML
        assert result.confidence == 0.1
        assert "not found" in result.reasoning.lower()

    def test_full_calculation_with_plant(self, calculator, mock_plant_service):
        """Test full calculation with valid plant data."""
        mock_plant = MockPlantProfile(
            plant_id=1,
            pot_size_liters=10.0,
            growing_medium="soil",
            current_stage="vegetative",
            plant_type="tomato",
        )
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.calculate(plant_id=1)

        assert isinstance(result, IrrigationCalculation)
        assert result.plant_id == 1
        assert result.water_volume_ml > 0
        assert result.duration_seconds > 0

    def test_calibrated_pump_increases_confidence(self, calculator, mock_plant_service):
        """Test that calibrated pump increases confidence."""
        mock_plant = MockPlantProfile()
        mock_plant_service.get_plant.return_value = mock_plant

        result_uncalibrated = calculator.calculate(plant_id=1, pump_flow_rate=None)
        result_calibrated = calculator.calculate(plant_id=1, pump_flow_rate=3.5)

        assert result_calibrated.confidence > result_uncalibrated.confidence

    def test_uses_custom_flow_rate(self, calculator, mock_plant_service):
        """Test that custom flow rate is used in calculation."""
        mock_plant = MockPlantProfile()
        mock_plant_service.get_plant.return_value = mock_plant

        custom_flow_rate = 5.0
        result = calculator.calculate(plant_id=1, pump_flow_rate=custom_flow_rate)

        assert result.flow_rate_ml_per_second == custom_flow_rate
        assert "calibrated" in result.reasoning


class TestCalculateForPlant:
    """Tests for calculate_for_plant method."""

    def test_handles_missing_plant_type(self, calculator, mock_plant_service):
        """Test handling of plant with missing plant_type."""
        mock_plant = MockPlantProfile(plant_type=None)
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.calculate_for_plant(mock_plant)

        assert result.plant_type == "default"

    def test_handles_missing_growth_stage(self, calculator, mock_plant_service):
        """Test handling of plant with missing growth stage."""
        mock_plant = MockPlantProfile(current_stage=None)

        result = calculator.calculate_for_plant(mock_plant)

        assert result.growth_stage == "vegetative"

    def test_handles_zero_pot_size(self, calculator, mock_plant_service):
        """Test handling of plant with zero pot size."""
        mock_plant = MockPlantProfile(pot_size_liters=0.0)

        result = calculator.calculate_for_plant(mock_plant)

        # Should use reference pot size as default
        assert result.pot_size_liters == REFERENCE_POT_SIZE_LITERS


class TestCalculateConfidence:
    """Tests for _calculate_confidence method."""

    def test_full_confidence_with_all_data(self, calculator):
        """Test 100% confidence when all data is available."""
        confidence = calculator._calculate_confidence(
            has_calibrated_flow_rate=True,
            has_pot_size=True,
            has_plant_type=True,
        )

        assert confidence == 1.0

    def test_partial_confidence_without_calibration(self, calculator):
        """Test reduced confidence without calibration."""
        confidence = calculator._calculate_confidence(
            has_calibrated_flow_rate=False,
            has_pot_size=True,
            has_plant_type=True,
        )

        assert confidence == 0.5  # Missing 50% from calibration

    def test_minimum_confidence(self, calculator):
        """Test minimum confidence with no data."""
        confidence = calculator._calculate_confidence(
            has_calibrated_flow_rate=False,
            has_pot_size=False,
            has_plant_type=False,
        )

        assert confidence == 0.0


class TestEstimateMoistureIncrease:
    """Tests for estimate_moisture_increase method."""

    def test_basic_moisture_estimate(self, calculator):
        """Test basic moisture increase estimation."""
        increase = calculator.estimate_moisture_increase(
            water_volume_ml=500.0,
            pot_size_liters=5.0,  # 5000ml
            growing_medium="soil",
        )

        # 500ml / 5000ml * 100 * 1.0 = 10%
        assert increase == 10.0

    def test_capped_at_50_percent(self, calculator):
        """Test that moisture increase is capped at 50%."""
        increase = calculator.estimate_moisture_increase(
            water_volume_ml=5000.0,  # Equal to pot volume
            pot_size_liters=5.0,
            growing_medium="soil",
        )

        assert increase == 50.0

    def test_zero_pot_size_returns_zero(self, calculator):
        """Test handling of zero pot size."""
        increase = calculator.estimate_moisture_increase(
            water_volume_ml=500.0,
            pot_size_liters=0.0,
            growing_medium="soil",
        )

        assert increase == 0.0

    def test_medium_affects_retention(self, calculator):
        """Test that growing medium affects moisture retention."""
        soil_increase = calculator.estimate_moisture_increase(
            water_volume_ml=500.0,
            pot_size_liters=5.0,
            growing_medium="soil",
        )

        perlite_increase = calculator.estimate_moisture_increase(
            water_volume_ml=500.0,
            pot_size_liters=5.0,
            growing_medium="perlite",
        )

        # Perlite has lower retention, so less moisture retained
        assert perlite_increase < soil_increase


class TestIrrigationCalculationDataclass:
    """Tests for IrrigationCalculation dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        calc = IrrigationCalculation(
            water_volume_ml=150.5,
            duration_seconds=30,
            flow_rate_ml_per_second=3.333,
            confidence=0.75,
            reasoning="test reasoning",
            plant_id=1,
            pot_size_liters=10.0,
            growing_medium="soil",
            growth_stage="vegetative",
            plant_type="tomato",
        )

        result = calc.to_dict()

        assert result["water_volume_ml"] == 150.5
        assert result["duration_seconds"] == 30
        assert result["flow_rate_ml_per_second"] == 3.333
        assert result["confidence"] == 0.75
        assert result["reasoning"] == "test reasoning"
        assert result["inputs"]["plant_id"] == 1
        assert result["inputs"]["pot_size_liters"] == 10.0
        assert result["ml_adjusted"] is False

    def test_to_dict_with_ml_prediction(self):
        """Test conversion with ML prediction data."""
        ml_pred = MLPrediction(
            predicted_volume_ml=200.0,
            adjustment_factor=1.1,
            confidence=0.85,
            model_version="v1.0",
            features_used=["temperature", "humidity"],
        )
        calc = IrrigationCalculation(
            water_volume_ml=180.0,
            duration_seconds=45,
            flow_rate_ml_per_second=4.0,
            confidence=0.9,
            reasoning="ML adjusted",
            ml_prediction=ml_pred,
            ml_adjusted=True,
        )

        result = calc.to_dict()

        assert result["ml_adjusted"] is True
        assert "ml_prediction" in result
        assert result["ml_prediction"]["predicted_volume_ml"] == 200.0
        assert result["ml_prediction"]["confidence"] == 0.85


class TestMLIntegration:
    """Tests for ML integration methods."""

    def test_calculate_with_ml_no_predictor(self, calculator, mock_plant_service):
        """Test ML calculation falls back when no predictor."""
        mock_plant = MockPlantProfile()
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.calculate_with_ml(plant_id=1)

        assert result.ml_adjusted is False
        assert result.ml_prediction is None

    def test_calculate_with_ml_predictor(self, mock_plant_service):
        """Test ML calculation with predictor."""
        # Create mock ML predictor
        ml_predictor = Mock()
        ml_predictor.predict_water_volume.return_value = 200.0
        ml_predictor.get_adjustment_factor.return_value = 1.0

        calculator = IrrigationCalculator(mock_plant_service, ml_predictor=ml_predictor)

        mock_plant = MockPlantProfile()
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.calculate_with_ml(plant_id=1, environmental_data={"temperature": 25.0, "humidity": 60.0})

        assert result.ml_adjusted is True
        assert result.ml_prediction is not None
        ml_predictor.predict_water_volume.assert_called_once()

    def test_calculate_with_ml_low_confidence(self, mock_plant_service):
        """Test ML calculation falls back when confidence is low."""
        ml_predictor = Mock()
        ml_predictor.predict_water_volume.return_value = None  # No prediction
        ml_predictor.get_adjustment_factor.return_value = 1.0

        calculator = IrrigationCalculator(mock_plant_service, ml_predictor=ml_predictor)

        mock_plant = MockPlantProfile()
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.calculate_with_ml(plant_id=1)

        # Should fall back to formula-based calculation
        assert result.ml_adjusted is False

    def test_record_feedback_with_callback(self, mock_plant_service):
        """Test feedback recording calls callback."""
        callback = Mock()
        calculator = IrrigationCalculator(mock_plant_service, feedback_callback=callback)

        calculator.record_feedback(plant_id=1, feedback_type="just_right", volume_ml=150.0)

        callback.assert_called_once_with(1, "just_right", 150.0)

    def test_record_feedback_without_callback(self, calculator):
        """Test feedback recording without callback doesn't error."""
        # Should not raise
        calculator.record_feedback(plant_id=1, feedback_type="too_little", volume_ml=100.0)


class TestGetRecommendations:
    """Tests for get_recommendations method."""

    def test_moisture_below_minimum(self, calculator, mock_plant_service):
        """Test recommendation when moisture is below minimum."""
        mock_plant = MockPlantProfile(growing_medium="soil")
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.get_recommendations(
            plant_id=1,
            current_moisture=30.0,  # Below soil minimum of 40%
        )

        assert result["action"] == "water_now"
        assert result["urgency"] in ("medium", "high")

    def test_moisture_above_maximum(self, calculator, mock_plant_service):
        """Test recommendation when moisture is above maximum."""
        mock_plant = MockPlantProfile(growing_medium="soil")
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.get_recommendations(
            plant_id=1,
            current_moisture=80.0,  # Above soil maximum of 70%
        )

        assert result["action"] == "wait"
        assert result["urgency"] == "low"

    def test_moisture_in_range(self, calculator, mock_plant_service):
        """Test recommendation when moisture is optimal."""
        mock_plant = MockPlantProfile(growing_medium="soil")
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.get_recommendations(
            plant_id=1,
            current_moisture=55.0,  # Within soil range of 40-70%
        )

        assert result["action"] == "monitor"
        assert result["in_range"] is True

    def test_plant_not_found(self, calculator, mock_plant_service):
        """Test recommendation when plant not found."""
        mock_plant_service.get_plant.return_value = None

        result = calculator.get_recommendations(plant_id=999, current_moisture=50.0)

        assert result["action"] == "unknown"

    def test_high_urgency_severe_deficit(self, calculator, mock_plant_service):
        """Test high urgency for severe moisture deficit."""
        mock_plant = MockPlantProfile(growing_medium="soil")
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.get_recommendations(
            plant_id=1,
            current_moisture=10.0,  # Very low, deficit > 20%
        )

        assert result["urgency"] == "high"


class TestMLPredictionDataclass:
    """Tests for MLPrediction dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        pred = MLPrediction(
            predicted_volume_ml=200.0,
            adjustment_factor=1.05,
            confidence=0.85,
            model_version="v1.2",
            features_used=["temp", "humidity"],
        )

        result = pred.to_dict()

        assert result["predicted_volume_ml"] == 200.0
        assert result["adjustment_factor"] == 1.05
        assert result["confidence"] == 0.85
        assert result["model_version"] == "v1.2"
        assert result["features_used"] == ["temp", "humidity"]

    def test_default_values(self):
        """Test default values."""
        pred = MLPrediction()

        assert pred.predicted_volume_ml is None
        assert pred.adjustment_factor == 1.0
        assert pred.confidence == 0.0
        assert pred.features_used == []


class TestMLWorkflowIntegration:
    """Integration tests for complete ML workflow with environmental data and fallback."""

    def test_calculate_with_ml_and_environmental_data(self, mock_plant_service):
        """Test ML calculation with full environmental data (Phase 2)."""
        # Create mock ML predictor that implements MLPredictorProtocol
        ml_predictor = Mock()
        # Phase 2: Returns actual prediction based on environmental data
        ml_predictor.predict_water_volume.return_value = 175.0  # ML suggests this
        ml_predictor.get_adjustment_factor.return_value = 1.05  # Slight increase from feedback

        calculator = IrrigationCalculator(mock_plant_service, ml_predictor=ml_predictor)

        mock_plant = MockPlantProfile(
            plant_type="tomato",
            pot_size_liters=10.0,
            growing_medium="soil",
            current_stage="flowering",
        )
        mock_plant_service.get_plant.return_value = mock_plant

        # Environmental data from irrigation request
        env_data = {
            "temperature": 25.5,
            "humidity": 65.0,
            "vpd": 1.2,
            "lux": 800.0,
            "soil_moisture": 45.0,
        }

        result = calculator.calculate_with_ml(
            plant_id=1,
            pump_flow_rate=3.5,
            environmental_data=env_data,
        )

        # Verify ML predictor was called with correct data
        ml_predictor.predict_water_volume.assert_called_once_with(1, env_data)
        ml_predictor.get_adjustment_factor.assert_called_once()

        # Phase 2: ML provides prediction, so result should be ML-adjusted
        assert result.ml_adjusted is True
        assert result.ml_prediction is not None
        assert result.ml_prediction.predicted_volume_ml == 175.0
        assert result.ml_prediction.adjustment_factor == 1.05
        assert result.ml_prediction.confidence > 0.0
        assert result.water_volume_ml > 0
        assert result.duration_seconds > 0

    def test_calculate_with_ml_missing_environmental_data(self, mock_plant_service):
        """Test ML calculation gracefully handles missing environmental data."""
        ml_predictor = Mock()
        ml_predictor.predict_water_volume.return_value = None  # No prediction without data
        ml_predictor.get_adjustment_factor.return_value = 1.0

        calculator = IrrigationCalculator(mock_plant_service, ml_predictor=ml_predictor)

        mock_plant = MockPlantProfile()
        mock_plant_service.get_plant.return_value = mock_plant

        # No environmental data (sensors offline)
        result = calculator.calculate_with_ml(
            plant_id=1,
            pump_flow_rate=3.5,
            environmental_data=None,
        )

        # Should still call ML predictor (it might use historical data)
        ml_predictor.predict_water_volume.assert_called_once_with(1, {})

        # Should fall back to formula-based
        assert result.water_volume_ml > 0
        assert result.duration_seconds > 0

    def test_calculate_with_ml_partial_environmental_data(self, mock_plant_service):
        """Test ML calculation with partial environmental data (some sensors missing)."""
        ml_predictor = Mock()
        # ML can work with partial data
        ml_predictor.predict_water_volume.return_value = 160.0
        ml_predictor.get_adjustment_factor.return_value = 1.0

        calculator = IrrigationCalculator(mock_plant_service, ml_predictor=ml_predictor)

        mock_plant = MockPlantProfile()
        mock_plant_service.get_plant.return_value = mock_plant

        # Partial environmental data (humidity and VPD sensors offline)
        partial_env_data = {
            "temperature": 24.0,
            "soil_moisture": 48.0,
        }

        result = calculator.calculate_with_ml(
            plant_id=1,
            environmental_data=partial_env_data,
        )

        # Should work with partial data
        ml_predictor.predict_water_volume.assert_called_once_with(1, partial_env_data)
        assert result.water_volume_ml > 0
        assert result.ml_adjusted is True  # ML provided prediction

    def test_apply_adjustment_factor_when_only_feedback(self, mock_plant_service):
        """Test applying adjustment factor when only feedback data is available."""
        ml_predictor = Mock()
        ml_predictor.predict_water_volume.return_value = None  # No prediction
        ml_predictor.get_adjustment_factor.return_value = 1.1  # Only adjustment factor
        ml_predictor.get_feedback_for_plant = Mock(
            return_value=[
                {"feedback_response": "too_little"},
                {"feedback_response": "just_right"},
            ]
        )

        calculator = IrrigationCalculator(mock_plant_service, ml_predictor=ml_predictor)
        calculator.ML_CONFIDENCE_THRESHOLD = 0.7  # Standard threshold

        mock_plant = MockPlantProfile()
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.calculate_with_ml(
            plant_id=1,
            environmental_data={"temperature": 25.0},
        )

        # Adjustment factor should still apply to formula-based result
        assert result.ml_adjusted is True
        assert result.ml_prediction is not None
        assert result.ml_prediction.adjustment_factor == 1.1

    def test_ml_adjustment_factor_applied(self, mock_plant_service):
        """Test that ML adjustment factor is applied to formula volume."""
        ml_predictor = Mock()
        ml_predictor.predict_water_volume.return_value = None  # No direct prediction
        ml_predictor.get_adjustment_factor.return_value = 1.15  # +15% adjustment
        ml_predictor.get_feedback_for_plant = Mock(
            return_value=[
                {"feedback_response": "too_little"},
            ]
        )

        calculator = IrrigationCalculator(mock_plant_service, ml_predictor=ml_predictor)

        mock_plant = MockPlantProfile()
        mock_plant_service.get_plant.return_value = mock_plant

        result = calculator.calculate_with_ml(
            plant_id=1,
            environmental_data={"soil_moisture": 45.0},
        )

        # Adjustment factor applied to formula volume
        assert result.ml_prediction is not None
        assert result.ml_prediction.adjustment_factor == 1.15
        assert result.ml_adjusted is True

    def test_integration_workflow_simulation(self, mock_plant_service):
        """Simulate complete workflow: detection → calculation with ML → execution."""
        # Setup
        ml_predictor = Mock()
        # Phase 2: ML provides predictions
        ml_predictor.predict_water_volume.return_value = 185.0
        ml_predictor.get_adjustment_factor.return_value = 1.05
        ml_predictor.get_feedback_for_plant = Mock(
            return_value=[
                {"feedback_response": "just_right"},
                {"feedback_response": "too_little"},
                {"feedback_response": "just_right"},
            ]
        )

        calculator = IrrigationCalculator(mock_plant_service, ml_predictor=ml_predictor)

        mock_plant = MockPlantProfile(
            plant_id=42,
            plant_type="basil",
            pot_size_liters=8.0,
            growing_medium="coco",
            current_stage="vegetative",
            unit_id=5,  # Add unit_id for feedback lookup
        )
        mock_plant_service.get_plant.return_value = mock_plant

        # Simulate detection - sensor readings captured
        ml_context = {
            "temperature": 23.5,
            "humidity": 58.0,
            "vpd": 1.15,
            "lux": 650.0,
            "soil_moisture": 42.0,
        }

        # Calculate irrigation with ML context
        calculation = calculator.calculate_with_ml(
            plant_id=42,
            pump_flow_rate=3.2,  # Calibrated pump
            environmental_data=ml_context,
        )

        # Verify calculation produced valid results
        assert calculation.plant_id == 42
        assert calculation.water_volume_ml > 0
        assert calculation.duration_seconds > 0
        assert calculation.flow_rate_ml_per_second == 3.2
        assert calculation.confidence > 0.5  # Has calibrated pump

        # Verify ML context was used
        assert calculation.ml_prediction is not None
        assert "temperature" in calculation.ml_prediction.features_used

        # Phase 2: ML provides predictions
        assert calculation.ml_adjusted is True
        assert calculation.ml_prediction.predicted_volume_ml == 185.0
        assert calculation.ml_prediction.adjustment_factor == 1.05
