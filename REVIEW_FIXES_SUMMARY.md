# Review Fixes Summary

Date: 2025-12-22

This file summarizes the fixes implemented after the last-commit review (backend + frontend wiring + AI/ML modules), plus a small repo hygiene update.

## Backend fixes

### Growth API registration
- Registered the Growth API blueprint so `/api/growth/...` routes are reachable (`app/__init__.py`).

### Per-unit camera API hardening
- Added server-side, type-specific validation in the per-unit camera settings endpoint to prevent persisting invalid configs that later crash on `/camera/start` (`app/blueprints/api/growth/camera.py`).
  - `esp32`: requires `ip_address`; validates `port` and optional `resolution` framesize range (0–13).
  - `usb`: validates `device_index >= 0`.
  - `rtsp`/`mjpeg`/`http`: requires `stream_url`.
  - Validates optional image settings (`quality`, `brightness`, `contrast`, `saturation`, `flip`).
- Improved `/camera/start` error handling to return `400` for invalid configuration errors (instead of guaranteed `500`) (`app/blueprints/api/growth/camera.py`).

### Camera runtime safety + persistence
- Hardened ESP32 settings application to skip `None` values and avoid failures when the settings payload is incomplete (`app/hardware/devices/camera_manager.py`).
- Fixed and rewrote `CameraService` logic to avoid broken indentation/syntax and to validate required camera fields before constructing camera handlers (`app/services/hardware/camera_service.py`).
- Added resolution mapping so legacy string resolutions like `"640x480"` don’t get sent to the ESP32 framesize endpoint incorrectly (`app/services/hardware/camera_service.py`).

### Camera DB access moved out of services (repository/ops)
- Implemented `CameraOperations` and `CameraRepository` so camera persistence lives in `infrastructure/database/...` (no direct DB connection in `CameraService`):
  - `infrastructure/database/ops/camera.py`
  - `infrastructure/database/repositories/camera.py`
- Wired the operations mixin into the SQLite handler and ensured `camera_configs` exists (`infrastructure/database/sqlite_handler.py`).
- Updated DI to inject `CameraRepository` into `CameraService` (`app/services/container.py`, `app/services/hardware/camera_service.py`).

### AI/ML API + registry alignment
- Fixed ML model versions API bug where metadata list construction was broken, and added missing fields expected by the dashboard (`app/blueprints/api/ml_ai/models.py`).
- Implemented a real drift-summary endpoint for the dashboard (uses `drift_detector.check_drift(...)`) instead of incorrectly aliasing to drift history (`app/blueprints/api/ml_ai/models.py`).
- Added `/api/ml/models/<model>/activate` alias (frontend called `/activate` while backend had `/promote`) (`app/blueprints/api/ml_ai/models.py`).
- Extended `ModelRegistry` to support the existing list-based `models/registry.json` format and `.joblib` artifacts (and to promote “active” versions correctly) (`app/services/ai/model_registry.py`).

### PlantService compatibility for ML predictions
- Added `PlantService.get_plants_by_unit()` and `PlantService.get_all_active_plants()` wrappers used by ML prediction endpoints (`app/services/application/plant_service.py`).
- Updated active-plant query to include `plant_type` and normalized stage fields (`infrastructure/database/ops/growth.py`).

## Frontend fixes

### Devices page
- Zigbee calibration UI now correctly unwraps the `{ ok, data }` envelope and uses `data.calibration_offsets` (plus improved error handling) (`static/js/devices/data-service.js`).
- Devices camera panel now loads/saves per-unit camera settings via Growth endpoints, refreshes after save, and reacts to unit selection changes (`static/js/devices/data-service.js`, `static/js/devices/ui-manager.js`).

### ML Dashboard
- Removed duplicate `id="drift-model-select"` in the template (DOM correctness + avoids event binding ambiguity) (`templates/ml_dashboard.html`).
- Updated dashboard JS to unwrap `{ ok, data }` responses for drift metrics, model details, retrain, and activate flows (`static/js/ml_dashboard.js`).
- Updated Socket.IO client transport preference to start with polling (prevents Werkzeug websocket upgrade errors) (`static/js/ml_dashboard.js`).

### Real-time sockets
- Updated the shared Socket.IO client to prefer polling first so pages don’t try `transport=websocket` on servers that can’t handle it (`static/js/socket.js`).

## Repo hygiene
- Added database-related patterns to `.gitignore` so local SQLite artifacts and sidecar files aren’t committed (`.gitignore`).
  - Note: if `database/sysgrow.db` (or logs) were already tracked, `.gitignore` won’t untrack them; you still need `git rm --cached ...` and a commit.

## Socket.IO stability (Werkzeug)
- Defaulted Engine.IO transports to polling-only to avoid `AssertionError: write() before start_response` when clients attempt websocket upgrades on the Werkzeug dev server; override with `SYSGROW_SOCKETIO_TRANSPORTS=polling,websocket` if running under a websocket-capable server (`app/extensions.py`).
- Tightened `requirements-essential.txt` to keep `Werkzeug` `<3.0.0`, consistent with other requirement sets (`requirements-essential.txt`).

## Validation (local)
- `python3 -m compileall -q app infrastructure` passes.
- `pytest` collection fails in this environment due to missing dependency `psutil` (not addressed here because it’s an environment/package issue, not a logic regression).
