"""Tests for no-fallback behavior when irrigation ML gating fails."""

from unittest.mock import Mock

from app.services.ai.irrigation_predictor import IrrigationPredictor


def _predictor_no_fallback() -> IrrigationPredictor:
    repo = Mock()
    repo.get_training_data_for_model.side_effect = AssertionError("No fallback expected")
    return IrrigationPredictor(irrigation_ml_repo=repo)


def test_threshold_no_fallback_when_ml_not_ready():
    predictor = _predictor_no_fallback()
    prediction = predictor.predict_threshold(
        unit_id=1,
        plant_type="tomato",
        growth_stage="Vegetative",
        current_threshold=45.0,
        feature_context=None,
    )

    assert prediction.confidence == 0.0
    assert prediction.optimal_threshold == 45.0
    assert prediction.adjustment_amount == 0.0
    assert prediction.adjustment_direction == "maintain"


def test_response_no_fallback_when_ml_not_ready():
    predictor = _predictor_no_fallback()
    prediction = predictor.predict_user_response(
        unit_id=1,
        current_moisture=40.0,
        threshold=50.0,
        hour_of_day=10,
        day_of_week=2,
        feature_context=None,
    )

    assert prediction.confidence == 0.0
    assert prediction.approve_probability == 0.0
    assert prediction.delay_probability == 0.0
    assert prediction.cancel_probability == 0.0
    assert prediction.most_likely == "approve"


def test_duration_no_fallback_when_ml_not_ready():
    predictor = _predictor_no_fallback()
    prediction = predictor.predict_duration(
        unit_id=1,
        current_moisture=40.0,
        target_moisture=55.0,
        current_default_seconds=120,
        feature_context=None,
    )

    assert prediction.confidence == 0.0
    assert prediction.recommended_seconds == 120
    assert prediction.current_default_seconds == 120
    assert prediction.expected_moisture_increase == 15.0


def test_timing_no_fallback_when_ml_not_ready():
    predictor = _predictor_no_fallback()
    prediction = predictor.predict_timing(
        unit_id=1,
        day_of_week=2,
        feature_context=None,
    )

    assert prediction.confidence == 0.0
    assert prediction.preferred_time == "00:00"
    assert prediction.preferred_hour == 0
    assert prediction.avoid_times == []
