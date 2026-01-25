# SYSGrow Architecture Boundaries

## Single Responsibility Services

### 🌱 PlantJsonHandler
**Responsibility**: Plant species metadata (catalog)  
**Location**: `app/utils/plant_json_handler.py`

**Owns**:
- Growth stages definitions
- Lighting schedules per stage
- Automation settings (watering, alerts)
- Plant catalog (species, varieties)
- GDD base temperatures
- Companion planting info
- Harvest guides

**Access Pattern**: 
- ✅ Services call PlantJsonHandler methods
- ✅ PlantViewService provides convenience wrappers
- ❌ No direct file access elsewhere

**Key Methods**:
```python
handler.get_growth_stages(plant_type)
handler.get_lighting_schedule(plant_type)
handler.get_automation_settings(plant_type)
handler.get_gdd_base_temp_c(plant_type)
```

---

### 🎯 ThresholdService
**Responsibility**: Environmental thresholds  
**Location**: `app/services/application/threshold_service.py`

**Owns**:
- Unit-level thresholds (temperature, humidity, etc.)
- Plant-specific threshold overrides
- AI-proposed threshold updates
- Threshold validation & filtering
- Threshold persistence to DB

**Access Pattern**:
- ✅ Services call ThresholdService methods
- ❌ No direct threshold DB queries elsewhere
- ❌ No direct plants_info.json threshold extraction

**Key Methods**:
```python
threshold_service.get_thresholds(plant_type, growth_stage)
threshold_service.get_unit_thresholds(unit_id)
threshold_service.get_plant_overrides(plant_id)
threshold_service.update_unit_thresholds(unit_id, thresholds)
```

---

### 📅 SchedulingService
**Responsibility**: Device schedules  
**Location**: `app/services/hardware/scheduling_service.py`

**Owns**:
- All device schedules (lights, fans, pumps)
- Schedule CRUD operations
- Schedule conflict detection
- Schedule execution logic
- Schedule persistence to DB

**Access Pattern**:
- ✅ Services call SchedulingService methods
- ✅ UnifiedScheduler executes via SchedulingService
- ❌ No direct schedule DB queries elsewhere
- ❌ No direct device_schedules JSON handling

**Key Methods**:
```python
scheduling_service.create_schedule(schedule)
scheduling_service.get_schedules_for_unit(unit_id)
scheduling_service.is_device_active(unit_id, device_type)
scheduling_service.generate_schedules_from_plant(unit_id, plant_info)
```

---

### 🌿 PlantViewService
**Responsibility**: Plant instances (DB + memory)  
**Location**: `app/services/application/plant_service.py`

**Owns**:
- Plant instance lifecycle (create, update, delete)
- Plant-sensor linking
- In-memory plant collection
- Active plant tracking
- Plant context resolution

**Delegates To**:
- **PlantJsonHandler**: Species metadata (growth stages, lighting)
- **ThresholdService**: Environmental thresholds
- **SchedulingService**: Device schedules

**Access Pattern**:
- ✅ Services call PlantViewService for plant instances
- ✅ PlantViewService calls PlantJsonHandler for species data
- ❌ No direct plant DB queries elsewhere (use PlantViewService)

**Key Methods**:
```python
# Plant instances
plant_service.create_plant(unit_id, plant_name, plant_type, ...)
plant_service.list_plants(unit_id)
plant_service.get_plant(plant_id)
plant_service.update_plant(plant_id, updates)

# Species metadata (delegates to PlantJsonHandler)
plant_service.get_plant_growth_stages(plant_type)
plant_service.get_plant_lighting_schedule(plant_type)
plant_service.get_plant_automation_settings(plant_type)
```

---

### 🏗️ GrowthService
**Responsibility**: Unit orchestration  
**Location**: `app/services/application/growth_service.py`

**Owns**:
- Unit runtime lifecycle
- Unit CRUD operations
- Hardware coordination
- Unit cache management

**Delegates To**:
- **PlantViewService**: All plant operations
- **ThresholdService**: All threshold operations
- **SchedulingService**: All schedule operations

**Key Methods**:
```python
growth_service.create_unit(name, location, ...)
growth_service.start_unit(unit_id)
growth_service.stop_unit(unit_id)
growth_service.get_unit_runtime(unit_id)

# Thin wrappers (delegate to PlantViewService)
growth_service.add_plant_to_unit(...)  # → plant_service.create_plant()
growth_service.set_active_plant(...)   # → plant_service.set_active_plant()
```

---

## Data Flow Patterns

### Plant Creation Flow
```
User/API
  ↓
PlantViewService.create_plant()
  ├→ PlantJsonHandler.get_growth_stages()  # Species metadata
  ├→ PlantJsonHandler.get_lighting_schedule()
  ├→ Repository.create_plant()              # DB persistence
  ├→ Memory storage (in PlantViewService)
  └→ EventBus.publish(PLANT_ADDED)
       ↓
GrowthService (subscribes to event)
  └→ Invalidate unit cache
```

### Threshold Application Flow
```
User/API
  ↓
ThresholdService.get_thresholds(plant_type, stage)
  ├→ PlantJsonHandler.get_plant_info()      # Species data
  ├→ Calculate optimal thresholds
  └→ Return EnvironmentalThresholds object
       ↓
GrowthService/ClimateController
  └→ Apply to hardware
```

### Schedule Creation Flow
```
User/API or PlantViewService
  ↓
SchedulingService.create_schedule()
  ├→ Validate schedule
  ├→ Check conflicts
  ├→ Repository.create_schedule()           # DB persistence
  ├→ Memory storage (in SchedulingService)
  └→ EventBus.publish(SCHEDULE_CREATED)
       ↓
UnifiedScheduler
  └→ Register for execution
```

---

## Migration Complete ✅

### Removed Legacy Code (~670 lines)
- ❌ `device_schedules` field from UnitSettings
- ❌ `light_mode` field from UnitSettings
- ❌ `_normalize_unit_record()` from GrowthService
- ❌ `_serialize_plant()` from GrowthService
- ❌ `_resolve_growth_stages()` from GrowthService
- ❌ `_load_plants()` from UnitRuntimeFactory
- ❌ `_create_plant_profile()` fallback from UnitRuntimeFactory

### New Architecture
- ✅ **UnitRepository** for unit operations
- ✅ **PlantRepository** for plant operations
- ✅ **GrowthRepository** as compatibility facade
- ✅ PlantViewService owns plant lifecycle
- ✅ PlantJsonHandler is single source for species data
- ✅ ThresholdService is single source for thresholds
- ✅ SchedulingService is single source for schedules

---

## Rules of Thumb

1. **Plant species data?** → PlantJsonHandler
2. **Plant instance data?** → PlantViewService
3. **Environmental thresholds?** → ThresholdService
4. **Device schedules?** → SchedulingService
5. **Unit operations?** → GrowthService
6. **Need plant metadata?** → Call PlantViewService helpers (which delegate to PlantJsonHandler)

**Golden Rule**: Each service has exactly ONE source of truth for its domain.

---

## Benefits

✅ **Clear boundaries** - No confusion about where data lives  
✅ **Easy testing** - Mock single service instead of multiple  
✅ **Maintainability** - Changes isolated to one service  
✅ **Type safety** - Domain objects (EnvironmentalThresholds, Schedule, PlantProfile)  
✅ **Performance** - Memory-first patterns with DB fallback  
✅ **Auditability** - Single place for each operation type

---

## See Also

- [AI_REFACTORING_COMPLETE.md](AI_REFACTORING_COMPLETE.md) - Detailed refactoring summary
- [AGENTS.md](AGENTS.md) - Development guidelines
