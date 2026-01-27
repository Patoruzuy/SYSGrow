"""
Domain Value Objects Package
=============================
Contains immutable value objects following Domain-Driven Design patterns.

Value objects are immutable objects that represent descriptive aspects of the domain
with no conceptual identity. They are defined only by their attributes.
"""

from .anomaly import Anomaly
from .control import ControlConfig, ControlMetrics
from .energy import EnergyReading, PowerProfile, ConsumptionStats
from .environmental_thresholds import EnvironmentalThresholds
from .irrigation import (
    PredictionConfidence,
    UserResponsePrediction,
    ThresholdPrediction,
    DurationPrediction,
    TimingPrediction,
    IrrigationPrediction,
)
from .notification_settings import NotificationSettings
from .plant_health import PlantHealthObservation, EnvironmentalCorrelation
from .plant_profile import PlantProfile
from .system import SystemHealthStatus, SystemHealthLevel, SystemHealthReport
from .unit_runtime import UnitRuntime, UnitSettings, UnitDimensions

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
