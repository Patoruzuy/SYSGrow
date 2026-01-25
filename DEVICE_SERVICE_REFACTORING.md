# DeviceService Refactoring Summary

**Date**: December 8, 2025  
**Session**: Session 8 - Code Structure Cleanup (Part 2)

## Overview

Split monolithic DeviceService (1757 lines, 44 methods) into 3 focused services following single-responsibility principle:

1. **DeviceCrudService**: Device lifecycle (CRUD, discovery) - 670 lines
2. **DeviceHealthService**: Health domain (monitoring, calibration, anomalies) - 687 lines  
3. **DeviceCoordinator**: Runtime coordination (EventBus, state tracking) - 358 lines

**Total**: ~1,715 lines (similar size but better organized)

## Architecture Changes

### Before
```
DeviceService (1757 lines)
├── Sensor CRUD (5 methods)
├── Actuator CRUD (8 methods)
├── Actuator Control (7 methods)
├── Sensor Health (7 methods)
├── Actuator Health (6 methods)
├── Actuator Anomaly (3 methods)
├── Actuator Calibration (2 methods)
├── EventBus Handlers (3 methods)
└── State History (5 methods)
```

### After
```
DeviceCrudService (670 lines)
├── Sensor CRUD (list, get, create, delete, read)
├── Actuator CRUD (list, create, delete)
├── Finders (find_actuator_by_type, find_actuator_by_device_name)
└── Discovery (permit_zigbee_device_join, discover_mqtt_sensors)

DeviceHealthService (687 lines)
├── Sensor Health (calibrate, health, anomalies, statistics)
├── Sensor History (calibration, health, anomaly)
├── Actuator Health (save, get_history)
├── Actuator Anomaly (log, get, resolve)
├── Actuator Calibration (save, get)
└── Actuator Power (save_reading, get_readings)

DeviceCoordinator (358 lines)
├── EventBus Subscriptions (start/stop)
├── Event Handlers (_on_relay_state_changed, _on_actuator_state_changed, _on_connectivity_changed)
└── State Queries (get_actuator_state_history, get_connectivity_history, prune_history)
```

## Implementation Details

### DeviceCrudService (app/services/device_crud_service.py)
**Purpose**: Handle device lifecycle operations only

**Key Features**:
- Memory-first architecture: Check runtime managers before database
- EventBus integration: Publishes SENSOR_CREATED, SENSOR_DELETED, ACTUATOR_CREATED, ACTUATOR_DELETED
- Protocol-aware: Handles GPIO, MQTT, Zigbee, wireless sensors
- Auto-start runtimes: Starts unit runtime if not running when accessing hardware

**Methods** (14 total):
- `list_sensors(unit_id)`: Memory-first sensor list with runtime fallback
- `get_sensor(sensor_id)`: Find sensor across all runtimes
- `create_sensor(**kwargs)`: DB → runtime sync → EventBus
- `delete_sensor(sensor_id)`: Runtime unregister → DB delete → EventBus
- `read_sensor(sensor_id)`: Real-time reading from runtime
- `list_actuators(unit_id)`: Memory-first actuator list
- `create_actuator(**kwargs)`: DB → runtime registration → EventBus
- `delete_actuator(actuator_id)`: Runtime unregister → DB → EventBus
- `find_actuator_by_type(type)`: First match by type
- `find_actuator_by_device_name(name)`: Match by device name
- `permit_zigbee_device_join(unit_id, duration)`: Enable Zigbee pairing
- `discover_mqtt_sensors(unit_id, prefix)`: MQTT sensor discovery
- `count_devices()`: Total device count
- `_get_runtime_with_hardware(unit_id)`: Helper with auto-start

### DeviceHealthService (app/services/device_health_service.py)
**Purpose**: Handle all health, calibration, and anomaly operations

**Key Features**:
- Delegates to UnitRuntimeManager.hardware_manager for real-time health data
- Persists health snapshots and anomalies to database
- EventBus integration: Publishes ACTUATOR_ANOMALY_DETECTED, ACTUATOR_ANOMALY_RESOLVED, ACTUATOR_CALIBRATION_UPDATED
- Unified sensor lookup helper: _get_sensor_unit_id() finds sensor across all runtimes

**Methods** (17 total):
- Sensor Health:
  * `calibrate_sensor(sensor_id, reference_value, calibration_type)`
  * `get_sensor_health(sensor_id)`: Health score, status, error_rate
  * `check_sensor_anomalies(sensor_id)`: Anomaly detection
  * `get_sensor_statistics(sensor_id)`: mean, std_dev, min, max
  * `get_sensor_calibration_history(sensor_id, limit)`
  * `get_sensor_health_history(sensor_id, limit)`
  * `get_sensor_anomaly_history(sensor_id, limit)`
- Actuator Health:
  * `save_actuator_health(actuator_id, health_score, status, ...)`
  * `get_actuator_health_history(actuator_id, limit)`
- Actuator Anomaly:
  * `log_actuator_anomaly(actuator_id, type, severity, details)`
  * `get_actuator_anomalies(actuator_id, limit)`
  * `resolve_actuator_anomaly(anomaly_id)`
- Actuator Calibration:
  * `save_actuator_calibration(actuator_id, type, data)`
  * `get_actuator_calibrations(actuator_id)`
- Actuator Power:
  * `save_actuator_power_reading(actuator_id, power_watts, ...)`
  * `get_actuator_power_readings(actuator_id, limit, hours)`

### DeviceCoordinator (app/services/device_coordinator.py)
**Purpose**: Coordinate device state across application layers

**Key Features**:
- EventBus subscriber: Listens to hardware events
- State persistence: Saves state changes to database for historical tracking
- Lifecycle management: start() subscribes to events, stop() unsubscribes
- Timestamp normalization: Handles both datetime and ISO string timestamps

**Methods** (10 total):
- Lifecycle:
  * `start()`: Subscribe to 3 hardware events
  * `stop()`: Unsubscribe from all events
- Event Handlers (private):
  * `_on_relay_state_changed(payload)`: Persist relay state changes
  * `_on_actuator_state_changed(payload)`: Persist actuator state changes
  * `_on_connectivity_changed(payload)`: Persist connectivity events
- State Queries:
  * `get_actuator_state_history(actuator_id, start_time, end_time, limit)`
  * `get_unit_actuator_state_history(unit_id, start_time, end_time, limit)`
  * `get_recent_actuator_state(actuator_id)`
  * `get_connectivity_history(device_id, device_type, hours, limit)`
  * `prune_actuator_state_history(days)`

## ServiceContainer Integration

### Added Fields
```python
device_crud_service: DeviceCrudService
device_health_service: DeviceHealthService
device_coordinator: DeviceCoordinator
```

### Initialization (in ServiceContainer.build())
```python
# Initialize EventBus
event_bus = EventBus()

# Initialize new focused device services
device_crud_service = DeviceCrudService(
    repository=device_repo,
    growth_service=growth_service
)

device_health_service = DeviceHealthService(
    repository=device_repo,
    growth_service=growth_service
)

device_coordinator = DeviceCoordinator(
    repository=device_repo,
    event_bus=event_bus
)

# Start coordinator to subscribe to hardware events
device_coordinator.start()
```

### Shutdown (in ServiceContainer.shutdown())
```python
# Stop device coordinator event subscriptions
self.device_coordinator.stop()
```

## API Migration Map

### Files to Update (8 API files)

**app/blueprints/api/devices/sensors.py**:
- `list_sensors()` → device_crud_service.list_sensors()
- `create_sensor()` → device_crud_service.create_sensor()
- `delete_sensor()` → device_crud_service.delete_sensor()
- `read_sensor()` → device_crud_service.read_sensor()
- `calibrate_sensor()` → device_health_service.calibrate_sensor()
- `check_sensor_anomalies()` → device_health_service.check_sensor_anomalies()
- `get_sensor_statistics()` → device_health_service.get_sensor_statistics()
- `discover_mqtt_sensors()` → device_crud_service.discover_mqtt_sensors()
- `get_sensor_calibration_history()` → device_health_service.get_sensor_calibration_history()
- `get_sensor_health_history()` → device_health_service.get_sensor_health_history()
- `get_sensor_anomaly_history()` → device_health_service.get_sensor_anomaly_history()

**app/blueprints/api/devices/actuators/crud.py**:
- `list_actuators()` → device_crud_service.list_actuators()
- `create_actuator()` → device_crud_service.create_actuator()
- `delete_actuator()` → device_crud_service.delete_actuator()

**app/blueprints/api/devices/actuators/control.py**:
- `list_actuators()` → device_crud_service.list_actuators()
- (control methods stay in DeviceService)

**app/blueprints/api/devices/actuators/analytics.py**:
- `list_actuators()` → device_crud_service.list_actuators()

**app/blueprints/api/devices/actuators/energy.py**:
- `get_actuator_calibrations()` → device_health_service.get_actuator_calibrations()
- `save_actuator_calibration()` → device_health_service.save_actuator_calibration()

**app/blueprints/api/devices/zigbee.py**:
- `get_sensor()` → device_crud_service.get_sensor()

**app/blueprints/api/devices/shared.py**:
- `list_sensors()` → device_crud_service.list_sensors()
- `list_actuators()` → device_crud_service.list_actuators()

**app/blueprints/api/health/__init__.py**:
- `get_sensor_health()` → device_health_service.get_sensor_health()
- `save_actuator_health()` → device_health_service.save_actuator_health()

### Methods Remaining in DeviceService

**Actuator Control** (7 methods - NOT moved):
- `control_actuator(actuator_id, command, value, unit_id)`
- `get_actuator_state(actuator_id, unit_id)`
- `set_actuator_schedule(actuator_id, start_time, end_time, ...)`
- `clear_actuator_schedule(actuator_id, unit_id)`
- `get_actuator_runtime_stats(actuator_id, unit_id)`

These remain in DeviceService because they're runtime control operations, not CRUD or health monitoring.

## Benefits

### Separation of Concerns
- **DeviceCrudService**: Pure lifecycle management (create, read, update, delete, discover)
- **DeviceHealthService**: Pure health domain (monitoring, calibration, diagnostics)
- **DeviceCoordinator**: Pure coordination (event handling, state persistence)

### Improved Testability
- Each service can be tested independently
- Mock dependencies are simpler (fewer methods per service)
- Health tests don't need CRUD operations and vice versa

### Better Maintainability
- Clear boundaries for feature additions
- Health monitoring changes isolated from CRUD logic
- EventBus coordination centralized in one place

### Reusability
- Services can be composed differently if needed
- Health monitoring can be used without CRUD operations
- Coordinator can track state for other device types

## Migration Status

✅ **Completed**:
1. Created DeviceCrudService (~670 lines)
2. Created DeviceHealthService (~687 lines)
3. Created DeviceCoordinator (~358 lines)
4. Updated ServiceContainer (added 3 new services)
5. Added coordinator.start() in initialization
6. Added coordinator.stop() in shutdown
7. Updated API endpoints (8 files):
   - ✅ app/blueprints/api/devices/sensors.py (11 endpoints)
   - ✅ app/blueprints/api/devices/actuators/crud.py (3 endpoints)
   - ✅ app/blueprints/api/devices/actuators/control.py (1 endpoint)
   - ✅ app/blueprints/api/devices/actuators/analytics.py (1 endpoint)
   - ✅ app/blueprints/api/devices/actuators/energy.py (2 endpoints)
   - ✅ app/blueprints/api/devices/zigbee.py (2 endpoints)
   - ✅ app/blueprints/api/devices/shared.py (2 endpoints)
   - ✅ app/blueprints/api/health/__init__.py (2 endpoints)
8. Added API utility functions (_device_crud_service, _device_health_service, _device_coordinator)
9. Tested ServiceContainer initialization ✅
10. Tested Flask app initialization ✅
11. Verified API utility functions ✅

**All 7 tasks complete! Migration successful!**

## Testing Plan

### Unit Tests
- [ ] DeviceCrudService tests (CRUD operations, discovery)
- [ ] DeviceHealthService tests (health, calibration, anomalies)
- [ ] DeviceCoordinator tests (event handling, state persistence)

### Integration Tests
- [ ] ServiceContainer initialization with all services
- [ ] EventBus flow: hardware → coordinator → database
- [ ] Memory-first pattern: runtime → database fallback
- [ ] API endpoints using new services

### Regression Tests
- [ ] All existing API tests pass with new services
- [ ] Hardware operations still work correctly
- [ ] State tracking persists correctly
- [ ] Health monitoring data accurate

## Notes

- Original DeviceService still exists with control methods (not refactored yet)
- No backward-compatible wrapper created (user chose Option A: direct migration)
- All new services use correct import paths (app.enums.events, app.utils.event_bus, infrastructure.database.repositories.devices)
- DeviceCoordinator properly starts/stops during container lifecycle
- Memory-first architecture preserved in all services
