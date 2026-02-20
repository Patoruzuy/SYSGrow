"""
Plant Health Monitoring
========================

Endpoints for recording and analyzing plant health observations, symptoms,
and recommendations. Includes integration with AI health monitoring.
"""

from __future__ import annotations

import logging

from flask import Response, current_app, request

from app.blueprints.api._common import (
    fail as _fail,
    get_container,
    get_plant_service as _plant_service,
    success as _success,
)
from app.utils.http import safe_route

from . import plants_api

logger = logging.getLogger("plants_api.health")


# ============================================================================
# PLANT HEALTH MONITORING
# ============================================================================

# Deprecated endpoint /api/plants/health/summary removed - use /api/health/plants/summary instead


@plants_api.post("/plants/<int:plant_id>/health/record")
@safe_route("Failed to record plant health observation")
def record_plant_health(plant_id: int) -> Response:
    """
    Record a plant health observation with optional image upload

    Accepts: multipart/form-data or application/json

    Form fields / JSON body:
    {
        "health_status": "stressed",  // Required: healthy, stressed, diseased, pest_infestation, nutrient_deficiency, dying
        "symptoms": ["yellowing_leaves", "wilting"],  // Optional JSON array or comma-separated string
        "disease_type": "fungal",  // Optional: fungal, bacterial, viral, pest, nutrient_deficiency, environmental_stress
        "severity_level": 3,  // Optional: 1-5 scale (required if not healthy)
        "affected_parts": ["leaves", "stems"],  // Optional JSON array or comma-separated string
        "treatment_applied": "Applied fungicide",  // Optional
        "notes": "Lower leaves showing yellowing",  // Required
        "growth_stage": "Vegetative"  // Optional, will be auto-detected if not provided
    }

    File field:
    - image: Image file (jpg, png, gif) - optional
    """
    logger.info("Recording health observation for plant %s", plant_id)
    import json
    import os

    from werkzeug.utils import secure_filename

    from app.services.ai import DiseaseType, HealthStatus, PlantHealthObservation

    plant_service = _plant_service()

    # Verify plant exists
    plant = plant_service.get_plant(plant_id)
    if not plant:
        return _fail(f"Plant {plant_id} not found", 404)

    # Handle both JSON and form-data
    if request.is_json:
        payload = request.get_json() or {}
        image_file = None
    else:
        # Form data (multipart)
        payload = request.form.to_dict()
        image_file = request.files.get("image")

    # Validate required fields
    health_status_str = payload.get("health_status")
    notes = payload.get("notes", "").strip()

    if not health_status_str:
        return _fail("Missing required field: health_status", 400)

    if not notes:
        return _fail("Missing required field: notes", 400)

    # Parse health status
    try:
        health_status = HealthStatus(health_status_str)
    except ValueError:
        valid_statuses = [s.value for s in HealthStatus]
        return _fail(f"Invalid health_status. Must be one of: {', '.join(valid_statuses)}", 400)

    # Parse symptoms (handle JSON string or comma-separated)
    symptoms = []
    symptoms_data = payload.get("symptoms")
    if symptoms_data:
        if isinstance(symptoms_data, str):
            try:
                symptoms = json.loads(symptoms_data)
            except json.JSONDecodeError:
                # Try comma-separated
                symptoms = [s.strip() for s in symptoms_data.split(",") if s.strip()]
        elif isinstance(symptoms_data, list):
            symptoms = symptoms_data

    # Parse affected parts (handle JSON string or comma-separated)
    affected_parts = []
    affected_data = payload.get("affected_parts")
    if affected_data:
        if isinstance(affected_data, str):
            try:
                affected_parts = json.loads(affected_data)
            except json.JSONDecodeError:
                # Try comma-separated
                affected_parts = [p.strip() for p in affected_data.split(",") if p.strip()]
        elif isinstance(affected_data, list):
            affected_parts = affected_data

    # Parse severity level
    severity = None
    if payload.get("severity_level"):
        try:
            severity = int(payload["severity_level"])
            if severity < 1 or severity > 5:
                return _fail("severity_level must be between 1 and 5", 400)
        except (ValueError, TypeError):
            return _fail("severity_level must be an integer", 400)

    # If not healthy, severity is recommended
    if health_status != HealthStatus.HEALTHY and severity is None:
        logger.warning("No severity provided for non-healthy status: %s", health_status_str)

    # Parse disease type (optional)
    disease_type = None
    if payload.get("disease_type"):
        try:
            disease_type = DiseaseType(payload["disease_type"])
        except ValueError:
            valid_types = [t.value for t in DiseaseType]
            return _fail(f"Invalid disease_type. Must be one of: {', '.join(valid_types)}", 400)

    # Handle image upload
    image_path = None
    if image_file and image_file.filename:
        # Validate file type
        allowed_extensions = {"png", "jpg", "jpeg", "gif", "webp"}
        filename = secure_filename(image_file.filename)
        file_ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""

        if file_ext not in allowed_extensions:
            return _fail(f"Invalid image format. Allowed: {', '.join(allowed_extensions)}", 400)

        # Create uploads directory if not exists
        upload_dir = os.path.join(current_app.root_path, "..", "uploads", "plant_health")
        os.makedirs(upload_dir, exist_ok=True)

        # Generate unique filename
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"plant_{plant_id}_{timestamp}.{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)

        # Save file
        image_file.save(file_path)

        # Store relative path for database
        image_path = f"/uploads/plant_health/{unique_filename}"
        logger.info("Saved health observation image: %s", image_path)

    # Get plant_type and growth_stage
    plant_type = plant.get("plant_type")
    growth_stage = payload.get("growth_stage") or plant.get("current_growth_stage")

    # Get environmental data for context
    unit_id = plant.get("unit_id")

    # Create observation
    observation = PlantHealthObservation(
        unit_id=unit_id,
        plant_id=plant_id,
        health_status=health_status,
        symptoms=symptoms,
        disease_type=disease_type,
        severity_level=severity or 0,
        affected_parts=affected_parts,
        environmental_factors={},  # Will be filled by monitor
        treatment_applied=payload.get("treatment_applied"),
        notes=notes,
        plant_type=plant_type,
        growth_stage=growth_stage,
        image_path=image_path,
        user_id=payload.get("user_id"),
    )

    # Record observation via the DI-wired health monitor
    health_monitor = get_container().plant_health_monitor
    health_id = health_monitor.record_health_observation(observation)

    # Get correlations
    correlations = health_monitor.analyze_environmental_correlation(observation)

    return _success(
        {
            "health_id": health_id,
            "plant_id": plant_id,
            "plant_name": plant.get("plant_name"),
            "plant_type": plant_type,
            "growth_stage": growth_stage,
            "observation_date": observation.observation_date.isoformat(),
            "image_path": image_path,
            "correlations": [
                {
                    "factor": corr.factor_name,
                    "strength": round(corr.correlation_strength, 2),
                    "confidence": round(corr.confidence_level, 2),
                    "recommended_range": corr.recommended_range,
                    "current_value": round(corr.current_value, 2),
                    "trend": corr.trend,
                }
                for corr in correlations
            ],
            "message": f"Health observation recorded successfully for {plant.get('plant_name')}",
        },
        201,
    )


@plants_api.get("/plants/<int:plant_id>/health/history")
@safe_route("Failed to get plant health history")
def get_plant_health_history(plant_id: int) -> Response:
    """
    Get health observation history for a plant

    Query params:
    - days: Number of days of history (default: 7)
    """
    logger.info("Getting health history for plant %s", plant_id)
    try:
        container = get_container()
        repo_health = container.ai_health_repo
    except Exception as e:
        logger.warning("Health monitor unavailable, returning empty history: %s", e)
        return _success(
            {"plant_id": plant_id, "observations": [], "count": 0, "days": request.args.get("days", 7, type=int)}
        )

    plant_service = _plant_service()

    # Verify plant exists
    plant = plant_service.get_plant(plant_id)
    if not plant:
        return _fail(f"Plant {plant_id} not found", 404)

    days = request.args.get("days", 7, type=int)
    plant = plant.to_dict()
    try:
        unit_id = plant.get("unit_id")
        observations = repo_health.get_recent_observations(unit_id, days)
    except Exception as exc:
        logger.warning("Health monitor backend unavailable, returning empty history: %s", exc)
        observations = []

    # Filter for this specific plant
    plant_observations = [obs for obs in observations if obs.get("plant_id") == plant_id]

    return _success(
        {
            "plant_id": plant_id,
            "plant_name": plant.get("plant_name"),
            "plant_type": plant.get("plant_type"),
            "observations": plant_observations,
            "count": len(plant_observations),
            "days": days,
        }
    )


@plants_api.get("/plants/<int:plant_id>/health/recommendations")
@safe_route("Failed to get health recommendations")
def get_plant_health_recommendations(plant_id: int) -> Response:
    """Get health recommendations for a plant"""
    logger.info("Getting health recommendations for plant %s", plant_id)
    container = get_container()
    health_monitor = container.plant_health_monitor

    plant_service = _plant_service()

    # Verify plant exists
    plant = plant_service.get_plant(plant_id)
    if not plant:
        return _fail(f"Plant {plant_id} not found", 404)

    unit_id = plant.get("unit_id")
    plant_type = plant.get("plant_type")
    growth_stage = plant.get("current_growth_stage")

    recommendations = health_monitor.get_health_recommendations(unit_id, plant_type, growth_stage)

    return _success(
        {
            "plant_id": plant_id,
            "plant_name": plant.get("plant_name"),
            "plant_type": plant_type,
            "growth_stage": growth_stage,
            "recommendations": recommendations,
        }
    )


@plants_api.get("/health/symptoms")
@safe_route("Failed to get available symptoms")
def get_available_symptoms() -> Response:
    """Get list of available plant health symptoms"""
    logger.info("Getting available plant health symptoms")
    container = get_container()
    health_monitor = container.plant_health_monitor

    symptoms = [
        {
            "name": symptom,
            "likely_causes": data["likely_causes"],
            "environmental_factors": data["environmental_factors"],
        }
        for symptom, data in health_monitor.symptom_database.items()
    ]

    return _success({"symptoms": symptoms, "count": len(symptoms)})


@plants_api.get("/health/statuses")
@safe_route("Failed to get health statuses")
def get_health_statuses() -> Response:
    """Get list of available health status values"""
    logger.info("Getting available health statuses")
    from app.services.ai import DiseaseType, HealthStatus

    statuses = [{"value": status.value, "name": status.name} for status in HealthStatus]

    disease_types = [{"value": dtype.value, "name": dtype.name} for dtype in DiseaseType]

    return _success({"health_statuses": statuses, "disease_types": disease_types})
