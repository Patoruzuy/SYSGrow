# Ops Health Dashboard Integration

Use these endpoints to wire Grafana/Prometheus or any ops dashboard.

## Endpoints
- `GET /status/ops` – JSON snapshot (event bus + per-unit polling/controller aggregates).
- `GET /status/ops/metrics` – Prometheus text exposition of the same snapshot.
- `GET /status/polling` – Detailed per-unit polling + controller health (JSON).

## Prometheus scrape example
```yaml
scrape_configs:
  - job_name: sysgrow_ops
    metrics_path: /status/ops/metrics
    static_configs:
      - targets: ["backend:5000"]
```

## Grafana (JSON API datasource) example queries
- Queue depth: `$.event_bus.queue_depth`
- Dropped events: `$.event_bus.dropped_events`
- Per-unit polling metrics: `$.units["1"].polling.backoff_count`, `pending_coalesced`, `queue_depth`, `dropped_events`, `last_seen_count`
- Controller metrics: `$.units["1"].controller.stale_sensors`, `sensor_updates`

## Quick validation
- Text scrape: `curl -s http://localhost:5000/status/ops/metrics`
- JSON scrape: `python scripts/ops_health_probe.py --base http://localhost:5000 --endpoint /status/ops`
- Lightweight logging (no Prom/Grafana yet): `python scripts/ops_health_logger.py --base http://localhost:5000 --interval 10 --out ops_health.log`

Tip: If scraping `/status/ops/metrics` behind auth, add the appropriate headers in your Prometheus or Grafana data source configuration.
