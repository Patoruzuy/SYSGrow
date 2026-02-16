"""
Anomaly Detection Domain Objects
=================================
Dataclasses for sensor anomaly detection.
"""

from dataclasses import dataclass
from datetime import datetime

from app.enums import AnomalyType


@dataclass
class Anomaly:
    """Detected anomaly in sensor readings."""

    sensor_id: int
    timestamp: datetime
    anomaly_type: AnomalyType
    value: float
    expected_range: tuple[float, float] | None
    severity: float  # 0.0 to 1.0
    description: str
