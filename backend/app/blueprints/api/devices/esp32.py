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
from flask import request

from . import devices_api
from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
    get_json as _json,
)

logger = logging.getLogger(__name__)


def _get_sysgrow_adapter(friendly_name: str = None):
    """
    Get a SYSGrowAdapter instance for bridge commands.

    Args:
        friendly_name: Device name for device-specific commands, or None for bridge

    Returns:
        SYSGrowAdapter instance or None if MQTT unavailable
    """
    from flask import current_app
    from app.hardware.adapters.sensors import SYSGrowAdapter

    container = current_app.config.get("CONTAINER")
    if not container or not hasattr(container, "mqtt_client"):
        return None

    mqtt_client = container.mqtt_client
    if not mqtt_client:
        return None

    return SYSGrowAdapter(
        sensor_id=0,
        mqtt_client=mqtt_client,
        friendly_name=friendly_name or "bridge",
        unit_id=0,
    )


# ==================== V2 BRIDGE OPERATIONS ====================


@devices_api.post("/v2/sysgrow/permit-join")
def sysgrow_permit_join():
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

    try:
        adapter = _get_sysgrow_adapter()
        if adapter is None:
            return _fail("MQTT client not available", 503)

        if enable:
            transaction_id = adapter.enable_ble_pairing(timeout_seconds=timeout)
        else:
            transaction_id = adapter.disable_ble_pairing()

        return _success({
            "command": "permit_join",
            "value": enable,
            "time": timeout,
            "status": "sent",
            "transaction_id": transaction_id
        })
    except Exception as exc:
        logger.error(f"Failed to send permit_join command: {exc}")
        return _fail(f"Failed to send permit_join command: {str(exc)}", 500)


@devices_api.get("/v2/sysgrow/health")
def sysgrow_health_check():
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
    try:
        adapter = _get_sysgrow_adapter()
        if adapter is None:
            return _fail("MQTT client not available", 503)

        success = adapter.request_health_check()
        return _success({
            "command": "health_check",
            "status": "sent" if success else "failed"
        })
    except Exception as exc:
        logger.error(f"Failed to send health check request: {exc}")
        return _fail(f"Failed to send health check request: {str(exc)}", 500)


@devices_api.post("/v2/sysgrow/restart-all")
def sysgrow_restart_all():
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
    try:
        adapter = _get_sysgrow_adapter()
        if adapter is None:
            return _fail("MQTT client not available", 503)

        success = adapter._publish("sysgrow/bridge/request/restart", {})

        return _success({
            "command": "restart_all",
            "status": "sent" if success else "failed"
        })
    except Exception as exc:
        logger.error(f"Failed to send restart command: {exc}")
        return _fail(f"Failed to send restart command: {str(exc)}", 500)


@devices_api.post("/v2/sysgrow/ota-update")
def sysgrow_ota_update():
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

    try:
        adapter = _get_sysgrow_adapter(friendly_name=str(device_id))
        if adapter is None:
            return _fail("MQTT client not available", 503)

        transaction_id = adapter.start_ota_update(firmware_url=firmware_url)
        return _success({
            "command": "ota_update",
            "id": device_id,
            "url": firmware_url,
            "status": "sent",
            "transaction_id": transaction_id
        })
    except Exception as exc:
        logger.error(f"Failed to send OTA update command: {exc}")
        return _fail(f"Failed to send OTA update command: {str(exc)}", 500)
