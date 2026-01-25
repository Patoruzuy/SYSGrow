# Ops Health Dashboard Integration

Use the new health endpoints to feed Grafana/ops dashboards without extra client logic.

## Endpoints
- `GET /api/dashboard/health`: full per-unit polling + climate controller health and EventBus metrics (JSON).
- `GET /status/polling`: detailed polling health (per-unit) for debugging.
- `GET /status/ops`: flattened summary for quick panels (queue depth, dropped events, backoff counts).

### Ops probe helper
- `python scripts/ops_health_probe.py --base http://localhost:5000 --endpoint /status/ops`
- Outputs compact key/value lines for easy ingestion plus raw JSON when using detailed endpoints.

## Example scrape (curl)
```bash
curl -s http://localhost:5000/api/dashboard/health | jq .
curl -s http://localhost:5000/status/ops | jq .
```

## Suggested Grafana panels
- **EventBus queue**: `event_bus.queue_depth`, `event_bus.dropped_events`.
- **Per-unit polling**: `units.<id>.polling.backoff_count`, `pending_coalesced`, `queue_depth`.
- **Controller stale sensors**: `units.<id>.controller.stale_sensors`.
- **Sensor update throughput**: `units.<id>.controller.sensor_updates`.

## Tuning knobs (environment)
- `SYSGROW_EVENTBUS_WORKERS` (default 8)
- `SYSGROW_EVENTBUS_QUEUE_SIZE` (default 1024)
- `SYSGROW_MQTT_RATE_LIMIT_SEC` (default 2)
- `SYSGROW_MQTT_COALESCE_FLUSH_SEC` (default 2)
- `SYSGROW_SENSOR_BACKOFF_BASE_SEC` (default 2)
- `SYSGROW_SENSOR_BACKOFF_MAX_SEC` (default 60)
- `SYSGROW_POLLING_HEARTBEAT_SEC` (default 10)

### Staging baseline
- Start with `SYSGROW_EVENTBUS_WORKERS=8`, `SYSGROW_EVENTBUS_QUEUE_SIZE=2048`.
- Keep MQTT rate limit/coalesce at `2s`; tighten to `1s` only if logs/DB can handle the throughput.
- Backoff base `2s`, max `60s`; lower max to `30s` if devices recover quickly.

Log lines on startup confirm the active settings.
