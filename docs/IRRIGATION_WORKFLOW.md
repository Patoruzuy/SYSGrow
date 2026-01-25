# Irrigation Workflow System

## Overview

The irrigation workflow provides a production-safe approval pipeline with diagnostics, manual mode support, and non-blocking execution. It creates pending requests when soil moisture drops below threshold, captures eligibility traces for every evaluation, and uses scheduled jobs to execute irrigation without blocking. Telemetry is written at each step to explain "why it did or did not water" and to separate volume vs. threshold issues.

All timestamps are stored as UTC ISO-8601 strings with timezone (+00:00).

## End-to-End Flow

```
Sensor Reading
     │
     ▼
Eligibility Check (records IrrigationEligibilityTrace)
     │
     ├── manual_mode_enabled → decision=skip (manual_mode_no_auto)
     │
     ├── no sensor / stale / cooldown / disabled → decision=skip
     │
     └── below threshold → create PendingIrrigationRequest
                 │
                 ▼
          Send Notification
                 │
                 ▼
         User Response?
        (approve/delay/cancel)
                 │
                 ▼
        Scheduler claim_due_requests()
                 │
                 ▼
        Acquire unit lock (IrrigationLock)
                 │
                 ▼
        Open valve (if configured)
                 │
                 ▼
        Start pump (non-blocking duration)
                 │
                 ▼
      Write IrrigationExecutionLog (started)
                 │
                 ▼
   Completion job stops pump / closes valve
                 │
                 ▼
      Update IrrigationExecutionLog (completed/failed)
                 │
                 ▼
   Post-capture job reads moisture after delay
                 │
                 ▼
    Update log + attribution recommendation
                 │
                 ▼
         Request user feedback
                 │
                 ▼
   Volume adjustment / threshold learning
```

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| `IrrigationWorkflowService` | `app/services/application/irrigation_workflow_service.py` | Core request lifecycle, execution, telemetry, attribution |
| `ManualIrrigationService` | `app/services/application/manual_irrigation_service.py` | Manual mode logging + post-capture |
| `PlantIrrigationModelService` | `app/services/application/plant_irrigation_model_service.py` | Dry-down model + prediction |
| `IrrigationPredictor` | `app/services/ai/irrigation_predictor.py` | ML/rule-based predictions |
| `PumpCalibrationService` | `app/services/hardware/pump_calibration.py` | Flow rate estimation |
| `ActuatorManager` | `app/hardware/actuators/manager.py` | Pump/valve actuation |
| `SchedulingService` | `app/services/hardware/scheduling_service.py` | Interval jobs for completion and post-capture |
| `IrrigationWorkflowRepository` | `infrastructure/database/repositories/irrigation_workflow.py` | Data access + locks + claim logic |
| `ControlLogic` | `app/services/hardware/control_logic.py` | Triggers detection callbacks |
| Irrigation API | `app/blueprints/api/irrigation/__init__.py` | REST endpoints |

## Database Tables

- `PendingIrrigationRequest` (status, scheduled time, execution_duration, claim metadata)
- `IrrigationWorkflowConfig` (per-unit settings incl. manual_mode_enabled)
- `IrrigationUserPreference` (feedback counts + threshold belief state)
- `IrrigationExecutionLog` (telemetry, estimated volume, post moisture, recommendation)
- `IrrigationEligibilityTrace` (explain "why no notification")
- `ManualIrrigationLog` (manual watering events + pre/post moisture)
- `PlantIrrigationModel` (dry-down rate + confidence)
- `IrrigationLock` (unit-level concurrency lock)

## Request State

### Request Status (`PendingIrrigationRequest.status`)

| Status | Meaning |
|--------|---------|
| `pending` | Awaiting user response |
| `approved` | Approved; waiting for scheduled time |
| `delayed` | Delayed to a new time |
| `executed` | Irrigation finished |
| `cancelled` | User cancelled |
| `expired` | No response within expiration window |
| `failed` | Execution failed |

### Execution Status (`PendingIrrigationRequest.execution_status`)

| Status | Meaning |
|--------|---------|
| `executing` | Claimed and running (non-blocking) |

Execution outcomes are written to `IrrigationExecutionLog.execution_status` (`started`, `completed`, `failed`).

## Scheduler Jobs

- `irrigation_due_check` (interval) → claims due requests
- `irrigation_execution_completion` (interval) → closes executions without blocking
- `irrigation_post_capture` (interval) → post-watering moisture capture + attribution
- `manual_irrigation_post_capture` (interval) → manual mode post-capture

## Concurrency & Non-Blocking Execution

- `claim_due_requests()` updates eligible requests in a single transaction and marks them `execution_status=executing`.
- A unit lock (`IrrigationLock`) prevents concurrent watering in the same unit.
- Pump control is non-blocking; completion is handled by scheduled jobs (no `sleep()` in workflow).

## Telemetry & Attribution

- `IrrigationExecutionLog` is created at execution start, updated on completion, then augmented with post-capture moisture and a recommendation:
  - `adjust_duration` for volume overshoot/undershoot
  - `adjust_threshold` for timing/threshold issues
  - `sensor_issue` or `unknown` when data is insufficient
- `IrrigationEligibilityTrace` records every evaluation (notify vs. skip + skip_reason).
- Telemetry can be viewed in the Dashboard Irrigation panel (24h / 7d / 30d ranges).

## Manual Mode (Sensor-Only)

When `manual_mode_enabled=True`, automation is skipped and eligibility tracing records `manual_mode_no_auto`. Users log watering events via `/api/irrigation/manual/log`, and the system:

- attaches nearest pre-moisture
- schedules post-capture
- updates `ManualIrrigationLog`
- updates `PlantIrrigationModel` dry-down rate
- can compute a predicted “next irrigation time”

## Valve + Pump Safety Sequence

1. Acquire unit lock
2. Open valve (if configured)
3. Start pump for duration (non-blocking)
4. Stop pump (or let duration expire)
5. Close valve
6. Always attempt stop/close on exceptions

Pump never runs if valve open fails. A max duration cap prevents runaway irrigation.

## Feedback & Learning

Supported feedback:
- `too_little`, `just_right`, `too_much`
- `triggered_too_early`, `triggered_too_late`

Learning behavior:
- Volume feedback updates duration adjustments
- Timing feedback (and attribution recommending `adjust_threshold`) drives threshold learning
- Bayesian threshold updates are used when enabled; fallback is fixed ±5%
- Volume feedback can also map to threshold adjustments when post-moisture is within the target band.

## Configuration & Tuning

`WorkflowConfig` fields (per unit):
- `workflow_enabled`, `auto_irrigation_enabled`, `manual_mode_enabled`
- `require_approval`, `default_scheduled_time`
- `delay_increment_minutes`, `max_delay_hours`, `expiration_hours`
- `request_feedback_enabled`, `feedback_delay_minutes`
- `ml_learning_enabled`, `ml_threshold_adjustment_enabled`

Env overrides (global):
- `SYSGROW_IRRIGATION_COMPLETION_INTERVAL_SECONDS`
- `SYSGROW_IRRIGATION_POST_CAPTURE_INTERVAL_SECONDS`
- `SYSGROW_IRRIGATION_POST_CAPTURE_DELAY_SECONDS`
- `SYSGROW_IRRIGATION_MAX_DURATION_SECONDS`
- `SYSGROW_IRRIGATION_HYSTERESIS`
- `SYSGROW_IRRIGATION_STALE_READING_SECONDS`
- `SYSGROW_IRRIGATION_COOLDOWN_MINUTES`

Defaults (current):
- `SYSGROW_IRRIGATION_STALE_READING_SECONDS` = 1800 (30 min)
- `SYSGROW_IRRIGATION_COOLDOWN_MINUTES` = 60

## API Endpoints

```
GET  /api/irrigation/requests
GET  /api/irrigation/requests/<id>
POST /api/irrigation/requests/<id>/approve
POST /api/irrigation/requests/<id>/delay
POST /api/irrigation/requests/<id>/cancel
POST /api/irrigation/requests/<id>/feedback
POST /api/irrigation/manual/log
GET  /api/irrigation/executions/<unit_id>
GET  /api/irrigation/eligibility/<unit_id>
GET  /api/irrigation/manual/<unit_id>
GET  /api/irrigation/manual/predict/<plant_id>
GET  /api/irrigation/history/<unit_id>
GET  /api/irrigation/config/<unit_id>
PUT  /api/irrigation/config/<unit_id>
GET  /api/irrigation/preferences
```

ML predictions:
```
GET /api/ml/predictions/irrigation/<unit_id>/next
```

## Notification Flow

1. Detection creates request + sends notification
2. User response updates status (approve/delay/cancel)
3. Execution runs at scheduled time; completion + post-capture jobs finalize
4. Feedback request is sent if enabled
