"""
Control System Domain Objects
==============================
Dataclasses for climate control logic.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class ControlConfig:
    """Configuration for control loops."""
    # Temperature control
    temp_setpoint: float = 24.0
    temp_kp: float = 1.0
    temp_ki: float = 0.1
    temp_kd: float = 0.05
    temp_deadband: float = 0.5  # Don't react to changes < 0.5°C

    # Humidity control
    humidity_setpoint: float = 60.0
    humidity_kp: float = 1.0
    humidity_ki: float = 0.1
    humidity_kd: float = 0.05
    humidity_deadband: float = 2.0  # Don't react to changes < 2%

    # Soil moisture control
    moisture_setpoint: float = 30.0
    moisture_kp: float = 1.0
    moisture_ki: float = 0.1
    moisture_kd: float = 0.05
    moisture_deadband: float = 3.0  # Don't react to changes < 3%

    # CO2 control
    co2_setpoint: float = 1200.0
    co2_kp: float = 0.5
    co2_ki: float = 0.05
    co2_kd: float = 0.01
    co2_deadband: float = 50.0  # PPM

    # Light (Lux) control
    lux_setpoint: float = 30000.0
    lux_kp: float = 0.2
    lux_ki: float = 0.02
    lux_kd: float = 0.01
    lux_deadband: float = 500.0  # Lux

    # General settings
    min_cycle_time: float = 60.0  # Minimum seconds between actuator changes
    feedback_timeout: float = 5.0  # Seconds to wait for actuator confirmation
    max_consecutive_errors: int = 3  # Max errors before disabling control


@dataclass
class ControlMetrics:
    """Metrics for control loop performance."""
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    average_response_time: float = 0.0
    last_action_time: Optional[datetime] = None
    consecutive_errors: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate percentage."""
        if self.total_actions == 0:
            return 100.0
        return (self.successful_actions / self.total_actions) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'total_actions': self.total_actions,
            'successful_actions': self.successful_actions,
            'failed_actions': self.failed_actions,
            'success_rate': self.success_rate,
            'average_response_time': self.average_response_time,
            'last_action_time': self.last_action_time.isoformat() if self.last_action_time else None,
            'consecutive_errors': self.consecutive_errors
        }
