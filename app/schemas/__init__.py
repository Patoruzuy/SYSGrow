"""
Schemas Module
==============

This module provides Pydantic models for request/response validation.
Schemas ensure data integrity and provide automatic validation.
"""

from app.schemas.growth import (
    CreateGrowthUnitRequest,
    UpdateGrowthUnitRequest,
    GrowthUnitResponse,
    CreatePlantRequest,
    UpdatePlantRequest,
    PlantResponse,
    ThresholdSettings,
    # v3 Schedule schemas
    ScheduleCreateSchema,
    ScheduleUpdateSchema,
    ScheduleResponseSchema,
    ScheduleListResponseSchema,
    ScheduleSummarySchema,
    PhotoperiodConfigSchema,
)

from app.schemas.device import (
    CreateSensorRequest,
    UpdateSensorRequest,
    SensorResponse,
    CreateActuatorRequest,
    UpdateActuatorRequest,
    ActuatorResponse,
    ControlActuatorRequest
)

from app.schemas.common import (
    SuccessResponse,
    ErrorResponse,
    PaginatedResponse
)

from app.schemas.system import (
    SystemInfoSchema
)

from app.schemas.health import (
    SystemHealthResponse,
    MetricDataPoint
)

from app.schemas.events import (
    SensorUpdatePayload,
    PlantLifecyclePayload,
    PlantStageUpdatePayload,
    PlantGrowthWarningPayload,
    DeviceLifecyclePayload,
    ActuatorLifecyclePayload,
    ActuatorAnomalyPayload,
    ActuatorAnomalyResolvedPayload,
    ActuatorCalibrationPayload,
    ThresholdsUpdatePayload,
    SensorReloadPayload,
    RelayStatePayload,
    DeviceCommandPayload,
    ActuatorStatePayload,
    ConnectivityStatePayload,
    NotificationPayload,
)

from app.schemas.plants import (
    RecordHealthObservationRequest,
    CreateObservationRequest,
    CreateNutrientRecordRequest,
    HarvestPlantRequest,
    UpdatePlantStageRequest,
    PlantDiagnosisRequest,
    AddPlantToCrudRequest,
    ModifyPlantCrudRequest,
    ObservationType,
    NutrientType,
    ApplicationType,
)

from app.schemas.irrigation import (
    IrrigationDelayRequest,
    IrrigationFeedbackRequest,
    ManualIrrigationLogRequest,
    IrrigationConfigRequest,
    IrrigationNotificationActionRequest,
    IrrigationAction,
    IrrigationFeedbackResponse,
    IrrigationExecutionLogResponse,
    IrrigationEligibilityTraceResponse,
    ManualIrrigationLogResponse,
    ManualIrrigationPredictionResponse,
)

from app.schemas.ml import (
    DiseaseRiskRequest,
    GrowthComparisonRequest,
    GrowthTransitionRequest,
    HealthObservationRequest,
    WhatIfSimulationRequest,
    RetrainingJobRequest,
    ModelCompareRequest,
    ModelActivateRequest,
    RootCauseAnalysisRequest,
    ScheduleType,
    ModelType,
)

from app.schemas.personalized import (
    ConditionProfileCard,
    ConditionProfileSection,
    ConditionProfileLinkSummary,
    ConditionProfileSelectorResponse,
)

__all__ = [
    # Growth schemas
    'CreateGrowthUnitRequest',
    'UpdateGrowthUnitRequest',
    'GrowthUnitResponse',
    'CreatePlantRequest',
    'UpdatePlantRequest',
    'PlantResponse',
    'ThresholdSettings',
    
    # Schedule schemas (v3)
    'ScheduleCreateSchema',
    'ScheduleUpdateSchema',
    'ScheduleResponseSchema',
    'ScheduleListResponseSchema',
    'ScheduleSummarySchema',
    'PhotoperiodConfigSchema',
    
    # Device schemas
    'CreateSensorRequest',
    'UpdateSensorRequest',
    'SensorResponse',
    'CreateActuatorRequest',
    'UpdateActuatorRequest',
    'ActuatorResponse',
    'ControlActuatorRequest',
    
    # Common schemas
    'SuccessResponse',
    'ErrorResponse',
    'PaginatedResponse',

    # System schemas
    'SystemInfoSchema',

    # Health schemas
    'SystemHealthResponse',
    'MetricDataPoint',

    # Plant schemas
    'RecordHealthObservationRequest',
    'CreateObservationRequest',
    'CreateNutrientRecordRequest',
    'HarvestPlantRequest',
    'UpdatePlantStageRequest',
    'PlantDiagnosisRequest',
    'AddPlantToCrudRequest',
    'ModifyPlantCrudRequest',
    'ObservationType',
    'NutrientType',
    'ApplicationType',
    
    # Irrigation schemas
    'IrrigationDelayRequest',
    'IrrigationFeedbackRequest',
    'ManualIrrigationLogRequest',
    'IrrigationConfigRequest',
    'IrrigationNotificationActionRequest',
    'IrrigationExecutionLogResponse',
    'IrrigationEligibilityTraceResponse',
    'ManualIrrigationLogResponse',
    'ManualIrrigationPredictionResponse',
    'IrrigationAction',
    'IrrigationFeedbackResponse',
    
    # ML/AI schemas
    'DiseaseRiskRequest',
    'GrowthComparisonRequest',
    'GrowthTransitionRequest',
    'HealthObservationRequest',
    'WhatIfSimulationRequest',
    'RetrainingJobRequest',
    'ModelCompareRequest',
    'ModelActivateRequest',
    'RootCauseAnalysisRequest',
    'ScheduleType',
    'ModelType',

    # Personalized learning schemas
    'ConditionProfileCard',
    'ConditionProfileSection',
    'ConditionProfileLinkSummary',
    'ConditionProfileSelectorResponse',

    # Event payload schemas
    'SensorUpdatePayload',
    'PlantLifecyclePayload',
    'PlantStageUpdatePayload',
    'PlantGrowthWarningPayload',
    'DeviceLifecyclePayload',
    'ActuatorLifecyclePayload',
    'ActuatorAnomalyPayload',
    'ActuatorAnomalyResolvedPayload',
    'ActuatorCalibrationPayload',
    'ThresholdsUpdatePayload',
    'SensorReloadPayload',
    'RelayStatePayload',
    'DeviceCommandPayload',
    'ActuatorStatePayload',
    'ConnectivityStatePayload',
    'NotificationPayload',
]
