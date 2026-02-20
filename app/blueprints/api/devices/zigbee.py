"""
Zigbee2MQTT Integration Endpoints
Handles Zigbee2MQTT device discovery, command sending, and device-level calibration.
"""

from __future__ import annotations

import logging

from flask import Response, request

from app.utils.http import safe_route

from ..devices import devices_api
from .utils import _actuator_service, _fail, _sensor_service, _success, _zigbee_service

logger = logging.getLogger(__name__)

# ======================== ZIGBEE2MQTT DISCOVERY ========================


@devices_api.get("/v2/zigbee2mqtt/discover")
@safe_route("Failed to discover zigbee devices")
def discover_zigbee_devices() -> Response:
    """
    Gets a list of devices discovered by the Zigbee service with full metadata.

    Returns:
        {
            "devices": [
                {
                    "ieee_address": "0x00124b001234abcd",
                    "friendly_name": "Living Room Sensor",
                    "type": "EndDevice",
                    "model_id": "TS0201",
                    "manufacturer": "TuYa",
                    "supported": true,
                    "definition": {
                        "model": "TS0201",
                        "vendor": "TuYa",
                        "description": "Temperature & humidity sensor",
                        "exposes": [...]
                    },
                    "power_source": "Battery",
                    "software_build_id": "..."
                }
            ]
        }
    """
    try:
        svc = _zigbee_service()

        # Check if service is available
        if svc is None:
            return _fail(
                "Zigbee2MQTT service is not available. Ensure MQTT is enabled in configuration.",
                503,
                details={"hint": "Set SYSGROW_ENABLE_MQTT=true and restart the server"},
            )

        # Get full device list with all metadata
        full_devices = svc.get_devices(timeout=3.0) or []

        logger.info("Discovered %s zigbee devices with full metadata", len(full_devices))

        devices = []
        for device in full_devices:
            # Handle DiscoveredDevice objects - convert to dict
            if hasattr(device, "to_dict"):
                # DiscoveredDevice object
                device_dict = device.to_dict()
                device_type = device_dict.get("device_type", "")

                # Extract sensor types from capabilities
                sensor_types = []
                if "capabilities" in device_dict:
                    for cap in device_dict.get("capabilities", []):
                        if isinstance(cap, dict):
                            # Prefer 'property' (matches Zigbee2MQTT payload keys), fallback to 'name'
                            cap_key = cap.get("property") or cap.get("name") or ""
                            if cap_key:
                                sensor_types.append(cap_key)
            elif isinstance(device, dict):
                # Already a dict
                device_dict = device
                device_type = device_dict.get("type", "")
                sensor_types = []
            else:
                # DiscoveredDevice object without to_dict method - convert manually
                device_dict = {
                    "ieee_address": getattr(device, "ieee_address", ""),
                    "friendly_name": getattr(device, "friendly_name", ""),
                    "device_type": getattr(device, "device_type", ""),
                    "model": getattr(device, "model", ""),
                    "vendor": getattr(device, "vendor", ""),
                    "supported": True,
                    "power_source": "Unknown",
                }
                device_type = device_dict.get("device_type", "")
                sensor_types = (
                    [cap.name for cap in getattr(device, "capabilities", [])] if hasattr(device, "capabilities") else []
                )

            # Include coordinator with special handling
            if device_type == "Coordinator":
                # Mark coordinator as online when discovered
                device_dict["online"] = True
                device_dict["role"] = "coordinator"

            # Extract key information
            device_info = {
                "ieee_address": device_dict.get("ieee_address", ""),
                "friendly_name": device_dict.get("friendly_name", device_dict.get("ieee_address", "")),
                "type": device_type,
                "model_id": device_dict.get("model_id", device_dict.get("model", "")),
                "manufacturer": device_dict.get("manufacturer", device_dict.get("vendor", "")),
                "supported": device_dict.get("supported", False),
                "power_source": device_dict.get("power_source", "Unknown"),
                "sensor_types": sensor_types,
            }

            # Add definition details if available (for additional metadata)
            if "definition" in device_dict and device_dict.get("definition"):
                definition = device_dict["definition"]
                device_info["definition"] = {
                    "model": definition.get("model", ""),
                    "vendor": definition.get("vendor", ""),
                    "description": definition.get("description", ""),
                }

            devices.append(device_info)

        return _success({"devices": devices})
    except TimeoutError as e:
        logger.warning("Zigbee discovery timeout: %s", e)
        return _fail(
            "Zigbee2MQTT bridge did not respond in time. Check if zigbee2mqtt is running.",
            504,
            details={"error": str(e)},
        )


@devices_api.get("/zigbee2mqtt/devices")
@safe_route("Failed to get Zigbee2MQTT devices")
def get_zigbee2mqtt_devices() -> Response:
    """
    DEPRECATED: Use /v2/zigbee2mqtt/discover instead.

    Get all discovered Zigbee2MQTT devices.
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail(
            "Zigbee2MQTT service is not available. Ensure MQTT is enabled in configuration.",
            503,
            details={"hint": "Set SYSGROW_ENABLE_MQTT=true and restart the server"},
        )

    # Get full device list
    full_devices = svc.get_devices(timeout=3.0) or []

    # Transform to old format for backward compatibility
    all_devices = []
    for device in full_devices:
        if hasattr(device, "to_dict"):
            device_dict = device.to_dict()
        elif isinstance(device, dict):
            device_dict = device
        else:
            continue

        transformed = {
            "ieee_address": device_dict.get("ieee_address", ""),
            "friendly_name": device_dict.get("friendly_name", ""),
            "model": device_dict.get("model", device_dict.get("model_id", "")),
            "vendor": device_dict.get("vendor", device_dict.get("manufacturer", "")),
            "device_type": device_dict.get("device_type", device_dict.get("type", "")),
            "supports_power_monitoring": False,
            "endpoints": [],
            "discovered_at": None,
        }
        all_devices.append(transformed)

    return _success({"devices": all_devices, "count": len(all_devices)})


@devices_api.get("/zigbee2mqtt/devices/unit/<int:unit_id>")
@safe_route("Failed to get Zigbee2MQTT devices by unit")
def get_zigbee2mqtt_devices_by_unit(unit_id: int) -> Response:
    """
    DEPRECATED: Use /v2/zigbee2mqtt/discover instead.

    Get discovered Zigbee2MQTT devices.
    Note: Zigbee devices are now managed globally, not per-unit.
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail("Zigbee2MQTT service is not available", 503)

    # Get all devices - they're global, not per-unit
    full_devices = svc.get_devices(timeout=3.0) or []

    # Transform to old format
    devices = []
    for device in full_devices:
        if hasattr(device, "to_dict"):
            device_dict = device.to_dict()
        elif isinstance(device, dict):
            device_dict = device
        else:
            continue

        transformed = {
            "ieee_address": device_dict.get("ieee_address", ""),
            "friendly_name": device_dict.get("friendly_name", ""),
            "model": device_dict.get("model", ""),
            "vendor": device_dict.get("vendor", ""),
            "device_type": device_dict.get("device_type", ""),
        }
        devices.append(transformed)

    return _success({"unit_id": unit_id, "devices": devices, "count": len(devices)})


@devices_api.post("/zigbee2mqtt/command")
@safe_route("Failed to send Zigbee2MQTT command")
def send_zigbee2mqtt_command() -> Response:
    """
    Send command to a Zigbee2MQTT device.

    Routes through SensorManagementService or ActuatorManagementService
    adapters when the device is registered, falling back to ZigbeeManagementService
    for unregistered devices.

    Request body:
        {
            "friendly_name": "smart_plug_1",
            "command": {"state": "ON"}
        }

    Returns:
        {
            "success": true,
            "message": "Command sent to smart_plug_1"
        }
    """
    data = request.get_json() if request.is_json else {}

    friendly_name = data.get("friendly_name")
    command = data.get("command")

    if not friendly_name or not command:
        return _fail("friendly_name and command are required", 400)

    # Try sensor management service first (handles registered sensors)
    sensor_svc = _sensor_service()
    if sensor_svc:
        success = sensor_svc.send_command_by_name(friendly_name, command)
        if success:
            return _success({"success": True, "message": f"Command sent to sensor {friendly_name}"})

    # Try actuator management service (handles registered actuators)
    actuator_svc = _actuator_service()
    if actuator_svc:
        success = actuator_svc.send_zigbee2mqtt_command(friendly_name, command)
        if success:
            return _success({"success": True, "message": f"Command sent to {friendly_name}"})

    # Fallback to direct ZigbeeManagementService for unregistered devices
    zigbee_svc = _zigbee_service()
    if not zigbee_svc:
        return _fail("Zigbee2MQTT service not available", 503)

    success = zigbee_svc.send_command(friendly_name, command)

    if success:
        return _success({"success": True, "message": f"Command sent to {friendly_name}"})
    else:
        return _fail(f"Failed to send command to {friendly_name}", 500)


# ======================== ZIGBEE2MQTT CALIBRATION ========================


@devices_api.get("/sensors/<int:sensor_id>/zigbee2mqtt/calibration")
@safe_route("Failed to get Zigbee2MQTT calibration")
def get_zigbee2mqtt_calibration(sensor_id: int) -> Response:
    """
    Get device-level calibration offsets for Zigbee2MQTT sensor.

    Returns:
        {
            "success": true,
            "sensor_id": 42,
            "calibration_offsets": {
                "temperature": -1.5,
                "humidity": 2.0
            }
        }
    """
    sensor_svc = _sensor_service()
    sensor = sensor_svc.get_sensor(sensor_id)

    if not sensor:
        return _fail(f"Sensor {sensor_id} not found", 404)

    # Check if this is a Zigbee2MQTT sensor
    if str(sensor.get("protocol") or "").lower() != "zigbee2mqtt":
        return _fail("This endpoint is only for Zigbee2MQTT sensors", 400)

    sensor_entity = sensor_svc.get_sensor_entity(sensor_id)
    if not sensor_entity:
        return _success(
            {
                "sensor_id": sensor_id,
                "calibration_offsets": {},
                "message": "Sensor not registered in runtime - calibration unavailable",
            }
        )

    if not sensor_entity or not hasattr(sensor_entity._adapter, "get_calibration_offsets"):
        return _fail("Sensor not available or does not support calibration", 503)

    offsets = sensor_entity._adapter.get_calibration_offsets()

    return _success({"sensor_id": sensor_id, "calibration_offsets": offsets})


@devices_api.post("/sensors/<int:sensor_id>/zigbee2mqtt/calibration")
@safe_route("Failed to set Zigbee2MQTT calibration")
def set_zigbee2mqtt_calibration(sensor_id: int) -> Response:
    """
    Set device-level calibration offset for Zigbee2MQTT sensor.

    Request body:
        {
            "sensor_type": "temperature",  // or "humidity", "soil_moisture", etc.
            "offset": -1.5
        }

    Returns:
        {
            "success": true,
            "sensor_id": 42,
            "sensor_type": "temperature",
            "offset": -1.5,
            "message": "Calibration offset set successfully"
        }
    """
    data = request.get_json() if request.is_json else {}

    sensor_type = data.get("sensor_type")
    offset = data.get("offset")

    if not sensor_type:
        return _fail("sensor_type is required", 400)

    if offset is None:
        return _fail("offset is required", 400)

    try:
        offset = float(offset)
    except (TypeError, ValueError):
        return _fail("offset must be numeric", 400)

    sensor_svc = _sensor_service()
    sensor = sensor_svc.get_sensor(sensor_id)

    if not sensor:
        return _fail(f"Sensor {sensor_id} not found", 404)

    # Check if this is a Zigbee2MQTT sensor
    if str(sensor.get("protocol") or "").lower() != "zigbee2mqtt":
        return _fail("This endpoint is only for Zigbee2MQTT sensors", 400)

    sensor_entity = sensor_svc.get_sensor_entity(sensor_id)
    if not sensor_entity or not hasattr(sensor_entity._adapter, "set_calibration_offset"):
        return _fail("Sensor not available or does not support calibration", 503)

    # Set calibration on device
    sensor_entity._adapter.set_calibration_offset(sensor_type, offset)

    return _success(
        {
            "sensor_id": sensor_id,
            "sensor_type": sensor_type,
            "offset": offset,
            "message": "Calibration offset set successfully",
        }
    )


# ======================== ZIGBEE2MQTT BRIDGE MANAGEMENT ========================


@devices_api.get("/v2/zigbee2mqtt/bridge/status")
@safe_route("Failed to get Zigbee bridge status")
def get_zigbee_bridge_status() -> Response:
    """
    Get Zigbee2MQTT bridge status and health.

    Returns:
        {
            "online": true,
            "health": {...},
            "device_count": 5
        }
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail(
            "Zigbee2MQTT service is not available",
            503,
            details={"hint": "Set SYSGROW_ENABLE_MQTT=true and restart the server"},
        )

    # Get bridge health
    health = svc.get_bridge_health(timeout=3.0)

    # Get device count
    devices = svc.get_discovered_devices()
    device_count = len([d for d in devices if d.device_type != "Coordinator"])

    return _success(
        {
            "online": svc.is_online or False,
            "health": health,
            "device_count": device_count,
            "coordinator_active": any(d.device_type == "Coordinator" for d in devices),
        }
    )


@devices_api.post("/v2/zigbee2mqtt/permit-join")
@safe_route("Failed to set Zigbee permit join")
def permit_zigbee_join() -> Response:
    """
    Enable permit join to allow new Zigbee devices to join the network.

    Request body:
        {
            "duration": 254  // Time in seconds (default 254 = ~4 minutes, 0 = disable)
        }

    Returns:
        {
            "permit_join": true,
            "duration": 254,
            "message": "Permit join enabled for 254 seconds"
        }
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail(
            "Zigbee2MQTT service is not available",
            503,
            details={"hint": "Set SYSGROW_ENABLE_MQTT=true and restart the server"},
        )

    data = request.get_json() if request.is_json else {}
    duration = data.get("duration", 254)

    # Validate duration
    try:
        duration = int(duration)
        if duration < 0 or duration > 254:
            return _fail("Duration must be between 0 and 254 seconds", 400)
    except (TypeError, ValueError):
        return _fail("Duration must be a valid integer", 400)

    success = svc.permit_device_join(time=duration)

    if success:
        if duration == 0:
            message = "Permit join disabled"
        else:
            message = f"Permit join enabled for {duration} seconds"

        return _success({"permit_join": duration > 0, "duration": duration, "message": message})
    else:
        return _fail("Failed to set permit join", 500)


@devices_api.post("/v2/zigbee2mqtt/rediscover")
@safe_route("Failed to force Zigbee rediscovery")
def force_zigbee_rediscovery() -> Response:
    """
    Force a complete rediscovery of all Zigbee devices.
    Clears the cache and requests fresh device list from bridge.

    Returns:
        {
            "message": "Rediscovery initiated",
            "previous_count": 5
        }
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail("Zigbee2MQTT service is not available", 503)

    # Get previous count
    previous_count = len(svc.get_discovered_devices())

    # Force rediscovery
    svc.force_rediscovery()

    return _success({"message": "Rediscovery initiated", "previous_count": previous_count})


# ======================== ZIGBEE2MQTT DEVICE MANAGEMENT ========================


@devices_api.get("/v2/zigbee2mqtt/devices/<ieee_address>")
@safe_route("Failed to get Zigbee device")
def get_zigbee_device(ieee_address: str) -> Response:
    """
    Get details for a specific Zigbee device by IEEE address.

    Returns:
        {
            "device": {
                "ieee_address": "0x00124b001234abcd",
                "friendly_name": "Living Room Sensor",
                ...
            },
            "state": {...}
        }
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail("Zigbee2MQTT service is not available", 503)

    device = svc.get_device_by_ieee(ieee_address)

    if not device:
        return _fail(f"Device {ieee_address} not found", 404)

    # Get current state
    state = svc.get_device_state(device.friendly_name)

    return _success({"device": device.to_dict(), "state": state})


@devices_api.get("/v2/zigbee2mqtt/devices/<ieee_address>/state")
@safe_route("Failed to get Zigbee device state")
def get_zigbee_device_state(ieee_address: str) -> Response:
    """
    Get current state of a Zigbee device.

    Returns:
        {
            "ieee_address": "0x00124b001234abcd",
            "friendly_name": "smart_plug_1",
            "state": {
                "state": "ON",
                "power": 45.5,
                "voltage": 230.1,
                ...
            }
        }
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail("Zigbee2MQTT service is not available", 503)

    device = svc.get_device_by_ieee(ieee_address)

    if not device:
        return _fail(f"Device {ieee_address} not found", 404)

    state = svc.get_device_state(device.friendly_name)

    return _success({"ieee_address": ieee_address, "friendly_name": device.friendly_name, "state": state or {}})


@devices_api.post("/v2/zigbee2mqtt/devices/<ieee_address>/rename")
@safe_route("Failed to rename Zigbee device")
def rename_zigbee_device(ieee_address: str) -> Response:
    """
    Rename a Zigbee device.

    Request body:
        {
            "new_name": "kitchen_sensor"
        }

    Returns:
        {
            "ieee_address": "0x00124b001234abcd",
            "old_name": "0x00124b001234abcd",
            "new_name": "kitchen_sensor",
            "message": "Device renamed successfully"
        }
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail("Zigbee2MQTT service is not available", 503)

    data = request.get_json() if request.is_json else {}
    new_name = data.get("new_name")

    if not new_name:
        return _fail("new_name is required", 400)

    # Validate name (no special characters that could cause issues)
    if not new_name.replace("_", "").replace("-", "").isalnum():
        return _fail("Device name can only contain letters, numbers, underscores and hyphens", 400)

    # Get current device info
    device = svc.get_device_by_ieee(ieee_address)
    old_name = device.friendly_name if device else ieee_address

    try:
        response = svc.rename_device(ieee_address, new_name, timeout=5.0)

        return _success(
            {
                "ieee_address": ieee_address,
                "old_name": old_name,
                "new_name": new_name,
                "response": response,
                "message": "Device renamed successfully",
            }
        )

    except TimeoutError:
        return _fail("Rename operation timed out", 504)


@devices_api.delete("/v2/zigbee2mqtt/devices/<ieee_address>")
@safe_route("Failed to remove Zigbee device")
def remove_zigbee_device(ieee_address: str) -> Response:
    """
    Remove a Zigbee device from the network.

    Query params:
        force: bool - Force remove even if device is offline (default: false)

    Returns:
        {
            "ieee_address": "0x00124b001234abcd",
            "message": "Device removal initiated"
        }
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail("Zigbee2MQTT service is not available", 503)

    # Check if device exists
    device = svc.get_device_by_ieee(ieee_address)
    if not device:
        return _fail(f"Device {ieee_address} not found", 404)

    # Don't allow removing coordinator
    if device.device_type == "Coordinator":
        return _fail("Cannot remove the coordinator", 400)

    success = svc.remove_device(ieee_address=ieee_address)

    if success:
        return _success(
            {
                "ieee_address": ieee_address,
                "friendly_name": device.friendly_name,
                "message": "Device removal initiated",
            }
        )
    else:
        return _fail("Failed to remove device", 500)


@devices_api.get("/v2/zigbee2mqtt/sensors")
@safe_route("Failed to get Zigbee sensors")
def get_zigbee_sensors() -> Response:
    """
    Get only Zigbee sensor devices (temperature, humidity, soil moisture, etc.)

    Returns:
        {
            "sensors": [...],
            "count": 3
        }
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail("Zigbee2MQTT service is not available", 503)

    sensors = svc.get_sensors()

    return _success({"sensors": [s.to_dict() for s in sensors], "count": len(sensors)})


@devices_api.get("/v2/zigbee2mqtt/actuators")
@safe_route("Failed to get Zigbee actuators")
def get_zigbee_actuators() -> Response:
    """
    Get only Zigbee actuator devices (switches, plugs, lights, etc.)

    Returns:
        {
            "actuators": [...],
            "count": 2
        }
    """
    svc = _zigbee_service()

    if svc is None:
        return _fail("Zigbee2MQTT service is not available", 503)

    actuators = svc.get_actuators()

    return _success({"actuators": [a.to_dict() for a in actuators], "count": len(actuators)})
