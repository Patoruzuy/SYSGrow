"""
SYSGrow Bridge Management
=========================

Bridge-level endpoints for managing SYSGrow ESP32-C6 networks.
Handles operations that affect the entire network or bridge, not individual devices.

Individual device operations (identify, rename, remove, restart) are available via:
    - POST /api/devices/v2/sensors/<id>/identify
    - POST /api/devices/v2/sensors/<id>/rename
    - POST /api/devices/v2/sensors/<id>/remove-from-network
    - POST /api/devices/v2/sensors/<id>/command

All routes are registered under /api/devices prefix.
"""

from __future__ import annotations

import logging

from flask import Response

from app.blueprints.api._common import (
    fail as _fail,
    get_json as _json,
    success as _success,
)
from app.utils.http import safe_route

from . import devices_api

logger = logging.getLogger(__name__)


def _get_sysgrow_adapter(friendly_name: str | None = None):
    """
    Retrieve a live, registered SYSGrowAdapter from the sensor management service.

    Adapters are created and owned by SensorManagementService at registration time.
    Creating a new adapter here would open duplicate MQTT subscriptions, bypass the
    command queue / state tracking, and produce an instance unknown to the rest of
    the system.

    For bridge-level commands (permit_join, health_check, restart_all) any registered
    SYSGrow adapter works because bridge topics are device-agnostic.
    For device-specific commands (OTA update) the caller passes the device's
    friendly_name so we can return that exact sensor's adapter.

    Args:
        friendly_name: Device friendly name for device-specific commands, or None
                       for bridge-level operations.

    Returns:
        The live SYSGrowAdapter instance, or None if none is registered / reachable.
    """
    from flask import current_app

    from app.hardware.adapters.sensors import SYSGrowAdapter

    container = current_app.config.get("CONTAINER")
    if not container:
        return None

    sensor_manager = getattr(container, "sensor_management_service", None)
    if not sensor_manager:
        return None

    if friendly_name:
        # Device-specific: return the adapter registered under that name.
        sensor = sensor_manager.get_sensor_by_friendly_name(friendly_name)
        if sensor is None:
            logger.warning("No registered SYSGrow sensor found for friendly_name=%s", friendly_name)
            return None
        adapter = getattr(sensor, "_adapter", None)
        if isinstance(adapter, SYSGrowAdapter):
            return adapter
        logger.warning("Sensor %s has no SYSGrowAdapter (type=%s)", friendly_name, type(adapter).__name__)
        return None

    # Bridge-level: any registered SYSGrow adapter will do since bridge topics
    # are the same regardless of which device's adapter publishes them.
    for sensor in sensor_manager.get_all_sensors():
        adapter = getattr(sensor, "_adapter", None)
        if isinstance(adapter, SYSGrowAdapter):
            return adapter

    logger.warning("No registered SYSGrow sensors found; bridge commands unavailable")
    return None


# ==================== V2 BRIDGE OPERATIONS ====================


@devices_api.post("/v2/sysgrow/permit-join")
@safe_route("Failed to send permit_join command")
def sysgrow_permit_join() -> Response:
    """
    Enable BLE pairing mode on SYSGrow bridge.

    Allows new devices to join the network for a specified duration.

    Request Body:
        - value: true to enable, false to disable (default: true)
        - time: Pairing timeout in seconds (default: 30, max: 300)

    Returns:
        {
            "command": "permit_join",
            "value": true,
            "time": 30,
            "status": "sent",
            "transaction_id": "abc123"
        }
    """
    payload = _json()

    enable = payload.get("value", True)
    timeout = min(payload.get("time", 30), 300)

    adapter = _get_sysgrow_adapter()
    if adapter is None:
        return _fail("No registered SYSGrow sensor available for bridge commands", 503)

    if enable:
        transaction_id = adapter.enable_ble_pairing(timeout_seconds=timeout)
    else:
        transaction_id = adapter.disable_ble_pairing()

    return _success(
        {
            "command": "permit_join",
            "value": enable,
            "time": timeout,
            "status": "sent",
            "transaction_id": transaction_id,
        }
    )


@devices_api.get("/v2/sysgrow/health")
@safe_route("Failed to send health check request")
def sysgrow_health_check() -> Response:
    """
    Request health check from SYSGrow bridge.

    The bridge will respond on sysgrow/bridge/health with status info
    including connected devices, uptime, and network health.

    Returns:
        {
            "command": "health_check",
            "status": "sent"
        }
    """
    adapter = _get_sysgrow_adapter()
    if adapter is None:
        return _fail("No registered SYSGrow sensor available for bridge commands", 503)

    success = adapter.request_health_check()
    return _success({"command": "health_check", "status": "sent" if success else "failed"})


@devices_api.post("/v2/sysgrow/restart-all")
@safe_route("Failed to send restart command")
def sysgrow_restart_all() -> Response:
    """
    Restart all SYSGrow devices on the network.

    This is a bridge-level command that restarts all connected devices.
    To restart a specific device, use POST /v2/sensors/<id>/command
    with {"restart": true}.

    Returns:
        {
            "command": "restart_all",
            "status": "sent"
        }
    """
    adapter = _get_sysgrow_adapter()
    if adapter is None:
        return _fail("No registered SYSGrow sensor available for bridge commands", 503)

    success = adapter._publish("sysgrow/bridge/request/restart", {})

    return _success({"command": "restart_all", "status": "sent" if success else "failed"})


@devices_api.post("/v2/sysgrow/ota-update")
@safe_route("Failed to send OTA update command")
def sysgrow_ota_update() -> Response:
    """
    Trigger OTA firmware update on a SYSGrow device.

    Request Body:
        - id (required): Device friendly_name or sensor_id
        - url (required): Firmware binary URL

    Returns:
        {
            "command": "ota_update",
            "id": "device_id",
            "url": "https://...",
            "status": "sent",
            "transaction_id": "abc123"
        }
    """
    payload = _json()

    device_id = payload.get("id")
    firmware_url = payload.get("url")

    if not device_id or not firmware_url:
        return _fail("Both 'id' and 'url' fields are required.", 400)

    adapter = _get_sysgrow_adapter(friendly_name=str(device_id))
    if adapter is None:
        return _fail(f"No registered SYSGrow sensor found for device '{device_id}'", 404)

    transaction_id = adapter.start_ota_update(firmware_url=firmware_url)
    return _success(
        {
            "command": "ota_update",
            "id": device_id,
            "url": firmware_url,
            "status": "sent",
            "transaction_id": transaction_id,
        }
    )
