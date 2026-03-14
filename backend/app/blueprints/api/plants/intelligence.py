"""
Plant Intelligence Endpoints
============================

Routes:
- GET /watering-decision
- GET /environmental-alerts
- POST /problem-diagnosis
- GET /yield-projection
- GET /harvest-recommendations
- GET /lighting-schedule
- GET /automation-status
- GET /available-plants
"""

from __future__ import annotations

import logging
from datetime import datetime

from flask import request

from app.utils.time import iso_now

from . import plants_api
from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
)

try:
    from integrations.smart_agriculture import SmartAgricultureManager
except ImportError:
    SmartAgricultureManager = None

logger = logging.getLogger(__name__)

# Lazy-init manager to avoid side effects at import time
_agriculture_manager = None
_manager_init_error: str | None = None


def _get_agriculture_manager():
    """Create the agriculture manager on first use to keep imports side-effect free."""
    global _agriculture_manager, _manager_init_error

    if _agriculture_manager is not None:
        return _agriculture_manager

    if _manager_init_error:
        return None

    if SmartAgricultureManager is None:
        _manager_init_error = "Smart agriculture features not available"
        return None

    try:
        _agriculture_manager = SmartAgricultureManager()
    except Exception as exc:
        logger.error("Failed to initialize SmartAgricultureManager: %s", exc)
        _manager_init_error = str(exc)
        return None

    return _agriculture_manager


def handle_api_error(error_msg: str, status_code: int = 400, *, details: dict | None = None):
    """Standard error response handler"""
    return _fail(error_msg, status_code, details=details)


def validate_plant_id(plant_id_str: str):
    """Validate and convert plant ID parameter"""
    try:
        plant_id = int(plant_id_str)
        if plant_id < 1:
            raise ValueError("Plant ID must be positive")
        return plant_id
    except (ValueError, TypeError):
        raise ValueError("Invalid plant_id parameter")


@plants_api.get("/watering-decision")
def get_watering_decision():
    """
    Get watering decision for a plant based on current conditions.

    Query Parameters:
        plant_id (int): Plant ID from plants_info.json
        moisture (float): Current soil moisture percentage (0-100)
        last_watered (optional): ISO timestamp of last watering
    """
    agriculture_manager = _get_agriculture_manager()
    if not agriculture_manager:
        return handle_api_error("Smart agriculture features not available", 503)

    try:
        plant_id = validate_plant_id(request.args.get("plant_id"))
        moisture = float(request.args.get("moisture", 0))

        if not 0 <= moisture <= 100:
            return handle_api_error("Moisture must be between 0-100")

        last_watered = None
        last_watered_str = request.args.get("last_watered")
        if last_watered_str:
            try:
                last_watered = datetime.fromisoformat(last_watered_str.replace("Z", "+00:00"))
            except ValueError:
                return handle_api_error("Invalid last_watered timestamp format")

        result = agriculture_manager.get_watering_decision(plant_id=plant_id, moisture=moisture, last_watered=last_watered)

        return _success({"decision": result, "timestamp": iso_now()})

    except ValueError as e:
        return handle_api_error(str(e))
    except Exception as e:
        logger.error("Error in watering decision: %s", e, exc_info=True)
        return handle_api_error("Internal server error", 500)


@plants_api.get("/environmental-alerts")
def get_environmental_alerts():
    """
    Get environmental alerts for a plant based on current conditions.

    Query Parameters:
        plant_id (int): Plant ID from plants_info.json
        temperature (float): Current temperature in °C
        humidity (float): Current humidity percentage (0-100)
        soil_moisture (optional): Current soil moisture percentage
    """
    agriculture_manager = _get_agriculture_manager()
    if not agriculture_manager:
        return handle_api_error("Smart agriculture features not available", 503)

    try:
        plant_id = validate_plant_id(request.args.get("plant_id"))
        temperature = request.args.get("temperature")
        humidity = request.args.get("humidity")

        if temperature is None or humidity is None:
            return handle_api_error("temperature and humidity are required parameters")

        soil_moisture = request.args.get("soil_moisture")

        alerts = agriculture_manager.get_environmental_alerts(
            plant_id=plant_id,
            temperature=float(temperature),
            humidity=float(humidity),
            soil_moisture=float(soil_moisture) if soil_moisture is not None else None,
        )

        return _success({"alerts": alerts, "timestamp": iso_now()})

    except ValueError as e:
        return handle_api_error(str(e))
    except Exception as e:
        logger.error("Error in environmental alerts: %s", e, exc_info=True)
        return handle_api_error("Internal server error", 500)


@plants_api.post("/problem-diagnosis")
def get_problem_diagnosis():
    """
    Diagnose plant problems based on symptoms.

    Request Body:
        {
            "plant_id": int,
            "symptoms": ["symptom1", "symptom2", ...]
        }
    """
    agriculture_manager = _get_agriculture_manager()
    if not agriculture_manager:
        return handle_api_error("Smart agriculture features not available", 503)

    try:
        data = request.get_json() or {}

        plant_id = data.get("plant_id")
        symptoms = data.get("symptoms", [])

        if plant_id is None:
            return handle_api_error("plant_id is required")

        if not symptoms:
            return handle_api_error("symptoms list is required")

        if not isinstance(symptoms, list):
            return handle_api_error("symptoms must be a list")

        plant_id = validate_plant_id(str(plant_id))

        diagnosis = agriculture_manager.get_problem_diagnosis(plant_id=plant_id, symptoms=symptoms)

        return _success({"diagnosis": diagnosis, "timestamp": iso_now()})

    except ValueError as e:
        return handle_api_error(str(e))
    except Exception as e:
        logger.error("Error in problem diagnosis: %s", e, exc_info=True)
        return handle_api_error("Internal server error", 500)


@plants_api.get("/yield-projection")
def get_yield_projection():
    """
    Get yield projection for a plant type.

    Query Parameters:
        plant_id (int): Plant ID from plants_info.json
        plants_count (int): Number of plants
        growth_quality (optional): "poor", "average", "good" (default: "average")
    """
    agriculture_manager = _get_agriculture_manager()
    if not agriculture_manager:
        return handle_api_error("Smart agriculture features not available", 503)

    try:
        plant_id = validate_plant_id(request.args.get("plant_id"))
        plants_count = request.args.get("plants_count")

        if plants_count is None:
            return handle_api_error("plants_count is required parameter")

        growth_quality = request.args.get("growth_quality", "average")

        projection = agriculture_manager.get_yield_projection(
            plant_id=plant_id,
            plants_count=int(plants_count),
            growth_quality=growth_quality,
        )

        return _success({"projection": projection, "timestamp": iso_now()})

    except ValueError as e:
        return handle_api_error(str(e))
    except Exception as e:
        logger.error("Error in yield projection: %s", e, exc_info=True)
        return handle_api_error("Internal server error", 500)


@plants_api.get("/harvest-recommendations")
def get_harvest_recommendations():
    """
    Get harvest recommendations for a plant.

    Query Parameters:
        plant_id (int): Plant ID from plants_info.json
        days_since_planting (int): Days since planting
    """
    agriculture_manager = _get_agriculture_manager()
    if not agriculture_manager:
        return handle_api_error("Smart agriculture features not available", 503)

    try:
        plant_id = validate_plant_id(request.args.get("plant_id"))
        days_since_planting = request.args.get("days_since_planting")

        if days_since_planting is None:
            return handle_api_error("days_since_planting is required parameter")

        recommendations = agriculture_manager.get_harvest_recommendations(
            plant_id=plant_id,
            days_since_planting=int(days_since_planting),
        )

        return _success({"recommendations": recommendations, "timestamp": iso_now()})

    except ValueError as e:
        return handle_api_error(str(e))
    except Exception as e:
        logger.error("Error in harvest recommendations: %s", e, exc_info=True)
        return handle_api_error("Internal server error", 500)


@plants_api.get("/lighting-schedule")
def get_lighting_schedule():
    """
    Get recommended lighting schedule for a plant growth stage.

    Query Parameters:
        plant_id (int): Plant ID from plants_info.json
        growth_stage (str): Growth stage (e.g., "seedling", "vegetative", "flowering")
    """
    agriculture_manager = _get_agriculture_manager()
    if not agriculture_manager:
        return handle_api_error("Smart agriculture features not available", 503)

    try:
        plant_id = validate_plant_id(request.args.get("plant_id"))
        growth_stage = request.args.get("growth_stage")

        if growth_stage is None:
            return handle_api_error("growth_stage is required parameter")

        schedule = agriculture_manager.get_lighting_schedule(plant_id=plant_id, growth_stage=growth_stage)

        return _success({"lighting_schedule": schedule, "timestamp": iso_now()})

    except ValueError as e:
        return handle_api_error(str(e))
    except Exception as e:
        logger.error("Error in lighting schedule: %s", e, exc_info=True)
        return handle_api_error("Internal server error", 500)


@plants_api.get("/automation-status")
def get_automation_status():
    """
    Get automation status for a plant.

    Query Parameters:
        plant_id (int): Plant ID from plants_info.json
        moisture (float, optional): Current soil moisture percentage
        temperature (float, optional): Current temperature in °C
        humidity (float, optional): Current humidity percentage
        growth_stage (str, optional): Current growth stage
        days_since_planting (int, optional): Days since planting
    """
    agriculture_manager = _get_agriculture_manager()
    if not agriculture_manager:
        return handle_api_error("Smart agriculture features not available", 503)

    try:
        plant_id = validate_plant_id(request.args.get("plant_id"))

        moisture = request.args.get("moisture")
        temperature = request.args.get("temperature")
        humidity = request.args.get("humidity")
        growth_stage = request.args.get("growth_stage")
        days_since_planting = request.args.get("days_since_planting")

        status = {}

        if moisture is not None:
            watering = agriculture_manager.get_watering_decision(
                plant_id=plant_id,
                moisture=float(moisture),
            )
            status["watering"] = watering

        if temperature is not None and humidity is not None:
            alerts = agriculture_manager.get_environmental_alerts(
                plant_id=plant_id,
                temperature=float(temperature),
                humidity=float(humidity),
            )
            status["environmental_alerts"] = alerts

        if growth_stage is not None:
            lighting = agriculture_manager.get_lighting_schedule(plant_id=plant_id, growth_stage=growth_stage)
            status["lighting"] = lighting

        if days_since_planting is not None:
            harvest = agriculture_manager.get_harvest_recommendations(
                plant_id=plant_id,
                days_since_planting=int(days_since_planting),
            )
            status["harvest"] = harvest

        return _success({"status": status, "timestamp": iso_now()})

    except ValueError as e:
        return handle_api_error(str(e))
    except Exception as e:
        logger.error("Error in automation status: %s", e, exc_info=True)
        return handle_api_error("Internal server error", 500)


@plants_api.get("/available-plants")
def get_available_plants():
    """Get list of all available plants with basic info."""
    agriculture_manager = _get_agriculture_manager()
    if not agriculture_manager:
        return handle_api_error("Smart agriculture features not available", 503)

    try:
        plants = agriculture_manager.plants_data.get("plants_info", [])

        plants_info = []
        for plant in plants:
            plants_info.append(
                {
                    "id": plant["id"],
                    "common_name": plant["common_name"],
                    "species": plant["species"],
                    "variety": plant.get("variety", ""),
                    "difficulty_level": plant.get("yield_data", {}).get("difficulty_level", "unknown"),
                    "harvest_frequency": plant.get("yield_data", {}).get("harvest_frequency", "unknown"),
                    "expected_yield_range": plant.get("yield_data", {}).get("expected_yield_per_plant", {}),
                    "market_value_per_kg": plant.get("yield_data", {}).get("market_value_per_kg", 0),
                }
            )

        return _success({"plants": plants_info, "plant_count": len(plants_info), "timestamp": iso_now()})

    except Exception as e:
        logger.error("Error getting available plants: %s", e, exc_info=True)
        return handle_api_error("Internal server error", 500)

