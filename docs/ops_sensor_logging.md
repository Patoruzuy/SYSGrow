# Sensor Driver Logging Guidance

Sensor drivers now use structured `logging` instead of `print`. Use these defaults and toggles when triaging hardware in staging/production.

- **Default level:** `SYSGROW_LOG_LEVEL` controls the root level (`INFO` by default via `app.config.setup_logging`). Keep production at `INFO`; enable `DEBUG` only in staging or during short-lived investigations.
- **Level mapping:** drivers already emit:
  - `INFO` for initialization/cleanup (`dht11_sensor`, `soil_moisture_sensor`, `light_sensor`, `co2_sensor`, `mq2_sensor`).
  - `WARNING` for transient read/retry issues (e.g., DHT11 runtime errors, soil moisture ADC read retries, MQ2 read fallbacks).
  - `ERROR` for hard failures (init failures, unexpected exceptions).
  This matches the desired split: INFO=normal lifecycle, WARN=retriable/backoff paths, ERROR=terminal failures.
- **Tuning tips:** When debugging noisy hardware, temporarily set `SYSGROW_LOG_LEVEL=DEBUG` and tail `logs/sysgrow.log`; revert to `INFO` after capturing data. For long-running production noise, prefer bumping specific logger names (e.g., `infrastructure.hardware.sensors.drivers.dht11_sensor`) in your logging config instead of raising the global level.
- **Where to look:** All hardware drivers live under `infrastructure/hardware/sensors/drivers` and use module-level loggers—no additional scripts outside `scripts/` require migration.
