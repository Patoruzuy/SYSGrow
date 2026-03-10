"""
Soil Moisture Sensor Implementation

Capacitive soil moisture sensor via ADS1115 ADC.

Features:
- Analog moisture level reading (0-100%)
- I2C communication through ADS1115
- Calibratable dry/wet values
"""

import logging
from typing import Any

from ..base_adapter import AdapterError, BaseSensorAdapter

logger = logging.getLogger(__name__)


class SoilMoistureAdapter(BaseSensorAdapter):
    """
    Specialized adapter for capacitive soil moisture sensor.

    Features:
    - Soil moisture percentage (0-100%)
    - ADC raw value
    - Voltage reading
    - Calibratable (dry/wet values)
    - ADS1115 ADC communication
    """

    def __init__(self, adc_channel: int = 0, unit_id: str = "1"):
        """
        Initialize soil moisture adapter.

        Args:
            adc_channel: ADC channel (0-3)
            unit_id: Unit identifier
        """
        self.adc_channel = adc_channel
        self.unit_id = unit_id
        self._sensor = None
        self._available = False

        try:
            self._initialize_sensor()
            self._available = True
        except Exception as e:
            logger.error("Failed to initialize soil moisture sensor: %s", e)
            self._available = False

    def _initialize_sensor(self):
        """Initialize the sensor hardware"""
        from app.hardware.sensors.drivers.soil_moisture_sensor import SoilMoistureSensorV2

        # Convert channel number to ADC constant if needed
        adc_channel_obj = self.adc_channel
        try:
            import adafruit_ads1x15.ads1115 as ADC

            if isinstance(self.adc_channel, int):
                adc_channel_obj = getattr(ADC, f"P{self.adc_channel}")
        except ImportError:
            pass  # Mock mode

        self._sensor = SoilMoistureSensorV2(adc_channel=adc_channel_obj, unit_id=self.unit_id)

    def read(self) -> dict[str, Any]:
        """
        Read from soil moisture sensor.

        Returns:
            Dict with keys:
            - soil_moisture: Moisture percentage (0-100%)
            - adc_raw: Raw ADC value
            - voltage: Voltage reading (V)
            - status: Sensor status
            - timestamp: ISO timestamp

        Raises:
            AdapterError: If read fails
        """
        if not self._sensor:
            raise AdapterError("Soil moisture sensor not initialized")

        try:
            data = self._sensor.read()

            # Validate data
            if data.get("status") == "ERROR":
                raise AdapterError("Sensor returned ERROR status")

            # Ensure moisture value is present
            if "soil_moisture" not in data or data["soil_moisture"] is None:
                raise AdapterError("No moisture reading available")

            return data

        except Exception as e:
            logger.error("Soil moisture read error: %s", e)
            raise AdapterError(f"Failed to read soil moisture: {e}") from e

    def configure(self, config: dict[str, Any]) -> None:
        """
        Configure the sensor.

        Args:
            config: Configuration parameters
                - adc_channel: Channel number
                - unit_id: Unit identifier
                - dry_value: ADC value for dry soil
                - wet_value: ADC value for wet soil
        """
        if "adc_channel" in config:
            self.adc_channel = config["adc_channel"]

        if "unit_id" in config:
            self.unit_id = config["unit_id"]

        # Apply calibration values if provided
        if self._sensor:
            if "dry_value" in config:
                self._sensor.dry_value = config["dry_value"]
            if "wet_value" in config:
                self._sensor.wet_value = config["wet_value"]

        # Reinitialize if requested
        if config.get("reinitialize", False):
            try:
                self._initialize_sensor()
                self._available = True
            except Exception as e:
                logger.error("Failed to reconfigure soil moisture sensor: %s", e)
                self._available = False
                raise AdapterError(f"Configuration failed: {e}") from e

    def is_available(self) -> bool:
        """Check if sensor is available"""
        return self._available and self._sensor is not None

    def get_protocol_name(self) -> str:
        """Get protocol name"""
        return "ADC"

    def cleanup(self) -> None:
        """Cleanup resources"""
        if self._sensor and hasattr(self._sensor, "cleanup"):
            try:
                self._sensor.cleanup()
            except Exception as e:
                logger.warning("Error during soil moisture cleanup: %s", e)
