"""
Manual irrigation logging and post-watering capture service.

Stores manual watering events for sensor-only setups and captures post-watering
moisture readings after a settle delay to support dry-down modeling.
"""
from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Any, Dict, List, Optional

from app.enums import NotificationSeverity, NotificationType, SensorEvent
from app.utils.time import coerce_datetime, iso_now, utc_now

logger = logging.getLogger(__name__)


class ManualIrrigationService:
    """Log manual irrigation events and capture post-watering outcomes."""

    def __init__(
        self,
        *,
        irrigation_repo: Any,
        analytics_repo: Any,
        plant_service: Optional[Any] = None,
        plant_model_service: Optional[Any] = None,
        notifications_service: Optional[Any] = None,
        device_repo: Optional[Any] = None,
        growth_repo: Optional[Any] = None,
        event_bus: Optional[Any] = None,
        scheduler: Optional[Any] = None,
    ) -> None:
        self._repo = irrigation_repo
        self._analytics = analytics_repo
        self._plant_service = plant_service
        self._model_service = plant_model_service
        self._notifications = notifications_service
        self._device_repo = device_repo
        self._growth_repo = growth_repo #TODO: Remove dependency on growth repo and use unit repo
        self._event_bus = event_bus
        self._scheduler = scheduler
        self._last_moisture_by_sensor: Dict[int, float] = {}
        self._last_prompt_by_plant: Dict[int, str] = {}

        self._pre_moisture_window_minutes = int(
            os.getenv("SYSGROW_MANUAL_IRRIGATION_PRE_WINDOW_MINUTES", "15")
        )
        self._default_settle_delay_min = int(
            os.getenv("SYSGROW_MANUAL_IRRIGATION_SETTLE_DELAY_MINUTES", "15")
        )
        self._post_capture_interval_seconds = int(
            os.getenv("SYSGROW_MANUAL_IRRIGATION_POST_CAPTURE_INTERVAL_SECONDS", "60")
        )
        self._moisture_rise_threshold = float(
            os.getenv("SYSGROW_MANUAL_IRRIGATION_RISE_THRESHOLD", "5.0")
        )
        self._prompt_cooldown_minutes = int(
            os.getenv("SYSGROW_MANUAL_IRRIGATION_PROMPT_COOLDOWN_MINUTES", "60")
        )
        self._recent_irrigation_minutes = int(
            os.getenv("SYSGROW_MANUAL_IRRIGATION_RECENT_AUTOWATER_MINUTES", "90")
        )
        self._fallback_window_hours = int(
            os.getenv("SYSGROW_MANUAL_IRRIGATION_FALLBACK_WINDOW_HOURS", "24")
        )

    def set_scheduler(self, scheduler: Any) -> None:
        """Attach scheduler for interval jobs."""
        self._scheduler = scheduler

    def log_watering_event(
        self,
        *,
        user_id: int,
        unit_id: int,
        plant_id: int,
        watered_at_utc: Optional[str] = None,
        amount_ml: Optional[float] = None,
        notes: Optional[str] = None,
        settle_delay_min: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Log a manual watering event with pre-moisture context."""
        watered_at = coerce_datetime(watered_at_utc) if watered_at_utc else utc_now()
        if watered_at is None:
            watered_at = utc_now()
        watered_at_iso = watered_at.isoformat()

        pre_start = watered_at - timedelta(minutes=self._pre_moisture_window_minutes)
        pre_reading = self._analytics.get_latest_plant_moisture_in_window(
            plant_id,
            start_ts=pre_start.isoformat(),
            end_ts=watered_at_iso,
        )
        pre_moisture = None
        pre_moisture_at_utc = None
        if pre_reading:
            pre_moisture = pre_reading.get("soil_moisture")
            pre_moisture_at_utc = pre_reading.get("timestamp")

        settle_delay = (
            int(settle_delay_min)
            if settle_delay_min is not None
            else self._default_settle_delay_min
        )

        log_id = self._repo.create_manual_irrigation_log(
            user_id=user_id,
            unit_id=unit_id,
            plant_id=plant_id,
            watered_at_utc=watered_at_iso,
            amount_ml=amount_ml,
            notes=notes,
            pre_moisture=pre_moisture,
            pre_moisture_at_utc=pre_moisture_at_utc,
            settle_delay_min=settle_delay,
            created_at_utc=iso_now(),
        )

        if not log_id:
            return {"ok": False, "error": "Failed to create manual irrigation log"}

        return {"ok": True, "log_id": log_id}

    def capture_manual_outcomes(self, limit: int = 50) -> List[int]:
        """Capture post-watering moisture for due manual logs."""
        pending = self._repo.get_manual_logs_pending_post_capture(limit=limit)
        if not pending:
            return []

        now = utc_now()
        updated: List[int] = []

        for log in pending:
            watered_at = coerce_datetime(log.get("watered_at_utc"))
            if watered_at is None:
                continue

            delay_min = log.get("settle_delay_min")
            if delay_min is None:
                delay_min = self._default_settle_delay_min

            due_at = watered_at + timedelta(minutes=int(delay_min))
            if due_at > now:
                continue

            post_moisture = self._get_current_moisture(
                plant_id=log.get("plant_id"),
                unit_id=log.get("unit_id"),
            )
            if post_moisture is None:
                continue

            pre_moisture = log.get("pre_moisture")
            delta = None
            if pre_moisture is not None:
                delta = float(post_moisture) - float(pre_moisture)

            updated_ok = self._repo.update_manual_log_post_moisture(
                log_id=log["id"],
                post_moisture=float(post_moisture),
                post_moisture_at_utc=iso_now(),
                delta_moisture=delta,
            )
            if updated_ok:
                updated.append(log["id"])
                if self._model_service:
                    try:
                        plant_id = log.get("plant_id")
                        if plant_id is not None:
                            update_result = self._model_service.update_drydown_model(int(plant_id))
                            self._maybe_notify_prediction(
                                plant_id=int(plant_id),
                                unit_id=int(log.get("unit_id") or 0),
                                current_moisture=float(post_moisture),
                                model_result=update_result,
                            )
                    except Exception as exc:
                        logger.debug("Dry-down update failed for plant %s: %s", log.get("plant_id"), exc)

        return updated

    def register_scheduled_tasks(self) -> None:
        """Register manual irrigation scheduled tasks."""
        if not self._scheduler:
            logger.warning("No scheduler available, skipping manual irrigation tasks")
            return

        @self._scheduler.task("manual_irrigation.capture_outcomes")
        def capture_outcomes_task():
            return self.capture_manual_outcomes()

        self._scheduler.schedule_interval(
            task_name="manual_irrigation.capture_outcomes",
            interval_seconds=self._post_capture_interval_seconds,
            job_id="manual_irrigation_post_capture",
            namespace="irrigation",
            start_immediately=True,
        )

        logger.info("Registered manual irrigation scheduled tasks")

    def register_event_handlers(self) -> None:
        """Subscribe to sensor events for manual irrigation prompts."""
        if not self._event_bus:
            logger.warning("No event bus available, skipping manual irrigation handlers")
            return

        self._event_bus.subscribe(
            SensorEvent.SOIL_MOISTURE_UPDATE,
            self._on_soil_moisture_update,
        )
        logger.info("Registered manual irrigation event handlers")

    def _get_current_moisture(
        self,
        *,
        plant_id: Optional[int],
        unit_id: Optional[int],
    ) -> Optional[float]:
        """Fetch the latest moisture reading for a plant or unit."""
        if self._plant_service:
            plant = None
            if plant_id is not None:
                plant = self._plant_service.get_plant(plant_id, unit_id=unit_id)
            elif unit_id is not None:
                plant = self._plant_service.get_active_plant(unit_id)

            if plant:
                moisture = getattr(plant, "moisture_level", None)
                if moisture is not None:
                    return float(moisture)

        if plant_id is None or not self._analytics:
            return None

        end_dt = utc_now()
        start_dt = end_dt - timedelta(hours=self._fallback_window_hours)
        reading = self._analytics.get_latest_plant_moisture_in_window(
            plant_id,
            start_ts=start_dt.isoformat(),
            end_ts=end_dt.isoformat(),
        )
        if reading and reading.get("soil_moisture") is not None:
            return float(reading["soil_moisture"])
        return None

    def _on_soil_moisture_update(self, data: Dict[str, Any]) -> None:
        """Prompt for manual irrigation logging on moisture spikes."""
        try:
            sensor_id = data.get("sensor_id")
            unit_id = data.get("unit_id")
            moisture = data.get("soil_moisture")
            if sensor_id is None or unit_id is None or moisture is None:
                return

            sensor_id = int(sensor_id)
            unit_id = int(unit_id)
            moisture = float(moisture)

            previous = self._last_moisture_by_sensor.get(sensor_id)
            self._last_moisture_by_sensor[sensor_id] = moisture

            if previous is None:
                return

            if moisture <= previous + self._moisture_rise_threshold:
                return

            if self._unit_has_irrigation_actuators(unit_id):
                return

            plant_id = self._resolve_plant_id(sensor_id, unit_id)
            if plant_id is None:
                return

            if self._should_throttle_prompt(plant_id):
                return

            if self._had_recent_irrigation_activity(plant_id):
                return

            user_id = self._resolve_user_id(unit_id)
            if not user_id or not self._notifications:
                return

            title = "Manual Watering Detected"
            message = (
                "Soil moisture increased unexpectedly. "
                "Did you water manually? Log the amount to improve predictions."
            )

            self._notifications.send_notification(
                user_id=user_id,
                notification_type=NotificationType.IRRIGATION_RECOMMENDATION,
                title=title,
                message=message,
                severity=NotificationSeverity.INFO,
                source_type="plant",
                source_id=plant_id,
                unit_id=unit_id,
                requires_action=True,
                action_type="manual_irrigation_log",
                action_data={
                    "plant_id": plant_id,
                    "unit_id": unit_id,
                    "sensor_id": sensor_id,
                    "previous_moisture": previous,
                    "current_moisture": moisture,
                },
            )

            self._last_prompt_by_plant[plant_id] = iso_now()
        except Exception as exc:
            logger.debug("Manual irrigation prompt failed: %s", exc)

    def _resolve_plant_id(self, sensor_id: int, unit_id: int) -> Optional[int]:
        """Resolve plant_id from sensor or unit context."""
        plant_id = self._analytics.get_plant_id_for_sensor(sensor_id)
        if plant_id:
            return int(plant_id)

        if self._plant_service:
            plant = self._plant_service.get_active_plant(unit_id)
            if plant and getattr(plant, "plant_id", None) is not None:
                return int(plant.plant_id)
        return None

    def _resolve_user_id(self, unit_id: int) -> Optional[int]:
        """Resolve user_id owning a unit."""
        if not self._growth_repo:
            return None
        unit = self._growth_repo.get_unit(unit_id)
        if not unit:
            return None
        unit_data = dict(unit)
        return unit_data.get("user_id")

    def _resolve_plant_threshold(self, plant_id: int, unit_id: int) -> Optional[float]:
        """Resolve per-plant soil moisture threshold."""
        if not self._plant_service:
            return None

        plant = self._plant_service.get_plant(plant_id, unit_id)
        if plant and plant.soil_moisture_threshold_override is not None:
            try:
                return float(plant.soil_moisture_threshold_override)
            except (TypeError, ValueError):
                return None

        if plant:
            name = plant.plant_type or plant.plant_name
            if name:
                try:
                    return self._plant_service.plant_json_handler.get_soil_moisture_trigger(name)
                except Exception:
                    return None

        return None

    def _unit_has_irrigation_actuators(self, unit_id: int) -> bool:
        """Check if unit has pump/valve actuators configured."""
        if not self._device_repo:
            return False
        actuators = self._device_repo.get_actuator_configs(unit_id=unit_id, limit=200, offset=0)
        for actuator in actuators or []:
            actuator_type = str(actuator.get("actuator_type") or "").lower()
            if actuator_type in {"pump", "water_pump", "water-pump", "valve"}:
                return True
        return False

    def _should_throttle_prompt(self, plant_id: int) -> bool:
        """Prevent repeated prompts within the cooldown window."""
        last_prompt = self._last_prompt_by_plant.get(plant_id)
        if not last_prompt:
            return False
        last_dt = coerce_datetime(last_prompt)
        if last_dt is None:
            return False
        return utc_now() - last_dt < timedelta(minutes=self._prompt_cooldown_minutes)

    def _had_recent_irrigation_activity(self, plant_id: int) -> bool:
        """Skip prompt if irrigation activity occurred recently."""
        end_dt = utc_now()
        start_dt = end_dt - timedelta(minutes=self._recent_irrigation_minutes)

        logs = self._repo.get_execution_logs_for_plant(
            plant_id,
            start_ts=start_dt.isoformat(),
            end_ts=end_dt.isoformat(),
        )
        if logs:
            return True

        manual_logs = self._repo.get_manual_logs_for_plant(
            plant_id,
            start_ts=start_dt.isoformat(),
            end_ts=end_dt.isoformat(),
        )
        return bool(manual_logs)

    def _maybe_notify_prediction(
        self,
        *,
        plant_id: int,
        unit_id: int,
        current_moisture: float,
        model_result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send next-irrigation prediction after manual watering."""
        if not self._notifications or not self._model_service or unit_id <= 0:
            return

        if not model_result or not model_result.get("ok"):
            return

        threshold = self._resolve_plant_threshold(plant_id, unit_id)
        if threshold is None:
            return

        prediction = self._model_service.predict_next_irrigation(
            plant_id=plant_id,
            threshold=threshold,
            now_moisture=current_moisture,
        )
        if not prediction.get("ok"):
            return

        user_id = self._resolve_user_id(unit_id)
        if not user_id:
            return

        hours_until = prediction.get("hours_until_threshold")
        predicted_at = prediction.get("predicted_at_utc")
        if hours_until is None or predicted_at is None:
            return
        title = "Next Watering Estimate"
        message = (
            f"Based on recent dry-down, likely needs water in ~{hours_until} hours "
            f"(around {predicted_at})."
        )

        self._notifications.send_notification(
            user_id=user_id,
            notification_type=NotificationType.IRRIGATION_RECOMMENDATION,
            title=title,
            message=message,
            severity=NotificationSeverity.INFO,
            source_type="plant",
            source_id=plant_id,
            unit_id=unit_id,
        )
