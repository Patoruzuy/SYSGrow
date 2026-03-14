"""
Environment Threshold Management
=================================

Endpoints for managing environmental sensor thresholds for growth units.
Includes recommended thresholds based on plant type and growth stage.
"""
from __future__ import annotations

from flask import jsonify, request
from app.schemas.growth import (
    UnitThresholdUpdate,
    UnitThresholdUpdateV2,
    ThresholdSettings,
    GrowthUnitResponse,
)
from app.domain.environmental_thresholds import EnvironmentalThresholds
import logging

from pydantic import ValidationError
from . import growth_api
from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
    get_container as _container,
    get_growth_service as _service,
)

logger = logging.getLogger("growth_api.thresholds")


def _unit_to_response(unit: dict) -> GrowthUnitResponse:
    """Convert unit dict to typed response"""
    from .units import _unit_to_response as convert
    return convert(unit)


# ============================================================================
# THRESHOLD MANAGEMENT
# ============================================================================

@growth_api.get("/units/<int:unit_id>/thresholds")
def get_thresholds(unit_id: int):
    """Get sensor thresholds for a growth unit"""
    logger.info(f"Getting thresholds for growth unit {unit_id}")
    try:
        if not _service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)
        
        data = _service().get_thresholds(unit_id)
        
        return _success(data)
        
    except Exception as e:
        logger.exception(f"Error getting thresholds for unit {unit_id}: {e}")
        return _fail("Failed to get thresholds", 500)


@growth_api.post("/units/<int:unit_id>/thresholds")
def set_thresholds(unit_id: int):
    """Set sensor thresholds for a growth unit"""
    logger.info(f"Setting thresholds for growth unit {unit_id}")
    try:
        raw = request.get_json() or {}
        try:
            payload = UnitThresholdUpdate(**raw)
        except ValidationError as ve:
            return _fail("Invalid threshold payload", 400, details={"errors": ve.errors()})

        if not _service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)
        
        unit = _service().set_thresholds(
            unit_id,
            temperature_threshold=payload.temperature_threshold,
            humidity_threshold=payload.humidity_threshold,
        )
        unit = unit or {}
        return _success(
            {
                "unit_id": unit.get("unit_id", unit_id),
                "temperature_threshold": unit.get("temperature_threshold", payload.temperature_threshold),
                "humidity_threshold": unit.get("humidity_threshold", payload.humidity_threshold),
            }
        )
        
    except (TypeError, ValueError) as e:
        logger.warning(f"Validation error setting thresholds: {e}")
        return _fail("Threshold values must be numeric", 400)
    except Exception as e:
        logger.exception(f"Error setting thresholds for unit {unit_id}: {e}")
        return _fail("Failed to set thresholds", 500)


@growth_api.post("/v2/units/<int:unit_id>/thresholds")
def update_unit_thresholds_v2(unit_id: int):
    """Typed v2 endpoint for updating thresholds."""
    logger.info("Updating thresholds for growth unit %s via v2 endpoint", unit_id)
    try:
        raw = request.get_json() or {}
        try:
            body = UnitThresholdUpdateV2(**raw)
        except ValidationError as ve:
            return _fail("Invalid threshold payload", 400, details={"errors": ve.errors()})

        updates = {
            "temperature_threshold": body.temperature_threshold,
            "humidity_threshold": body.humidity_threshold,
        }
        if body.co2_threshold is not None:
            updates["co2_threshold"] = body.co2_threshold
        if body.voc_threshold is not None:
            updates["voc_threshold"] = body.voc_threshold
        if body.lux_threshold is not None:
            updates["lux_threshold"] = body.lux_threshold
        if body.air_quality_threshold is not None:
            updates["air_quality_threshold"] = body.air_quality_threshold

        ok = _service().update_unit_thresholds(
            unit_id,
            updates,
        )
        if not ok:
            return _fail("Failed to update thresholds", 500)

        updated = _service().get_unit(unit_id)
        if not updated:
            return _success({"unit_id": unit_id})
        return _success(_unit_to_response(updated).model_dump())
    except Exception as e:
        logger.exception("Error updating thresholds for unit %s: %s", unit_id, e)
        return _fail("Failed to update thresholds", 500)


@growth_api.get("/v2/units/<int:unit_id>/thresholds")
def get_unit_thresholds_v2(unit_id: int):
    """Typed v2 getter for unit thresholds."""
    logger.info("Getting thresholds for growth unit %s via v2 endpoint", unit_id)
    try:
        if not _service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)

        payload = _service().get_thresholds(unit_id)
        return _success(payload)
    except Exception as e:
        logger.exception("Error fetching thresholds for unit %s: %s", unit_id, e)
        return _fail("Failed to fetch thresholds", 500)


@growth_api.get("/thresholds/recommended")
def get_recommended_thresholds():
    """
    Get recommended environmental threshold ranges for a plant type.

    Query parameters:
      - plant_type (required): common name, e.g. 'Tomatoes'
      - growth_stage (optional): stage name, e.g. 'Vegetative'

    Response:
      {
        "plant_type": "...",
        "growth_stage": "...",
        "thresholds": { ... ThresholdSettings ... },
        "raw": { ... full threshold map from ThresholdService ... }
      }
    """
    plant_type = request.args.get("plant_type")
    growth_stage = request.args.get("growth_stage")

    if not plant_type:
        return _fail("plant_type is required", 400)

    container = _container()
    threshold_service = getattr(container, "threshold_service", None) if container else None
    if not threshold_service:
        return _fail("Threshold service not available", 503)

    # Get domain object (modern API - returns EnvironmentalThresholds)
    thresholds_obj = threshold_service.get_thresholds(plant_type, growth_stage)
    
    # Convert to dict for API response
    thresholds_dict = thresholds_obj.to_dict()

    # Build settings from domain object
    settings = ThresholdSettings(
        min_temp=thresholds_dict['temperature'] * 0.9,  # 10% tolerance
        max_temp=thresholds_dict['temperature'] * 1.1,
        min_humidity=thresholds_dict['humidity'] * 0.9,
        max_humidity=thresholds_dict['humidity'] * 1.1,
        min_soil_moisture=thresholds_dict['soil_moisture'] * 0.9,
        max_soil_moisture=thresholds_dict['soil_moisture'] * 1.1,
    )

    return _success(
        {
            "plant_type": plant_type,
            "growth_stage": growth_stage,
            "thresholds": settings.model_dump(),
            "raw": thresholds_obj.to_settings_dict(),  # Full map from ThresholdService
        }
    )


# ============================================================================
# THRESHOLD PROPOSAL HANDLING
# ============================================================================

@growth_api.post("/thresholds/proposal/respond")
def respond_to_threshold_proposal():
    """
    Handle user response to a stage transition threshold proposal.
    
    When a plant transitions to a new growth stage, the system sends a notification
    with proposed threshold changes. This endpoint handles the user's response.
    
    Request body:
        - action: 'apply' | 'keep_current' | 'customize'
        - unit_id: Target unit ID
        - plant_id: Plant that triggered the proposal
        - proposed_thresholds: Dict of proposed values (only for 'apply')
        - custom_thresholds: Dict of custom values (only for 'customize')
    
    Returns:
        - ok: Success status
        - applied_thresholds: The thresholds that were applied (if any)
    """
    raw = request.get_json() or {}
    
    action = raw.get("action")
    unit_id = raw.get("unit_id")
    plant_id = raw.get("plant_id")
    
    if not action:
        return _fail("Missing 'action' field", 400)
    if not unit_id:
        return _fail("Missing 'unit_id' field", 400)
    
    valid_actions = {"apply", "keep_current", "customize"}
    if action not in valid_actions:
        return _fail(f"Invalid action. Must be one of: {valid_actions}", 400)
    
    try:
        container = _container()
        plant_service = getattr(container, "plant_service", None)
        
        if action == "keep_current":
            # User wants to keep current thresholds - no DB update needed
            logger.info(
                "User chose to keep current thresholds for unit %s (plant %s)",
                unit_id, plant_id
            )
            return _success({
                "action": "keep_current",
                "message": "Current thresholds retained",
                "unit_id": unit_id,
            })
        
        elif action == "apply":
            # Apply the proposed per-plant soil moisture threshold
            if not plant_id:
                return _fail("Missing plant_id for apply action", 400)
            if not plant_service:
                return _fail("Plant service not available", 503)

            proposed = raw.get("proposed_thresholds", {})
            if not proposed:
                return _fail("Missing 'proposed_thresholds' for apply action", 400)

            soil_moisture_data = proposed.get("soil_moisture", {})
            new_threshold = soil_moisture_data.get("proposed")

            if new_threshold is None:
                return _fail("No soil moisture threshold in proposal", 400)

            ok = plant_service.update_soil_moisture_threshold(
                int(plant_id),
                float(new_threshold),
                unit_id=unit_id,
            )

            if ok:
                logger.info(
                    "Applied proposed soil moisture threshold %.1f%% for plant %s",
                    new_threshold, plant_id
                )
                return _success({
                    "action": "apply",
                    "message": f"Soil moisture threshold updated to {new_threshold:.1f}%",
                    "unit_id": unit_id,
                    "plant_id": plant_id,
                    "applied_thresholds": {"soil_moisture_threshold": new_threshold},
                })
            return _fail("Failed to apply threshold update", 500)
        
        elif action == "customize":
            if not plant_id:
                return _fail("Missing plant_id for customize action", 400)
            if not plant_service:
                return _fail("Plant service not available", 503)

            custom = raw.get("custom_thresholds", {})
            if not custom:
                return _fail("Missing 'custom_thresholds' for customize action", 400)

            soil_threshold = custom.get("soil_moisture_threshold")
            if soil_threshold is None:
                return _fail("Missing 'soil_moisture_threshold' in custom_thresholds", 400)

            # Validate range (0-100%)
            try:
                soil_threshold = float(soil_threshold)
                if not (0 <= soil_threshold <= 100):
                    return _fail("Soil moisture threshold must be between 0 and 100", 400)
            except (TypeError, ValueError):
                return _fail("Invalid soil moisture threshold value", 400)

            ok = plant_service.update_soil_moisture_threshold(
                int(plant_id),
                soil_threshold,
                unit_id=unit_id,
            )

            if ok:
                logger.info(
                    "Applied custom soil moisture threshold %.1f%% for plant %s",
                    soil_threshold, plant_id
                )
                return _success({
                    "action": "customize",
                    "message": f"Custom soil moisture threshold set to {soil_threshold:.1f}%",
                    "unit_id": unit_id,
                    "plant_id": plant_id,
                    "applied_thresholds": {"soil_moisture_threshold": soil_threshold},
                })
            return _fail("Failed to apply custom threshold", 500)
    
    except Exception as e:
        logger.exception("Error responding to threshold proposal: %s", e)
        return _fail("Failed to process threshold proposal response", 500)
