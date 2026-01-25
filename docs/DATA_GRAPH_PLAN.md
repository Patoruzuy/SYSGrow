# Data Graph & Dashboard Enhancement Plan

Scope: address TODO 7 by mapping available data, proposing a user-friendly dashboard layout, and outlining the implementation roadmap for charts/alerts/personalization.

## Current data surface (ready for charts)
- Sensor + readings: `Sensor`, `SensorConfig`, `SensorReading.reading_data` JSON, `SensorHealthHistory`, `SensorAnomaly` (see `infrastructure/database/sqlite_handler.py` around the sensor schema). Helpers already decode legacy/JSON payloads via `AnalyticsOperations._decode_reading_payload` and `get_sensor_data` (`infrastructure/database/ops/analytics.py`).
- Plants + lifecycle: `Plants`, `PlantHealth`, `PlantHealthLogs`, `PlantHarvestSummary`, `plant_history`; relationships through `PlantSensors` and `GrowthUnitPlants`.
- Environment/threshold context: `GrowthUnits` thresholds/device_schedules, `ThresholdOverrides`.
- Energy/device context for overlays: `EnergyReadings`, `ActuatorStateHistory`, `DeviceConnectivityHistory`.
- ML snapshots (optional enrichment): `MLTrainingData` with env readings and `plant_health_score`.
- Gaps to resolve: `PlantReadings` and `SoilMoistureHistory` are referenced in `analytics.py` but no tables exist—either create normalized tables or retire those helpers.

## Proposed dashboard layout (wireframe, desktop → mobile stacks)
```
[Top bar] Unit/plant switcher | Date range | Save view preset | Alerts bell
[Row 1 KPIs] Env composite (temp/humidity/soil moisture vs thresholds) | Soil moisture pct | CO2/VOC | Health score | Energy today
[Row 2 Trends] Multi-line env chart with threshold bands + VPD | Soil moisture by plant | Anomaly overlays
[Row 3 Plant] Stage timeline (seed/veg/flower days) | Health log stream | Harvest/yield tiles
[Row 4 Reliability] Sensor uptime/quality (SensorHealthHistory) | Anomaly list | Calibration/last-update badges
[Row 5 Actions/Feedback] Quick actuations | Alert rules editor | Feedback (thumbs up/down on insights)
```
- Mobile: stack rows, collapse filters into a drawer, keep KPIs + alerts sticky.

## Chart and widget priorities
- Env time-series: temp/humidity/soil_moisture/CO2 from `SensorReading.reading_data`, per-sensor toggles, threshold bands from `GrowthUnits`/`ThresholdOverrides`.
- Soil moisture by plant: join `PlantSensors` → `SensorReading`, group by `plant_id`, highlight below-threshold streaks.
- Sensor health: rolling `health_score`/`error_rate` from `SensorHealthHistory`, status chips for offline/degraded.
- Anomaly heatmap: count `SensorAnomaly` by sensor/day with links to raw values.
- Plant lifecycle: stage days (Plants + PlantHarvestSummary) and yield vs avg_temp/humidity overlay.
- Energy overlay (optional): `EnergyReadings.power_watts` aligned with lights/fans state to show causal spikes.

## Personalization and alerts
- Saved views/presets: persist widget layout, selected metrics, date range per `user_id`/`unit_id` (new `DashboardPreferences` or reuse `Settings` pattern).
- Alert builder: “when metric exceeds X for Y mins” using aggregated `SensorReading`; templates for moisture drop, CO2 spike, sensor offline (health_score/status). Deliver to alerts panel; email/webhook later.
- Widget library: add/remove/reorder cards; persist via saved view. Threshold overlays use plant-specific values from `ThresholdService` when available.
- Feedback loop: thumbs up/down on insights storing context (view_id, unit_id) in `Feedback` or a new table.

## Implementation roadmap (milestones/deliverables)
1) **Schema sanity & API plumbing**: decide on `PlantReadings`/`SoilMoistureHistory` (create or drop callers); add `/api/dashboard/timeseries` and `/api/dashboard/health` returning decoded series (ISO timestamps, downsample + raw).
2) **Data graph revamp**: replace `templates/data_graph.html` static image with interactive charts (Chart.js/Plotly) using the new APIs; ship env multi-line + soil moisture by plant first, with anomaly/threshold overlays.
3) **Dashboard layout update**: apply the wireframe to `templates/index.html` (or a new insights page) with responsive grid, sensor health and plant lifecycle panels, alert bell + preset selector in the header.
4) **Personalization & alerts**: persist layouts/presets, build alert rule CRUD + persistence, render alerts in the header/panel, add feedback CTA.
5) **Polish & rollout**: downsampling/caching, a11y audit, staging soak with real data; document widgets/alert recipes and enable for production users.

## Progress (Milestone 1)
- Added `PlantReadings` and `SoilMoistureHistory` tables plus indexes to support plant-level and soil moisture history charts.
- Extended sensor history plumbing to accept unit/sensor filters and optional limits for downsampling.
- Added `/api/dashboard/timeseries` to return decoded sensor series (ISO timestamps, optional unit/sensor filters, server-side downsample friendly).

## Open questions
- Should we materialize plant-level readings (`PlantReadings`/`SoilMoistureHistory`) or remove those analytics hooks?
- Preferred charting library for consistency with existing pages (Chart.js vs Plotly vs ECharts)?
- Do we expose alerts externally (webhook/email) in this phase or keep in-dashboard only?
