"""
ENS160 + AHT21 Sensor Implementation

Features:
- eCO2 measurement (400-65000 ppm)
- TVOC measurement (0-65000 ppb)
- Temperature (-40°C to 85°C)
- Relative humidity (0-100%)
- I2C communication
"""

import logging
from typing import Any

from ..base_adapter import AdapterError, BaseSensorAdapter

logger = logging.getLogger(__name__)


class ENS160AHT21Adapter(BaseSensorAdapter):
    """
    Specialized adapter for ENS160 + AHT21 combo sensor.

    Features:
    - eCO2 measurement (400-65000 ppm)
    - TVOC measurement (0-65000 ppb)
    - Temperature (-40°C to 85°C)
    - Relative humidity (0-100%)
    - I2C communication
    """

    def __init__(self, unit_id: str = "1", i2c_bus: int = 1):
        """
        Initialize ENS160+AHT21 adapter.

        Args:
            unit_id: Unit identifier
            i2c_bus: I2C bus number
        """
        self.unit_id = unit_id
        self.i2c_bus = i2c_bus
        self._sensor = None
        self._available = False

        try:
            self._initialize_sensor()
            self._available = True
        except Exception as e:
            logger.error(f"Failed to initialize ENS160+AHT21: {e}")
            self._available = False

    def _initialize_sensor(self):
        """Initialize the sensor hardware"""
        from app.hardware.sensors.drivers.co2_sensor import ENS160_AHT21Sensor

        self._sensor = ENS160_AHT21Sensor(unit_id=self.unit_id)

    def read(self) -> dict[str, Any]:
        """
        Read from ENS160+AHT21 sensor.

        Returns:
            Dict with keys:
            - eco2: CO2 equivalent (ppm)
            - tvoc: Total VOC (ppb)
            - temperature: Temperature (°C)
            - humidity: Relative humidity (%)
            - status: Sensor status
            - timestamp: ISO timestamp

        Raises:
            AdapterError: If read fails
        """
        if not self._sensor:
            raise AdapterError("ENS160+AHT21 sensor not initialized")

        try:
            data = self._sensor.read()

            # Validate data
            if "error" in data:
                raise AdapterError(f"Sensor error: {data['error']}")

            # Ensure all expected fields are present
            required_fields = ["eco2", "tvoc", "temperature", "humidity"]
            for field in required_fields:
                if field not in data:
                    logger.warning(f"Missing field '{field}' in ENS160+AHT21 reading")

            return data

        except Exception as e:
            logger.error(f"ENS160+AHT21 read error: {e}")
            raise AdapterError(f"Failed to read ENS160+AHT21: {e}")

    def configure(self, config: dict[str, Any]) -> None:
        """
        Configure the sensor.

        Args:
            config: Configuration parameters
        """
        if "unit_id" in config:
            self.unit_id = config["unit_id"]

        if "i2c_bus" in config:
            self.i2c_bus = config["i2c_bus"]

        # Reinitialize if requested
        if config.get("reinitialize", False):
            try:
                self._initialize_sensor()
                self._available = True
            except Exception as e:
                logger.error(f"Failed to reconfigure ENS160+AHT21: {e}")
                self._available = False
                raise AdapterError(f"Configuration failed: {e}")

    def is_available(self) -> bool:
        """Check if sensor is available"""
        return self._available and self._sensor is not None

    def get_protocol_name(self) -> str:
        """Get protocol name"""
        return "I2C"

    def cleanup(self) -> None:
        """Cleanup resources"""
        if self._sensor and hasattr(self._sensor, "cleanup"):
            try:
                self._sensor.cleanup()
            except Exception as e:
                logger.warning(f"Error during ENS160+AHT21 cleanup: {e}")
