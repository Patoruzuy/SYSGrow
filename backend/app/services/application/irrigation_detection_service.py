"""
Irrigation Detection Service
==============================

Extracted from IrrigationWorkflowService (Sprint 4 – god-service split).

Handles irrigation need detection, eligibility checks, skip logic,
and notification dispatch when soil moisture drops below threshold.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Callable

from app.enums import (
    IrrigationEligibilityDecision,
    IrrigationSkipReason,
    NotificationSeverity,
    NotificationType,
)
from app.utils.time import coerce_datetime, iso_now, utc_now

if TYPE_CHECKING:
    from app.services.application.notifications_service import NotificationsService
    from app.services.application.plant_service import PlantViewService
    from infrastructure.database.repositories.irrigation_workflow import IrrigationWorkflowRepository

logger = logging.getLogger(__name__)


class IrrigationDetectionService:
    """Irrigation need detection, eligibility evaluation, and notification dispatch."""

    def __init__(
        self,
        repo: "IrrigationWorkflowRepository",
        get_config: Callable,
        *,
        notifications: "NotificationsService | None" = None,
        plant_service: "PlantViewService | None" = None,
        stale_reading_seconds: int = 1800,
        cooldown_minutes: int = 60,
        sensor_missing_alert_minutes: int = 60,
    ):
        self._repo = repo
        self._get_config = get_config
        self._notifications = notifications
        self._plant_service = plant_service
        self._stale_reading_seconds = stale_reading_seconds
        self._cooldown_minutes = cooldown_minutes
        self._sensor_missing_alert_minutes = sensor_missing_alert_minutes
        self._last_sensor_missing_alert: dict[str, datetime] = {}

    # ── Setters (circular dependency resolution) ─────────────────────

    def set_notifications_service(self, service: "NotificationsService") -> None:
        self._notifications = service

    def set_plant_service(self, service: "PlantViewService") -> None:
        self._plant_service = service

    # ── Main Detection ───────────────────────────────────────────────

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
        *,
        get_last_completed_irrigation: Callable | None = None,
    ) -> int | None:
        """
        Handle detection of irrigation need.

        Creates a pending request and sends notification to user
        unless manual mode or other skip conditions apply.
        """
        config = self._get_config(unit_id)

        # ---- Skip checks ------------------------------------------------
        if not config.workflow_enabled:
            logger.debug("Workflow disabled for unit %s, skipping", unit_id)
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
                logger.debug("Stale irrigation reading for unit %s (age=%.1fs), skipping", unit_id, age_seconds)
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

        # Duplicate check
        if plant_pump_assigned and (plant_id is not None or actuator_id is not None):
            if self._repo.has_active_request(unit_id, plant_id=plant_id, actuator_id=actuator_id):
                logger.debug(
                    "Active request already exists for unit %s (plant=%s actuator=%s)", unit_id, plant_id, actuator_id
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
            logger.debug("Active request already exists for unit %s", unit_id)
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

        # Cooldown check
        if self._cooldown_minutes > 0 and get_last_completed_irrigation:
            last_irrigation = get_last_completed_irrigation(unit_id, plant_id=plant_id)
            executed_at = None
            if last_irrigation:
                executed_at = coerce_datetime(last_irrigation.get("executed_at"))
            if executed_at is not None:
                cooldown_delta = timedelta(minutes=int(self._cooldown_minutes))
                if utc_now() - executed_at < cooldown_delta:
                    logger.debug("Cooldown active for unit %s, skipping irrigation request", unit_id)
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

        # ---- Create request ----------------------------------------------
        scheduled_time = self._calculate_scheduled_time(config.default_scheduled_time)
        expires_at = (utc_now() + timedelta(hours=config.expiration_hours)).isoformat()
        hours_since_last = self._calculate_hours_since_last_irrigation(unit_id)

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
            temperature_at_detection=temperature,
            humidity_at_detection=humidity,
            vpd_at_detection=vpd,
            lux_at_detection=lux,
            hours_since_last_irrigation=hours_since_last,
            plant_type=plant_type,
            growth_stage=growth_stage,
        )

        if not request_id:
            logger.error("Failed to create irrigation request for unit %s", unit_id)
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
            "Created pending irrigation request %s for unit %s: moisture=%.1f%% (threshold=%.1f%%), scheduled=%s",
            request_id,
            unit_id,
            soil_moisture,
            threshold,
            scheduled_time,
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

        # Notify user
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

    # ── Helpers ──────────────────────────────────────────────────────

    def _maybe_notify_sensor_missing(
        self,
        *,
        user_id: int,
        unit_id: int,
        sensor_id: int | None,
        plant_id: int | None,
        plant_name: str | None,
        reason: IrrigationSkipReason,
        last_seen: str | None = None,
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
        plant_id: int | None,
        sensor_id: int | None,
        moisture: float | None,
        threshold: float | None,
        decision: IrrigationEligibilityDecision,
        skip_reason: IrrigationSkipReason | None,
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
        """Public wrapper for recording an eligibility trace."""
        self._record_eligibility_trace(
            unit_id=unit_id,
            plant_id=plant_id,
            sensor_id=sensor_id,
            moisture=moisture,
            threshold=threshold,
            decision=decision,
            skip_reason=skip_reason,
        )

    def _calculate_scheduled_time(self, time_str: str) -> str:
        """Calculate next scheduled time (today or tomorrow)."""
        now = utc_now()
        hour, minute = map(int, time_str.split(":"))
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if scheduled <= now:
            scheduled += timedelta(days=1)
        return scheduled.isoformat()

    def _calculate_hours_since_last_irrigation(self, unit_id: int) -> float | None:
        """Calculate hours since last successful irrigation for ML context."""
        try:
            last_irrigation = self._repo.get_last_completed_irrigation(unit_id)
            if not last_irrigation or not last_irrigation.get("executed_at"):
                return None
            last_time = coerce_datetime(last_irrigation["executed_at"])
            if last_time is None:
                return None
            now = utc_now()
            delta = now - last_time.astimezone(UTC)
            return delta.total_seconds() / 3600
        except Exception as exc:
            logger.debug("Could not calculate hours since last irrigation: %s", exc)
            return None

    def _send_approval_notification(
        self,
        request_id: int,
        user_id: int,
        unit_id: int,
        plant_name: str | None,
        soil_moisture: float,
        threshold: float,
        scheduled_time: str,
    ) -> int | None:
        """Send notification requesting user approval for irrigation."""
        if not self._notifications:
            return None

        display_name = plant_name or f"Unit {unit_id}"
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
            NotificationSeverity,
            NotificationType,
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
