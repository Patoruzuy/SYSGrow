# Plant Service Refactoring Plan

## Overview

This document outlines the plan to refactor plant management so that **PlantViewService** (renamed to `PlantService`) becomes the single source of truth for all plant operations, following a memory-first architecture.

**Date**: January 10, 2026  
**Author**: Architecture Review  
**Status**: ✅ COMPLETE  

---

## Progress Tracking

| Phase | Description | Status |
|-------|-------------|--------|
| Phase 1 | PlantService Owns Plant Collection | ✅ Complete |
| Phase 2 | PlantService Creates PlantProfiles | ✅ Complete |
| Phase 3 | Wire Into Unit Lifecycle | ✅ Complete |
| Phase 4 | API Compatibility Layer | ✅ Complete |
| Phase 5 | Simplify UnitRuntime | ✅ Complete |
| Phase 6 | Cleanup and Testing | ✅ Complete |

---

## Refactoring Complete Summary

### What Was Done

**Phase 6 - Cleanup and Testing:**
- ✅ Removed dual-write patterns from `GrowthService` (writing to both PlantService and UnitRuntime)
- ✅ Removed all fallbacks to `runtime.plants` and `runtime.get_plant()`
- ✅ Removed `plants: Dict[int, PlantProfile]` from `UnitRuntime`
- ✅ Removed `plant_lock = threading.Lock()` from `UnitRuntime`
- ✅ Removed deprecated methods from `UnitRuntime`:
  - `get_plant()`, `get_all_plants()`
  - `add_plant_to_memory()`, `pop_plant_from_memory()`
  - `set_active_plant()` (now handled by GrowthService)
- ✅ Updated `scheduled_tasks.py` to use `PlantService.list_plants()`
- ✅ Updated health API (`units.py`) to use `PlantService.get_active_plant()`
- ✅ Updated test files to reflect new architecture

### Final Architecture

1. **PlantService** is the single source of truth for all plant data
2. **UnitRuntime** is a pure domain model with no plant collection
3. **GrowthService** orchestrates plant operations via PlantService
4. **Memory-first pattern** with database fallback for persistence

---

## Current State Analysis

### Current Architecture Issues

1. **Scattered Plant Ownership**
   - `UnitRuntime` owns `plants: Dict[int, PlantProfile]` collection
   - `UnitRuntimeFactory` creates `PlantProfile` instances directly
   - `GrowthService.add_plant_to_unit()` creates plants in DB and runtime
   - `PlantViewService` reads/updates plants but delegates creation to `GrowthService`

2. **Mixed Responsibilities**
   - `UnitRuntimeFactory._load_plants()` loads plants from DB
   - `UnitRuntimeFactory._create_plant_profile()` creates PlantProfile objects
   - `GrowthService.add_plant_to_unit()` creates DB records + adds to runtime
   - `PlantViewService.create_plant()` calls `GrowthService.add_plant_to_unit()`

3. **UnitRuntime is Not Pure Domain**
   - Contains `plants` dictionary (should be managed by PlantService)
   - Has `plant_lock` for thread safety (becomes PlantService concern)
   - Has `add_plant_to_memory()`, `pop_plant_from_memory()` methods
   - Contains plant-related logic that belongs in PlantService

4. **Not Truly Memory-First**
   - Some paths fetch from DB first, then try runtime
   - Inconsistent patterns across different methods

---

## Target Architecture

### Design Principles

1. **PlantService owns all plant operations**
   - Single service for create/read/update/delete
   - Owns the in-memory plant collection
   - Only service that reads/writes plant tables

2. **Memory-First Pattern**
   - All reads check in-memory collection first
   - Fallback to database only when needed
   - All writes update memory AND persist to DB

3. **UnitRuntime as Pure Domain Model**
   - No plant collection (reference PlantService)
   - No plant-related logic
   - Only unit settings, thresholds, schedules
   - Query PlantService for active plant info

4. **UnitRuntimeFactory Simplification**
   - No longer creates PlantProfile instances
   - Calls `PlantService.load_plants_for_unit()` during runtime creation
   - Or: Factory just creates UnitRuntime, PlantService loads plants separately

---

## Implementation Plan

### Phase 1: PlantService Owns Plant Collection ✅

**Goal**: Move plant collection from UnitRuntime to PlantService

#### 1.1 Add Plants Collection to PlantService

```python
class PlantService:
    def __init__(self, ...):
        # In-memory plant storage: unit_id -> {plant_id: PlantProfile}
        self._plants: Dict[int, Dict[int, PlantProfile]] = {}
        self._plants_lock = threading.Lock()
```

#### 1.2 Plant Collection Methods

```python
def _get_unit_plants(self, unit_id: int) -> Dict[int, PlantProfile]:
    """Get or initialize plant collection for a unit."""

def _add_plant_to_memory(self, unit_id: int, plant: PlantProfile) -> None:
    """Add plant to in-memory collection."""

def _remove_plant_from_memory(self, unit_id: int, plant_id: int) -> Optional[PlantProfile]:
    """Remove plant from in-memory collection."""

def get_plant_from_memory(self, unit_id: int, plant_id: int) -> Optional[PlantProfile]:
    """Get plant from memory (fast path)."""
```

### Phase 2: PlantService Creates PlantProfiles ✅

**Goal**: PlantService is the only creator of PlantProfile objects

#### 2.1 Move PlantProfile Creation to PlantService

```python
def _create_plant_profile(
    self,
    plant_id: int,
    plant_name: str,
    plant_type: str,
    current_stage: str,
    days_in_stage: int,
    moisture_level: float,
    growth_stages: Optional[Any] = None,
    **kwargs
) -> PlantProfile:
    """Create PlantProfile domain object (internal use)."""
```

#### 2.2 PlantJsonHandler Integration

- PlantService gets `PlantJsonHandler` dependency
- Uses it to resolve growth stages when creating plants

### Phase 3: PlantService Handles All Plant DB Operations ✅

**Goal**: PlantService is the only service reading/writing plant tables

#### 3.1 Direct Repository Access

```python
def __init__(self, ..., plant_repo: PlantRepository, ...):
    # Note: Could use growth_repo or create dedicated PlantRepository
    self._plant_repo = plant_repo
```

#### 3.2 Create Plant (Full Ownership)

```python
def create_plant(
    self,
    unit_id: int,
    plant_name: str,
    plant_type: str,
    current_stage: str,
    **kwargs
) -> Optional[Dict[str, Any]]:
    """
    Create plant with memory-first pattern:
    1. Validate inputs
    2. Create in database (get plant_id)
    3. Create PlantProfile object
    4. Add to in-memory collection
    5. Publish events
    6. Return plant data
    """
```

#### 3.3 Remove GrowthService.add_plant_to_unit()

- Deprecate `GrowthService.add_plant_to_unit()`
- All callers use `PlantService.create_plant()` instead

### Phase 4: Refactor UnitRuntimeFactory ✅

**Goal**: Factory no longer loads/creates plants

#### 4.1 Option A: Factory Delegates to PlantService

```python
class UnitRuntimeFactory:
    def __init__(self, ..., plant_service: PlantService):
        self.plant_service = plant_service

    def create_runtime(self, unit_data: Dict) -> UnitRuntime:
        # Create runtime WITHOUT plants
        runtime = UnitRuntime(
            unit_id=unit_id,
            unit_name=unit_name,
            ...
            # NO plants parameter
        )
        
        # PlantService loads plants for this unit
        self.plant_service.load_plants_for_unit(unit_id)
        
        return runtime
```

#### 4.2 Option B: GrowthService Coordinates Loading

```python
class GrowthService:
    def start_unit_runtime(self, unit_id: int) -> bool:
        # Create runtime (no plants)
        runtime = self.factory.create_runtime(unit_data)
        
        # Load plants via PlantService
        self.plant_service.load_plants_for_unit(unit_id)
        
        # Set active plant
        active_plant_id = unit_data.get('active_plant_id')
        if active_plant_id:
            self.plant_service.set_active_plant(unit_id, active_plant_id)
```

**Recommendation**: Option B - clearer separation

### Phase 5: Simplify UnitRuntime ✅

**Goal**: Remove all plant collection logic from UnitRuntime

#### 5.1 Remove Plant Collection

```python
class UnitRuntime:
    def __init__(self, ...):
        # REMOVED: self.plants = {}
        # REMOVED: self.active_plant = None
        # REMOVED: self.plant_lock = threading.Lock()
        
        # Keep reference to active plant ID only
        self._active_plant_id: Optional[int] = None
```

#### 5.2 Remove Plant Methods

```python
# REMOVE these methods from UnitRuntime:
# - get_plant()
# - get_all_plants()
# - get_active_plant()
# - add_plant_to_memory()
# - pop_plant_from_memory()
# - set_active_plant()
```

#### 5.3 Add PlantService Reference

```python
class UnitRuntime:
    def get_active_plant(self) -> Optional[PlantProfile]:
        """Delegate to PlantService."""
        if self._plant_service and self._active_plant_id:
            return self._plant_service.get_plant_from_memory(
                self.unit_id, 
                self._active_plant_id
            )
        return None
```

### Phase 6: Update All Callers ✅

**Goal**: Ensure all code uses PlantService for plant operations

#### 6.1 Update GrowthService

```python
# Before:
runtime = self.get_unit_runtime(unit_id)
plants = runtime.get_all_plants()

# After:
plants = self.plant_service.list_plants(unit_id)
```

#### 6.2 Update API Blueprints

```python
# Before:
runtime = container.growth_service.get_unit_runtime(unit_id)
plant = runtime.get_plant(plant_id)

# After:
plant = container.plant_service.get_plant(plant_id, unit_id=unit_id)
```

---

## File Changes Summary

### Files to Modify

| File | Changes |
|------|---------|
| `app/services/application/plant_service.py` | Add plant collection, create_plant_profile, memory-first CRUD |
| `app/domain/unit_runtime.py` | Remove plants dict, plant methods, add active_plant_id ref |
| `app/domain/unit_runtime_factory.py` | Remove _load_plants, _create_plant_profile, delegate to PlantService |
| `app/services/application/growth_service.py` | Remove add_plant_to_unit, use PlantService instead |
| `app/services/container.py` | Update initialization order, wire dependencies |

### Files to Review (for caller updates)

- `app/blueprints/api/plants.py`
- `app/blueprints/api/growth.py`
- `app/services/application/harvest_service.py`
- `app/services/ai/plant_health_monitor.py`
- `tests/test_plant_service.py`

---

## Migration Strategy

### Step 1: Add New Capabilities (Non-Breaking)

1. Add `_plants` collection to PlantService
2. Add `_create_plant_profile()` method to PlantService
3. Add `load_plants_for_unit()` method to PlantService
4. Keep existing UnitRuntime methods working

### Step 2: Dual-Write Mode

1. PlantService writes to both its collection AND UnitRuntime
2. Validate consistency between both stores
3. Log any discrepancies

### Step 3: Switch Reads to PlantService

1. Update callers to read from PlantService
2. Deprecate UnitRuntime plant accessors
3. Add deprecation warnings

### Step 4: Remove Legacy Code

1. Remove plants from UnitRuntime
2. Remove _load_plants from UnitRuntimeFactory
3. Remove add_plant_to_unit from GrowthService

---

## Testing Plan

### Unit Tests

1. **PlantService Tests**
   - `test_create_plant_adds_to_memory`
   - `test_get_plant_memory_first`
   - `test_remove_plant_clears_memory`
   - `test_load_plants_for_unit`

2. **UnitRuntime Tests**
   - `test_runtime_without_plants` (after cleanup)
   - `test_active_plant_via_service`

3. **Integration Tests**
   - `test_plant_lifecycle_end_to_end`
   - `test_memory_db_consistency`

### Regression Tests

- All existing plant API tests must pass
- Performance benchmarks (memory-first should be faster)

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Circular dependency PlantService ↔ GrowthService | Use setter injection (ContainerBuilder pattern) |
| Breaking existing API contracts | Keep PlantViewService name temporarily, add aliases |
| Thread safety issues | Use same locking pattern as UnitRuntime |
| Memory leaks with plant collections | Clear collections when unit is stopped/deleted |

---

## Success Criteria

1. ✅ PlantService owns all plant CRUD operations
2. ✅ PlantService is only creator of PlantProfile
3. ✅ UnitRuntime has no plant collection or plant logic
4. ✅ Memory-first pattern: collection first, DB fallback
5. ✅ All existing tests pass
6. ✅ No circular import issues
7. ✅ Thread-safe plant operations

---

## Timeline Estimate

| Phase | Effort | Dependencies |
|-------|--------|--------------|
| Phase 1: Plant Collection | 2-3 hours | None |
| Phase 2: PlantProfile Creation | 1-2 hours | Phase 1 |
| Phase 3: DB Operations | 2-3 hours | Phase 2 |
| Phase 4: Factory Refactor | 1-2 hours | Phase 3 |
| Phase 5: UnitRuntime Cleanup | 2-3 hours | Phase 4 |
| Phase 6: Update Callers | 3-4 hours | Phase 5 |
| Testing & Validation | 2-3 hours | All phases |

**Total Estimate**: 13-20 hours

---

## Open Questions

1. **PlantRepository vs GrowthRepository**: Should we create a dedicated `PlantRepository` or continue using `GrowthRepository` for plant operations?
   - **Recommendation**: Keep using `GrowthRepository` for now, extract later if needed

2. **Active Plant Storage**: Should active plant be stored per-unit in PlantService or keep it in UnitRuntime?
   - **Recommendation**: Keep `active_plant_id` in UnitRuntime (it's unit configuration)

3. **PlantJournalService**: Does it need the same refactoring?
   - **Recommendation**: PlantJournalService can remain as-is, uses PlantService for plant lookups

---

## Next Steps

1. [ ] Review this plan with stakeholders
2. [ ] Create feature branch: `refactor/plant-service-ownership`
3. [ ] Implement Phase 1 with tests
4. [ ] Iterate through remaining phases
5. [ ] Code review and merge
