"""
Internal hardware driver for TSL2591 light intensity sensor.
This module should only be used by sensor adapters, not directly by application code.
"""

import logging
from typing import Any

from app.utils.time import iso_now

from .base import BaseSensorDriver

logger = logging.getLogger(__name__)

try:
    import adafruit_tsl2591
    import board
    import busio

    IS_PI = True
except (ImportError, NotImplementedError):
    logger.warning("Raspberry Pi-specific libraries not available. Using mock TSL2591 sensor.")
    IS_PI = False


class TSL2591Driver(BaseSensorDriver):
    """
    Hardware driver for TSL2591 light intensity sensor via I2C.
    Inherits from BaseSensorDriver for a unified interface.
    """

    def __init__(self, unit_id: str = "1"):
        """
        Initialize the TSL2591 sensor hardware.

        Args:
            unit_id (str): Unit identifier for reference.
        """
        super().__init__(unit_id)
        self.sensor = None

        if IS_PI:
            try:
                i2c = busio.I2C(board.SCL, board.SDA)
                self.sensor = adafruit_tsl2591.TSL2591(i2c)
                logger.info("TSL2591 sensor initialized successfully.")
            except Exception as e:
                logger.error("Failed to initialize TSL2591 sensor: %s", e)
        else:
            self.mock_data = {"lux": 550.5, "full_spectrum": 1200, "infrared": 450, "visible": 750, "status": "MOCK"}

    def read(self) -> dict[str, Any]:
        """
        Read raw data from the TSL2591 light sensor.

        Returns:
            dict: Light sensor data including lux, full_spectrum, IR, visible, timestamp, and status.
        """
        if IS_PI and self.sensor:
            try:
                lux = self.sensor.lux
                full = self.sensor.full_spectrum
                ir = self.sensor.infrared
                visible = full - ir
                return {
                    "lux": lux,
                    "full_spectrum": full,
                    "infrared": ir,
                    "visible": visible,
                    "timestamp": iso_now(),
                    "status": "OK",
                }
            except Exception as e:
                logger.error("Error reading TSL2591: %s", e)
                return {"error": str(e), "status": "ERROR", "timestamp": iso_now()}
        return self._return_mock()
