# Service Architecture Review

## Overview

**Date**: January 10, 2026  
**Author**: Architecture Review  
**Status**: In Progress  

This document outlines issues with the current service architecture and proposes refactoring to ensure each service owns its domain logic following the memory-first pattern.

---

## Issues Identified

### 1. Duplicated Constants (DRY Violation)

`THRESHOLD_KEYS` and `PLANT_OVERRIDE_FIELDS` are defined in **both** files:
- `growth_service.py` (lines 109-125)
- `threshold_service.py` (lines 21-35)

**Impact**: Maintenance burden, risk of drift between definitions.

**Solution**: Single source of truth in `threshold_service.py`, import where needed.

---

### 2. GrowthService Has Threshold Logic (SRP Violation)

GrowthService contains threshold-specific methods that belong in ThresholdService:

| Method | Location | Should Be |
|--------|----------|-----------|
| `_handle_thresholds_persist()` | GrowthService | ThresholdService |
| `_handle_thresholds_proposed()` | GrowthService | ThresholdService (with NotificationsService) |
| `_filter_threshold_changes()` | GrowthService | ThresholdService |
| `_apply_active_plant_overrides()` | GrowthService | ThresholdService |
| `_update_plant_threshold_overrides()` | GrowthService | ThresholdService |

**Impact**: GrowthService is bloated (~1900 lines), threshold logic is scattered.

**Solution**: Move threshold event handlers and logic to ThresholdService.

---

### 3. SchedulingService Uses Read-Through Cache (Not Memory-First)

Current behavior:
```python
# On write - invalidates cache, next read fetches from DB
def create_schedule(...):
    created = self.repository.create(schedule)
    self._invalidate_cache(schedule.unit_id)  # Forces DB re-fetch
    
# On read - checks cache, falls back to DB
def get_schedules_for_unit(...):
    if unit_id in self._cache:
        return self._cache[unit_id]  # Cache hit
    schedules = self.repository.get_by_unit(unit_id)  # DB fetch
    self._cache[unit_id] = schedules  # Populate cache
```

**Problems**:
- Cannot operate without repository (not memory-first)
- Every write forces DB re-fetch on next read
- No thread safety for concurrent access
- Inconsistent with PlantService pattern

**Solution**: Implement memory-first pattern like PlantService.

---

### 4. Services Fetch Same Data Repeatedly

Multiple services independently fetch:
- Unit data from `growth_repo.get_unit()`
- Plant data from `growth_repo.get_plant()`
- Threshold data from multiple sources

**Solution**: Each service owns its domain data:
- GrowthService → Units
- PlantService → Plants (✅ DONE)
- ThresholdService → Thresholds
- SchedulingService → Schedules

---

## Refactoring Plan

### Phase 1: SchedulingService Memory-First (This PR)

1. Add in-memory schedule storage: `_schedules: Dict[int, Dict[int, Schedule]]`
2. Add thread lock: `_schedules_lock`
3. Implement memory-first CRUD operations
4. Add `load_schedules_for_unit()` method
5. Update writes to update memory AND persist to DB

### Phase 2: Threshold Logic to ThresholdService (Future)

1. Move `THRESHOLD_KEYS` and `PLANT_OVERRIDE_FIELDS` constants
2. Move event handlers from GrowthService
3. Add event subscriptions to ThresholdService
4. GrowthService delegates to ThresholdService

### Phase 3: Remove Duplicate Data Fetching (Future)

1. Each service queries its own service for cross-domain data
2. Remove duplicate repository calls
3. Establish clear service boundaries

---

## Memory-First Pattern Reference

From PlantService:

```python
class PlantViewService:
    def __init__(self, ...):
        # Primary storage: unit_id -> {plant_id: PlantProfile}
        self._plants: Dict[int, Dict[int, PlantProfile]] = {}
        self._plants_lock = threading.Lock()
        
    def _add_plant_to_memory(self, unit_id: int, plant: PlantProfile) -> None:
        with self._plants_lock:
            if unit_id not in self._plants:
                self._plants[unit_id] = {}
            self._plants[unit_id][plant.plant_id] = plant
    
    def load_plants_for_unit(self, unit_id: int) -> int:
        """Load from DB into memory at startup."""
        self.clear_unit_plants(unit_id)
        plant_data_list = self.growth_repo.get_plants_in_unit(unit_id)
        for plant_data in plant_data_list:
            plant = self._create_plant_profile(**plant_data)
            self._add_plant_to_memory(unit_id, plant)
        return len(plant_data_list)
```

Key principles:
1. **In-memory storage is the source of truth for active data**
2. **DB is for persistence and cold-start loading**
3. **Thread-safe access via locks**
4. **Load on unit startup, clear on unit stop**
5. **Writes update memory AND persist to DB**

---

## Success Criteria

- [x] SchedulingService uses memory-first pattern
- [x] Thread-safe schedule access
- [x] Schedules loaded on unit startup
- [x] Writes update memory immediately, persist to DB
- [x] No code duplication between services (Phase 2 - COMPLETE)

---

## Phase 1 Complete Summary

### Changes Made

**SchedulingService (`app/services/hardware/scheduling_service.py`)**:
- Added `_schedules: Dict[int, Dict[int, Schedule]]` - primary in-memory storage
- Added `_schedules_lock = threading.Lock()` - thread safety
- Added `_loaded_units: set[int]` - tracks which units are loaded
- Added memory management methods:
  - `_get_unit_schedules()` - thread-safe access
  - `_add_schedule_to_memory()` - thread-safe insertion
  - `_remove_schedule_from_memory()` - thread-safe removal
  - `_update_schedule_in_memory()` - thread-safe update
  - `get_schedule_from_memory()` - fast read path
  - `get_schedules_for_unit_from_memory()` - fast list path
  - `clear_unit_schedules()` - cleanup on stop
  - `is_unit_loaded()` - check if unit loaded
  - `load_schedules_for_unit()` - load from DB at startup
- Updated CRUD methods for memory-first:
  - `create_schedule()` - adds to memory after DB persist
  - `get_schedule()` - checks memory first, falls back to DB
  - `get_schedules_for_unit()` - returns from memory if loaded
  - `update_schedule()` - updates memory first, then persists
  - `delete_schedule()` - removes from memory first, then DB
  - `set_schedule_enabled()` - updates memory first
- Removed old cache methods (`_invalidate_cache`, `clear_cache`, `set_cache_enabled`)

**GrowthService (`app/services/application/growth_service.py`)**:
- `start_unit_runtime()` - calls `scheduling_service.load_schedules_for_unit()`
- `stop_unit_runtime()` - calls `scheduling_service.clear_unit_schedules()`

---

## Phase 2 Complete Summary

### Changes Made

**ThresholdService (`app/services/application/threshold_service.py`)** - Single Source of Truth:
- Owns `THRESHOLD_KEYS` and `PLANT_OVERRIDE_FIELDS` constants
- Added `subscribe_to_events()` - subscribes to `RuntimeEvent.THRESHOLDS_PERSIST`
- Added `_handle_thresholds_persist()` - persists thresholds from UnitRuntime events
- Added `set_cache_invalidation_callback()` - allows GrowthService cache to be invalidated
- Added `filter_threshold_changes()` - filters changes based on tolerance

**GrowthService (`app/services/application/growth_service.py`)** - Reduced Responsibilities:
- Removed duplicate `THRESHOLD_KEYS` and `PLANT_OVERRIDE_FIELDS` constants
- Removed `_handle_thresholds_persist()` method (moved to ThresholdService)
- Removed `_filter_threshold_changes()` method (moved to ThresholdService)
- Removed unused imports: `THRESHOLD_UPDATE_TOLERANCE`, `ThresholdsPersistPayload`
- Updated `_subscribe_to_runtime_events()` - only subscribes to THRESHOLDS_PROPOSED, ACTIVE_PLANT_SET
- Added `_setup_threshold_service_integration()` - wires ThresholdService event handling and cache callback
- Updated `_handle_thresholds_proposed()` - delegates filtering to ThresholdService
- Imports `THRESHOLD_KEYS`, `PLANT_OVERRIDE_FIELDS` from ThresholdService

### Architecture After Phase 2

```
┌─────────────────┐     ┌────────────────────┐
│  UnitRuntime    │     │  NotificationsService
│                 │     └──────────┬─────────┘
│ emits:          │                │
│ THRESHOLDS_     │                │
│   PERSIST       │                │
│ THRESHOLDS_     │                │
│   PROPOSED      │                │
└────────┬────────┘                │
         │                         │
         ▼                         │
  ┌──────────────────┐             │
  │   EventBus       │             │
  └──────────────────┘             │
         │                         │
    ┌────┴────┐                    │
    │         │                    │
    ▼         ▼                    │
┌────────┐  ┌────────────────────┐ │
│Threshold│  │   GrowthService    │ │
│Service  │  │                    │◄┘
│         │  │ handles:           │
│ handles:│  │ THRESHOLDS_PROPOSED│
│ PERSIST │  │ ACTIVE_PLANT_SET   │
│         │  │                    │
│ updates:│  │ delegates to:      │
│ DB      │  │ ThresholdService   │
│ notifies│  │ NotificationsService
│ cache   │  │                    │
└─────────┘  └────────────────────┘
```

### Lines of Code Reduction

- **GrowthService**: ~70 lines removed (from ~1900 to ~1830)
- **SettingsService**: ~30 lines removed (removed threshold wrappers)
- **Threshold logic**: Now centralized in ThresholdService

### API Changes

**Environment Thresholds API** (`/api/settings/environment`):
- Now uses `ThresholdService` directly via `get_threshold_service()` accessor
- Removed indirection through `SettingsService`

**SettingsService**:
- Removed `get_environment_thresholds()` - use `ThresholdService` directly
- Removed `update_environment_thresholds()` - use `ThresholdService` directly
- Removed `threshold_service` dependency

**GrowthService**:
- `get_thresholds(unit_id)` - Delegates to `ThresholdService`, adds non-threshold settings
- `set_thresholds(unit_id, ...)` - Delegates to `ThresholdService`, adds audit logging

---