"""
Sensor Reading Value Object
============================
Immutable value object representing a sensor reading.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum


class ReadingStatus(str, Enum):
    """Status of a sensor reading"""
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    MOCK = "mock"


@dataclass(frozen=True)
class SensorReading:
    """
    Immutable sensor reading value object.
    Represents a single point-in-time reading from a sensor.
    """
    sensor_id: int
    unit_id: int
    sensor_type: str
    sensor_name: str
    data: Dict[str, Any]
    timestamp: datetime
    status: ReadingStatus
    
    # Optional metadata
    quality_score: Optional[float] = None  # 0.0 to 1.0
    is_anomaly: bool = False
    anomaly_reason: Optional[str] = None
    calibration_applied: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'sensor_id': self.sensor_id,
            'unit_id': self.unit_id,
            'sensor_type': self.sensor_type,
            'sensor_name': self.sensor_name,
            'timestamp': self.timestamp.isoformat(),
            'status': self.status.value,
            'data': self.data,
            'quality_score': self.quality_score,
            'is_anomaly': self.is_anomaly,
            'anomaly_reason': self.anomaly_reason,
            'calibration_applied': self.calibration_applied
        }
    
    def get_value(self, key: str, default: Any = None) -> Any:
        """Get a specific value from the data"""
        return self.data.get(key, default)
    
    def has_error(self) -> bool:
        """Check if reading has an error"""
        return self.status == ReadingStatus.ERROR or 'error' in self.data
