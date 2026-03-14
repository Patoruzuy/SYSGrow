"""
Irrigation Schemas
==================

Request/response schemas for irrigation workflow endpoints.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List
from enum import Enum


class IrrigationAction(str, Enum):
    """Irrigation workflow actions."""
    APPROVE = "approve"
    DELAY = "delay"
    CANCEL = "cancel"


class IrrigationFeedbackResponse(str, Enum):
    """Irrigation feedback responses."""
    TOO_LITTLE = "too_little"
    JUST_RIGHT = "just_right"
    TOO_MUCH = "too_much"
    TRIGGERED_TOO_EARLY = "triggered_too_early"
    TRIGGERED_TOO_LATE = "triggered_too_late"
    SKIPPED = "skipped"


class IrrigationDelayRequest(BaseModel):
    """Request schema for delaying irrigation."""
    delay_minutes: Optional[int] = Field(
        default=None, 
        ge=1, 
        le=1440,
        description="Minutes to delay (1-1440)"
    )


class IrrigationFeedbackRequest(BaseModel):
    """Request schema for irrigation feedback."""
    response: IrrigationFeedbackResponse = Field(
        ..., 
        description=(
            "Feedback: too_little, just_right, too_much, "
            "triggered_too_early, triggered_too_late, skipped"
        )
    )
    notes: Optional[str] = Field(default=None, description="Additional feedback notes")

    @field_validator("response", mode="before")
    @classmethod
    def normalize_response(cls, v):
        """Normalize response string to enum."""
        if isinstance(v, str):
            return IrrigationFeedbackResponse(v.lower())
        return v


class ManualIrrigationLogRequest(BaseModel):
    """Request schema for manual irrigation logging."""
    plant_id: int = Field(..., ge=1, description="Plant identifier")
    unit_id: int = Field(..., ge=1, description="Unit identifier")
    watered_at_utc: Optional[str] = Field(
        default=None,
        description="UTC timestamp for watering event (ISO-8601)",
    )
    amount_ml: Optional[float] = Field(
        default=None,
        ge=0,
        description="Water amount in ml (optional)",
    )
    notes: Optional[str] = Field(default=None, description="Optional notes")
    settle_delay_min: Optional[int] = Field(
        default=None,
        ge=1,
        le=240,
        description="Minutes to wait before post-moisture capture",
    )


class IrrigationConfigRequest(BaseModel):
    """Request schema for irrigation configuration."""
    enabled: Optional[bool] = Field(default=None, description="Enable/disable irrigation")
    notification_delay_minutes: Optional[int] = Field(
        default=None, 
        ge=0, 
        le=60,
        description="Delay before sending notification (0-60 min)"
    )
    auto_approve_delay_minutes: Optional[int] = Field(
        default=None, 
        ge=0, 
        le=120,
        description="Auto-approve after this delay (0-120 min)"
    )
    require_confirmation: Optional[bool] = Field(
        default=None, 
        description="Require user confirmation before irrigation"
    )
    threshold_moisture_min: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Minimum soil moisture threshold (%)"
    )
    threshold_moisture_max: Optional[float] = Field(
        default=None,
        ge=0,
        le=100,
        description="Maximum soil moisture threshold (%)"
    )


class IrrigationNotificationActionRequest(BaseModel):
    """Request schema for responding to irrigation notification."""
    action: IrrigationAction = Field(..., description="Action: approve, delay, cancel")
    delay_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        le=1440,
        description="Delay minutes (required for delay action)"
    )
    reason: Optional[str] = Field(default=None, description="Reason for action")

    @field_validator("action", mode="before")
    @classmethod
    def normalize_action(cls, v):
        """Normalize action string to enum."""
        if isinstance(v, str):
            return IrrigationAction(v.lower())
        return v


class IrrigationExecutionLogResponse(BaseModel):
    """Response schema for irrigation execution logs."""
    model_config = ConfigDict(extra="ignore")

    id: int
    request_id: Optional[int] = None
    unit_id: int
    plant_id: Optional[int] = None
    trigger_reason: str
    execution_status: str
    executed_at_utc: str
    planned_duration_s: Optional[int] = None
    actual_duration_s: Optional[int] = None
    estimated_volume_ml: Optional[float] = None
    post_moisture: Optional[float] = None
    delta_moisture: Optional[float] = None
    recommendation: Optional[str] = None


class IrrigationEligibilityTraceResponse(BaseModel):
    """Response schema for irrigation eligibility traces."""
    model_config = ConfigDict(extra="ignore")

    id: int
    unit_id: int
    plant_id: Optional[int] = None
    sensor_id: Optional[str] = None
    moisture: Optional[float] = None
    threshold: Optional[float] = None
    decision: str
    skip_reason: Optional[str] = None
    evaluated_at_utc: str


class ManualIrrigationLogResponse(BaseModel):
    """Response schema for manual irrigation logs."""
    model_config = ConfigDict(extra="ignore")

    id: int
    user_id: int
    unit_id: int
    plant_id: int
    watered_at_utc: str
    amount_ml: Optional[float] = None
    notes: Optional[str] = None
    pre_moisture: Optional[float] = None
    pre_moisture_at_utc: Optional[str] = None
    post_moisture: Optional[float] = None
    post_moisture_at_utc: Optional[str] = None
    settle_delay_min: Optional[int] = None
    delta_moisture: Optional[float] = None
    created_at_utc: Optional[str] = None


class ManualIrrigationPredictionResponse(BaseModel):
    """Response schema for manual irrigation predictions."""
    model_config = ConfigDict(extra="ignore")

    ok: bool
    plant_id: int
    unit_id: Optional[int] = None
    predicted_at_utc: Optional[str] = None
    hours_until_threshold: Optional[float] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None
