"""
System Health Status
====================
Tracks system health and reliability.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum

from app.domain.sensors import HealthLevel


class SystemHealthLevel(str, Enum):
    """System health status levels"""
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    MAINTENANCE = "maintenance"
    OUTAGE = "outage"
    UNKNOWN = "unknown"


@dataclass
class SystemHealthStatus:
    """
    System health status tracking.
    """
    system_id: int
    level: SystemHealthLevel
    message: str
    last_check: Optional[datetime] = None
    uptime_percentage: float = 100.0
    incident_count: int = 0
    
    def record_incident(self) -> None:
        """Record a system incident"""
        self.incident_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'system_id': self.system_id,
            'level': self.level.value,
            'message': self.message,
            'last_check': self.last_check.isoformat() if self.last_check else None,
            'uptime_percentage': self.uptime_percentage,
            'incident_count': self.incident_count,
        }


@dataclass
class SystemHealthReport:
    """System-wide sensor health report."""
    timestamp: datetime
    total_sensors: int
    healthy_sensors: int
    degraded_sensors: int
    critical_sensors: int
    offline_sensors: int
    system_health_level: HealthLevel
    average_success_rate: float
    issues: List[str]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'total_sensors': self.total_sensors,
            'healthy_sensors': self.healthy_sensors,
            'degraded_sensors': self.degraded_sensors,
            'critical_sensors': self.critical_sensors,
            'offline_sensors': self.offline_sensors,
            'system_health_level': self.system_health_level.value,
            'average_success_rate': round(self.average_success_rate, 2),
            'issues': self.issues,
        }

