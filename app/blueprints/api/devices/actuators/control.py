"""
Actuator Control Operations
Handles actuator state control, toggling, and state history management.
"""

import logging

from flask import Response, request

from app.security.auth import api_login_required

from app.utils.http import safe_error

from ...devices import devices_api
from ..utils import (
    _actuator_service,
    _device_repo,
    _fail,
    _success,
    _to_csv,
)

logger = logging.getLogger(__name__)

# ======================== ACTUATOR CONTROL ========================


@devices_api.post("/actuators/<int:actuator_id>/toggle")
@api_login_required
def toggle_actuator(actuator_id: int):
    """Toggle actuator state ON/OFF"""
    try:
        actuator_svc = _actuator_service()
        actuator = actuator_svc.get_actuator(actuator_id)
        if actuator is None:
            return _fail(f"Actuator {actuator_id} not found", 404)

        current_state_bool = actuator_svc.get_actuator_state(actuator_id)
        if current_state_bool is None:
            return _fail(f"State not available for actuator {actuator_id}", 503)

        new_state_bool = not current_state_bool
        success = actuator_svc.set_actuator_state(actuator_id, new_state_bool)
        if not success:
            return _fail(f"Failed to set actuator {actuator_id} state", 500)

        current_state = "ON" if current_state_bool else "OFF"
        new_state = "ON" if new_state_bool else "OFF"

        return _success(
            {
                "actuator_id": actuator_id,
                "previous_state": current_state,
                "new_state": new_state,
                "message": f"Actuator {actuator_id} toggled to {new_state}",
            }
        )

    except Exception as e:
        return safe_error(e, 500)


@devices_api.post("/control_actuator")
@api_login_required
def control_actuator_by_type():
    """
    Control all actuators of a specific type.

    Request body:
        {
            "actuator_type": "pump",
            "action": "activate" | "deactivate"
        }
    """
    try:
        data = request.get_json() if request.is_json else {}
        actuator_type = data.get("actuator_type")
        action = data.get("action")

        if not actuator_type or not action:
            return _fail("actuator_type and action are required", 400)

        target_state = action == "activate"

        actuator_svc = _actuator_service()
        actuators = actuator_svc.list_actuators()

        # Filter by type (case-insensitive)
        target_actuators = [a for a in actuators if str(a.get("actuator_type", "")).lower() == actuator_type.lower()]

        if not target_actuators:
            return _fail(f"No actuators found of type {actuator_type}", 404)

        results = []
        for actuator in target_actuators:
            actuator_id = actuator.get("actuator_id")
            if actuator_id:
                try:
                    actuator_svc.set_actuator_state(int(actuator_id), bool(target_state))
                    results.append({"id": actuator_id, "status": "success"})
                except Exception as e:
                    results.append({"id": actuator_id, "status": "error", "error": str(e)})

        return _success({"message": f"Processed {len(results)} actuators", "results": results})

    except Exception as e:
        return safe_error(e, 500)


# ======================== ACTUATOR STATE HISTORY ========================


@devices_api.get("/actuators/<int:actuator_id>/state-history")
def get_actuator_state_history(actuator_id: int):
    """Get recent actuator state history by actuator_id."""
    try:
        limit = request.args.get("limit", default=100, type=int)
        since = request.args.get("since")
        until = request.args.get("until")
        device_repo = _device_repo()
        rows = device_repo.get_actuator_state_history(
            actuator_id,
            limit=limit,
            since=since,
            until=until,
        )

        actuator_svc = _actuator_service()
        meta = actuator_svc.get_actuator(actuator_id) or {}
        for r in rows:
            r["name"] = meta.get("name")
            r["unit_id"] = meta.get("unit_id")

        return _success({"actuator_id": actuator_id, "history": rows, "count": len(rows)})
    except Exception as e:
        return safe_error(e, 500)


@devices_api.get("/units/<int:unit_id>/actuators/state-history")
def get_unit_actuator_state_history(unit_id: int):
    """Get recent actuator state history across all actuators in a unit."""
    try:
        limit = request.args.get("limit", default=100, type=int)
        since = request.args.get("since")
        until = request.args.get("until")
        device_name = request.args.get("device_name")
        device_repo = _device_repo()
        rows = device_repo.get_unit_actuator_state_history(
            unit_id,
            limit=limit,
            since=since,
            until=until,
        )
        if device_name:
            rows = [r for r in rows if str(r.get("name")) == device_name]
        return _success({"unit_id": unit_id, "history": rows, "count": len(rows)})
    except Exception as e:
        return safe_error(e, 500)


@devices_api.get("/actuators/<int:actuator_id>/state-history.csv")
def export_actuator_state_history_csv(actuator_id: int):
    try:
        limit = request.args.get("limit", default=1000, type=int)
        since = request.args.get("since")
        until = request.args.get("until")
        device_repo = _device_repo()
        rows = device_repo.get_actuator_state_history(
            actuator_id,
            limit=limit,
            since=since,
            until=until,
        )

        actuator_svc = _actuator_service()
        meta = actuator_svc.get_actuator(actuator_id) or {}
        for r in rows:
            r["name"] = meta.get("name")
            r["unit_id"] = meta.get("unit_id")

        headers = ["timestamp", "actuator_id", "name", "unit_id", "state", "value"]
        csv_data = _to_csv(rows, headers)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=actuator_{actuator_id}_state_history.csv"},
        )
    except Exception as e:
        return safe_error(e, 500)


@devices_api.get("/units/<int:unit_id>/actuators/state-history.csv")
def export_unit_actuator_state_history_csv(unit_id: int):
    try:
        limit = request.args.get("limit", default=1000, type=int)
        since = request.args.get("since")
        until = request.args.get("until")
        device_name = request.args.get("device_name")
        device_repo = _device_repo()
        rows = device_repo.get_unit_actuator_state_history(
            unit_id,
            limit=limit,
            since=since,
            until=until,
        )
        if device_name:
            rows = [r for r in rows if str(r.get("name")) == device_name]
        headers = ["timestamp", "actuator_id", "name", "unit_id", "state", "value"]
        csv_data = _to_csv(rows, headers)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=unit_{unit_id}_actuator_state_history.csv"},
        )
    except Exception as e:
        return safe_error(e, 500)


@devices_api.post("/actuators/state-history/prune")
@api_login_required
def prune_actuator_state_history():
    """Prune actuator state history older than N days. Body: {days: int}."""
    try:
        data = request.get_json(silent=True) or {}
        days = int(data.get("days", 30))
        if days < 1 or days > 3650:
            return _fail("days must be between 1 and 3650", 400)
        device_repo = _device_repo()
        deleted = device_repo.prune_actuator_state_history(days)
        return _success({"deleted": deleted, "days": days})
    except Exception as e:
        return safe_error(e, 500)
