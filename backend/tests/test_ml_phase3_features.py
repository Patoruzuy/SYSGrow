"""
Integration tests for Phase 3 ML features.

Tests all 4 advanced features:
1. Trained ML model integration
2. Moisture decline rate tracking
3. Plant-specific learning
4. Seasonal adjustment patterns
"""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from app.domain.irrigation import MoistureDeclinePrediction
from app.services.ai.irrigation_predictor import IrrigationPredictor


class TestPhase3Integration:
    """Integration tests for Phase 3 advanced ML features."""

    def test_trained_model_integration(self):
        """Test Feature 1: Trained ML model integration."""
        # Setup
        mock_repo = Mock()
        mock_model = Mock()
        mock_feature_engineer = Mock()

        # Mock trained model prediction
        mock_model.predict.return_value = [105.0]
        mock_feature_engineer.extract_features.return_value = [
            45.0,
            26.5,
            50.0,
            1.4,
            600.0,  # soil_moisture, temp, humidity, vpd, light
        ]

        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)
        predictor._duration_model = mock_model
        predictor._feature_engineer = mock_feature_engineer

        # Execute
        volume = predictor.predict_water_volume(
            plant_id=123,
            environmental_data={
                "soil_moisture": 45.0,
                "temperature": 26.5,
                "humidity": 50.0,
                "vpd": 1.4,
                "lux": 600.0,
            },
        )

        # Verify trained model was used
        assert volume == 105.0
        mock_model.predict.assert_called_once()
        mock_feature_engineer.extract_features.assert_called_once()

    def test_algorithmic_fallback_when_model_unavailable(self):
        """Test that system falls back to algorithmic when trained model unavailable."""
        # Setup - no trained model
        mock_repo = Mock()
        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)
        predictor._duration_model = None

        # Execute
        volume = predictor.predict_water_volume(
            plant_id=123,
            environmental_data={
                "soil_moisture": 45.0,
                "temperature": 26.5,
                "humidity": 50.0,
                "vpd": 1.4,
            },
        )

        # Verify algorithmic calculation works
        assert volume is not None
        assert 50 < volume < 200  # Reasonable range

    def test_seasonal_adjustment_summer(self, monkeypatch):
        """Test Feature 4: Seasonal adjustment for summer (+15%)."""

        # Mock datetime to return July (summer)
        class MockDatetime:
            @staticmethod
            def now():
                return datetime(2024, 7, 15)  # July 15

        monkeypatch.setattr("app.services.ai.irrigation_predictor.datetime", MockDatetime)

        # Setup
        mock_repo = Mock()
        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)

        # Execute
        seasonal_factor = predictor._get_seasonal_adjustment()

        # Verify summer adjustment
        assert seasonal_factor == 1.15  # +15%

        # Test volume with seasonal adjustment
        volume = predictor.predict_water_volume(
            plant_id=123,
            environmental_data={
                "soil_moisture": 45.0,
                "temperature": 26.5,
            },
        )

        # Verify seasonal boost applied (should be higher than baseline)
        assert volume is not None
        assert volume > 100  # Summer boost applied

    def test_seasonal_adjustment_winter(self, monkeypatch):
        """Test Feature 4: Seasonal adjustment for winter (-10%)."""

        # Mock datetime to return January (winter)
        class MockDatetime:
            @staticmethod
            def now():
                return datetime(2024, 1, 15)  # January 15

        monkeypatch.setattr("app.services.ai.irrigation_predictor.datetime", MockDatetime)

        # Setup
        mock_repo = Mock()
        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)

        # Execute
        seasonal_factor = predictor._get_seasonal_adjustment()

        # Verify winter adjustment
        assert seasonal_factor == 0.90  # -10%

    def test_plant_specific_learning(self):
        """Test Feature 3: Plant-specific learning."""
        # Setup
        mock_repo = Mock()
        mock_repo.get_training_data_for_model.return_value = [
            {"plant_id": 123, "feedback_response": "too_little"},
            {"plant_id": 123, "feedback_response": "just_right"},
            {"plant_id": 456, "feedback_response": "too_much"},  # Different plant
            {"plant_id": 123, "feedback_response": "just_right"},
        ]

        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)

        # Execute - get feedback for specific plant
        feedback = predictor.get_feedback_for_plant(
            unit_id=1,
            plant_id=123,  # Filter for plant 123
            limit=20,
        )

        # Verify only plant 123 feedback returned
        assert len(feedback) == 3
        assert all(f["plant_id"] == 123 for f in feedback)

    def test_plant_specific_adjustment_factor(self):
        """Test that adjustment factor uses plant-specific feedback."""
        # Setup
        mock_repo = Mock()
        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)

        # Plant-specific feedback: mostly "too_little"
        plant_feedback = [
            {"feedback_response": "too_little"},
            {"feedback_response": "too_little"},
            {"feedback_response": "too_little"},
            {"feedback_response": "just_right"},
        ]

        # Execute
        adjustment = predictor.get_adjustment_factor(plant_id=123, historical_feedback=plant_feedback)

        # Verify adjustment increases volume (>1.0)
        assert adjustment > 1.0  # Should increase due to "too_little" feedback

    def test_moisture_decline_prediction_mock(self):
        """Test Feature 2: Moisture decline rate tracking (mocked)."""
        # Setup
        mock_repo = Mock()
        # Mock moisture history showing steady decline
        now = datetime.now()
        mock_repo.get_moisture_history.return_value = [
            {"soil_moisture": 60.0, "timestamp": (now - timedelta(hours=24)).isoformat()},
            {"soil_moisture": 57.0, "timestamp": (now - timedelta(hours=18)).isoformat()},
            {"soil_moisture": 54.0, "timestamp": (now - timedelta(hours=12)).isoformat()},
            {"soil_moisture": 51.0, "timestamp": (now - timedelta(hours=6)).isoformat()},
            {"soil_moisture": 48.0, "timestamp": now.isoformat()},
        ]

        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)

        # Execute
        prediction = predictor.predict_next_irrigation_time(
            plant_id=123, current_moisture=48.0, threshold=40.0, hours_lookback=72
        )

        # Verify prediction made
        assert prediction is not None
        assert isinstance(prediction, MoistureDeclinePrediction)
        assert prediction.current_moisture == 48.0
        assert prediction.threshold == 40.0
        assert prediction.decline_rate_per_hour < 0  # Declining
        assert prediction.hours_until_threshold > 0  # Time until threshold
        assert 0.3 <= prediction.confidence <= 0.95
        assert prediction.samples_used == 5

    def test_complete_phase3_workflow(self, monkeypatch):
        """Test all 4 Phase 3 features working together."""

        # Mock datetime for summer season
        class MockDatetime:
            @staticmethod
            def now():
                return datetime(2024, 7, 15)  # July (summer)

        monkeypatch.setattr("app.services.ai.irrigation_predictor.datetime", MockDatetime)

        # Setup
        mock_repo = Mock()
        mock_repo.get_training_data_for_model.return_value = [
            {"plant_id": 123, "feedback_response": "too_little"},
            {"plant_id": 123, "feedback_response": "just_right"},
            {"plant_id": 123, "feedback_response": "just_right"},
        ]

        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)

        # Test 1: Volume prediction with seasonal adjustment (summer +15%)
        volume = predictor.predict_water_volume(
            plant_id=123,
            environmental_data={
                "soil_moisture": 45.0,
                "temperature": 28.0,  # Hot summer day
                "vpd": 1.5,
            },
        )
        assert volume is not None
        seasonal_factor = predictor._get_seasonal_adjustment()
        assert seasonal_factor == 1.15  # Summer boost

        # Test 2: Plant-specific feedback
        feedback = predictor.get_feedback_for_plant(unit_id=1, plant_id=123, limit=20)
        assert len(feedback) == 3
        assert all(f["plant_id"] == 123 for f in feedback)

        # Test 3: Plant-specific adjustment
        adjustment = predictor.get_adjustment_factor(123, feedback)
        assert 0.95 <= adjustment <= 1.05  # Mostly "just_right" feedback

        # Test 4: Final adjusted volume
        final_volume = volume * adjustment
        assert final_volume > 80  # Reasonable summer volume with adjustments

        print("\\n=== Phase 3 Complete Workflow ===")
        print("Season: Summer (July)")
        print(f"Seasonal factor: {seasonal_factor} (+15%)")
        print(f"Base volume: {volume:.1f}ml")
        print(f"Plant-specific adjustment: {adjustment:.2f}")
        print(f"Final volume: {final_volume:.1f}ml")
        print(f"Plant-specific feedback samples: {len(feedback)}")


class TestMoistureDeclineCalculations:
    """Detailed tests for moisture decline rate calculations."""

    def test_linear_regression_calculation(self):
        """Test linear regression math for decline rate."""
        # Setup
        mock_repo = Mock()
        # Perfect linear decline: -0.5%/hour (need 5+ samples)
        now = datetime.now()
        mock_repo.get_moisture_history.return_value = [
            {"soil_moisture": 52.5, "timestamp": (now - timedelta(hours=15)).isoformat()},
            {"soil_moisture": 51.25, "timestamp": (now - timedelta(hours=12)).isoformat()},
            {"soil_moisture": 50.0, "timestamp": (now - timedelta(hours=10)).isoformat()},
            {"soil_moisture": 47.5, "timestamp": (now - timedelta(hours=5)).isoformat()},
            {"soil_moisture": 45.0, "timestamp": now.isoformat()},
        ]

        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)

        # Execute
        prediction = predictor.predict_next_irrigation_time(
            plant_id=123, current_moisture=45.0, threshold=40.0, hours_lookback=24
        )

        # Verify
        assert prediction is not None
        assert abs(prediction.decline_rate_per_hour - (-0.5)) < 0.1  # ~-0.5%/hour
        assert abs(prediction.hours_until_threshold - 10.0) < 2.0  # ~10 hours

    def test_insufficient_data(self):
        """Test that insufficient data returns None."""
        # Setup
        mock_repo = Mock()
        # Only 2 samples (need 5+)
        now = datetime.now()
        mock_repo.get_moisture_history.return_value = [
            {"soil_moisture": 50.0, "timestamp": (now - timedelta(hours=5)).isoformat()},
            {"soil_moisture": 48.0, "timestamp": now.isoformat()},
        ]

        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)

        # Execute
        prediction = predictor.predict_next_irrigation_time(plant_id=123, current_moisture=48.0, threshold=40.0)

        # Verify returns None for insufficient data
        assert prediction is None

    def test_already_below_threshold(self):
        """Test prediction when moisture already below threshold."""
        # Setup
        mock_repo = Mock()
        now = datetime.now()
        mock_repo.get_moisture_history.return_value = [
            {"soil_moisture": 48.0, "timestamp": (now - timedelta(hours=12)).isoformat()},
            {"soil_moisture": 45.0, "timestamp": (now - timedelta(hours=10)).isoformat()},
            {"soil_moisture": 42.0, "timestamp": (now - timedelta(hours=5)).isoformat()},
            {"soil_moisture": 40.5, "timestamp": (now - timedelta(hours=2)).isoformat()},
            {"soil_moisture": 39.0, "timestamp": now.isoformat()},  # Below threshold of 40
        ]

        predictor = IrrigationPredictor(irrigation_ml_repo=mock_repo)

        # Execute
        prediction = predictor.predict_next_irrigation_time(plant_id=123, current_moisture=39.0, threshold=40.0)

        # Verify immediate irrigation
        assert prediction is not None
        assert prediction.hours_until_threshold == 0
        assert "already at or below threshold" in prediction.reasoning.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
