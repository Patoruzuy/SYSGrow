"""app.socketio.sensor_handlers

Socket.IO namespace handlers used by the web UI.

Only the following namespaces are supported:
- /dashboard
- /devices
- /notifications
- /session
- /alerts
- /system

Note: Real-time sensor broadcasting is handled by MQTTSensorService via
EmitterService; these handlers focus on room membership and lifecycle.
"""
import logging

from flask import request, session
from flask_socketio import join_room, leave_room

from app.extensions import socketio
from app.utils.emitters import (
    SOCKETIO_NAMESPACE_ALERTS,
    SOCKETIO_NAMESPACE_DASHBOARD,
    SOCKETIO_NAMESPACE_DEVICES,
    SOCKETIO_NAMESPACE_NOTIFICATIONS,
    SOCKETIO_NAMESPACE_SESSION,
    SOCKETIO_NAMESPACE_SYSTEM,
)

logger = logging.getLogger(__name__)

def _auto_join_unit_room(namespace_label: str) -> None:
    """Best-effort auto-join the unit room based on session.selected_unit."""
    try:
        selected_unit = session.get("selected_unit")
        if selected_unit is None:
            logger.info(
                f"⚠️  Client {request.sid} connected to {namespace_label} with no selected_unit in session"
            )
            return

        unit_id = int(selected_unit)
        join_room(f"unit_{unit_id}")
        logger.info(f"✅ Client {request.sid} auto-joined room unit_{unit_id} ({namespace_label})")
    except Exception as e:
        logger.warning(f"Failed to auto-join unit room for client {request.sid} ({namespace_label}): {e}")


def _join_unit_from_payload(data) -> None:
    """Explicitly join a unit room (best-effort), respecting session as source of truth."""
    try:
        unit_id = data.get("unit_id") if isinstance(data, dict) else None
        if unit_id is None:
            logger.warning(f"Client {request.sid} sent join_unit without unit_id")
            return

        unit_id = int(unit_id)

        selected_unit = session.get("selected_unit")
        if selected_unit is not None:
            try:
                selected_unit_id = int(selected_unit)
                if selected_unit_id != unit_id:
                    logger.warning(
                        f"Client {request.sid} requested join_unit={unit_id} but session selected_unit={selected_unit_id}; ignoring"
                    )
                    return
            except Exception:
                logger.warning(
                    f"Client {request.sid} has invalid session selected_unit={selected_unit}; allowing join_unit={unit_id}"
                )

        join_room(f"unit_{unit_id}")
        logger.info(f"✅ Client {request.sid} joined room unit_{unit_id}")
    except Exception as e:
        logger.error(f"Error joining unit room: {e}", exc_info=True)


def _leave_unit_from_payload(data) -> None:
    """Best-effort leave a unit room to avoid receiving cross-unit updates."""
    try:
        unit_id = data.get("unit_id") if isinstance(data, dict) else None
        if unit_id is None:
            logger.warning(f"Client {request.sid} sent leave_unit without unit_id")
            return

        unit_id = int(unit_id)
        leave_room(f"unit_{unit_id}")
        logger.info(f"✅ Client {request.sid} left room unit_{unit_id}")
    except Exception as e:
        logger.error(f"Error leaving unit room: {e}", exc_info=True)


# =====================================
# /dashboard NAMESPACE HANDLERS
# =====================================

@socketio.on('connect', namespace=SOCKETIO_NAMESPACE_DASHBOARD)
def handle_dashboard_connect():
    """Handle client connection to /dashboard namespace"""
    logger.info(f"Client connected to /dashboard namespace: {request.sid}")
    _auto_join_unit_room("/dashboard")


@socketio.on('join_unit', namespace=SOCKETIO_NAMESPACE_DASHBOARD)
def handle_dashboard_join_unit(data):
    _join_unit_from_payload(data)


@socketio.on('leave_unit', namespace=SOCKETIO_NAMESPACE_DASHBOARD)
def handle_dashboard_leave_unit(data):
    _leave_unit_from_payload(data)


@socketio.on('disconnect', namespace=SOCKETIO_NAMESPACE_DASHBOARD)
def handle_dashboard_disconnect():
    """Handle client disconnection from /dashboard namespace"""
    logger.info(f"Client disconnected from /dashboard namespace: {request.sid}")


# =====================================
# /devices NAMESPACE HANDLERS
# =====================================

@socketio.on('connect', namespace=SOCKETIO_NAMESPACE_DEVICES)
def handle_devices_connect():
    """Handle client connection to /devices namespace"""
    logger.info(f"Client connected to /devices namespace: {request.sid}")
    _auto_join_unit_room("/devices")


@socketio.on('join_unit', namespace=SOCKETIO_NAMESPACE_DEVICES)
def handle_devices_join_unit(data):
    _join_unit_from_payload(data)


@socketio.on('leave_unit', namespace=SOCKETIO_NAMESPACE_DEVICES)
def handle_devices_leave_unit(data):
    _leave_unit_from_payload(data)


@socketio.on('disconnect', namespace=SOCKETIO_NAMESPACE_DEVICES)
def handle_devices_disconnect():
    """Handle client disconnection from /devices namespace"""
    logger.info(f"Client disconnected from /devices namespace: {request.sid}")


# =====================================
# /system NAMESPACE HANDLERS
# =====================================


@socketio.on('connect', namespace=SOCKETIO_NAMESPACE_SYSTEM)
def handle_system_connect():
    logger.info(f"Client connected to /system namespace: {request.sid}")
    _auto_join_unit_room("/system")


@socketio.on('join_unit', namespace=SOCKETIO_NAMESPACE_SYSTEM)
def handle_system_join_unit(data):
    _join_unit_from_payload(data)


@socketio.on('leave_unit', namespace=SOCKETIO_NAMESPACE_SYSTEM)
def handle_system_leave_unit(data):
    _leave_unit_from_payload(data)


@socketio.on('disconnect', namespace=SOCKETIO_NAMESPACE_SYSTEM)
def handle_system_disconnect():
    logger.info(f"Client disconnected from /system namespace: {request.sid}")


# =====================================
# /alerts NAMESPACE HANDLERS
# =====================================


@socketio.on('connect', namespace=SOCKETIO_NAMESPACE_ALERTS)
def handle_alerts_connect():
    logger.info(f"Client connected to /alerts namespace: {request.sid}")


@socketio.on('disconnect', namespace=SOCKETIO_NAMESPACE_ALERTS)
def handle_alerts_disconnect():
    logger.info(f"Client disconnected from /alerts namespace: {request.sid}")


# =====================================
# /notifications NAMESPACE HANDLERS
# =====================================


@socketio.on('connect', namespace=SOCKETIO_NAMESPACE_NOTIFICATIONS)
def handle_notifications_connect():
    logger.info(f"Client connected to /notifications namespace: {request.sid}")


@socketio.on('disconnect', namespace=SOCKETIO_NAMESPACE_NOTIFICATIONS)
def handle_notifications_disconnect():
    logger.info(f"Client disconnected from /notifications namespace: {request.sid}")


# =====================================
# /session NAMESPACE HANDLERS
# =====================================


@socketio.on('connect', namespace=SOCKETIO_NAMESPACE_SESSION)
def handle_session_connect():
    logger.info(f"Client connected to /session namespace: {request.sid}")


@socketio.on('disconnect', namespace=SOCKETIO_NAMESPACE_SESSION)
def handle_session_disconnect():
    logger.info(f"Client disconnected from /session namespace: {request.sid}")


# =====================================
# DEFAULT NAMESPACE HANDLERS
# =====================================

@socketio.on('connect')
def handle_connect():
    """Handle client connection to default namespace"""
    logger.debug(f"Client {request.sid} connected to default namespace")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection from default namespace"""
    logger.debug(f"Client {request.sid} disconnected from default namespace")
