"""
Shared utilities for device management API
==========================================

Common helper functions, response builders, and service accessors
used across all device API modules.
"""
from __future__ import annotations

import logging
from typing import Any

from app.schemas.device import SensorResponse, ActuatorResponse

# Import shared utilities from centralized module
from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
    get_growth_service as _growth_service,
    get_device_health_service as _device_health_service,
    get_device_coordinator as _device_coordinator,
    get_analytics_service as _analytics_service,
    get_device_repo as _device_repo,
    get_zigbee_service as _zigbee_service,
    get_sensor_service as _sensor_service,
    get_actuator_service as _actuator_service,
)

logger = logging.getLogger("devices_api")


# =====================================
# RESPONSE MAPPERS
# =====================================

def _sensor_to_response(sensor: dict[str, Any]) -> SensorResponse:
    """Map database sensor dict to SensorResponse schema"""
    config = dict(sensor.get("config") or {})
    return SensorResponse(
        id=int(sensor.get("sensor_id") or sensor.get("id") or 0),
        name=str(sensor.get("name") or ""),
        type=str(sensor.get("sensor_type") or sensor.get("type") or ""),
        model=str(sensor.get("model") or ""),
        communication_type=str(sensor.get("protocol") or sensor.get("communication_type") or ""),
        gpio_pin=config.get("gpio_pin"),
        i2c_address=config.get("i2c_address"),
        unit_id=int(sensor.get("unit_id") or 0),
        esp32_id=config.get("esp32_device_id") or config.get("esp32_id"),
        power_mode=str(config.get("power_mode") or "normal"),
        min_threshold=config.get("min_threshold"),
        max_threshold=config.get("max_threshold"),
        primary_metrics=config.get("primary_metrics"),
        enabled=bool(sensor.get("is_active", sensor.get("enabled", True))),
        last_value=None,
        last_reading_time=None,
        created_at=sensor.get("created_at"),
        updated_at=sensor.get("updated_at"),
    )


def _actuator_to_response(actuator: dict[str, Any]) -> ActuatorResponse:
    """Map database actuator dict to ActuatorResponse schema"""
    config = dict(actuator.get("config") or {})
    return ActuatorResponse(
        id=int(actuator.get("actuator_id") or actuator.get("id") or 0),
        name=str(actuator.get("name") or actuator.get("device") or ""),
        type=str(actuator.get("actuator_type") or actuator.get("type") or ""),
        communication_type=str(actuator.get("protocol") or actuator.get("communication_type") or ""),
        gpio_pin=config.get("gpio_pin"),
        unit_id=int(actuator.get("unit_id") or 0),
        esp32_id=config.get("esp32_id") or config.get("device_id"),
        state=str(actuator.get("state") or "OFF"),
        power_mode=str(config.get("power_mode") or "normal"),
        enabled=bool(actuator.get("is_active", actuator.get("enabled", True))),
        last_state_change=actuator.get("last_state_change"),
        created_at=actuator.get("created_at"),
        updated_at=actuator.get("updated_at"),
    )


# =====================================
# CSV EXPORT HELPER
# =====================================

def _to_csv(rows: list[dict], headers: list[str]) -> str:
    """Convert rows to CSV format"""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(headers)
    
    # Write data rows
    for row in rows:
        writer.writerow([row.get(h, '') for h in headers])
    
    return output.getvalue()
