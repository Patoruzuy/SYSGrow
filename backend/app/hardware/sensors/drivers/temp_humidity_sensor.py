"""
Internal hardware driver for BME280 temperature, humidity, and pressure sensor.
This module should only be used by sensor adapters, not directly by application code.
"""

import logging
from typing import Any

from app.utils.time import iso_now

from .base import BaseSensorDriver

logger = logging.getLogger(__name__)

try:
    import adafruit_bme280
    import board
    import busio

    IS_PI = True
except (ImportError, NotImplementedError):
    logger.warning("Raspberry Pi-specific libraries not available. Using mock BME280 sensor.")
    IS_PI = False


class BME280Sensor(BaseSensorDriver):
    """
    Hardware driver for BME280 sensor via I2C.
    Inherits from BaseSensorDriver for a unified interface.
    Provides raw sensor readings for temperature, humidity, pressure, and altitude.
    """

    def __init__(self, unit_id: str = "1"):
        """
        Initialize the BME280 sensor hardware.

        Args:
            unit_id (str): Unit identifier for reference.
        """
        super().__init__(unit_id)
        if IS_PI:
            try:
                self.i2c_bus = busio.I2C(board.SCL, board.SDA)
                self.bme280 = adafruit_bme280.Adafruit_BME280_I2C(self.i2c_bus)
                logger.info("BME280 sensor initialized for unit %s", unit_id)
            except Exception as e:
                logger.error("BME280 init failed for unit %s: %s", unit_id, e)
        else:
            self.mock_data = {
                "temperature": 24.7,
                "humidity": 51.2,
                "pressure": 1012.3,
                "altitude": 100.5,
                "status": "MOCK",
            }

    def read(self, include_altitude: bool = False) -> dict[str, Any]:
        """
        Read raw data from the BME280 sensor.

        Args:
            include_altitude (bool): Include altitude calculation in the output.

        Returns:
            dict: Sensor reading with temperature, humidity, pressure, optional altitude, timestamp, and status.
        """
        if IS_PI and hasattr(self, "bme280"):
            try:
                data = {
                    "temperature": self.bme280.temperature,
                    "humidity": self.bme280.humidity,
                    "pressure": self.bme280.pressure,
                    "altitude": self.bme280.altitude if include_altitude else None,
                    "status": "OK",
                    "timestamp": iso_now(),
                }
                if not include_altitude:
                    data.pop("altitude", None)
                return data
            except Exception as e:
                logger.error("Error reading BME280: %s", e)
                return {"error": str(e), "status": "ERROR", "timestamp": iso_now()}
        data = self._return_mock()
        if not include_altitude:
            data.pop("altitude", None)
        return data

    def set_sea_level_pressure(self, pressure_hpa: float) -> None:
        """
        Set the sea-level pressure for more accurate altitude calculations.

        Args:
            pressure_hpa (float): Pressure in hPa.
        """
        try:
            if IS_PI and hasattr(self, "bme280"):
                self.bme280.sea_level_pressure = pressure_hpa
                logger.info("Sea level pressure set to %s hPa", pressure_hpa)
        except Exception as e:
            logger.error("Error setting sea level pressure: %s", e)
