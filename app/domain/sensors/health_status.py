"""
Sensor Health Status
====================
Tracks sensor health and reliability.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any


class HealthLevel(str, Enum):
    """Health status levels"""

    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class HealthStatus:
    """
    Sensor health status tracking.
    """

    sensor_id: int
    level: HealthLevel
    message: str
    last_check: datetime | None = None
    consecutive_errors: int = 0
    total_reads: int = 0
    successful_reads: int = 0
    failed_reads: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_reads == 0:
            return 0.0
        return (self.successful_reads / self.total_reads) * 100

    def record_read(self, success: bool) -> None:
        """Record a read attempt"""
        self.total_reads += 1
        if success:
            self.successful_reads += 1
            self.consecutive_errors = 0
        else:
            self.failed_reads += 1
            self.consecutive_errors += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "sensor_id": self.sensor_id,
            "level": self.level.value,
            "message": self.message,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "consecutive_errors": self.consecutive_errors,
            "total_reads": self.total_reads,
            "successful_reads": self.successful_reads,
            "failed_reads": self.failed_reads,
            "success_rate": round(self.success_rate, 2),
        }
