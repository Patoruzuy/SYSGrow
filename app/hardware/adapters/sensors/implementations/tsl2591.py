"""
TSL2591 Light Sensor Implementation

High dynamic range light-to-digital converter.

Features:
- Light sensor (lux, full spectrum, IR, visible)
- High dynamic range (0-88,000 lux)
- I2C communication
"""

import logging
from typing import Any

from ..base_adapter import AdapterError, BaseSensorAdapter

logger = logging.getLogger(__name__)


class TSL2591Adapter(BaseSensorAdapter):
    """
    Specialized adapter for TSL2591 light sensor.

    Features:
    - Lux measurement (0-88,000 lux)
    - Full spectrum light
    - Infrared measurement
    - Visible light calculation
    - I2C communication
    """

    def __init__(self, unit_id: str = "1", i2c_bus: int = 1):
        """
        Initialize TSL2591 adapter.

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
            logger.error(f"Failed to initialize TSL2591: {e}")
            self._available = False

    def _initialize_sensor(self):
        """Initialize the sensor hardware"""
        from app.hardware.sensors.drivers.light_sensor import TSL2591Driver

        self._sensor = TSL2591Driver(unit_id=self.unit_id)

    def read(self) -> dict[str, Any]:
        """
        Read from TSL2591 sensor.

        Returns:
            Dict with keys:
            - lux: Light intensity (lux)
            - full_spectrum: Full spectrum reading
            - infrared: IR reading
            - visible: Visible light (full - IR)
            - status: Sensor status
            - timestamp: ISO timestamp

        Raises:
            AdapterError: If read fails
        """
        if not self._sensor:
            raise AdapterError("TSL2591 sensor not initialized")

        try:
            data = self._sensor.read()

            # Validate data
            if "error" in data:
                raise AdapterError(f"Sensor error: {data['error']}")

            # Ensure all expected fields are present
            required_fields = ["lux", "full_spectrum", "infrared", "visible"]
            for field in required_fields:
                if field not in data:
                    logger.warning(f"Missing field '{field}' in TSL2591 reading")

            return data

        except Exception as e:
            logger.error(f"TSL2591 read error: {e}")
            raise AdapterError(f"Failed to read TSL2591: {e}")

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
                logger.error(f"Failed to reconfigure TSL2591: {e}")
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
                logger.warning(f"Error during TSL2591 cleanup: {e}")
