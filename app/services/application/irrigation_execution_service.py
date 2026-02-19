"""
Irrigation Execution Service
==============================

Extracted from IrrigationWorkflowService (Sprint 4 – god-service split).

Handles scheduled irrigation execution, completion, post-watering
moisture capture, duration calculation, and valve/pump orchestration.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable

from app.domain.actuators import ActuatorState
from app.utils.concurrency import synchronized
from app.utils.time import coerce_datetime, iso_now, utc_now

if TYPE_CHECKING:
    from app.domain.irrigation_calculator import IrrigationCalculator
    from app.services.application.notifications_service import NotificationsService
    from app.services.application.plant_service import PlantViewService
    from app.services.hardware.actuator_management_service import ActuatorManagementService
    from app.services.hardware.pump_calibration import PumpCalibrationService
    from infrastructure.database.repositories.irrigation_workflow import IrrigationWorkflowRepository

logger = logging.getLogger(__name__)


# Inline constants (avoid circular imports)
class _RequestStatus:
    EXECUTING = "executing"
    FAILED = "failed"


class _UserResponse:
    AUTO = "auto"


class IrrigationExecutionService:
    """Irrigation execution, completion, duration calculation, and post-capture."""

    def __init__(
        self,
        repo: "IrrigationWorkflowRepository",
        get_config: Callable,
        *,
        actuator_service: "ActuatorManagementService | None" = None,
        notifications: "NotificationsService | None" = None,
        irrigation_calculator: "IrrigationCalculator | None" = None,
        pump_calibration: "PumpCalibrationService | None" = None,
        plant_service: "PlantViewService | None" = None,
        max_duration_seconds: int = 900,
        post_capture_delay_seconds: int = 900,
        hysteresis_margin: float = 5.0,
    ):
        self._repo = repo
        self._get_config = get_config
        self._actuator_service = actuator_service
        self._notifications = notifications
        self._irrigation_calculator = irrigation_calculator
        self._pump_calibration = pump_calibration
        self._plant_service = plant_service
        self._max_duration_seconds = max_duration_seconds
        self._post_capture_delay_seconds = post_capture_delay_seconds
        self._hysteresis_margin = hysteresis_margin

    # ── Setters ──────────────────────────────────────────────────────

    def set_actuator_manager(self, manager: "ActuatorManagementService") -> None:
        self._actuator_service = manager

    def set_notifications_service(self, service: "NotificationsService") -> None:
        self._notifications = service

    def set_irrigation_calculator(self, calculator: "IrrigationCalculator") -> None:
        self._irrigation_calculator = calculator

    def set_pump_calibration_service(self, service: "PumpCalibrationService") -> None:
        self._pump_calibration = service

    def set_plant_service(self, service: "PlantViewService") -> None:
        self._plant_service = service

    # ── Scheduled Execution ──────────────────────────────────────────

    @synchronized
    def execute_due_requests(self) -> list[dict[str, Any]]:
        """Execute all requests that are due."""
        results = []
        due_requests = self._repo.claim_due_requests(iso_now())

        for request in due_requests:
            result = self._execute_irrigation(request)
            results.append(result)

        self._handle_expired_requests()
        return results

    @synchronized
    def complete_due_executions(self) -> list[dict[str, Any]]:
        """Complete executing irrigations that have reached their planned duration."""
        results: list[dict[str, Any]] = []
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
                valve_actuator_id = _coerce_actuator_id(latest_log.get("valve_actuator_id"))

            if not request_id or not unit_id or not actuator_id:
                continue
            if started_at is None or planned_duration is None:
                continue

            due_at = started_at + timedelta(seconds=int(planned_duration))
            if now < due_at:
                continue

            if not self._actuator_service:
                error = "No actuator manager available"
                self._repo.update_execution_log_status(request_id, execution_status="failed", execution_error=error)
                self._repo.record_execution(request_id, success=False, error=error)
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

                self._repo.record_execution(request_id, success=True, duration_seconds=duration_seconds)
                self._repo.update_execution_log_status(
                    request_id,
                    execution_status="completed",
                    actual_duration_s=duration_seconds,
                    estimated_volume_ml=estimated_volume_ml,
                )

                config = self._get_config(unit_id)
                if config.request_feedback_enabled and self._notifications:
                    self._schedule_feedback_request(request, config)

                results.append({"request_id": request_id, "success": True, "duration_seconds": duration_seconds})
            except Exception as exc:
                error = str(exc)
                self._repo.update_execution_log_status(request_id, execution_status="failed", execution_error=error)
                self._repo.record_execution(request_id, success=False, error=error)
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
    def capture_due_post_moisture(self) -> list[dict[str, Any]]:
        """Capture post-watering moisture for completed irrigations."""
        results: list[dict[str, Any]] = []
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

    # ── Core Execution ───────────────────────────────────────────────

    def _execute_irrigation(self, request: dict[str, Any]) -> dict[str, Any]:
        """Execute irrigation for a single request."""
        request_id = request["request_id"]
        unit_id = request["unit_id"]
        actuator_id = request.get("actuator_id")
        plant_id = request.get("plant_id")

        logger.info("Executing irrigation for request %s, unit %s", request_id, unit_id)

        if not request.get("user_response"):
            config = self._get_config(unit_id)
            if config.ml_learning_enabled:
                self._repo.update_preference_on_response(request["user_id"], _UserResponse.AUTO, 0, unit_id)
                self._repo.mark_ml_collected(request_id, preference_score=0.0)

        if not self._actuator_service or not actuator_id:
            error = "No actuator available"
            logger.warning("No actuator manager or actuator ID for request %s", request_id)
            self._log_execution_result(
                request,
                pump_actuator_id=str(actuator_id) if actuator_id is not None else None,
                execution_status="failed",
                execution_error=error,
            )
            self._repo.record_execution(request_id, success=False, error=error)
            return {"request_id": request_id, "success": False, "error": error}

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
            self._log_execution_result(
                request,
                planned_duration_s=int(irrigation_duration),
                pump_actuator_id=str(actuator_id),
                valve_actuator_id=str(valve_actuator_id) if valve_actuator_id is not None else None,
                execution_status="failed",
                execution_error=error,
            )
            self._repo.record_execution(request_id, success=False, error=error)
            return {"request_id": request_id, "success": False, "error": error}

        log_created = False
        started_at = None
        flow_rate = None
        estimated_volume_ml = None

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
                    self._log_execution_result(
                        request,
                        planned_duration_s=int(irrigation_duration),
                        pump_actuator_id=str(actuator_id),
                        valve_actuator_id=str(valve_actuator_id),
                        execution_status="failed",
                        execution_error=error,
                    )
                    self._repo.record_execution(request_id, success=False, error=error)
                    self._repo.release_unit_lock(unit_id)
                    return {"request_id": request_id, "success": False, "error": error}

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

            log_id = self._log_execution_result(
                request,
                planned_duration_s=int(irrigation_duration),
                pump_actuator_id=str(actuator_id),
                valve_actuator_id=str(valve_actuator_id) if valve_actuator_id is not None else None,
                assumed_flow_ml_s=flow_rate,
                estimated_volume_ml=estimated_volume_ml,
                execution_status="started",
                executed_at_utc=started_at,
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
            logger.error("Irrigation failed for request %s: %s", request_id, e)
            try:
                if self._actuator_service and actuator_id:
                    self._actuator_service.turn_off(actuator_id)
            except Exception:
                pass
            with contextlib.suppress(Exception):
                close_valve()

            if log_created:
                self._repo.update_execution_log_status(request_id, execution_status="failed", execution_error=str(e))
            else:
                self._log_execution_result(
                    request,
                    planned_duration_s=int(irrigation_duration),
                    pump_actuator_id=str(actuator_id),
                    valve_actuator_id=str(valve_actuator_id) if valve_actuator_id is not None else None,
                    assumed_flow_ml_s=flow_rate,
                    estimated_volume_ml=estimated_volume_ml,
                    execution_status="failed",
                    execution_error=str(e),
                    executed_at_utc=started_at or iso_now(),
                )
            self._repo.record_execution(request_id, success=False, error=str(e))
            self._repo.release_unit_lock(unit_id)
            return {"request_id": request_id, "success": False, "error": str(e)}

    # ── Duration Calculation ─────────────────────────────────────────

    def _calculate_irrigation_duration(
        self,
        plant_id: int | None,
        actuator_id: int,
        request: dict[str, Any],
    ) -> int:
        """Calculate irrigation duration using IrrigationCalculator if available."""
        default_duration = 30
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
            adjusted = round(duration_seconds * factor)
            adjusted = int(max(min_duration, min(max_duration, adjusted)))
            logger.info(
                "Applied volume feedback adjustment factor %.2f for unit %s: %ds -> %ds",
                factor,
                request.get("unit_id"),
                duration_seconds,
                adjusted,
            )
            return adjusted

        if self._irrigation_calculator and plant_id:
            try:
                flow_rate = None
                if self._pump_calibration:
                    flow_rate = self._pump_calibration.get_flow_rate(actuator_id)

                environmental_data = None
                if request:
                    env_fields = {
                        "temperature": request.get("temperature_at_detection"),
                        "humidity": request.get("humidity_at_detection"),
                        "vpd": request.get("vpd_at_detection"),
                        "lux": request.get("lux_at_detection"),
                        "soil_moisture": request.get("soil_moisture_detected"),
                    }
                    environmental_data = {k: v for k, v in env_fields.items() if v is not None}
                    if not environmental_data:
                        environmental_data = None

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
                    calculation = self._irrigation_calculator.calculate(plant_id=plant_id, pump_flow_rate=flow_rate)
                    logger.info(
                        "Calculated irrigation (formula-based) for plant %s: %d seconds (%.1f ml, confidence=%.2f)",
                        plant_id,
                        calculation.duration_seconds,
                        calculation.water_volume_ml,
                        calculation.confidence,
                    )

                return apply_volume_adjustment(calculation.duration_seconds, ml_adjusted=calculation.ml_adjusted)
            except Exception as e:
                logger.warning("IrrigationCalculator failed for plant %s, using default: %s", plant_id, e)

        logger.debug("Using default irrigation duration %ds for request (no calculator or plant_id)", default_duration)
        return apply_volume_adjustment(default_duration, ml_adjusted=False)

    # ── Private Helpers ──────────────────────────────────────────────

    def _handle_expired_requests(self) -> None:
        expired = self._repo.get_expired_requests()
        for request in expired:
            self._repo.update_status(request["request_id"], "expired")
            logger.info("Request %s expired", request["request_id"])

    def _schedule_feedback_request(self, request: dict[str, Any], config: Any) -> None:
        if not self._notifications:
            return
        try:
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
            logger.error("Failed to request feedback for request %s: %s", request["request_id"], e)

    def _log_execution_result(
        self,
        request: dict[str, Any],
        *,
        planned_duration_s: int | None = None,
        pump_actuator_id: str | None = None,
        valve_actuator_id: str | None = None,
        assumed_flow_ml_s: float | None = None,
        estimated_volume_ml: float | None = None,
        execution_status: str = "failed",
        execution_error: str | None = None,
        executed_at_utc: str | None = None,
    ) -> int | None:
        return self._repo.create_execution_log(
            request_id=request["request_id"],
            user_id=request.get("user_id"),
            unit_id=request["unit_id"],
            plant_id=request.get("plant_id"),
            sensor_id=(str(request.get("sensor_id")) if request.get("sensor_id") is not None else None),
            trigger_reason="below_threshold",
            trigger_moisture=request.get("soil_moisture_detected"),
            threshold_at_trigger=request.get("soil_moisture_threshold"),
            triggered_at_utc=request.get("detected_at") or iso_now(),
            planned_duration_s=planned_duration_s,
            pump_actuator_id=pump_actuator_id,
            valve_actuator_id=valve_actuator_id,
            assumed_flow_ml_s=assumed_flow_ml_s,
            estimated_volume_ml=estimated_volume_ml,
            execution_status=execution_status,
            execution_error=execution_error,
            executed_at_utc=executed_at_utc or iso_now(),
            post_moisture_delay_s=self._post_capture_delay_seconds,
        )

    def _get_current_moisture(self, plant_id: int | None, unit_id: int | None) -> float | None:
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
        return float(moisture) if moisture is not None else None

    def _get_volume_adjustment_factor(self, user_id: int, unit_id: int) -> float:
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
        adjustment = net * 0.1
        return max(0.8, min(1.2, 1.0 + adjustment))

    def _classify_attribution(
        self,
        *,
        trigger_moisture: float | None,
        threshold_at_trigger: float | None,
        post_moisture: float | None,
    ) -> str:
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

    def _resolve_valve_actuator_id(self, plant_id: int | None) -> int | None:
        if plant_id is None or not self._plant_service:
            return None
        try:
            return self._plant_service.get_plant_valve_actuator_id(int(plant_id))
        except Exception as exc:
            logger.debug("Failed to resolve valve actuator for plant %s: %s", plant_id, exc)
            return None


def _coerce_actuator_id(value: Any) -> int | None:
    """Coerce actuator id values to int if possible."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
