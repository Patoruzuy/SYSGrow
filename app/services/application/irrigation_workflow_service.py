"""
Irrigation Workflow Service — Thin Facade
==========================================

Sprint 4 refactoring: the original 2,193-line god service has been split
into three focused sub-services.  This facade preserves the public API
so that **no callers need to change** (blueprints, container, scheduler).

Sub-services:
    * ``IrrigationDetectionService``  – eligibility checks, skip logic, notifications
    * ``IrrigationExecutionService``  – scheduled execution, completion, valve/pump
    * ``IrrigationFeedbackService``   – user response, feedback, Bayesian learning
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable

from app.defaults import SystemConfigDefaults
from app.enums import (
    IrrigationEligibilityDecision,
    IrrigationFeedback,
    IrrigationSkipReason,
)
from app.services.application.irrigation_detection_service import IrrigationDetectionService
from app.services.application.irrigation_execution_service import IrrigationExecutionService
from app.services.application.irrigation_feedback_service import IrrigationFeedbackService
from app.utils.cache import TTLCache
from app.utils.time import coerce_datetime, utc_now

if TYPE_CHECKING:
    from app.domain.irrigation_calculator import IrrigationCalculator
    from app.services.ai.bayesian_threshold import BayesianThresholdAdjuster
    from app.services.application.notifications_service import NotificationsService
    from app.services.application.plant_service import PlantViewService
    from app.services.hardware.actuator_management_service import ActuatorManagementService
    from app.services.hardware.pump_calibration import PumpCalibrationService
    from app.workers.unified_scheduler import UnifiedScheduler
    from infrastructure.database.repositories.irrigation_workflow import IrrigationWorkflowRepository

logger = logging.getLogger(__name__)

# Type alias for backwards compatibility
ActuatorManager = "ActuatorManagementService"


# ── Shared Constants (re-exported for consumers) ─────────────────


class RequestStatus:
    """Pending irrigation request status constants."""

    PENDING = "pending"
    APPROVED = "approved"
    DELAYED = "delayed"
    EXECUTED = "executed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    FAILED = "failed"


class UserResponse:
    """User response types."""

    APPROVE = "approve"
    DELAY = "delay"
    CANCEL = "cancel"
    AUTO = "auto"


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
    def from_dict(cls, data: dict[str, Any]) -> "WorkflowConfig":
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

    def to_dict(self) -> dict[str, Any]:
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
    Backward-compatible façade that delegates to focused sub-services.

    Workflow:
    1. detect_irrigation_need() → IrrigationDetectionService
    2. handle_user_response()   → IrrigationFeedbackService
    3. execute_due_requests()   → IrrigationExecutionService
    4. handle_feedback()        → IrrigationFeedbackService
    """

    def __init__(
        self,
        workflow_repo: "IrrigationWorkflowRepository",
        notifications_service: "NotificationsService" | None = None,
        actuator_service: "ActuatorManagementService" | None = None,
        scheduler: "UnifiedScheduler" | None = None,
        scheduling_service: Any | None = None,
        bayesian_adjuster: "BayesianThresholdAdjuster" | None = None,
        irrigation_calculator: "IrrigationCalculator" | None = None,
        pump_calibration_service: "PumpCalibrationService" | None = None,
        plant_service: "PlantViewService" | None = None,
        completion_interval_seconds: int | None = None,
        post_capture_interval_seconds: int | None = None,
        post_capture_delay_seconds: int | None = None,
        hysteresis_margin: float | None = None,
    ):
        self._repo = workflow_repo
        self._notifications = notifications_service
        self._actuator_service = actuator_service
        self._scheduler = scheduler
        self._scheduling_service = scheduling_service
        self._bayesian_adjuster = bayesian_adjuster
        self._irrigation_calculator = irrigation_calculator
        self._pump_calibration = pump_calibration_service
        self._plant_service = plant_service

        self._config_cache: TTLCache = TTLCache(enabled=True, ttl_seconds=300, maxsize=64)
        self._lock = threading.Lock()

        self._threshold_adjustment_callback: Callable | None = None

        # Env config
        self._completion_interval_seconds = (
            completion_interval_seconds
            if completion_interval_seconds is not None
            else _read_int_env("SYSGROW_IRRIGATION_COMPLETION_INTERVAL_SECONDS", 5)
        )
        self._post_capture_interval_seconds = (
            post_capture_interval_seconds
            if post_capture_interval_seconds is not None
            else _read_int_env("SYSGROW_IRRIGATION_POST_CAPTURE_INTERVAL_SECONDS", 60)
        )
        self._post_capture_delay_seconds = (
            post_capture_delay_seconds
            if post_capture_delay_seconds is not None
            else _read_int_env("SYSGROW_IRRIGATION_POST_CAPTURE_DELAY_SECONDS", 15 * 60)
        )
        self._max_duration_seconds = _read_int_env("SYSGROW_IRRIGATION_MAX_DURATION_SECONDS", 900)
        self._hysteresis_margin = (
            hysteresis_margin
            if hysteresis_margin is not None
            else _read_float_env("SYSGROW_IRRIGATION_HYSTERESIS", float(SystemConfigDefaults.HYSTERESIS))
        )
        self._stale_reading_seconds = _read_int_env("SYSGROW_IRRIGATION_STALE_READING_SECONDS", 30 * 60)
        self._cooldown_minutes = _read_int_env("SYSGROW_IRRIGATION_COOLDOWN_MINUTES", 60)
        self._sensor_missing_alert_minutes = _read_int_env("SYSGROW_IRRIGATION_SENSOR_MISSING_ALERT_MINUTES", 60)

        # ---- build sub-services ----
        self._detection = IrrigationDetectionService(
            repo=workflow_repo,
            get_config=self.get_config,
            notifications=notifications_service,
            plant_service=plant_service,
            stale_reading_seconds=self._stale_reading_seconds,
            cooldown_minutes=self._cooldown_minutes,
            sensor_missing_alert_minutes=self._sensor_missing_alert_minutes,
        )
        self._execution = IrrigationExecutionService(
            repo=workflow_repo,
            get_config=self.get_config,
            actuator_service=actuator_service,
            notifications=notifications_service,
            irrigation_calculator=irrigation_calculator,
            pump_calibration=pump_calibration_service,
            plant_service=plant_service,
            max_duration_seconds=self._max_duration_seconds,
            post_capture_delay_seconds=self._post_capture_delay_seconds,
            hysteresis_margin=self._hysteresis_margin,
        )
        self._feedback = IrrigationFeedbackService(
            repo=workflow_repo,
            get_config=self.get_config,
            notifications=notifications_service,
            bayesian_adjuster=bayesian_adjuster,
            plant_service=plant_service,
            hysteresis_margin=self._hysteresis_margin,
        )

        logger.info("IrrigationWorkflowService initialized")

    # ══════════════════════════════════════════════════════════════════
    # Setters (circular dependency resolution)
    # ══════════════════════════════════════════════════════════════════

    def set_notifications_service(self, service: "NotificationsService") -> None:
        self._notifications = service
        self._detection.set_notifications_service(service)
        self._execution.set_notifications_service(service)
        self._feedback.set_notifications_service(service)

    def set_actuator_manager(self, manager: "ActuatorManagementService") -> None:
        self._actuator_service = manager
        self._execution.set_actuator_manager(manager)

    def set_scheduler(self, scheduler: "UnifiedScheduler") -> None:
        self._scheduler = scheduler

    def set_scheduling_service(self, service: Any) -> None:
        self._scheduling_service = service

    def set_threshold_callback(self, callback: Callable) -> None:
        self._threshold_adjustment_callback = callback
        self._feedback.set_threshold_callback(callback)

    def set_bayesian_adjuster(self, adjuster: "BayesianThresholdAdjuster") -> None:
        self._bayesian_adjuster = adjuster
        self._feedback.set_bayesian_adjuster(adjuster)
        logger.info("Bayesian threshold adjuster configured")

    def set_irrigation_calculator(self, calculator: "IrrigationCalculator") -> None:
        self._irrigation_calculator = calculator
        self._execution.set_irrigation_calculator(calculator)
        logger.info("Irrigation calculator configured")

    def set_pump_calibration_service(self, service: "PumpCalibrationService") -> None:
        self._pump_calibration = service
        self._execution.set_pump_calibration_service(service)
        logger.info("Pump calibration service configured")

    def set_plant_service(self, service: "PlantViewService") -> None:
        self._plant_service = service
        self._detection.set_plant_service(service)
        self._execution.set_plant_service(service)
        self._feedback.set_plant_service(service)
        logger.info("Plant service configured for irrigation workflow")

    # ══════════════════════════════════════════════════════════════════
    # Configuration
    # ══════════════════════════════════════════════════════════════════

    def get_config(self, unit_id: int) -> WorkflowConfig:
        cached = self._config_cache.get(unit_id)
        if cached is not None:
            return cached
        data = self._repo.get_config(unit_id)
        config = WorkflowConfig.from_dict(data) if data else WorkflowConfig()
        self._config_cache.set(unit_id, config)
        return config

    def save_config(self, unit_id: int, config: WorkflowConfig) -> bool:
        success = self._repo.save_config(unit_id, config.to_dict())
        if success:
            self._config_cache.set(unit_id, config)
        return success

    def update_config(self, unit_id: int, updates: dict[str, Any]) -> bool:
        current = self.get_config(unit_id)
        for key, value in updates.items():
            if hasattr(current, key):
                setattr(current, key, value)
        return self.save_config(unit_id, current)

    # ══════════════════════════════════════════════════════════════════
    # Detection  (delegates → IrrigationDetectionService)
    # ══════════════════════════════════════════════════════════════════

    def detect_irrigation_need(
        self,
        unit_id: int,
        soil_moisture: float,
        threshold: float,
        user_id: int,
        plant_id: int | None = None,
        actuator_id: int | None = None,
        sensor_id: int | None = None,
        reading_timestamp: str | None = None,
        plant_name: str | None = None,
        plant_pump_assigned: bool = False,
        temperature: float | None = None,
        humidity: float | None = None,
        vpd: float | None = None,
        lux: float | None = None,
        plant_type: str | None = None,
        growth_stage: str | None = None,
    ) -> int | None:
        return self._detection.detect_irrigation_need(
            unit_id=unit_id,
            soil_moisture=soil_moisture,
            threshold=threshold,
            user_id=user_id,
            plant_id=plant_id,
            actuator_id=actuator_id,
            sensor_id=sensor_id,
            reading_timestamp=reading_timestamp,
            plant_name=plant_name,
            plant_pump_assigned=plant_pump_assigned,
            temperature=temperature,
            humidity=humidity,
            vpd=vpd,
            lux=lux,
            plant_type=plant_type,
            growth_stage=growth_stage,
            get_last_completed_irrigation=self.get_last_completed_irrigation,
        )

    def record_eligibility_trace(
        self,
        *,
        unit_id: int,
        plant_id: int | None,
        sensor_id: int | None,
        moisture: float | None,
        threshold: float | None,
        decision: IrrigationEligibilityDecision,
        skip_reason: IrrigationSkipReason | None,
    ) -> None:
        self._detection.record_eligibility_trace(
            unit_id=unit_id,
            plant_id=plant_id,
            sensor_id=sensor_id,
            moisture=moisture,
            threshold=threshold,
            decision=decision,
            skip_reason=skip_reason,
        )

    # ══════════════════════════════════════════════════════════════════
    # Execution  (delegates → IrrigationExecutionService)
    # ══════════════════════════════════════════════════════════════════

    def execute_due_requests(self) -> list[dict[str, Any]]:
        return self._execution.execute_due_requests()

    def complete_due_executions(self) -> list[dict[str, Any]]:
        return self._execution.complete_due_executions()

    def capture_due_post_moisture(self) -> list[dict[str, Any]]:
        return self._execution.capture_due_post_moisture()

    # ══════════════════════════════════════════════════════════════════
    # User Response & Feedback  (delegates → IrrigationFeedbackService)
    # ══════════════════════════════════════════════════════════════════

    def handle_user_response(
        self,
        request_id: int,
        response: str,
        user_id: int,
        delay_minutes: int | None = None,
    ) -> dict[str, Any]:
        return self._feedback.handle_user_response(request_id, response, user_id, delay_minutes)

    def handle_feedback(
        self,
        request_id: int,
        feedback_response: str | IrrigationFeedback,
        user_id: int,
        notes: str | None = None,
    ) -> dict[str, Any]:
        return self._feedback.handle_feedback(request_id, feedback_response, user_id, notes)

    def handle_feedback_for_feedback_id(
        self,
        feedback_id: int,
        feedback_response: str | IrrigationFeedback,
        user_id: int,
        notes: str | None = None,
    ) -> dict[str, Any]:
        return self._feedback.handle_feedback_for_feedback_id(feedback_id, feedback_response, user_id, notes)

    # ══════════════════════════════════════════════════════════════════
    # Query Methods
    # ══════════════════════════════════════════════════════════════════

    def get_pending_requests(self, user_id: int, limit: int = 20) -> list[dict[str, Any]]:
        return self._repo.get_requests_for_user(user_id, status=RequestStatus.PENDING, limit=limit)

    def get_request_history(self, unit_id: int, limit: int = 50) -> list[dict[str, Any]]:
        return self._repo.get_history(unit_id, limit)

    def build_irrigation_feature_inputs(
        self,
        *,
        unit_id: int,
        plant_id: int | None = None,
        user_id: int | None = None,
        lookback_hours: int = 7 * 24,
        history_limit: int = 200,
    ) -> dict[str, Any]:
        """Build ML feature inputs directly from irrigation workflow telemetry."""
        now = utc_now()
        window_hours = max(1, int(lookback_hours))
        history_limit = max(1, int(history_limit))
        start_ts = (now - timedelta(hours=window_hours)).isoformat()
        end_ts = now.isoformat()

        irrigation_history: list[dict[str, Any]] = []
        latest_trace: dict[str, Any] | None = None

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
                        key=lambda row: (
                            coerce_datetime(row.get("evaluated_at_utc")) or datetime.min.replace(tzinfo=UTC)
                        ),
                        reverse=True,
                    )
                    latest_trace = traces[0]
            except Exception as exc:
                logger.debug("Failed to load irrigation eligibility traces: %s", exc)

        current_conditions: dict[str, Any] = {}
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
                current_conditions["pending_request"] = self._repo.has_active_request(unit_id, plant_id=plant_id)
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

        user_preferences: dict[str, Any] = {}
        if self._repo and user_id is not None:
            try:
                prefs = self._repo.get_user_preference(int(user_id), unit_id)
                if prefs:
                    user_preferences = prefs
            except Exception as exc:
                logger.debug("Failed to load irrigation user preferences: %s", exc)

        plant_info: dict[str, Any] = {}
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

    def get_request(self, request_id: int) -> dict[str, Any] | None:
        return self._repo.get_request(request_id)

    def get_last_completed_irrigation(self, unit_id: int, *, plant_id: int | None = None) -> dict[str, Any] | None:
        try:
            return self._repo.get_last_completed_irrigation(unit_id, plant_id)
        except Exception as exc:
            logger.debug("Failed to fetch last completed irrigation for unit %s: %s", unit_id, exc)
            return None

    def get_user_preferences(self, user_id: int, unit_id: int | None = None) -> dict[str, Any] | None:
        return self._repo.get_user_preference(user_id, unit_id)

    # ── Telemetry query methods (Sprint 4 – layer violation fix) ─────

    def get_execution_logs(
        self,
        unit_id: int,
        *,
        start_ts: str | None = None,
        end_ts: str | None = None,
        limit: int = 200,
        plant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._repo.get_execution_logs_for_unit(
            unit_id, start_ts=start_ts, end_ts=end_ts, limit=limit, plant_id=plant_id
        )

    def get_eligibility_traces(
        self,
        unit_id: int,
        *,
        start_ts: str | None = None,
        end_ts: str | None = None,
        limit: int = 200,
        plant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._repo.get_eligibility_traces_for_unit(
            unit_id, start_ts=start_ts, end_ts=end_ts, limit=limit, plant_id=plant_id
        )

    def get_manual_irrigation_logs(
        self,
        unit_id: int,
        *,
        start_ts: str | None = None,
        end_ts: str | None = None,
        limit: int = 200,
        plant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._repo.get_manual_logs_for_unit(
            unit_id, start_ts=start_ts, end_ts=end_ts, limit=limit, plant_id=plant_id
        )

    # ══════════════════════════════════════════════════════════════════
    # Scheduler Integration
    # ══════════════════════════════════════════════════════════════════

    def register_scheduled_tasks(self) -> None:
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

        @self._scheduler.task("irrigation.execute_due_requests")
        def execute_due_requests_task():
            return self.execute_due_requests()

        @self._scheduler.task("irrigation.complete_due_executions")
        def complete_due_executions_task():
            return self.complete_due_executions()

        @self._scheduler.task("irrigation.capture_post_moisture")
        def capture_post_moisture_task():
            return self.capture_due_post_moisture()

        self._scheduler.schedule_interval(
            task_name="irrigation.execute_due_requests",
            interval_seconds=300,
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


# ── Module-level helpers ─────────────────────────────────────────


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    if not raw.strip():
        return default
    try:
        value = int(float(raw.strip()))
    except ValueError:
        return default
    return max(1, value)


def _read_float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "")
    if not raw.strip():
        return default
    try:
        value = float(raw.strip())
    except ValueError:
        return default
    return max(0.0, value)
