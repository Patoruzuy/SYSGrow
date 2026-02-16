"""
BME280 Weather Sensor Implementation

Temperature, humidity, and pressure sensor.

Features:
- Temperature measurement (-40°C to 85°C, ±1°C accuracy)
- Humidity measurement (0-100%, ±3% accuracy)
- Pressure measurement (300-1100 hPa, ±1 hPa accuracy)
- Altitude calculation
- I2C communication
"""

import logging
from typing import Any

from ..base_adapter import AdapterError, BaseSensorAdapter

logger = logging.getLogger(__name__)


class BME280Adapter(BaseSensorAdapter):
    """
    Specialized adapter for BME280 weather sensor.

    Features:
    - Temperature measurement (-40°C to 85°C, ±1°C accuracy)
    - Humidity measurement (0-100%, ±3% accuracy)
    - Pressure measurement (300-1100 hPa, ±1 hPa accuracy)
    - Altitude calculation
    - I2C communication
    """

    def __init__(self, unit_id: str = "1", i2c_bus: int = 1):
        """
        Initialize BME280 adapter.

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
            logger.error(f"Failed to initialize BME280: {e}")
            self._available = False

    def _initialize_sensor(self):
        """Initialize the sensor hardware"""
        from app.hardware.sensors.drivers.temp_humidity_sensor import BME280Sensor

        self._sensor = BME280Sensor(unit_id=self.unit_id)

    def read(self) -> dict[str, Any]:
        """
        Read from BME280 sensor.

        Returns:
            Dict with keys:
            - temperature: Temperature (°C)
            - humidity: Relative humidity (%)
            - pressure: Atmospheric pressure (hPa)
            - altitude: Altitude (m) - optional
            - status: Sensor status
            - timestamp: ISO timestamp

        Raises:
            AdapterError: If read fails
        """
        if not self._sensor:
            raise AdapterError("BME280 sensor not initialized")

        try:
            data = self._sensor.read(include_altitude=False)

            # Validate data
            if "error" in data:
                raise AdapterError(f"Sensor error: {data['error']}")

            # Ensure all expected fields are present
            required_fields = ["temperature", "humidity", "pressure"]
            for field in required_fields:
                if field not in data:
                    logger.warning(f"Missing field '{field}' in BME280 reading")

            return data

        except Exception as e:
            logger.error(f"BME280 read error: {e}")
            raise AdapterError(f"Failed to read BME280: {e}")

    def configure(self, config: dict[str, Any]) -> None:
        """
        Configure the sensor.

        Args:
            config: Configuration parameters
                - unit_id: Unit identifier
                - i2c_bus: I2C bus number
                - sea_level_pressure: Sea level pressure for altitude calc (hPa)
        """
        if "unit_id" in config:
            self.unit_id = config["unit_id"]

        if "i2c_bus" in config:
            self.i2c_bus = config["i2c_bus"]

        # Set sea level pressure if provided
        if "sea_level_pressure" in config and self._sensor:
            try:
                self._sensor.set_sea_level_pressure(config["sea_level_pressure"])
            except Exception as e:
                logger.warning(f"Failed to set sea level pressure: {e}")

        # Reinitialize if requested
        if config.get("reinitialize", False):
            try:
                self._initialize_sensor()
                self._available = True
            except Exception as e:
                logger.error(f"Failed to reconfigure BME280: {e}")
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
                logger.warning(f"Error during BME280 cleanup: {e}")
