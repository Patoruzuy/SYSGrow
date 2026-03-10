"""
Actuator CRUD Operations
Handles creating, reading, and deleting actuators.
"""

from __future__ import annotations

import logging

from flask import Response, request
from pydantic import ValidationError

from app.schemas import CreateActuatorRequest
from app.utils.http import safe_route

from ...devices import devices_api
from ..utils import (
    _actuator_service,  # Direct hardware service access
    _actuator_to_response,
    _fail,
    _growth_service,
    _success,
)

logger = logging.getLogger(__name__)

# ======================== ACTUATOR CRUD ========================


@devices_api.get("/v2/actuators")
@safe_route("Failed to list actuators")
def get_all_actuators_() -> Response:
    """
    Endpoint returning ActuatorResponse objects for all actuators.
    """
    actuator_svc = _actuator_service()
    actuators = actuator_svc.list_actuators()

    typed = [_actuator_to_response(actuator) for actuator in actuators]

    return _success([a.model_dump() for a in typed])


@devices_api.get("/v2/actuators/unit/<int:unit_id>")
@safe_route("Failed to list actuators for unit")
def get_actuators_for_unit(unit_id: int) -> Response:
    """Endpoint returning actuators for a specific unit."""
    actuator_svc = _actuator_service()
    actuators = actuator_svc.list_actuators(unit_id=unit_id)
    typed = [_actuator_to_response(actuator) for actuator in actuators]
    return _success([a.model_dump() for a in typed])


@devices_api.post("/v2/actuators")
@safe_route("Failed to create actuator")
def add_actuator_v2() -> Response:
    """
    Typed actuator creation endpoint using CreateActuatorRequest.

    This v2-style API validates the payload with Pydantic and calls
    ActuatorManagementService.create_actuator with normalized values.
    """
    raw = request.get_json() or {}
    try:
        body = CreateActuatorRequest(**raw)
    except ValidationError as ve:
        return _fail("Invalid actuator payload", 400, details={"errors": ve.errors()})

    unit_id = body.unit_id

    growth_service = _growth_service()
    if not growth_service.get_unit(unit_id):
        return _fail(f"Growth unit {unit_id} not found", 404)

    actuator_svc = _actuator_service()
    config = {}
    if body.gpio_pin is not None:
        config["gpio_pin"] = body.gpio_pin

    actuator_id = actuator_svc.create_actuator(
        unit_id=unit_id,
        name=body.name,
        actuator_type=body.type.value,
        protocol=body.communication_type.value,
        model="Generic",
        config=config,
        register_runtime=True,
    )

    if not actuator_id:
        return _fail("Failed to create actuator", 500)

    return _success(
        {
            "actuator_id": actuator_id,
            "message": f"Actuator '{body.name}' created successfully",
        },
        201,
    )


@devices_api.delete("/v2/actuators/<int:actuator_id>")
@safe_route("Failed to remove actuator")
def remove_actuator(actuator_id: int) -> Response:
    """
    Remove an actuator.

    Query params:
        remove_from_zigbee: If true, also remove from Zigbee network (default: false)
    """
    from flask import request

    remove_from_zigbee = request.args.get("remove_from_zigbee", "false").lower() == "true"
    actuator_svc = _actuator_service()
    actuator_svc.delete_actuator(actuator_id, remove_from_zigbee=remove_from_zigbee)
    return _success({"actuator_id": actuator_id, "message": "Actuator removed"})


# ======================== DEVICE OPERATIONS ========================


@devices_api.post("/v2/actuators/<int:actuator_id>/identify")
@safe_route("Failed to identify actuator")
def identify_actuator(actuator_id: int) -> Response:
    """
    Trigger identification on an actuator (e.g., flash LED).

    Works with Zigbee2MQTT and other actuators that support identification.

    Query params:
        duration: int - Duration in seconds (default: 10)

    Returns:
        {
            "actuator_id": 42,
            "success": true,
            "message": "Identification triggered"
        }
    """
    duration = request.args.get("duration", 10, type=int)

    actuator_svc = _actuator_service()
    success = actuator_svc.identify_actuator(actuator_id, duration)

    if success:
        return _success(
            {"actuator_id": actuator_id, "success": True, "message": f"Identification triggered for {duration}s"}
        )
    else:
        return _fail(f"Actuator {actuator_id} does not support identification", 400)


@devices_api.get("/v2/actuators/<int:actuator_id>/device-info")
@safe_route("Failed to get actuator device info")
def get_actuator_device_info(actuator_id: int) -> Response:
    """
    Get device information for an actuator.

    Returns hardware-level information including capabilities,
    protocol details, and network information.

    Returns:
        {
            "actuator_id": 42,
            "device_name": "smart_plug_1",
            "zigbee_id": "0x00124b001234abcd",
            "protocol": "Zigbee2MQTT",
            "available": true,
            ...
        }
    """
    actuator_svc = _actuator_service()
    info = actuator_svc.get_actuator_device_info(actuator_id)

    if info:
        return _success(info)
    else:
        return _fail(f"Actuator {actuator_id} not found or has no device info", 404)


@devices_api.post("/v2/actuators/<int:actuator_id>/rename")
@safe_route("Failed to rename actuator device")
def rename_actuator_device(actuator_id: int) -> Response:
    """
    Rename actuator device on its network (e.g., Zigbee2MQTT).

    This renames the device at the network level. The database name
    should be updated separately using the update actuator endpoint.

    Request body:
        {
            "new_name": "kitchen_plug"
        }

    Returns:
        {
            "actuator_id": 42,
            "success": true,
            "message": "Device renamed on network"
        }
    """
    data = request.get_json() if request.is_json else {}
    new_name = data.get("new_name")

    if not new_name:
        return _fail("new_name is required", 400)

    # Validate name
    if not new_name.replace("_", "").replace("-", "").isalnum():
        return _fail("Device name can only contain letters, numbers, underscores and hyphens", 400)

    actuator_svc = _actuator_service()
    success = actuator_svc.rename_actuator_device(actuator_id, new_name)

    if success:
        return _success(
            {
                "actuator_id": actuator_id,
                "new_name": new_name,
                "success": True,
                "message": "Device renamed on network",
            }
        )
    else:
        return _fail(f"Actuator {actuator_id} does not support rename", 400)


@devices_api.post("/v2/actuators/<int:actuator_id>/remove-from-network")
@safe_route("Failed to remove actuator from network")
def remove_actuator_from_network(actuator_id: int) -> Response:
    """
    Remove actuator device from its network (e.g., Zigbee network).

    This removes the device from the network level. The device will
    need to be re-paired to rejoin the network. This does NOT delete
    the actuator from the database.

    Returns:
        {
            "actuator_id": 42,
            "success": true,
            "message": "Device removal initiated"
        }
    """
    actuator_svc = _actuator_service()
    success = actuator_svc.remove_actuator_from_network(actuator_id)

    if success:
        return _success({"actuator_id": actuator_id, "success": True, "message": "Device removal initiated"})
    else:
        return _fail(f"Actuator {actuator_id} does not support network removal", 400)


@devices_api.post("/v2/actuators/<int:actuator_id>/command")
@safe_route("Failed to send actuator command")
def send_actuator_command(actuator_id: int) -> Response:
    """
    Send a command to an actuator device.

    This is a unified endpoint for sending protocol-specific commands
    to actuators. The adapter handles command translation.

    Supported commands vary by adapter:
        - Zigbee2MQTT: state (on/off/toggle), brightness, color, identify
        - GPIO: state (on/off)

    Request body:
        {
            "state": "on",           // Turn on/off/toggle
            "brightness": 255,       // Set brightness (0-255)
            "identify": 10,          // Flash LED for N seconds
            ...                      // Other protocol-specific params
        }

    Returns:
        {
            "actuator_id": 42,
            "success": true,
            "message": "Command sent successfully"
        }
    """
    from flask import request

    data = request.get_json() if request.is_json else {}

    if not data:
        return _fail("Request body is required", 400)

    actuator_svc = _actuator_service()
    success = actuator_svc.send_command(actuator_id, data)

    if success:
        return _success({"actuator_id": actuator_id, "success": True, "message": "Command sent successfully"})
    else:
        return _fail(f"Actuator {actuator_id} does not support commands", 400)
