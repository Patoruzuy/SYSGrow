"""
WebSocket Emitters
=====================================

Purpose:
    Centralized WebSocket emitter service leveraging Socket.IO Server.

Features:
- Emit to user-specific Socket.IO rooms or broadcast globally.
- Explicit event namespace management.
- Sensor reading emission with processor pipeline support.
- Multi-value sensor support (combo sensors).

Usage:
    Instantiate EmitterService with Server, and aioredis.Redis instances.
    Call emit_to_user(), emit_notification(), emit_session_event(),
    or emit_sensor_reading() to send real-time WebSocket events with replay support.

Author:
    Sebastian Gomez

Created:
    April 2025

Updated:
    December 2025 - Added sensor reading emission support
"""

import logging
from typing import Any, Iterable

from flask_socketio import SocketIO

from app.enums.events import WebSocketEvent
from app.schemas.events import (
    DashboardSnapshotPayload,
    DeviceSensorReadingPayload,
    NotificationPayload,
    UnregisteredSensorPayload,
)
from app.schemas.session import SessionBroadcastSchema

logger = logging.getLogger("emitters")

# WebSocket event names (single source of truth)
WS_EVENT_DEVICE_READING = WebSocketEvent.DEVICE_SENSOR_READING.value
WS_EVENT_DASHBOARD_SNAPSHOT = WebSocketEvent.DASHBOARD_SNAPSHOT.value
WS_EVENT_UNREGISTERED = WebSocketEvent.UNREGISTERED_SENSOR_DATA.value

# Socket.IO Namespace Constants
SOCKETIO_NAMESPACE_DASHBOARD = "/dashboard"
SOCKETIO_NAMESPACE_DEVICES = "/devices"
SOCKETIO_NAMESPACE_NOTIFICATIONS = "/notifications"
SOCKETIO_NAMESPACE_SESSION = "/session"
SOCKETIO_NAMESPACE_ALERTS = "/alerts"
SOCKETIO_NAMESPACE_SYSTEM = "/system"


class EmitterService:
    """
    Centralized WebSocket Emitter Service.

    Attributes:
        sio: The Socket.IO SocketIO instance for emitting events.
    """

    def __init__(
        self,
        sio: SocketIO,
        replay_maxlen: int,
    ):
        self.sio = sio
        self.replay_maxlen = replay_maxlen

    def emit(
        self,
        event: str,
        payload: dict,
        room: str | None = None,
        namespace: str = "/",
    ):
        """
        Emit a Socket.IO event.

        Args:
            event (str): Event name (e.g., "notification").
            payload (dict): JSON serializable data to send.
            room (Optional[str]): Socket.IO room identifier. Broadcasts if None.
            namespace (str): Socket.IO namespace to emit under (default "/").
        """
        try:
            logger.info(f"📡 Emitting event='{event}' to namespace='{namespace}' room='{room or 'broadcast'}'")
            self.sio.emit(event, payload, room=room, namespace=namespace)
            logger.info("   ✓ Emit successful")
        except Exception as e:
            logger.exception(f"[Emitter] Failed to emit event '{event}' to room '{room}': {e}")

    def emit_to_user(
        self,
        user_id: int,
        event: str,
        payload: dict,
        namespace: str = "/",
    ):
        """
        Emit an event to a specific user's room and append it to Redis Stream replay.

        Args:
            user_id (int): Target user ID. Emits to room 'user_<user_id>'.
            event (str): Event name (e.g., "notification").
            payload (dict): JSON serializable payload.
            namespace (str): Socket.IO namespace (default "/").
        """
        room = f"user_{user_id}"
        self.emit(event=event, payload=payload, room=room, namespace=namespace)
        logger.info(f"[Emitter] Event '{event}' emitted to user_{user_id} in namespace='{namespace}'")

    def emit_notification(
        self,
        # Removed unused request: Request
        notification: NotificationPayload,
    ):
        """
        Emit a notification event to a user.

        Args:
            notification (NotificationPayload):
            Validated notification data.
        """
        self.emit_to_user(
            user_id=notification.userId,
            event="notification",
            payload=notification.model_dump(),
            namespace=SOCKETIO_NAMESPACE_NOTIFICATIONS,
        )
        logger.info(f"[Emitter] Notification emitted to user_{notification.userId}")

    def emit_session_event(
        self,
        session: SessionBroadcastSchema,
    ):
        """
        Emit a session-related event (login, logout, revoke, etc.).

        Args:
            session (SessionBroadcastSchema): Validated session data.
        """
        self.emit_to_user(
            user_id=session.userId,
            event=session.event,
            payload=session.model_dump(),
            namespace=SOCKETIO_NAMESPACE_SESSION,
        )

        logger.info(f"[Emitter] Session event emitted to user '{session.userId}'")

    def emit_alert_event(
        self,
        alert: dict,
    ):
        self.emit_to_user(
            user_id=alert.userId,
            event=alert.event,
            payload=alert.model_dump(),
            namespace=SOCKETIO_NAMESPACE_ALERTS,
        )
        logger.info(f"[Emitter] Alert event emitted to user '{alert.userId}'")

    def emit_error(
        self,
        event: str,
        payload: dict,
        room: str | None = None,
        namespace: str = "/",
    ):
        """
        Emit an error event.

        Args:
            event (str): Event name (e.g., "error").
            payload (dict): JSON serializable data to send.
            room (str): Room name.
            namespace (str): Socket.IO namespace (default "/").
        """
        self.emit(
            event=event,
            payload=payload,
            room=room,
            namespace=namespace,
        )
        logger.info(f"[Emitter] Error event emitted to room='{room or 'broadcast'}' namespace='{namespace}'")

    # ---------------------------------------------------------------------
    # Consolidated sensor payload emitters (single source of truth)
    # ---------------------------------------------------------------------

    def emit_device_sensor_reading(self, payload: DeviceSensorReadingPayload) -> None:
        """Emit a per-sensor payload to the Devices namespace."""
        self.emit(
            event=WS_EVENT_DEVICE_READING,
            payload=payload.model_dump(),
            room=f"unit_{payload.unit_id}",
            namespace=SOCKETIO_NAMESPACE_DEVICES,
        )

    def emit_dashboard_snapshot(self, payload: DashboardSnapshotPayload) -> None:
        """Emit an aggregated per-unit snapshot to the Dashboard namespace."""
        self.emit(
            event=WS_EVENT_DASHBOARD_SNAPSHOT,
            payload=payload.model_dump(),
            room=f"unit_{payload.unit_id}",
            namespace=SOCKETIO_NAMESPACE_DASHBOARD,
        )

    def emit_unregistered_sensor_data(self, payload: UnregisteredSensorPayload) -> None:
        """Emit unregistered sensor payload to the Devices namespace."""
        room = f"unit_{payload.unit_id}" if getattr(payload, "unit_id", None) else None
        self.emit(
            event=WS_EVENT_UNREGISTERED,
            payload=payload.model_dump(),
            room=room,
            namespace=SOCKETIO_NAMESPACE_DEVICES,
        )

    def emit_sensor_reading(
        self,
        sensor_id: int,
        reading: Any,  # SensorReading object
        namespace: str = SOCKETIO_NAMESPACE_DEVICES,
        *,
        allowed_types: Iterable[str] | None = None,
        readings_override: dict[str, Any] | None = None,
    ):
        """
        Emit sensor reading to WebSocket clients.

        Args:
            sensor_id: Sensor ID
            reading: SensorReading object from processor pipeline
            namespace: SocketIO namespace ("/devices", "/dashboard")

        Emits:
            - Single-value sensors: traditional format
            - Multi-value sensors: expanded format with all readings
        """
        try:
            logger.info(f"🎯 EmitterService.emit_sensor_reading: sensor_id={sensor_id} namespace={namespace}")
            raw_readings = (
                readings_override if isinstance(readings_override, dict) else (getattr(reading, "data", None) or {})
            )
            logger.info(f"   Raw readings: {list(raw_readings.keys())}")
            numeric_readings = self._coerce_numeric_readings(raw_readings)
            logger.info(f"   Numeric readings: {list(numeric_readings.keys())}")

            if allowed_types is not None:
                allowed = set(str(x) for x in allowed_types)
                numeric_readings = {k: v for k, v in numeric_readings.items() if k in allowed}

            if not numeric_readings:
                logger.warning(
                    "[Emitter] No numeric readings to emit: sensor_id=%s unit_id=%s keys=%s",
                    sensor_id,
                    getattr(reading, "unit_id", None),
                    list(raw_readings.keys()),
                )
                return

            # Normalize status
            status_obj = getattr(reading, "status", "success")
            status_raw = getattr(status_obj, "value", status_obj)
            status = str(status_raw).strip().lower()
            if status not in {"success", "warning", "error", "mock"}:
                status = "success"

            # Power/connectivity
            battery = raw_readings.get("battery")
            linkquality = raw_readings.get("linkquality")
            try:
                battery_i = int(float(battery)) if battery is not None else None
            except Exception:
                battery_i = None
            try:
                linkquality_i = int(float(linkquality)) if linkquality is not None else None
            except Exception:
                linkquality_i = None
            power_source = "battery" if battery_i is not None else "mains"

            # Convert reading to consolidated device payload
            ts = getattr(reading, "timestamp", None)
            timestamp = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")
            payload = DeviceSensorReadingPayload(
                schema_version=1,
                sensor_id=int(sensor_id),
                unit_id=int(getattr(reading, "unit_id", 0) or 0),
                sensor_name=str(getattr(reading, "sensor_name", "") or "") or None,
                sensor_type=str(getattr(reading, "sensor_type", "") or "") or None,
                readings=numeric_readings,
                units=self._get_units_for_readings(numeric_readings),
                status=status,  # type: ignore[arg-type]
                timestamp=timestamp,
                battery=battery_i,
                power_source=power_source,  # type: ignore[arg-type]
                linkquality=linkquality_i,
                quality_score=getattr(reading, "quality_score", None),
                is_anomaly=bool(getattr(reading, "is_anomaly", False)),
                anomaly_reason=getattr(reading, "anomaly_reason", None),
                calibration_applied=bool(getattr(reading, "calibration_applied", False)),
            )

            logger.info(f"   📦 Payload created: {payload.model_dump()}")

            # Emit ONE consolidated event per call
            logger.info(
                f"   📤 Emitting consolidated '{WS_EVENT_DEVICE_READING}' to namespace={namespace} room=unit_{payload.unit_id}"
            )
            self.emit(
                event=WS_EVENT_DEVICE_READING,
                payload=payload.model_dump(),
                room=f"unit_{payload.unit_id}",
                namespace=namespace,
            )
            logger.info("   ✅ Emitted consolidated device_sensor_reading event")

            logger.debug(
                f"[Emitter] Sensor reading emitted: sensor_id={sensor_id}, "
                f"unit_id={reading.unit_id}, readings={list(numeric_readings.keys())}, "
                f"namespace='{namespace}'"
            )
        except Exception as e:
            logger.exception(f"[Emitter] Failed to emit sensor reading for sensor {sensor_id}: {e}")

    def _coerce_numeric_readings(self, readings: dict[str, Any]) -> dict[str, float]:
        """Filter/coerce raw reading values to numeric types for websocket payloads."""
        result: dict[str, float] = {}
        for key, value in (readings or {}).items():
            if value is None:
                continue
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                result[key] = float(value)
                continue
            if isinstance(value, str):
                try:
                    result[key] = float(value)
                except ValueError:
                    continue

        return result

    def _get_units_for_readings(self, readings: dict[str, Any]) -> dict[str, str]:
        """
        Get units for each reading type.

        Args:
            readings: Sensor readings dict

        Returns:
            Dictionary mapping reading type to unit string
        """
        from app.hardware.sensors.processors.utils import UNIT_MAP

        return {k: UNIT_MAP.get(k, "") for k in (readings or {}).keys()}

    def ping(self):
        """
        Redis service health check.
        """
        return self.redis.ping()
