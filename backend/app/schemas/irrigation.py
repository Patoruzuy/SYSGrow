"""
Irrigation Schemas
==================

Request/response schemas for irrigation workflow endpoints.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    delay_minutes: int | None = Field(default=None, ge=1, le=1440, description="Minutes to delay (1-1440)")


class IrrigationFeedbackRequest(BaseModel):
    """Request schema for irrigation feedback."""

    response: IrrigationFeedbackResponse = Field(
        ...,
        description=("Feedback: too_little, just_right, too_much, triggered_too_early, triggered_too_late, skipped"),
    )
    notes: str | None = Field(default=None, description="Additional feedback notes")

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
    watered_at_utc: str | None = Field(
        default=None,
        description="UTC timestamp for watering event (ISO-8601)",
    )
    amount_ml: float | None = Field(
        default=None,
        ge=0,
        description="Water amount in ml (optional)",
    )
    notes: str | None = Field(default=None, description="Optional notes")
    settle_delay_min: int | None = Field(
        default=None,
        ge=1,
        le=240,
        description="Minutes to wait before post-moisture capture",
    )


class IrrigationConfigRequest(BaseModel):
    """Request schema for irrigation configuration."""

    enabled: bool | None = Field(default=None, description="Enable/disable irrigation")
    notification_delay_minutes: int | None = Field(
        default=None, ge=0, le=60, description="Delay before sending notification (0-60 min)"
    )
    auto_approve_delay_minutes: int | None = Field(
        default=None, ge=0, le=120, description="Auto-approve after this delay (0-120 min)"
    )
    require_confirmation: bool | None = Field(default=None, description="Require user confirmation before irrigation")
    threshold_moisture_min: float | None = Field(
        default=None, ge=0, le=100, description="Minimum soil moisture threshold (%)"
    )
    threshold_moisture_max: float | None = Field(
        default=None, ge=0, le=100, description="Maximum soil moisture threshold (%)"
    )


class IrrigationNotificationActionRequest(BaseModel):
    """Request schema for responding to irrigation notification."""

    action: IrrigationAction = Field(..., description="Action: approve, delay, cancel")
    delay_minutes: int | None = Field(
        default=None, ge=1, le=1440, description="Delay minutes (required for delay action)"
    )
    reason: str | None = Field(default=None, description="Reason for action")

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
    request_id: int | None = None
    unit_id: int
    plant_id: int | None = None
    trigger_reason: str
    execution_status: str
    executed_at_utc: str
    planned_duration_s: int | None = None
    actual_duration_s: int | None = None
    estimated_volume_ml: float | None = None
    post_moisture: float | None = None
    delta_moisture: float | None = None
    recommendation: str | None = None


class IrrigationEligibilityTraceResponse(BaseModel):
    """Response schema for irrigation eligibility traces."""

    model_config = ConfigDict(extra="ignore")

    id: int
    unit_id: int
    plant_id: int | None = None
    sensor_id: str | None = None
    moisture: float | None = None
    threshold: float | None = None
    decision: str
    skip_reason: str | None = None
    evaluated_at_utc: str


class ManualIrrigationLogResponse(BaseModel):
    """Response schema for manual irrigation logs."""

    model_config = ConfigDict(extra="ignore")

    id: int
    user_id: int
    unit_id: int
    plant_id: int
    watered_at_utc: str
    amount_ml: float | None = None
    notes: str | None = None
    pre_moisture: float | None = None
    pre_moisture_at_utc: str | None = None
    post_moisture: float | None = None
    post_moisture_at_utc: str | None = None
    settle_delay_min: int | None = None
    delta_moisture: float | None = None
    created_at_utc: str | None = None


class ManualIrrigationPredictionResponse(BaseModel):
    """Response schema for manual irrigation predictions."""

    model_config = ConfigDict(extra="ignore")

    ok: bool
    plant_id: int
    unit_id: int | None = None
    predicted_at_utc: str | None = None
    hours_until_threshold: float | None = None
    confidence: float | None = None
    reason: str | None = None
