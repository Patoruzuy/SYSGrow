"""
Energy Monitoring Domain Objects
=================================
Dataclasses for energy consumption tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EnergyReading:
    """Energy consumption reading from a smart switch/actuator."""

    actuator_id: int
    voltage: float | None = None  # Volts
    current: float | None = None  # Amps
    power: float | None = None  # Watts
    energy: float | None = None  # kWh (cumulative)
    power_factor: float | None = None
    frequency: float | None = None  # Hz
    temperature: float | None = None  # Device temperature
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "actuator_id": self.actuator_id,
            "voltage": self.voltage,
            "current": self.current,
            "power": self.power,
            "energy": self.energy,
            "power_factor": self.power_factor,
            "frequency": self.frequency,
            "temperature": self.temperature,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class PowerProfile:
    """Power consumption profile for an actuator type."""

    actuator_type: str
    rated_power_watts: float
    standby_power_watts: float = 0.0
    efficiency_factor: float = 1.0
    power_curve: dict[int, float] = field(default_factory=dict)  # level -> watts

    def estimate_power(self, level: float) -> float:
        """Estimate power consumption at given level (0-100)."""
        if level <= 0:
            return self.standby_power_watts

        # Use power curve if available
        if self.power_curve:
            # Find closest level in curve
            closest_level = min(self.power_curve.keys(), key=lambda k: abs(k - level))
            return self.power_curve[closest_level]

        # Linear estimation
        return self.standby_power_watts + (self.rated_power_watts * (level / 100.0) * self.efficiency_factor)


@dataclass
class ConsumptionStats:
    """Statistics for actuator power consumption."""

    actuator_id: int
    total_energy_kwh: float
    average_power_watts: float
    peak_power_watts: float
    runtime_hours: float
    cost_estimate: float
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "actuator_id": self.actuator_id,
            "total_energy_kwh": round(self.total_energy_kwh, 3),
            "average_power_watts": round(self.average_power_watts, 2),
            "peak_power_watts": round(self.peak_power_watts, 2),
            "runtime_hours": round(self.runtime_hours, 2),
            "cost_estimate": round(self.cost_estimate, 2),
            "last_updated": self.last_updated.isoformat(),
        }
