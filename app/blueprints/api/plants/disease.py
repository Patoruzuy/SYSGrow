"""
Disease Tracking API Routes

Endpoints for recording, viewing, and managing disease occurrences.
Completes the disease tracking feedback loop for ML model improvement.
"""

from __future__ import annotations

import logging

from flask import Blueprint, Response, jsonify, request

from app.blueprints.api._common import get_container
from app.utils.http import safe_route

logger = logging.getLogger(__name__)

disease_bp = Blueprint("disease", __name__)


def _get_ai_repo():
    """Get the AI repository from the container."""
    container = get_container()
    return getattr(container, "ai_repo", None)


def _get_disease_predictor():
    """Get the disease predictor service from container."""
    container = get_container()
    return getattr(container, "disease_predictor", None)


@disease_bp.route("/occurrences", methods=["POST"])
@safe_route("Failed to record disease occurrence")
def record_disease_occurrence() -> Response:
    """
    Record a confirmed disease occurrence.

    This endpoint allows users to log when a disease is detected/confirmed,
    providing training data for ML models and creating a disease history.

    Request body:
    {
        "unit_id": 1,                    // Required
        "plant_id": 5,                   // Optional
        "disease_type": "fungal",        // Required: fungal, bacterial, viral, pest, nutrient_deficiency, environmental_stress
        "severity": "moderate",          // Optional: mild, moderate, severe (default: mild)
        "symptoms": "yellowing leaves, white spots",  // Optional
        "affected_parts": "leaves, stems",            // Optional
        "notes": "First noticed 2 days ago"           // Optional
    }
    """
    ai_repo = _get_ai_repo()
    if not ai_repo:
        return jsonify({"ok": False, "data": None, "error": {"message": "AI repository not available"}}), 503

    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "data": None, "error": {"message": "Request body is required"}}), 400

    # Validate required fields
    unit_id = data.get("unit_id")
    disease_type = data.get("disease_type")

    if not unit_id:
        return jsonify({"ok": False, "data": None, "error": {"message": "unit_id is required"}}), 400

    if not disease_type:
        return jsonify({"ok": False, "data": None, "error": {"message": "disease_type is required"}}), 400

    valid_types = ["fungal", "bacterial", "viral", "pest", "nutrient_deficiency", "environmental_stress"]
    if disease_type.lower() not in valid_types:
        return jsonify(
            {
                "ok": False,
                "data": None,
                "error": {"message": f"disease_type must be one of: {', '.join(valid_types)}"},
            }
        ), 400

    # Get current environmental conditions for the record
    env_data = _get_current_environmental_data(unit_id)

    # Prepare occurrence data
    occurrence_data = {
        "unit_id": unit_id,
        "plant_id": data.get("plant_id"),
        "disease_type": disease_type.lower(),
        "severity": data.get("severity", "mild"),
        "confirmed_by_user": True,
        "symptoms": data.get("symptoms"),
        "affected_parts": data.get("affected_parts"),
        "notes": data.get("notes"),
        "plant_type": data.get("plant_type"),
        "growth_stage": data.get("growth_stage"),
        "days_in_stage": data.get("days_in_stage"),
        # Environmental snapshot
        "temperature_at_detection": env_data.get("temperature"),
        "humidity_at_detection": env_data.get("humidity"),
        "soil_moisture_at_detection": env_data.get("soil_moisture"),
        "vpd_at_detection": env_data.get("vpd"),
        "avg_temperature_72h": env_data.get("avg_temperature_72h"),
        "avg_humidity_72h": env_data.get("avg_humidity_72h"),
        "avg_soil_moisture_72h": env_data.get("avg_soil_moisture_72h"),
        "humidity_variance_72h": env_data.get("humidity_variance_72h"),
    }

    occurrence_id = ai_repo.save_disease_occurrence(occurrence_data)

    if occurrence_id:
        logger.info("Disease occurrence recorded: %s for unit %s", disease_type, unit_id)
        return jsonify(
            {
                "ok": True,
                "data": {"occurrence_id": occurrence_id, "message": "Disease occurrence recorded successfully"},
                "error": None,
            }
        ), 201
    else:
        return jsonify({"ok": False, "data": None, "error": {"message": "Failed to save disease occurrence"}}), 500


@disease_bp.route("/occurrences/<int:occurrence_id>", methods=["GET"])
@safe_route("Failed to get disease occurrence")
def get_disease_occurrence(occurrence_id: int) -> Response:
    """
    Get details of a specific disease occurrence.
    """
    ai_repo = _get_ai_repo()
    if not ai_repo:
        return jsonify({"ok": False, "data": None, "error": {"message": "AI repository not available"}}), 503

    occurrence = ai_repo.get_disease_occurrence_by_id(occurrence_id)

    if not occurrence:
        return jsonify({"ok": False, "data": None, "error": {"message": "Disease occurrence not found"}}), 404

    return jsonify({"ok": True, "data": occurrence, "error": None}), 200


@disease_bp.route("/occurrences/<int:occurrence_id>/resolve", methods=["PUT"])
@safe_route("Failed to resolve disease occurrence")
def resolve_disease_occurrence(occurrence_id: int) -> Response:
    """
    Mark a disease occurrence as resolved with treatment details.

    Request body:
    {
        "treatment_applied": "Applied fungicide (neem oil)",  // Required
        "notes": "Plant recovered fully after 2 weeks"        // Optional
    }
    """
    ai_repo = _get_ai_repo()
    if not ai_repo:
        return jsonify({"ok": False, "data": None, "error": {"message": "AI repository not available"}}), 503

    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "data": None, "error": {"message": "Request body is required"}}), 400

    treatment_applied = data.get("treatment_applied")
    if not treatment_applied:
        return jsonify({"ok": False, "data": None, "error": {"message": "treatment_applied is required"}}), 400

    success = ai_repo.resolve_disease_occurrence(
        occurrence_id=occurrence_id,
        treatment_applied=treatment_applied,
        notes=data.get("notes"),
    )

    if success:
        logger.info("Disease occurrence %s resolved with treatment: %s", occurrence_id, treatment_applied)
        return jsonify(
            {"ok": True, "data": {"message": "Disease occurrence resolved successfully"}, "error": None}
        ), 200
    else:
        return jsonify(
            {"ok": False, "data": None, "error": {"message": "Disease occurrence not found or already resolved"}}
        ), 404


@disease_bp.route("/history", methods=["GET"])
@safe_route("Failed to get disease history")
def get_disease_history() -> Response:
    """
    Get disease occurrence history with optional filters.

    Query parameters:
    - unit_id: Filter by growth unit
    - plant_id: Filter by specific plant
    - disease_type: Filter by disease type
    - include_resolved: Include resolved occurrences (default: true)
    - limit: Max records (default: 100, max: 500)
    - offset: Pagination offset
    """
    ai_repo = _get_ai_repo()
    if not ai_repo:
        return jsonify({"ok": False, "data": None, "error": {"message": "AI repository not available"}}), 503

    unit_id = request.args.get("unit_id", type=int)
    plant_id = request.args.get("plant_id", type=int)
    disease_type = request.args.get("disease_type")
    include_resolved = request.args.get("include_resolved", "true").lower() != "false"
    limit = min(request.args.get("limit", 100, type=int), 500)
    offset = request.args.get("offset", 0, type=int)

    history = ai_repo.get_disease_history(
        unit_id=unit_id,
        plant_id=plant_id,
        disease_type=disease_type,
        include_resolved=include_resolved,
        limit=limit,
        offset=offset,
    )

    return jsonify(
        {
            "ok": True,
            "data": {
                "count": len(history),
                "occurrences": history,
                "filters": {
                    "unit_id": unit_id,
                    "plant_id": plant_id,
                    "disease_type": disease_type,
                    "include_resolved": include_resolved,
                },
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                },
            },
            "error": None,
        }
    ), 200


@disease_bp.route("/statistics", methods=["GET"])
@safe_route("Failed to get disease statistics")
def get_disease_statistics() -> Response:
    """
    Get disease occurrence statistics and summaries.

    Query parameters:
    - unit_id: Filter by growth unit (optional)
    - days: Number of days to analyze (default: 90)
    """
    ai_repo = _get_ai_repo()
    if not ai_repo:
        return jsonify({"ok": False, "data": None, "error": {"message": "AI repository not available"}}), 503

    unit_id = request.args.get("unit_id", type=int)
    days = request.args.get("days", 90, type=int)

    stats = ai_repo.get_disease_summary_stats(
        unit_id=unit_id,
        days_limit=days,
    )

    return jsonify({"ok": True, "data": stats, "error": None}), 200


@disease_bp.route("/prediction/feedback", methods=["POST"])
@safe_route("Failed to record prediction feedback")
def record_prediction_feedback() -> Response:
    """
    Record feedback on a disease prediction (was it accurate?).

    This helps improve ML model accuracy through user feedback.

    Request body:
    {
        "prediction_id": "pred_abc123",           // Optional - prediction identifier
        "unit_id": 1,                             // Required
        "predicted_disease_type": "fungal",       // Required - what was predicted
        "predicted_risk_level": "high",           // Required - low, moderate, high, critical
        "predicted_risk_score": 0.85,             // Optional - confidence score
        "actual_disease_occurred": true,          // Required - did disease actually occur?
        "actual_disease_type": "fungal",          // Optional - if occurred, what type?
        "actual_severity": "moderate",            // Optional - if occurred, how severe?
        "days_to_occurrence": 5,                  // Optional - days from prediction to occurrence
        "feedback_source": "user"                 // Optional - user, automated, expert
    }
    """
    ai_repo = _get_ai_repo()
    if not ai_repo:
        return jsonify({"ok": False, "data": None, "error": {"message": "AI repository not available"}}), 503

    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "data": None, "error": {"message": "Request body is required"}}), 400

    # Validate required fields
    required = ["unit_id", "predicted_disease_type", "predicted_risk_level", "actual_disease_occurred"]
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify(
            {"ok": False, "data": None, "error": {"message": f"Missing required fields: {', '.join(missing)}"}}
        ), 400

    feedback_id = ai_repo.save_disease_prediction_feedback(data)

    if feedback_id:
        logger.info("Prediction feedback recorded for unit %s", data["unit_id"])
        return jsonify(
            {
                "ok": True,
                "data": {"feedback_id": feedback_id, "message": "Prediction feedback recorded successfully"},
                "error": None,
            }
        ), 201
    else:
        return jsonify({"ok": False, "data": None, "error": {"message": "Failed to save prediction feedback"}}), 500


@disease_bp.route("/prediction/accuracy", methods=["GET"])
@safe_route("Failed to get prediction accuracy")
def get_prediction_accuracy() -> Response:
    """
    Get prediction accuracy metrics from feedback data.

    Query parameters:
    - disease_type: Filter by disease type (optional)
    - days: Number of days to analyze (default: 90)
    """
    ai_repo = _get_ai_repo()
    if not ai_repo:
        return jsonify({"ok": False, "data": None, "error": {"message": "AI repository not available"}}), 503

    disease_type = request.args.get("disease_type")
    days = request.args.get("days", 90, type=int)

    metrics = ai_repo.get_disease_prediction_accuracy(
        disease_type=disease_type,
        days_limit=days,
    )

    return jsonify({"ok": True, "data": metrics, "error": None}), 200


def _get_current_environmental_data(unit_id: int) -> dict:
    """
    Get current environmental conditions for a unit.

    Used to snapshot conditions when recording a disease occurrence.
    """
    try:
        container = get_container()
        analytics_service = getattr(container, "analytics_service", None)

        if not analytics_service:
            return {}

        # Get latest sensor readings
        latest = analytics_service.get_latest_sensor_reading(unit_id=unit_id)
        if not latest:
            return {}

        # Get 72-hour averages if available
        avg_data = {}
        try:
            history = analytics_service.get_sensor_history(
                unit_id=unit_id,
                hours=72,
            )
            if history and len(history) > 0:
                temps = [r.get("temperature") for r in history if r.get("temperature") is not None]
                humidities = [r.get("humidity") for r in history if r.get("humidity") is not None]
                moistures = [r.get("soil_moisture") for r in history if r.get("soil_moisture") is not None]

                if temps:
                    avg_data["avg_temperature_72h"] = sum(temps) / len(temps)
                if humidities:
                    avg_data["avg_humidity_72h"] = sum(humidities) / len(humidities)
                    # Calculate variance
                    mean = avg_data["avg_humidity_72h"]
                    variance = sum((h - mean) ** 2 for h in humidities) / len(humidities)
                    avg_data["humidity_variance_72h"] = variance
                if moistures:
                    avg_data["avg_soil_moisture_72h"] = sum(moistures) / len(moistures)
        except (RuntimeError, ValueError, TypeError) as exc:
            logger.debug("Failed to compute 72h environmental averages for unit %s: %s", unit_id, exc)

        return {
            "temperature": latest.get("temperature"),
            "humidity": latest.get("humidity"),
            "soil_moisture": latest.get("soil_moisture"),
            "vpd": latest.get("vpd"),
            **avg_data,
        }

    except Exception as e:
        logger.warning("Could not get environmental data for unit %s: %s", unit_id, e)
        return {}
