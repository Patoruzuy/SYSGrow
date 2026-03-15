"""
Sensor Management Endpoints
===========================

All sensor-related REST API endpoints including:
- CRUD operations (list, create, delete)
- Calibration management (system-level)
- Health monitoring and statistics
- Anomaly detection
- Discovery and reading
"""
from __future__ import annotations

import logging
from flask import request, current_app
from pydantic import ValidationError

from app.schemas.device import CreateSensorRequest, UpdateSensorRequest
from app.hardware.sensors.processors.utils import DASHBOARD_METRICS
from . import devices_api
from .utils import (
    _device_health_service,
    _device_repo,
    _sensor_service,  # Direct hardware service access
    _success,
    _fail,
    _sensor_to_response,
)

logger = logging.getLogger("devices_api")


def _normalize_primary_metrics(values: object) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError("primary_metrics must be a list")

    cleaned: list[str] = []
    for item in values:
        if item is None:
            continue
        metric = str(item).strip().lower()
        if not metric:
            continue
        if metric not in DASHBOARD_METRICS:
            raise ValueError(f"Unsupported primary metric '{metric}'")
        if metric not in cleaned:
            cleaned.append(metric)

    return cleaned


def _find_primary_metric_conflicts(
    *,
    unit_id: int,
    desired_metrics: list[str],
    exclude_sensor_id: int | None = None,
) -> list[dict[str, object]]:
    if not desired_metrics:
        return []

    device_repo = _device_repo()
    sensors = device_repo.list_sensor_configs(unit_id=unit_id)
    conflicts: dict[str, list[dict[str, object]]] = {}

    for sensor in sensors:
        sensor_id = int(sensor.get("sensor_id") or 0)
        if exclude_sensor_id and sensor_id == exclude_sensor_id:
            continue

        config = sensor.get("config") or {}
        primary_metrics = config.get("primary_metrics") or []
        if not isinstance(primary_metrics, list):
            continue

        for metric in desired_metrics:
            if metric not in primary_metrics:
                continue
            conflicts.setdefault(metric, []).append({
                "sensor_id": sensor_id,
                "name": sensor.get("name"),
                "type": sensor.get("sensor_type"),
            })

    return [
        {"metric": metric, "sensors": sensors}
        for metric, sensors in conflicts.items()
    ]


def _update_primary_metrics(
    *,
    sensor_id: int,
    unit_id: int,
    new_metrics: list[str],
) -> None:
    device_repo = _device_repo()
    sensor_svc = _sensor_service()

    sensor_config = device_repo.find_sensor_config_by_id(sensor_id)
    if not sensor_config:
        raise ValueError(f"Sensor {sensor_id} not found")
    if int(sensor_config.get("unit_id") or 0) != int(unit_id):
        raise ValueError(f"Sensor {sensor_id} does not belong to unit {unit_id}")

    config = dict(sensor_config.get("config") or {})
    if new_metrics:
        config["primary_metrics"] = list(new_metrics)
    else:
        config.pop("primary_metrics", None)

    if not device_repo.update_sensor_config(sensor_id=sensor_id, config_data=config):
        raise ValueError(f"Failed to update sensor {sensor_id} config")

    refreshed = dict(sensor_config)
    refreshed["config"] = config
    sensor_svc.register_sensor_config(refreshed)


# =====================================
# SENSOR CRUD OPERATIONS
# =====================================

@devices_api.get('/v2/sensors')
def get_all_sensors():
    """Endpoint returning SensorResponse objects for all sensors."""
    try:
        sensor_svc = _sensor_service()
        sensors = sensor_svc.list_sensors()
        typed = [_sensor_to_response(sensor) for sensor in sensors]
        return _success([s.model_dump() for s in typed])
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.get('/v2/sensors/unit/<int:unit_id>')
def get_unit_sensors(unit_id: int):
    """Endpoint returning sensors for a specific unit."""
    try:
        sensor_svc = _sensor_service()
        sensors = sensor_svc.list_sensors(unit_id=unit_id)
        typed = [_sensor_to_response(sensor) for sensor in sensors]
        return _success([s.model_dump() for s in typed])
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.post('/v2/sensors')
def add_sensor():
    """
    Typed sensor creation endpoint using CreateSensorRequest.
    Validates the payload with Pydantic and delegates to SensorManagementService.
    """
    try:
        raw = request.get_json() or {}
        try:
            body = CreateSensorRequest(**raw)
        except ValidationError as ve:
            logger.warning("Validation error creating sensor: %s raw=%s", ve.errors(), raw)
            return _fail("Invalid sensor payload", 400, details={"errors": ve.errors()})

        sensor_svc = _sensor_service()
        protocol_value = body.protocol.value
        protocol_lower = protocol_value.lower()

        # Store only adapter-relevant config keys. Extra keys in this dict are
        # passed directly into adapter constructors via SensorManager.
        config: dict = {}

        primary_metrics = _normalize_primary_metrics(body.primary_metrics)
        if primary_metrics:
            conflicts = _find_primary_metric_conflicts(
                unit_id=body.unit_id,
                desired_metrics=primary_metrics,
            )
            if conflicts:
                return _fail(
                    "Primary metrics already assigned",
                    409,
                    details={"conflicts": conflicts},
                )
            config["primary_metrics"] = list(primary_metrics)

        if protocol_lower in ("gpio", "i2c", "adc", "spi"):
            if body.gpio_pin is not None:
                config["gpio_pin"] = body.gpio_pin
            if body.i2c_address is not None:
                config["i2c_address"] = body.i2c_address

        elif protocol_lower == "mqtt":
            if not body.mqtt_topic:
                raise ValueError("mqtt_topic is required for MQTT sensors")
            config["mqtt_topic"] = body.mqtt_topic
            if body.esp32_id is not None:
                config["esp32_device_id"] = body.esp32_id

        elif protocol_lower == "zigbee":
            if body.esp32_id is None:
                raise ValueError("esp32_id is required for Zigbee sensors")
            if not body.zigbee_address:
                raise ValueError("zigbee_address is required for Zigbee sensors")
            config["esp32_device_id"] = body.esp32_id
            config["zigbee_ieee"] = body.zigbee_address
            config["sensor_type"] = body.type.value

        elif protocol_lower == "zigbee2mqtt":
            friendly_name = None
            if body.mqtt_topic:
                # Handle both fully qualified topics and short names
                if "/" in body.mqtt_topic:
                    parts = body.mqtt_topic.split("/", 1)
                    if len(parts) == 2 and parts[0] == "zigbee2mqtt":
                        friendly_name = parts[1]
                else:
                    friendly_name = body.mqtt_topic

            if not friendly_name:
                friendly_name = body.zigbee_address
            
            if not friendly_name:
                raise ValueError("mqtt_topic or zigbee_address is required for Zigbee2MQTT sensors")

            config["friendly_name"] = friendly_name
            config["mqtt_topic"] = f"zigbee2mqtt/{friendly_name}"
            
            from app.enums import SensorType
            # Capabilities are now determined by primary_metrics, not sensor type
            # Default capabilities based on category for Zigbee2MQTT auto-discovery
            if body.type == SensorType.ENVIRONMENTAL:
                capabilities = ["temperature", "humidity", "illuminance", "co2", "voc", "pressure"]
            elif body.type == SensorType.PLANT:
                capabilities = ["soil_moisture", "ph", "ec"]
            else:
                capabilities = []

            config["sensor_capabilities"] = capabilities
            config["timeout"] = 120

        sensor_id = sensor_svc.create_sensor(
            unit_id=body.unit_id,
            name=body.name,
            sensor_type=body.type.value,
            protocol=protocol_value,
            model=body.model.value,
            config=config,
            register_runtime=True,
        )

        return _success(
            {
                "sensor_id": sensor_id,
                "message": f"Sensor '{body.name}' created successfully",
            },
            201,
        )
    except ValueError as e:
        return _fail(str(e), 400)
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.delete('/v2/sensors/<int:sensor_id>')
def remove_sensor(sensor_id: int):
    """
    Remove a sensor.
    
    Query params:
        remove_from_zigbee: If true, also remove from Zigbee network (default: false)
    """
    try:
        remove_from_zigbee = request.args.get('remove_from_zigbee', 'false').lower() == 'true'
        sensor_svc = _sensor_service()
        sensor_svc.delete_sensor(sensor_id, remove_from_zigbee=remove_from_zigbee)
        return _success({"sensor_id": sensor_id, "message": "Sensor removed"})
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.post('/v2/sensors/primary-metrics/resolve')
def resolve_primary_metrics_conflicts():
    """Remove conflicting primary metrics from selected sensors."""
    try:
        raw = request.get_json() or {}
        unit_id = int(raw.get("unit_id") or 0)
        if unit_id <= 0:
            return _fail("unit_id is required", 400)

        updates = raw.get("unassign") or []
        if not isinstance(updates, list) or not updates:
            return _fail("unassign list is required", 400)

        for entry in updates:
            sensor_id = int(entry.get("sensor_id") or 0)
            if sensor_id <= 0:
                continue
            metrics = _normalize_primary_metrics(entry.get("metrics") or [])
            sensor_config = _device_repo().find_sensor_config_by_id(sensor_id)
            if not sensor_config:
                return _fail(f"Sensor {sensor_id} not found", 404)
            if int(sensor_config.get("unit_id") or 0) != unit_id:
                return _fail(f"Sensor {sensor_id} does not belong to unit {unit_id}", 400)

            current = list(sensor_config.get("config", {}).get("primary_metrics") or [])
            remaining = [m for m in current if m not in metrics]
            _update_primary_metrics(
                sensor_id=sensor_id,
                unit_id=unit_id,
                new_metrics=remaining,
            )

        return _success({"message": "Conflicts resolved"})
    except ValueError as e:
        return _fail(str(e), 400)
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.patch('/v2/sensors/<int:sensor_id>/primary-metrics')
def update_primary_metrics(sensor_id: int):
    """Update primary metrics for a sensor with conflict checking."""
    try:
        raw = request.get_json() or {}
        desired_metrics = _normalize_primary_metrics(raw.get("primary_metrics"))

        sensor_config = _device_repo().find_sensor_config_by_id(sensor_id)
        if not sensor_config:
            return _fail("Sensor not found", 404)
        unit_id = int(sensor_config.get("unit_id") or 0)
        if unit_id <= 0:
            return _fail("Invalid sensor unit", 400)

        conflicts = _find_primary_metric_conflicts(
            unit_id=unit_id,
            desired_metrics=desired_metrics,
            exclude_sensor_id=sensor_id,
        )
        if conflicts:
            return _fail(
                "Primary metrics already assigned",
                409,
                details={"conflicts": conflicts},
            )

        _update_primary_metrics(
            sensor_id=sensor_id,
            unit_id=unit_id,
            new_metrics=desired_metrics,
        )

        return _success({"sensor_id": sensor_id, "primary_metrics": desired_metrics})
    except ValueError as e:
        return _fail(str(e), 400)
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.patch('/v2/sensors/<int:sensor_id>')
def update_sensor(sensor_id: int):
    """Update sensor details (name/config)."""
    try:
        raw = request.get_json() or {}
        try:
            body = UpdateSensorRequest(**raw)
        except ValidationError as ve:
            logger.warning("Validation error updating sensor: %s raw=%s", ve.errors(), raw)
            return _fail("Invalid sensor payload", 400, details={"errors": ve.errors()})

        device_repo = _device_repo()
        sensor_svc = _sensor_service()
        sensor_config = device_repo.find_sensor_config_by_id(sensor_id)
        if not sensor_config:
            return _fail("Sensor not found", 404)

        updates = {}
        if body.name is not None:
            updates["name"] = body.name
        if body.type is not None:
            updates["sensor_type"] = body.type.value
        if body.communication_type is not None:
            updates["protocol"] = body.communication_type.value
        if body.model is not None:
            updates["model"] = body.model.value if hasattr(body.model, "value") else str(body.model)

        if updates:
            if not device_repo.update_sensor_fields(sensor_id=sensor_id, **updates):
                return _fail("Failed to update sensor fields", 500)

        config = dict(sensor_config.get("config") or {})
        config_updated = False

        if "friendly_name" in raw and raw.get("friendly_name"):
            config["friendly_name"] = raw.get("friendly_name")
            config_updated = True
        if "mqtt_topic" in raw and raw.get("mqtt_topic"):
            config["mqtt_topic"] = raw.get("mqtt_topic")
            config_updated = True

        if config_updated:
            if not device_repo.update_sensor_config(sensor_id=sensor_id, config_data=config):
                return _fail("Failed to update sensor config", 500)

        refreshed = dict(sensor_config)
        refreshed.update(updates)
        refreshed["config"] = config
        sensor_svc.register_sensor_config(refreshed)

        return _success({"sensor_id": sensor_id, **updates, "config": config})
    except Exception as e:
        return _fail(str(e), 500)


# =====================================
# SENSOR CALIBRATION (System-level)
# =====================================

@devices_api.post('/sensors/<int:sensor_id>/calibrate')
def calibrate_sensor(sensor_id: int):
    """
    Calibrate a sensor with a known reference value.
    
    Request body:
        {
            "reference_value": 50.0,
            "calibration_type": "linear"  // optional: linear, polynomial, lookup
        }
    """
    try:
        data = request.get_json() if request.is_json else {}
        
        reference_value = data.get('reference_value')
        calibration_type = data.get('calibration_type', 'linear')
        
        if reference_value is None:
            return _fail('reference_value is required', 400)
        
        try:
            reference_value = float(reference_value)
        except (TypeError, ValueError):
            return _fail('reference_value must be numeric', 400)
        
        device_health = _device_health_service()
        result = device_health.calibrate_sensor(
            sensor_id=sensor_id,
            reference_value=reference_value,
            calibration_type=calibration_type
        )
        
        if result.get('success'):
            return _success(result)
        else:
            error_msg = result.get('error', 'Calibration failed')
            error_type = result.get('error_type', 'unknown')
            
            if error_type == 'not_found':
                return _fail(error_msg, 404)
            elif error_type in ['service_unavailable', 'runtime_unavailable']:
                return _fail(error_msg, 503)
            else:
                return _fail(error_msg, 400)
                
    except Exception as e:
        return _fail(str(e), 500)


# =====================================
# SENSOR HEALTH & MONITORING
# =====================================

# Deprecated endpoint /api/devices/sensors/<id>/health removed - use /api/health/sensors/<id> instead


@devices_api.get('/sensors/<int:sensor_id>/anomalies')
def check_sensor_anomalies(sensor_id: int):
    """Check if sensor's recent readings contain anomalies."""
    try:
        device_health = _device_health_service()
        result = device_health.check_sensor_anomalies(sensor_id)
        
        if result.get('success'):
            return _success(result)
        else:
            error_msg = result.get('error', 'Failed to check anomalies')
            error_type = result.get('error_type', 'unknown')
            
            if error_type == 'not_found':
                return _fail(error_msg, 404)
            elif error_type in ['service_unavailable', 'runtime_unavailable']:
                return _fail(error_msg, 503)
            else:
                return _fail(error_msg, 400)
                
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.get('/sensors/<int:sensor_id>/statistics')
def get_sensor_statistics(sensor_id: int):
    """Get statistical analysis of sensor readings."""
    try:
        device_health = _device_health_service()
        result = device_health.get_sensor_statistics(sensor_id)
        
        if result.get('success'):
            return _success(result)
        else:
            error_msg = result.get('error', 'Failed to get statistics')
            error_type = result.get('error_type', 'unknown')
            
            if error_type == 'not_found':
                return _fail(error_msg, 404)
            elif error_type in ['service_unavailable', 'runtime_unavailable']:
                return _fail(error_msg, 503)
            else:
                return _fail(error_msg, 400)
                
    except Exception as e:
        return _fail(str(e), 500)


# =====================================
# SENSOR DISCOVERY & READING
# =====================================

@devices_api.post('/sensors/discover')
def discover_mqtt_sensors():
    """
    Discover available MQTT sensors for a unit.
    
    Request body:
        {
            "unit_id": 1,
            "mqtt_topic_prefix": "growtent"  // optional
        }
    """
    try:
        data = request.get_json() if request.is_json else {}
        
        unit_id = data.get('unit_id')
        mqtt_topic_prefix = data.get('mqtt_topic_prefix', 'growtent')
        
        if unit_id is None:
            return _fail('unit_id is required', 400)
        
        try:
            unit_id = int(unit_id)
        except (TypeError, ValueError):
            return _fail('unit_id must be an integer', 400)
        
        logger.info(
            "MQTT discovery requested for unit %s (prefix=%s) - not implemented",
            unit_id,
            mqtt_topic_prefix,
        )
        return _success({"sensors": [], "count": 0})
                
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.get('/sensors/<int:sensor_id>/read')
def read_sensor_value(sensor_id: int):
    """Get current reading from a sensor."""
    try:
        sensor_svc = _sensor_service()
        reading = sensor_svc.read_sensor(sensor_id)
        
        if reading:
            return _success(reading.to_dict())

        return _fail(f"Sensor {sensor_id} not found or unavailable", 404)
                
    except Exception as e:
        return _fail(str(e), 500)


# =====================================
# SENSOR HISTORY
# =====================================

@devices_api.get('/sensors/<int:sensor_id>/history/calibration')
def get_sensor_calibration_history(sensor_id: int):
    """Get calibration history for a sensor."""
    try:
        limit = request.args.get('limit', 20, type=int)
        
        device_health = _device_health_service()
        history = device_health.get_sensor_calibration_history(sensor_id, limit)
        
        return _success({"history": history, "count": len(history)})
                
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.get('/sensors/<int:sensor_id>/history/health')
def get_sensor_health_history(sensor_id: int):
    """Get health history for a sensor."""
    try:
        limit = request.args.get('limit', 100, type=int)
        
        device_health = _device_health_service()
        history = device_health.get_sensor_health_history(sensor_id, limit)
        
        return _success({"history": history, "count": len(history)})
                
    except Exception as e:
        return _fail(str(e), 500)


@devices_api.get('/sensors/<int:sensor_id>/history/anomalies')
def get_sensor_anomaly_history(sensor_id: int):
    """Get anomaly history for a sensor."""
    try:
        limit = request.args.get('limit', 100, type=int)
        
        device_health = _device_health_service()
        history = device_health.get_sensor_anomaly_history(sensor_id, limit)
        
        return _success({"history": history, "count": len(history)})
                
    except Exception as e:
        return _fail(str(e), 500)


# ======================== DEVICE OPERATIONS ========================

@devices_api.post('/v2/sensors/<int:sensor_id>/identify')
def identify_sensor(sensor_id: int):
    """
    Trigger identification on a sensor (e.g., flash LED).
    
    Works with Zigbee2MQTT and other sensors that support identification.
    
    Query params:
        duration: int - Duration in seconds (default: 10)
    
    Returns:
        {
            "sensor_id": 42,
            "success": true,
            "message": "Identification triggered"
        }
    """
    try:
        duration = request.args.get('duration', 10, type=int)
        
        sensor_svc = _sensor_service()
        success = sensor_svc.identify_sensor(sensor_id, duration)
        
        if success:
            return _success({
                "sensor_id": sensor_id,
                "success": True,
                "message": f"Identification triggered for {duration}s"
            })
        else:
            return _fail(f"Sensor {sensor_id} does not support identification", 400)
            
    except Exception as e:
        logger.error(f"Error identifying sensor {sensor_id}: {e}")
        return _fail(str(e), 500)


@devices_api.get('/v2/sensors/<int:sensor_id>/device-info')
def get_sensor_device_info(sensor_id: int):
    """
    Get device information for a sensor.
    
    Returns hardware-level information including capabilities,
    protocol details, and network information.
    
    Returns:
        {
            "sensor_id": 42,
            "friendly_name": "garden_sensor_1",
            "ieee_address": "0x00124b001234abcd",
            "protocol": "Zigbee2MQTT",
            "capabilities": ["temperature", "humidity", "soil_moisture"],
            "available": true,
            ...
        }
    """
    try:
        sensor_svc = _sensor_service()
        info = sensor_svc.get_sensor_device_info(sensor_id)
        
        if info:
            return _success(info)
        else:
            return _fail(f"Sensor {sensor_id} not found or has no device info", 404)
            
    except Exception as e:
        logger.error(f"Error getting device info for sensor {sensor_id}: {e}")
        return _fail(str(e), 500)


@devices_api.get('/v2/sensors/<int:sensor_id>/state')
def get_sensor_state(sensor_id: int):
    """
    Get current state of a sensor.
    
    Returns the current readings and state information.
    
    Returns:
        {
            "sensor_id": 42,
            "available": true,
            "readings": {
                "temperature": 25.5,
                "humidity": 60.0
            },
            "last_update": "2025-01-24T10:30:00"
        }
    """
    try:
        sensor_svc = _sensor_service()
        state = sensor_svc.get_sensor_state(sensor_id)
        
        if state:
            return _success(state)
        else:
            return _fail(f"Sensor {sensor_id} not found or has no state", 404)
            
    except Exception as e:
        logger.error(f"Error getting state for sensor {sensor_id}: {e}")
        return _fail(str(e), 500)


@devices_api.post('/v2/sensors/<int:sensor_id>/rename')
def rename_sensor_device(sensor_id: int):
    """
    Rename sensor device on its network (e.g., Zigbee2MQTT).
    
    This renames the device at the network level. The database name
    should be updated separately using the update sensor endpoint.
    
    Request body:
        {
            "new_name": "kitchen_sensor"
        }
    
    Returns:
        {
            "sensor_id": 42,
            "success": true,
            "message": "Device renamed on network"
        }
    """
    try:
        data = request.get_json() if request.is_json else {}
        new_name = data.get('new_name')
        
        if not new_name:
            return _fail("new_name is required", 400)
        
        # Validate name
        if not new_name.replace('_', '').replace('-', '').isalnum():
            return _fail(
                "Device name can only contain letters, numbers, underscores and hyphens",
                400
            )
        
        sensor_svc = _sensor_service()
        success = sensor_svc.rename_sensor_device(sensor_id, new_name)
        
        if success:
            return _success({
                "sensor_id": sensor_id,
                "new_name": new_name,
                "success": True,
                "message": "Device renamed on network"
            })
        else:
            return _fail(f"Sensor {sensor_id} does not support rename", 400)
            
    except Exception as e:
        logger.error(f"Error renaming sensor {sensor_id}: {e}")
        return _fail(str(e), 500)


@devices_api.post('/v2/sensors/<int:sensor_id>/remove-from-network')
def remove_sensor_from_network(sensor_id: int):
    """
    Remove sensor device from its network (e.g., Zigbee network).
    
    This removes the device from the network level. The device will
    need to be re-paired to rejoin the network. This does NOT delete
    the sensor from the database.
    
    Returns:
        {
            "sensor_id": 42,
            "success": true,
            "message": "Device removal initiated"
        }
    """
    try:
        sensor_svc = _sensor_service()
        success = sensor_svc.remove_sensor_from_network(sensor_id)
        
        if success:
            return _success({
                "sensor_id": sensor_id,
                "success": True,
                "message": "Device removal initiated"
            })
        else:
            return _fail(f"Sensor {sensor_id} does not support network removal", 400)
            
    except Exception as e:
        logger.error(f"Error removing sensor {sensor_id} from network: {e}")
        return _fail(str(e), 500)


@devices_api.post('/v2/sensors/<int:sensor_id>/command')
def send_sensor_command(sensor_id: int):
    """
    Send a command to a sensor device.
    
    This is a unified endpoint for sending protocol-specific commands
    to sensors. The adapter handles command translation.
    
    Supported commands vary by adapter:
        - SYSGrow: restart, factory_reset, polling_interval, trigger_read, 
                   temperature_calibration, humidity_calibration, identify
        - Zigbee2MQTT: identify, calibration
        - WiFi: restart, polling_interval, calibration
    
    Request body:
        {
            "restart": true,              // Restart device
            "factory_reset": true,        // Factory reset
            "trigger_read": true,         // Immediate sensor read
            "polling_interval": 30000,    // Polling in ms
            "identify": 10,               // Flash LED for N seconds
            ...                           // Other protocol-specific params
        }
    
    Returns:
        {
            "sensor_id": 42,
            "success": true,
            "message": "Command sent successfully"
        }
    """
    try:
        data = request.get_json() if request.is_json else {}
        
        if not data:
            return _fail("Request body is required", 400)
        
        sensor_svc = _sensor_service()
        success = sensor_svc.send_command(sensor_id, data)
        
        if success:
            return _success({
                "sensor_id": sensor_id,
                "success": True,
                "message": "Command sent successfully"
            })
        else:
            return _fail(f"Sensor {sensor_id} does not support commands", 400)
            
    except Exception as e:
        logger.error(f"Error sending command to sensor {sensor_id}: {e}")
        return _fail(str(e), 500)
