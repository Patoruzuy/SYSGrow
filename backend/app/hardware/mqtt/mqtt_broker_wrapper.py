"""
    This module provides a wrapper class for handling MQTT client functionality.
    It includes methods for connecting, disconnecting, publishing, and subscribing
    to an MQTT broker, with appropriate logging for each operation.

Author: Sebastian Gomez
Date: 11/03/2025
"""

import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Callable

import paho.mqtt.client as mqtt

from app.enums.events import DeviceEvent
from app.hardware.mqtt.client_factory import create_mqtt_client
from app.schemas.events import ConnectivityStatePayload
from app.utils.event_bus import EventBus
from app.utils.time import iso_now, utc_now

# Configure rotating log handler for MQTT operations
# Prevents log file explosion on Raspberry Pi (critical fix)
_mqtt_logger = logging.getLogger("sysgrow.mqtt")
if not _mqtt_logger.handlers:
    os.makedirs("logs", exist_ok=True)
    _mqtt_handler = RotatingFileHandler(
        "logs/devices_mqtt.log",
        maxBytes=10 * 1024 * 1024,  # 10MB max per file
        backupCount=3,  # Keep 3 backup files (40MB total max)
        encoding="utf-8",
    )
    _mqtt_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    _mqtt_logger.addHandler(_mqtt_handler)
    _mqtt_logger.setLevel(logging.INFO)
    _mqtt_logger.propagate = False  # Don't duplicate to root logger

_LOG_MQTT_DISPATCH = os.getenv("SYSGROW_LOG_MQTT_DISPATCH", "").lower() in {"1", "true", "t", "yes", "on"}


@dataclass
class HealthStatus:
    """
    Tracks the health status of the MQTT client connection.
    """

    is_connected: bool = False
    last_error: str | None = None
    last_error_time: datetime | None = None
    connection_attempts: int = 0
    successful_publishes: int = 0
    failed_publishes: int = 0
    active_subscriptions: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate publish success rate percentage"""
        total_publishes = self.successful_publishes + self.failed_publishes
        if total_publishes == 0:
            return 0.0
        return (self.successful_publishes / total_publishes) * 100

    def mark_status(self, connected: bool):
        """Mark the connection status."""
        self.is_connected = connected

    def mark_connected(self):
        """Mark the client as successfully connected."""
        self.is_connected = True
        self.last_error = None
        self.last_error_time = None

    def mark_disconnected(self):
        """Mark the client as disconnected."""
        self.is_connected = False

    def record_error(self, error: Exception):
        """Record a connection or operation error."""
        self.last_error = str(error)
        self.last_error_time = utc_now()

    def increment_connection_attempts(self):
        """Increment the connection attempt counter."""
        self.connection_attempts += 1

    def record_publish_success(self):
        """Record a successful publish operation."""
        self.successful_publishes += 1

    def record_publish_failure(self):
        """Record a failed publish operation."""
        self.failed_publishes += 1

    def set_active_subscriptions(self, count: int):
        """Update the count of active subscriptions."""
        self.active_subscriptions = count

    def to_dict(self):
        """Return health status as a dictionary."""
        return {
            "is_connected": self.is_connected,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None,
            "connection_attempts": self.connection_attempts,
            "successful_publishes": self.successful_publishes,
            "failed_publishes": self.failed_publishes,
            "active_subscriptions": self.active_subscriptions,
            "publish_success_rate": round(self.success_rate, 2),
        }


class MQTTClientWrapper:
    """
    Wrapper class for handling MQTT client functionality.
    """

    def __init__(self, broker, port, client_id=""):
        """
        Initializes the MQTT client wrapper.

        Args:
            broker (str): The MQTT broker address.
            port (int): The MQTT broker port.
            client_id (str, optional): The MQTT client ID. Defaults to "".
        """
        self.broker = broker
        self.port = port
        self.client_id = client_id
        self.client = create_mqtt_client(client_id=client_id)
        self.connected = False
        self.subscribe_count = 0
        self._callback_lock = threading.Lock()
        self._callbacks: list[tuple[str, Callable]] = []
        # Always dispatch through our fan-out handler so multiple subscribers can coexist
        self.client.on_message = self._dispatch_message
        self.event_bus = EventBus()
        self.health_status = HealthStatus()
        self._connect()

    def _connect(self):
        """
        Connects to the MQTT broker.
        """
        try:
            self.client.connect(self.broker, self.port, 60)
            self.connected = True
            self.client.loop_start()  # Start the MQTT loop in a separate thread
            self.health_status.mark_connected()
            _mqtt_logger.info("Connected to MQTT broker %s:%s", self.broker, self.port)
            # Publish connectivity event
            try:
                payload = ConnectivityStatePayload(
                    connection_type="mqtt",
                    status="connected",
                    endpoint=f"{self.broker}:{self.port}",
                    port=self.port,
                    timestamp=iso_now(),
                )
                self.event_bus.publish(DeviceEvent.CONNECTIVITY_CHANGED, payload)
            except Exception as e:
                _mqtt_logger.error("Failed to publish connectivity event: %s", e)
        except Exception as e:
            _mqtt_logger.error("Error connecting to MQTT broker: %s", e)
            self.connected = False
            self.health_status.record_error(e)
            self.health_status.increment_connection_attempts()

    def disconnect(self):
        """
        Disconnects from the MQTT broker.
        """
        if self.connected:
            try:
                self.client.disconnect()
                self.client.loop_stop()
                self.connected = False
                self.health_status.mark_disconnected()
                with self._callback_lock:
                    self._callbacks.clear()
                _mqtt_logger.info("Disconnected from MQTT broker.")
                # Publish connectivity event
                try:
                    payload = ConnectivityStatePayload(
                        connection_type="mqtt",
                        status="disconnected",
                        endpoint=f"{self.broker}:{self.port}",
                        port=self.port,
                        timestamp=iso_now(),
                    )
                    self.event_bus.publish(DeviceEvent.CONNECTIVITY_CHANGED, payload)
                except Exception as e:
                    _mqtt_logger.error("Error publishing connectivity event on disconnect: %s", e, exc_info=True)
            except Exception as e:
                _mqtt_logger.error("Error disconnecting from MQTT broker: %s", e)
                self.health_status.record_error(e)

    def publish(self, topic, payload):
        """
        Publishes a message to the MQTT broker.

        Args:
            topic (str): The MQTT topic to publish to.
            payload (str): The message payload.
        """
        if self.connected:
            try:
                msg_info = self.client.publish(topic, payload)
                if msg_info.rc == mqtt.MQTT_ERR_SUCCESS:
                    self.health_status.record_publish_success()
                    _mqtt_logger.debug("Published to %s: %s", topic, payload)
                else:
                    self.health_status.record_publish_failure()
                    _mqtt_logger.error("Failed to publish to %s: %s. MQTT result code: %s", topic, payload, msg_info.rc)
            except Exception as e:
                self.health_status.record_publish_failure()
                self.health_status.record_error(e)
                _mqtt_logger.error("Error publishing to MQTT: %s", e)
        else:
            _mqtt_logger.warning("MQTT client not connected. Cannot publish.")

    def subscribe(self, topic, callback):
        """
        Subscribes to a topic and sets a callback function.

        Args:
            topic (str): The MQTT topic to subscribe to.
            callback (Callable): The callback function to handle messages.
        """
        if self.connected:
            try:
                result, _mid = self.client.subscribe(topic)
                if result == mqtt.MQTT_ERR_SUCCESS:
                    self._register_callback(topic, callback)
                    self.subscribe_count += 1
                    self.health_status.set_active_subscriptions(self.subscribe_count)
                    _mqtt_logger.info("Subscribed to topic %s with callback %s", topic, callback.__name__)
                    _mqtt_logger.info(
                        "   Total subscriptions: %s, registered callbacks: %s",
                        self.subscribe_count,
                        len(self._callbacks),
                    )
                else:
                    _mqtt_logger.error("Failed to subscribe to topic %s: result code %s", topic, result)
            except Exception as e:
                self.health_status.record_error(e)
                _mqtt_logger.error("Error subscribing to MQTT topic %s: %s", topic, e)
        else:
            _mqtt_logger.warning("MQTT client not connected. Cannot subscribe.")

    def _register_callback(self, topic: str, callback: Callable) -> None:
        """Register a message handler without clobbering existing subscribers."""
        with self._callback_lock:
            self._callbacks.append((topic, callback))

    def _dispatch_message(self, client, userdata, msg) -> None:
        """
        Fan out MQTT messages to all registered callbacks that match the topic
        using MQTT wildcard semantics.
        """
        if _LOG_MQTT_DISPATCH:
            _mqtt_logger.debug(
                "MQTT DISPATCHER: topic=%s payload_len=%s registered_callbacks=%s",
                msg.topic,
                len(msg.payload),
                len(self._callbacks),
            )

        with self._callback_lock:
            callbacks = list(self._callbacks)

        handled = False
        for sub, callback in callbacks:
            try:
                if mqtt.topic_matches_sub(sub, msg.topic):
                    handled = True
                    if _LOG_MQTT_DISPATCH:
                        _mqtt_logger.debug("   Matched subscription '%s' -> calling %s", sub, callback.__name__)
                    callback(client, userdata, msg)
            except Exception as e:
                _mqtt_logger.error("Error in MQTT callback for topic %s: %s", sub, e, exc_info=True)

        if not handled:
            _mqtt_logger.warning(
                "MQTT message on %s had no registered handlers (subscriptions: %s)",
                msg.topic,
                [s[0] for s in callbacks],
            )

    def __del__(self):
        """
        Destructor to ensure disconnection from the MQTT broker.
        """
        # Avoid AttributeError if 'connected' is missing during destruction
        if hasattr(self, "connected") and self.connected:
            self.disconnect()
