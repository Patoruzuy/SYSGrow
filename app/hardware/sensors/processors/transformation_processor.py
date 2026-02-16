"""
Transformation Processor
========================
Transforms validated data into standardized SensorReading format.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.domain.sensors.fields import FIELD_ALIASES, get_standard_field
from app.domain.sensors.reading import ReadingStatus

from .base_processor import IDataProcessor

if TYPE_CHECKING:
    from app.domain.sensors import SensorEntity, SensorReading

logger = logging.getLogger(__name__)


class TransformationProcessor(IDataProcessor):
    """
    Transforms sensor data into standardized SensorReading objects.

    Handles:
    - Format standardization
    - Unit conversion
    - Field name mapping
    - Metadata addition
    """

    def __init__(self):
        """Initialize transformation processor"""
        self.field_mappings = self._create_field_mappings()

    def _create_field_mappings(self) -> dict[str, str]:
        """
        Create mappings for field name standardization.

        Returns:
            Dict mapping various field names to standard names
        """
        return FIELD_ALIASES

    def standardize_fields(self, raw_data: dict[str, Any], *, meta_keys: set | None = None) -> dict[str, Any]:
        """
        Standardize field names and flatten nested payloads.

        Args:
            raw_data: Incoming sensor payload
            meta_keys: Optional set of metadata keys to preserve as-is

        Returns:
            Sanitized dict with standardized keys
        """
        if not isinstance(raw_data, dict):
            return {}

        meta_keys = {str(k).strip().lower() for k in (meta_keys or set())}
        sanitized: dict[str, Any] = {}

        def process_value(k: str, v: Any) -> None:
            std_k = str(get_standard_field(k)).strip().lower()

            # Handle nested structures (e.g. {"lux": {"value": 100}})
            if isinstance(v, dict):
                sub_val = v.get("value") or v.get(f"{std_k}_value") or v.get(f"{k}_value")
                if sub_val is not None:
                    sanitized[std_k] = sub_val
                else:
                    sanitized[std_k] = v
            else:
                sanitized[std_k] = v

        for k, v in raw_data.items():
            raw_key = str(k).strip()
            normalized_key = raw_key.lower()

            if normalized_key in meta_keys:
                sanitized[normalized_key] = v
            else:
                process_value(raw_key, v)

        return sanitized

    def validate(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """Pass-through validation (handled by ValidationProcessor)"""
        return raw_data

    def transform(self, validated_data: dict[str, Any], sensor: "SensorEntity") -> "SensorReading":
        """
        Transform validated data into SensorReading.

        Args:
            validated_data: Validated (and possibly calibrated) data
            sensor: Sensor entity

        Returns:
            SensorReading object
        """
        from app.domain.sensors import SensorReading

        # Note: field standardization now happens in CompositeProcessor before validation

        # Determine status
        status = self._determine_status(validated_data)

        # Create reading
        reading = SensorReading(
            sensor_id=sensor.id,
            unit_id=sensor.unit_id,
            sensor_type=sensor.sensor_type.value,
            sensor_name=sensor.name,
            data=validated_data,
            timestamp=datetime.now(),
            status=status,
            calibration_applied=sensor._calibration is not None,
        )

        return reading

    def _determine_status(self, data: dict[str, Any]) -> "ReadingStatus":
        """
        Determine reading status based on data content.

        Args:
            data: Sensor data

        Returns:
            ReadingStatus enum value
        """
        # Check for error field
        if "error" in data:
            return ReadingStatus.ERROR

        # Check for mock/test data indicator
        if data.get("status") == "MOCK":
            return ReadingStatus.MOCK

        # Check for warning indicators (low battery, weak signal)
        if "battery" in data and data["battery"] < 20:
            return ReadingStatus.WARNING

        if "linkquality" in data and data["linkquality"] < 50:
            return ReadingStatus.WARNING

        # Default: success
        return ReadingStatus.SUCCESS

    def convert_units(self, data: dict[str, Any], conversions: dict[str, tuple]) -> dict[str, Any]:
        """
        Convert units for specified fields.

        Args:
            data: Data to convert
            conversions: Dict mapping field names to (from_unit, to_unit, conversion_func)

        Returns:
            Data with converted units
        """
        converted = data.copy()

        for field, (from_unit, to_unit, func) in conversions.items():
            if field in converted:
                try:
                    converted[field] = func(converted[field])
                    logger.debug(f"Converted {field} from {from_unit} to {to_unit}")
                except Exception as e:
                    logger.error(f"Failed to convert {field}: {e}")

        return converted
