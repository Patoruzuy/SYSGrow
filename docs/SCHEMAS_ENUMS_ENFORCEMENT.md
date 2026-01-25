SYSGrow — Schemas/Enums Enforcement

Policy
- Replace magic string topics with enums from `app/enums/*`.
- Replace raw dict request/response payloads with Pydantic models from `app/schemas/*`.
- Validate at boundaries (blueprints/services), keep internals typed.

Current Findings (based on latest code)
- Devices API (enums + schemas)
  - `app/blueprints/api/devices.py` now imports `SensorType` and `CommunicationType` from `app.enums.device` and uses them when deriving communication modes and sensor types.
  - A typed `/v2/sensors` endpoint validates payloads via `app.schemas.device.CreateSensorRequest` before delegating to `DeviceService`, while the legacy `/sensors` endpoint remains for backwards compatibility with string-based payloads.

- Growth API (HTTP helpers + thresholds)
  - `app/blueprints/api/growth.py` imports `success_response` and `error_response` from `app.utils.http` and delegates `_success/_fail` to these shared helpers.
  - Threshold endpoints validate and normalize payloads using `UnitThresholdUpdate` and `ThresholdSettings` from `app.schemas.growth`, replacing earlier manual casting.

- Event publishing (enums + Pydantic payloads)
  - `app/services/device_service.py` publishes `DeviceEvent.*` topics with Pydantic payloads from `app.schemas.events` (e.g. `DeviceLifecyclePayload`, `ActuatorAnomalyPayload`, `ActuatorAnomalyResolvedPayload`, `ActuatorCalibrationPayload`).
  - `workers/sensor_polling_service.py` now routes sensor updates via `SensorEvent.for_type(...)` and publishes `SensorUpdatePayload` instances through the `EventBus`, instead of raw string topics and dicts.
  - `workers/climate_controller.py`, `app/models/unit_runtime.py`, and `infrastructure/hardware/actuators/*` subscribe to these enum topics and receive normalized dict payloads via the EventBus.

- Remaining gaps / legacy patterns
  - `app/models/plant_profile.py` still uses dynamic per-plant topics like `f"plant_stage_update_{self.id}"` and `f"growth_warning_{self.id}"` with dict payloads for local warnings, while also publishing canonical `PlantEvent.PLANT_STAGE_UPDATE` events with `PlantStageUpdatePayload`.
  - These dynamic topics are intentionally scoped but could be backed by enums and typed payloads (e.g. `PlantLifecyclePayload`) for consistency, keeping dynamic aliases as needed for backwards compatibility.

Checklist
- [x] Replace raw device/sensor strings in API with `app/enums/device.py` (major endpoints now use `SensorType`/`CommunicationType`; legacy v1 endpoints kept for compatibility)
- [x] Swap inline `_success/_fail` for `app/utils/http.py` helpers across API blueprints
- [x] Validate thresholds via `app/schemas/growth.py` (`UnitThresholdUpdate` / `ThresholdSettings`)
- [x] Publish core event payloads with Pydantic models from `app/schemas/events.py`
- [ ] Migrate remaining plant-specific dynamic topics (`plant_stage_update_*`, `growth_warning_*`) to canonical enums in `app/enums/events.py` or explicitly bless them as local-only aliases
