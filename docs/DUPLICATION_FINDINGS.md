SYSGrow — Duplication Findings

Clusters (Python)
- Response helpers duplicated across blueprints
  - app/blueprints/api/climate.py:34
  - app/blueprints/status/routes.py:13
  - app/blueprints/api/dashboard.py:13
  - app/blueprints/api/agriculture.py:44
  - app/blueprints/api/settings.py:16
  - app/blueprints/api/insights.py:31
  - app/blueprints/api/plants.py:33
  - app/blueprints/api/growth.py:41
  - app/blueprints/api/sensors.py:22
  - app/blueprints/api/devices.py:40
  - app/blueprints/api/esp32_c6.py:16
  Suggest single source: app/utils/http.py with `success_response(data, status)` and `error_response(message, status, details=None)`.

- Timestamp formatting repeated
  - widespread `datetime.now().isoformat()` in: workers/climate_controller.py:259,293,336; workers/task_scheduler.py:229,236,289; many API blueprints
  - Suggest single source: app/utils/time.py → add `iso_now()` and adopt in write-heavy paths first.

- EventBus API inconsistency
  - `infrastructure/hardware/actuators/manager.py` uses `event_bus.emit(...)` while `app/utils/event_bus.py` exposes `publish(...)` only.
  - Suggest: add `emit = publish` alias in EventBus to dedupe code changes.

- Enums duplicated (devices)
  - app/enums/device.py defines CommunicationType/SensorType/ActuatorType/...
  - infrastructure/hardware/actuators/domain.py defines ActuatorType/ActuatorState/Protocol (overlap)
  - Suggest: favor app/enums for app-facing code; infra layer maps to its own if needed. Long-term: deprecate infra enums in favor of app enums.

- Relay state event publishes duplicated
  - infrastructure/hardware/actuators/relays/{relay.py,gpio_relay.py,wifi_relay.py,wireless_relay.py}: multiple identical `publish("relay_state_changed", {...})`
  - Suggest: helper in a base class or utility function to reduce repetition.

Clusters (CSS)
- Card/layout/utilities patterns repeated across:
  - static/css/dashboard.css, static/css/units.css, static/css/settings.css, static/css/status.css
  - Consider consolidating shared `.card`, `.card-header`, `.card-actions`, grid utilities into static/css/components.css or utilities.css.

Clusters (JS)
- Notification/snackbar patterns repeated in static/js/* (e.g., plant_health.js)
  - Suggest: small notification helper exported from a shared module.

Suggested Single Sources
- app/utils/http.py — JSON response helpers (success/error) + typing with app/schemas/common.py
- app/utils/time.py — `iso_now()`, `format_time(dt, fmt)`, `utc_now()`
- app/utils/event_bus.py — standardized API (`subscribe/publish/emit`) and typed topic support
- app/enums/events.py — canonical event topics; adopt incrementally

