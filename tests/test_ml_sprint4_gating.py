"""
Sprint 4: Metrics gating and retraining hardening tests.

Covers:
- IrrigationPredictor._passes_gate() per model type (pass / fail / missing metrics)
- IrrigationPredictor.get_model_status() / get_model_statuses() output shape
- AutomatedRetrainingService irrigation job setup
- MLReadinessMonitor MODEL_CONFIG completeness
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.services.ai.automated_retraining import AutomatedRetrainingService
from app.services.ai.irrigation_predictor import IrrigationPredictor
from app.services.ai.ml_readiness_monitor import MODEL_CONFIG

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_predictor(**bundles: dict) -> IrrigationPredictor:
    """Return a predictor whose _model_bundles is pre-populated."""
    predictor = IrrigationPredictor(irrigation_ml_repo=Mock())
    predictor._model_bundles = bundles
    return predictor


def _bundle_with_metrics(**metrics) -> dict:
    meta = Mock()
    meta.metrics = metrics
    meta.version = "v1"
    return {"model_name": "irrigation_test", "metadata": meta, "features": []}


# ---------------------------------------------------------------------------
# _passes_gate — response_predictor
# ---------------------------------------------------------------------------


class TestPassesGateResponsePredictor:
    MODEL = "response_predictor"

    def test_passes_when_both_thresholds_met(self):
        p = _make_predictor(response_predictor=_bundle_with_metrics(macro_f1=0.65, balanced_accuracy=0.60))
        passed, conf, metrics = p._passes_gate(self.MODEL)
        assert passed is True
        assert 0.0 <= conf <= 1.0
        assert "macro_f1" in metrics

    def test_fails_when_macro_f1_below_threshold(self):
        p = _make_predictor(response_predictor=_bundle_with_metrics(macro_f1=0.45, balanced_accuracy=0.60))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is False

    def test_fails_when_balanced_accuracy_below_threshold(self):
        p = _make_predictor(response_predictor=_bundle_with_metrics(macro_f1=0.70, balanced_accuracy=0.50))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is False

    def test_fails_when_metrics_missing(self):
        p = _make_predictor(response_predictor=_bundle_with_metrics())
        passed, conf, _ = p._passes_gate(self.MODEL)
        assert passed is False
        assert conf == 0.0

    def test_fails_when_no_bundle(self):
        p = _make_predictor()
        passed, conf, metrics = p._passes_gate(self.MODEL)
        assert passed is False
        assert conf == 0.0
        assert metrics == {}

    def test_exactly_at_threshold_passes(self):
        p = _make_predictor(response_predictor=_bundle_with_metrics(macro_f1=0.55, balanced_accuracy=0.55))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is True


# ---------------------------------------------------------------------------
# _passes_gate — timing_predictor
# ---------------------------------------------------------------------------


class TestPassesGateTimingPredictor:
    MODEL = "timing_predictor"

    def test_passes_when_both_thresholds_met(self):
        p = _make_predictor(timing_predictor=_bundle_with_metrics(top3_accuracy=0.75, mrr=0.62))
        passed, conf, _ = p._passes_gate(self.MODEL)
        assert passed is True
        assert conf == pytest.approx(0.75)

    def test_fails_when_top3_below_threshold(self):
        p = _make_predictor(timing_predictor=_bundle_with_metrics(top3_accuracy=0.55, mrr=0.65))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is False

    def test_fails_when_mrr_below_threshold(self):
        p = _make_predictor(timing_predictor=_bundle_with_metrics(top3_accuracy=0.70, mrr=0.50))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is False

    def test_fails_when_metrics_missing(self):
        p = _make_predictor(timing_predictor=_bundle_with_metrics(top3_accuracy=0.70))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is False

    def test_confidence_clamped_to_one(self):
        # top3_accuracy > 1.0 (bad data) should be clamped
        p = _make_predictor(timing_predictor=_bundle_with_metrics(top3_accuracy=1.5, mrr=0.80))
        _, conf, _ = p._passes_gate(self.MODEL)
        assert conf <= 1.0


# ---------------------------------------------------------------------------
# _passes_gate — threshold_optimizer
# ---------------------------------------------------------------------------


class TestPassesGateThresholdOptimizer:
    MODEL = "threshold_optimizer"

    def test_passes_via_mae_alone(self):
        p = _make_predictor(threshold_optimizer=_bundle_with_metrics(mae=3.5))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is True

    def test_passes_via_r2_alone(self):
        p = _make_predictor(threshold_optimizer=_bundle_with_metrics(test_score=0.60))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is True

    def test_fails_when_mae_too_high_and_r2_absent(self):
        p = _make_predictor(threshold_optimizer=_bundle_with_metrics(mae=10.0))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is False

    def test_fails_when_r2_too_low_and_mae_absent(self):
        p = _make_predictor(threshold_optimizer=_bundle_with_metrics(test_score=0.40))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is False

    def test_confidence_uses_r2_when_available(self):
        p = _make_predictor(threshold_optimizer=_bundle_with_metrics(test_score=0.75, mae=3.0))
        _, conf, _ = p._passes_gate(self.MODEL)
        assert conf == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# _passes_gate — duration_optimizer
# ---------------------------------------------------------------------------


class TestPassesGateDurationOptimizer:
    MODEL = "duration_optimizer"

    def test_passes_when_both_thresholds_met(self):
        p = _make_predictor(duration_optimizer=_bundle_with_metrics(mae=20.0, mape=0.30))
        passed, conf, _ = p._passes_gate(self.MODEL)
        assert passed is True
        assert conf == pytest.approx(0.70)

    def test_fails_when_mae_too_high(self):
        p = _make_predictor(duration_optimizer=_bundle_with_metrics(mae=30.0, mape=0.20))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is False

    def test_fails_when_mape_too_high(self):
        p = _make_predictor(duration_optimizer=_bundle_with_metrics(mae=15.0, mape=0.50))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is False

    def test_fails_when_mae_missing(self):
        p = _make_predictor(duration_optimizer=_bundle_with_metrics(mape=0.20))
        passed, conf, _ = p._passes_gate(self.MODEL)
        assert passed is False
        assert conf == 0.0

    def test_exactly_at_threshold_passes(self):
        p = _make_predictor(duration_optimizer=_bundle_with_metrics(mae=25.0, mape=0.40))
        passed, _, _ = p._passes_gate(self.MODEL)
        assert passed is True


# ---------------------------------------------------------------------------
# get_model_status / get_model_statuses
# ---------------------------------------------------------------------------


class TestGetModelStatus:
    KNOWN_KEYS = {"threshold_optimizer", "response_predictor", "duration_optimizer", "timing_predictor"}

    def test_status_contains_required_keys(self):
        p = IrrigationPredictor(irrigation_ml_repo=Mock())
        status = p.get_model_status("response_predictor")
        assert "model_key" in status
        assert "model_name" in status
        assert "ml_ready" in status
        assert "gating_metrics" in status
        assert isinstance(status["ml_ready"], bool)

    def test_status_ml_ready_false_when_no_model(self):
        p = IrrigationPredictor(irrigation_ml_repo=Mock())
        status = p.get_model_status("response_predictor")
        assert status["ml_ready"] is False

    def test_status_ml_ready_true_when_metrics_pass(self):
        p = _make_predictor(response_predictor=_bundle_with_metrics(macro_f1=0.70, balanced_accuracy=0.65))
        status = p.get_model_status("response_predictor")
        assert status["ml_ready"] is True

    def test_get_model_statuses_returns_all_four_keys(self):
        p = IrrigationPredictor(irrigation_ml_repo=Mock())
        statuses = p.get_model_statuses()
        assert set(statuses.keys()) == self.KNOWN_KEYS

    def test_get_model_statuses_filters_to_requested_keys(self):
        p = IrrigationPredictor(irrigation_ml_repo=Mock())
        statuses = p.get_model_statuses(["response_predictor", "timing_predictor"])
        assert set(statuses.keys()) == {"response_predictor", "timing_predictor"}

    def test_get_model_statuses_ignores_unknown_keys(self):
        p = IrrigationPredictor(irrigation_ml_repo=Mock())
        statuses = p.get_model_statuses(["response_predictor", "nonexistent_model"])
        assert "nonexistent_model" not in statuses
        assert "response_predictor" in statuses

    def test_model_version_exposed_in_status(self):
        p = _make_predictor(response_predictor=_bundle_with_metrics(macro_f1=0.70, balanced_accuracy=0.65))
        status = p.get_model_status("response_predictor")
        assert "model_version" in status
        assert status["model_version"] == "v1"


# ---------------------------------------------------------------------------
# AutomatedRetrainingService job setup
# ---------------------------------------------------------------------------


class TestIrrigationRetrainingJobSetup:
    def _make_service(self) -> AutomatedRetrainingService:
        return AutomatedRetrainingService(
            model_registry=Mock(),
            drift_detector=Mock(),
            ml_trainer=Mock(),
        )

    def test_setup_registers_four_irrigation_jobs(self):
        svc = self._make_service()
        svc.setup_irrigation_retraining_jobs()
        jobs = svc.get_jobs()
        model_types = {j.model_type for j in jobs}
        assert "irrigation_threshold" in model_types
        assert "irrigation_response" in model_types
        assert "irrigation_duration" in model_types
        assert "irrigation_timing" in model_types

    def test_all_jobs_enabled_by_default(self):
        svc = self._make_service()
        svc.setup_irrigation_retraining_jobs()
        assert all(j.enabled for j in svc.get_jobs())

    def test_threshold_job_is_weekly(self):
        svc = self._make_service()
        svc.setup_irrigation_retraining_jobs()
        job = next(j for j in svc.get_jobs() if j.model_type == "irrigation_threshold")
        assert job.schedule_type == "weekly"

    def test_duration_job_is_monthly(self):
        svc = self._make_service()
        svc.setup_irrigation_retraining_jobs()
        job = next(j for j in svc.get_jobs() if j.model_type == "irrigation_duration")
        assert job.schedule_type == "monthly"

    def test_min_samples_set_per_job(self):
        svc = self._make_service()
        svc.setup_irrigation_retraining_jobs()
        threshold_job = next(j for j in svc.get_jobs() if j.model_type == "irrigation_threshold")
        response_job = next(j for j in svc.get_jobs() if j.model_type == "irrigation_response")
        assert threshold_job.min_samples == 30
        assert response_job.min_samples == 20

    def test_get_status_shape(self):
        svc = self._make_service()
        svc.setup_irrigation_retraining_jobs()
        status = svc.get_status()
        assert "total_jobs" in status
        assert "enabled_jobs" in status
        assert status["total_jobs"] == 4
        assert status["enabled_jobs"] == 4


# ---------------------------------------------------------------------------
# MLReadinessMonitor MODEL_CONFIG completeness
# ---------------------------------------------------------------------------


class TestModelReadinessConfig:
    EXPECTED_MODELS = {"response_predictor", "threshold_optimizer", "duration_optimizer", "timing_predictor"}
    REQUIRED_FIELDS = {"display_name", "required_samples", "description", "benefits"}

    def test_all_four_models_configured(self):
        assert set(MODEL_CONFIG.keys()) == self.EXPECTED_MODELS

    def test_each_model_has_required_fields(self):
        for model_key, config in MODEL_CONFIG.items():
            missing = self.REQUIRED_FIELDS - set(config.keys())
            assert not missing, f"{model_key} missing fields: {missing}"

    def test_required_samples_are_positive_integers(self):
        for model_key, config in MODEL_CONFIG.items():
            samples = config["required_samples"]
            assert isinstance(samples, int) and samples > 0, f"{model_key}.required_samples invalid: {samples}"

    def test_benefits_is_non_empty_list(self):
        for model_key, config in MODEL_CONFIG.items():
            benefits = config["benefits"]
            assert isinstance(benefits, list) and len(benefits) > 0, f"{model_key}.benefits is empty"


# ---------------------------------------------------------------------------
# Auto-suspend after consecutive failures
# ---------------------------------------------------------------------------


class TestAutoSuspendOnConsecutiveFailures:
    def _make_service(self) -> AutomatedRetrainingService:
        return AutomatedRetrainingService(
            model_registry=Mock(),
            drift_detector=Mock(),
            ml_trainer=Mock(),
        )

    def test_job_disabled_after_max_consecutive_failures(self):
        svc = self._make_service()
        svc.setup_irrigation_retraining_jobs()
        job = next(j for j in svc.get_jobs() if j.model_type == "irrigation_threshold")

        # Simulate MAX_CONSECUTIVE_FAILURES failures
        from app.services.ai.automated_retraining import MAX_CONSECUTIVE_FAILURES

        for _ in range(MAX_CONSECUTIVE_FAILURES):
            svc._record_job_failure(job)

        assert job.enabled is False, "Job should be disabled after too many consecutive failures"

    def test_job_consecutive_failures_reset_on_success(self):
        svc = self._make_service()
        svc.setup_irrigation_retraining_jobs()
        job = next(j for j in svc.get_jobs() if j.model_type == "irrigation_threshold")

        from app.services.ai.automated_retraining import MAX_CONSECUTIVE_FAILURES

        # Fail a few times (below threshold)
        for _ in range(MAX_CONSECUTIVE_FAILURES - 1):
            svc._record_job_failure(job)

        assert job.enabled is True

        # One success resets
        svc._record_job_success(job)
        assert job.consecutive_failures == 0

    def test_job_still_enabled_below_threshold(self):
        svc = self._make_service()
        svc.setup_irrigation_retraining_jobs()
        job = next(j for j in svc.get_jobs() if j.model_type == "irrigation_response")

        from app.services.ai.automated_retraining import MAX_CONSECUTIVE_FAILURES

        for _ in range(MAX_CONSECUTIVE_FAILURES - 1):
            svc._record_job_failure(job)

        assert job.enabled is True
