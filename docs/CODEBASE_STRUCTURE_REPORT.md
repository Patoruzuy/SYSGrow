SYSGrow — Codebase Structure Report

Scope: per .codex.json include set (app/**, infrastructure/**, workers/**, templates/**, static/css/**, static/js/**)

Summary
- [x] Blueprints present under `app/blueprints/*` and appear thin-ish
- [x] Services under `app/services/*` encapsulate domain logic
- [x] Infrastructure split under `infrastructure/**` (db, hardware, mqtt)
- [x] Workers under `workers/**` (polling, climate controller, scheduler)
- [x] Core event topics centralized in `app/enums/events.py` and used via `app/utils/event_bus.py` with Enum-aware publish/emit
- [x] Shared HTTP helpers in `app/utils/http.py` used across API blueprints
- [x] Central time helper `iso_now()` available in `app/utils/time.py`
- [ ] Duplicate device/enums across `app/enums/device.py` and `infrastructure/hardware/actuators/domain.py` (ActuatorType/State/Protocol)
- [ ] Some legacy dynamic event topics and raw-string publishes remain (e.g. plant-stage warnings), candidates for gradual enum migration

Proposed Moves (tree diffs)
- from: `infrastructure/logging/event_logger.py:1`
  to: keep or optionally move to `app/utils/event_logging.py`
  rationale: Listener already uses `app.utils.event_bus` and `app.enums.events`; consider relocating under `app/utils` for layering, but not required for correctness.
  risk: Low (standalone class). Quick-win: Optional.

- from: `app/models/*`
  to: keep
  rationale: Domain models correctly live under `app/models/` and integrate with services.
  risk: N/A.

- from: `infrastructure/hardware/actuators/domain.py:ActuatorType/State/Protocol`
  to: unify with `app/enums/device.py` by importing app enums in domain (adapter layer maps to infra if needed)
  rationale: Remove duplicate enums; single source of truth under `app/enums`.
  risk: Medium (touches multiple imports). Stage gradually (adapters first). Quick-win: Partial.

- from: `app/models/plant_profile.py` / `app/models/unit_runtime.py`
  to: keep but gradually route plant lifecycle and warning events through `PlantEvent` enums + typed payloads (while preserving dynamic topics where needed)
  rationale: Most events are now enum-based with Pydantic/datataclass payloads; plant-stage/growth-warning topics are the main remaining raw-string hotspots.
  risk: Low/Medium (event consumers must be checked). Quick-win: Partial.

Notable Structure Observations
- `app/__init__.py` wires blueprints and starts unit runtimes on startup (OK). EventBus wiring occurs inside workers/services constructors.
- `app/blueprints/api/*` now use shared response helpers from `app/utils/http.py`; UI routes keep thin `_api_success/_fail` wrappers for template-oriented responses.
- `infrastructure/hardware/**` contains adapters, services, and enums separate from app/enums; plan consolidation.

Quick-Win Order
1) Gradually replace remaining `datetime.now().isoformat()` call sites with `app.utils.time.iso_now()` for consistency (Low risk)
2) Tighten enum usage for actuator/device concepts by reducing duplication between `app/enums/device.py` and `infrastructure/hardware/actuators/domain.py` (Med)
3) Consolidate remaining dynamic event topics (e.g. per-plant stage warnings) behind `app/enums/events.py` while keeping aliases for backwards compatibility (Low/Med)
4) Plan deeper enum/schema unification between infra layer and `app/schemas/events.py` where payloads are still bare dicts (Med)

Warnings
- Top-level scripts under root (`start_*.py`, `run_server.py`) — acceptable for dev; ensure no production reliance.
