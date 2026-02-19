"""
DHT11 Sensor Implementation

Temperature and humidity sensor.

Features:
- Temperature measurement (0-50°C, ±2°C accuracy)
- Humidity measurement (20-90%, ±5% accuracy)
- GPIO communication
- Retry logic for reliability
"""

import logging
from typing import Any

from ..base_adapter import AdapterError, BaseSensorAdapter

logger = logging.getLogger(__name__)


class DHT11Adapter(BaseSensorAdapter):
    """
    Specialized adapter for DHT11 temperature/humidity sensor.

    Features:
    - Temperature measurement (0-50°C, ±2°C accuracy)
    - Humidity measurement (20-90%, ±5% accuracy)
    - GPIO communication
    - Retry logic for reliability
    """

    def __init__(self, gpio_pin: int = 4, unit_id: str = "1"):
        """
        Initialize DHT11 adapter.

        Args:
            gpio_pin: GPIO pin number (BCM numbering)
            unit_id: Unit identifier
        """
        self.gpio_pin = gpio_pin
        self.unit_id = unit_id
        self._sensor = None
        self._available = False

        try:
            self._initialize_sensor()
            self._available = True
        except Exception as e:
            logger.error("Failed to initialize DHT11: %s", e)
            self._available = False

    def _initialize_sensor(self):
        """Initialize the sensor hardware"""
        from app.hardware.sensors.drivers.dht11_sensor import DHT11Sensor

        self._sensor = DHT11Sensor(pin=self.gpio_pin, unit_id=self.unit_id)

    def read(self) -> dict[str, Any]:
        """
        Read from DHT11 sensor.

        Returns:
            Dict with keys:
            - temperature: Temperature (°C)
            - humidity: Relative humidity (%)
            - status: Sensor status
            - timestamp: ISO timestamp

        Raises:
            AdapterError: If read fails
        """
        if not self._sensor:
            raise AdapterError("DHT11 sensor not initialized")

        try:
            # DHT11 can be unreliable, use retries
            data = self._sensor.read(retries=3, delay=2)

            # Validate data
            if data.get("temperature") is None or data.get("humidity") is None:
                raise AdapterError("DHT11 returned null values")

            return data

        except Exception as e:
            logger.error("DHT11 read error: %s", e)
            raise AdapterError(f"Failed to read DHT11: {e}") from e

    def configure(self, config: dict[str, Any]) -> None:
        """
        Configure the sensor.

        Args:
            config: Configuration parameters
                - gpio_pin: GPIO pin number
                - unit_id: Unit identifier
        """
        if "gpio_pin" in config:
            self.gpio_pin = config["gpio_pin"]

        if "unit_id" in config:
            self.unit_id = config["unit_id"]

        # Reinitialize if requested
        if config.get("reinitialize", False):
            try:
                self._initialize_sensor()
                self._available = True
            except Exception as e:
                logger.error("Failed to reconfigure DHT11: %s", e)
                self._available = False
                raise AdapterError(f"Configuration failed: {e}") from e

    def is_available(self) -> bool:
        """Check if sensor is available"""
        return self._available and self._sensor is not None

    def get_protocol_name(self) -> str:
        """Get protocol name"""
        return "GPIO"

    def cleanup(self) -> None:
        """Cleanup resources"""
        if self._sensor and hasattr(self._sensor, "cleanup"):
            try:
                self._sensor.cleanup()
            except Exception as e:
                logger.warning("Error during DHT11 cleanup: %s", e)
