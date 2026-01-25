# Task 5: Plant Logic Consolidation Analysis

**Date:** 2025-12-26
**Status:** COMPLETE (All phases finished)
**Objective:** Consolidate plant lifecycle + runtime synchronization to eliminate drift and contract mismatches without bloating services.

---

## Why This Task Exists

Plant logic historically lived in three places:

- `GrowthService`: unit runtime orchestration + some plant lifecycle + observers
- `PlantService`: plant CRUD + sensor linking + AI helpers
- `UnitRuntime`: in-memory plant state + AI apply + some delegations back into services

This created two predictable failure modes:

1. **Runtime drift**: DB writes happen, but `UnitRuntime.plants` is stale (or vice versa).
2. **Contract drift**: one layer expects dicts while another returns domain objects (e.g., `EnvironmentalThresholds`).

---

## Current Ownership (Intentional)

### GrowthService (`app/services/application/growth_service.py`)

**Owns:**
- Plant lifecycle writes: add/remove/set active
- Runtime synchronization (write-through): update runtime + persist DB + invalidate caches
- Plant observers (timers/schedulers) + lifecycle events
- Activity logging for user-visible plant lifecycle actions

**Does not own:**
- API payload shaping / sensor-link UX fields
- Sensor linking operations

### PlantService (`app/services/application/plant_service.py`)

**Owns:**
- Runtime-first reads (`list_plants`, `get_plant`) + API payload shaping
- Sensor linking / lookup (many-to-many via repository)
- Thin legacy wrapper `apply_ai_conditions()` (delegates to `UnitRuntime`)

**Delegates to GrowthService:**
- `create_plant`, `remove_plant`, `set_active_plant` (single write path to prevent drift)

**Still needs migration:**
- `update_plant`, `update_plant_stage` should be write-through (either move into `GrowthService` or call a `GrowthService` helper)

### UnitRuntime (`app/domain/unit_runtime.py`)

**Owns:**
- In-memory state: `plants`, `active_plant`, `latest_sensor_data`
- Thread-safe mutation helpers: `add_plant_to_memory`, `pop_plant_from_memory`
- Canonical AI application: `apply_ai_conditions()` (computes thresholds and applies settings)

**Note:** `UnitRuntime` currently supports an injected `_growth_service` to persist threshold updates. Target is to replace this with an event/callback to keep domain pure, but it is acceptable short-term for write-through consistency.

### UnitRuntimeFactory (`app/domain/unit_runtime_factory.py`)

- Canonical DB → `PlantProfile` mapping via `create_plant_profile()`
- Normalizes growth stages to a list (never `{}`) and aligns naming (`plant_name` / `name`)

### ThresholdService (`app/services/application/threshold_service.py`)

- Canonical return type: `EnvironmentalThresholds`
- Provides `get_threshold_ranges()` for hardware/UI min/max/optimal ranges

---

## Current Call Flow (Runtime-First + Single Write Path)

```
API
  -> PlantService
       - reads: runtime-first (fallback DB)
       - sensors: link/unlink + payload shaping
       - lifecycle: delegates
            -> GrowthService (single writer)
                 - repo writes + runtime updates + cache invalidation
                 - observers + events + activity logs
                 -> UnitRuntime (in-memory + AI apply)
```

---

## Data Flow Policy (Memory vs Cache)

### Reads

1. **Runtime-first** when `GrowthService.get_unit_runtime(unit_id)` returns a runtime.
2. Fallback to repository reads (may be cached) when no runtime exists.

### Writes

**Write-through** for plant lifecycle and thresholds:
- update runtime (if present)
- persist to DB
- invalidate caches (unit + plant lists)
- emit events
- log activity when user-visible

This makes the DB the durable source of truth and the runtime the authoritative live view.

---

## Domain Contract Rules

- `ThresholdService.get_optimal_conditions()` returns `EnvironmentalThresholds` (not a dict). Convert via `.to_settings_dict()` only at the boundary where settings/DB updates happen.
- `PlantProfile` compatibility:
  - `plant.id` aliases `plant_id`
  - `days_in_current_stage` aliases `days_in_stage`
  - `growth_stages` is always `list[dict]` (factory normalizes)
- Sensor model: `PlantProfile.sensor_id` remains a primary sensor; additional linked sensors live in the association table and are surfaced by `PlantService` as `linked_sensor_ids`.

---

## Activity Logging Expectations

Log via `ActivityLogger` for user-visible changes:

- Plant added/removed
- Active plant changed
- Plant stage updated
- Plant profile fields updated (name/type/etc.)
- Sensor linked/unlinked (optional: if it changes UI behavior)

---

## Implementation Progress

### Phase 1 — Contract + Drift Stabilization (COMPLETE)

- `PlantProfile`: fixed syntax issue, added compatibility aliases, stage metadata refresh.
- `UnitRuntimeFactory`: added `create_plant_profile()` public wrapper; normalized growth stage fallbacks.
- `ThresholdService`: added `get_threshold_ranges()`; ensured optimal thresholds stay as `EnvironmentalThresholds`.
- `UnitRuntime`: canonical `apply_ai_conditions()` uses `EnvironmentalThresholds`; added thread-safe plant add/pop helpers.
- `GrowthService`: plant add/remove use runtime helpers; thresholds persist even when runtime exists; added activity logging.
- `PlantService`: runtime-first reads; delegates lifecycle writes to `GrowthService`; `apply_ai_conditions()` is a wrapper.

**Validation:** `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q` (`97 passed, 16 skipped`)

### Phase 2 — Memory-First for Raspberry Pi (COMPLETE)

**Date:** 2025-12-26

Goal: Minimize database fetching on Raspberry Pi by using runtime memory as the primary source.

**Completed Changes:**

1. **PlantService.create_plant()** - Returns from runtime memory after creation
   ```python
   # MEMORY-FIRST: Get plant data from runtime (no DB fetch)
   runtime = self.growth_service.get_unit_runtime(unit_id)
   if runtime:
       plant_obj = runtime.get_plant(plant_id)
       if plant_obj:
           return plant_obj.to_dict()  # No DB round-trip
   ```

2. **PlantService.remove_plant()** - Memory-first removal
   ```python
   # MEMORY-FIRST: Remove from runtime immediately
   runtime.pop_plant_from_memory(plant_id)  # Fast, in-memory
   # Then persist to database
   self.growth_repo.remove_plant(plant_id)
   ```

3. **Verified existing memory-first patterns:**
   - `list_plants()` - Already runtime-first with DB fallback
   - `get_plant()` - Already runtime-first when unit_id known

**Pi Optimization Impact:**
- Reduced DB queries on plant creation (~1 fewer SELECT)
- Faster plant removal (memory-first, then DB)
- Lower I/O on SQLite (important for SD card longevity)

### Phase 2b — Write-Through for Updates (COMPLETE)

**Date:** 2025-12-26

`update_plant()` and `update_plant_stage()` already follow write-through pattern in PlantViewService.
No changes needed - verified existing implementation is correct.

### Phase 3 — Rename PlantService to PlantViewService (COMPLETE)

**Date:** 2025-12-26

Renamed `PlantService` → `PlantViewService` to clarify its role:
- Views: `list_plants`, `get_plant`, `get_plant_sensors`
- Updates: `update_plant`, `update_plant_stage`, `link_sensor`, `unlink_sensor`
- Lifecycle (create/remove) via GrowthService delegation

**Files updated:**
- `app/services/application/plant_service.py` - Class rename
- `app/services/container.py` - Import update
- `app/services/container_builder.py` - Import and instantiation
- `app/blueprints/api/growth/units.py` - Import and type hint
- `app/blueprints/ui/helpers.py` - Import and type hint
- `app/services/application/growth_service.py` - Docstrings

### Phase 4 — Purify UnitRuntime (COMPLETE)

**Date:** 2025-12-26

Removed `_growth_service` and `_plant_service` dependencies from `UnitRuntime`.
Now uses EventBus for persistence requests:

**New Events:**
- `RuntimeEvent.THRESHOLDS_PERSIST` - Emitted when thresholds change
- `RuntimeEvent.ACTIVE_PLANT_SET` - Emitted when active plant changes

**Event Handlers in GrowthService:**
- `_handle_thresholds_persist()` - Persists thresholds to database
- `_handle_active_plant_set()` - Persists active plant, emits ACTIVE_PLANT_CHANGED

**Hardware Running State:**
- Added `set_hardware_running(bool)` method to UnitRuntime
- GrowthService sets this flag when starting/stopping hardware

**Files updated:**
- `app/enums/events.py` - Added RuntimeEvent.THRESHOLDS_PERSIST, ACTIVE_PLANT_SET
- `app/schemas/events.py` - Added ThresholdsPersistPayload, ActivePlantSetPayload
- `app/domain/unit_runtime.py` - Removed service dependencies, emit events instead
- `app/domain/unit_runtime_factory.py` - Removed service injection
- `app/services/application/growth_service.py` - Event subscription and handlers

---

## Architecture Summary (Final)

```
API Layer
  │
  ├─→ PlantViewService (reads, updates, sensor links)
  │     └─→ delegates lifecycle to GrowthService
  │
  └─→ GrowthService (unit orchestration, plant lifecycle, runtime registry)
        │
        ├─→ subscribes to RuntimeEvent.THRESHOLDS_PERSIST
        ├─→ subscribes to RuntimeEvent.ACTIVE_PLANT_SET
        │
        └─→ UnitRuntime (pure domain model)
              │
              ├─→ emits RuntimeEvent.THRESHOLDS_PERSIST
              ├─→ emits RuntimeEvent.ACTIVE_PLANT_SET
              └─→ emits PlantEvent.ACTIVE_PLANT_CHANGED
```

---

## Risks / Mitigations

- **GrowthService bloat:** keep plant-specific logic in internal helpers/modules (e.g., `app/services/application/plant_lifecycle.py`) while maintaining single ownership.
- **Hidden drift paths:** require "write-through" semantics for every repo write that affects plant state.
- **Event-based persistence:** Ensure GrowthService event handlers are robust (error handling, logging).

