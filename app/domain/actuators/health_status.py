"""
Sensor Health Status
====================
Tracks actuator health and reliability.
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
    Actuator health status tracking.
    """

    actuator_id: int
    level: HealthLevel
    message: str
    last_check: datetime | None = None
    consecutive_errors: int = 0
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage"""
        if self.total_operations == 0:
            return 0.0
        return (self.successful_operations / self.total_operations) * 100

    def record_operation(self, success: bool) -> None:
        """Record an operation attempt"""
        self.total_operations += 1
        if success:
            self.successful_operations += 1
            self.consecutive_errors = 0
        else:
            self.failed_operations += 1
            self.consecutive_errors += 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "actuator_id": self.actuator_id,
            "level": self.level.value,
            "message": self.message,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "consecutive_errors": self.consecutive_errors,
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "success_rate": self.success_rate,
        }
