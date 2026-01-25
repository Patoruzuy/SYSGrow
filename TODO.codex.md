# SYSGrow Backend – Remaining TODOs

This checklist captures only what is *left* to do after the recent CSS, theming, dark mode, API, and legacy‑cleanup work.

---

## 1) Backend & API follow‑ups

- [ ] **End‑to‑end verification**
  - [ ] Run the full test suite after the GrowthService/UnitRuntime/settings/UI changes (MQTT disabled, temp DB) – all green.
  - [ ] Fi  regressions around `list_units`, `get_unit`, settings persistence, and sensor history decoding for the new `reading_data` schema.

- [ ] **Optional UI hooks for v2 device APIs**
  - [ ] Add small UI flows (e.g. in `templates/devices.html` or settings) that call:
    - `POST /api/devices/v2/sensors`
    - `POST /api/devices/v2/actuators`

---

## 2) Legacy light schedule cleanup

The code now uses `device_schedules` as the source of truth. What’s left is DB/data hygiene.

- [ ] Verify all persisted units in the production database use `device_schedules` instead of `light_start_time` / `light_end_time`.
      - Use `python scripts/verify_light_schedule_cleanup.py --db <path>` to confirm columns are gone and schedules populated.
- [ ] After that verification:
  - [ ] Drop the `light_start_time` and `light_end_time` columns from `GrowthUnits` (via a migration).
  - [ ] Remove any remaining references to those columns in `infrastructure/database/ops/growth.py` and related analytics/helpers.

---

## 3) AI/ThresholdService rollout

`UnitRuntime.apply_ai_conditions` now relies solely on `ThresholdService` and no longer falls back to AI‑only behavior. The remaining work is operational rollout and deprecation.

- [ ] Ensure `ThresholdService` is deployed/enabled in all production environments where plant‑specific thresholds are required.
- [ ] Review `AIClimateModel` usage:
  - [ ] Identify any remaining entry points that still construct or depend on `AIClimateModel`. We will keep using 'AIClimateModel', so we will not remove the AI- logic
  - [ ] Modernize call sites to go through `ThresholdService` (container now gates AI model creation; UnitRuntime consumes the shared instance instead of constructing its own).

---

## 4) V1 → V2 API migration plan

Typed v2 endpoints now e ist for growth units, sensors, and actuators (read + create). Legacy v1 endpoints are still active and in use.

- [ ] Inventory all v1 endpoints under:
  - [ ] `/api/growth/*` (growth units & thresholds).
  - [ ] `/api/devices/*` (sensor/actuator/device config).
      - See docs/api_v1_inventory.md for current list and v2 coverage.
- [ ] For each v1 endpoint:
  - [ ] Confirm whether it is still called by the UI or e ternal clients.
  - [ ] Provide a v2 equivalent using the e isting Pydantic schemas if one does not already e ist. (Progress: added v2 growth create/update/delete/thresholds/schedules and per-unit/device deletes; analytics/config/zigbee still v1.)
- [ ] Deprecation strategy:
  - [ ] Add logging or metrics to track v1 endpoint usage in production.
  - [ ] Document v1 deprecation in README/docs and communicate to any e ternal consumers.
  - [ ] Once v1 usage is near‑zero, remove v1 routes and any code paths unique to them.

---

## 5) Hardware/ops follow‑ups

Sensor drivers now use structured logging instead of `print`, but there are still a couple of ops decisions to close out.

- [ ] Confirm there are no remaining hardware/debug scripts that should be moved under `scripts/` and documented (or removed if obsolete).
- [ ] Decide logging levels for sensor drivers (INFO vs DEBUG for init/cleanup and WARN/ERROR for retries/failures) and tune as needed in production logs. (Documented in docs/ops_sensor_logging.md; uses SYSGROW_LOG_LEVEL)


## 6) CSS
- [ ] Add transparency to the buttons and containers
- [ ] Adjust the hover effects on buttons to have a more subtle transition
- [ ] Standardize color schemes across different components for a cohesive look
- [ ] Improve spacing between elements for better readability
- [ ] Ensure all interactive elements have appropriate focus states for accessibility
- [ ] Ensure consistent padding and margin across all sections and components
- [ ] Review font sizes and styles for better readability
- [ ] Optimize the layout for different screen sizes to ensure responsiveness
- [ ] Implement smooth scrolling for better user experience
- [ ] Add animations or transitions to enhance interactivity
- [ ] Test the CSS across different browsers to ensure compatibility

## 7) Data graph
- [ ] Review data tables (sensors, readings JSON, plant health/history) and propose dashboard graphs.
- [ ] Add interactive Sensor Data Graphs page with multi-metric chart, plant overlay, and timeseries API.
- [ ] Add pagination or “load more” for Recent Points beyond the current 10 rows.
- [ ] Improve tick density/format for long ranges (day boundaries labels).
- [ ] Hook alert builder/personalization (saved views/layouts) per plan.
- [ ] Add backend downsampling and caching for large ranges; e pose unit/sensor names directly in timeseries payload to avoid e tra lookups on the client.
- [ ] Verify plant dropdown populates in all environments (primary + fallback plants API; ensure DB has plants and server restart).

## 8) Sensor polling robustness
- [ ] Bound the EventBus with a worker queue (env-tunable) and e posed queue depth/dropped metrics for health checks.
- [ ] Added per-sensor GPIO backoff plus MQTT rate limiting/coalescing with last-known cache and health snapshot wiring.
- [ ] Add smoke/integration tests for MQTT coalescing/backoff (especially soil moisture) to guard the new flow.
- [ ] Surface the new polling health snapshot through an API/health endpoint or ops dashboard.
- [ ] Tune env knobs (`SYSGROW_EVENTBUS_WORKERS`, `SYSGROW_EVENTBUS_QUEUE_SIZE`, `SYSGROW_MQTT_RATE_LIMIT_SEC`, `SYSGROW_SENSOR_BACKOFF_*`) in staging based on real device throughput (ops.env.e ample added for baseline; see docs/ops_sensor_polling_tuning.md for steps).


  To hook your ops dashboard:

  1. Point your scrape to GET /status/ops for lightweight panels (queue/backoff/stale counts); use /api/dashboard/health
     for drilldowns.
  2. Use python scripts/ops_health_probe.py --base http://<host>:<port> --endpoint /status/ops as a quick feed or to
     validate dashboards.
  3. Apply ops.env.e ample values in staging (SYSGROW_EVENTBUS_QUEUE_SIZE=2048, etc.), watch queue/dropped/backoff
     metrics, then lock tuned values in your deployment config.

## 9) Dashboard redesign (tracking notes)
- [ ] E tract the new dark card-based dashboard styles from `templates/inde .html` into a CSS asset and keep class names stable for `dashboard.js` hooks.
- [ ] Wire the unit/plant/time-range selects into the dashboard data loaders (currently placeholders mirroring the Data Graph filters).
- [ ] Quick sanity: verify responsive behavior and a11y labels; adjust spacing/contrast if needed.
## Summary of what have been done yesterday and what it left to do:
• - Added typed v2 read endpoints:
      - GET /api/growth/v2/units in app/blueprints/api/growth.py:80 now returns a list of GrowthUnitResponse models
      - GET /api/devices/v2/sensors and GET /api/devices/v2/actuators in app/blueprints/api/devices.py:40 map
        DeviceService.list_sensors() / list_actuators() into SensorResponse and ActuatorResponse lists, while keeping
        the v1 list endpoints unchanged.
  - Updated UnitRuntime persistence and legacy hooks:
      - _save_to_database in app/models/unit_runtime.py:885 now uses GrowthRepository.update_unit_settings(self.unit_id,
        self.settings.to_dict()) instead of recreating units with deprecated light_start_time/light_end_time, fully
        aligning with the new device_schedules-based schema.
      - Confirmed the legacy migration from light_start_time/light_end_time to device_schedules is removed from both
        UnitSettings.from_dict and its test mirror in tests/test_device_schedules.py:18.
  - Wired UI behavior to the recommended-thresholds API:
      - Added a “Suggest Thresholds” button ne t to the environment form submit in templates/settings.html:104 and
        a corresponding click handler in the footer script (templates/settings.html:1378) that calls /api/growth/
        thresholds/recommended?plant_type=Tomatoes&growth_stage=Vegetative, then populates the temperature, humidity,
        and soil moisture fields with returned values and shows a flash message.
  - Completed typed endpoint and UI items in the checklist:
      - Marked the v2 read endpoints (growth units, sensors, actuators) and the UI wiring for the recommended-thresholds
        endpoint as done in TODO.code .md:126, leaving only migration-oriented work (DB column removal, AIClimateModel
        deprecation, v1 endpoint inventory/removal, and full test-suite verification) as future cleanup tasks.
          - TODO.code .md is not 100% finished, but the big blocks you asked for are:
      - CSS/Theming/Accessibility: all theme consistency, page checks, dark mode, and accessibility checklist items are
        marked complete.
      - Backend tests & typed endpoints: tests for the recommended-thresholds and v2 device APIs are in place, v2 read
        endpoints for growth units/sensors/actuators are implemented, and the “Suggest thresholds” UI wiring is done.
      - Legacy cleanup: dynamic plant event topics, light-schedule migration inside UnitRuntime, AI-only fallback in
        apply_ai_conditions, and sensor-driver print diagnostics are all removed.
  - What remains in TODO.code .md are mainly migration/operational tasks:
      - Verifying all persisted units use device_schedules and then deleting the legacy DB columns and helpers.
      - Ensuring ThresholdService is deployed everywhere and deciding how to deprecate or trim AIClimateModel.
      - Inventorying which v1 endpoints are still called by real clients, introducing any missing v2 equivalents, and
        then planning deprecation/removal.
      - Running the full test suite after all these changes and fi ing any regressions.
• Sensor history endpoints/services now decode both legacy column shapes and the newer `reading_data` JSON payload, and tests insert/read both forms successfully.

---

## 10) Zigbee2MQTT & ESP32-C6 fi es
- [  ] Fi ed Zigbee service to accept pre-connected MQTT client from Container without calling connect/loop_start/loop_stop.
- [  ] Subscribed to zigbee2mqtt topics in ZigbeeService.__init__ using the pre-connected client.
- [  ] Used threading.Event to synchronize MQTT connection state instead of time.sleep.
- [  ] Improved error handling in ZigbeeService and API blueprint for device discovery.
- [  ] Clarified frontend settings UI to distinguish between native Zigbee2MQTT devices and ESP32-C6-based Zigbee devices.
- [  ] Tested end-to-end device discovery and addition for both Zigbee2MQTT and ESP32-C6 scenarios.
- [  ] Updated documentation with deployment checklist and troubleshooting steps.


## 11) Frontend – Dark mode & theming
- [ ] Verified all pages/components use the new CSS variables for colors, spacing, and fonts.
- [ ] Ensured dark mode toggle works across all pages, with no visual glitches.
- [ ] Checked accessibility compliance (contrast ratios, font sizes) in both light and dark modes.
- [ ] Updated any custom styles in `static/css/` to align with the new theming system.
- [ ] Tested responsiveness and layout consistency across different screen sizes and devices.
- [ ] Reviewed and cleaned up any deprecated CSS classes or styles.
- [ ] Documented the theming system and dark mode implementation for future reference.
- [ ] Added unit tests for critical UI components to ensure theme consistency.

## 12) Frontend – Plant health monitoring UI
- [ ] Created `PlantHealthService` in `lib/services/plant_health_service.dart` to interact with the backend API.
- [ ] Developed `PlantHealthScreen` in `lib/ui/screens/plant_health_screen.dart` to display real-time plant health metrics.
- [ ] Built `HealthHistoryScreen` in `lib/ui/screens/health_history_screen.dart` for viewing historical data and trends.
- [ ] Added `HealthRecommendationsWidget` in `lib/ui/widgets/health_recommendations_widget.dart` to show actionable insights based on plant health data.
- [ ] Tested the entire flow from data retrieval to UI rendering, ensuring smooth user e perience.

## 13) Frontend – Sensor data graph
- [ ] Implemented interactive Sensor Data Graphs page with multi-metric charting capabilities.
- [ ] Added plant overlay feature to visualize plant growth stages alongside sensor data.
- [ ] Developed timeseries API endpoint to support frontend data requests.
- [ ] Integrated pagination and “load more” functionality for recent data points.
- [ ] Enhanced tick density and formatting for long-range data views.

## 14) Review the code structure and organization
- [x] Review Mixed concerns, No clear sections, Duplicate endpoints and Modularization
- [x] Reviewed the directory structure for logical grouping of modules and services.
- [x] Ensured that each module has a single responsibility and clear interfaces.
- [x] Reviewed the overall project structure to ensure modular organization.
- [x] Verified that backend services, models, and blueprints are logically separated.
- [x] Ensured that frontend components, services, and screens follow a consistent naming convention.
- [x] Checked that utility functions and shared resources are appropriately placed for easy access. 
- [x] Confirmed that documentation is up-to-date with the latest code changes.
- [x] Ensured that tests are organized and cover all critical functionalities.
- [x] Validated that environment variables and configuration files are clearly defined and documented.
- [x] Reviewed commit history and pull request practices for consistency and clarity.
- [x] Ensured that coding style guidelines are followed throughout the codebase.
- [x] Verified that dependency management is handled correctly with requirements files.
- [x] Checked that logging and error handling practices are consistently applied.
- [x] **Removed ClimateService** (Dec 8, 2025) - Eliminated 400+ lines of redundant wrapper code

**Analysis Complete**: See `docs/CODE_STRUCTURE_ANALYSIS.md` for detailed findings and recommendations.

**Latest Architectural Improvements** (Dec 8, 2025):

**ClimateService Removal** - Completed full migration:
- ✅ ClimateService was a redundant wrapper delegating 100% to GrowthService
- ✅ Removed ~400 lines of duplicate hardware management code
- ✅ Migrated all API endpoints (/api/climate/*) to use GrowthService directly
- ✅ Updated app initialization, socketio handlers, health endpoints, dashboard
- ✅ Removed ClimateService from ServiceContainer
- ✅ Deleted app/services/climate_service.py
- ✅ Single source of truth: GrowthService → UnitRuntime → UnitRuntimeManager
- ✅ Eliminated duplicate state management (runtime_managers vs _unit_runtimes)
- ✅ Flask app verified working after removal

**Service Architecture - Current State**:

1. **GrowthService** (~1000 lines) - CLEAN ✅
   - Unit lifecycle (create, start, stop, delete)
   - Runtime registry management (_unit_runtimes)
   - Hardware manager coordination
   - Settings persistence
   - Plant management (add/remove/set_active)
   - Device schedules
   - RESPONSIBILITY: Single owner of unit lifecycle and hardware operations

2. **DeviceService** (~1782 lines) - NEEDS REVIEW ⚠️
   - Sensor/actuator CRUD operations
   - Device analytics delegation to AnalyticsService
   - EventBus subscriptions for device events
   - Runtime manager synchronization
   - CONCERN: Large file, mixing device CRUD with analytics coordination
   - RECOMMENDATION: Consider splitting into DeviceService (CRUD) + DeviceCoordinator (runtime sync)

3. **PlantService** (~784 lines) - CLEAN ✅
   - Plant CRUD operations
   - Plant-sensor linking
   - AI conditions application
   - Plant lifecycle events
   - RESPONSIBILITY: Single owner of plant domain logic

4. **SettingsService** (~542 lines) - CLEAN ✅
   - Application settings (hotspot, camera, environment)
   - ESP32-C6 device management
   - Retention policies
   - RESPONSIBILITY: Single owner of app-wide settings

5. **AnalyticsService** - CLEAN ✅
   - Analytics queries and recommendations
   - Energy monitoring
   - Cost trends
   - RESPONSIBILITY: Single owner of analytics domain

**Key Findings**:

1. Duplicate health endpoints across 10 different blueprints
2. Dashboard/analytics routes scattered across multiple modules
3. Large files with mixed concerns (actuators.py: 1089 lines, growth.py: 823 lines, plants.py: 800 lines)
4. Inconsistent naming conventions (\_api vs \_bp suffixes)
5. Overlap between sensors.py, devices/sensors.py, and legacy sensor_history endpoints

**Recommended Action Items** (prioritized):

- [ ] **Phase 1**: Standardize naming conventions (_api suffix, remove redundant /api/ prefixes)
- [x] **Phase 2**: Consolidate health endpoints under unified /api/health/* structure (COMPLETE)
  - ✅ Created new `/api/health` blueprint with all health endpoints
  - ✅ Added deprecation warnings to old endpoints
  - ✅ Maintained backwards compatibility
  - ✅ Updated frontend to use new health endpoints
- [x] **Phase 3**: Split actuators.py into separate modules (COMPLETE)
- [x] **Phase 4**: Split growth.py, plants.py, settings.py into focused modules (COMPLETE Dec 7, 2025)
  - ✅ Growth: 4 modules (units, thresholds, schedules, camera)
  - ✅ Plants: 4 modules (crud, lifecycle, sensors, health)
  - ✅ Actuators: 4 modules under devices/actuators/
  - ✅ Settings: 5 modules (hotspot, camera, environment, esp32, retention)
- [x] **Phase 5**: API Structure Reorganization (COMPLETE Dec 7, 2025)
  - ✅ Namespace fixes: sensors, disease, agriculture, health
  - ✅ ESP32 consolidation: 2 APIs → 1 unified devices/esp32
  - ✅ Frontend migration: 10 API calls updated
  - ✅ Test updates: 7 files updated
  - ✅ Deprecated files removed: 5 files deleted
  - ✅ Circular imports fixed: 15+ files
  - ✅ API Migration Guide created
- [x] **Phase 6**: Remove ClimateService redundant wrapper (COMPLETE Dec 8, 2025)
  - ✅ Migrated all endpoints to GrowthService
  - ✅ Updated ServiceContainer
  - ✅ Deleted climate_service.py
  - ✅ Single source of truth for hardware management
- [ ] **Phase 7**: Review DeviceService for potential splitting
  - [ ] Consider DeviceService (CRUD) + DeviceCoordinator (runtime sync)
  - [ ] Move EventBus device subscriptions to DeviceCoordinator
  - [ ] Reduce file size and improve cohesion
- [ ] **Phase 8**: Remove remaining legacy code
  - [ ] Drop light_start_time/light_end_time columns
  - [ ] Clean up old API v1 patterns
- [ ] **Phase 9**: Documentation updates
  - [ ] Update CODE_STRUCTURE_ANALYSIS.md
  - [ ] Create OpenAPI/Swagger specifications

---

## 15) Frontend to backend troubleshooting
- [x] Reviewed API endpoint connectivity between frontend and backend.
- [x] Verified data flow from backend services to frontend components.
- [x] Checked for any CORS issues or misconfigurations in API requests.
- [x] Ensured that authentication and authorization mechanisms are functioning correctly.
- [x] Validated that data formats and structures match between frontend expectations and backend responses.
- [x] Review each major feature for integration issues:
      - Add devices (frontend to backend)
      - View sensor data (backend to frontend) - Fixed unit filtering for sensor updates
      - Remove devices (frontend to backend)
      - View energy consumption (backend to frontend)
- [x] Device commands (frontend to backend)
- [x] Sensor data graph (backend to frontend) - Fixed sensor cards to show "--" when no data
- [x] Plant health monitoring (backend to frontend)


  
  ### Open – Device discovery (frontend)
- [ ] New devices discovered via Zigbee2MQTT are not appearing in the UI.
- [ ] The backend logs show successful discovery callbacks (see `on_device_discovered` in docs/ENERGY_MONITORING_QUICK_REFERENCE.md), but the frontend device list remains unchanged.
- [ ] Next steps: verify the API endpoint `/api/devices/zigbee/discovered` is returning the expected list of devices. If it is, check the frontend code in `devices.js` that fetches and displays discovered devices for any issues.

## Open – Zigbee realtime feed(frontend)
- [ ] Zigbee Socket.IO payloads are not reaching the UI. Browser console shows connection to `/sensors` but no `📡 Zigbee event received` logs and dashboards/devices.html never update.
- [ ] Backend worker currently emits `zigbee_sensor_data` (see `workers/sensor_polling_service.py`); socket bridge aliases to `zigbee_data`/`sensor_update` and requests data on connect, but still nothing arrives.
- [ ] Ne t steps: confirm the polling worker is running and actually broadcasting (look for “Socket.IO (/sensors): zigbee_sensor_data” logs). If absent, ensure sensor polling service is started alongside the web app. If present, trace namespace/event names and any auth/cors blocks.
