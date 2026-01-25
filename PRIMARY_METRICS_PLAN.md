# Primary Metrics Ownership Plan

## Goals
- Make primary dashboard metrics explicitly assigned per sensor.
- Prevent multiple sensors in the same unit from owning the same metric.
- Provide UI to select, resolve conflicts, and edit primary metrics.
- Remove derived metrics from dashboard ownership choices.

## Scope
- Backend validation, persistence, and conflict resolution endpoints.
- Sensor processing pipeline to respect primary metrics.
- DB migration and cleanup for existing data.
- UI wiring for selection and edit flows.

## Plan (with status)

### 1) Standardize sensor field handling in the pipeline
- [x] Consolidate field standardization into `TransformationProcessor` and use standardized data downstream.
- [x] Update `PriorityProcessor` to use standardized fields and only assign first primary when the metric is actually primary for that sensor.
- [x] Fix soil sensors incorrectly claiming temperature/humidity via priority selection logic and event gating.

### 2) Add primary metrics configuration support in the API and schemas
- [x] Extend request/response schemas to carry `primary_metrics`.
  - [x] Update request/response shapes in [app/schemas/device.py](app/schemas/device.py).
  - [x] Include `primary_metrics` in API response mapping in [app/blueprints/api/devices/utils.py](app/blueprints/api/devices/utils.py).
- [x] Persist primary metrics on create/update in [app/blueprints/api/devices/sensors.py](app/blueprints/api/devices/sensors.py).
- [x] Add conflict detection and normalized input handling in [app/blueprints/api/devices/sensors.py](app/blueprints/api/devices/sensors.py).
- [x] Add endpoints for conflict resolution and patching primary metrics in [app/blueprints/api/devices/sensors.py](app/blueprints/api/devices/sensors.py).
- [x] Add config upsert support in [infrastructure/database/ops/devices.py](infrastructure/database/ops/devices.py) and [infrastructure/database/repositories/devices.py](infrastructure/database/repositories/devices.py).

### 3) Data migration + cleanup
- [x] Add migration to set default primary metrics for existing sensors in [infrastructure/database/migrations/056_set_sensor_primary_metrics.py](infrastructure/database/migrations/056_set_sensor_primary_metrics.py).
- [x] Add cleanup script to remove invalid rows for soil sensor temp/humidity in [scripts/cleanup_soil_temp_humidity.py](scripts/cleanup_soil_temp_humidity.py) and execute it.

### 4) Zigbee2MQTT mapping reliability
- [x] Add payload-based Zigbee2MQTT mapping when friendly_name is missing in [app/services/hardware/mqtt_sensor_service.py](app/services/hardware/mqtt_sensor_service.py).

### 5) Dashboard metric ownership list
- [x] Remove derived metrics from dashboard ownership list in [app/hardware/sensors/processors/utils.py](app/hardware/sensors/processors/utils.py).

### 6) UI — primary metrics selection for Zigbee add flow
- [x] Add primary metrics selection section in [templates/devices.html](templates/devices.html).
- [x] Add styles for selection grid and conflict modal in [static/css/devices.css](static/css/devices.css).
- [x] Wire selection rendering, defaults, and conflict handling in [static/js/devices/ui-manager.js](static/js/devices/ui-manager.js).
- [x] Add client support for conflict error details and new endpoints in [static/js/api.js](static/js/api.js) and [static/js/devices/data-service.js](static/js/devices/data-service.js).

### 7) UI — edit primary metrics for existing sensors
- [x] Add Edit Primary Metrics action in [templates/devices.html](templates/devices.html).
- [x] Add edit modal markup in [templates/devices.html](templates/devices.html).
- [x] Wire edit flow + conflict resolution for updates in [static/js/devices/ui-manager.js](static/js/devices/ui-manager.js).

### 8) Validation & follow-ups
- [ ] Verify UI behavior end-to-end:
  - [ ] Add Zigbee sensor with preselected metrics.
  - [ ] Trigger conflict dialog and confirm unassign flow.
  - [ ] Edit existing sensor primary metrics and resolve conflicts if needed.
- [ ] Confirm non-Zigbee sensor add/edit flows remain unaffected.
- [ ] Review UI copy and any missing labels for metrics.

### 9) UI sensor card editor (plan)
- [ ] Add an editable sensor card in the Zigbee sensor list with:
  - [ ] Friendly name display + inline edit.
  - [ ] Sensor metadata section (model, manufacturer, IEEE, unit, protocol, last seen).
  - [ ] Primary metrics chips + edit action (opens modal).
  - [ ] Save/cancel actions + optimistic UI update.
- [ ] API wiring for sensor updates:
  - [ ] Add endpoint to update friendly name / metadata (if not already available).
  - [ ] Reuse existing `PATCH /v2/sensors/<id>/primary-metrics` for primary metrics.
- [ ] Validation & UX:
  - [ ] Disable metrics already claimed by other sensors in the unit.
  - [ ] Conflict dialog for primary metrics (reuse existing modal).
  - [ ] Inline error states (server errors and validation).
- [ ] Data refresh:
  - [ ] Update local cache state after save.
  - [ ] Refresh card contents without full page reload.

## Notes / Decisions
- Primary metric claims are per unit; conflicts return 409 with details for conflict resolution.
- Default primary metrics:
  - Environment sensors: temperature, humidity, co2, lux, voc, smoke, pressure, air_quality.
  - Plant sensors: soil_moisture, ph, ec.

## Current Status Summary
Most core backend and UI wiring is complete. Remaining work is verification and any polish based on testing results.
