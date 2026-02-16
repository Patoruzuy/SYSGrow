"""
GPIO Sensor Adapter
===================
Adapter for sensors connected via GPIO, I2C, or ADC.

All supported drivers now inherit from BaseSensorDriver and provide a unified interface:
- `read()` returns a dict with sensor data, `status`, and `timestamp`.
- `cleanup()` is always available for resource cleanup.
"""

import logging
from typing import Any

from app.hardware.sensors.drivers.base import BaseSensorDriver

from .base_adapter import AdapterError, ISensorAdapter

logger = logging.getLogger(__name__)


class GPIOAdapter(ISensorAdapter):
    """
    Adapter for GPIO-based sensors (I2C, ADC, digital/analog GPIO).
    Wraps sensor drivers that all inherit from BaseSensorDriver.

    All drivers now:
    - Expose a `read()` method returning a standardized dict:
        {
            ...sensor fields...,
            'status': 'OK' | 'MOCK' | 'ERROR',
            'timestamp': <iso8601>
        }
    - Provide a `cleanup()` method for resource cleanup.
    """

    def __init__(self, sensor_model: str, sensor_config: dict[str, Any], **kwargs):
        """
        Initialize GPIO adapter with specific sensor implementation.

        Args:
            sensor_model: Model name (ENS160AHT21, TSL2591, Soil-Moisture, MQ2)
            sensor_config: Configuration dict with gpio_pin, i2c_bus, adc_channel, etc.
            **kwargs: Catch extra parameters leaked from factory
        """
        self.sensor_model: str = sensor_model
        self.config: dict[str, Any] = sensor_config
        self._sensor_impl: BaseSensorDriver | None = None
        self._available: bool = False

        try:
            self._initialize_sensor()
            self._available = True
        except Exception as e:
            logger.error(f"Failed to initialize GPIO sensor {sensor_model}: {e}")
            self._available = False

    def _initialize_sensor(self) -> None:
        """Initialize the specific sensor implementation (type safe)."""
        unit_id: str = self.config.get("unit_id", "1")
        model = self.sensor_model
        if model == "ENS160AHT21":
            from app.hardware.sensors.drivers.co2_sensor import ENS160_AHT21Sensor

            self._sensor_impl = ENS160_AHT21Sensor(unit_id=unit_id)
        elif model == "TSL2591":
            from app.hardware.sensors.drivers.light_sensor import TSL2591Driver

            self._sensor_impl = TSL2591Driver(unit_id=unit_id)
        elif model == "Soil-Moisture":
            from app.hardware.sensors.drivers.soil_moisture_sensor import SoilMoistureSensorV2

            adc_channel = self.config.get("adc_channel") or self.config.get("gpio_pin")
            if adc_channel is None:
                raise ValueError("Soil moisture sensor requires adc_channel or gpio_pin")

            # Import ADC constants if on Pi
            try:
                import adafruit_ads1x15.ads1115 as ADC

                # Map channel number to ADC.P0, ADC.P1, etc.
                if isinstance(adc_channel, int):
                    adc_channel = getattr(ADC, f"P{adc_channel}")
            except ImportError:
                pass  # Mock mode will handle it

            self._sensor_impl = SoilMoistureSensorV2(adc_channel=adc_channel, unit_id=unit_id)

        elif model == "MQ2":
            from app.hardware.sensors.drivers.mq2_sensor import MQ2Sensor

            pin = self.config.get("gpio_pin")
            is_digital = self.config.get("is_digital", True)
            channel = self.config.get("adc_channel", 0)
            if pin is None and is_digital:
                raise ValueError("MQ2 sensor requires gpio_pin for digital mode")

            self._sensor_impl = MQ2Sensor(
                sensor_pin=pin if pin else 17, is_digital=is_digital, channel=channel, unit_id=unit_id
            )

        elif model == "DHT11":
            from app.hardware.sensors.drivers.dht11_sensor import DHT11Sensor

            pin = self.config.get("gpio_pin")
            if pin is None:
                raise ValueError("DHT11 sensor requires gpio_pin")

            self._sensor_impl = DHT11Sensor(pin=pin, unit_id=unit_id)

        elif model == "BME280":
            from app.hardware.sensors.drivers.temp_humidity_sensor import BME280Sensor

            self._sensor_impl = BME280Sensor(unit_id=unit_id)
        else:
            raise ValueError(f"Unsupported GPIO sensor model: {model}")

    def read(self) -> dict[str, Any]:
        """
        Read data from GPIO sensor.

        Returns:
            Dict with sensor readings, always including 'status' and 'timestamp'.
        Raises:
            AdapterError: If read fails
        """
        if not isinstance(self._sensor_impl, BaseSensorDriver):
            raise AdapterError(f"Sensor {self.sensor_model} not initialized or invalid type")
        try:
            # Read from sensor - drivers no longer have push parameter
            data = self._sensor_impl.read()

            # Ensure data is a dict
            if not isinstance(data, dict):
                raise AdapterError(f"Expected dict from sensor, got {type(data)}")
            return data
        except Exception as e:
            logger.error(f"GPIO adapter read error for {self.sensor_model}: {e}")
            raise AdapterError(f"Failed to read GPIO sensor: {e}")

    def configure(self, config: dict[str, Any]) -> None:
        """
        Apply new configuration to sensor.

        Args:
            config: Configuration dictionary
        Note:
            If 'reinitialize' is set, the sensor will be re-instantiated with the new config.
        """
        self.config.update(config)

        # Re-initialize sensor with new config if needed
        if config.get("reinitialize", False):
            try:
                self._initialize_sensor()
                self._available = True
            except Exception as e:
                logger.error(f"Failed to reconfigure sensor: {e}")
                self._available = False
                raise AdapterError(f"Configuration failed: {e}")

    def is_available(self) -> bool:
        """
        Check if GPIO sensor is available.

        Returns:
            True if sensor initialized successfully
        """
        return self._available and isinstance(self._sensor_impl, BaseSensorDriver)

    def get_protocol_name(self) -> str:
        """
        Get protocol name.
        Returns:
            Always returns 'GPIO'.
        """
        return "GPIO"

    def cleanup(self) -> None:
        """
        Cleanup GPIO resources using the driver's cleanup() method.
        """
        if isinstance(self._sensor_impl, BaseSensorDriver):
            try:
                self._sensor_impl.cleanup()
            except Exception as e:
                logger.warning(f"Error during GPIO cleanup: {e}")
