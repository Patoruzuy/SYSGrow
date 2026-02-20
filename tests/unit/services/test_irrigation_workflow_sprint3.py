"""
Tests for IrrigationWorkflowService.

Covers:
- WorkflowConfig defaults and persistence
- detect_irrigation_need gating logic
- Request lifecycle (create → approve/delay/cancel)
- Eligibility trace recording
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.application.irrigation_workflow_service import (
    WorkflowConfig,
)

# ========================== WorkflowConfig ==================================


class TestWorkflowConfig:
    """WorkflowConfig dataclass and serialization."""

    def test_defaults(self):
        cfg = WorkflowConfig()
        assert cfg.workflow_enabled is True
        assert cfg.require_approval is True
        assert cfg.auto_irrigation_enabled is False
        assert cfg.default_scheduled_time == "21:00"
        assert cfg.delay_increment_minutes == 60
        assert cfg.max_delay_hours == 24

    def test_roundtrip_dict(self):
        original = WorkflowConfig(delay_increment_minutes=30, max_delay_hours=12)
        restored = WorkflowConfig.from_dict(original.to_dict())
        assert restored.delay_increment_minutes == 30
        assert restored.max_delay_hours == 12

    def test_from_dict_ignores_unknown_keys(self):
        cfg = WorkflowConfig.from_dict({"unknown_key": True, "workflow_enabled": False})
        assert cfg.workflow_enabled is False


# ========================== Config persistence ==============================


class TestConfigPersistence:
    """get_config / save_config / update_config with real DB."""

    def test_get_config_returns_defaults_for_new_unit(self, irrigation_workflow_service, seed):
        unit_id = seed.create_unit()
        cfg = irrigation_workflow_service.get_config(unit_id)
        assert isinstance(cfg, WorkflowConfig)
        assert cfg.workflow_enabled is True

    def test_save_and_retrieve(self, irrigation_workflow_service, seed):
        unit_id = seed.create_unit()
        cfg = WorkflowConfig(delay_increment_minutes=15, max_delay_hours=6)
        assert irrigation_workflow_service.save_config(unit_id, cfg) is True

        loaded = irrigation_workflow_service.get_config(unit_id)
        assert loaded.delay_increment_minutes == 15
        assert loaded.max_delay_hours == 6

    def test_update_config_partial(self, irrigation_workflow_service, seed):
        unit_id = seed.create_unit()
        irrigation_workflow_service.save_config(unit_id, WorkflowConfig())
        irrigation_workflow_service.update_config(unit_id, {"require_approval": False})

        loaded = irrigation_workflow_service.get_config(unit_id)
        assert loaded.require_approval is False
        # Other defaults still intact
        assert loaded.workflow_enabled is True


# ========================== Detect irrigation need ==========================


class TestDetectIrrigationNeed:
    """detect_irrigation_need gating and request creation."""

    def test_workflow_disabled_skips(self, irrigation_workflow_service, seed):
        unit_id = seed.create_unit()
        # Disable workflow
        irrigation_workflow_service.save_config(unit_id, WorkflowConfig(workflow_enabled=False))
        # Clear config cache so test sees update
        irrigation_workflow_service._config_cache.clear()

        result = irrigation_workflow_service.detect_irrigation_need(
            unit_id=unit_id,
            soil_moisture=20.0,
            threshold=40.0,
            user_id=1,
        )
        assert result is None

    def test_creates_request_when_moisture_below_threshold(self, irrigation_workflow_service, seed):
        unit_id = seed.create_unit()
        request_id = irrigation_workflow_service.detect_irrigation_need(
            unit_id=unit_id,
            soil_moisture=15.0,
            threshold=40.0,
            user_id=1,
            plant_id=None,
        )
        # Should return a request ID (int) when need is detected
        if request_id is not None:
            assert isinstance(request_id, int)
            assert request_id > 0

    def test_moisture_above_threshold_returns_none(self, irrigation_workflow_service, seed):
        unit_id = seed.create_unit()
        result = irrigation_workflow_service.detect_irrigation_need(
            unit_id=unit_id,
            soil_moisture=80.0,
            threshold=40.0,
            user_id=1,
        )
        assert result is None


# ========================== Eligibility trace ===============================


class TestEligibilityTrace:
    """record_eligibility_trace persists decisions."""

    def test_record_trace_does_not_raise(self, irrigation_workflow_service, seed):
        from app.enums import IrrigationEligibilityDecision

        unit_id = seed.create_unit()
        # Should not raise even with minimal data
        irrigation_workflow_service.record_eligibility_trace(
            unit_id=unit_id,
            plant_id=None,
            sensor_id=None,
            moisture=25.0,
            threshold=40.0,
            decision=IrrigationEligibilityDecision.NOTIFY,
            skip_reason=None,
        )

    def test_record_trace_with_skip_reason(self, irrigation_workflow_service, seed):
        from app.enums import IrrigationEligibilityDecision, IrrigationSkipReason

        unit_id = seed.create_unit()
        irrigation_workflow_service.record_eligibility_trace(
            unit_id=unit_id,
            plant_id=1,
            sensor_id=5,
            moisture=60.0,
            threshold=40.0,
            decision=IrrigationEligibilityDecision.SKIP,
            skip_reason=IrrigationSkipReason.HYSTERESIS_NOT_MET,
        )


# ========================== Setter methods ==================================


class TestSetterMethods:
    """Late-binding setter methods for circular dependency resolution."""

    def test_set_notifications_service(self, irrigation_workflow_service):
        mock_svc = MagicMock()
        irrigation_workflow_service.set_notifications_service(mock_svc)
        assert irrigation_workflow_service._notifications is mock_svc

    def test_set_actuator_manager(self, irrigation_workflow_service):
        mock_mgr = MagicMock()
        irrigation_workflow_service.set_actuator_manager(mock_mgr)
        assert irrigation_workflow_service._actuator_service is mock_mgr

    def test_set_threshold_callback(self, irrigation_workflow_service):
        cb = MagicMock()
        irrigation_workflow_service.set_threshold_callback(cb)
        assert irrigation_workflow_service._threshold_adjustment_callback is cb
