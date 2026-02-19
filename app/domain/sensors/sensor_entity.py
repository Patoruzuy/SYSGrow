"""
Sensor Domain Entity
====================
Rich domain model representing a sensor with business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

from app.enums.device import Protocol, SensorType

if TYPE_CHECKING:
    from app.domain.sensors.calibration import CalibrationData
    from app.domain.sensors.health_status import HealthStatus
    from app.domain.sensors.reading import SensorReading
    from app.domain.sensors.sensor_config import SensorConfig


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
    _last_reading: "SensorReading" | None = None
    _last_read_time: datetime | None = None
    _error_count: int = 0
    _health_status: "HealthStatus" | None = None
    _calibration: "CalibrationData" | None = None

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
            raise SensorReadError(f"Failed to read sensor {self.id} ({self.name}): {e}") from e

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

    def get_last_reading(self) -> "SensorReading" | None:
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
