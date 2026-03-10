"""
Enums Module
============

This module provides enumeration types for the SYSGrow application.
Enums ensure type safety and consistency across the codebase.
"""

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
    Protocol,
    SensorModel,
    SensorType,
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
    "ActuatorState",
    "ActuatorType",
    "AnomalySeverity",
    "AnomalyType",
    "ConditionProfileMode",
    "ConditionProfileTarget",
    "ConditionProfileVisibility",
    "ControlStrategy",
    "DayOfWeek",
    "DeviceCategory",
    "DeviceEvent",
    "DeviceStatus",
    "DeviceType",
    "DiseaseType",
    "DriftRecommendation",
    "EventType",
    "GrowthPhase",
    "HealthLevel",
    "IrrigationEligibilityDecision",
    "IrrigationFeedback",
    "IrrigationSkipReason",
    # Growth enums
    "LocationType",
    "MQTTSource",
    "NotificationChannel",
    "NotificationSeverity",
    "NotificationType",
    "PhotoperiodSource",
    "PlantEvent",
    "PlantHealthStatus",
    "PlantStage",
    "PowerMode",
    "Priority",
    # Device enums
    "Protocol",
    "RequestStatus",
    # Common enums
    "RiskLevel",
    "RuntimeEvent",
    "ScheduleState",
    # Schedule enums
    "ScheduleType",
    # Event enums
    "SensorEvent",
    "SensorModel",
    "SensorState",
    "SensorType",
    "TrainingDataType",
]
