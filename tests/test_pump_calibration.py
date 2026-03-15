"""
Pump Calibration Service Tests
==============================
Tests for PumpCalibrationService.
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

from app.services.hardware.pump_calibration import (
    PumpCalibrationService,
    CalibrationSession,
    CalibrationResult,
    PumpCalibrationData,
)
from app.constants import PUMP_CALIBRATION_DEFAULTS


@pytest.fixture
def mock_actuator_manager():
    """Create mock ActuatorManager."""
    manager = Mock()
    manager.turn_on.return_value = True
    manager.turn_off.return_value = True
    return manager


@pytest.fixture
def mock_device_repo():
    """Create mock DeviceRepository."""
    repo = Mock()
    repo.get_actuator_config_by_id.return_value = {
        "actuator_id": 1,
        "actuator_type": "pump",
        "unit_id": 1,
        "config_data": "{}",
    }
    repo.update_actuator_config.return_value = True
    return repo


@pytest.fixture
def service(mock_actuator_manager, mock_device_repo):
    """Create PumpCalibrationService with mocked dependencies."""
    return PumpCalibrationService(mock_actuator_manager, mock_device_repo)


class TestIsPump:
    """Tests for is_pump method."""

    def test_recognizes_pump_type(self, service):
        """Test recognition of pump type."""
        assert service.is_pump("pump") is True

    def test_case_insensitive(self, service):
        """Test case insensitivity."""
        assert service.is_pump("PUMP") is True
        assert service.is_pump("Pump") is True
        assert service.is_pump("PuMp") is True

    def test_rejects_non_pump_types(self, service):
        """Test rejection of non-pump actuator types."""
        assert service.is_pump("light") is False
        assert service.is_pump("fan") is False
        assert service.is_pump("heater") is False
        assert service.is_pump("relay") is False
        # Note: water-pump, water_pump are separate types (not handled by is_pump)
        assert service.is_pump("water-pump") is False
        assert service.is_pump("water_pump") is False


class TestStartCalibration:
    """Tests for start_calibration method."""

    def test_successful_start(self, service, mock_actuator_manager):
        """Test successful calibration start."""
        result = service.start_calibration(actuator_id=1)
        
        assert result["ok"] is True
        assert result["actuator_id"] == 1
        assert result["status"] == "awaiting_measurement"
        assert "duration_seconds" in result
        mock_actuator_manager.turn_on.assert_called_once()

    def test_uses_default_duration(self, service, mock_actuator_manager):
        """Test that default duration is used when not specified."""
        result = service.start_calibration(actuator_id=1)
        
        default_duration = PUMP_CALIBRATION_DEFAULTS["calibration_duration_seconds"]
        assert result["duration_seconds"] == default_duration
        mock_actuator_manager.turn_on.assert_called_with(1, duration_seconds=default_duration)

    def test_custom_duration(self, service, mock_actuator_manager):
        """Test using custom duration."""
        result = service.start_calibration(actuator_id=1, duration_seconds=60)
        
        assert result["duration_seconds"] == 60
        mock_actuator_manager.turn_on.assert_called_with(1, duration_seconds=60)

    def test_actuator_not_found(self, service, mock_device_repo):
        """Test handling of non-existent actuator."""
        mock_device_repo.get_actuator_config_by_id.return_value = None
        
        result = service.start_calibration(actuator_id=999)
        
        assert result["ok"] is False
        assert "not found" in result["error"].lower()

    def test_non_pump_actuator(self, service, mock_device_repo):
        """Test rejection of non-pump actuator."""
        mock_device_repo.get_actuator_config_by_id.return_value = {
            "actuator_id": 1,
            "actuator_type": "light",
        }
        
        result = service.start_calibration(actuator_id=1)
        
        assert result["ok"] is False
        assert "not a pump" in result["error"].lower()

    def test_pump_activation_failure(self, service, mock_actuator_manager):
        """Test handling of pump activation failure."""
        mock_actuator_manager.turn_on.return_value = False
        
        result = service.start_calibration(actuator_id=1)
        
        assert result["ok"] is False
        assert "failed" in result["error"].lower()

    def test_existing_session_awaiting_measurement(self, service):
        """Test handling of existing calibration session awaiting measurement."""
        # Start first session - this creates an "awaiting_measurement" session
        service.start_calibration(actuator_id=1)
        
        # Try to start second session - should be blocked until existing is completed/cancelled
        result = service.start_calibration(actuator_id=1)
        
        assert result["ok"] is False
        assert "already in progress" in result["error"].lower()


class TestCompleteCalibration:
    """Tests for complete_calibration method."""

    def test_successful_completion(self, service, mock_device_repo):
        """Test successful calibration completion."""
        # Start calibration first
        service.start_calibration(actuator_id=1, duration_seconds=30)
        
        # Complete with measurement
        result = service.complete_calibration(actuator_id=1, measured_ml=100.0)
        
        assert isinstance(result, CalibrationResult)
        assert result.actuator_id == 1
        assert result.measured_volume_ml == 100.0
        assert result.flow_rate_ml_per_second == pytest.approx(100.0 / 30)
        assert result.confidence == 1.0

    def test_flow_rate_calculation(self, service):
        """Test accurate flow rate calculation."""
        service.start_calibration(actuator_id=1, duration_seconds=20)
        result = service.complete_calibration(actuator_id=1, measured_ml=50.0)
        
        # 50ml / 20s = 2.5 ml/s
        assert result.flow_rate_ml_per_second == 2.5

    def test_no_active_session_raises(self, service):
        """Test that completing without session raises error."""
        with pytest.raises(ValueError, match="No active calibration session"):
            service.complete_calibration(actuator_id=999, measured_ml=100.0)

    def test_zero_measured_volume_raises(self, service):
        """Test that zero measurement raises error."""
        service.start_calibration(actuator_id=1)
        
        with pytest.raises(ValueError, match="positive"):
            service.complete_calibration(actuator_id=1, measured_ml=0.0)

    def test_negative_measured_volume_raises(self, service):
        """Test that negative measurement raises error."""
        service.start_calibration(actuator_id=1)
        
        with pytest.raises(ValueError, match="positive"):
            service.complete_calibration(actuator_id=1, measured_ml=-50.0)

    def test_session_cleared_after_completion(self, service):
        """Test that session is cleared after completion."""
        service.start_calibration(actuator_id=1)
        service.complete_calibration(actuator_id=1, measured_ml=100.0)
        
        # Should be able to start new session
        result = service.start_calibration(actuator_id=1)
        assert result["ok"] is True


class TestCancelCalibration:
    """Tests for cancel_calibration method."""

    def test_successful_cancellation(self, service, mock_actuator_manager):
        """Test successful calibration cancellation."""
        service.start_calibration(actuator_id=1)
        
        result = service.cancel_calibration(actuator_id=1)
        
        assert result["ok"] is True
        mock_actuator_manager.turn_off.assert_called_with(1)

    def test_no_session_to_cancel(self, service):
        """Test cancelling non-existent session."""
        result = service.cancel_calibration(actuator_id=999)
        
        assert result["ok"] is False
        assert "no active session" in result["error"].lower()

    def test_session_cleared_after_cancellation(self, service):
        """Test that session is cleared after cancellation."""
        service.start_calibration(actuator_id=1)
        service.cancel_calibration(actuator_id=1)
        
        # Should be able to start new session
        result = service.start_calibration(actuator_id=1)
        assert result["ok"] is True


class TestAdjustFromFeedback:
    """Tests for adjust_from_feedback method."""

    def test_too_little_decreases_rate(self, service, mock_device_repo):
        """Test that 'too_little' feedback decreases flow rate."""
        # Set up existing calibration - use 'config' not 'config_data'
        mock_device_repo.get_actuator_config_by_id.return_value = {
            "actuator_id": 1,
            "actuator_type": "pump",
            "config": {"flow_rate_ml_per_second": 3.0, "calibration_confidence": 1.0},
        }
        mock_device_repo._backend = Mock()
        mock_device_repo._backend.update_actuator_config.return_value = True
        
        new_rate = service.adjust_from_feedback(actuator_id=1, feedback="too_little")
        
        # 3.0 * (1 - 0.05) = 2.85
        assert new_rate == pytest.approx(2.85)

    def test_too_much_increases_rate(self, service, mock_device_repo):
        """Test that 'too_much' feedback increases flow rate."""
        mock_device_repo.get_actuator_config_by_id.return_value = {
            "actuator_id": 1,
            "actuator_type": "pump",
            "config": {"flow_rate_ml_per_second": 3.0, "calibration_confidence": 1.0},
        }
        mock_device_repo._backend = Mock()
        mock_device_repo._backend.update_actuator_config.return_value = True
        
        new_rate = service.adjust_from_feedback(actuator_id=1, feedback="too_much")
        
        # 3.0 * (1 + 0.05) = 3.15
        assert new_rate == pytest.approx(3.15)

    def test_just_right_no_change(self, service, mock_device_repo):
        """Test that 'just_right' feedback doesn't change rate."""
        mock_device_repo.get_actuator_config_by_id.return_value = {
            "actuator_id": 1,
            "actuator_type": "pump",
            "config": {"flow_rate_ml_per_second": 3.0, "calibration_confidence": 1.0},
        }
        
        new_rate = service.adjust_from_feedback(actuator_id=1, feedback="just_right")
        
        assert new_rate == 3.0

    def test_custom_adjustment_factor(self, service, mock_device_repo):
        """Test using custom adjustment factor."""
        mock_device_repo.get_actuator_config_by_id.return_value = {
            "actuator_id": 1,
            "actuator_type": "pump",
            "config": {"flow_rate_ml_per_second": 3.0, "calibration_confidence": 1.0},
        }
        mock_device_repo._backend = Mock()
        mock_device_repo._backend.update_actuator_config.return_value = True
        
        new_rate = service.adjust_from_feedback(
            actuator_id=1, 
            feedback="too_little", 
            adjustment_factor=0.10
        )
        
        # 3.0 * (1 - 0.10) = 2.7
        assert new_rate == pytest.approx(2.7)

    def test_uncalibrated_pump_returns_none(self, service, mock_device_repo):
        """Test that uncalibrated pump returns None."""
        mock_device_repo.get_actuator_config_by_id.return_value = {
            "actuator_id": 1,
            "actuator_type": "pump",
            "config": {},  # No calibration data
        }
        
        new_rate = service.adjust_from_feedback(actuator_id=1, feedback="too_little")
        
        assert new_rate is None

    def test_non_existent_actuator_returns_none(self, service, mock_device_repo):
        """Test handling of non-existent actuator."""
        mock_device_repo.get_actuator_config_by_id.return_value = None
        
        new_rate = service.adjust_from_feedback(actuator_id=999, feedback="too_little")
        
        assert new_rate is None


class TestGetFlowRate:
    """Tests for get_flow_rate method."""

    def test_returns_calibrated_rate(self, service, mock_device_repo):
        """Test retrieving calibrated flow rate."""
        mock_device_repo.get_actuator_config_by_id.return_value = {
            "actuator_id": 1,
            "config": {"flow_rate_ml_per_second": 3.5},
        }
        
        rate = service.get_flow_rate(actuator_id=1)
        
        assert rate == 3.5

    def test_uncalibrated_returns_none(self, service, mock_device_repo):
        """Test that uncalibrated pump returns None."""
        mock_device_repo.get_actuator_config_by_id.return_value = {
            "actuator_id": 1,
            "config": {},
        }
        
        rate = service.get_flow_rate(actuator_id=1)
        
        assert rate is None

    def test_non_existent_actuator_returns_none(self, service, mock_device_repo):
        """Test handling of non-existent actuator."""
        mock_device_repo.get_actuator_config_by_id.return_value = None
        
        rate = service.get_flow_rate(actuator_id=999)
        
        assert rate is None


class TestPumpCalibrationDataDataclass:
    """Tests for PumpCalibrationData dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        data = PumpCalibrationData(
            flow_rate_ml_per_second=3.5,
            calibration_volume_ml=105.0,
            calibration_duration_seconds=30,
            calibrated_at="2026-01-14T10:00:00Z",
            calibration_confidence=0.9,
            last_feedback_adjustment="2026-01-14T11:00:00Z",
            feedback_adjustments_count=2,
        )
        
        result = data.to_dict()
        
        assert result["flow_rate_ml_per_second"] == 3.5
        assert result["calibration_volume_ml"] == 105.0
        assert result["calibration_duration_seconds"] == 30
        assert result["calibration_confidence"] == 0.9
        assert result["feedback_adjustments_count"] == 2

    def test_from_dict(self):
        """Test creation from dictionary."""
        source = {
            "flow_rate_ml_per_second": 3.5,
            "calibration_volume_ml": 105.0,
            "calibration_duration_seconds": 30,
            "calibrated_at": "2026-01-14T10:00:00Z",
            "calibration_confidence": 0.9,
        }
        
        data = PumpCalibrationData.from_dict(source)
        
        assert data.flow_rate_ml_per_second == 3.5
        assert data.calibration_volume_ml == 105.0
        assert data.calibration_confidence == 0.9

    def test_from_dict_with_defaults(self):
        """Test creation from partial dictionary uses defaults."""
        data = PumpCalibrationData.from_dict({})
        
        assert data.flow_rate_ml_per_second == 0
        assert data.calibration_confidence == 1.0
        assert data.feedback_adjustments_count == 0


class TestCalibrationResultDataclass:
    """Tests for CalibrationResult dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = CalibrationResult(
            actuator_id=1,
            flow_rate_ml_per_second=3.333,
            measured_volume_ml=100.0,
            duration_seconds=30.0,
            calibrated_at="2026-01-14T10:00:00Z",
            confidence=1.0,
        )
        
        d = result.to_dict()
        
        assert d["actuator_id"] == 1
        assert d["flow_rate_ml_per_second"] == 3.333
        assert d["measured_volume_ml"] == 100.0
        assert d["confidence"] == 1.0


class TestIntegration:
    """Integration tests for full calibration workflow."""

    def test_full_calibration_workflow(self, service, mock_device_repo):
        """Test complete calibration workflow."""
        # Set up mock for update
        mock_device_repo._backend = Mock()
        mock_device_repo._backend.update_actuator_config.return_value = True
        
        # Step 1: Start calibration
        start_result = service.start_calibration(actuator_id=1, duration_seconds=30)
        assert start_result["ok"] is True
        
        # Step 2: Complete calibration
        calibration = service.complete_calibration(actuator_id=1, measured_ml=100.0)
        assert calibration.flow_rate_ml_per_second == pytest.approx(100.0 / 30)
        
        # Step 3: Verify stored
        mock_device_repo._backend.update_actuator_config.assert_called()

    def test_calibration_then_adjustment(self, service, mock_device_repo):
        """Test calibration followed by feedback adjustment."""
        # Set up mock
        mock_device_repo._backend = Mock()
        mock_device_repo._backend.update_actuator_config.return_value = True
        
        # Start and complete calibration
        service.start_calibration(actuator_id=1, duration_seconds=30)
        service.complete_calibration(actuator_id=1, measured_ml=100.0)
        
        # Set up return value with calibration data (use 'config' dict not JSON string)
        mock_device_repo.get_actuator_config_by_id.return_value = {
            "actuator_id": 1,
            "actuator_type": "pump",
            "config": {"flow_rate_ml_per_second": 3.333, "calibration_confidence": 1.0},
        }
        
        # Adjust from feedback
        new_rate = service.adjust_from_feedback(actuator_id=1, feedback="too_little")
        
        # Should decrease by 5%
        expected = 3.333 * 0.95
        assert new_rate == pytest.approx(expected, rel=0.01)


class TestCalibrationHistoryTracking:
    """Tests for calibration history tracking."""

    def test_history_added_on_calibration(self, service, mock_device_repo):
        """Test that history entry is added on calibration."""
        from app.services.hardware.pump_calibration import PumpCalibrationData
        
        mock_device_repo._backend = Mock()
        mock_device_repo._backend.update_actuator_config.return_value = True
        
        service.start_calibration(actuator_id=1, duration_seconds=30)
        calibration = service.complete_calibration(actuator_id=1, measured_ml=100.0)
        
        # Check that update was called with history
        call_args = mock_device_repo._backend.update_actuator_config.call_args
        # Arguments are (actuator_id, config_data)
        config_data = call_args[0][1]  # Second positional argument
        
        # Should have history entry
        assert "calibration_history" in config_data
        assert len(config_data["calibration_history"]) == 1
        assert config_data["calibration_history"][0]["method"] == "manual"

    def test_history_added_on_feedback_adjustment(self, service, mock_device_repo):
        """Test that history entry is added on feedback adjustment."""
        mock_device_repo._backend = Mock()
        mock_device_repo._backend.update_actuator_config.return_value = True
        
        # Set up existing calibration
        mock_device_repo.get_actuator_config_by_id.return_value = {
            "actuator_id": 1,
            "actuator_type": "pump",
            "config": {
                "flow_rate_ml_per_second": 3.333,
                "calibration_confidence": 1.0,
                "calibration_history": [],
            },
        }
        
        service.adjust_from_feedback(actuator_id=1, feedback="too_little")
        
        # Check that update was called with new history entry
        call_args = mock_device_repo._backend.update_actuator_config.call_args
        # Arguments are (actuator_id, config_data)
        config_data = call_args[0][1]  # Second positional argument
        
        assert "calibration_history" in config_data
        assert len(config_data["calibration_history"]) == 1
        assert "feedback_adjustment" in config_data["calibration_history"][0]["method"]


class TestPumpCalibrationDataHistory:
    """Tests for PumpCalibrationData history methods."""

    def test_add_history_entry(self):
        """Test adding history entries."""
        from app.services.hardware.pump_calibration import PumpCalibrationData, CalibrationHistoryEntry
        
        data = PumpCalibrationData(
            flow_rate_ml_per_second=3.0,
            calibration_volume_ml=100.0,
            calibration_duration_seconds=30,
            calibrated_at="2026-01-01T00:00:00Z",
        )
        
        entry = CalibrationHistoryEntry(
            flow_rate_ml_per_second=3.0,
            measured_volume_ml=100.0,
            duration_seconds=30,
            calibrated_at="2026-01-01T00:00:00Z",
            confidence=1.0,
            method="manual",
        )
        
        data.add_history_entry(entry)
        
        assert len(data.calibration_history) == 1
        assert data.calibration_history[0]["flow_rate_ml_per_second"] == 3.0

    def test_history_max_entries(self):
        """Test that history is limited to max entries."""
        from app.services.hardware.pump_calibration import PumpCalibrationData, CalibrationHistoryEntry
        
        data = PumpCalibrationData(
            flow_rate_ml_per_second=3.0,
            calibration_volume_ml=100.0,
            calibration_duration_seconds=30,
            calibrated_at="2026-01-01T00:00:00Z",
        )
        
        # Add 15 entries (more than default max of 10)
        for i in range(15):
            entry = CalibrationHistoryEntry(
                flow_rate_ml_per_second=3.0 + i * 0.1,
                measured_volume_ml=100.0,
                duration_seconds=30,
                calibrated_at=f"2026-01-{i+1:02d}T00:00:00Z",
                confidence=1.0,
                method="manual",
            )
            data.add_history_entry(entry, max_entries=10)
        
        # Should only have 10 entries
        assert len(data.calibration_history) == 10
        # Most recent should be at index 0
        assert data.calibration_history[0]["flow_rate_ml_per_second"] == pytest.approx(3.0 + 14 * 0.1)

    def test_get_flow_rate_trend_stable(self):
        """Test trend analysis with stable flow rates."""
        from app.services.hardware.pump_calibration import PumpCalibrationData
        
        history = [
            {"flow_rate_ml_per_second": 3.0, "calibrated_at": "2026-01-03T00:00:00Z"},
            {"flow_rate_ml_per_second": 3.0, "calibrated_at": "2026-01-02T00:00:00Z"},
            {"flow_rate_ml_per_second": 3.0, "calibrated_at": "2026-01-01T00:00:00Z"},
        ]
        
        data = PumpCalibrationData(
            flow_rate_ml_per_second=3.0,
            calibration_volume_ml=100.0,
            calibration_duration_seconds=30,
            calibrated_at="2026-01-03T00:00:00Z",
            calibration_history=history,
        )
        
        trend = data.get_flow_rate_trend()
        
        assert trend is not None
        assert trend["trend"] == "stable"
        assert trend["consistency"] == "consistent"
        assert trend["current_rate"] == 3.0
        assert trend["average_rate"] == 3.0

    def test_get_flow_rate_trend_increasing(self):
        """Test trend analysis with increasing flow rates."""
        from app.services.hardware.pump_calibration import PumpCalibrationData
        
        history = [
            {"flow_rate_ml_per_second": 3.5, "calibrated_at": "2026-01-03T00:00:00Z"},
            {"flow_rate_ml_per_second": 3.2, "calibrated_at": "2026-01-02T00:00:00Z"},
            {"flow_rate_ml_per_second": 3.0, "calibrated_at": "2026-01-01T00:00:00Z"},
        ]
        
        data = PumpCalibrationData(
            flow_rate_ml_per_second=3.5,
            calibration_volume_ml=100.0,
            calibration_duration_seconds=30,
            calibrated_at="2026-01-03T00:00:00Z",
            calibration_history=history,
        )
        
        trend = data.get_flow_rate_trend()
        
        assert trend is not None
        assert trend["trend"] == "increasing"
        assert trend["current_rate"] == 3.5
        assert trend["oldest_rate"] == 3.0
        assert trend["rate_change_percent"] > 0

    def test_get_flow_rate_trend_insufficient_data(self):
        """Test trend analysis with insufficient data."""
        from app.services.hardware.pump_calibration import PumpCalibrationData
        
        data = PumpCalibrationData(
            flow_rate_ml_per_second=3.0,
            calibration_volume_ml=100.0,
            calibration_duration_seconds=30,
            calibrated_at="2026-01-01T00:00:00Z",
            calibration_history=[{"flow_rate_ml_per_second": 3.0}],  # Only 1 entry
        )
        
        trend = data.get_flow_rate_trend()
        
        assert trend is None  # Need at least 2 entries

    def test_get_flow_rate_trend_zero_average(self):
        """Test trend analysis when average flow rate is zero."""
        from app.services.hardware.pump_calibration import PumpCalibrationData

        history = [
            {"flow_rate_ml_per_second": 0.0, "calibrated_at": "2026-01-03T00:00:00Z"},
            {"flow_rate_ml_per_second": 0.0, "calibrated_at": "2026-01-02T00:00:00Z"},
        ]

        data = PumpCalibrationData(
            flow_rate_ml_per_second=0.0,
            calibration_volume_ml=0.0,
            calibration_duration_seconds=30,
            calibrated_at="2026-01-03T00:00:00Z",
            calibration_history=history,
        )

        trend = data.get_flow_rate_trend()

        assert trend is not None
        assert trend["consistency"] == "unknown"


class TestCalibrationHistoryEntryDataclass:
    """Tests for CalibrationHistoryEntry dataclass."""

    def test_to_dict(self):
        """Test to_dict conversion."""
        from app.services.hardware.pump_calibration import CalibrationHistoryEntry
        
        entry = CalibrationHistoryEntry(
            flow_rate_ml_per_second=3.333,
            measured_volume_ml=100.5,
            duration_seconds=30.0,
            calibrated_at="2026-01-01T00:00:00Z",
            confidence=0.95,
            method="manual",
        )
        
        d = entry.to_dict()
        
        assert d["flow_rate_ml_per_second"] == 3.333
        assert d["measured_volume_ml"] == 100.5
        assert d["duration_seconds"] == 30.0
        assert d["method"] == "manual"

    def test_from_dict(self):
        """Test from_dict conversion."""
        from app.services.hardware.pump_calibration import CalibrationHistoryEntry
        
        d = {
            "flow_rate_ml_per_second": 3.333,
            "measured_volume_ml": 100.5,
            "duration_seconds": 30.0,
            "calibrated_at": "2026-01-01T00:00:00Z",
            "confidence": 0.95,
            "method": "feedback_adjustment_too_little",
        }
        
        entry = CalibrationHistoryEntry.from_dict(d)
        
        assert entry.flow_rate_ml_per_second == 3.333
        assert entry.method == "feedback_adjustment_too_little"
