"""
Irrigation Workflow API Blueprint
=================================

REST API endpoints for irrigation standby/notification/approval workflow.

Endpoints:
- GET /api/irrigation/requests - Get pending irrigation requests
- GET /api/irrigation/requests/<id> - Get specific request
- POST /api/irrigation/requests/<id>/approve - Approve irrigation
- POST /api/irrigation/requests/<id>/delay - Delay irrigation
- POST /api/irrigation/requests/<id>/cancel - Cancel irrigation
- POST /api/irrigation/requests/<id>/feedback - Submit feedback
- POST /api/irrigation/manual/log - Log manual irrigation event
- GET /api/irrigation/executions/<unit_id> - Execution telemetry
- GET /api/irrigation/eligibility/<unit_id> - Eligibility trace
- GET /api/irrigation/manual/<unit_id> - Manual irrigation history
- GET /api/irrigation/manual/predict/<plant_id> - Manual mode prediction
- GET /api/irrigation/history/<unit_id> - Get irrigation history for unit
- GET /api/irrigation/config/<unit_id> - Get workflow config
- PUT /api/irrigation/config/<unit_id> - Update workflow config
- GET /api/irrigation/preferences - Get user preferences

Author: SYSGrow Team
Date: January 2026
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict

from flask import Blueprint, Response, jsonify, request
from pydantic import ValidationError

from app.blueprints.api._common import (
    get_analytics_repo,
    get_container,
    get_device_repo,
    get_irrigation_service,
    get_manual_irrigation_service,
    get_plant_irrigation_model_service,
    get_plant_service,
    get_pump_calibration_service,
    get_selected_unit_id,
    get_unit_repo,
    get_user_id,
)
from app.schemas import (
    IrrigationConfigRequest,
    IrrigationDelayRequest,
    IrrigationEligibilityTraceResponse,
    IrrigationExecutionLogResponse,
    IrrigationFeedbackRequest,
    ManualIrrigationLogRequest,
    ManualIrrigationLogResponse,
    ManualIrrigationPredictionResponse,
)
from app.utils.http import error_response, safe_route, success_response
from app.utils.time import coerce_datetime, utc_now

irrigation_bp = Blueprint("irrigation", __name__)


def _resolve_time_window() -> tuple[str, str]:
    end_raw = request.args.get("end_ts")
    start_raw = request.args.get("start_ts")

    end_dt = coerce_datetime(end_raw) if end_raw else utc_now()
    if end_dt is None:
        end_dt = utc_now()

    start_dt = coerce_datetime(start_raw) if start_raw else (end_dt - timedelta(days=7))
    if start_dt is None:
        start_dt = end_dt - timedelta(days=7)

    return start_dt.isoformat(), end_dt.isoformat()


# ==================== Request Management ====================


@irrigation_bp.route("/requests", methods=["GET"])
@safe_route("Failed to get pending requests")
def get_pending_requests() -> Response:
    """
    Get pending irrigation requests for current user.

    Query params:
    - status: Filter by status (pending, approved, delayed, executed, cancelled)
    - limit: Max results (default 20)
    """
    service = get_irrigation_service()
    if not service:
        return jsonify({"ok": False, "error": {"message": "Service not available"}}), 503

    user_id = get_user_id()
    limit = request.args.get("limit", 20, type=int)

    requests_list = service.get_pending_requests(user_id, limit=limit)
    return jsonify(
        {
            "ok": True,
            "data": requests_list,
            "count": len(requests_list),
        }
    )


@irrigation_bp.route("/requests/<int:request_id>", methods=["GET"])
@safe_route("Failed to get irrigation request")
def get_request(request_id: int) -> Response:
    """Get a specific irrigation request."""
    service = get_irrigation_service()
    if not service:
        return jsonify({"ok": False, "error": {"message": "Service not available"}}), 503

    req = service.get_request(request_id)
    if not req:
        return jsonify({"ok": False, "error": {"message": "Request not found"}}), 404

    return jsonify({"ok": True, "data": req})


@irrigation_bp.route("/requests/<int:request_id>/approve", methods=["POST"])
@safe_route("Failed to approve irrigation request")
def approve_request(request_id: int) -> Response:
    """
    Approve an irrigation request.

    The irrigation will execute at the scheduled time.
    """
    service = get_irrigation_service()
    if not service:
        return jsonify({"ok": False, "error": {"message": "Service not available"}}), 503

    user_id = get_user_id()

    result = service.handle_user_response(request_id, "approve", user_id)

    if result.get("ok"):
        return jsonify(result)
    else:
        return jsonify(result), 400


@irrigation_bp.route("/requests/<int:request_id>/delay", methods=["POST"])
@safe_route("Failed to delay irrigation request")
def delay_request(request_id: int) -> Response:
    """
    Delay an irrigation request.

    Request body (optional):
    - delay_minutes: Minutes to delay (default from config)
    """
    service = get_irrigation_service()
    if not service:
        return jsonify({"ok": False, "error": {"message": "Service not available"}}), 503

    user_id = get_user_id()
    raw = request.get_json() or {}

    try:
        body = IrrigationDelayRequest(**raw)
    except ValidationError as ve:
        return jsonify({"ok": False, "error": {"message": "Invalid request", "details": ve.errors()}}), 400

    result = service.handle_user_response(request_id, "delay", user_id, delay_minutes=body.delay_minutes)

    if result.get("ok"):
        return jsonify(result)
    else:
        return jsonify(result), 400


@irrigation_bp.route("/requests/<int:request_id>/cancel", methods=["POST"])
@safe_route("Failed to cancel irrigation request")
def cancel_request(request_id: int) -> Response:
    """Cancel an irrigation request."""
    service = get_irrigation_service()
    if not service:
        return jsonify({"ok": False, "error": {"message": "Service not available"}}), 503

    user_id = get_user_id()

    result = service.handle_user_response(request_id, "cancel", user_id)

    if result.get("ok"):
        return jsonify(result)
    else:
        return jsonify(result), 400


@irrigation_bp.route("/requests/<int:request_id>/feedback", methods=["POST"])
@safe_route("Failed to submit irrigation feedback")
def submit_feedback(request_id: int) -> Response:
    """
    Submit feedback for an executed irrigation request.

    Request body:
    - response: 'too_little', 'just_right', 'too_much',
      'triggered_too_early', 'triggered_too_late', or 'skipped'
    - notes: Optional notes
    """
    service = get_irrigation_service()
    if not service:
        return jsonify({"ok": False, "error": {"message": "Service not available"}}), 503

    user_id = get_user_id()
    raw = request.get_json() or {}

    try:
        body = IrrigationFeedbackRequest(**raw)
    except ValidationError as ve:
        return jsonify({"ok": False, "error": {"message": "Invalid request", "details": ve.errors()}}), 400

    result = service.handle_feedback(request_id, body.response.value, user_id, body.notes)

    if result.get("ok"):
        return jsonify(result)
    else:
        return jsonify(result), 400


# ==================== Manual Irrigation ====================


@irrigation_bp.route("/manual/log", methods=["POST"])
@safe_route("Failed to log manual irrigation")
def log_manual_irrigation() -> Response:
    """Log a manual irrigation event (sensor-only mode)."""
    service = get_manual_irrigation_service()
    if not service:
        return jsonify({"ok": False, "error": {"message": "Manual irrigation service not available"}}), 503

    user_id = get_user_id()
    raw = request.get_json() or {}

    try:
        body = ManualIrrigationLogRequest(**raw)
    except ValidationError as ve:
        return jsonify({"ok": False, "error": {"message": "Invalid request", "details": ve.errors()}}), 400

    result = service.log_watering_event(
        user_id=user_id,
        unit_id=body.unit_id,
        plant_id=body.plant_id,
        watered_at_utc=body.watered_at_utc,
        amount_ml=body.amount_ml,
        notes=body.notes,
        settle_delay_min=body.settle_delay_min,
    )

    if result.get("ok"):
        return jsonify(result)
    return jsonify(result), 400


# ==================== Telemetry & Manual History ====================


@irrigation_bp.route("/executions/<int:unit_id>", methods=["GET"])
@safe_route("Failed to get execution logs")
def get_execution_logs(unit_id: int) -> Response:
    """Fetch irrigation execution logs for diagnostics."""
    service = get_irrigation_service()

    limit = request.args.get("limit", 200, type=int)
    plant_id = request.args.get("plant_id", type=int)
    start_ts, end_ts = _resolve_time_window()

    logs = service.get_execution_logs(
        unit_id,
        start_ts=start_ts,
        end_ts=end_ts,
        limit=limit,
        plant_id=plant_id,
    )
    items = [IrrigationExecutionLogResponse(**log).model_dump() for log in logs]
    return success_response({"items": items, "count": len(items)})


@irrigation_bp.route("/eligibility/<int:unit_id>", methods=["GET"])
@safe_route("Failed to get eligibility traces")
def get_eligibility_traces(unit_id: int) -> Response:
    """Fetch irrigation eligibility traces for diagnostics."""
    service = get_irrigation_service()

    limit = request.args.get("limit", 200, type=int)
    plant_id = request.args.get("plant_id", type=int)
    start_ts, end_ts = _resolve_time_window()

    traces = service.get_eligibility_traces(
        unit_id,
        start_ts=start_ts,
        end_ts=end_ts,
        limit=limit,
        plant_id=plant_id,
    )
    items = [IrrigationEligibilityTraceResponse(**trace).model_dump() for trace in traces]
    return success_response({"items": items, "count": len(items)})


@irrigation_bp.route("/manual/<int:unit_id>", methods=["GET"])
@safe_route("Failed to get manual irrigation history")
def get_manual_irrigation_history(unit_id: int) -> Response:
    """Fetch manual irrigation history for a unit."""
    service = get_irrigation_service()

    limit = request.args.get("limit", 200, type=int)
    plant_id = request.args.get("plant_id", type=int)
    start_ts, end_ts = _resolve_time_window()

    logs = service.get_manual_irrigation_logs(
        unit_id,
        start_ts=start_ts,
        end_ts=end_ts,
        limit=limit,
        plant_id=plant_id,
    )
    items = [ManualIrrigationLogResponse(**log).model_dump() for log in logs]
    return success_response({"items": items, "count": len(items)})


@irrigation_bp.route("/manual/predict/<int:plant_id>", methods=["GET"])
@safe_route("Failed to predict next manual irrigation")
def predict_manual_next_irrigation(plant_id: int) -> Response:
    """Predict next irrigation time for manual-mode users."""
    try:
        service = get_plant_irrigation_model_service()
    except Exception as exc:
        return jsonify({"ok": False, "error": {"message": str(exc)}}), 503

    unit_id = request.args.get("unit_id", type=int)
    threshold = request.args.get("threshold", type=float)
    now_moisture = request.args.get("soil_moisture", type=float)

    if threshold is None or now_moisture is None:
        return error_response("threshold and soil_moisture are required", 400)

    prediction = service.predict_next_irrigation(
        plant_id=plant_id,
        threshold=threshold,
        now_moisture=now_moisture,
    )
    payload = {"ok": True, "plant_id": plant_id, "unit_id": unit_id}
    payload.update(prediction)
    response = ManualIrrigationPredictionResponse(**payload).model_dump()
    return success_response(response)


# ==================== History ====================


@irrigation_bp.route("/history/<int:unit_id>", methods=["GET"])
@safe_route("Failed to get irrigation history")
def get_history(unit_id: int) -> Response:
    """
    Get irrigation request history for a unit.

    Query params:
    - limit: Max results (default 50)
    """
    service = get_irrigation_service()
    if not service:
        return jsonify({"ok": False, "error": {"message": "Service not available"}}), 503

    limit = request.args.get("limit", 50, type=int)

    history = service.get_request_history(unit_id, limit=limit)
    return jsonify(
        {
            "ok": True,
            "data": history,
            "count": len(history),
        }
    )


# ==================== Configuration ====================


@irrigation_bp.route("/config/<int:unit_id>", methods=["GET"])
@safe_route("Failed to get irrigation configuration")
def get_config(unit_id: int) -> Response:
    """Get irrigation workflow configuration for a unit."""
    service = get_irrigation_service()
    if not service:
        return error_response("Service not available", status=503)

    config = service.get_config(unit_id)
    if not config:
        return error_response("Configuration not found", status=404, details={"unit_id": unit_id})

    return success_response(config.to_dict())


@irrigation_bp.route("/config/<int:unit_id>", methods=["PUT"])
@safe_route("Failed to update irrigation configuration")
def update_config(unit_id: int) -> Response:
    """
    Update irrigation workflow configuration for a unit.

    Request body (all fields optional):
    - workflow_enabled: bool
    - auto_irrigation_enabled: bool
    - manual_mode_enabled: bool
    - require_approval: bool
    - default_scheduled_time: str (HH:MM)
    - delay_increment_minutes: int
    - max_delay_hours: int
    - expiration_hours: int
    - send_reminder_before_execution: bool
    - reminder_minutes_before: int
    - request_feedback_enabled: bool
    - feedback_delay_minutes: int
    - ml_learning_enabled: bool
    - ml_threshold_adjustment_enabled: bool
    """
    service = get_irrigation_service()
    if not service:
        return error_response("Service not available", status=503)

    data = request.get_json() or {}

    success = service.update_config(unit_id, data)
    if success:
        config = service.get_config(unit_id)
        if not config:
            return error_response(
                "Configuration updated but fetch failed",
                status=500,
                details={"unit_id": unit_id},
            )

        return success_response(
            config.to_dict(),
            message="Configuration updated",
        )
    else:
        return error_response(
            "Failed to update config",
            status=500,
            details={"unit_id": unit_id},
        )


# ==================== User Preferences ====================


@irrigation_bp.route("/preferences", methods=["GET"])
@safe_route("Failed to get irrigation preferences")
def get_preferences() -> Response:
    """
    Get user irrigation preferences (ML learning data).

    Query params:
    - unit_id: Optional unit ID for unit-specific preferences
    """
    service = get_irrigation_service()
    if not service:
        return jsonify({"ok": False, "error": {"message": "Service not available"}}), 503

    user_id = get_user_id()
    unit_id = request.args.get("unit_id", type=int)

    preferences = service.get_user_preferences(user_id, unit_id)
    return jsonify(
        {
            "ok": True,
            "data": preferences or {},
        }
    )


# ==================== Action Endpoints (for notification dropdown) ====================


@irrigation_bp.route("/action/<int:request_id>", methods=["POST"])
@safe_route("Failed to handle irrigation action")
def handle_action(request_id: int) -> Response:
    """
    Handle action from notification dropdown.

    This is a convenience endpoint that accepts action type in the body.

    Request body:
    - action: 'approve', 'delay', 'cancel'
    - delay_minutes: Optional (for delay action)
    """
    service = get_irrigation_service()
    if not service:
        return jsonify({"ok": False, "error": {"message": "Service not available"}}), 503

    user_id = get_user_id()
    data = request.get_json() or {}

    action = data.get("action")
    if not action:
        return jsonify({"ok": False, "error": {"message": "Missing 'action' field"}}), 400

    valid_actions = {"approve", "delay", "cancel"}
    if action not in valid_actions:
        return jsonify({"ok": False, "error": {"message": f"Invalid action. Must be one of: {valid_actions}"}}), 400

    delay_minutes = data.get("delay_minutes") if action == "delay" else None

    result = service.handle_user_response(request_id, action, user_id, delay_minutes=delay_minutes)

    if result.get("ok"):
        return jsonify(result)
    else:
        return jsonify(result), 400


# ==================== Pump Calibration ====================


@irrigation_bp.route("/calibration/pump/start", methods=["POST"])
@safe_route("Failed to start pump calibration")
def start_pump_calibration() -> Response:
    """
    Start pump calibration for an actuator.

    Request body:
    - actuator_id: ID of the pump actuator to calibrate
    - duration_seconds: Optional duration to run the pump (default from config)

    Returns:
    - duration_seconds: Duration used for calibration
    - status: Session status
    - message: User instructions
    """
    try:
        pump_cal = get_pump_calibration_service()
    except RuntimeError as e:
        return jsonify({"ok": False, "error": {"message": str(e)}}), 503

    data = request.get_json() or {}
    actuator_id = data.get("actuator_id")
    if not actuator_id:
        return jsonify({"ok": False, "error": {"message": "Missing 'actuator_id'"}}), 400

    duration_seconds = data.get("duration_seconds")
    if duration_seconds is not None:
        try:
            duration_seconds = int(duration_seconds)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": {"message": "Invalid 'duration_seconds'"}}), 400
        if duration_seconds <= 0:
            return jsonify({"ok": False, "error": {"message": "'duration_seconds' must be positive"}}), 400

    try:
        result = pump_cal.start_calibration(
            actuator_id=actuator_id,
            duration_seconds=duration_seconds,
        )
        if not result.get("ok"):
            payload = {
                "ok": False,
                "error": {"message": result.get("error", "Failed to start calibration")},
            }
            if result.get("status"):
                payload["status"] = result.get("status")
            return jsonify(payload), 400
        data = {key: value for key, value in result.items() if key != "ok"}
        return jsonify(
            {
                "ok": True,
                "data": data,
            }
        )
    except ValueError as e:
        return jsonify({"ok": False, "error": {"message": str(e)}}), 400


@irrigation_bp.route("/calibration/pump/<int:actuator_id>/complete", methods=["POST"])
@safe_route("Failed to complete pump calibration")
def complete_pump_calibration(actuator_id: int) -> Response:
    """
    Complete pump calibration with measured volume.

    Request body:
    - measured_ml: Actual volume measured by user

    Returns:
    - flow_rate_ml_per_second: Calculated flow rate
    - confidence: Confidence in the calibration
    """
    try:
        pump_cal = get_pump_calibration_service()
    except RuntimeError as e:
        return jsonify({"ok": False, "error": {"message": str(e)}}), 503

    data = request.get_json() or {}
    measured_ml = data.get("measured_ml", data.get("actual_ml"))
    if measured_ml is None:
        return jsonify({"ok": False, "error": {"message": "Missing 'measured_ml'"}}), 400
    try:
        measured_ml = float(measured_ml)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": {"message": "Invalid 'measured_ml'"}}), 400

    try:
        result = pump_cal.complete_calibration(
            actuator_id=actuator_id,
            measured_ml=measured_ml,
        )
        response_data = result.to_dict()
        response_data["message"] = f"Calibration complete. Flow rate: {result.flow_rate_ml_per_second:.2f} ml/s"
        return jsonify({"ok": True, "data": response_data})
    except ValueError as e:
        return jsonify({"ok": False, "error": {"message": str(e)}}), 400


@irrigation_bp.route("/calibration/pump/<int:actuator_id>", methods=["GET"])
@safe_route("Failed to get pump calibration")
def get_pump_calibration(actuator_id: int) -> Response:
    """
    Get current calibration data for a pump actuator.

    Returns:
    - calibration_data: Current calibration info (flow rate, confidence, history)
    """
    try:
        pump_cal = get_pump_calibration_service()
    except RuntimeError as e:
        return jsonify({"ok": False, "error": {"message": str(e)}}), 503

    cal_data = pump_cal.get_calibration_data(actuator_id)
    if cal_data:
        return jsonify(
            {
                "ok": True,
                "data": cal_data.to_dict(),
            }
        )
    else:
        return jsonify(
            {
                "ok": True,
                "data": None,
                "message": "No calibration data for this actuator",
            }
        )


@irrigation_bp.route("/calibration/pump/<int:actuator_id>/adjust", methods=["POST"])
@safe_route("Failed to adjust pump calibration")
def adjust_pump_calibration(actuator_id: int) -> Response:
    """
    Adjust pump calibration based on post-irrigation feedback.

    Use this when the irrigation result doesn't match expectations.
    The ML feedback loop will refine the flow rate estimate.

    Request body:
    - feedback: "too_little", "just_right", or "too_much"
    - adjustment_factor: Optional adjustment percentage (e.g., 0.05 = 5%)
    """
    try:
        pump_cal = get_pump_calibration_service()
    except RuntimeError as e:
        return jsonify({"ok": False, "error": {"message": str(e)}}), 503

    data = request.get_json() or {}
    feedback = data.get("feedback")
    if not feedback:
        return jsonify({"ok": False, "error": {"message": "Missing required field: feedback"}}), 400
    if feedback not in {"too_little", "just_right", "too_much"}:
        return jsonify(
            {"ok": False, "error": {"message": "Invalid feedback. Use: too_little, just_right, too_much"}}
        ), 400

    adjustment_factor = data.get("adjustment_factor")
    if adjustment_factor is not None:
        try:
            adjustment_factor = float(adjustment_factor)
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": {"message": "Invalid 'adjustment_factor'"}}), 400
        if adjustment_factor <= 0 or adjustment_factor >= 1:
            return jsonify({"ok": False, "error": {"message": "'adjustment_factor' must be between 0 and 1"}}), 400

    if adjustment_factor is None:
        new_flow_rate = pump_cal.adjust_from_feedback(
            actuator_id=actuator_id,
            feedback=feedback,
        )
    else:
        new_flow_rate = pump_cal.adjust_from_feedback(
            actuator_id=actuator_id,
            feedback=feedback,
            adjustment_factor=adjustment_factor,
        )
    if new_flow_rate:
        return jsonify(
            {
                "ok": True,
                "data": {
                    "actuator_id": actuator_id,
                    "adjusted_flow_rate": new_flow_rate,
                    "message": f"Flow rate adjusted to {new_flow_rate:.2f} ml/s based on feedback",
                },
            }
        )
    else:
        return jsonify(
            {"ok": False, "error": {"message": "No calibration data exists for this actuator to adjust"}}
        ), 400


@irrigation_bp.route("/calibration/pump/<int:actuator_id>/history", methods=["GET"])
@safe_route("Failed to get pump calibration history")
def get_pump_calibration_history(actuator_id: int) -> Response:
    """
    Get calibration history and trend analysis for a pump.

    Returns history of calibrations and feedback adjustments with trend analysis.
    This helps identify pump degradation, recalibration needs, and validate
    feedback-based adjustments over time.
    ---
    tags:
      - Irrigation
      - Pump Calibration
    parameters:
      - name: actuator_id
        in: path
        type: integer
        required: true
        description: The pump actuator ID
    responses:
      200:
        description: Calibration history and trend analysis
        schema:
          type: object
          properties:
            ok:
              type: boolean
              example: true
            data:
              type: object
              properties:
                actuator_id:
                  type: integer
                  example: 1
                current_flow_rate:
                  type: number
                  example: 3.333
                  description: Current calibrated flow rate in ml/s
                current_confidence:
                  type: number
                  example: 0.85
                  description: Confidence in calibration (1.0 = manual, decreases with adjustments)
                feedback_adjustments_count:
                  type: integer
                  example: 3
                  description: Number of feedback-based adjustments
                last_feedback_adjustment:
                  type: string
                  format: date-time
                  nullable: true
                  description: ISO timestamp of last feedback adjustment
                calibration_history:
                  type: array
                  items:
                    type: object
                    properties:
                      flow_rate_ml_per_second:
                        type: number
                      measured_volume_ml:
                        type: number
                      duration_seconds:
                        type: number
                      calibrated_at:
                        type: string
                      confidence:
                        type: number
                      method:
                        type: string
                        enum: [manual, feedback_adjustment_too_little, feedback_adjustment_too_much]
                trend_analysis:
                  type: object
                  nullable: true
                  description: Flow rate trend analysis (null if < 2 history entries)
                  properties:
                    trend:
                      type: string
                      enum: [stable, increasing, decreasing]
                    consistency:
                      type: string
                      enum: [consistent, variable]
                    current_rate:
                      type: number
                    average_rate:
                      type: number
                    std_dev:
                      type: number
                    sample_count:
                      type: integer
                    rate_change_percent:
                      type: number
      404:
        description: No calibration data for this actuator
      503:
        description: Pump calibration service not available
    """
    try:
        pump_cal = get_pump_calibration_service()
    except RuntimeError as e:
        return jsonify({"ok": False, "error": {"message": str(e)}}), 503

    calibration = pump_cal.get_calibration_data(actuator_id)
    if not calibration:
        return jsonify({"ok": False, "error": {"message": "No calibration data for this actuator"}}), 404

    trend = calibration.get_flow_rate_trend()

    return jsonify(
        {
            "ok": True,
            "data": {
                "actuator_id": actuator_id,
                "current_flow_rate": calibration.flow_rate_ml_per_second,
                "current_confidence": calibration.calibration_confidence,
                "feedback_adjustments_count": calibration.feedback_adjustments_count,
                "last_feedback_adjustment": calibration.last_feedback_adjustment,
                "calibration_history": calibration.calibration_history,
                "trend_analysis": trend,
            },
        }
    )


@irrigation_bp.route("/recommendations/<int:plant_id>", methods=["GET"])
@safe_route("Failed to get irrigation recommendations")
def get_irrigation_recommendations(plant_id: int) -> Response:
    """
    Get smart irrigation recommendations for a plant.

    Analyzes plant requirements, current soil moisture, growth stage, and
    environmental thresholds to provide actionable irrigation recommendations.
    ---
    tags:
      - Irrigation
    parameters:
      - name: plant_id
        in: path
        type: integer
        required: true
        description: The plant ID
      - name: current_moisture
        in: query
        type: number
        required: false
        description: Current soil moisture percentage (0-100). If not provided, will use latest sensor reading.
    responses:
      200:
        description: Irrigation recommendation with calculation preview
        schema:
          type: object
          properties:
            ok:
              type: boolean
              example: true
            data:
              type: object
              properties:
                plant_id:
                  type: integer
                  example: 1
                current_moisture:
                  type: number
                  example: 42.5
                recommendation:
                  type: object
                  properties:
                    recommendation:
                      type: string
                      enum: [water_now, wait, monitor]
                      description: Recommended action
                    urgency:
                      type: string
                      enum: [high, medium, low]
                      description: Urgency level of the recommendation
                    reason:
                      type: string
                      description: Human-readable explanation
                    reasoning:
                      type: array
                      items:
                        type: string
                      description: List of factors considered
                    threshold_proposals:
                      type: array
                      items:
                        type: string
                      description: Suggested threshold adjustments
                calculation:
                  type: object
                  properties:
                    plant_id:
                      type: integer
                    volume_ml:
                      type: number
                      description: Recommended water volume in milliliters
                    duration_seconds:
                      type: number
                      description: Estimated pump runtime in seconds
                    confidence:
                      type: number
                      description: Calculation confidence (0.0-1.0)
                    reasoning:
                      type: array
                      items:
                        type: string
      503:
        description: Plant service not available
    """
    from app.domain.irrigation_calculator import IrrigationCalculator

    plant_service = get_plant_service()
    if not plant_service:
        return error_response("Plant service not available", status=503)

    calculator = IrrigationCalculator(plant_service)

    # Get current moisture from query param or sensor
    current_moisture = request.args.get("current_moisture", type=float)
    if current_moisture is None:
        # Try to get from sensor data
        plant = plant_service.get_plant(plant_id)
        if plant:
            current_moisture = plant.get_moisture_level()

        if current_moisture is None:
            analytics_repo = get_analytics_repo()
            if analytics_repo:
                latest = analytics_repo.get_soil_moisture_history(plant_id)
                if latest:
                    current_moisture = latest[0].get("soil_moisture", 50.0)

    if current_moisture is None:
        # Fall back to neutral soil moisture to keep calculator stable
        current_moisture = 50.0

    # Get recommendation
    recommendation = calculator.get_recommendations(
        plant_id=plant_id,
        current_moisture=current_moisture,
    )

    # Get calculation preview
    calculation = calculator.calculate(plant_id=plant_id)

    return success_response(
        {
            "plant_id": plant_id,
            "current_moisture": current_moisture,
            "recommendation": recommendation,
            "calculation": calculation.to_dict(),
        }
    )


@irrigation_bp.route("/calculate/<int:plant_id>", methods=["GET"])
@safe_route("Failed to calculate irrigation")
def calculate_irrigation(plant_id: int) -> Response:
    """
    Calculate irrigation parameters for a plant.

    Returns the optimal water volume, duration, and confidence based on:
    - Plant pot size and growing medium
    - Current growth stage
    - Pump calibration (if available)
    - Optional ML model predictions (when use_ml=true)
    ---
    tags:
      - Irrigation
    parameters:
      - name: plant_id
        in: path
        type: integer
        required: true
        description: The plant ID
      - name: pump_flow_rate
        in: query
        type: number
        required: false
        description: Override calibrated pump flow rate (ml/s). If not provided, uses calibrated rate.
      - name: use_ml
        in: query
        type: boolean
        required: false
        default: false
        description: Enable ML-enhanced calculation for adaptive irrigation recommendations
    responses:
      200:
        description: Irrigation calculation parameters
        schema:
          type: object
          properties:
            ok:
              type: boolean
              example: true
            data:
              type: object
              properties:
                plant_id:
                  type: integer
                  example: 1
                volume_ml:
                  type: number
                  example: 250.5
                  description: Recommended water volume in milliliters
                duration_seconds:
                  type: number
                  example: 75.2
                  description: Estimated pump runtime in seconds (null if no pump calibration)
                confidence:
                  type: number
                  example: 0.85
                  description: Calculation confidence (0.0-1.0)
                reasoning:
                  type: array
                  items:
                    type: string
                  description: Factors considered in calculation
                ml_enhanced:
                  type: boolean
                  description: Whether ML prediction was used
                ml_prediction:
                  type: object
                  nullable: true
                  description: ML model prediction details (if use_ml=true)
                  properties:
                    volume_ml:
                      type: number
                    confidence:
                      type: number
                    model_version:
                      type: string
      503:
        description: Plant service not available
    """
    from app.domain.irrigation_calculator import IrrigationCalculator

    plant_service = get_plant_service()
    if not plant_service:
        return jsonify({"ok": False, "error": {"message": "Plant service not available"}}), 503

    calculator = IrrigationCalculator(plant_service)

    # Get optional params
    pump_flow_rate = request.args.get("pump_flow_rate", type=float)
    use_ml = request.args.get("use_ml", "false").lower() == "true"

    # Calculate
    if use_ml:
        calculation = calculator.calculate_with_ml(
            plant_id=plant_id,
            pump_flow_rate=pump_flow_rate,
        )
    else:
        calculation = calculator.calculate(
            plant_id=plant_id,
            pump_flow_rate=pump_flow_rate,
        )

    return jsonify(
        {
            "ok": True,
            "data": calculation.to_dict(),
        }
    )


@irrigation_bp.route("/send-recommendation/<int:plant_id>", methods=["POST"])
@safe_route("Failed to send irrigation recommendation")
def send_recommendation_notification(plant_id: int) -> Response:
    """
    Send an irrigation recommendation notification to the plant owner.

    Generates a recommendation based on current conditions and sends it as
    an actionable notification. Supports threshold proposal notifications
    when significant adjustments are recommended.
    ---
    tags:
      - Irrigation
      - Notifications
    parameters:
      - name: plant_id
        in: path
        type: integer
        required: true
        description: The plant ID
      - name: body
        in: body
        required: false
        schema:
          type: object
          properties:
            current_moisture:
              type: number
              description: Override soil moisture percentage (0-100)
    responses:
      200:
        description: Notification result with recommendation details
        schema:
          type: object
          properties:
            ok:
              type: boolean
              example: true
            data:
              type: object
              properties:
                sent:
                  type: boolean
                  description: Whether notification was sent
                message_id:
                  type: integer
                  nullable: true
                  description: Notification message ID (if sent)
                reason:
                  type: string
                  description: Reason if notification was not sent
                recommendation:
                  type: object
                  properties:
                    recommendation:
                      type: string
                      enum: [water_now, wait, monitor]
                    urgency:
                      type: string
                      enum: [high, medium, low]
                    reason:
                      type: string
                calculation:
                  type: object
                  properties:
                    volume_ml:
                      type: number
                    duration_seconds:
                      type: number
                    confidence:
                      type: number
      404:
        description: Plant not found
      503:
        description: Plant service or notification service not available
    """
    from app.blueprints.api._common import get_notifications_service
    from app.domain.irrigation_calculator import IrrigationCalculator
    from app.enums import NotificationSeverity, NotificationType

    plant_service = get_plant_service()
    if not plant_service:
        return jsonify({"ok": False, "error": {"message": "Plant service not available"}}), 503

    # Get plant info
    plant = plant_service.get_plant(plant_id)
    if not plant:
        return jsonify({"ok": False, "error": {"message": "Plant not found"}}), 404

    calculator = IrrigationCalculator(plant_service)

    # Get current moisture
    raw = request.get_json() or {}
    current_moisture = raw.get("current_moisture")
    if current_moisture is None:
        # Try to get from sensor data
        plant = plant_service.get_plant(plant_id)
        if plant:
            current_moisture = plant.get_moisture_level()

            if not current_moisture:
                analytics_repo = get_analytics_repo()
                latest = analytics_repo.get_soil_moisture_history(plant_id)
                current_moisture = latest[0].get("soil_moisture", 50.0)

    # Get recommendation
    recommendation = calculator.get_recommendations(
        plant_id=plant_id,
        current_moisture=current_moisture,
    )

    # Get calculation for the notification
    calculation = calculator.calculate(plant_id=plant_id)

    # Determine if we should send notification
    rec_type = recommendation.get("recommendation", "monitor")
    if rec_type == "monitor":
        return jsonify(
            {
                "ok": True,
                "data": {
                    "sent": False,
                    "reason": "No action needed - plant moisture levels are adequate",
                    "recommendation": recommendation,
                },
            }
        )

    # Get notification service
    try:
        notifications_service = get_notifications_service()
    except RuntimeError:
        return jsonify({"ok": False, "error": {"message": "Notification service not available"}}), 503

    # Get user_id
    user_id = get_user_id()
    if not user_id:
        return jsonify({"ok": False, "error": {"message": "User not authenticated"}}), 401

    # Build notification message
    plant_name = plant.plant_name or f"Plant #{plant_id}"
    urgency = recommendation.get("urgency", "low")
    reason = recommendation.get("reason", "")
    volume_ml = calculation.volume_ml
    duration_s = calculation.duration_seconds

    severity_map = {
        "high": NotificationSeverity.CRITICAL,
        "medium": NotificationSeverity.WARNING,
        "low": NotificationSeverity.INFO,
    }
    severity = severity_map.get(urgency, NotificationSeverity.INFO)

    if rec_type == "water_now":
        title = f"💧 {plant_name} Needs Water"
        message = f"{reason}\n\nRecommended: {volume_ml:.0f}ml ({duration_s:.0f}s)"
    else:  # wait
        title = f"⏰ {plant_name} - Irrigation Reminder"
        message = f"{reason}\n\nWhen ready: {volume_ml:.0f}ml ({duration_s:.0f}s)"

    # Add threshold proposals if any
    threshold_proposals = recommendation.get("threshold_proposals", [])
    if threshold_proposals:
        message += "\n\nSuggested threshold updates:"
        for tp in threshold_proposals[:3]:  # Max 3 proposals
            message += f"\n• {tp}"

    # Send notification
    message_id = notifications_service.send_notification(
        user_id=user_id,
        notification_type=NotificationType.IRRIGATION_RECOMMENDATION,
        title=title,
        message=message,
        severity=severity,
        unit_id=plant.unit_id,
        requires_action=rec_type == "water_now",
        action_type="irrigation_recommendation",
        action_data={
            "plant_id": plant_id,
            "unit_id": plant.unit_id,
            "recommendation": rec_type,
            "urgency": urgency,
            "volume_ml": volume_ml,
            "duration_seconds": duration_s,
            "current_moisture": current_moisture,
            "threshold_proposals": threshold_proposals,
            "actions": ["water_now", "delay", "dismiss"],
        },
    )

    return jsonify(
        {
            "ok": True,
            "data": {
                "sent": message_id is not None,
                "message_id": message_id,
                "recommendation": recommendation,
                "calculation": calculation.to_dict(),
            },
        }
    )
