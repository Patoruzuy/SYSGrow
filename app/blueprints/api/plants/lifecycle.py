"""
Plant Lifecycle Management
===========================

Endpoints for managing plant growth stages and active plant selection for climate control.
"""

from __future__ import annotations

import logging

from flask import request
from pydantic import ValidationError

from app.blueprints.api._common import (
    fail as _fail,
    get_growth_service as _growth_service,
    get_plant_service as _plant_service,
    success as _success,
)
from app.schemas import UpdatePlantStageRequest

from . import plants_api

logger = logging.getLogger("plants_api.lifecycle")


# ============================================================================
# PLANT STAGE MANAGEMENT
# ============================================================================


@plants_api.put("/plants/<int:plant_id>/stage")
def update_plant_stage(plant_id: int):
    """Update plant growth stage"""
    logger.info(f"Updating stage for plant {plant_id}")
    try:
        raw = request.get_json() or {}

        try:
            body = UpdatePlantStageRequest(**raw)
        except ValidationError as ve:
            return _fail("Invalid request", 400, details={"errors": ve.errors()})

        plant_service = _plant_service()

        # Verify plant exists
        plant = plant_service.get_plant(plant_id)
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)

        # Update plant stage
        success = plant_service.update_plant_stage(plant_id, body.stage, body.days_in_stage)

        if success:
            return _success(
                {
                    "plant_id": plant_id,
                    "plant_name": plant.get("plant_name"),
                    "new_stage": body.stage,
                    "days_in_stage": body.days_in_stage,
                    "message": f"Plant stage updated to '{body.stage}'",
                }
            )
        else:
            return _fail("Failed to update plant stage", 500)

    except ValueError as e:
        logger.warning(f"Validation error updating plant stage: {e}")
        return safe_error(e, 400)
    except Exception as e:
        logger.exception(f"Error updating plant {plant_id} stage: {e}")
        return _fail("Failed to update plant stage", 500)


@plants_api.post("/units/<int:unit_id>/plants/<int:plant_id>/active")
def set_active_plant(unit_id: int, plant_id: int):
    """Set a plant as the active plant for climate control"""
    logger.info(f"Setting plant {plant_id} as active in growth unit {unit_id}")
    try:
        # Verify unit exists
        if not _growth_service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)

        plant_service = _plant_service()

        # Verify plant exists
        plant = plant_service.get_plant(plant_id)
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)

        # Verify plant belongs to unit
        if plant.get("unit_id") != unit_id:
            return _fail(f"Plant {plant_id} does not belong to unit {unit_id}", 400)

        # Set as active plant
        success = plant_service.set_active_plant(unit_id, plant_id)

        if success:
            return _success(
                {
                    "unit_id": unit_id,
                    "plant_id": plant_id,
                    "plant_name": plant.get("plant_name"),
                    "message": f"Plant '{plant.get('plant_name')}' set as active for climate control",
                }
            )
        else:
            return _fail("Failed to set active plant", 500)

    except Exception as e:
        logger.exception(f"Error setting active plant {plant_id}: {e}")
        return _fail("Failed to set active plant", 500)
