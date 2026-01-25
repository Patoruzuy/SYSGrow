# V1 Endpoint Inventory (Growth & Devices)

Use this list to track v1 endpoints still exposed and plan v2 replacements.

## /api/growth (v1 unless noted)
- Units
  - `POST /api/growth/units` (create)
  - `GET /api/growth/units/<unit_id>` (read)
  - `PATCH /api/growth/units/<unit_id>` (update)
  - `DELETE /api/growth/units/<unit_id>` (delete)
  - `GET /api/growth/units/<unit_id>/plants`
  - `POST /api/growth/units/<unit_id>/plants`
- Thresholds
  - `GET /api/growth/units/<unit_id>/thresholds`
  - `POST /api/growth/units/<unit_id>/thresholds`
  - `GET /api/growth/thresholds/recommended` (already v2-compatible shape; keep)
- Schedules
  - `GET /api/growth/units/<unit_id>/schedules`
  - `GET /api/growth/units/<unit_id>/schedules/<device_type>`
  - `POST /api/growth/units/<unit_id>/schedules`
  - `DELETE /api/growth/units/<unit_id>/schedules/<device_type>`
  - Active: `GET /api/growth/units/<unit_id>/schedules/active`
- Camera
  - `POST /api/growth/units/<unit_id>/camera/start`
  - `POST /api/growth/units/<unit_id>/camera/stop`
  - `POST /api/growth/units/<unit_id>/camera/capture`
  - `GET /api/growth/units/<unit_id>/camera/status`
- V2 already present
  - Units CRUD: `GET/POST/PATCH/DELETE /api/growth/v2/units`
  - Thresholds: `POST /api/growth/v2/units/<id>/thresholds`
  - Schedules: `GET/POST/DELETE /api/growth/v2/units/<id>/schedules`

## /api/devices (v1 unless noted)
- Sensors
  - `GET /api/devices/sensors` (all)
  - `GET /api/devices/sensors/unit/<unit_id>`
  - `POST /api/devices/sensors`
  - `DELETE /api/devices/sensors/<sensor_id>`
  - Health/anomalies/calibration/history endpoints under `/api/devices/sensors/<sensor_id>/*`
- Actuators
  - `GET /api/devices/actuators`
  - `GET /api/devices/actuators/unit/<unit_id>`
  - `POST /api/devices/actuators`
  - `DELETE /api/devices/actuators/<actuator_id>`
  - Power/energy/health/anomaly endpoints under `/api/devices/actuators/<actuator_id>/*`
- Analytics/config/zigbee
  - Config: `/api/devices/config/*`
  - Zigbee2MQTT: `/api/devices/zigbee2mqtt/*`
  - Analytics: multiple `/api/devices/analytics/*` and power/cost endpoints
- V2 already present
  - Sensors: `GET /api/devices/v2/sensors`, `GET /api/devices/v2/sensors/unit/<unit_id>`, `POST /api/devices/v2/sensors`, `DELETE /api/devices/v2/sensors/<sensor_id>`
  - Actuators: `GET /api/devices/v2/actuators`, `GET /api/devices/v2/actuators/unit/<unit_id>`, `POST /api/devices/v2/actuators`, `DELETE /api/devices/v2/actuators/<actuator_id>`

## Next steps
- Capture real usage: enable access logs or metrics tags (already logging v1 usage via `before_request` in growth/devices blueprints).
- Decide v2 coverage gaps: analytics/config/zigbee and sensor/actuator sub-resources still v1-only.
- Deprecation plan: document timelines, add warnings in responses, and remove v1 once usage is near-zero.
