"""
Sensor Domain Entity
====================
Rich domain model representing a sensor with business logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from app.domain.sensors.calibration import CalibrationData
    from app.domain.sensors.health_status import HealthStatus
    from app.domain.sensors.reading import SensorReading
    from app.domain.sensors.sensor_config import SensorConfig


class SensorType(str, Enum):
    """
    Sensor categories.

    Two categories that group all sensors:
    - ENVIRONMENTAL: temperature, humidity, co2, lux, voc, smoke, pressure, air_quality
    - PLANT: soil_moisture, ph, ec

    The specific metrics each sensor provides are defined in `primary_metrics` field,
    allowing maximum flexibility (e.g., a plant sensor can provide lux readings).
    """

    ENVIRONMENTAL = "environmental"
    PLANT = "plant"

    @classmethod
    def _missing_(cls, value: object) -> "SensorType | None":
        """Map legacy sensor type values to new categories."""
        if not isinstance(value, str):
            return None

        # Map old individual types to new categories
        environmental_types = {
            "environment_sensor",
            "temperature",
            "temperature_sensor",
            "humidity",
            "humidity_sensor",
            "co2",
            "lux_sensor",
            "light",
            "light_sensor",
            "voc",
            "smoke_sensor",
            "pressure",
            "pressure_sensor",
            "air_quality",
            "air_quality_sensor",
        }
        plant_types = {
            "plant_sensor",
            "soil_moisture",
            "soil_moisture_sensor",
            "ph",
            "ec",
        }

        if value in environmental_types:
            return cls.ENVIRONMENTAL
        if value in plant_types:
            return cls.PLANT

        return None


class Protocol(str, Enum):
    """Communication protocols"""

    GPIO = "GPIO"
    I2C = "I2C"
    ADC = "ADC"
    MQTT = "mqtt"
    ZIGBEE = "zigbee"
    ZIGBEE2MQTT = "zigbee2mqtt"
    HTTP = "http"
    MODBUS = "Modbus"
    WIRELESS = "wireless"

    @classmethod
    def _missing_(cls, value: object) -> "Protocol | None":
        """Backwards-compatible mapping for legacy protocol values."""
        if not isinstance(value, str):
            return None

        legacy_map = {
            "MQTT": cls.MQTT.value,
            "ZIGBEE": cls.ZIGBEE.value,
            "ZIGBEE2MQTT": cls.ZIGBEE2MQTT.value,
            "HTTP": cls.HTTP.value,
            "MODBUS": cls.MODBUS.value,
            "WIRELESS": cls.WIRELESS.value,
        }

        mapped = legacy_map.get(value)
        if mapped is None:
            return None

        return cls(mapped)


@dataclass
class SensorEntity:
    """
    Rich domain entity for sensors with business logic.
    Maintains in-memory state while being protocol-agnostic.
    """

    id: int
    unit_id: int
    name: str
    sensor_type: SensorType
    model: str
    protocol: Protocol
    config: "SensorConfig"

    # Runtime state
    _adapter: Any | None = field(default=None, repr=False)
    _processor: Any | None = field(default=None, repr=False)
    _last_reading: Optional["SensorReading"] = None
    _last_read_time: datetime | None = None
    _error_count: int = 0
    _health_status: Optional["HealthStatus"] = None
    _calibration: Optional["CalibrationData"] = None

    def __post_init__(self):
        """Initialize health status"""
        from app.domain.sensors.health_status import HealthLevel, HealthStatus

        if self._health_status is None:
            self._health_status = HealthStatus(
                sensor_id=self.id, level=HealthLevel.UNKNOWN, message="Not yet initialized"
            )

    def set_adapter(self, adapter) -> None:
        """Set the hardware adapter"""
        self._adapter = adapter

    def set_processor(self, processor) -> None:
        """Set the data processor"""
        self._processor = processor

    def set_calibration(self, calibration: "CalibrationData") -> None:
        """Apply calibration data"""
        self._calibration = calibration

    def read(self) -> "SensorReading":
        """
        Read sensor with full processing pipeline:
        1. Read raw data from adapter
        2. Validate data
        3. Apply calibration
        4. Transform to standard format
        5. Update health status
        """
        if not self._adapter:
            raise RuntimeError(f"Sensor {self.id} has no adapter configured")

        try:
            # 1. Read raw data
            raw_data = self._adapter.read()

            # 2. Process data
            if self._processor:
                validated = self._processor.validate(raw_data)
                if self._calibration:
                    calibrated = self._processor.apply_calibration(validated, self._calibration)
                else:
                    calibrated = validated
                reading = self._processor.transform(calibrated, self)
            else:
                reading = self._create_reading_from_raw(raw_data)

            # 3. Update state
            self._last_reading = reading
            self._last_read_time = datetime.now()
            self._error_count = 0
            self._update_health_status(success=True)

            return reading

        except Exception as e:
            self._error_count += 1
            self._update_health_status(success=False, error=str(e))
            raise SensorReadError(f"Failed to read sensor {self.id} ({self.name}): {e}")

    def _create_reading_from_raw(self, raw_data: dict) -> "SensorReading":
        """Create reading from raw data without processor"""
        from app.domain.sensors.reading import ReadingStatus, SensorReading

        return SensorReading(
            sensor_id=self.id,
            unit_id=self.unit_id,
            sensor_type=self.sensor_type.value,
            sensor_name=self.name,
            data=raw_data,
            timestamp=datetime.now(),
            status=ReadingStatus.SUCCESS,
        )

    def _update_health_status(self, success: bool, error: str | None = None) -> None:
        """Update sensor health based on read results"""
        from app.domain.sensors.health_status import HealthLevel

        if success:
            self._health_status.level = HealthLevel.HEALTHY
            self._health_status.message = "Operating normally"
            self._health_status.consecutive_errors = 0
        else:
            self._health_status.consecutive_errors = self._error_count

            if self._error_count >= 10:
                self._health_status.level = HealthLevel.CRITICAL
                self._health_status.message = f"Critical: {self._error_count} consecutive errors"
            elif self._error_count >= 5:
                self._health_status.level = HealthLevel.DEGRADED
                self._health_status.message = f"Degraded: {self._error_count} errors"
            else:
                self._health_status.level = HealthLevel.WARNING
                self._health_status.message = f"Warning: {error}"

        self._health_status.last_check = datetime.now()

    def is_healthy(self) -> bool:
        """Check if sensor is healthy"""
        from app.domain.sensors.health_status import HealthLevel

        return self._health_status.level in (HealthLevel.HEALTHY, HealthLevel.WARNING)

    def is_wireless(self) -> bool:
        """Check if sensor uses wireless communication"""
        return self.protocol in (Protocol.MQTT, Protocol.ZIGBEE, Protocol.ZIGBEE2MQTT, Protocol.WIRELESS)

    def get_last_reading(self) -> Optional["SensorReading"]:
        """Get last successful reading"""
        return self._last_reading

    def get_health_status(self) -> "HealthStatus":
        """Get current health status"""
        return self._health_status

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "name": self.name,
            "sensor_type": self.sensor_type.value,
            "model": self.model,
            "protocol": self.protocol.value,
            "last_reading": self._last_reading.to_dict() if self._last_reading else None,
            "last_read_time": self._last_read_time.isoformat() if self._last_read_time else None,
            "error_count": self._error_count,
            "health": self._health_status.to_dict(),
            "is_calibrated": self._calibration is not None,
        }


class SensorReadError(Exception):
    """Exception raised when sensor read fails"""

    pass
