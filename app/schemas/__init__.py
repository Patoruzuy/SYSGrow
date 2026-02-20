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
    "ActuatorAnomalyPayload",
    "ActuatorAnomalyResolvedPayload",
    "ActuatorCalibrationPayload",
    "ActuatorLifecyclePayload",
    "ActuatorResponse",
    "ActuatorStatePayload",
    "AddPlantToCrudRequest",
    "ApplicationType",
    # Personalized learning schemas
    "ConditionProfileCard",
    "ConditionProfileLinkSummary",
    "ConditionProfileSection",
    "ConditionProfileSelectorResponse",
    "ConnectivityStatePayload",
    "ControlActuatorRequest",
    "CreateActuatorRequest",
    # Growth schemas
    "CreateGrowthUnitRequest",
    "CreateNutrientRecordRequest",
    "CreateObservationRequest",
    "CreatePlantRequest",
    # Device schemas
    "CreateSensorRequest",
    "DeviceCommandPayload",
    "DeviceLifecyclePayload",
    # ML/AI schemas
    "DiseaseRiskRequest",
    "ErrorResponse",
    "GrowthComparisonRequest",
    "GrowthTransitionRequest",
    "GrowthUnitResponse",
    "HarvestPlantRequest",
    "HealthObservationRequest",
    "IrrigationAction",
    "IrrigationConfigRequest",
    # Irrigation schemas
    "IrrigationDelayRequest",
    "IrrigationEligibilityTraceResponse",
    "IrrigationExecutionLogResponse",
    "IrrigationFeedbackRequest",
    "IrrigationFeedbackResponse",
    "IrrigationNotificationActionRequest",
    "ManualIrrigationLogRequest",
    "ManualIrrigationLogResponse",
    "ManualIrrigationPredictionResponse",
    "MetricDataPoint",
    "ModelActivateRequest",
    "ModelCompareRequest",
    "ModelType",
    "ModifyPlantCrudRequest",
    "NotificationPayload",
    "NutrientType",
    "ObservationType",
    "PaginatedResponse",
    "PhotoperiodConfigSchema",
    "PlantDiagnosisRequest",
    "PlantGrowthWarningPayload",
    "PlantLifecyclePayload",
    "PlantResponse",
    "PlantStageUpdatePayload",
    # Plant schemas
    "RecordHealthObservationRequest",
    "RelayStatePayload",
    "RetrainingJobRequest",
    "RootCauseAnalysisRequest",
    # Schedule schemas (v3)
    "ScheduleCreateSchema",
    "ScheduleListResponseSchema",
    "ScheduleResponseSchema",
    "ScheduleSummarySchema",
    "ScheduleType",
    "ScheduleUpdateSchema",
    "SensorReloadPayload",
    "SensorResponse",
    # Event payload schemas
    "SensorUpdatePayload",
    # Common schemas
    "SuccessResponse",
    # Health schemas
    "SystemHealthResponse",
    # System schemas
    "SystemInfoSchema",
    "ThresholdSettings",
    "ThresholdsUpdatePayload",
    "UpdateActuatorRequest",
    "UpdateGrowthUnitRequest",
    "UpdatePlantRequest",
    "UpdatePlantStageRequest",
    "UpdateSensorRequest",
    "WhatIfSimulationRequest",
]
