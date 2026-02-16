"""
Plant-Sensor Linking
=====================

Endpoints for linking plants to sensors and managing plant sensor associations.
Includes VPD (Vapor Pressure Deficit) monitoring for plant health optimization.
"""

from __future__ import annotations

import logging

from flask import current_app, request

from app.blueprints.api._common import (
    fail as _fail,
    get_growth_service as _growth_service,
    get_plant_service as _plant_service,
    success as _success,
)
from app.utils.psychrometrics import calculate_vpd_kpa
from app.utils.time import iso_now

from . import plants_api

logger = logging.getLogger("plants_api.sensors")


# ============================================================================
# PLANT-SENSOR LINKING
# ============================================================================


@plants_api.get("/units/<int:unit_id>/sensors/available")
def get_available_sensors(unit_id: int):
    """Get all available sensors that can be linked to plants"""
    logger.info(f"Getting available sensors for growth unit {unit_id}")
    try:
        # Verify unit exists
        if not _growth_service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)

        # Optional sensor_type filter (default: SOIL_MOISTURE)
        sensor_type = request.args.get("sensor_type", "SOIL_MOISTURE")

        plant_service = _plant_service()

        # Get available sensors with friendly names
        sensors = plant_service.get_available_sensors_for_plant(unit_id, sensor_type)

        return _success(
            {
                "unit_id": unit_id,
                "sensor_type": sensor_type,
                "sensors": sensors,
                "count": len(sensors),
                "timestamp": iso_now(),
            }
        )

    except Exception as e:
        logger.exception(f"Error getting available sensors for unit {unit_id}: {e}")
        return _fail("Failed to get available sensors", 500)


@plants_api.post("/plants/<int:plant_id>/sensors/<int:sensor_id>")
def link_plant_to_sensor(plant_id: int, sensor_id: int):
    """Link a plant to a sensor"""
    logger.info(f"Linking plant {plant_id} to sensor {sensor_id}")
    try:
        plant_service = _plant_service()

        # Verify plant exists
        plant = plant_service.get_plant(plant_id)
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)

        # Link sensor to plant
        success = plant_service.link_plant_sensor(plant_id, sensor_id)

        if success:
            return _success(
                {
                    "plant_id": plant_id,
                    "sensor_id": sensor_id,
                    "message": f"Sensor {sensor_id} linked to plant '{plant.get('plant_name')}' successfully",
                }
            )
        else:
            return _fail(f"Failed to link sensor {sensor_id} to plant {plant_id}", 400)

    except ValueError as e:
        logger.warning(f"Validation error linking sensor: {e}")
        return safe_error(e, 400)
    except Exception as e:
        logger.exception(f"Error linking plant {plant_id} to sensor {sensor_id}: {e}")
        return _fail("Failed to link plant to sensor", 500)


@plants_api.delete("/plants/<int:plant_id>/sensors/<int:sensor_id>")
def unlink_plant_from_sensor(plant_id: int, sensor_id: int):
    """Unlink a plant from a sensor"""
    logger.info(f"Unlinking plant {plant_id} from sensor {sensor_id}")
    try:
        plant_service = _plant_service()

        # Verify plant exists
        plant = plant_service.get_plant(plant_id)
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)

        # Unlink sensor from plant
        success = plant_service.unlink_plant_sensor(plant_id, sensor_id)

        if success:
            return _success(
                {
                    "plant_id": plant_id,
                    "sensor_id": sensor_id,
                    "message": f"Sensor {sensor_id} unlinked from plant successfully",
                }
            )
        else:
            return _fail(f"Failed to unlink sensor {sensor_id} from plant {plant_id}", 400)

    except Exception as e:
        logger.exception(f"Error unlinking plant {plant_id} from sensor {sensor_id}: {e}")
        return _fail("Failed to unlink plant from sensor", 500)


@plants_api.get("/plants/<int:plant_id>/sensors")
def get_plant_sensors(plant_id: int):
    """Get all sensors linked to a plant with full details"""
    logger.info(f"Getting sensors for plant {plant_id}")
    try:
        plant_service = _plant_service()

        # Verify plant exists
        plant = plant_service.get_plant(plant_id)
        plant = plant.to_dict() if plant else None
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)

        # Get full sensor details
        sensors = plant_service.get_plant_sensors(plant_id)

        return _success(
            {
                "plant_id": plant_id,
                "plant_name": plant.get("plant_name"),
                "sensors": sensors,
                "sensor_count": len(sensors),
                "timestamp": iso_now(),
            }
        )

    except Exception as e:
        logger.exception(f"Error getting sensors for plant {plant_id}: {e}")
        return _fail("Failed to get plant sensors", 500)


# ============================================================================
# VPD (VAPOR PRESSURE DEFICIT) MONITORING
# ============================================================================

# Optimal VPD ranges by growth stage (in kPa)
VPD_RANGES = {
    "seedling": {"min": 0.4, "max": 0.8, "target": 0.6},
    "clone": {"min": 0.4, "max": 0.8, "target": 0.6},
    "vegetative": {"min": 0.8, "max": 1.2, "target": 1.0},
    "flowering": {"min": 1.0, "max": 1.5, "target": 1.2},
    "fruiting": {"min": 1.0, "max": 1.5, "target": 1.2},
    "ripening": {"min": 1.0, "max": 1.5, "target": 1.2},
    "default": {"min": 0.8, "max": 1.2, "target": 1.0},
}


@plants_api.get("/units/<int:unit_id>/vpd")
def get_vpd_status(unit_id: int):
    """
    Get current VPD status and recommendations for a growth unit.

    VPD (Vapor Pressure Deficit) is a critical metric for plant health that
    indicates the difference between moisture in the air and how much moisture
    the air can hold when saturated.

    Returns:
        - Current VPD value in kPa
        - Status (optimal, low, high)
        - Optimal range based on plant growth stage
        - Suggested actions for optimization
        - Current temperature and humidity readings

    Query params:
        - plant_id: Optional specific plant to check (uses its growth stage)
    """
    logger.info(f"Getting VPD status for growth unit {unit_id}")
    try:
        # Verify unit exists
        growth_service = _growth_service()
        unit = growth_service.get_unit(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        # Get latest sensor readings
        container = current_app.config.get("CONTAINER")
        analytics_service = getattr(container, "analytics_service", None)

        if not analytics_service:
            return _fail("Analytics service not available", 503)

        latest = analytics_service.get_latest_sensor_reading(unit_id=unit_id)

        if not latest:
            return _fail("No sensor data available for this unit", 404)

        temperature = latest.get("temperature")
        humidity = latest.get("humidity")

        if temperature is None or humidity is None:
            return _fail(
                "Temperature or humidity data not available. Ensure temperature and humidity sensors are configured.",
                404,
            )

        # Calculate VPD
        vpd = calculate_vpd_kpa(temperature, humidity)

        if vpd is None:
            return _fail("Unable to calculate VPD from current readings", 500)

        vpd = round(vpd, 3)

        # Determine growth stage from plants in unit
        plant_service = _plant_service()
        plant_id = request.args.get("plant_id", type=int)

        growth_stage = "default"
        plant_name = None

        if plant_id:
            plant = plant_service.get_plant(plant_id)
            if plant:
                plant_dict = plant.to_dict() if hasattr(plant, "to_dict") else plant
                growth_stage = plant_dict.get("current_stage", "vegetative")
                plant_name = plant_dict.get("plant_name")
        else:
            # Get primary plant in unit
            plants = plant_service.list_plants(unit_id)
            if plants:
                first_plant = plants[0]
                plant_dict = first_plant.to_dict() if hasattr(first_plant, "to_dict") else first_plant
                growth_stage = plant_dict.get("current_stage", "vegetative")
                plant_name = plant_dict.get("plant_name")

        # Normalize stage name
        growth_stage = growth_stage.lower() if growth_stage else "default"
        if growth_stage not in VPD_RANGES:
            growth_stage = "default"

        # Get optimal range for this stage
        optimal = VPD_RANGES[growth_stage]
        min_vpd = optimal["min"]
        max_vpd = optimal["max"]
        target_vpd = optimal["target"]

        # Determine status and actions
        status = "optimal"
        suggested_actions = []

        if vpd < min_vpd:
            status = "low"
            deficit = min_vpd - vpd
            suggested_actions = [
                f"Increase temperature by {round(deficit * 5, 1)}°C",
                f"Decrease humidity by {round(deficit * 15, 1)}%",
                "Improve air circulation with fans",
                "Check for excess moisture sources",
            ]
        elif vpd > max_vpd:
            status = "high"
            excess = vpd - max_vpd
            suggested_actions = [
                f"Decrease temperature by {round(excess * 5, 1)}°C",
                f"Increase humidity by {round(excess * 15, 1)}%",
                "Add humidifier or misting system",
                "Reduce ventilation temporarily",
            ]
        else:
            suggested_actions = ["VPD is within optimal range", "Continue current environmental settings"]

        # Calculate how far from optimal
        deviation_percent = round(abs(vpd - target_vpd) / target_vpd * 100, 1)

        return _success(
            {
                "unit_id": unit_id,
                "vpd_kpa": vpd,
                "status": status,
                "optimal_range": {"min": min_vpd, "max": max_vpd, "target": target_vpd},
                "growth_stage": growth_stage,
                "plant_name": plant_name,
                "current_conditions": {"temperature_c": round(temperature, 1), "humidity_percent": round(humidity, 1)},
                "deviation_percent": deviation_percent,
                "suggested_actions": suggested_actions,
                "vpd_explanation": {
                    "low_vpd": "Low VPD reduces transpiration, can lead to mold/mildew and nutrient uptake issues",
                    "high_vpd": "High VPD causes excessive transpiration, leading to stress, wilting, and nutrient lockout",
                    "optimal_vpd": "Optimal VPD promotes healthy transpiration and nutrient uptake",
                },
                "timestamp": iso_now(),
            }
        )

    except Exception as e:
        logger.exception(f"Error getting VPD status for unit {unit_id}: {e}")
        return _fail("Failed to calculate VPD status", 500)
