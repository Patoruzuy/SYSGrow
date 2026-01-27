"""
Blueprint Common Utilities
==========================

Shared helper functions for all API blueprints.
Import these instead of duplicating helper code in each blueprint.

Usage:
    from app.blueprints.api._common import (
        get_container, get_json, success, fail,
        get_growth_service, get_analytics_service, ...
    )

This module centralizes:
- Service container access
- Request JSON parsing
- Standardized response helpers
- Common service accessors
- Datetime parsing utilities
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from flask import current_app, request, session
from app.utils.http import success_response, error_response
from app.utils.time import coerce_datetime as _coerce_datetime_util

logger = logging.getLogger("api._common")

# ============================================================================
# User Session Utilities
# ============================================================================


def get_user_id() -> int:
    """Get current user ID from session."""
    return session.get("user_id", 1)

def get_user_role() -> str:
    """Get current user role from session."""
    return session.get("user_role", "user")

# ============================================================================
# UNIT UTILITIES
# ============================================================================

def get_selected_unit_id() -> Optional[int]:
    """Get current unit ID from session, if set."""
    return session.get("selected_unit")

# ============================================================================
# CONTAINER ACCESS
# ============================================================================

def get_container():
    """
    Get the service container from Flask app config.
    
    Returns:
        ServiceContainer: The application service container
        
    Raises:
        RuntimeError: If container is not configured
    """
    container = current_app.config.get("CONTAINER")
    if not container:
        raise RuntimeError("ServiceContainer not found in app config")
    return container


# ============================================================================
# REQUEST HELPERS
# ============================================================================

def get_json() -> dict:
    """
    Get JSON request body with silent failure.
    
    Returns:
        dict: Parsed JSON body or empty dict if not available
    """
    return request.get_json(silent=True) or {}


# ============================================================================
# RESPONSE HELPERS
# ============================================================================

def success(data: dict | list | None = None, status: int = 200, *, message: str | None = None):
    """
    Standard success response wrapper.
    
    Args:
        data: Response data (dict or list)
        status: HTTP status code (default 200)
        message: Optional success message
        
    Returns:
        Flask Response with format: {"ok": true, "data": ..., "error": null}
    """
    return success_response(data, status, message=message)


def fail(message: str, status: int = 400, *, details: dict | None = None):
    """
    Standard error response wrapper.
    
    Args:
        message: Error message
        status: HTTP status code (default 400)
        details: Optional error details dict
        
    Returns:
        Flask Response with format: {"ok": false, "data": null, "error": {...}}
    """
    return error_response(message, status, details=details)


# ============================================================================
# DATETIME UTILITIES
# ============================================================================

def parse_datetime(param: Optional[str], default: datetime) -> datetime:
    """
    Parse ISO datetime string or return default.
    
    Args:
        param: ISO 8601 datetime string (optional)
        default: Default datetime if param is None
        
    Returns:
        Parsed datetime in UTC
        
    Raises:
        ValueError: If param is invalid format
    """
    if not param:
        return ensure_utc(default)
    try:
        raw = param.strip()
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"Invalid datetime format: {param}. Expected ISO 8601.")
    return ensure_utc(parsed)


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure datetime is in UTC timezone.
    
    Args:
        dt: Datetime to convert
        
    Returns:
        Datetime with UTC timezone
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def coerce_datetime(value: Any) -> Optional[datetime]:
    """
    Coerce value to datetime, returning None on failure.
    
    Args:
        value: String or datetime to coerce
        
    Returns:
        Datetime in UTC or None if invalid
    """
    return _coerce_datetime_util(value)


# ============================================================================
# SERVICE ACCESSORS
# ============================================================================

def get_analytics_service():
    """
    Get analytics service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "analytics_service", None):
        raise RuntimeError("Analytics service not available")
    return container.analytics_service


def get_growth_service():
    """
    Get growth service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "growth_service", None):
        raise RuntimeError("Growth service not available")
    return container.growth_service


def get_sensor_service():
    """
    Get sensor management service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "sensor_management_service", None):
        raise RuntimeError("Sensor management service not available")
    return container.sensor_management_service


def get_scheduling_service():
    """
    Get scheduling service from container.
    
    Accesses the SchedulingService via the actuator manager.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    actuator_service = getattr(container, "actuator_management_service", None)
    if not actuator_service:
        raise RuntimeError("Actuator management service not available")
    # ActuatorManagementService now contains scheduling_service directly
    scheduling_service = getattr(actuator_service, "scheduling_service", None)
    if not scheduling_service:
        raise RuntimeError("Scheduling service not available")
    return scheduling_service


def get_database():
    """
    Get database handler from container.
    
    Raises:
        RuntimeError: If database not available
    """
    container = get_container()
    if not getattr(container, "database", None):
        raise RuntimeError("Database not available")
    return container.database


def get_actuator_service():
    """
    Get actuator management service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "actuator_management_service", None):
        raise RuntimeError("Actuator management service not available")
    return container.actuator_management_service


def get_plant_service():
    """
    Get plant service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "plant_service", None):
        raise RuntimeError("Plant service not available")
    return container.plant_service


def get_harvest_service():
    """
    Get harvest service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "harvest_service", None):
        raise RuntimeError("Harvest service not available")
    return container.harvest_service


def get_system_health_service():
    """
    Get system health service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "system_health_service", None):
        raise RuntimeError("System health service not available")
    return container.system_health_service


def get_device_health_service():
    """
    Get device health service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "device_health_service", None):
        raise RuntimeError("Device health service not available")
    return container.device_health_service


def get_climate_service():
    """
    Get climate control service from container.
    Returns the climate controller from growth service.
    
    Raises:
        RuntimeError: If service not available
    """
    growth = get_growth_service()
    return growth


def get_notifications_service():
    """
    Get notifications service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "notifications_service", None):
        raise RuntimeError("Notifications service not available")
    return container.notifications_service

def get_irrigation_service():
    """
    Get irrigation workflow service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "irrigation_workflow_service", None):
        raise RuntimeError("Irrigation workflow service not available")
    return container.irrigation_workflow_service


def get_manual_irrigation_service():
    """
    Get manual irrigation service from container.

    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "manual_irrigation_service", None):
        raise RuntimeError("Manual irrigation service not available")
    return container.manual_irrigation_service


def get_plant_irrigation_model_service():
    """
    Get plant irrigation model service from container.

    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "plant_irrigation_model_service", None):
        raise RuntimeError("Plant irrigation model service not available")
    return container.plant_irrigation_model_service


def get_threshold_service():
    """
    Get threshold service from container.
    Single source of truth for all threshold operations.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "threshold_service", None):
        raise RuntimeError("Threshold service not available")
    return container.threshold_service


def get_ml_service():
    """
    Get ML models service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "ml_models_service", None):
        raise RuntimeError("ML models service not available")
    return container.ml_models_service


def get_device_repo():
    """
    Get device repository from container.
    
    Raises:
        RuntimeError: If repository not available
    """
    container = get_container()
    if not getattr(container, "device_repo", None):
        raise RuntimeError("Device repository not available")
    return container.device_repo

def get_analytics_repo():
    """
    Get analytics repository from container.
    
    Raises:
        RuntimeError: If repository not available
    """
    container = get_container()
    if not getattr(container, "analytics_repo", None):
        raise RuntimeError("Analytics repository not available")
    return container.analytics_repo

def get_unit_repo():
    """
    Get unit repository from container.
    
    Raises:
        RuntimeError: If repository not available
    """
    container = get_container()
    if not getattr(container, "unit_repo", None):
        raise RuntimeError("Unit repository not available")
    return container.unit_repo


def get_zigbee_service():
    """
    Get Zigbee service from container.
    May return None if MQTT/Zigbee is disabled.
    """
    container = get_container()
    return getattr(container, "zigbee_service", None)


def get_device_coordinator():
    """
    Get device coordinator from container.
    
    Raises:
        RuntimeError: If coordinator not available
    """
    container = get_container()
    if not getattr(container, "device_coordinator", None):
        raise RuntimeError("Device coordinator not available")
    return container.device_coordinator


def get_plant_journal_service():
    """
    Get plant journal service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "plant_journal_service", None):
        raise RuntimeError("Plant journal service not available")
    return container.plant_journal_service


def get_camera_service():
    """
    Get camera service from container.
    May return None if camera service is not configured.
    """
    container = get_container()
    return getattr(container, "camera_service", None)


def get_settings_service():
    """
    Get settings service from container.
    
    Raises:
        RuntimeError: If service not available
    """
    container = get_container()
    if not getattr(container, "settings_service", None):
        raise RuntimeError("Settings service not available")
    return container.settings_service


def get_pump_calibration_service():
    """
    Get pump calibration service from container via irrigation workflow service.
    
    Raises:
        RuntimeError: If service not available
    """
    irrigation_service = get_irrigation_service()
    pump_cal = getattr(irrigation_service, "_pump_calibration", None)
    if not pump_cal:
        raise RuntimeError("Pump calibration service not available")
    return pump_cal
