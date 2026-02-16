"""
Sensor Data Throttling Settings API
===================================

Endpoints for managing sensor data persistence throttling configuration.
Allows users to customize how aggressively sensor readings are stored to balance
database efficiency with data quality requirements.

Author: Sebastian Gomez
Date: December 2025
"""

import logging

from flask import request

from app.blueprints.api._common import (
    fail as error_response,
    get_container,
    success as success_response,
)
from app.blueprints.api.settings import settings_api

logger = logging.getLogger(__name__)


@settings_api.get("/throttle")
def get_throttle_config():
    """
    Get current sensor data throttling configuration.

    Returns:
        JSON response with throttle configuration including:
        - Time intervals for each sensor type
        - Change thresholds for each sensor type
        - Strategy (time-only or hybrid)
        - Feature flags (throttling_enabled, debug_logging)

    Example Response:
        {
            "success": true,
            "data": {
                "time_intervals": {
                    "temp_humidity_minutes": 30,
                    "co2_voc_minutes": 30,
                    "soil_moisture_minutes": 60
                },
                "change_thresholds": {
                    "temp_celsius": 1.0,
                    "humidity_percent": 5.0,
                    "soil_moisture_percent": 10.0,
                    "co2_ppm": 100.0,
                    "voc_ppb": 50.0
                },
                "strategy": "hybrid",
                "throttling_enabled": true,
                "debug_logging": false
            }
        }
    """
    try:
        container = get_container()
        if not container:
            return error_response("Service container not available", 500)

        unit_id = request.args.get("unit_id", type=int)
        if unit_id is None:
            return error_response("unit_id query parameter is required", 400)

        growth_service = getattr(container, "growth_service", None)
        if not growth_service:
            return error_response("Growth service not available", 503)

        climate_controller = growth_service.get_climate_controller(unit_id)
        if not climate_controller:
            return error_response("Climate controller not available for unit", 404)

        config = climate_controller.get_throttle_config()
        return success_response(config)

    except Exception as e:
        logger.exception("Error getting throttle configuration")
        return error_response(f"Failed to get throttle configuration: {e!s}", 500)


@settings_api.put("/throttle")
def update_throttle_config():
    """
    Update sensor data throttling configuration.

    Supports partial updates - only provided fields will be updated.

    Request Body (all fields optional):
        {
            "time_intervals": {
                "temp_humidity_minutes": 30,
                "co2_voc_minutes": 30,
                "soil_moisture_minutes": 60
            },
            "change_thresholds": {
                "temp_celsius": 1.0,
                "humidity_percent": 5.0,
                "soil_moisture_percent": 10.0,
                "co2_ppm": 100.0,
                "voc_ppb": 50.0
            },
            "strategy": "hybrid",  // or "time_only"
            "throttling_enabled": true,
            "debug_logging": false
        }

    Returns:
        JSON response with updated configuration

    Examples:
        # Change only time intervals
        PUT /api/settings/throttle
        {"time_intervals": {"temp_humidity_minutes": 15}}

        # Change strategy to time-only
        PUT /api/settings/throttle
        {"strategy": "time_only"}

        # Disable throttling (store all readings)
        PUT /api/settings/throttle
        {"throttling_enabled": false}
    """
    try:
        container = get_container()
        if not container:
            return error_response("Service container not available", 500)

        unit_id = request.args.get("unit_id", type=int)
        if unit_id is None:
            return error_response("unit_id query parameter is required", 400)

        growth_service = getattr(container, "growth_service", None)
        if not growth_service:
            return error_response("Growth service not available", 503)

        climate_controller = growth_service.get_climate_controller(unit_id)
        if not climate_controller:
            return error_response("Climate controller not available for unit", 404)

        data = request.get_json()
        if not data:
            return error_response("Request body is required", 400)

        # Validate time intervals
        time_intervals = data.get("time_intervals", {})
        for key, value in time_intervals.items():
            if not isinstance(value, (int, float)) or value < 0:
                return error_response(f"Invalid time interval value for {key}: must be positive number", 400)

        # Validate change thresholds
        change_thresholds = data.get("change_thresholds", {})
        for key, value in change_thresholds.items():
            if not isinstance(value, (int, float)) or value < 0:
                return error_response(f"Invalid change threshold value for {key}: must be positive number", 400)

        # Validate strategy
        strategy = data.get("strategy")
        if strategy and strategy not in ["hybrid", "time_only"]:
            return error_response("Invalid strategy: must be 'hybrid' or 'time_only'", 400)

        # Update configuration
        climate_controller.update_throttle_config(data)

        # Return updated config
        updated_config = climate_controller.get_throttle_config()
        return success_response(updated_config, message="Throttle configuration updated successfully")

    except ValueError as e:
        logger.warning(f"Invalid throttle configuration: {e}")
        return error_response(f"Invalid configuration: {e!s}", 400)
    except Exception as e:
        logger.exception("Error updating throttle configuration")
        return error_response(f"Failed to update throttle configuration: {e!s}", 500)


@settings_api.post("/throttle/reset")
def reset_throttle_config():
    """
    Reset sensor data throttling configuration to defaults.

    Returns:
        JSON response with default configuration

    Default Configuration:
        - Time intervals: 30 min (temp/humidity/CO2/VOC), 60 min (soil moisture)
        - Change thresholds: 1°C (temp), 5% (humidity), 10% (soil), 100ppm (CO2), 50ppb (VOC)
        - Strategy: Hybrid (time OR change)
        - Throttling: Enabled
        - Debug logging: Disabled
    """
    try:
        container = get_container()
        if not container:
            return error_response("Service container not available", 500)

        unit_id = request.args.get("unit_id", type=int)
        if unit_id is None:
            return error_response("unit_id query parameter is required", 400)

        growth_service = getattr(container, "growth_service", None)
        if not growth_service:
            return error_response("Growth service not available", 503)

        climate_controller = growth_service.get_climate_controller(unit_id)
        if not climate_controller:
            return error_response("Climate controller not available for unit", 404)

        from app.controllers import DEFAULT_THROTTLE_CONFIG

        # Reset to defaults
        climate_controller.update_throttle_config(DEFAULT_THROTTLE_CONFIG.to_dict())

        # Return updated config
        config = climate_controller.get_throttle_config()
        return success_response(config, message="Throttle configuration reset to defaults")

    except Exception as e:
        logger.exception("Error resetting throttle configuration")
        return error_response(f"Failed to reset throttle configuration: {e!s}", 500)
