"""
Pump Calibration Service
========================
Handles pump flow rate calibration through timed water collection.

The calibration flow:
1. User clicks "Start Calibration" in UI
2. System runs pump for fixed duration (e.g., 30 seconds)
3. User measures collected water volume
4. User enters measured_ml in UI
5. System calculates flow_rate = measured_ml / duration
6. Flow rate stored in actuator config_data

ML Refinement:
- When user gives feedback (too_little/too_much), system adjusts flow_rate
- Feedback adjusts by small increments (±5%) to converge on true rate
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.constants import PUMP_CALIBRATION_DEFAULTS
from app.enums.device import ActuatorType
from app.utils.time import iso_now, utc_now

if TYPE_CHECKING:
    from app.services.hardware.actuator_management_service import ActuatorManagementService
    from infrastructure.database.repositories.devices import DeviceRepository

# Type alias for backwards compatibility
ActuatorManager = "ActuatorManagementService"

logger = logging.getLogger(__name__)


@dataclass
class CalibrationSession:
    """Active calibration session."""

    actuator_id: int
    start_time: datetime
    target_duration_seconds: int
    status: str  # "running", "awaiting_measurement", "completed", "cancelled"
    unit_id: int | None = None


@dataclass
class CalibrationResult:
    """Result of pump calibration."""

    actuator_id: int
    flow_rate_ml_per_second: float
    measured_volume_ml: float
    duration_seconds: float
    calibrated_at: str
    confidence: float  # 1.0 for manual, adjusted by ML feedback

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "actuator_id": self.actuator_id,
            "flow_rate_ml_per_second": round(self.flow_rate_ml_per_second, 3),
            "measured_volume_ml": round(self.measured_volume_ml, 1),
            "duration_seconds": round(self.duration_seconds, 1),
            "calibrated_at": self.calibrated_at,
            "confidence": round(self.confidence, 2),
        }


@dataclass
class CalibrationHistoryEntry:
    """Single entry in calibration history."""

    flow_rate_ml_per_second: float
    measured_volume_ml: float
    duration_seconds: float
    calibrated_at: str
    confidence: float
    method: str  # "manual", "feedback_adjustment"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "flow_rate_ml_per_second": round(self.flow_rate_ml_per_second, 3),
            "measured_volume_ml": round(self.measured_volume_ml, 1),
            "duration_seconds": round(self.duration_seconds, 1),
            "calibrated_at": self.calibrated_at,
            "confidence": round(self.confidence, 2),
            "method": self.method,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CalibrationHistoryEntry":
        """Create from dictionary."""
        return cls(
            flow_rate_ml_per_second=data.get("flow_rate_ml_per_second", 0),
            measured_volume_ml=data.get("measured_volume_ml", 0),
            duration_seconds=data.get("duration_seconds", 0),
            calibrated_at=data.get("calibrated_at", ""),
            confidence=data.get("confidence", 1.0),
            method=data.get("method", "manual"),
        )


@dataclass
class PumpCalibrationData:
    """Calibration data stored in actuator config."""

    flow_rate_ml_per_second: float
    calibration_volume_ml: float
    calibration_duration_seconds: int
    calibrated_at: str
    calibration_confidence: float = 1.0
    last_feedback_adjustment: str | None = None
    feedback_adjustments_count: int = 0
    calibration_history: list[dict[str, Any]] = field(default_factory=list)  # History of calibrations

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "flow_rate_ml_per_second": self.flow_rate_ml_per_second,
            "calibration_volume_ml": self.calibration_volume_ml,
            "calibration_duration_seconds": self.calibration_duration_seconds,
            "calibrated_at": self.calibrated_at,
            "calibration_confidence": self.calibration_confidence,
            "last_feedback_adjustment": self.last_feedback_adjustment,
            "feedback_adjustments_count": self.feedback_adjustments_count,
            "calibration_history": self.calibration_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PumpCalibrationData":
        """Create from dictionary."""
        return cls(
            flow_rate_ml_per_second=data.get("flow_rate_ml_per_second", 0),
            calibration_volume_ml=data.get("calibration_volume_ml", 0),
            calibration_duration_seconds=data.get("calibration_duration_seconds", 0),
            calibrated_at=data.get("calibrated_at", ""),
            calibration_confidence=data.get("calibration_confidence", 1.0),
            last_feedback_adjustment=data.get("last_feedback_adjustment"),
            feedback_adjustments_count=data.get("feedback_adjustments_count", 0),
            calibration_history=data.get("calibration_history", []),
        )

    def add_history_entry(self, entry: CalibrationHistoryEntry, max_entries: int = 10) -> None:
        """
        Add a new calibration entry to history.

        Args:
            entry: CalibrationHistoryEntry to add
            max_entries: Maximum number of entries to keep (default 10)
        """
        self.calibration_history.insert(0, entry.to_dict())
        # Keep only the most recent entries
        if len(self.calibration_history) > max_entries:
            self.calibration_history = self.calibration_history[:max_entries]

    def get_flow_rate_trend(self) -> dict[str, Any] | None:
        """
        Analyze calibration history to determine flow rate trend.

        Returns:
            Dict with trend analysis or None if insufficient data
        """
        if len(self.calibration_history) < 2:
            return None

        rates = [h.get("flow_rate_ml_per_second", 0) for h in self.calibration_history]
        avg_rate = sum(rates) / len(rates)
        current_rate = rates[0]
        oldest_rate = rates[-1]

        # Calculate trend direction and magnitude
        if current_rate > oldest_rate * 1.05:
            trend = "increasing"
        elif current_rate < oldest_rate * 0.95:
            trend = "decreasing"
        else:
            trend = "stable"

        # Calculate variance
        variance = sum((r - avg_rate) ** 2 for r in rates) / len(rates)
        std_dev = variance**0.5
        if avg_rate <= 0:
            consistency = "unknown"
        else:
            consistency = "consistent" if std_dev / avg_rate < 0.1 else "variable"

        return {
            "trend": trend,
            "consistency": consistency,
            "current_rate": current_rate,
            "average_rate": round(avg_rate, 3),
            "std_dev": round(std_dev, 3),
            "sample_count": len(rates),
            "oldest_rate": oldest_rate,
            "rate_change_percent": round((current_rate - oldest_rate) / oldest_rate * 100, 1) if oldest_rate > 0 else 0,
        }


class PumpCalibrationService:
    """
    Service for calibrating pump flow rates.

    Calibration Flow:
    1. User clicks "Start Calibration" in UI
    2. System runs pump for fixed duration (e.g., 30 seconds)
    3. User measures collected water volume
    4. User enters measured_ml in UI
    5. System calculates flow_rate = measured_ml / duration
    6. Flow rate stored in actuator metadata

    ML Refinement:
    - When user gives feedback (too_little/too_much), system adjusts flow_rate
    - Feedback adjusts by small increments (±5%) to converge on true rate
    """

    def __init__(
        self,
        actuator_service: "ActuatorManagementService",
        device_repo: "DeviceRepository",
    ):
        """
        Initialize pump calibration service.

        Args:
            actuator_service: ActuatorManagementService for pump control
            device_repo: DeviceRepository for persisting calibration data
        """
        self._actuator_service = actuator_service
        self._device_repo = device_repo
        self._active_sessions: dict[int, CalibrationSession] = {}

    def is_pump(self, actuator_type: str) -> bool:
        """Check if actuator type is a pump."""
        try:
            return ActuatorType(actuator_type) is ActuatorType.WATER_PUMP
        except ValueError:
            return False

    def start_calibration(
        self,
        actuator_id: int,
        duration_seconds: int | None = None,
    ) -> dict[str, Any]:
        """
        Start pump calibration by running pump for fixed duration.

        Args:
            actuator_id: The pump actuator ID
            duration_seconds: How long to run pump (default: 30s)

        Returns:
            Status dict with session info
        """
        if duration_seconds is None:
            duration_seconds = PUMP_CALIBRATION_DEFAULTS["calibration_duration_seconds"]

        # Block new calibrations if any session is still active.
        for session in self._active_sessions.values():
            if session.status in {"running", "awaiting_measurement"}:
                return {
                    "ok": False,
                    "error": "Calibration already in progress",
                    "status": session.status,
                    "actuator_id": session.actuator_id,
                }

        # Validate actuator is a pump
        actuator = self._device_repo.get_actuator_config_by_id(actuator_id)
        if not actuator:
            return {"ok": False, "error": "Actuator not found"}

        actuator_type = actuator.get("actuator_type", "")
        if not self.is_pump(actuator_type):
            return {
                "ok": False,
                "error": f"Actuator is not a pump (type: {actuator_type})",
            }

        # Run pump
        success = self._actuator_service.turn_on(
            actuator_id,
            duration_seconds=duration_seconds,
        )

        if not success:
            return {"ok": False, "error": "Failed to activate pump"}

        # Create session
        session = CalibrationSession(
            actuator_id=actuator_id,
            start_time=utc_now(),
            target_duration_seconds=duration_seconds,
            status="awaiting_measurement",
            unit_id=actuator.get("unit_id"),
        )
        self._active_sessions[actuator_id] = session

        logger.info(
            "Started calibration for pump %s, running for %ds",
            actuator_id,
            duration_seconds,
        )

        return {
            "ok": True,
            "actuator_id": actuator_id,
            "duration_seconds": duration_seconds,
            "status": "awaiting_measurement",
            "message": f"Pump running for {duration_seconds}s. Collect the water and measure the volume.",
            "next_step": "Call complete_calibration with the measured volume in ml",
        }

    def complete_calibration(
        self,
        actuator_id: int,
        measured_ml: float,
    ) -> CalibrationResult:
        """
        Complete calibration with user's measured water volume.

        Args:
            actuator_id: The pump actuator ID
            measured_ml: Volume of water collected (measured by user)

        Returns:
            CalibrationResult with calculated flow rate

        Raises:
            ValueError: If no active session or invalid measurement
        """
        session = self._active_sessions.get(actuator_id)
        if not session:
            raise ValueError(f"No active calibration session for actuator {actuator_id}")

        if measured_ml <= 0:
            raise ValueError("Measured volume must be positive")

        # Calculate flow rate
        duration = session.target_duration_seconds
        flow_rate = measured_ml / duration if duration > 0 else 0

        # Get existing calibration data (for history)
        existing = self.get_calibration_data(actuator_id)
        history = existing.calibration_history if existing else []

        # Create calibration data
        calibration_data = PumpCalibrationData(
            flow_rate_ml_per_second=flow_rate,
            calibration_volume_ml=measured_ml,
            calibration_duration_seconds=duration,
            calibrated_at=iso_now(),
            calibration_confidence=1.0,
            calibration_history=history,
        )

        # Add current calibration to history
        history_entry = CalibrationHistoryEntry(
            flow_rate_ml_per_second=flow_rate,
            measured_volume_ml=measured_ml,
            duration_seconds=duration,
            calibrated_at=calibration_data.calibrated_at,
            confidence=1.0,
            method="manual",
        )
        calibration_data.add_history_entry(history_entry)

        # Store in actuator config_data
        self._update_actuator_calibration(actuator_id, calibration_data)

        # Clean up session
        del self._active_sessions[actuator_id]

        logger.info(
            "Completed calibration for pump %s: %.3f ml/s (measured %s ml in %ds)",
            actuator_id,
            flow_rate,
            measured_ml,
            duration,
        )

        return CalibrationResult(
            actuator_id=actuator_id,
            flow_rate_ml_per_second=flow_rate,
            measured_volume_ml=measured_ml,
            duration_seconds=duration,
            calibrated_at=calibration_data.calibrated_at,
            confidence=1.0,
        )

    def cancel_calibration(self, actuator_id: int) -> dict[str, Any]:
        """
        Cancel an active calibration session.

        Args:
            actuator_id: The pump actuator ID

        Returns:
            Status dict
        """
        session = self._active_sessions.pop(actuator_id, None)
        if not session:
            return {"ok": False, "error": "No active session"}

        # Turn off pump if still running
        self._actuator_service.turn_off(actuator_id)

        logger.info("Cancelled calibration for pump %s", actuator_id)
        return {"ok": True, "message": "Calibration cancelled"}

    def adjust_from_feedback(
        self,
        actuator_id: int,
        feedback: str,
        adjustment_factor: float = 0.05,
    ) -> float | None:
        """
        Adjust flow rate based on irrigation feedback.

        If user says "too_little", we delivered less water than calculated,
        meaning actual flow rate is LOWER than stored → decrease stored rate.

        If user says "too_much", actual flow rate is HIGHER → increase stored rate.

        Args:
            actuator_id: The pump actuator ID
            feedback: "too_little", "just_right", or "too_much"
            adjustment_factor: Percentage adjustment per feedback (default 5%)

        Returns:
            New flow rate or None if not calibrated
        """
        calibration = self.get_calibration_data(actuator_id)
        if not calibration:
            logger.warning(
                "Cannot adjust uncalibrated pump %s from feedback",
                actuator_id,
            )
            return None

        current_rate = calibration.flow_rate_ml_per_second

        # Adjust rate
        if feedback == "too_little":
            # We thought we delivered X ml but it was less → rate is lower
            new_rate = current_rate * (1 - adjustment_factor)
        elif feedback == "too_much":
            # We delivered more than expected → rate is higher
            new_rate = current_rate * (1 + adjustment_factor)
        else:
            # "just_right" - no adjustment needed
            return current_rate

        # Update confidence (decreases with each adjustment, min 50%)
        new_confidence = max(0.5, calibration.calibration_confidence - 0.05)

        # Update calibration data
        calibration.flow_rate_ml_per_second = new_rate
        calibration.calibration_confidence = new_confidence
        calibration.last_feedback_adjustment = iso_now()
        calibration.feedback_adjustments_count += 1

        # Add feedback adjustment to history
        history_entry = CalibrationHistoryEntry(
            flow_rate_ml_per_second=new_rate,
            measured_volume_ml=0,  # Not applicable for feedback adjustments
            duration_seconds=0,  # Not applicable for feedback adjustments
            calibrated_at=iso_now(),
            confidence=new_confidence,
            method=f"feedback_adjustment_{feedback}",
        )
        calibration.add_history_entry(history_entry)

        self._update_actuator_calibration(actuator_id, calibration)

        logger.info(
            "Adjusted pump %s flow rate from %.3f to %.3f ml/s based on '%s' feedback",
            actuator_id,
            current_rate,
            new_rate,
            feedback,
        )

        return new_rate

    def get_flow_rate(self, actuator_id: int) -> float | None:
        """
        Get calibrated flow rate for an actuator.

        Args:
            actuator_id: The pump actuator ID

        Returns:
            Flow rate in ml/s or None if not calibrated
        """
        calibration = self.get_calibration_data(actuator_id)
        return calibration.flow_rate_ml_per_second if calibration else None

    def get_calibration_data(self, actuator_id: int) -> PumpCalibrationData | None:
        """
        Get full calibration data for an actuator.

        Args:
            actuator_id: The pump actuator ID

        Returns:
            PumpCalibrationData or None if not calibrated
        """
        actuator = self._device_repo.get_actuator_config_by_id(actuator_id)
        if not actuator:
            return None

        config = actuator.get("config", {})
        if isinstance(config, str):
            try:
                config = json.loads(config) if config else {}
            except json.JSONDecodeError:
                config = {}

        # Check for calibration data
        if "flow_rate_ml_per_second" not in config:
            return None

        return PumpCalibrationData.from_dict(config)

    def is_calibrated(self, actuator_id: int) -> bool:
        """Check if pump has been calibrated."""
        return self.get_flow_rate(actuator_id) is not None

    def get_active_session(self, actuator_id: int) -> CalibrationSession | None:
        """Get active calibration session if any."""
        return self._active_sessions.get(actuator_id)

    def list_calibrated_pumps(self, unit_id: int | None = None) -> list[dict[str, Any]]:
        """
        List all calibrated pumps for a unit.

        Args:
            unit_id: Filter by unit (optional)

        Returns:
            List of pump info with calibration data
        """
        actuators = self._device_repo.list_actuator_configs(unit_id=unit_id)
        calibrated = []

        for actuator in actuators:
            if not self.is_pump(actuator.get("actuator_type", "")):
                continue

            calibration = self.get_calibration_data(actuator["actuator_id"])
            if calibration:
                calibrated.append(
                    {
                        "actuator_id": actuator["actuator_id"],
                        "name": actuator.get("name"),
                        "unit_id": actuator.get("unit_id"),
                        "calibration": calibration.to_dict(),
                    }
                )

        return calibrated

    def _update_actuator_calibration(
        self,
        actuator_id: int,
        calibration: PumpCalibrationData,
    ) -> bool:
        """
        Update actuator config with calibration data.

        Args:
            actuator_id: The pump actuator ID
            calibration: Calibration data to store

        Returns:
            True if successful
        """
        actuator = self._device_repo.get_actuator_config_by_id(actuator_id)
        if not actuator:
            return False

        # Get existing config and merge calibration data
        config = actuator.get("config", {})
        if isinstance(config, str):
            try:
                config = json.loads(config) if config else {}
            except json.JSONDecodeError:
                config = {}

        # Merge calibration data into config
        config.update(calibration.to_dict())

        # Update via repository - need to use backend directly
        return self._device_repo._backend.update_actuator_config(actuator_id, config)
