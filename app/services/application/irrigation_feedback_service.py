"""
Irrigation Feedback Service
=============================

Extracted from IrrigationWorkflowService (Sprint 4 – god-service split).

Handles user responses (approve/delay/cancel), irrigation feedback
(too_little/just_right/too_much), Bayesian threshold adjustment,
and ML preference learning.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Callable

from app.enums import IrrigationFeedback
from app.utils.time import coerce_datetime, utc_now

if TYPE_CHECKING:
    from app.services.ai.bayesian_threshold import BayesianThresholdAdjuster
    from app.services.application.notifications_service import NotificationsService
    from app.services.application.plant_service import PlantViewService
    from infrastructure.database.repositories.irrigation_workflow import IrrigationWorkflowRepository

logger = logging.getLogger(__name__)


# Inline constants to avoid circular imports
class _RequestStatus:
    PENDING = "pending"
    APPROVED = "approved"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


class _UserResponse:
    APPROVE = "approve"
    DELAY = "delay"
    CANCEL = "cancel"


class IrrigationFeedbackService:
    """User response handling, feedback processing, and ML threshold learning."""

    def __init__(
        self,
        repo: "IrrigationWorkflowRepository",
        get_config: Callable,
        *,
        notifications: "NotificationsService | None" = None,
        bayesian_adjuster: "BayesianThresholdAdjuster | None" = None,
        plant_service: "PlantViewService | None" = None,
        hysteresis_margin: float = 5.0,
        threshold_adjustment_callback: Callable | None = None,
    ):
        self._repo = repo
        self._get_config = get_config
        self._notifications = notifications
        self._bayesian_adjuster = bayesian_adjuster
        self._plant_service = plant_service
        self._hysteresis_margin = hysteresis_margin
        self._threshold_adjustment_callback = threshold_adjustment_callback

    # ── Setters ──────────────────────────────────────────────────────

    def set_notifications_service(self, service: "NotificationsService") -> None:
        self._notifications = service

    def set_bayesian_adjuster(self, adjuster: "BayesianThresholdAdjuster") -> None:
        self._bayesian_adjuster = adjuster

    def set_plant_service(self, service: "PlantViewService") -> None:
        self._plant_service = service

    def set_threshold_callback(self, callback: Callable) -> None:
        self._threshold_adjustment_callback = callback

    # ── User Response Handling ───────────────────────────────────────

    def handle_user_response(
        self,
        request_id: int,
        response: str,
        user_id: int,
        delay_minutes: int | None = None,
    ) -> dict[str, Any]:
        """Handle user response to irrigation request (approve/delay/cancel)."""
        request = self._repo.get_request(request_id)
        if not request:
            return {"ok": False, "error": "Request not found"}

        if request["status"] not in (_RequestStatus.PENDING, _RequestStatus.DELAYED):
            return {"ok": False, "error": f"Request cannot be modified (status: {request['status']})"}

        detected_at = coerce_datetime(request.get("detected_at")) or utc_now()
        response_time_seconds = (utc_now() - detected_at).total_seconds()
        config = self._get_config(request["unit_id"])

        if response == _UserResponse.APPROVE:
            return self._handle_approve(request, config, user_id, response_time_seconds)
        elif response == _UserResponse.DELAY:
            return self._handle_delay(request, config, user_id, response_time_seconds, delay_minutes)
        elif response == _UserResponse.CANCEL:
            return self._handle_cancel(request, config, user_id, response_time_seconds)
        else:
            return {"ok": False, "error": f"Invalid response: {response}"}

    def _handle_approve(self, request: dict, config: Any, user_id: int, response_time_seconds: float) -> dict:
        request_id = request["request_id"]
        self._repo.update_status(request_id, _RequestStatus.APPROVED, user_response=_UserResponse.APPROVE)
        if config.ml_learning_enabled:
            self._repo.update_preference_on_response(
                user_id, _UserResponse.APPROVE, response_time_seconds, request["unit_id"]
            )
            self._repo.mark_ml_collected(request_id, preference_score=1.0)
        logger.info("Request %s approved by user %s", request_id, user_id)
        return {
            "ok": True,
            "message": "Irrigation approved. Will execute at scheduled time.",
            "scheduled_time": request.get("scheduled_time"),
        }

    def _handle_delay(
        self, request: dict, config: Any, user_id: int, response_time_seconds: float, delay_minutes: int | None
    ) -> dict:
        request_id = request["request_id"]
        unit_id = request["unit_id"]
        delay_mins = delay_minutes or config.delay_increment_minutes
        detected_at = coerce_datetime(request.get("detected_at")) or utc_now()
        max_delay_time = detected_at + timedelta(hours=config.max_delay_hours)
        new_time = utc_now() + timedelta(minutes=delay_mins)
        if new_time > max_delay_time:
            return {"ok": False, "error": f"Cannot delay beyond {config.max_delay_hours} hours from detection"}
        delayed_until = new_time.isoformat()
        self._repo.update_status(
            request_id, _RequestStatus.DELAYED, user_response=_UserResponse.DELAY, delayed_until=delayed_until
        )
        if config.ml_learning_enabled:
            self._repo.update_preference_on_response(user_id, _UserResponse.DELAY, response_time_seconds, unit_id)
            self._repo.mark_ml_collected(request_id, preference_score=0.5)
        logger.info("Request %s delayed to %s by user %s", request_id, delayed_until, user_id)
        return {"ok": True, "message": f"Irrigation delayed by {delay_mins} minutes.", "delayed_until": delayed_until}

    def _handle_cancel(self, request: dict, config: Any, user_id: int, response_time_seconds: float) -> dict:
        request_id = request["request_id"]
        unit_id = request["unit_id"]
        self._repo.update_status(request_id, _RequestStatus.CANCELLED, user_response=_UserResponse.CANCEL)
        if config.ml_learning_enabled:
            self._repo.update_preference_on_response(user_id, _UserResponse.CANCEL, response_time_seconds, unit_id)
            self._repo.mark_ml_collected(request_id, preference_score=-1.0)
        logger.info("Request %s cancelled by user %s", request_id, user_id)
        return {"ok": True, "message": "Irrigation cancelled."}

    # ── Feedback Handling ────────────────────────────────────────────

    def handle_feedback(
        self,
        request_id: int,
        feedback_response: str | IrrigationFeedback,
        user_id: int,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Handle user feedback on irrigation amount."""
        request = self._repo.get_request(request_id)
        if not request:
            return {"ok": False, "error": "Request not found"}

        config = self._get_config(request["unit_id"])

        try:
            response = (
                feedback_response
                if isinstance(feedback_response, IrrigationFeedback)
                else IrrigationFeedback(str(feedback_response))
            )
        except ValueError:
            return {"ok": False, "error": "Invalid feedback response"}

        volume_feedback = {IrrigationFeedback.TOO_LITTLE, IrrigationFeedback.JUST_RIGHT, IrrigationFeedback.TOO_MUCH}
        timing_feedback = {IrrigationFeedback.TRIGGERED_TOO_EARLY, IrrigationFeedback.TRIGGERED_TOO_LATE}

        feedback_id = request.get("feedback_id")
        if self._notifications and feedback_id:
            self._notifications.submit_irrigation_feedback(
                feedback_id=feedback_id, response=response.value, notes=notes
            )

        if config.ml_learning_enabled and response in volume_feedback:
            self._repo.update_moisture_feedback(user_id, response.value, request["unit_id"])

        execution_log = self._repo.get_latest_execution_log_for_request(request_id)
        recommendation = execution_log.get("recommendation") if execution_log else None

        adjustment = None
        bayesian_result = None
        plant_id = request.get("plant_id")
        current_threshold = float(request.get("soil_moisture_threshold", 50.0))
        plant_context = None
        plant_variety = None
        strain_variety = None
        pot_size_liters = None
        if plant_id and self._plant_service:
            try:
                plant_context = self._plant_service.get_plant(int(plant_id))
                if plant_context:
                    plant_variety = getattr(plant_context, "plant_variety", None)
                    strain_variety = getattr(plant_context, "strain_variety", None)
                    pot_size_liters = getattr(plant_context, "pot_size_liters", None)
            except Exception:
                logger.debug("Failed to resolve plant context for irrigation feedback", exc_info=True)

        threshold_feedback = None
        if response in timing_feedback:
            threshold_feedback = (
                IrrigationFeedback.TOO_MUCH
                if response == IrrigationFeedback.TRIGGERED_TOO_EARLY
                else IrrigationFeedback.TOO_LITTLE
            )
        elif response in volume_feedback:
            threshold_feedback = self._resolve_threshold_feedback_from_volume(response, execution_log)

        if threshold_feedback is None and recommendation == "adjust_threshold":
            if response == IrrigationFeedback.TOO_MUCH:
                threshold_feedback = IrrigationFeedback.TOO_MUCH
            elif response == IrrigationFeedback.TOO_LITTLE:
                threshold_feedback = IrrigationFeedback.TOO_LITTLE

        if threshold_feedback and config.ml_threshold_adjustment_enabled:
            if self._bayesian_adjuster:
                try:
                    plant_type = request.get("plant_type") or getattr(plant_context, "plant_type", None) or "default"
                    growth_stage = (
                        request.get("growth_stage") or getattr(plant_context, "current_stage", None) or "Vegetative"
                    )
                    bayesian_result = self._bayesian_adjuster.update_from_feedback(
                        unit_id=request["unit_id"],
                        user_id=user_id,
                        feedback=threshold_feedback.value,
                        current_threshold=current_threshold,
                        soil_moisture_at_request=request.get("soil_moisture_detected", 45.0),
                        plant_type=plant_type,
                        growth_stage=growth_stage,
                        plant_variety=plant_variety,
                        strain_variety=strain_variety,
                        pot_size_liters=pot_size_liters,
                    )
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
                            "Applied Bayesian threshold adjustment of %.1f%% for unit %s (confidence: %.0f%%)",
                            adjustment,
                            request["unit_id"],
                            bayesian_result.confidence * 100.0,
                        )
                except Exception as e:
                    logger.error("Bayesian adjustment failed, falling back to fixed: %s", e)
                    bayesian_result = None

            if bayesian_result is None:
                if threshold_feedback == IrrigationFeedback.TOO_LITTLE:
                    adjustment = 5.0
                elif threshold_feedback == IrrigationFeedback.TOO_MUCH:
                    adjustment = -5.0
                if adjustment:
                    self._apply_soil_moisture_adjustment(
                        unit_id=request["unit_id"],
                        plant_id=plant_id,
                        current_threshold=current_threshold,
                        adjustment=adjustment,
                    )
                    logger.info(
                        "Applied fixed threshold adjustment of %.1f%% for unit %s", adjustment, request["unit_id"]
                    )

        logger.info("Received feedback '%s' for request %s from user %s", response.value, request_id, user_id)

        result: dict[str, Any] = {
            "ok": True,
            "message": "Thank you for your feedback!",
            "adjustment_applied": adjustment is not None,
        }
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
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Handle feedback submission using a feedback record ID."""
        request = self._repo.get_request_by_feedback_id(feedback_id)
        if not request:
            return {"ok": False, "error": "Request not found for feedback"}
        return self.handle_feedback(
            request_id=request["request_id"], feedback_response=feedback_response, user_id=user_id, notes=notes
        )

    # ── Private Helpers ──────────────────────────────────────────────

    def _resolve_threshold_feedback_from_volume(
        self,
        response: IrrigationFeedback,
        execution_log: dict[str, Any] | None,
    ) -> IrrigationFeedback | None:
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
            return IrrigationFeedback.TOO_MUCH if post_value <= target_high + epsilon else None
        if response == IrrigationFeedback.TOO_LITTLE:
            return IrrigationFeedback.TOO_LITTLE if post_value >= threshold_value - epsilon else None
        return None

    def _apply_soil_moisture_adjustment(
        self,
        *,
        unit_id: int,
        plant_id: int | None,
        current_threshold: float,
        adjustment: float,
    ) -> None:
        new_threshold = max(0.0, min(100.0, current_threshold + float(adjustment)))
        if plant_id is not None and self._plant_service:
            updated = self._plant_service.update_soil_moisture_threshold(
                plant_id=int(plant_id),
                threshold=new_threshold,
                unit_id=unit_id,
            )
            if not updated:
                logger.error("Failed to update soil moisture threshold for plant %s (unit %s)", plant_id, unit_id)
            return
        if self._threshold_adjustment_callback:
            try:
                self._threshold_adjustment_callback(
                    unit_id=unit_id, metric="soil_moisture", adjustment=float(adjustment)
                )
            except Exception as exc:
                logger.error("Failed to apply unit threshold adjustment: %s", exc)
            return
        logger.warning("No threshold adjustment handler available for unit %s (plant %s)", unit_id, plant_id)
