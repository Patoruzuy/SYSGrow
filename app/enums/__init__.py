"""
Enums Module
============

This module provides enumeration types for the SYSGrow application.
Enums ensure type safety and consistency across the codebase.
"""
from app.domain.sensors.sensor_entity import Protocol, SensorType

from app.enums.device import (
    SensorModel,
    ActuatorType,
    ActuatorState,
    PowerMode,
    DeviceType,
    DeviceStatus,
    DeviceCategory,
)

from app.enums.growth import (
    LocationType,
    PlantStage,
    GrowthPhase,
    # Schedule enums
    ScheduleType,
    ScheduleState,
    PhotoperiodSource,
    DayOfWeek,
)
from app.enums.events import (
    SensorEvent,
    PlantEvent,
    DeviceEvent,
    RuntimeEvent,
    EventType,
    IrrigationEligibilityDecision,
    IrrigationSkipReason,
)
from app.enums.common import (
    RiskLevel,
    HealthLevel,
    Priority,
    DriftRecommendation,
    TrainingDataType,
    AnomalyType,
    AnomalySeverity,
    RequestStatus,
    MQTTSource,
    DiseaseType,
    PlantHealthStatus,
    ControlStrategy,
    SensorState,
    NotificationType,
    NotificationSeverity,
    NotificationChannel,
    IrrigationFeedback,
    ConditionProfileMode,
    ConditionProfileVisibility,
    ConditionProfileTarget,
)

__all__ = [
    # Device enums
    'Protocol',
    'SensorType',
    'SensorModel',
    'ActuatorType',
    'ActuatorState',
    'PowerMode',
    'DeviceType',
    'DeviceStatus',
    'DeviceCategory',
    
    # Growth enums
    'LocationType',
    'PlantStage',
    'GrowthPhase',
    
    # Schedule enums
    'ScheduleType',
    'ScheduleState',
    'PhotoperiodSource',
    'DayOfWeek',

    # Event enums
    'SensorEvent',
    'PlantEvent',
    'DeviceEvent',
    'RuntimeEvent',
    'EventType',
    'IrrigationEligibilityDecision',
    'IrrigationSkipReason',
    
    # Common enums
    'RiskLevel',
    'HealthLevel',
    'Priority',
    'DriftRecommendation',
    'TrainingDataType',
    'AnomalyType',
    'AnomalySeverity',
    'RequestStatus',
    'MQTTSource',
    'DiseaseType',
    'PlantHealthStatus',
    'ControlStrategy',
    'SensorState',
    'NotificationType',
    'NotificationSeverity',
    'NotificationChannel',
    'IrrigationFeedback',
    'ConditionProfileMode',
    'ConditionProfileVisibility',
    'ConditionProfileTarget',
]
