"""
Irrigation Workflow Service
============================

Manages the irrigation standby/notification/approval workflow:
1. Detection: When soil moisture drops below threshold, creates a pending request
2. Notification: Sends notification to user for approval
3. User Response: Handles approve/delay/cancel responses
4. Scheduled Execution: Executes irrigation at scheduled time (default 21:00)
5. Fallback: Auto-executes if no response by scheduled time
6. Feedback: Requests feedback after irrigation for ML learning

Author: SYSGrow Team
Date: January 2026
"""
from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from app.domain.actuators import ActuatorState
from app.enums import (
    IrrigationEligibilityDecision,
    IrrigationSkipReason,
    IrrigationFeedback,
    NotificationType,
    NotificationSeverity,
)
from app.utils.concurrency import synchronized
from app.utils.time import coerce_datetime, iso_now, utc_now
from app.defaults import SystemConfigDefaults

if TYPE_CHECKING:
    from infrastructure.database.repositories.irrigation_workflow import IrrigationWorkflowRepository
    from app.services.application.notifications_service import NotificationsService
    from app.services.application.plant_service import PlantViewService
    from app.services.hardware.actuator_management_service import ActuatorManagementService
    from app.workers.unified_scheduler import UnifiedScheduler
    from app.services.ai.bayesian_threshold import BayesianThresholdAdjuster
    from app.domain.irrigation_calculator import IrrigationCalculator
    from app.services.hardware.pump_calibration import PumpCalibrationService

logger = logging.getLogger(__name__)

# Type alias for backwards compatibility - ActuatorManager is now ActuatorManagementService
ActuatorManager = "ActuatorManagementService"


# Request status constants
class RequestStatus:
    """Pending irrigation request status constants."""
    PENDING = "pending"
    APPROVED = "approved"
    DELAYED = "delayed"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FAILED = "failed"


# User response constants
class UserResponse:
    """User response types."""
    APPROVE = "approve"
    DELAY = "delay"
    CANCEL = "cancel"
    AUTO = "auto"  # No response, auto-executed


@dataclass
class WorkflowConfig:
    """Configuration for irrigation workflow."""
    workflow_enabled: bool = True
    auto_irrigation_enabled: bool = False
    manual_mode_enabled: bool = False
    require_approval: bool = True
    default_scheduled_time: str = "21:00"
    delay_increment_minutes: int = 60
    max_delay_hours: int = 24
    expiration_hours: int = 48
    send_reminder_before_execution: bool = True
    reminder_minutes_before: int = 30
    request_feedback_enabled: bool = True
    feedback_delay_minutes: int = 30
    ml_learning_enabled: bool = True
    ml_threshold_adjustment_enabled: bool = False

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowConfig":
        """Create config from dictionary."""
        return cls(
            workflow_enabled=bool(data.get("workflow_enabled", True)),
            auto_irrigation_enabled=bool(data.get("auto_irrigation_enabled", False)),
            manual_mode_enabled=bool(data.get("manual_mode_enabled", False)),
            require_approval=bool(data.get("require_approval", True)),
            default_scheduled_time=data.get("default_scheduled_time", "21:00"),
            delay_increment_minutes=int(data.get("delay_increment_minutes", 60)),
            max_delay_hours=int(data.get("max_delay_hours", 24)),
            expiration_hours=int(data.get("expiration_hours", 48)),
            send_reminder_before_execution=bool(data.get("send_reminder_before_execution", True)),
            reminder_minutes_before=int(data.get("reminder_minutes_before", 30)),
            request_feedback_enabled=bool(data.get("request_feedback_enabled", True)),
            feedback_delay_minutes=int(data.get("feedback_delay_minutes", 30)),
            ml_learning_enabled=bool(data.get("ml_learning_enabled", True)),
            ml_threshold_adjustment_enabled=bool(data.get("ml_threshold_adjustment_enabled", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "workflow_enabled": self.workflow_enabled,
            "auto_irrigation_enabled": self.auto_irrigation_enabled,
            "manual_mode_enabled": self.manual_mode_enabled,
            "require_approval": self.require_approval,
            "default_scheduled_time": self.default_scheduled_time,
            "delay_increment_minutes": self.delay_increment_minutes,
            "max_delay_hours": self.max_delay_hours,
            "expiration_hours": self.expiration_hours,
            "send_reminder_before_execution": self.send_reminder_before_execution,
            "reminder_minutes_before": self.reminder_minutes_before,
            "request_feedback_enabled": self.request_feedback_enabled,
            "feedback_delay_minutes": self.feedback_delay_minutes,
            "ml_learning_enabled": self.ml_learning_enabled,
            "ml_threshold_adjustment_enabled": self.ml_threshold_adjustment_enabled,
        }


class IrrigationWorkflowService:
    """
    Service for managing irrigation standby/notification/approval workflow.

    Workflow:
    1. detect_irrigation_need() - Called when soil moisture drops below threshold
    2. Creates pending request and sends notification to user
    3. User responds via handle_user_response() - approve/delay/cancel
    4. Scheduler calls execute_due_requests() at scheduled time
    5. After execution, requests feedback via notification
    6. ML learning captures user preferences for future optimization
    """

    def __init__(
        self,
        workflow_repo: "IrrigationWorkflowRepository",
        notifications_service: Optional["NotificationsService"] = None,
        actuator_service: Optional["ActuatorManagementService"] = None,
        scheduler: Optional["UnifiedScheduler"] = None,
        scheduling_service: Optional[Any] = None,
        bayesian_adjuster: Optional["BayesianThresholdAdjuster"] = None,
        irrigation_calculator: Optional["IrrigationCalculator"] = None,
        pump_calibration_service: Optional["PumpCalibrationService"] = None,
        plant_service: Optional["PlantViewService"] = None,
        completion_interval_seconds: Optional[int] = None,
        post_capture_interval_seconds: Optional[int] = None,
        post_capture_delay_seconds: Optional[int] = None,
        hysteresis_margin: Optional[float] = None,
    ):
        """
        Initialize IrrigationWorkflowService.

        Args:
            workflow_repo: Repository for workflow data
            notifications_service: Service for sending notifications
            actuator_manager: Manager for actuator control
            scheduler: Unified scheduler for scheduled execution
            bayesian_adjuster: Optional Bayesian threshold adjuster for ML learning
            irrigation_calculator: Optional calculator for data-driven irrigation duration
            pump_calibration_service: Optional service for pump flow rate calibration
            plant_service: Optional plant service for plant data access
            completion_interval_seconds: Interval for completion checks (seconds)
            post_capture_interval_seconds: Interval for post-watering capture checks (seconds)
            post_capture_delay_seconds: Delay after watering before capturing moisture (seconds)
            hysteresis_margin: Moisture hysteresis margin for attribution
        """
        self._repo = workflow_repo
        self._notifications = notifications_service
        self._actuator_service = actuator_service
        self._scheduler = scheduler
        self._scheduling_service = scheduling_service
        self._bayesian_adjuster = bayesian_adjuster
        self._irrigation_calculator = irrigation_calculator
        self._pump_calibration = pump_calibration_service
        self._plant_service = plant_service

        # Cache for workflow configs
        self._config_cache: Dict[int, WorkflowConfig] = {}
        self._lock = threading.Lock()

        # Callback for threshold adjustment (set by ThresholdService)
        self._threshold_adjustment_callback: Optional[Callable] = None

        self._completion_interval_seconds = (
            completion_interval_seconds
            if completion_interval_seconds is not None
            else self._read_int_env("SYSGROW_IRRIGATION_COMPLETION_INTERVAL_SECONDS", 5)
        )
        self._post_capture_interval_seconds = (
            post_capture_interval_seconds
            if post_capture_interval_seconds is not None
            else self._read_int_env("SYSGROW_IRRIGATION_POST_CAPTURE_INTERVAL_SECONDS", 60)
        )
        self._post_capture_delay_seconds = (
            post_capture_delay_seconds
            if post_capture_delay_seconds is not None
            else self._read_int_env("SYSGROW_IRRIGATION_POST_CAPTURE_DELAY_SECONDS", 15 * 60)
        )
        self._max_duration_seconds = self._read_int_env("SYSGROW_IRRIGATION_MAX_DURATION_SECONDS", 900)
        self._hysteresis_margin = (
            hysteresis_margin
            if hysteresis_margin is not None
            else self._read_float_env("SYSGROW_IRRIGATION_HYSTERESIS", float(SystemConfigDefaults.HYSTERESIS))
        )
        self._stale_reading_seconds = self._read_int_env(
            "SYSGROW_IRRIGATION_STALE_READING_SECONDS",
            30 * 60,
        )
        self._cooldown_minutes = self._read_int_env(
            "SYSGROW_IRRIGATION_COOLDOWN_MINUTES",
            60,
        )
        self._sensor_missing_alert_minutes = self._read_int_env(
            "SYSGROW_IRRIGATION_SENSOR_MISSING_ALERT_MINUTES",
            60,
        )
        self._last_sensor_missing_alert: Dict[str, datetime] = {}

        logger.info("IrrigationWorkflowService initialized")

    @staticmethod
    def _read_int_env(name: str, default: int) -> int:
        raw = os.getenv(name, "")
        if not raw.strip():
            return default
        try:
            value = int(float(raw.strip()))
        except ValueError:
            return default
        return max(1, value)

    @staticmethod
    def _read_float_env(name: str, default: float) -> float:
        raw = os.getenv(name, "")
        if not raw.strip():
            return default
        try:
            value = float(raw.strip())
        except ValueError:
            return default
        return max(0.0, value)

    def _maybe_notify_sensor_missing(
        self,
        *,
        user_id: int,
        unit_id: int,
        sensor_id: Optional[int],
        plant_id: Optional[int],
        plant_name: Optional[str],
        reason: IrrigationSkipReason,
        last_seen: Optional[str] = None,
    ) -> None:
        """Send a throttled alert when soil moisture sensor is missing or stale."""
        if not self._notifications or not user_id:
            return

        throttle_minutes = max(1, int(self._sensor_missing_alert_minutes))
        key = f"{unit_id}:{sensor_id or 'none'}:{plant_id or 'none'}:{reason.value}"
        now = utc_now()
        last_sent = self._last_sensor_missing_alert.get(key)
        if last_sent and (now - last_sent) < timedelta(minutes=throttle_minutes):
            return

        device_name = "Soil moisture sensor"
        if plant_name:
            device_name = f"{plant_name} soil sensor"

        message = "Soil moisture sensor is missing or offline."
        if reason == IrrigationSkipReason.STALE_READING:
            message = "Soil moisture sensor data is stale and automation is paused."

        self._notifications.send_notification(
            user_id=user_id,
            notification_type=NotificationType.DEVICE_OFFLINE,
            title=f"{device_name} offline",
            message=message,
            severity=NotificationSeverity.WARNING,
            source_type="sensor",
            source_id=sensor_id,
            unit_id=unit_id,
        )
        self._last_sensor_missing_alert[key] = now

    def _record_eligibility_trace(
        self,
        *,
        unit_id: int,
        plant_id: Optional[int],
        sensor_id: Optional[int],
        moisture: Optional[float],
        threshold: Optional[float],
        decision: IrrigationEligibilityDecision,
        skip_reason: Optional[IrrigationSkipReason],
    ) -> None:
        """Persist an irrigation eligibility decision for troubleshooting."""
        if not self._repo:
            return

        try:
            self._repo.create_eligibility_trace(
                plant_id=plant_id,
                unit_id=unit_id,
                sensor_id=str(sensor_id) if sensor_id is not None else None,
                moisture=moisture,
                threshold=threshold,
                decision=decision.value,
                skip_reason=skip_reason.value if skip_reason is not None else None,
                evaluated_at_utc=iso_now(),
            )
        except Exception as exc:
            logger.debug("Failed to record irrigation eligibility trace: %s", exc)

    @staticmethod
    def _coerce_actuator_id(value: Any) -> Optional[int]:
        """Coerce actuator id values to int if possible."""
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _resolve_valve_actuator_id(
        self,
        plant_id: Optional[int],
    ) -> Optional[int]:
        """Resolve valve actuator for a plant, if configured."""
        if plant_id is None or not self._plant_service:
            return None
        try:
            return self._plant_service.get_plant_valve_actuator_id(int(plant_id))
        except Exception as exc:
            logger.debug("Failed to resolve valve actuator for plant %s: %s", plant_id, exc)
            return None

    def set_notifications_service(self, service: "NotificationsService") -> None:
        """Set notifications service (for circular dependency resolution)."""
        self._notifications = service

    def set_actuator_manager(self, manager: "ActuatorManagementService") -> None:
        """Set actuator manager."""
        self._actuator_service = manager

    def set_scheduler(self, scheduler: "UnifiedScheduler") -> None:
        """Set scheduler."""
        self._scheduler = scheduler

    def set_scheduling_service(self, service: Any) -> None:
        """Set scheduling service for interval task registration."""
        self._scheduling_service = service

    def set_threshold_callback(self, callback: Callable) -> None:
        """Set callback for threshold adjustments."""
        self._threshold_adjustment_callback = callback

    def set_bayesian_adjuster(self, adjuster: "BayesianThresholdAdjuster") -> None:
        """Set Bayesian threshold adjuster for intelligent learning."""
        self._bayesian_adjuster = adjuster
        logger.info("Bayesian threshold adjuster configured")

    def set_irrigation_calculator(self, calculator: "IrrigationCalculator") -> None:
        """Set irrigation calculator for data-driven duration computation."""
        self._irrigation_calculator = calculator
        logger.info("Irrigation calculator configured")

    def set_pump_calibration_service(self, service: "PumpCalibrationService") -> None:
        """Set pump calibration service for flow rate management."""
        self._pump_calibration = service
        logger.info("Pump calibration service configured")

    def set_plant_service(self, service: "PlantViewService") -> None:
        """Set plant service for plant data access."""
        self._plant_service = service
        logger.info("Plant service configured for irrigation workflow")

    def record_eligibility_trace(
        self,
        *,
        unit_id: int,
        plant_id: Optional[int],
        sensor_id: Optional[int],
        moisture: Optional[float],
        threshold: Optional[float],
        decision: IrrigationEligibilityDecision,
        skip_reason: Optional[IrrigationSkipReason],
    ) -> None:
        """Record an eligibility trace entry for irrigation decisions."""
        self._record_eligibility_trace(
            unit_id=unit_id,
            plant_id=plant_id,
            sensor_id=sensor_id,
            moisture=moisture,
            threshold=threshold,
            decision=decision,
            skip_reason=skip_reason,
        )

    # ==================== Configuration ====================

    def get_config(self, unit_id: int) -> WorkflowConfig:
        """Get workflow configuration for a unit."""
        if unit_id in self._config_cache:
            return self._config_cache[unit_id]

        data = self._repo.get_config(unit_id)
        if data:
            config = WorkflowConfig.from_dict(data)
        else:
            config = WorkflowConfig()  # defaults

        self._config_cache[unit_id] = config
        return config

    def save_config(self, unit_id: int, config: WorkflowConfig) -> bool:
        """Save workflow configuration for a unit."""
        success = self._repo.save_config(unit_id, config.to_dict())
        if success:
            self._config_cache[unit_id] = config
        return success

    def update_config(self, unit_id: int, updates: Dict[str, Any]) -> bool:
        """Update specific configuration values."""
        current = self.get_config(unit_id)
        for key, value in updates.items():
            if hasattr(current, key):
                setattr(current, key, value)
        return self.save_config(unit_id, current)

    # ==================== Detection & Request Creation ====================

    def detect_irrigation_need(
        self,
        unit_id: int,
        soil_moisture: float,
        threshold: float,
        user_id: int,
        plant_id: Optional[int] = None,
        actuator_id: Optional[int] = None,
        sensor_id: Optional[int] = None,
        reading_timestamp: Optional[str] = None,
        plant_name: Optional[str] = None,
        plant_pump_assigned: bool = False,
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        vpd: Optional[float] = None,
        lux: Optional[float] = None,
        plant_type: Optional[str] = None,
        growth_stage: Optional[str] = None,
    ) -> Optional[int]:
        """
        Handle detection of irrigation need.

        Called when soil moisture drops below threshold. Creates a pending
        request and sends notification to user unless manual mode is enabled.

        Args:
            unit_id: Growth unit ID
            soil_moisture: Current soil moisture reading
            threshold: Configured threshold that was breached
            user_id: User ID to notify
            plant_id: Optional plant ID
            actuator_id: Optional water pump actuator ID
            sensor_id: Optional sensor ID that detected the condition
            reading_timestamp: Optional ISO timestamp for the reading
            plant_name: Optional plant name for notification
            plant_pump_assigned: True if a dedicated pump is mapped to the plant
            temperature: Temperature at detection (for ML)
            humidity: Humidity at detection (for ML)
            vpd: VPD at detection (for ML)
            lux: Light level at detection (for ML)
            plant_type: Plant type for ML context
            growth_stage: Growth stage for ML context

        Returns:
            Request ID if created, None otherwise
        """
        config = self.get_config(unit_id)

        # Check if workflow is enabled
        if not config.workflow_enabled:
            logger.debug(f"Workflow disabled for unit {unit_id}, skipping")
            self._record_eligibility_trace(
                unit_id=unit_id,
                plant_id=plant_id,
                sensor_id=sensor_id,
                moisture=soil_moisture,
                threshold=threshold,
                decision=IrrigationEligibilityDecision.SKIP,
                skip_reason=IrrigationSkipReason.DISABLED,
            )
            return None

        # Manual mode skips automated checks and requests
        if config.manual_mode_enabled:
            logger.debug("Manual irrigation mode enabled for unit %s, skipping", unit_id)
            self._record_eligibility_trace(
                unit_id=unit_id,
                plant_id=plant_id,
                sensor_id=sensor_id,
                moisture=soil_moisture,
                threshold=threshold,
                decision=IrrigationEligibilityDecision.SKIP,
                skip_reason=IrrigationSkipReason.MANUAL_MODE_NO_AUTO,
            )
            return None

        if sensor_id is None:
            logger.debug("No sensor id for unit %s irrigation evaluation, skipping", unit_id)
            self._record_eligibility_trace(
                unit_id=unit_id,
                plant_id=plant_id,
                sensor_id=None,
                moisture=soil_moisture,
                threshold=threshold,
                decision=IrrigationEligibilityDecision.SKIP,
                skip_reason=IrrigationSkipReason.NO_SENSOR,
            )
            self._maybe_notify_sensor_missing(
                user_id=user_id,
                unit_id=unit_id,
                sensor_id=None,
                plant_id=plant_id,
                plant_name=plant_name,
                reason=IrrigationSkipReason.NO_SENSOR,
                last_seen=reading_timestamp,
            )
            return None

        if reading_timestamp is not None and self._stale_reading_seconds > 0:
            reading_dt = coerce_datetime(reading_timestamp)
            if reading_dt is None:
                logger.debug("Invalid reading timestamp for unit %s, skipping", unit_id)
                self._record_eligibility_trace(
                    unit_id=unit_id,
                    plant_id=plant_id,
                    sensor_id=sensor_id,
                    moisture=soil_moisture,
                    threshold=threshold,
                    decision=IrrigationEligibilityDecision.SKIP,
                    skip_reason=IrrigationSkipReason.STALE_READING,
                )
                self._maybe_notify_sensor_missing(
                    user_id=user_id,
                    unit_id=unit_id,
                    sensor_id=sensor_id,
                    plant_id=plant_id,
                    plant_name=plant_name,
                    reason=IrrigationSkipReason.STALE_READING,
                    last_seen=reading_timestamp,
                )
                return None
            age_seconds = (utc_now() - reading_dt).total_seconds()
            if age_seconds > float(self._stale_reading_seconds):
                logger.debug(
                    "Stale irrigation reading for unit %s (age=%.1fs), skipping",
                    unit_id,
                    age_seconds,
                )
                self._record_eligibility_trace(
                    unit_id=unit_id,
                    plant_id=plant_id,
                    sensor_id=sensor_id,
                    moisture=soil_moisture,
                    threshold=threshold,
                    decision=IrrigationEligibilityDecision.SKIP,
                    skip_reason=IrrigationSkipReason.STALE_READING,
                )
                self._maybe_notify_sensor_missing(
                    user_id=user_id,
                    unit_id=unit_id,
                    sensor_id=sensor_id,
                    plant_id=plant_id,
                    plant_name=plant_name,
                    reason=IrrigationSkipReason.STALE_READING,
                    last_seen=reading_timestamp,
                )
                return None

        # Check for existing active request (avoid duplicates)
        if plant_pump_assigned and (plant_id is not None or actuator_id is not None):
            if self._repo.has_active_request(unit_id, plant_id=plant_id, actuator_id=actuator_id):
                logger.debug(
                    "Active request already exists for unit %s (plant=%s actuator=%s)",
                    unit_id,
                    plant_id,
                    actuator_id,
                )
                self._record_eligibility_trace(
                    unit_id=unit_id,
                    plant_id=plant_id,
                    sensor_id=sensor_id,
                    moisture=soil_moisture,
                    threshold=threshold,
                    decision=IrrigationEligibilityDecision.SKIP,
                    skip_reason=IrrigationSkipReason.PENDING_REQUEST,
                )
                return None
        elif self._repo.has_active_request(unit_id):
            logger.debug(f"Active request already exists for unit {unit_id}")
            self._record_eligibility_trace(
                unit_id=unit_id,
                plant_id=plant_id,
                sensor_id=sensor_id,
                moisture=soil_moisture,
                threshold=threshold,
                decision=IrrigationEligibilityDecision.SKIP,
                skip_reason=IrrigationSkipReason.PENDING_REQUEST,
            )
            return None

        if self._cooldown_minutes > 0:
            last_irrigation = self.get_last_completed_irrigation(unit_id, plant_id=plant_id)
            executed_at = None
            if last_irrigation:
                executed_at = coerce_datetime(last_irrigation.get("executed_at"))
            if executed_at is not None:
                cooldown_delta = timedelta(minutes=int(self._cooldown_minutes))
                if utc_now() - executed_at < cooldown_delta:
                    logger.debug(
                        "Cooldown active for unit %s, skipping irrigation request",
                        unit_id,
                    )
                    self._record_eligibility_trace(
                        unit_id=unit_id,
                        plant_id=plant_id,
                        sensor_id=sensor_id,
                        moisture=soil_moisture,
                        threshold=threshold,
                        decision=IrrigationEligibilityDecision.SKIP,
                        skip_reason=IrrigationSkipReason.COOLDOWN_ACTIVE,
                    )
                    return None

        # Calculate scheduled time (today or tomorrow at default time)
        scheduled_time = self._calculate_scheduled_time(config.default_scheduled_time)

        # Calculate expiration time
        expires_at = (utc_now() + timedelta(hours=config.expiration_hours)).isoformat()

        # Calculate hours since last irrigation for ML context
        hours_since_last = self._calculate_hours_since_last_irrigation(unit_id)

        # Create pending request with ML context
        request_id = self._repo.create_request(
            unit_id=unit_id,
            soil_moisture_detected=soil_moisture,
            soil_moisture_threshold=threshold,
            user_id=user_id,
            plant_id=plant_id,
            actuator_id=actuator_id,
            sensor_id=sensor_id,
            scheduled_time=scheduled_time,
            expires_at=expires_at,
            # ML context fields
            temperature_at_detection=temperature,
            humidity_at_detection=humidity,
            vpd_at_detection=vpd,
            lux_at_detection=lux,
            hours_since_last_irrigation=hours_since_last,
            plant_type=plant_type,
            growth_stage=growth_stage,
        )

        if not request_id:
            logger.error(f"Failed to create irrigation request for unit {unit_id}")
            self._record_eligibility_trace(
                unit_id=unit_id,
                plant_id=plant_id,
                sensor_id=sensor_id,
                moisture=soil_moisture,
                threshold=threshold,
                decision=IrrigationEligibilityDecision.SKIP,
                skip_reason=IrrigationSkipReason.REQUEST_CREATE_FAILED,
            )
            return None

        logger.info(
            f"Created pending irrigation request {request_id} for unit {unit_id}: "
            f"moisture={soil_moisture:.1f}% (threshold={threshold:.1f}%), "
            f"scheduled={scheduled_time}"
        )

        self._record_eligibility_trace(
            unit_id=unit_id,
            plant_id=plant_id,
            sensor_id=sensor_id,
            moisture=soil_moisture,
            threshold=threshold,
            decision=IrrigationEligibilityDecision.NOTIFY,
            skip_reason=None,
        )

        # Send notification to user
        if self._notifications and config.require_approval:
            display_name = plant_name if plant_pump_assigned else None
            notification_id = self._send_approval_notification(
                request_id=request_id,
                user_id=user_id,
                unit_id=unit_id,
                plant_name=display_name,
                soil_moisture=soil_moisture,
                threshold=threshold,
                scheduled_time=scheduled_time,
            )

            if notification_id:
                self._repo.link_notification(request_id, notification_id)

        return request_id

    def _calculate_scheduled_time(self, time_str: str) -> str:
        """Calculate next scheduled time (today or tomorrow)."""
        now = utc_now()
        hour, minute = map(int, time_str.split(":"))

        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If time has already passed today, schedule for tomorrow
        if scheduled <= now:
            scheduled += timedelta(days=1)

        return scheduled.isoformat()

    def _calculate_hours_since_last_irrigation(self, unit_id: int) -> Optional[float]:
        """Calculate hours since last successful irrigation for ML context."""
        try:
            last_irrigation = self._repo.get_last_completed_irrigation(unit_id)
            if not last_irrigation or not last_irrigation.get("executed_at"):
                return None
            
            last_time = coerce_datetime(last_irrigation["executed_at"])
            if last_time is None:
                return None
            now = utc_now()
            delta = now - last_time.astimezone(timezone.utc)
            return delta.total_seconds() / 3600  # Convert to hours
        except Exception as exc:
            logger.debug(f"Could not calculate hours since last irrigation: {exc}")
            return None

    def _send_approval_notification(
        self,
        request_id: int,
        user_id: int,
        unit_id: int,
        plant_name: Optional[str],
        soil_moisture: float,
        threshold: float,
        scheduled_time: str,
    ) -> Optional[int]:
        """Send notification requesting user approval for irrigation."""
        if not self._notifications:
            return None

        display_name = plant_name or f"Unit {unit_id}"

        # Parse scheduled time for display
        try:
            sched_dt = coerce_datetime(scheduled_time)
            if sched_dt is None:
                raise ValueError("Invalid scheduled time")
            sched_display = sched_dt.strftime("%H:%M")
        except Exception:
            sched_display = "21:00"

        title = f"Irrigation Request: {display_name}"
        message = (
            f"Soil moisture for '{display_name}' is {soil_moisture:.1f}% "
            f"(threshold: {threshold:.1f}%). "
            f"Irrigation is scheduled for {sched_display}. "
            f"Would you like to approve, delay, or cancel?"
        )

        from app.services.application.notifications_service import (
            NotificationType,
            NotificationSeverity,
        )

        return self._notifications.send_notification(
            user_id=user_id,
            notification_type=NotificationType.IRRIGATION_CONFIRM,
            title=title,
            message=message,
            severity=NotificationSeverity.WARNING,
            source_type="irrigation_request",
            source_id=request_id,
            unit_id=unit_id,
            requires_action=True,
            action_type="irrigation_approval",
            action_data={
                "request_id": request_id,
                "unit_id": unit_id,
                "soil_moisture": soil_moisture,
                "threshold": threshold,
                "scheduled_time": scheduled_time,
            },
        )

    # ==================== User Response Handling ====================

    def handle_user_response(
        self,
        request_id: int,
        response: str,
        user_id: int,
        delay_minutes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Handle user response to irrigation request.

        Args:
            request_id: Pending request ID
            response: User response ('approve', 'delay', 'cancel')
            user_id: User who responded
            delay_minutes: Minutes to delay (for 'delay' response)

        Returns:
            Result dictionary with status and message
        """
        request = self._repo.get_request(request_id)
        if not request:
            return {"ok": False, "error": "Request not found"}

        if request["status"] not in (RequestStatus.PENDING, RequestStatus.DELAYED):
            return {"ok": False, "error": f"Request cannot be modified (status: {request['status']})"}

        # Calculate response time for ML learning
        detected_at = coerce_datetime(request.get("detected_at")) or utc_now()
        response_time_seconds = (utc_now() - detected_at).total_seconds()

        config = self.get_config(request["unit_id"])

        if response == UserResponse.APPROVE:
            return self._handle_approve(request, config, user_id, response_time_seconds)

        elif response == UserResponse.DELAY:
            return self._handle_delay(request, config, user_id, response_time_seconds, delay_minutes)

        elif response == UserResponse.CANCEL:
            return self._handle_cancel(request, config, user_id, response_time_seconds)

        else:
            return {"ok": False, "error": f"Invalid response: {response}"}

    def _handle_approve(
        self,
        request: Dict[str, Any],
        config: WorkflowConfig,
        user_id: int,
        response_time_seconds: float,
    ) -> Dict[str, Any]:
        """Handle approval response."""
        request_id = request["request_id"]

        # Update status
        self._repo.update_status(
            request_id,
            RequestStatus.APPROVED,
            user_response=UserResponse.APPROVE,
        )

        # Update user preference for ML
        if config.ml_learning_enabled:
            self._repo.update_preference_on_response(
                user_id, UserResponse.APPROVE, response_time_seconds, request["unit_id"]
            )
            # Positive preference score for immediate approval
            self._repo.mark_ml_collected(request_id, preference_score=1.0)

        logger.info(f"Request {request_id} approved by user {user_id}")

        return {
            "ok": True,
            "message": "Irrigation approved. Will execute at scheduled time.",
            "scheduled_time": request.get("scheduled_time"),
        }

    def _handle_delay(
        self,
        request: Dict[str, Any],
        config: WorkflowConfig,
        user_id: int,
        response_time_seconds: float,
        delay_minutes: Optional[int],
    ) -> Dict[str, Any]:
        """Handle delay response."""
        request_id = request["request_id"]
        unit_id = request["unit_id"]

        # Calculate delay
        delay_mins = delay_minutes or config.delay_increment_minutes

        # Check max delay
        detected_at = coerce_datetime(request.get("detected_at")) or utc_now()
        max_delay_time = detected_at + timedelta(hours=config.max_delay_hours)
        new_time = utc_now() + timedelta(minutes=delay_mins)

        if new_time > max_delay_time:
            return {
                "ok": False,
                "error": f"Cannot delay beyond {config.max_delay_hours} hours from detection",
            }

        delayed_until = new_time.isoformat()

        # Update status
        self._repo.update_status(
            request_id,
            RequestStatus.DELAYED,
            user_response=UserResponse.DELAY,
            delayed_until=delayed_until,
        )

        # Update user preference for ML
        if config.ml_learning_enabled:
            self._repo.update_preference_on_response(
                user_id, UserResponse.DELAY, response_time_seconds, unit_id
            )
            # Neutral preference score for delay
            self._repo.mark_ml_collected(request_id, preference_score=0.5)

        logger.info(f"Request {request_id} delayed to {delayed_until} by user {user_id}")

        return {
            "ok": True,
            "message": f"Irrigation delayed by {delay_mins} minutes.",
            "delayed_until": delayed_until,
        }

    def _handle_cancel(
        self,
        request: Dict[str, Any],
        config: WorkflowConfig,
        user_id: int,
        response_time_seconds: float,
    ) -> Dict[str, Any]:
        """Handle cancel response."""
        request_id = request["request_id"]
        unit_id = request["unit_id"]

        # Update status
        self._repo.update_status(
            request_id,
            RequestStatus.CANCELLED,
            user_response=UserResponse.CANCEL,
        )

        # Update user preference for ML
        if config.ml_learning_enabled:
            self._repo.update_preference_on_response(
                user_id, UserResponse.CANCEL, response_time_seconds, unit_id
            )
            # Negative preference score for cancellation
            self._repo.mark_ml_collected(request_id, preference_score=-1.0)

        logger.info(f"Request {request_id} cancelled by user {user_id}")

        return {
            "ok": True,
            "message": "Irrigation cancelled.",
        }

    # ==================== Scheduled Execution ====================

    @synchronized
    def execute_due_requests(self) -> List[Dict[str, Any]]:
        """
        Execute all requests that are due.

        Called by scheduler at regular intervals or at specific times.

        Returns:
            List of execution results
        """
        results = []
        due_requests = self._repo.claim_due_requests(iso_now())

        for request in due_requests:
            result = self._execute_irrigation(request)
            results.append(result)

        # Also handle expired requests
        self._handle_expired_requests()

        return results

    @synchronized
    def complete_due_executions(self) -> List[Dict[str, Any]]:
        """Complete executing irrigations that have reached their planned duration."""
        results: List[Dict[str, Any]] = []
        executing = self._repo.get_executing_requests()
        if not executing:
            return results

        now = utc_now()
        for request in executing:
            request_id = request.get("request_id")
            unit_id = request.get("unit_id")
            actuator_id = request.get("actuator_id")
            started_at = coerce_datetime(request.get("last_attempt_at_utc"))
            planned_duration = request.get("execution_duration_seconds")
            valve_actuator_id = None
            latest_log = None
            if request_id is not None:
                latest_log = self._repo.get_latest_execution_log_for_request(int(request_id))
            if latest_log:
                valve_actuator_id = self._coerce_actuator_id(latest_log.get("valve_actuator_id"))

            if not request_id or not unit_id or not actuator_id:
                continue
            if started_at is None or planned_duration is None:
                continue

            due_at = started_at + timedelta(seconds=int(planned_duration))
            if now < due_at:
                continue

            if not self._actuator_service:
                error = "No actuator manager available"
                self._repo.update_execution_log_status(
                    request_id,
                    execution_status="failed",
                    execution_error=error,
                )
                self._repo.record_execution(
                    request_id,
                    success=False,
                    error=error,
                )
                self._repo.release_unit_lock(unit_id)
                results.append({"request_id": request_id, "success": False, "error": error})
                continue

            try:
                reading = self._actuator_service.turn_off(int(actuator_id))
                if reading.state in {ActuatorState.ERROR, ActuatorState.UNAVAILABLE}:
                    raise Exception(reading.error_message or "Actuator stop failed")

                duration_seconds = reading.runtime_seconds
                if duration_seconds is None:
                    duration_seconds = (utc_now() - started_at).total_seconds()

                duration_seconds = int(max(0, duration_seconds))

                estimated_volume_ml = None
                if self._pump_calibration:
                    flow_rate = self._pump_calibration.get_flow_rate(int(actuator_id))
                    if flow_rate is not None:
                        estimated_volume_ml = float(flow_rate) * float(duration_seconds)

                self._repo.record_execution(
                    request_id,
                    success=True,
                    duration_seconds=duration_seconds,
                )
                self._repo.update_execution_log_status(
                    request_id,
                    execution_status="completed",
                    actual_duration_s=duration_seconds,
                    estimated_volume_ml=estimated_volume_ml,
                )

                config = self.get_config(unit_id)
                if config.request_feedback_enabled and self._notifications:
                    self._schedule_feedback_request(request, config)

                results.append(
                    {
                        "request_id": request_id,
                        "success": True,
                        "duration_seconds": duration_seconds,
                    }
                )
            except Exception as exc:
                error = str(exc)
                self._repo.update_execution_log_status(
                    request_id,
                    execution_status="failed",
                    execution_error=error,
                )
                self._repo.record_execution(
                    request_id,
                    success=False,
                    error=error,
                )
                results.append({"request_id": request_id, "success": False, "error": error})
            finally:
                if valve_actuator_id is not None and self._actuator_service:
                    try:
                        self._actuator_service.turn_off(int(valve_actuator_id))
                    except Exception:
                        logger.debug("Failed to close valve actuator %s", valve_actuator_id)
                self._repo.release_unit_lock(unit_id)

        return results

    @synchronized
    def capture_due_post_moisture(self) -> List[Dict[str, Any]]:
        """Capture post-watering moisture for completed irrigations."""
        results: List[Dict[str, Any]] = []
        logs = self._repo.get_execution_logs_pending_post_capture()
        if not logs:
            return results

        now = utc_now()
        for log in logs:
            log_id = log.get("id")
            if not log_id:
                continue

            executed_at = coerce_datetime(log.get("executed_at_utc"))
            actual_duration = log.get("actual_duration_s")
            delay_seconds = log.get("post_moisture_delay_s") or self._post_capture_delay_seconds

            if executed_at is None or actual_duration is None:
                continue

            due_at = executed_at + timedelta(seconds=int(actual_duration) + int(delay_seconds))
            if now < due_at:
                continue

            plant_id = log.get("plant_id")
            unit_id = log.get("unit_id")

            post_moisture = self._get_current_moisture(plant_id, unit_id)
            if post_moisture is None:
                continue

            trigger_moisture = log.get("trigger_moisture")
            threshold_at_trigger = log.get("threshold_at_trigger")
            delta_moisture = None
            if trigger_moisture is not None:
                delta_moisture = float(post_moisture) - float(trigger_moisture)

            recommendation = self._classify_attribution(
                trigger_moisture=trigger_moisture,
                threshold_at_trigger=threshold_at_trigger,
                post_moisture=post_moisture,
            )

            self._repo.update_execution_log_post_moisture(
                log_id,
                post_moisture=float(post_moisture),
                post_measured_at_utc=iso_now(),
                delta_moisture=delta_moisture,
                recommendation=recommendation,
            )

            results.append({"log_id": log_id, "post_moisture": post_moisture})

        return results

    def _execute_irrigation(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute irrigation for a single request.
        
        Uses IrrigationCalculator for data-driven duration when available,
        falling back to configurable default duration.

        Safety: if a valve is configured, it must open before the pump starts.
        The pump will not run when the valve open fails, and the valve is
        closed on completion or failure.
        """
        request_id = request["request_id"]
        unit_id = request["unit_id"]
        actuator_id = request.get("actuator_id")
        plant_id = request.get("plant_id")

        logger.info(f"Executing irrigation for request {request_id}, unit {unit_id}")

        # Record if this was auto-executed (no user response)
        if not request.get("user_response"):
            config = self.get_config(unit_id)
            if config.ml_learning_enabled:
                self._repo.update_preference_on_response(
                    request["user_id"], UserResponse.AUTO, 0, unit_id
                )
                self._repo.mark_ml_collected(request_id, preference_score=0.0)

        # Execute via actuator manager
        if not self._actuator_service or not actuator_id:
            error = "No actuator available"
            logger.warning("No actuator manager or actuator ID for request %s", request_id)
            self._repo.create_execution_log(
                request_id=request_id,
                user_id=request.get("user_id"),
                unit_id=unit_id,
                plant_id=plant_id,
                sensor_id=str(request.get("sensor_id")) if request.get("sensor_id") is not None else None,
                trigger_reason="below_threshold",
                trigger_moisture=request.get("soil_moisture_detected"),
                threshold_at_trigger=request.get("soil_moisture_threshold"),
                triggered_at_utc=request.get("detected_at") or iso_now(),
                planned_duration_s=None,
                pump_actuator_id=str(actuator_id) if actuator_id is not None else None,
                valve_actuator_id=None,
                assumed_flow_ml_s=None,
                estimated_volume_ml=None,
                execution_status="failed",
                execution_error=error,
                executed_at_utc=iso_now(),
                post_moisture_delay_s=self._post_capture_delay_seconds,
            )
            self._repo.record_execution(
                request_id,
                success=False,
                error=error,
            )
            return {
                "request_id": request_id,
                "success": False,
                "error": error,
            }

        # Calculate irrigation duration using IrrigationCalculator if available
        irrigation_duration = self._calculate_irrigation_duration(
            plant_id=plant_id,
            actuator_id=actuator_id,
            request=request,
        )
        irrigation_duration = int(min(irrigation_duration, self._max_duration_seconds))

        valve_actuator_id = self._resolve_valve_actuator_id(plant_id)

        lock_seconds = max(60, int(irrigation_duration) + 120)
        if not self._repo.acquire_unit_lock(unit_id, lock_seconds, iso_now()):
            error = "Unit irrigation lock busy"
            self._repo.create_execution_log(
                request_id=request_id,
                user_id=request.get("user_id"),
                unit_id=unit_id,
                plant_id=plant_id,
                sensor_id=str(request.get("sensor_id")) if request.get("sensor_id") is not None else None,
                trigger_reason="below_threshold",
                trigger_moisture=request.get("soil_moisture_detected"),
                threshold_at_trigger=request.get("soil_moisture_threshold"),
                triggered_at_utc=request.get("detected_at") or iso_now(),
                planned_duration_s=int(irrigation_duration),
                pump_actuator_id=str(actuator_id),
                valve_actuator_id=str(valve_actuator_id) if valve_actuator_id is not None else None,
                assumed_flow_ml_s=None,
                estimated_volume_ml=None,
                execution_status="failed",
                execution_error=error,
                executed_at_utc=iso_now(),
                post_moisture_delay_s=self._post_capture_delay_seconds,
            )
            self._repo.record_execution(
                request_id,
                success=False,
                error=error,
            )
            return {
                "request_id": request_id,
                "success": False,
                "error": error,
            }

        log_created = False
        started_at = None
        flow_rate = None
        estimated_volume_ml = None

        # Turn on water pump
        try:
            def close_valve() -> None:
                if valve_actuator_id is None or not self._actuator_service:
                    return
                try:
                    self._actuator_service.turn_off(int(valve_actuator_id))
                except Exception:
                    logger.debug("Failed to close valve actuator %s", valve_actuator_id)

            if valve_actuator_id is not None:
                valve_result = self._actuator_service.turn_on(int(valve_actuator_id))
                if valve_result.state in {ActuatorState.ERROR, ActuatorState.UNAVAILABLE}:
                    error = valve_result.error_message or "Valve open failed"
                    self._repo.create_execution_log(
                        request_id=request_id,
                        user_id=request.get("user_id"),
                        unit_id=unit_id,
                        plant_id=plant_id,
                        sensor_id=str(request.get("sensor_id")) if request.get("sensor_id") is not None else None,
                        trigger_reason="below_threshold",
                        trigger_moisture=request.get("soil_moisture_detected"),
                        threshold_at_trigger=request.get("soil_moisture_threshold"),
                        triggered_at_utc=request.get("detected_at") or iso_now(),
                        planned_duration_s=int(irrigation_duration),
                        pump_actuator_id=str(actuator_id),
                        valve_actuator_id=str(valve_actuator_id),
                        assumed_flow_ml_s=None,
                        estimated_volume_ml=None,
                        execution_status="failed",
                        execution_error=error,
                        executed_at_utc=iso_now(),
                        post_moisture_delay_s=self._post_capture_delay_seconds,
                    )
                    self._repo.record_execution(
                        request_id,
                        success=False,
                        error=error,
                    )
                    self._repo.release_unit_lock(unit_id)
                    return {
                        "request_id": request_id,
                        "success": False,
                        "error": error,
                    }

            started_at = iso_now()
            if not self._repo.mark_execution_started(
                request_id=request_id,
                started_at_utc=started_at,
                planned_duration_seconds=int(irrigation_duration),
            ):
                raise Exception("Failed to mark execution start")

            if self._pump_calibration:
                flow_rate = self._pump_calibration.get_flow_rate(actuator_id)
                if flow_rate is not None:
                    estimated_volume_ml = float(flow_rate) * float(irrigation_duration)

            log_id = self._repo.create_execution_log(
                request_id=request_id,
                user_id=request.get("user_id"),
                unit_id=unit_id,
                plant_id=plant_id,
                sensor_id=str(request.get("sensor_id")) if request.get("sensor_id") is not None else None,
                trigger_reason="below_threshold",
                trigger_moisture=request.get("soil_moisture_detected"),
                threshold_at_trigger=request.get("soil_moisture_threshold"),
                triggered_at_utc=request.get("detected_at") or started_at,
                planned_duration_s=int(irrigation_duration),
                pump_actuator_id=str(actuator_id),
                valve_actuator_id=str(valve_actuator_id) if valve_actuator_id is not None else None,
                assumed_flow_ml_s=flow_rate,
                estimated_volume_ml=estimated_volume_ml,
                execution_status="started",
                execution_error=None,
                executed_at_utc=started_at,
                post_moisture_delay_s=self._post_capture_delay_seconds,
            )
            if log_id is None:
                raise Exception("Failed to create execution log")
            log_created = True

            result = self._actuator_service.turn_on(actuator_id)

            if result.state == ActuatorState.ERROR:
                raise Exception(result.error_message or "Actuator error")

            return {
                "request_id": request_id,
                "success": True,
                "status": "started",
                "duration_seconds": int(irrigation_duration),
            }

        except Exception as e:
            logger.error(f"Irrigation failed for request {request_id}: {e}")

            # Try to turn off actuator
            try:
                if self._actuator_service and actuator_id:
                    self._actuator_service.turn_off(actuator_id)
            except Exception:
                pass
            try:
                close_valve()
            except Exception:
                pass

            if log_created:
                self._repo.update_execution_log_status(
                    request_id,
                    execution_status="failed",
                    execution_error=str(e),
                )
            else:
                self._repo.create_execution_log(
                    request_id=request_id,
                    user_id=request.get("user_id"),
                    unit_id=unit_id,
                    plant_id=plant_id,
                    sensor_id=str(request.get("sensor_id")) if request.get("sensor_id") is not None else None,
                    trigger_reason="below_threshold",
                    trigger_moisture=request.get("soil_moisture_detected"),
                    threshold_at_trigger=request.get("soil_moisture_threshold"),
                    triggered_at_utc=request.get("detected_at") or iso_now(),
                    planned_duration_s=int(irrigation_duration),
                    pump_actuator_id=str(actuator_id),
                    valve_actuator_id=str(valve_actuator_id) if valve_actuator_id is not None else None,
                    assumed_flow_ml_s=flow_rate,
                    estimated_volume_ml=estimated_volume_ml,
                    execution_status="failed",
                    execution_error=str(e),
                    executed_at_utc=started_at or iso_now(),
                    post_moisture_delay_s=self._post_capture_delay_seconds,
                )
            self._repo.record_execution(
                request_id,
                success=False,
                error=str(e),
            )
            self._repo.release_unit_lock(unit_id)

            return {
                "request_id": request_id,
                "success": False,
                "error": str(e),
            }

    def _calculate_irrigation_duration(
        self,
        plant_id: Optional[int],
        actuator_id: int,
        request: Dict[str, Any],
    ) -> int:
        """
        Calculate irrigation duration using IrrigationCalculator if available.
        
        Falls back to default duration if calculator not configured or plant not found.
        
        Args:
            plant_id: Optional plant ID for plant-specific calculation
            actuator_id: Pump actuator ID for flow rate lookup
            request: Irrigation request with context data
            
        Returns:
            Duration in seconds
        """
        default_duration = 30  # Fallback default
        min_duration = 5
        max_duration = max(min_duration, int(self._max_duration_seconds))

        def apply_volume_adjustment(duration_seconds: int, ml_adjusted: bool = False) -> int:
            user_id = request.get("user_id") if request else None
            unit_id = request.get("unit_id") if request else None
            if ml_adjusted or not user_id or not unit_id:
                return int(max(min_duration, min(max_duration, duration_seconds)))

            factor = self._get_volume_adjustment_factor(int(user_id), int(unit_id))
            if factor == 1.0:
                return int(max(min_duration, min(max_duration, duration_seconds)))

            adjusted = int(round(duration_seconds * factor))
            adjusted = int(max(min_duration, min(max_duration, adjusted)))
            logger.info(
                "Applied volume feedback adjustment factor %.2f for unit %s: %ds -> %ds",
                factor,
                unit_id,
                duration_seconds,
                adjusted,
            )
            return adjusted
        
        # Try to use IrrigationCalculator for data-driven duration
        if self._irrigation_calculator and plant_id:
            try:
                # Get pump flow rate from calibration service
                flow_rate = None
                if self._pump_calibration:
                    flow_rate = self._pump_calibration.get_flow_rate(actuator_id)
                
                # Build environmental data from ML context if available
                environmental_data = None
                if request:
                    env_fields = {
                        'temperature': request.get('temperature_at_detection'),
                        'humidity': request.get('humidity_at_detection'),
                        'vpd': request.get('vpd_at_detection'),
                        'lux': request.get('lux_at_detection'),
                        'soil_moisture': request.get('soil_moisture_detected'),
                    }
                    # Only include fields that have values (not None)
                    environmental_data = {k: v for k, v in env_fields.items() if v is not None}
                    if not environmental_data:
                        environmental_data = None
                
                # Use calculate_with_ml if environmental data available, otherwise calculate()
                # calculate_with_ml will fall back to formula-based if ML predictor unavailable
                if environmental_data:
                    calculation = self._irrigation_calculator.calculate_with_ml(
                        plant_id=plant_id,
                        pump_flow_rate=flow_rate,
                        environmental_data=environmental_data,
                    )
                    logger.info(
                        "Calculated irrigation with ML for plant %s: %d seconds (%.1f ml, confidence=%.2f, ml_adjusted=%s)",
                        plant_id,
                        calculation.duration_seconds,
                        calculation.water_volume_ml,
                        calculation.confidence,
                        calculation.ml_adjusted,
                    )
                else:
                    # Fall back to formula-based calculation if no environmental data
                    calculation = self._irrigation_calculator.calculate(
                        plant_id=plant_id,
                        pump_flow_rate=flow_rate,
                    )
                    logger.info(
                        "Calculated irrigation (formula-based) for plant %s: %d seconds (%.1f ml, confidence=%.2f)",
                        plant_id,
                        calculation.duration_seconds,
                        calculation.water_volume_ml,
                        calculation.confidence,
                    )
                
                return apply_volume_adjustment(
                    calculation.duration_seconds,
                    ml_adjusted=calculation.ml_adjusted,
                )
                
            except Exception as e:
                logger.warning(
                    "IrrigationCalculator failed for plant %s, using default: %s",
                    plant_id, e
                )
        
        # Fallback: Use default duration
        logger.debug(
            "Using default irrigation duration %ds for request (no calculator or plant_id)",
            default_duration,
        )
        return apply_volume_adjustment(default_duration, ml_adjusted=False)

    def _handle_expired_requests(self) -> None:
        """Handle expired pending requests."""
        expired = self._repo.get_expired_requests()

        for request in expired:
            self._repo.update_status(request["request_id"], RequestStatus.EXPIRED)
            logger.info(f"Request {request['request_id']} expired")

    def _schedule_feedback_request(self, request: Dict[str, Any], config: WorkflowConfig) -> None:
        """Schedule feedback request after irrigation."""
        if not self._notifications:
            return

        # For immediate feedback request (could be delayed via scheduler)
        try:
            from app.services.application.notifications_service import IrrigationFeedbackResponse

            feedback_id = self._notifications.request_irrigation_feedback(
                user_id=request["user_id"],
                unit_id=request["unit_id"],
                plant_id=request.get("plant_id"),
                soil_moisture_before=request.get("soil_moisture_detected"),
                actuator_id=request.get("actuator_id"),
            )

            if feedback_id:
                self._repo.link_feedback(request["request_id"], feedback_id)

        except Exception as e:
            logger.error(f"Failed to request feedback for request {request['request_id']}: {e}")

    def _get_current_moisture(self, plant_id: Optional[int], unit_id: Optional[int]) -> Optional[float]:
        """Fetch the latest moisture reading for a plant or unit."""
        if not self._plant_service:
            return None

        plant = None
        if plant_id is not None:
            plant = self._plant_service.get_plant(plant_id, unit_id=unit_id)
        elif unit_id is not None:
            plant = self._plant_service.get_active_plant(unit_id)

        if not plant:
            return None

        moisture = getattr(plant, "moisture_level", None)
        if moisture is None:
            return None
        return float(moisture)

    def _get_volume_adjustment_factor(self, user_id: int, unit_id: int) -> float:
        """Compute duration adjustment factor from user volume feedback history."""
        preference = self._repo.get_user_preference(user_id, unit_id)
        if not preference:
            return 1.0

        too_little = int(preference.get("too_little_feedback_count") or 0)
        too_much = int(preference.get("too_much_feedback_count") or 0)
        just_right = int(preference.get("just_right_feedback_count") or 0)
        total = too_little + too_much + just_right

        if total < 3:
            return 1.0

        net = (too_little - too_much) / float(total)
        adjustment = net * 0.1  # Max +/-10%
        factor = 1.0 + adjustment
        return max(0.8, min(1.2, factor))

    def _classify_attribution(
        self,
        *,
        trigger_moisture: Optional[float],
        threshold_at_trigger: Optional[float],
        post_moisture: Optional[float],
    ) -> str:
        """
        Classify irrigation outcomes to separate timing vs volume issues.

        Returns recommendation labels:
        - adjust_threshold: triggered at/above threshold
        - adjust_duration: post watering overshoot/undershoot
        - sensor_issue/unknown: invalid or missing data
        """
        if trigger_moisture is None or threshold_at_trigger is None or post_moisture is None:
            return "unknown"

        for value in (trigger_moisture, threshold_at_trigger, post_moisture):
            if value < 0 or value > 100:
                return "sensor_issue"

        epsilon = 0.01
        target_high = threshold_at_trigger + float(self._hysteresis_margin)

        if trigger_moisture >= threshold_at_trigger - epsilon:
            return "adjust_threshold"
        if post_moisture > target_high:
            return "adjust_duration"
        if post_moisture < threshold_at_trigger - epsilon:
            return "adjust_duration"

        return "unknown"

    # ==================== Feedback Handling ====================

    def _resolve_threshold_feedback_from_volume(
        self,
        response: IrrigationFeedback,
        execution_log: Optional[Dict[str, Any]],
    ) -> Optional[IrrigationFeedback]:
        """Map volume feedback to threshold adjustment when moisture is within band."""
        if not execution_log:
            return None

        post_moisture = execution_log.get("post_moisture")
        threshold_at_trigger = execution_log.get("threshold_at_trigger")
        if post_moisture is None or threshold_at_trigger is None:
            return None

        try:
            post_value = float(post_moisture)
            threshold_value = float(threshold_at_trigger)
        except (TypeError, ValueError):
            return None

        epsilon = 0.01
        target_high = threshold_value + float(self._hysteresis_margin)

        if response == IrrigationFeedback.TOO_MUCH:
            if post_value <= target_high + epsilon:
                return IrrigationFeedback.TOO_MUCH
            return None

        if response == IrrigationFeedback.TOO_LITTLE:
            if post_value >= threshold_value - epsilon:
                return IrrigationFeedback.TOO_LITTLE
            return None

        return None

    def _apply_soil_moisture_adjustment(
        self,
        *,
        unit_id: int,
        plant_id: Optional[int],
        current_threshold: float,
        adjustment: float,
    ) -> None:
        """Apply a soil moisture threshold adjustment at plant or unit scope."""
        new_threshold = max(0.0, min(100.0, current_threshold + float(adjustment)))
        if plant_id is not None and self._plant_service:
            updated = self._plant_service.update_soil_moisture_threshold(
                plant_id=int(plant_id),
                threshold=new_threshold,
                unit_id=unit_id,
            )
            if not updated:
                logger.error(
                    "Failed to update soil moisture threshold for plant %s (unit %s)",
                    plant_id,
                    unit_id,
                )
            return

        if self._threshold_adjustment_callback:
            try:
                self._threshold_adjustment_callback(
                    unit_id=unit_id,
                    metric="soil_moisture",
                    adjustment=float(adjustment),
                )
            except Exception as exc:
                logger.error("Failed to apply unit threshold adjustment: %s", exc)
            return

        logger.warning(
            "No threshold adjustment handler available for unit %s (plant %s)",
            unit_id,
            plant_id,
        )

    def handle_feedback(
        self,
        request_id: int,
        feedback_response: str | IrrigationFeedback,
        user_id: int,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle user feedback on irrigation amount.

        Args:
            request_id: The irrigation request ID
            feedback_response: 'too_little', 'just_right', 'too_much',
                'triggered_too_early', 'triggered_too_late', or 'skipped'
            user_id: User providing feedback
            notes: Optional notes

        Returns:
            Result dictionary
        """
        request = self._repo.get_request(request_id)
        if not request:
            return {"ok": False, "error": "Request not found"}

        config = self.get_config(request["unit_id"])

        try:
            response = (
                feedback_response
                if isinstance(feedback_response, IrrigationFeedback)
                else IrrigationFeedback(str(feedback_response))
            )
        except ValueError:
            return {"ok": False, "error": "Invalid feedback response"}

        volume_feedback = {
            IrrigationFeedback.TOO_LITTLE,
            IrrigationFeedback.JUST_RIGHT,
            IrrigationFeedback.TOO_MUCH,
        }
        timing_feedback = {
            IrrigationFeedback.TRIGGERED_TOO_EARLY,
            IrrigationFeedback.TRIGGERED_TOO_LATE,
        }

        feedback_id = request.get("feedback_id")
        if self._notifications and feedback_id:
            self._notifications.submit_irrigation_feedback(
                feedback_id=feedback_id,
                response=response.value,
                notes=notes,
            )

        # Update user preference statistics
        if config.ml_learning_enabled and response in volume_feedback:
            self._repo.update_moisture_feedback(
                user_id, response.value, request["unit_id"]
            )

        execution_log = self._repo.get_latest_execution_log_for_request(request_id)
        recommendation = execution_log.get("recommendation") if execution_log else None

        # Calculate threshold adjustment
        adjustment = None
        bayesian_result = None
        plant_id = request.get("plant_id")
        current_threshold = float(request.get("soil_moisture_threshold", 50.0))

        threshold_feedback = None
        if response in timing_feedback:
            if response == IrrigationFeedback.TRIGGERED_TOO_EARLY:
                threshold_feedback = IrrigationFeedback.TOO_MUCH
            else:
                threshold_feedback = IrrigationFeedback.TOO_LITTLE
        elif response in volume_feedback:
            threshold_feedback = self._resolve_threshold_feedback_from_volume(
                response, execution_log
            )

        if threshold_feedback is None and recommendation == "adjust_threshold":
            if response == IrrigationFeedback.TOO_MUCH:
                threshold_feedback = IrrigationFeedback.TOO_MUCH
            elif response == IrrigationFeedback.TOO_LITTLE:
                threshold_feedback = IrrigationFeedback.TOO_LITTLE

        if threshold_feedback and config.ml_threshold_adjustment_enabled:
            # Use Bayesian adjuster if available (intelligent learning)
            if self._bayesian_adjuster:
                try:
                    bayesian_result = self._bayesian_adjuster.update_from_feedback(
                        unit_id=request["unit_id"],
                        user_id=user_id,
                        feedback=threshold_feedback.value,
                        current_threshold=current_threshold,
                        soil_moisture_at_request=request.get("soil_moisture_detected", 45.0),
                        plant_type=request.get("plant_type", "default"),
                        growth_stage=request.get("growth_stage", "Vegetative"),
                    )
                    
                    # Only apply if adjustment is significant
                    if bayesian_result.direction != "maintain" and bayesian_result.adjustment_amount >= 1.0:
                        adjustment = bayesian_result.adjustment_amount
                        if bayesian_result.direction == "decrease":
                            adjustment = -adjustment
                        
                        self._apply_soil_moisture_adjustment(
                            unit_id=request["unit_id"],
                            plant_id=plant_id,
                            current_threshold=current_threshold,
                            adjustment=adjustment,
                        )
                        logger.info(
                            "Applied Bayesian threshold adjustment of %.1f%% "
                            "for unit %s (confidence: %.0f%%)",
                            adjustment,
                            request["unit_id"],
                            bayesian_result.confidence * 100.0,
                        )
                except Exception as e:
                    logger.error(f"Bayesian adjustment failed, falling back to fixed: {e}")
                    bayesian_result = None
            
            # Fallback to fixed ±5% adjustment if Bayesian not available
            if bayesian_result is None:
                if threshold_feedback == IrrigationFeedback.TOO_LITTLE:
                    adjustment = 5.0  # Increase threshold
                elif threshold_feedback == IrrigationFeedback.TOO_MUCH:
                    adjustment = -5.0  # Decrease threshold

                if adjustment:
                    self._apply_soil_moisture_adjustment(
                        unit_id=request["unit_id"],
                        plant_id=plant_id,
                        current_threshold=current_threshold,
                        adjustment=adjustment,
                    )
                    logger.info(
                        "Applied fixed threshold adjustment of %.1f%% for unit %s",
                        adjustment,
                        request["unit_id"],
                    )

        logger.info(
            "Received feedback '%s' for request %s from user %s",
            response.value,
            request_id,
            user_id,
        )

        result = {
            "ok": True,
            "message": "Thank you for your feedback!",
            "adjustment_applied": adjustment is not None,
        }
        
        # Include Bayesian learning info if available
        if bayesian_result:
            result["learning"] = {
                "method": "bayesian",
                "confidence": round(bayesian_result.confidence, 2),
                "recommended_threshold": round(bayesian_result.recommended_threshold, 1),
                "reasoning": bayesian_result.reasoning,
            }
        
        return result

    def handle_feedback_for_feedback_id(
        self,
        feedback_id: int,
        feedback_response: str | IrrigationFeedback,
        user_id: int,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle feedback submission using a feedback record ID."""
        request = self._repo.get_request_by_feedback_id(feedback_id)
        if not request:
            return {"ok": False, "error": "Request not found for feedback"}
        return self.handle_feedback(
            request_id=request["request_id"],
            feedback_response=feedback_response,
            user_id=user_id,
            notes=notes,
        )

    # ==================== Query Methods ====================

    def get_pending_requests(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get pending irrigation requests for a user."""
        return self._repo.get_requests_for_user(user_id, status=RequestStatus.PENDING, limit=limit)

    def get_request_history(self, unit_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get irrigation request history for a unit."""
        return self._repo.get_history(unit_id, limit)

    def build_irrigation_feature_inputs(
        self,
        *,
        unit_id: int,
        plant_id: Optional[int] = None,
        user_id: Optional[int] = None,
        lookback_hours: int = 7 * 24,
        history_limit: int = 200,
    ) -> Dict[str, Any]:
        """
        Build ML feature inputs directly from irrigation workflow telemetry.

        Returns a dict with:
        - current_conditions: latest moisture/threshold + eligibility context
        - irrigation_history: execution logs within the lookback window
        - user_preferences: stored irrigation preference stats
        - plant_info: growth stage + drydown model (if available)
        """
        now = utc_now()
        window_hours = max(1, int(lookback_hours))
        history_limit = max(1, int(history_limit))
        start_ts = (now - timedelta(hours=window_hours)).isoformat()
        end_ts = now.isoformat()

        irrigation_history: List[Dict[str, Any]] = []
        latest_trace: Optional[Dict[str, Any]] = None

        if self._repo:
            try:
                irrigation_history = self._repo.get_execution_logs_for_unit(
                    unit_id,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    limit=history_limit,
                    plant_id=plant_id,
                )
            except Exception as exc:
                logger.debug("Failed to load irrigation execution logs: %s", exc)

            try:
                traces = self._repo.get_eligibility_traces_for_unit(
                    unit_id,
                    start_ts=start_ts,
                    end_ts=end_ts,
                    limit=5,
                    plant_id=plant_id,
                )
                if traces:
                    traces = sorted(
                        traces,
                        key=lambda row: coerce_datetime(row.get("evaluated_at_utc"))
                        or datetime.min.replace(tzinfo=timezone.utc),
                        reverse=True,
                    )
                    latest_trace = traces[0]
            except Exception as exc:
                logger.debug("Failed to load irrigation eligibility traces: %s", exc)

        current_conditions: Dict[str, Any] = {}
        if latest_trace:
            moisture = latest_trace.get("moisture")
            threshold = latest_trace.get("threshold")
            if moisture is not None:
                current_conditions["soil_moisture"] = moisture
            if threshold is not None:
                current_conditions["soil_moisture_threshold"] = threshold
                current_conditions["threshold"] = threshold

            evaluated_at = coerce_datetime(latest_trace.get("evaluated_at_utc"))
            if evaluated_at:
                age_seconds = max(0.0, (now - evaluated_at).total_seconds())
                current_conditions["stale_reading_seconds"] = age_seconds

        if self._repo:
            try:
                config = self.get_config(unit_id)
                current_conditions["manual_mode"] = bool(config.manual_mode_enabled)
            except Exception as exc:
                logger.debug("Failed to load workflow config: %s", exc)

            try:
                current_conditions["pending_request"] = self._repo.has_active_request(
                    unit_id,
                    plant_id=plant_id,
                )
            except Exception as exc:
                logger.debug("Failed to check active irrigation request: %s", exc)

            try:
                cooldown_active = False
                if self._cooldown_minutes > 0:
                    last = self._repo.get_last_completed_irrigation(unit_id, plant_id)
                    executed_at = None
                    if last:
                        executed_at = coerce_datetime(last.get("executed_at")) or coerce_datetime(
                            last.get("executed_at_utc")
                        )
                    if executed_at:
                        cooldown_delta = timedelta(minutes=int(self._cooldown_minutes))
                        cooldown_active = (now - executed_at) < cooldown_delta
                current_conditions["cooldown_active"] = cooldown_active
            except Exception as exc:
                logger.debug("Failed to compute irrigation cooldown: %s", exc)

        user_preferences: Dict[str, Any] = {}
        if self._repo and user_id is not None:
            try:
                prefs = self._repo.get_user_preference(int(user_id), unit_id)
                if prefs:
                    user_preferences = prefs
            except Exception as exc:
                logger.debug("Failed to load irrigation user preferences: %s", exc)

        plant_info: Dict[str, Any] = {}
        resolved_plant_id = plant_id
        if resolved_plant_id is None and self._plant_service:
            active = self._plant_service.get_active_plant(unit_id)
            if active:
                resolved_plant_id = getattr(active, "plant_id", None) or getattr(active, "id", None)

        if resolved_plant_id is not None and self._plant_service:
            plant = self._plant_service.get_plant(int(resolved_plant_id), unit_id=unit_id)
            if plant:
                plant_info["growth_stage"] = getattr(plant, "current_stage", None) or "Vegetative"
                plant_info["plant_age_days"] = int(getattr(plant, "days_in_stage", 0) or 0)

        if self._repo and resolved_plant_id is not None:
            try:
                model = self._repo.get_plant_irrigation_model(int(resolved_plant_id))
                if model:
                    plant_info["drydown_rate_per_hour"] = model.get("drydown_rate_per_hour")
                    plant_info["drydown_confidence"] = model.get("confidence")
            except Exception as exc:
                logger.debug("Failed to load plant irrigation model: %s", exc)

        return {
            "current_conditions": current_conditions,
            "irrigation_history": irrigation_history,
            "user_preferences": user_preferences,
            "plant_info": plant_info,
        }

    def get_request(self, request_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific request."""
        return self._repo.get_request(request_id)

    def get_last_completed_irrigation(
        self,
        unit_id: int,
        *,
        plant_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent completed irrigation for a unit or plant."""
        try:
            return self._repo.get_last_completed_irrigation(unit_id, plant_id)
        except Exception as exc:
            logger.debug("Failed to fetch last completed irrigation for unit %s: %s", unit_id, exc)
            return None

    def get_user_preferences(self, user_id: int, unit_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get user irrigation preferences."""
        return self._repo.get_user_preference(user_id, unit_id)

    # ==================== Scheduler Integration ====================

    def register_scheduled_tasks(self) -> None:
        """Register scheduled tasks via SchedulingService (preferred)."""
        if self._scheduling_service:
            self._scheduling_service.register_interval_task(
                task_name="irrigation.execute_due_requests",
                func=self.execute_due_requests,
                interval_seconds=300,
                job_id="irrigation_due_check",
                namespace="irrigation",
                start_immediately=False,
            )
            self._scheduling_service.register_interval_task(
                task_name="irrigation.complete_due_executions",
                func=self.complete_due_executions,
                interval_seconds=self._completion_interval_seconds,
                job_id="irrigation_execution_completion",
                namespace="irrigation",
                start_immediately=True,
            )
            self._scheduling_service.register_interval_task(
                task_name="irrigation.capture_post_moisture",
                func=self.capture_due_post_moisture,
                interval_seconds=self._post_capture_interval_seconds,
                job_id="irrigation_post_capture",
                namespace="irrigation",
                start_immediately=True,
            )
            logger.info("Registered irrigation workflow scheduled tasks via SchedulingService")
            return

        if not self._scheduler:
            logger.warning("No scheduler available, skipping task registration")
            return

        # Register the execution check task
        @self._scheduler.task("irrigation.execute_due_requests")
        def execute_due_requests_task():
            return self.execute_due_requests()

        @self._scheduler.task("irrigation.complete_due_executions")
        def complete_due_executions_task():
            return self.complete_due_executions()

        @self._scheduler.task("irrigation.capture_post_moisture")
        def capture_post_moisture_task():
            return self.capture_due_post_moisture()

        # Schedule to run every 5 minutes to check for due requests
        self._scheduler.schedule_interval(
            task_name="irrigation.execute_due_requests",
            interval_seconds=300,  # 5 minutes
            job_id="irrigation_due_check",
            namespace="irrigation",
        )

        self._scheduler.schedule_interval(
            task_name="irrigation.complete_due_executions",
            interval_seconds=self._completion_interval_seconds,
            job_id="irrigation_execution_completion",
            namespace="irrigation",
            start_immediately=True,
        )

        self._scheduler.schedule_interval(
            task_name="irrigation.capture_post_moisture",
            interval_seconds=self._post_capture_interval_seconds,
            job_id="irrigation_post_capture",
            namespace="irrigation",
            start_immediately=True,
        )

        logger.info("Registered irrigation workflow scheduled tasks via UnifiedScheduler fallback")
