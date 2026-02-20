"""
Calibration Processor
=====================
Applies calibration to sensor data.
"""

import logging
from typing import TYPE_CHECKING, Any

from .base_processor import IDataProcessor

if TYPE_CHECKING:
    from app.domain.sensors import CalibrationData

logger = logging.getLogger(__name__)


class CalibrationProcessor(IDataProcessor):
    """
    Applies calibration to numeric sensor values.

    Supports multiple calibration methods:
    - Linear (y = mx + b)
    - Polynomial
    - Lookup table
    - Custom functions
    """

    # Fields that typically need calibration (Standardized Names)
    CALIBRATABLE_FIELDS = [
        "temperature",
        "humidity",
        "soil_moisture",
        "moisture_level",
        "lux",
        "illuminance",
        "co2",
        "eco2",
        "voc",
        "tvoc",
        "pressure",
        "ph",
        "ec",
        "air_quality",
    ]

    def __init__(self):
        """Initialize calibration processor"""
        pass

    def apply_calibration(self, data: dict[str, Any], calibration: "CalibrationData") -> dict[str, Any]:
        """
        Apply calibration to data.

        Args:
            data: Validated sensor data
            calibration: Calibration data

        Returns:
            Calibrated data
        """
        calibrated_data = data.copy()

        # Find calibratable fields in the data
        for field in self.CALIBRATABLE_FIELDS:
            if field in calibrated_data:
                value = calibrated_data[field]

                # Only calibrate numeric values
                if isinstance(value, (int, float)):
                    try:
                        calibrated_value = calibration.apply(value)
                        calibrated_data[field] = calibrated_value
                        logger.debug("Calibrated %s: %s -> %s", field, value, calibrated_value)
                    except Exception as e:
                        logger.error("Failed to calibrate %s: %s", field, e)
                        # Keep original value on error

        return calibrated_data

    def validate(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Pass-through validation (handled by ValidationProcessor)"""
        return raw_data

    def transform(self, validated_data: dict[str, Any], sensor) -> Any:
        """Pass-through transformation (handled by TransformationProcessor)"""
        return validated_data
