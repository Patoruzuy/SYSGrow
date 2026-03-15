"""
Internal hardware driver for ENS160 + AHT21 sensors.
This module should only be used by sensor adapters, not directly by application code.
"""

import logging
from typing import Any, Dict
from app.utils.time import iso_now
from .base import BaseSensorDriver

logger = logging.getLogger(__name__)

try:
    import adafruit_ahtx0
    import adafruit_ens160
    import board
    import busio
    IS_PI = True
except (ImportError, NotImplementedError):
    logger.warning("Raspberry Pi-specific libraries not available. Using mock CO2/air-quality sensors.")
    IS_PI = False



class ENS160_AHT21Sensor(BaseSensorDriver):
    """
    Hardware driver for ENS160 (air quality) and AHT21 (temperature/humidity) sensors via I2C.
    Inherits from BaseSensorDriver for a unified interface.
    """

    def __init__(self, unit_id: str = "1"):
        """
        Initialize the ENS160 + AHT21 sensor hardware.

        Args:
            unit_id (str): Unit identifier for reference.
        """
        super().__init__(unit_id)
        self.ens160 = None
        self.aht21 = None

        if IS_PI:
            try:
                self.i2c = busio.I2C(board.SCL, board.SDA)
                self.aht21 = adafruit_ahtx0.AHTx0(self.i2c)
                self.ens160 = adafruit_ens160.ENS160(self.i2c)
                self.ens160.operation_mode = adafruit_ens160.MODE_STANDARD
                logger.info("ENS160 + AHT21 sensors initialized for unit %s", unit_id)
            except Exception as e:
                logger.error("ENS160/AHT21 sensor init failed for unit %s: %s", unit_id, e)
        else:
            self.mock_data = {
                'co2': 420,
                'voc': 35,
                'temperature': 24.3,
                'humidity': 55.1,
                'status': 'MOCK'
            }


    def read(self) -> Dict[str, Any]:
        """
        Read raw data from the ENS160 and AHT21 sensors.

        Returns:
            dict: Sensor reading with timestamp and status.
        """
        if IS_PI and self.ens160 and self.aht21:
            try:
                # Use standardized field names: co2 instead of eco2, voc instead of tvoc
                return {
                    'co2': self.ens160.eco2,
                    'voc': self.ens160.tvoc,
                    'temperature': self.aht21.temperature,
                    'humidity': self.aht21.relative_humidity,
                    'status': self.ens160.operating_mode,
                    'timestamp': iso_now()
                }
            except Exception as e:
                logger.error("ENS160/AHT21 read error for unit %s: %s", self.unit_id, e)
                return {'error': str(e), 'timestamp': iso_now(), 'status': 'ERROR'}
        return self._return_mock()
