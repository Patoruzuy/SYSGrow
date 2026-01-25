# Plant Growth Integration Complete 🌱

## Overview

Successfully integrated plant growth scheduling into the new architecture. Plants now automatically grow each day at midnight (00:00) through the TaskScheduler → PlantTimerObserver pattern.

## Architecture

```
┌─────────────────┐
│  GrowthService  │  Registry + Orchestrator
└────────┬────────┘
         │ manages
         ↓
┌─────────────────┐     bidirectional     ┌──────────────────────┐
│   UnitRuntime   │←─────reference───────→│ UnitRuntimeManager   │
│   (Domain)      │                        │  (Infrastructure)    │
└────────┬────────┘                        └──────────┬───────────┘
         │ owns                                       │ manages
         ↓                                            ↓
┌─────────────────┐                        ┌──────────────────────┐
│  PlantProfile   │                        │  PlantTimerObserver  │
│   Collection    │                        │    Collection        │
└─────────────────┘                        └──────────────────────┘
```

## Implementation Details

### 1. UnitRuntimeManager Plant Management

**File**: `infrastructure/hardware/unit_runtime_manager.py`

**New Fields**:
```python
self.unit_runtime: Optional['UnitRuntime'] = None
self._plant_observers: Dict[int, PlantTimerObserver] = {}
```

**Key Methods**:

#### `attach_unit_runtime(unit_runtime: 'UnitRuntime')`
Links the UnitRuntime domain model to the hardware manager.
- Enables plant observer management
- Called by `GrowthService.start_unit_runtime()`

#### `_setup_plant_observers()`
Creates PlantTimerObserver for each plant in the unit.
- Called automatically when hardware starts
- Attaches observers to TaskScheduler

#### `_schedule_plant_growth(growth_time: str = "00:00")`
Schedules daily growth notification at specified time.
- Default: midnight (00:00)
- Triggers all attached plant observers

#### `add_plant_observer(plant: PlantProfile)`
Adds observer for newly added plant.
- Called by `UnitRuntime.add_plant()`
- Automatically integrates into existing schedule

#### `remove_plant_observer(plant_id: int)`
Removes observer for deleted plant.
- Called by `UnitRuntime.remove_plant()`
- Cleans up TaskScheduler attachments

#### `reload_plant_observers()`
Clears and recreates all plant observers.
- Useful after bulk plant operations
- Ensures sync between plants and observers

### 2. PlantTimerObserver Class

**File**: `infrastructure/hardware/unit_runtime_manager.py` (lines 425-467)

**Purpose**: Observer pattern implementation for plant growth scheduling.

**Key Method**: `update(message=None)`
- Called daily by TaskScheduler
- Calls `plant.grow()` to advance growth
- Logs growth progress with stage and day info

**Example**:
```python
observer = PlantTimerObserver(plant)
task_scheduler.attach(observer)
task_scheduler.schedule_plant_growth("00:00")
```

### 3. GrowthService Integration

**File**: `app/services/growth.py`

**Updated**: `start_unit_runtime()` method (lines 127-140)

**Change**:
```python
# Create hardware manager
hardware_manager = UnitRuntimeManager(...)

# Attach to UnitRuntime
runtime.attach_hardware_manager(hardware_manager)

# NEW: Attach UnitRuntime to hardware manager (bidirectional)
hardware_manager.attach_unit_runtime(runtime)

# Start hardware (now includes plant growth scheduling)
return runtime.start_hardware()
```

**Result**: When unit starts, plant observers are automatically created and scheduled.

### 4. UnitRuntime Plant Notifications

**File**: `grow_room/unit_runtime.py`

**Updated Methods**:

#### `add_plant()` (lines 259-266)
```python
# Add to collection
with self.plant_lock:
    self.plants[plant_id] = plant

# NEW: Notify hardware manager to add plant observer
if self.hardware_manager:
    self.hardware_manager.add_plant_observer(plant)

# Publish event
self.event_bus.publish("plant_added", {...})
```

#### `remove_plant()` (lines 290-298)
```python
# Remove from collection
with self.plant_lock:
    del self.plants[plant_id]

# NEW: Notify hardware manager to remove plant observer
if self.hardware_manager:
    self.hardware_manager.remove_plant_observer(plant_id)

# Delete from database
self.database_handler.remove_plant(plant_id)
```

**Result**: Plant additions/removals automatically update growth scheduling.

## Growth Flow

### Daily Growth Cycle

1. **Midnight (00:00)**: TaskScheduler triggers 'grow' notification
2. **Observer Pattern**: All PlantTimerObserver instances receive notification
3. **Plant Growth**: Each observer calls `plant.grow()`
4. **Stage Progression**: `PlantProfile.grow()` increments `days_in_stage`
5. **Auto-Advancement**: If stage complete, automatically advances to next stage
6. **Event Publishing**: Growth events published via EventBus
7. **Logging**: Growth progress logged with stage/day info

### Example Log Output

```
🌱 Plant Tomato 1 (ID: 42) advanced growth: Stage 'vegetative' - Day 5
🌱 Plant Basil 2 (ID: 43) advanced growth: Stage 'flowering' - Day 12
```

### Plant Addition Flow

1. **User Action**: Add plant via API
2. **GrowthService**: Calls `unit_runtime.add_plant()`
3. **UnitRuntime**: Creates PlantProfile, adds to collection
4. **Hardware Notification**: Calls `hardware_manager.add_plant_observer(plant)`
5. **Observer Creation**: PlantTimerObserver created and attached
6. **Automatic Growth**: Plant now included in daily growth cycle

### Plant Removal Flow

1. **User Action**: Remove plant via API
2. **GrowthService**: Calls `unit_runtime.remove_plant()`
3. **UnitRuntime**: Removes from collection
4. **Hardware Notification**: Calls `hardware_manager.remove_plant_observer(plant_id)`
5. **Observer Cleanup**: Observer detached from TaskScheduler
6. **Database Cleanup**: Plant deleted from database

## Startup Sequence

When `GrowthService.start_unit_runtime(unit_id)` is called:

```
1. Get UnitRuntime from registry
2. Create UnitRuntimeManager(unit_id, ...)
3. runtime.attach_hardware_manager(hardware_manager)  ← UnitRuntime → HW Manager
4. hardware_manager.attach_unit_runtime(runtime)      ← HW Manager → UnitRuntime
5. runtime.start_hardware()
   └─→ hardware_manager.start()
       ├─→ Start sensor polling
       ├─→ Start climate control
       └─→ IF unit_runtime attached:
           ├─→ _setup_plant_observers()    ← Create observers for all plants
           └─→ _schedule_plant_growth()    ← Schedule daily growth at 00:00
```

## Configuration

### Growth Time

Default growth time: **00:00 (midnight)**

To change:
```python
# In unit_runtime_manager.py, modify _schedule_plant_growth()
self._schedule_plant_growth("06:00")  # 6 AM instead
```

### Custom Growth Schedules

Each unit can have different growth schedules:
```python
# In start() method, pass custom time
if self.unit_runtime:
    self._setup_plant_observers()
    self._schedule_plant_growth("08:00")  # Custom time per unit
```

## Testing

### Manual Testing

1. **Create Unit with Plants**:
```python
unit_id = growth_service.create_unit("Test Unit", "Lab", user_id=1)
plant_id = growth_service.add_plant(unit_id, "Tomato", "tomato", "seedling")
```

2. **Start Unit Runtime**:
```python
growth_service.start_unit_runtime(unit_id)
# Check logs for: "🌿 Setup 1 plant observers for unit X"
```

3. **Verify Growth Scheduling**:
```python
# Wait for midnight (00:00) or modify growth_time for testing
# Check logs for: "🌱 Plant Tomato (ID: X) advanced growth: Stage 'seedling' - Day 1"
```

4. **Test Plant Addition**:
```python
new_plant_id = growth_service.add_plant(unit_id, "Basil", "basil", "seedling")
# Check logs for: "🌿 Added plant 'Basil' (ID: X) to unit Y"
# Check logs for: "🌿 Added plant observer for Basil (ID: X)"
```

5. **Test Plant Removal**:
```python
growth_service.remove_plant(plant_id)
# Check logs for: "🗑️ Removed plant X from unit Y"
# Check logs for: "🗑️ Removed plant observer for plant X"
```

### Automated Testing

Create test in `tests/test_plant_growth_integration.py`:
```python
def test_plant_growth_scheduling():
    # Create unit with plants
    # Start runtime
    # Verify observers created
    # Manually trigger growth
    # Verify plant.grow() called
    # Verify logs generated
```

## Benefits

1. **Automatic Growth**: Plants grow every day without manual intervention
2. **Dynamic Management**: Add/remove plants anytime, growth schedule updates automatically
3. **Loose Coupling**: Observer pattern keeps domain and infrastructure separated
4. **Extensible**: Easy to add custom growth logic, schedules, or notifications
5. **Traceable**: Comprehensive logging for debugging and monitoring
6. **Thread-Safe**: Observer dictionary protected, safe for concurrent operations

## Edge Cases Handled

1. **Unit Started Without Plants**: Warning logged, no observers created (no error)
2. **Plants Added After Startup**: Observer added immediately, participates in next growth cycle
3. **Hardware Manager Not Attached**: No observers created (safe degradation)
4. **UnitRuntime Not Attached**: Warning logged when hardware starts
5. **Observer Errors**: Caught and logged, doesn't crash entire growth cycle

## Future Enhancements

1. **Variable Growth Rates**: Different schedules per plant type
2. **Growth Metrics**: Track growth velocity, stage duration analytics
3. **Growth Notifications**: Alert users when plants reach maturity
4. **Manual Growth Trigger**: API endpoint to manually advance plant growth
5. **Growth History**: Database table to track historical growth events

## Related Files

- `infrastructure/hardware/unit_runtime_manager.py` - Plant observer management
- `grow_room/unit_runtime.py` - Plant collection, hardware notifications
- `grow_room/plant_profile.py` - Plant growth logic (`grow()` method)
- `app/services/growth.py` - Unit startup, bidirectional attachment
- `task_scheduler.py` - Timer, observer pattern, scheduling

## Status

✅ **COMPLETE** - Plant growth integration fully implemented and integrated

**Completed**:
- ✅ Added plant observer infrastructure to UnitRuntimeManager
- ✅ Integrated PlantTimerObserver class
- ✅ Updated GrowthService to attach UnitRuntime bidirectionally
- ✅ Updated UnitRuntime to notify hardware manager on plant changes
- ✅ Modified startup sequence to setup observers automatically
- ✅ Handled edge cases (no plants, late additions, errors)

**Ready for**:
- ⏳ Integration testing
- ⏳ Production deployment
- ⏳ User acceptance testing

---

*Last Updated: 2025-01-XX*
*Architecture Version: 2.0 (Post-Refactor)*
