# Sensor Polling & Event Bus Tuning Guide

Use these steps to tune the sensor polling settings in staging before promoting to production.

## Quick-start values
- Base env: see `ops.env.example` (workers=8, queue=2048, MQTT rate limit=2s, coalesce flush=2s, backoff base=2s, backoff max=60s, heartbeat=10s).

## Tuning loop
1) Deploy to staging with `ops.env.example` values and real (or replayed) device traffic.
2) Observe metrics for 10–15 minutes:
   - `GET /status/ops` → `event_bus_queue_depth`, `event_bus_dropped`, `sensor_backoff_until`, `pending_coalesced`.
   - `GET /api/dashboard/health` for deeper drilldowns.
   - Optional: `python scripts/ops_health_probe.py --base http://<host>:<port> --endpoint /status/ops --interval 5`.
3) Adjust:
   - If `event_bus_queue_depth` rises steadily or `event_bus_dropped > 0`: increase `SYSGROW_EVENTBUS_WORKERS` (e.g., +2) or `SYSGROW_EVENTBUS_QUEUE_SIZE` (e.g., 2048→4096). If CPU is saturated, prefer more workers over queue size.
   - If MQTT bursts still drop updates (pending_coalesced stays long): raise `SYSGROW_MQTT_QUEUE_SIZE` (queue) or loosen `SYSGROW_MQTT_RATE_LIMIT_SEC` slightly (e.g., 2→1.5) and keep `SYSGROW_MQTT_COALESCE_FLUSH_SEC` close to the rate limit.
   - If flaky sensors flap: increase `SYSGROW_SENSOR_BACKOFF_BASE_SEC` (e.g., 2→4) or cap with `SYSGROW_SENSOR_BACKOFF_MAX_SEC` if retries are too slow.
4) Re-run step 2 after each tweak until:
   - Dropped events = 0 over several flush intervals.
   - Queue depth oscillates but does not trend upward.
   - Pending coalesced entries clear within one flush interval.
   - Backoff list stabilizes (no oscillating failures).
5) Record the final tuned values in your deployment config and, if helpful, update `ops.env.example` with the chosen numbers.

## Notes
- Keep `SYSGROW_MQTT_RATE_LIMIT_SEC` ≤ `SYSGROW_MQTT_COALESCE_FLUSH_SEC` to ensure timely flushes.
- If running with constrained CPUs, prefer slightly higher rate limits (less publishing) and a modest worker count to avoid contention.
- When testing without real MQTT, you can simulate load with a publisher pushing bursts to the broker and watch the coalesce/queue metrics.
