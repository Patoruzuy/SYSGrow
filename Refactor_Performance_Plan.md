Here’s the updated Pi-first refactor plan (future Flutter/server compatible).

Principles

- Models become thin dataclasses; validation lives in schemas or service guards (avoid Pydantic in hot paths unless needed).
- Behavior, IO, DB access, and coordination move to services/managers.
- Keep API shapes JSON-native; internal structured fields stay as dict/list, never JSON strings.
- Incremental per-model steps so the app stays runnable between changes.

Refactor Sequence

- Baseline: document current field shapes and target types for PlantProfile, UnitRuntime, UnitRuntimeManager, UnitSettings, UnitDimensions, DeviceSchedule; note service method contracts.
- Move logic out of PlantProfile → plant_service; UnitRuntime/UnitRuntimeManager → growth_service/runtime_manager helpers; keep models as fields-only dataclasses. Adjust callers and run focused tests.
- Repeat for UnitSettings, UnitDimensions, DeviceSchedule with validation in schemas/services.
- Standardize structured fields (dimensions, device_schedules, config blobs) as dict/list internally; serialize only at DB/API boundaries with a shared helper. Add read-old/write-new shims; remove after backfill.

Data & Serialization

- Add a `structured_fields` helper to parse/emit dimensions and schedules; use it in DB ops, services, and API blueprints.
- Keep API responses JSON-native for Flutter (no JSON strings inside payloads). Services return dicts or dataclasses that serialize cleanly via schemas.
- Migration/backfill plan: decide per-field storage (JSON column vs. normalized columns), dry-run via `SYSGROW_DATABASE_PATH` + `verify_migration.py`, and include rollback (DB copy restore). Shims are short-lived.

Caching (Pi-friendly)

- Config flags: `SYSGROW_CACHE_ENABLED`, `SYSGROW_CACHE_TTL`, `SYSGROW_CACHE_MAXSIZE`.
- Start with per-process read-through caches (lru/TTL) inside services; expose `invalidate_*` on writes. Keep maxsize/TTL small.
- Allow cache disable for multi-process/server mode; document invalidation triggers per service.

Config & Logging

- Centralize config in `app/config.py`; normalize `SYSGROW_*` envs with Pi defaults (small cache, fewer workers, MQTT optional) and server overrides later.
- Keep rotating logs; only add lightweight structured formatting when helpful.

Testing & Metrics

- After each model-to-service move: run focused pytest targets (e.g., plant_service, growth_service, runtime_manager) plus `python verify_routes.py`.
- Add regression tests for service behavior, schema validation, cache hit/miss/invalidate, and structured-field parsing.
- Capture simple before/after timings on Pi (DB fetch loops, schedule evaluation, sensor read paths) and record them alongside the step.

Rollout

- Small PR-sized steps: model slimmed, service updated, callers adjusted, tests run, migration/backfill noted.
- Track a short migration checklist per change (data shape change, cache invalidation rules, tests run) and remove compatibility shims after data is migrated.
