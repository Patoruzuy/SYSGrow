"""
MQ2 Smoke/Gas Sensor Implementation

Combustible gas and smoke sensor.

Features:
- Digital mode (threshold detection)
- Analog mode (gas concentration via ADC)
- Detects: LPG, smoke, alcohol, propane, hydrogen, methane, CO
- GPIO or ADS1115 ADC communication
"""

import logging
from typing import Any

from ..base_adapter import AdapterError, BaseSensorAdapter

logger = logging.getLogger(__name__)


class MQ2Adapter(BaseSensorAdapter):
    """
    Specialized adapter for MQ2 smoke/gas sensor.

    Features:
    - Digital mode (threshold detection)
    - Analog mode (gas concentration via ADC)
    - Detects: LPG, smoke, alcohol, propane, hydrogen, methane, CO
    - GPIO or ADS1115 ADC communication
    """

    def __init__(self, gpio_pin: int = 17, is_digital: bool = True, adc_channel: int = 0, unit_id: str = "1"):
        """
        Initialize MQ2 adapter.

        Args:
            gpio_pin: GPIO pin for digital mode
            is_digital: True for digital, False for analog
            adc_channel: ADC channel for analog mode (0-3)
            unit_id: Unit identifier
        """
        self.gpio_pin = gpio_pin
        self.is_digital = is_digital
        self.adc_channel = adc_channel
        self.unit_id = unit_id
        self._sensor = None
        self._available = False

        try:
            self._initialize_sensor()
            self._available = True
        except Exception as e:
            logger.error("Failed to initialize MQ2: %s", e)
            self._available = False

    def _initialize_sensor(self):
        """Initialize the sensor hardware"""
        from app.hardware.sensors.drivers.mq2_sensor import MQ2Sensor

        self._sensor = MQ2Sensor(
            sensor_pin=self.gpio_pin, is_digital=self.is_digital, channel=self.adc_channel, unit_id=self.unit_id
        )

    def read(self) -> dict[str, Any]:
        """
        Read from MQ2 sensor.

        Returns:
            Dict with keys:
            - smoke: Digital (0/1) or analog (ADC value)
            - mode: 'digital' or 'analog'
            - status: Sensor status
            - timestamp: ISO timestamp

        Raises:
            AdapterError: If read fails
        """
        if not self._sensor:
            raise AdapterError("MQ2 sensor not initialized")

        try:
            data = self._sensor.read()

            # Validate data
            if "smoke" not in data:
                raise AdapterError("MQ2 returned no smoke value")

            return data

        except Exception as e:
            logger.error("MQ2 read error: %s", e)
            raise AdapterError(f"Failed to read MQ2: {e}") from e

    def configure(self, config: dict[str, Any]) -> None:
        """
        Configure the sensor.

        Args:
            config: Configuration parameters
                - gpio_pin: GPIO pin number
                - is_digital: Digital or analog mode
                - adc_channel: ADC channel
                - unit_id: Unit identifier
        """
        if "gpio_pin" in config:
            self.gpio_pin = config["gpio_pin"]

        if "is_digital" in config:
            self.is_digital = config["is_digital"]

        if "adc_channel" in config:
            self.adc_channel = config["adc_channel"]

        if "unit_id" in config:
            self.unit_id = config["unit_id"]

        # Reinitialize if requested
        if config.get("reinitialize", False):
            try:
                self._initialize_sensor()
                self._available = True
            except Exception as e:
                logger.error("Failed to reconfigure MQ2: %s", e)
                self._available = False
                raise AdapterError(f"Configuration failed: {e}") from e

    def is_available(self) -> bool:
        """Check if sensor is available"""
        return self._available and self._sensor is not None

    def get_protocol_name(self) -> str:
        """Get protocol name"""
        return "GPIO" if self.is_digital else "ADC"

    def cleanup(self) -> None:
        """Cleanup resources"""
        if self._sensor and hasattr(self._sensor, "cleanup"):
            try:
                self._sensor.cleanup()
            except Exception as e:
                logger.warning("Error during MQ2 cleanup: %s", e)
