"""
Enums Module
============

This module provides enumeration types for the SYSGrow application.
Enums ensure type safety and consistency across the codebase.
"""

from app.domain.sensors.sensor_entity import Protocol, SensorType
from app.enums.common import (
    AnomalySeverity,
    AnomalyType,
    ConditionProfileMode,
    ConditionProfileTarget,
    ConditionProfileVisibility,
    ControlStrategy,
    DiseaseType,
    DriftRecommendation,
    HealthLevel,
    IrrigationFeedback,
    MQTTSource,
    NotificationChannel,
    NotificationSeverity,
    NotificationType,
    PlantHealthStatus,
    Priority,
    RequestStatus,
    RiskLevel,
    SensorState,
    TrainingDataType,
)
from app.enums.device import (
    ActuatorState,
    ActuatorType,
    DeviceCategory,
    DeviceStatus,
    DeviceType,
    PowerMode,
    SensorModel,
)
from app.enums.events import (
    DeviceEvent,
    EventType,
    IrrigationEligibilityDecision,
    IrrigationSkipReason,
    PlantEvent,
    RuntimeEvent,
    SensorEvent,
)
from app.enums.growth import (
    DayOfWeek,
    GrowthPhase,
    LocationType,
    PhotoperiodSource,
    PlantStage,
    ScheduleState,
    # Schedule enums
    ScheduleType,
)

__all__ = [
    # Device enums
    "Protocol",
    "SensorType",
    "SensorModel",
    "ActuatorType",
    "ActuatorState",
    "PowerMode",
    "DeviceType",
    "DeviceStatus",
    "DeviceCategory",
    # Growth enums
    "LocationType",
    "PlantStage",
    "GrowthPhase",
    # Schedule enums
    "ScheduleType",
    "ScheduleState",
    "PhotoperiodSource",
    "DayOfWeek",
    # Event enums
    "SensorEvent",
    "PlantEvent",
    "DeviceEvent",
    "RuntimeEvent",
    "EventType",
    "IrrigationEligibilityDecision",
    "IrrigationSkipReason",
    # Common enums
    "RiskLevel",
    "HealthLevel",
    "Priority",
    "DriftRecommendation",
    "TrainingDataType",
    "AnomalyType",
    "AnomalySeverity",
    "RequestStatus",
    "MQTTSource",
    "DiseaseType",
    "PlantHealthStatus",
    "ControlStrategy",
    "SensorState",
    "NotificationType",
    "NotificationSeverity",
    "NotificationChannel",
    "IrrigationFeedback",
    "ConditionProfileMode",
    "ConditionProfileVisibility",
    "ConditionProfileTarget",
]
