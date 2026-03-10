"""
WiFi Sensor Adapter
===================

Passive adapter for ESP32 sensors communicating via direct WiFi HTTP.

This adapter receives data pushed from an external service (WiFiSensorService)
and implements the ISensorAdapter interface for consistent hardware abstraction.

Features:
    - Passive data reception (no active polling in adapter)
    - Staleness detection via configurable timeout
    - HTTP command sending to device
    - mDNS-compatible device addressing

Author: SYSGrow Team
Version: 1.0.0
"""

import logging
from datetime import datetime
from typing import Any

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

from .base_adapter import AdapterError, ISensorAdapter

logger = logging.getLogger(__name__)


class WiFiAdapter(ISensorAdapter):
    """
    Passive adapter for ESP32 sensors via direct WiFi HTTP.

    Data is pushed to this adapter via update_data() from a WiFi sensor service.
    The adapter caches the data and implements ISensorAdapter interface.

    Features:
        - Passive data reception (no active polling)
        - Staleness detection via timeout
        - Command sending via HTTP POST to device
        - Configurable HTTP port and timeout
    """

    # Default HTTP settings
    DEFAULT_HTTP_PORT = 80
    DEFAULT_TIMEOUT = 120  # seconds
    DEFAULT_HTTP_TIMEOUT = 5  # seconds for HTTP requests

    def __init__(
        self,
        sensor_id: int,
        ip_address: str,
        unit_id: int = 0,
        http_port: int = DEFAULT_HTTP_PORT,
        timeout: int = DEFAULT_TIMEOUT,
        http_timeout: int = DEFAULT_HTTP_TIMEOUT,
        primary_metrics: list[str] | None = None,
    ):
        """
        Initialize WiFi sensor adapter.

        Args:
            sensor_id: Unique sensor ID in database
            ip_address: Device IP address or mDNS hostname
            unit_id: Associated growth unit ID
            http_port: HTTP server port on device (default: 80)
            timeout: Data staleness timeout in seconds (default: 120)
            http_timeout: HTTP request timeout in seconds (default: 5)
            primary_metrics: Optional list of primary metrics for this sensor
        """
        self.sensor_id = sensor_id
        self.ip_address = ip_address
        self.unit_id = unit_id
        self.http_port = http_port
        self.timeout = timeout
        self.http_timeout = http_timeout

        # Cached data
        self._last_data: dict[str, Any] | None = None
        self._last_update: datetime | None = None

        logger.info("WiFi adapter initialized for sensor %d at %s:%d", sensor_id, ip_address, http_port)

    # =========================================================================
    # ISensorAdapter Implementation
    # =========================================================================

    def read(self) -> dict[str, Any]:
        """
        Read cached sensor data.

        Returns:
            Dict with sensor readings

        Raises:
            AdapterError: If no recent data available
        """
        if self._last_data is None:
            raise AdapterError(f"No data received from WiFi device at {self.ip_address}")

        # Check if data is stale
        if self._last_update:
            age = (datetime.now() - self._last_update).total_seconds()
            if age > self.timeout:
                raise AdapterError(f"WiFi data stale (age: {age:.1f}s, timeout: {self.timeout}s)")

        return self._last_data.copy()

    def configure(self, config: dict[str, Any]) -> None:
        """
        Reconfigure WiFi adapter.

        Args:
            config: Configuration dictionary with optional keys:
                - ip_address: New device IP address
                - http_port: New HTTP port
                - timeout: New data staleness timeout
                - http_timeout: New HTTP request timeout
        """
        if "ip_address" in config:
            self.ip_address = config["ip_address"]
            logger.info("WiFi adapter IP changed to: %s", self.ip_address)

        if "http_port" in config:
            self.http_port = int(config["http_port"])

        if "timeout" in config:
            self.timeout = int(config["timeout"])

        if "http_timeout" in config:
            self.http_timeout = int(config["http_timeout"])

    def is_available(self) -> bool:
        """
        Check if WiFi sensor is available.

        Returns:
            True if data is recent (within timeout)
        """
        if self._last_data is None or self._last_update is None:
            return False

        age = (datetime.now() - self._last_update).total_seconds()
        return age <= self.timeout

    def get_protocol_name(self) -> str:
        """Get protocol name."""
        return "WiFi"

    def cleanup(self) -> None:
        """Cleanup adapter resources."""
        self._last_data = None
        self._last_update = None
        logger.info("WiFi adapter cleaned up for %s", self.ip_address)

    # =========================================================================
    # ISensorAdapter Optional Methods (Standard Interface)
    # =========================================================================

    def identify(self, duration: int = 10) -> bool:
        """
        Trigger device identification (e.g., flash LED).

        Args:
            duration: Duration in seconds (default: 10)

        Returns:
            True if command sent successfully
        """
        return self.send_command("/api/identify", {"duration": duration})

    def get_state(self) -> dict[str, Any] | None:
        """
        Get current device state (ISensorAdapter interface).

        Returns:
            State dictionary with availability and readings
        """
        return {
            "ip_address": self.ip_address,
            "available": self.is_available(),
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "data_age_seconds": self.get_data_age(),
            "readings": self._last_data.copy() if self._last_data else None,
        }

    def rename(self, new_name: str) -> bool:
        """
        Rename device on network (ISensorAdapter interface).

        For WiFi devices, this updates the device's friendly name
        via HTTP API.

        Args:
            new_name: New friendly name

        Returns:
            True if rename command sent successfully
        """
        return self.send_command("/api/set", {"friendly_name": new_name})

    def remove_from_network(self) -> bool:
        """
        Remove/factory reset device (ISensorAdapter interface).

        For WiFi devices, this triggers a factory reset via HTTP.

        Returns:
            True if factory reset command sent
        """
        return self.send_command("/api/factory-reset", {"confirm": True})

    # =========================================================================
    # Passive Data Reception
    # =========================================================================

    def update_data(self, data: dict[str, Any]) -> None:
        """
        Update cached sensor data (called by WiFiSensorService).

        This method is called externally when new data arrives from the device.

        Args:
            data: Sensor data dictionary
        """
        self._last_data = data
        self._last_update = datetime.now()
        logger.debug("WiFi adapter received data from %s: %d fields", self.ip_address, len(data))

    def get_last_update(self) -> datetime | None:
        """Get timestamp of last data update."""
        return self._last_update

    def get_data_age(self) -> float | None:
        """
        Get age of cached data in seconds.

        Returns:
            Age in seconds, or None if no data
        """
        if self._last_update is None:
            return None
        return (datetime.now() - self._last_update).total_seconds()

    # =========================================================================
    # HTTP Commands
    # =========================================================================

    def _get_base_url(self) -> str:
        """Get base URL for device HTTP API."""
        return f"http://{self.ip_address}:{self.http_port}"

    def send_command(self, endpoint: str, params: dict[str, Any] | None = None, method: str = "POST") -> bool:
        """
        Send HTTP command to device.

        Args:
            endpoint: API endpoint (e.g., "/api/set")
            params: Optional parameters (sent as JSON body for POST)
            method: HTTP method (default: POST)

        Returns:
            True if command sent successfully
        """
        if not REQUESTS_AVAILABLE:
            logger.error("requests library not available for HTTP commands")
            return False

        url = f"{self._get_base_url()}{endpoint}"

        try:
            if method.upper() == "POST":
                response = requests.post(url, json=params or {}, timeout=self.http_timeout)
            else:
                response = requests.get(url, params=params, timeout=self.http_timeout)

            if response.status_code == 200:
                logger.debug("Command sent to %s: %s", self.ip_address, endpoint)
                return True
            else:
                logger.warning("Command failed (%d): %s %s", response.status_code, self.ip_address, endpoint)
                return False

        except requests.exceptions.Timeout:
            logger.warning("HTTP timeout to %s: %s", self.ip_address, endpoint)
            return False
        except requests.exceptions.ConnectionError:
            logger.warning("Connection error to %s: %s", self.ip_address, endpoint)
            return False
        except Exception as e:
            logger.error("HTTP error to %s: %s", self.ip_address, e)
            return False

    def trigger_read(self) -> bool:
        """
        Trigger immediate sensor read on device.

        Returns:
            True if trigger sent successfully
        """
        return self.send_command("/api/get")

    def set_polling_interval(self, interval_ms: int) -> bool:
        """
        Set sensor polling interval.

        Args:
            interval_ms: Polling interval in milliseconds (5000-3600000)

        Returns:
            True if command sent successfully
        """
        interval_ms = max(5000, min(3600000, interval_ms))
        return self.send_command("/api/set", {"polling_interval": interval_ms})

    def set_calibration(self, temperature_offset: float | None = None, humidity_offset: float | None = None) -> bool:
        """
        Set sensor calibration offsets.

        Args:
            temperature_offset: Temperature calibration offset in Celsius
            humidity_offset: Humidity calibration offset in percentage

        Returns:
            True if command sent successfully
        """
        params = {}
        if temperature_offset is not None:
            params["temperature_calibration"] = temperature_offset
        if humidity_offset is not None:
            params["humidity_calibration"] = humidity_offset

        if not params:
            return False

        return self.send_command("/api/set", params)

    def restart_device(self) -> bool:
        """
        Restart the device.

        Returns:
            True if command sent successfully
        """
        return self.send_command("/api/restart", {"restart": True})

    def get_device_info(self) -> dict[str, Any] | None:
        """
        Get device information via HTTP.

        Returns:
            Device info dict, or None on error
        """
        if not REQUESTS_AVAILABLE:
            return None

        url = f"{self._get_base_url()}/api/info"

        try:
            response = requests.get(url, timeout=self.http_timeout)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.debug("Failed to get device info: %s", e)

        return None

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """
        Get adapter status information.

        Returns:
            Status dictionary with availability and timing info
        """
        return {
            "sensor_id": self.sensor_id,
            "ip_address": self.ip_address,
            "http_port": self.http_port,
            "available": self.is_available(),
            "data_age_seconds": self.get_data_age(),
            "timeout": self.timeout,
            "last_update": self._last_update.isoformat() if self._last_update else None,
            "protocol": self.get_protocol_name(),
        }
