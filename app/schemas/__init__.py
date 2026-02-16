"""
Schemas Module
==============

This module provides Pydantic models for request/response validation.
Schemas ensure data integrity and provide automatic validation.
"""

from app.schemas.common import ErrorResponse, PaginatedResponse, SuccessResponse
from app.schemas.device import (
    ActuatorResponse,
    ControlActuatorRequest,
    CreateActuatorRequest,
    CreateSensorRequest,
    SensorResponse,
    UpdateActuatorRequest,
    UpdateSensorRequest,
)
from app.schemas.events import (
    ActuatorAnomalyPayload,
    ActuatorAnomalyResolvedPayload,
    ActuatorCalibrationPayload,
    ActuatorLifecyclePayload,
    ActuatorStatePayload,
    ConnectivityStatePayload,
    DeviceCommandPayload,
    DeviceLifecyclePayload,
    NotificationPayload,
    PlantGrowthWarningPayload,
    PlantLifecyclePayload,
    PlantStageUpdatePayload,
    RelayStatePayload,
    SensorReloadPayload,
    SensorUpdatePayload,
    ThresholdsUpdatePayload,
)
from app.schemas.growth import (
    CreateGrowthUnitRequest,
    CreatePlantRequest,
    GrowthUnitResponse,
    PhotoperiodConfigSchema,
    PlantResponse,
    # v3 Schedule schemas
    ScheduleCreateSchema,
    ScheduleListResponseSchema,
    ScheduleResponseSchema,
    ScheduleSummarySchema,
    ScheduleUpdateSchema,
    ThresholdSettings,
    UpdateGrowthUnitRequest,
    UpdatePlantRequest,
)
from app.schemas.health import MetricDataPoint, SystemHealthResponse
from app.schemas.irrigation import (
    IrrigationAction,
    IrrigationConfigRequest,
    IrrigationDelayRequest,
    IrrigationEligibilityTraceResponse,
    IrrigationExecutionLogResponse,
    IrrigationFeedbackRequest,
    IrrigationFeedbackResponse,
    IrrigationNotificationActionRequest,
    ManualIrrigationLogRequest,
    ManualIrrigationLogResponse,
    ManualIrrigationPredictionResponse,
)
from app.schemas.ml import (
    DiseaseRiskRequest,
    GrowthComparisonRequest,
    GrowthTransitionRequest,
    HealthObservationRequest,
    ModelActivateRequest,
    ModelCompareRequest,
    ModelType,
    RetrainingJobRequest,
    RootCauseAnalysisRequest,
    ScheduleType,
    WhatIfSimulationRequest,
)
from app.schemas.personalized import (
    ConditionProfileCard,
    ConditionProfileLinkSummary,
    ConditionProfileSection,
    ConditionProfileSelectorResponse,
)
from app.schemas.plants import (
    AddPlantToCrudRequest,
    ApplicationType,
    CreateNutrientRecordRequest,
    CreateObservationRequest,
    HarvestPlantRequest,
    ModifyPlantCrudRequest,
    NutrientType,
    ObservationType,
    PlantDiagnosisRequest,
    RecordHealthObservationRequest,
    UpdatePlantStageRequest,
)
from app.schemas.system import SystemInfoSchema

__all__ = [
    # Growth schemas
    "CreateGrowthUnitRequest",
    "UpdateGrowthUnitRequest",
    "GrowthUnitResponse",
    "CreatePlantRequest",
    "UpdatePlantRequest",
    "PlantResponse",
    "ThresholdSettings",
    # Schedule schemas (v3)
    "ScheduleCreateSchema",
    "ScheduleUpdateSchema",
    "ScheduleResponseSchema",
    "ScheduleListResponseSchema",
    "ScheduleSummarySchema",
    "PhotoperiodConfigSchema",
    # Device schemas
    "CreateSensorRequest",
    "UpdateSensorRequest",
    "SensorResponse",
    "CreateActuatorRequest",
    "UpdateActuatorRequest",
    "ActuatorResponse",
    "ControlActuatorRequest",
    # Common schemas
    "SuccessResponse",
    "ErrorResponse",
    "PaginatedResponse",
    # System schemas
    "SystemInfoSchema",
    # Health schemas
    "SystemHealthResponse",
    "MetricDataPoint",
    # Plant schemas
    "RecordHealthObservationRequest",
    "CreateObservationRequest",
    "CreateNutrientRecordRequest",
    "HarvestPlantRequest",
    "UpdatePlantStageRequest",
    "PlantDiagnosisRequest",
    "AddPlantToCrudRequest",
    "ModifyPlantCrudRequest",
    "ObservationType",
    "NutrientType",
    "ApplicationType",
    # Irrigation schemas
    "IrrigationDelayRequest",
    "IrrigationFeedbackRequest",
    "ManualIrrigationLogRequest",
    "IrrigationConfigRequest",
    "IrrigationNotificationActionRequest",
    "IrrigationExecutionLogResponse",
    "IrrigationEligibilityTraceResponse",
    "ManualIrrigationLogResponse",
    "ManualIrrigationPredictionResponse",
    "IrrigationAction",
    "IrrigationFeedbackResponse",
    # ML/AI schemas
    "DiseaseRiskRequest",
    "GrowthComparisonRequest",
    "GrowthTransitionRequest",
    "HealthObservationRequest",
    "WhatIfSimulationRequest",
    "RetrainingJobRequest",
    "ModelCompareRequest",
    "ModelActivateRequest",
    "RootCauseAnalysisRequest",
    "ScheduleType",
    "ModelType",
    # Personalized learning schemas
    "ConditionProfileCard",
    "ConditionProfileSection",
    "ConditionProfileLinkSummary",
    "ConditionProfileSelectorResponse",
    # Event payload schemas
    "SensorUpdatePayload",
    "PlantLifecyclePayload",
    "PlantStageUpdatePayload",
    "PlantGrowthWarningPayload",
    "DeviceLifecyclePayload",
    "ActuatorLifecyclePayload",
    "ActuatorAnomalyPayload",
    "ActuatorAnomalyResolvedPayload",
    "ActuatorCalibrationPayload",
    "ThresholdsUpdatePayload",
    "SensorReloadPayload",
    "RelayStatePayload",
    "DeviceCommandPayload",
    "ActuatorStatePayload",
    "ConnectivityStatePayload",
    "NotificationPayload",
]
