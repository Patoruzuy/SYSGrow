"""
Domain Value Objects Package
=============================
Contains immutable value objects following Domain-Driven Design patterns.

Value objects are immutable objects that represent descriptive aspects of the domain
with no conceptual identity. They are defined only by their attributes.
"""

from .anomaly import Anomaly
from .control import ControlConfig, ControlMetrics
from .energy import ConsumptionStats, EnergyReading, PowerProfile
from .environmental_thresholds import EnvironmentalThresholds
from .irrigation import (
    DurationPrediction,
    IrrigationPrediction,
    PredictionConfidence,
    ThresholdPrediction,
    TimingPrediction,
    UserResponsePrediction,
)
from .notification_settings import NotificationSettings
from .plant_health import EnvironmentalCorrelation, PlantHealthObservation
from .plant_profile import PlantProfile
from .system import SystemHealthLevel, SystemHealthReport, SystemHealthStatus
from .unit_runtime import UnitDimensions, UnitRuntime, UnitSettings

__all__ = [
    # Anomaly detection
    "Anomaly",
    # Control system
    "ControlConfig",
    "ControlMetrics",
    # Energy monitoring
    "EnergyReading",
    "PowerProfile",
    "ConsumptionStats",
    # Environmental
    "EnvironmentalThresholds",
    # Irrigation predictions
    "PredictionConfidence",
    "UserResponsePrediction",
    "ThresholdPrediction",
    "DurationPrediction",
    "TimingPrediction",
    "IrrigationPrediction",
    # Notifications
    "NotificationSettings",
    # Plant health
    "PlantHealthObservation",
    "EnvironmentalCorrelation",
    # Plant
    "PlantProfile",
    # System health
    "SystemHealthStatus",
    "SystemHealthLevel",
    "SystemHealthReport",
    # Unit
    "UnitRuntime",
    "UnitSettings",
    "UnitDimensions",
]
