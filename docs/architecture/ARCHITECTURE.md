# New Growth Unit Architecture

## Overview

The growth unit management system has been refactored into a clean, layered architecture with clear separation of concerns.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                    Flask Blueprints                         │
│              (API endpoints, HTTP concerns)                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                   GrowthService                             │
│         (App-level registry & orchestrator)                 │
│  • Manages dict of {unit_id: UnitRuntime}                  │
│  • Caching layer (reduce DB calls)                         │
│  • Coordinates unit lifecycle                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    UnitRuntime                              │
│            (Domain model for one unit)                      │
│  • Owns PlantProfile instances                              │
│  • Manages unit settings (thresholds, schedules)            │
│  • Active plant selection                                   │
│  • AI condition application                                 │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              UnitRuntimeManager                             │
│        (Infrastructure - hardware operations)               │
│  • Sensor polling (GPIO + MQTT)                             │
│  • Climate control automation                               │
│  • Actuator management                                      │
│  • EventBus communication                                   │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. GrowthService (`app/services/growth.py`)

**Role**: Application-level registry and orchestrator

**Responsibilities**:
- Maintain registry of active `UnitRuntime` instances
- Provide caching layer before repository calls
- Manage unit lifecycle (create, start, stop, delete)
- Coordinate between domain and infrastructure layers

**Key Methods**:
```python
# Registry management
get_unit_runtime(unit_id) -> UnitRuntime
start_unit_runtime(unit_id) -> bool
stop_unit_runtime(unit_id) -> bool

# CRUD operations (with caching)
list_units(user_id=None) -> List[dict]
get_unit(unit_id) -> dict
create_unit(name, location, ...) -> int
update_unit(unit_id, name, location) -> dict
delete_unit(unit_id) -> None

# Plant management
list_plants(unit_id) -> List[dict]
add_plant(unit_id, name, plant_type, ...) -> int
remove_plant(unit_id, plant_id) -> None

# Settings
get_thresholds(unit_id) -> dict
set_thresholds(unit_id, **thresholds) -> dict
```

**Caching Strategy**:
- Unit data cached to reduce database queries
- Cache cleared on create/update/delete operations
- Registry holds active `UnitRuntime` instances in memory

### 2. UnitRuntime (`grow_room/unit_runtime.py`)

**Role**: Domain model for a single growth unit

**Responsibilities**:
- Manage `PlantProfile` instances (add, remove, set active)
- Maintain unit settings (thresholds, schedules, dimensions)
- Apply AI-based environmental conditions
- Coordinate with hardware layer (`UnitRuntimeManager`)
- Pure domain logic - no HTTP/database concerns

**Key Methods**:
```python
# Plant management
load_plants_from_db() -> None
add_plant(name, plant_type, stage, growth_stages) -> int
remove_plant(plant_id) -> bool
get_plant(plant_id) -> PlantProfile
get_all_plants() -> List[PlantProfile]
set_active_plant(plant_id) -> bool

# Settings management
update_settings(**kwargs) -> bool
set_light_schedule(start_time, end_time) -> bool

# AI integration
apply_ai_conditions(data=None) -> None

# Hardware coordination
attach_hardware_manager(hardware_manager) -> None
start_hardware() -> bool
stop_hardware() -> bool
is_hardware_running() -> bool

# Status
get_status() -> dict
to_dict() -> dict
```

**Data Classes**:
```python
@dataclass
class UnitDimensions:
    width: float   # cm
    height: float  # cm
    depth: float   # cm

@dataclass
class UnitSettings:
    temperature_threshold: float = 24.0
    humidity_threshold: float = 50.0
    soil_moisture_threshold: float = 40.0
    co2_threshold: float = 1000.0
    voc_threshold: float = 1000.0
    light_intensity_threshold: float = 1000.0
    aqi_threshold: float = 1000.0
    light_start_time: str = "08:00"
    light_end_time: str = "20:00"
    unit_dimensions: Optional[UnitDimensions] = None
```

### 3. UnitRuntimeManager (`infrastructure/hardware/unit_runtime_manager.py`)

**Role**: Infrastructure layer for physical hardware operations

**Responsibilities**:
- Sensor polling (GPIO + MQTT + Redis)
- Climate control automation (PID loops)
- Actuator management
- EventBus communication
- Task scheduling

**Key Components**:
- `SensorManager`: GPIO and wireless sensor management
- `ActuatorController`: Relay and device control
- `SensorPollingService`: Periodic sensor reading
- `ClimateController`: PID-based climate automation
- `TaskScheduler`: Device scheduling (lights, fans)

## Benefits of New Architecture

### 1. **Clean Separation of Concerns**
- **Domain** (UnitRuntime): Business logic, plants, settings
- **Infrastructure** (UnitRuntimeManager): Hardware operations
- **Application** (GrowthService): Orchestration, caching, lifecycle

### 2. **Single Responsibility**
- `GrowthService`: Registry and orchestration
- `UnitRuntime`: One unit's domain logic
- `UnitRuntimeManager`: Hardware operations for one unit

### 3. **Improved Performance**
- Caching layer reduces database calls
- Unit runtimes kept in memory
- Efficient plant and settings access

### 4. **Better Testability**
- Domain logic (UnitRuntime) isolated from infrastructure
- Mock hardware manager easily for testing
- No Flask dependencies in domain layer

### 5. **Scalability**
- Easy to add new units (just add to registry)
- Units can be started/stopped independently
- Clear entry points for multi-user support

## Migration from Old Architecture

### Deprecated Classes

The following classes are **deprecated** and replaced:

| Old Class | New Class | Notes |
|-----------|-----------|-------|
| `GrowthUnit` | `UnitRuntime` | Domain model now pure, no hardware mixing |
| `GrowthUnitManager` | `GrowthService` | Renamed to reflect registry role |
| `UnitService` | *Removed* | API concerns moved to blueprints |

### Breaking Changes

1. **Imports**:
   ```python
   # OLD (deprecated)
   from grow_room.growth_unit import GrowthUnit
   from grow_room.growth_hub_manager import GrowthUnitManager
   
   # NEW
   from grow_room.unit_runtime import UnitRuntime
   from app.services.growth import GrowthService
   ```

2. **Initialization**:
   ```python
   # OLD
   manager = GrowthUnitManager(database_handler)
   unit = GrowthUnit(unit_id, name, location, redis_client, db_handler)
   
   # NEW
   service = GrowthService(repository, audit_logger, db_handler, mqtt_client)
   runtime = service.get_unit_runtime(unit_id)  # Loads from DB automatically
   ```

3. **Hardware Management**:
   ```python
   # OLD
   unit.climate_controller.start()
   
   # NEW
   service.start_unit_runtime(unit_id)  # Creates and starts hardware automatically
   ```

## Usage Examples

### Creating a New Unit

```python
from app.services.growth import GrowthService

# Create unit
unit_id = growth_service.create_unit(
    name="Indoor Tent 1",
    location="Indoor",
    user_id=1,
    dimensions={"width": 120, "height": 200, "depth": 120}
)

# Hardware starts automatically
runtime = growth_service.get_unit_runtime(unit_id)
print(runtime.is_hardware_running())  # True
```

### Adding Plants

```python
# Add plant
plant_id = growth_service.add_plant(
    unit_id=unit_id,
    name="Tomato 1",
    plant_type="tomato",
    current_stage="seedling"
)

# Set as active plant for climate control
runtime = growth_service.get_unit_runtime(unit_id)
runtime.set_active_plant(plant_id)
```

### Updating Settings

```python
# Update thresholds
growth_service.set_thresholds(
    unit_id=unit_id,
    temperature_threshold=26.0,
    humidity_threshold=60.0,
    soil_moisture_threshold=50.0
)

# Set light schedule
runtime = growth_service.get_unit_runtime(unit_id)
runtime.set_light_schedule("08:00", "22:00")
```

### Accessing Unit Data

```python
# Get unit details (cached)
unit_data = growth_service.get_unit(unit_id)

# Get runtime instance (with plants)
runtime = growth_service.get_unit_runtime(unit_id)
plants = runtime.get_all_plants()
active_plant = runtime.active_plant

# Get comprehensive status
status = runtime.get_status()
# Returns: {
#   "unit_id": 1,
#   "name": "Indoor Tent 1",
#   "settings": {...},
#   "plants": [...],
#   "active_plant": "Tomato 1",
#   "hardware_running": True,
#   ...
# }
```

### Stopping a Unit

```python
# Stop hardware operations
growth_service.stop_unit_runtime(unit_id)

# Delete unit (stops hardware first)
growth_service.delete_unit(unit_id)
```

## Caching Details

### Cache Hierarchy

1. **Registry Cache** (`_unit_runtimes`):
   - In-memory `UnitRuntime` instances
   - Contains full domain objects with plants
   - Cleared only when unit is stopped/deleted

2. **Data Cache** (`_unit_cache`):
   - Database query results
   - Unit metadata and settings
   - Cleared on create/update/delete

### Cache Keys

```python
# Single unit
cache_key = unit_id  # int

# User's units
cache_key = f"user_{user_id}_units"

# All units
cache_key = "all_units"
```

### Cache Strategy

- **Read-through**: Check cache → DB → update cache
- **Write-through**: Update DB → clear cache
- **Lazy loading**: Units loaded into registry on first access

## Thread Safety

- `_runtime_lock`: Protects unit runtime registry
- `_cache_lock`: Protects data cache
- `plant_lock`: Protects plant collections in UnitRuntime
- All operations use appropriate locks

## Event Bus Integration

UnitRuntime subscribes to events:
- `plant_added`: Log plant addition
- `plant_removed`: Log plant removal
- `plant_stage_update`: Apply AI conditions
- `thresholds_update`: Update hardware

## Next Steps

1. ✅ **Completed**:
   - Created `UnitRuntime` domain class
   - Refactored `GrowthService` as registry
   - Added caching layer
   - Deprecated old classes

2. **TODO**:
   - Move `unit_service.py` API methods to blueprints
   - Test unit initialization and hardware coordination
   - Update Flask application to use new GrowthService
   - Add unit tests for new architecture

## Files Changed

| File | Status | Description |
|------|--------|-------------|
| `grow_room/unit_runtime.py` | ✅ Created | New domain model |
| `app/services/growth.py` | ✅ Refactored | Registry with caching |
| `grow_room/growth_unit.py` | ⚠️ Deprecated | Old class marked deprecated |
| `grow_room/growth_hub_manager.py` | ⚠️ Deprecated | Old manager marked deprecated |
| `app/services/unit_service.py` | ⏳ Pending | To be removed/refactored |

---

**Author**: Senior Engineering Team  
**Date**: November 2025  
**Status**: Phase 1 Complete - Ready for Testing
