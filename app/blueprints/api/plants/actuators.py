"""
Plant-Actuator Linking
======================

Endpoints for linking plants to actuators (e.g., dedicated irrigation pumps).
"""
from __future__ import annotations

import logging

from flask import request

from app.utils.time import iso_now
from . import plants_api
from app.blueprints.api._common import (
    fail as _fail,
    get_growth_service as _growth_service,
    get_plant_service as _plant_service,
    success as _success,
)

logger = logging.getLogger("plants_api.actuators")


# ============================================================================
# PLANT-ACTUATOR LINKING
# ============================================================================

@plants_api.get("/units/<int:unit_id>/actuators/available")
def get_available_actuators(unit_id: int):
    """Get all available actuators that can be linked to plants."""
    logger.info("Getting available actuators for growth unit %s", unit_id)
    try:
        if not _growth_service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)

        actuator_type = request.args.get("actuator_type", "pump")
        plant_service = _plant_service()

        actuators = plant_service.get_available_actuators_for_plant(unit_id, actuator_type)

        return _success(
            {
                "unit_id": unit_id,
                "actuator_type": actuator_type,
                "actuators": actuators,
                "count": len(actuators),
                "timestamp": iso_now(),
            }
        )
    except Exception as e:
        logger.exception("Error getting available actuators for unit %s: %s", unit_id, e)
        return _fail("Failed to get available actuators", 500)


@plants_api.post("/plants/<int:plant_id>/actuators/<int:actuator_id>")
def link_plant_to_actuator(plant_id: int, actuator_id: int):
    """Link a plant to an actuator."""
    logger.info("Linking plant %s to actuator %s", plant_id, actuator_id)
    try:
        plant_service = _plant_service()
        plant = plant_service.get_plant(plant_id)
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)

        success = plant_service.link_plant_actuator(plant_id, actuator_id)
        if success:
            return _success(
                {
                    "plant_id": plant_id,
                    "actuator_id": actuator_id,
                    "message": (
                        f"Actuator {actuator_id} linked to plant "
                        f"'{plant.get('plant_name')}' successfully"
                    ),
                }
            )
        return _fail(f"Failed to link actuator {actuator_id} to plant {plant_id}", 400)
    except ValueError as e:
        logger.warning("Validation error linking actuator: %s", e)
        return _fail(str(e), 400)
    except Exception as e:
        logger.exception("Error linking plant %s to actuator %s: %s", plant_id, actuator_id, e)
        return _fail("Failed to link plant to actuator", 500)


@plants_api.delete("/plants/<int:plant_id>/actuators/<int:actuator_id>")
def unlink_plant_from_actuator(plant_id: int, actuator_id: int):
    """Unlink a plant from an actuator."""
    logger.info("Unlinking plant %s from actuator %s", plant_id, actuator_id)
    try:
        plant_service = _plant_service()
        plant = plant_service.get_plant(plant_id)
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)

        success = plant_service.unlink_plant_actuator(plant_id, actuator_id)
        if success:
            return _success(
                {
                    "plant_id": plant_id,
                    "actuator_id": actuator_id,
                    "message": f"Actuator {actuator_id} unlinked from plant successfully",
                }
            )
        return _fail(f"Failed to unlink actuator {actuator_id} from plant {plant_id}", 400)
    except Exception as e:
        logger.exception("Error unlinking plant %s from actuator %s: %s", plant_id, actuator_id, e)
        return _fail("Failed to unlink plant from actuator", 500)


@plants_api.get("/plants/<int:plant_id>/actuators")
def get_plant_actuators(plant_id: int):
    """Get all actuators linked to a plant with full details."""
    logger.info("Getting actuators for plant %s", plant_id)
    try:
        plant_service = _plant_service()
        plant = plant_service.get_plant(plant_id)
        plant = plant.to_dict() if plant else None
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)

        actuators = plant_service.get_plant_actuators(plant_id)
        return _success(
            {
                "plant_id": plant_id,
                "plant_name": plant.get("plant_name"),
                "actuators": actuators,
                "actuator_count": len(actuators),
                "timestamp": iso_now(),
            }
        )
    except Exception as e:
        logger.exception("Error getting actuators for plant %s: %s", plant_id, e)
        return _fail("Failed to get plant actuators", 500)
