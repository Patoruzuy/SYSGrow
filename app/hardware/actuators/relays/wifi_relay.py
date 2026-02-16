import logging
import os
from logging.handlers import RotatingFileHandler

import requests

from app.enums.events import DeviceEvent
from app.schemas.events import ConnectivityStatePayload, RelayStatePayload
from app.utils.time import iso_now

from .relay_base import RelayBase

# Module-level logger with rotation (prevents unbounded log file growth)
logger = logging.getLogger(__name__)
if not logger.handlers:
    os.makedirs("logs", exist_ok=True)
    _handler = RotatingFileHandler(
        "logs/devices.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding="utf-8",
    )
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't duplicate to root logger


class WiFiRelay(RelayBase):
    """
    Controls a relay via an HTTP API (e.g., ESP8266 or ESP-01).

    Attributes:
        device (str): The name of the controlled device.
        ip (str): The IP address of the relay module.

    Methods:
        turn_on(): Sends an HTTP request to turn on the relay.
        turn_off(): Sends an HTTP request to turn off the relay.
    """

    def __init__(self, device: str, ip: str):
        """
        Initializes the WiFi relay with an IP address.

        Args:
            device (str): The name of the device.
            ip (str): The IP address of the relay module.
        """
        super().__init__(device)
        self.ip = ip

    def turn_on(self):
        """Sends an HTTP request to turn on the relay."""
        try:
            self._send_request("on")
            self.event_bus.publish(
                DeviceEvent.RELAY_STATE_CHANGED,
                RelayStatePayload(device=self.device, state="on"),
            )  # Publish Event
            logger.info(f"Turned on WiFi relay for {self.device} at {self.ip}")
        except Exception as e:
            logger.error(f"Error turning on WiFi relay {self.device}: {e}")

    def turn_off(self):
        """Sends an HTTP request to turn off the relay."""
        try:
            self._send_request("off")
            self.event_bus.publish(
                DeviceEvent.RELAY_STATE_CHANGED,
                RelayStatePayload(device=self.device, state="off"),
            )  # Publish Event
            logger.info(f"Turned off WiFi relay for {self.device} at {self.ip}")
        except Exception as e:
            logger.error(f"Error turning off WiFi relay {self.device}: {e}")

    def _send_request(self, state: str):
        """
        Sends an HTTP request to the relay module.

        Args:
            state (str): The relay state ('on' or 'off').
        """
        url = f"http://{self.ip}/relay/{state}"
        try:
            response = requests.get(url, timeout=5)  # Added timeout
            response.raise_for_status()
            # Emit connectivity success event for WiFi reachability
            try:
                self.event_bus.publish(
                    DeviceEvent.CONNECTIVITY_CHANGED,
                    ConnectivityStatePayload(
                        connection_type="wifi",
                        status="connected",
                        endpoint=self.ip,
                        device_id=self.device,
                        timestamp=iso_now(),
                    ),
                )
            except Exception:
                pass
        except requests.exceptions.RequestException as e:
            # Emit connectivity failure event for WiFi reachability
            try:
                self.event_bus.publish(
                    DeviceEvent.CONNECTIVITY_CHANGED,
                    ConnectivityStatePayload(
                        connection_type="wifi",
                        status="disconnected",
                        endpoint=self.ip,
                        device_id=self.device,
                        timestamp=iso_now(),
                        details={"error": str(e)},
                    ),
                )
            except Exception:
                pass
            raise Exception(f"Error controlling relay at {url}: {e}") from e
