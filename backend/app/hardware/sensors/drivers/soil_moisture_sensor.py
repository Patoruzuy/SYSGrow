"""
Internal hardware driver for analog soil moisture sensor via ADS1115 ADC.
This module should only be used by sensor adapters, not directly by application code.
"""

import time
import logging
from typing import Any, Dict
from app.utils.time import iso_now
from .base import BaseSensorDriver

logger = logging.getLogger(__name__)

try:
    import board
    import busio
    import adafruit_ads1x15.ads1115 as ADC
    from adafruit_ads1x15.analog_in import AnalogIn
    IS_PI = True
except (ImportError, NotImplementedError):
    logger.warning("Raspberry Pi-specific libraries not available. Using mock soil sensor.")
    IS_PI = False



class SoilMoistureSensorV2(BaseSensorDriver):
    """
    Hardware driver for analog soil moisture sensor via ADS1115 ADC.
    Inherits from BaseSensorDriver for a unified interface.
    Provides raw sensor readings with calibration mapping.
    """

    def __init__(self, adc_channel: Any, unit_id: str = "1"):
        """
        Initialize the soil moisture sensor hardware.

        Args:
            adc_channel: ADC channel (e.g., ADC.P0, ADC.P1, ADC.P2, ADC.P3).
            unit_id (str): Unit identifier for reference.
        """
        super().__init__(unit_id)
        self.adc_channel = adc_channel
        self.dry_value = 15000  # ADC value when dry
        self.wet_value = 8000   # ADC value when fully wet
        self.i2c_address = 0x48 # ADS1115 I2C address

        if IS_PI:
            try:
                self.i2c = busio.I2C(board.SCL, board.SDA)
                self.adc = ADC.ADS1115(self.i2c, address=self.i2c_address)
                logger.info("Soil moisture sensor initialized on ADS1115 channel %s", adc_channel)
            except Exception as e:
                logger.error("Failed to initialize ADS1115 for soil sensor: %s", e)
        else:
            self.mock_data = {
                'soil_moisture': 52.4,
                'adc_channel': str(adc_channel),
                'status': 'MOCK'
            }


    def read(self, retries: int = 3, delay: int = 1) -> Dict[str, Any]:
        """
        Read raw data from the sensor with retry logic.

        Args:
            retries (int): Number of retry attempts if I/O fails.
            delay (int): Delay between retries in seconds.

        Returns:
            dict: Sensor reading with moisture percentage, raw ADC value, voltage, timestamp, and status.
        """
        if IS_PI:
            for attempt in range(retries):
                try:
                    chan = AnalogIn(self.adc, self.adc_channel)
                    raw = chan.value
                    voltage = chan.voltage
                    moisture = self._map(raw, self.dry_value, self.wet_value, 0, 100)
                    moisture = max(0, min(100, moisture))  # Clamp to 0-100%
                    return {
                        'soil_moisture': round(moisture, 2),
                        'adc_raw': raw,
                        'voltage': round(voltage, 3),
                        'timestamp': iso_now(),
                        'status': 'OK'
                    }
                except OSError as e:
                    logger.warning("Soil sensor read failed (attempt %s): %s", attempt + 1, e)
                    time.sleep(delay)
            return {
                'soil_moisture': None,
                'status': 'ERROR',
                'timestamp': iso_now()
            }
        return self._return_mock()


    def _map(self, x: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
        """
        Map an input value from one range to another.

        Args:
            x (float): Input value.
            in_min (float): Input range minimum.
            in_max (float): Input range maximum.
            out_min (float): Output range minimum.
            out_max (float): Output range maximum.

        Returns:
            float: Mapped output value.
        """
        return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
