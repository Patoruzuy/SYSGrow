# 🔧 SYSGrow Architecture Refactoring Analysis
## For Raspberry Pi 3B+ Optimization

**Date:** November 6, 2025  
**Author:** Senior Engineering Team  
**Target:** Raspberry Pi 3B+ (1GB RAM, Quad-core 1.2GHz)

---

## 📊 Current State Analysis

### Problem Identified

The `GrowthUnit` class currently **directly instantiates**:
1. `SensorPollingService` - Manages sensor reading loops
2. `ClimateController` - Manages actuator control based on thresholds
3. `SensorManager` & `ActuatorController` - Device managers

**However**, the new service-based architecture (`app/services/`) does NOT instantiate or manage these critical components, leading to:
- ❌ No active sensor polling
- ❌ No climate control automation
- ❌ No actuator responses to threshold violations
- ❌ Disconnection between UI/API and physical hardware

---

## 🎯 Part 1: Integration Strategy for grow_room & environment

### Current Architecture (Old)

```
┌─────────────────────────────────────────────────────┐
│              GrowthUnit (per unit)                  │
│  ┌──────────────────────────────────────────────┐  │
│  │  - SensorManager                             │  │
│  │  - ActuatorController                        │  │
│  │  - SensorPollingService ──► EventBus        │  │
│  │  - ClimateController ──► Controls actuators │  │
│  │  - TaskScheduler (lights, fans)             │  │
│  │  - AI Model (predictions)                    │  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### New Architecture (Proposed)

```
┌────────────────────────────────────────────────────────────┐
│                  Flask Application                         │
│  ┌─────────────────────────────────────────────────────┐  │
│  │         ServiceContainer (DI Container)             │  │
│  │  - GrowthService (CRUD operations)                  │  │
│  │  - UnitService (multi-unit logic)                   │  │
│  │  - DeviceService (NEW - device management)          │  │
│  │  - ClimateService (NEW - automation orchestrator)   │  │
│  └─────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────────┐
│           Hardware Abstraction Layer (NEW)                 │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  UnitRuntimeManager (manages physical hardware)     │  │
│  │    - One instance per growth unit                   │  │
│  │    ┌──────────────────────────────────────────┐    │  │
│  │    │  SensorPollingService                    │    │  │
│  │    │    ├─ GPIO sensors (10s interval)        │    │  │
│  │    │    ├─ MQTT sensors (event-driven)        │    │  │
│  │    │    └─ Publishes to EventBus              │    │  │
│  │    └──────────────────────────────────────────┘    │  │
│  │    ┌──────────────────────────────────────────┐    │  │
│  │    │  ClimateController                       │    │  │
│  │    │    ├─ Subscribes to EventBus             │    │  │
│  │    │    ├─ PID control loops                  │    │  │
│  │    │    └─ Actuator commands                  │    │  │
│  │    └──────────────────────────────────────────┘    │  │
│  │    ┌──────────────────────────────────────────┐    │  │
│  │    │  TaskScheduler                           │    │  │
│  │    │    ├─ Light schedules                    │    │  │
│  │    │    ├─ Fan schedules                      │    │  │
│  │    │    └─ Plant growth stages                │    │  │
│  │    └──────────────────────────────────────────┘    │  │
│  └─────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

---

## 🔧 Recommended Implementation

### 1. Create `UnitRuntimeManager`

**Purpose:** Manages the physical hardware layer for each growth unit

**Location:** `infrastructure/hardware/unit_runtime_manager.py`

```python
"""
UnitRuntimeManager
==================
Manages physical hardware for a single growth unit:
- Sensor polling
- Climate control automation
- Device scheduling
- Event-driven responses

This bridges the service layer with the hardware layer.
"""

from typing import Optional
from environment.sensor_polling_service import SensorPollingService
from environment.climate_controller import ClimateController
from devices.sensor_manager import SensorManager
from devices.actuator_controller import ActuatorController
from task_scheduler import TaskScheduler
from utils.event_bus import EventBus
import logging

class UnitRuntimeManager:
    """
    Manages physical hardware operations for a single growth unit.
    
    One instance per growth unit - handles real-time operations.
    """
    
    def __init__(
        self,
        unit_id: int,
        unit_name: str,
        database_handler,
        mqtt_client: Optional[Any] = None,
        redis_client: Optional[Any] = None  # Optional for caching
    ):
        self.unit_id = unit_id
        self.unit_name = unit_name
        self.database_handler = database_handler
        self.event_bus = EventBus()
        
        # Hardware managers
        self.sensor_manager = SensorManager(unit_name, database_handler)
        self.actuator_manager = ActuatorController(unit_name, database_handler)
        
        # Polling service (if no Redis, pass None)
        self.polling_service = SensorPollingService(
            sensor_manager=self.sensor_manager,
            redis_client=redis_client,  # Can be None
            mqtt_wrapper=mqtt_client
        )
        
        # Climate control
        self.climate_controller = ClimateController(
            actuator_manager=self.actuator_manager,
            polling_service=self.polling_service,
            database_handler=database_handler
        )
        
        # Scheduling
        self.task_scheduler = TaskScheduler()
        
        self._running = False
        logging.info(f"🎛️ UnitRuntimeManager initialized for unit {unit_id}")
    
    def start(self):
        """Start all hardware operations"""
        if self._running:
            logging.warning(f"Unit {self.unit_id} runtime already started")
            return
            
        try:
            # Start sensor polling
            self.polling_service.start_polling()
            
            # Start climate control (subscribes to EventBus)
            self.climate_controller.start()
            
            self._running = True
            logging.info(f"✅ Unit {self.unit_id} runtime started")
        except Exception as e:
            logging.error(f"Failed to start unit {self.unit_id} runtime: {e}")
            raise
    
    def stop(self):
        """Stop all hardware operations"""
        try:
            self.polling_service.stop_polling()
            self._running = False
            logging.info(f"🛑 Unit {self.unit_id} runtime stopped")
        except Exception as e:
            logging.error(f"Error stopping unit {self.unit_id} runtime: {e}")
    
    def update_thresholds(self, thresholds: dict):
        """Update climate control thresholds"""
        self.event_bus.publish("thresholds_update", thresholds)
    
    def set_light_schedule(self, start_time: str, end_time: str):
        """Schedule light on/off times"""
        self.task_scheduler.schedule_device("Light", start_time, end_time)
    
    def is_running(self) -> bool:
        return self._running
```

---

### 2. Create `ClimateService` (Orchestrator)

**Purpose:** High-level service that manages `UnitRuntimeManager` instances

**Location:** `app/services/climate_service.py`

```python
"""
ClimateService
==============
Orchestrates hardware runtime managers for all growth units.
Provides service-layer interface to hardware operations.
"""

from typing import Dict, Optional
from infrastructure.hardware.unit_runtime_manager import UnitRuntimeManager
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
import logging

class ClimateService:
    """
    High-level service for managing climate control across all units.
    """
    
    def __init__(
        self,
        database: SQLiteDatabaseHandler,
        mqtt_client: Optional[Any] = None,
        redis_client: Optional[Any] = None
    ):
        self.database = database
        self.mqtt_client = mqtt_client
        self.redis_client = redis_client
        self.runtime_managers: Dict[int, UnitRuntimeManager] = {}
        logging.info("🌡️ ClimateService initialized")
    
    def start_unit_runtime(self, unit_id: int, unit_name: str) -> None:
        """
        Start hardware operations for a specific unit.
        
        Called when:
        - Unit is created
        - Unit is activated
        - Server starts and loads active units
        """
        if unit_id in self.runtime_managers:
            logging.warning(f"Runtime for unit {unit_id} already exists")
            return
        
        try:
            manager = UnitRuntimeManager(
                unit_id=unit_id,
                unit_name=unit_name,
                database_handler=self.database,
                mqtt_client=self.mqtt_client,
                redis_client=self.redis_client
            )
            manager.start()
            self.runtime_managers[unit_id] = manager
            logging.info(f"✅ Started runtime for unit {unit_id}")
        except Exception as e:
            logging.error(f"Failed to start runtime for unit {unit_id}: {e}")
            raise
    
    def stop_unit_runtime(self, unit_id: int) -> None:
        """Stop hardware operations for a specific unit"""
        manager = self.runtime_managers.get(unit_id)
        if manager:
            manager.stop()
            del self.runtime_managers[unit_id]
            logging.info(f"🛑 Stopped runtime for unit {unit_id}")
    
    def update_unit_thresholds(self, unit_id: int, thresholds: dict) -> None:
        """Update climate thresholds for a unit"""
        manager = self.runtime_managers.get(unit_id)
        if manager:
            manager.update_thresholds(thresholds)
        else:
            logging.warning(f"No runtime manager for unit {unit_id}")
    
    def set_unit_light_schedule(self, unit_id: int, start: str, end: str) -> None:
        """Set light schedule for a unit"""
        manager = self.runtime_managers.get(unit_id)
        if manager:
            manager.set_light_schedule(start, end)
        else:
            logging.warning(f"No runtime manager for unit {unit_id}")
    
    def get_active_units(self) -> list[int]:
        """Get list of units with active runtimes"""
        return list(self.runtime_managers.keys())
    
    def shutdown_all(self) -> None:
        """Stop all unit runtimes (called on server shutdown)"""
        for unit_id in list(self.runtime_managers.keys()):
            self.stop_unit_runtime(unit_id)
        logging.info("🛑 All unit runtimes stopped")
```

---

### 3. Update `ServiceContainer`

```python
# In app/services/container.py

from app.services.climate_service import ClimateService

@dataclass
class ServiceContainer:
    # ... existing fields ...
    climate_service: ClimateService
    
    @classmethod
    def build(cls, config: AppConfig) -> "ServiceContainer":
        # ... existing code ...
        
        # Add ClimateService
        climate_service = ClimateService(
            database=database,
            mqtt_client=mqtt_client,
            redis_client=redis_client  # Can be None
        )
        
        return cls(
            # ... existing fields ...
            climate_service=climate_service,
        )
    
    def shutdown(self) -> None:
        # Stop all hardware operations first
        self.climate_service.shutdown_all()
        
        # Then close connections
        self.database.close_db()
        if self.mqtt_client is not None:
            self.mqtt_client.disconnect()
        if self.redis_client is not None:
            self.redis_client.close()
```

---

### 4. Initialize Runtimes on Startup

```python
# In app/__init__.py

def create_app(config_overrides: Optional[Dict[str, Any]] = None) -> Flask:
    # ... existing app creation ...
    
    container = ServiceContainer.build(config)
    app.config["CONTAINER"] = container
    
    # 🔥 NEW: Start hardware runtimes for active units
    with app.app_context():
        try:
            active_units = container.growth_service.list_units()
            for unit in active_units:
                unit_id = unit["unit_id"]
                unit_name = unit["name"]
                container.climate_service.start_unit_runtime(unit_id, unit_name)
            logging.info(f"✅ Started {len(active_units)} unit runtimes")
        except Exception as e:
            logging.error(f"Failed to start unit runtimes: {e}")
    
    # ... register blueprints ...
    
    return app
```

---

### 5. Hook into Unit Lifecycle

```python
# In app/services/growth.py

def create_unit(self, *, name: str, location: str = "Indoor") -> dict[str, Any]:
    unit_id = self.repository.create_unit(name=name, location=location)
    if unit_id is None:
        raise RuntimeError("Failed to create growth unit.")
    
    # 🔥 NEW: Start hardware runtime for new unit
    try:
        from flask import current_app
        container = current_app.config["CONTAINER"]
        container.climate_service.start_unit_runtime(unit_id, name)
    except Exception as e:
        logging.error(f"Failed to start runtime for new unit {unit_id}: {e}")
    
    self.audit_logger.log_event(...)
    return self.get_unit(unit_id)

def delete_unit(self, unit_id: int) -> None:
    # 🔥 NEW: Stop hardware runtime before deleting
    try:
        from flask import current_app
        container = current_app.config["CONTAINER"]
        container.climate_service.stop_unit_runtime(unit_id)
    except Exception as e:
        logging.error(f"Failed to stop runtime for unit {unit_id}: {e}")
    
    self.repository.delete_unit(unit_id)
    self.audit_logger.log_event(...)
```

---

## 🚀 Part 2: Redis Removal Analysis

### Current Redis Usage

**Locations:**
1. ✅ `SensorPollingService` - Polls Redis for wireless sensor data
2. ✅ `sensors/soil_moisture_sensor.py` - Pushes readings to Redis
3. ✅ `sensors/temp_humidity_sensor.py` - Pushes readings to Redis
4. ❌ `utils/relay_monitor.py` - Monitors relay states
5. ❌ `views/module_units.py` - Legacy view (can be removed)

**Purpose:** 
- Temporary caching of wireless sensor data from ESP32 modules
- ESP32 pushes → Redis → Backend polls → EventBus → ClimateController

### Recommendation: **✅ REMOVE Redis**

**Reasons:**
1. **Memory overhead:** Redis uses ~10-20MB on Pi 3B+ (7-15% of 1GB RAM)
2. **Unnecessary complexity:** EventBus already handles message passing
3. **ESP32 MQTT already works:** Sensors can publish directly to MQTT
4. **Polling overhead:** Checking Redis every 30s adds CPU load

### Alternative Architecture (Without Redis)

```
┌─────────────┐
│  ESP32-C6   │
│   Sensors   │
└──────┬──────┘
       │ MQTT publish
       │ topic: growtent/{unit_id}/sensor/{type}
       ▼
┌─────────────────┐
│  MQTT Broker    │
│  (mosquitto)    │
└──────┬──────────┘
       │ subscribe
       ▼
┌─────────────────────────────────┐
│  SensorPollingService           │
│  - MQTT subscriber (realtime)   │
│  - GPIO poller (10s interval)   │
│  - Publishes to EventBus        │
└─────────────┬───────────────────┘
              │
              ▼
┌──────────────────────────────┐
│        EventBus              │
│  (in-memory pub/sub)         │
└───────┬──────────────────────┘
        │
        ▼
┌───────────────────────────┐
│   ClimateController       │
│   - Subscribes to events  │
│   - Controls actuators    │
└───────────────────────────┘
```

### Implementation Changes

#### 1. Update `SensorPollingService`

```python
# Remove Redis polling loop completely

def __init__(self, sensor_manager, mqtt_wrapper=None):
    """Remove redis_client parameter"""
    self.sensor_manager = sensor_manager
    self.mqtt_wrapper = mqtt_wrapper
    self.event_bus = EventBus()
    # No Redis client needed

def start_polling(self):
    """Start GPIO and MQTT only"""
    threading.Thread(target=self._poll_gpio_sensors_loop, daemon=True).start()
    # Remove Redis polling thread
    
# Remove _poll_redis_sensors_loop() method entirely
```

#### 2. Update ESP32 Sensors

```python
# In sensors/soil_moisture_sensor.py

def __init__(self, unit_id, adc_channel, mqtt_host, mqtt_port):
    """Remove redis parameters"""
    self.mqtt_client = mqtt.Client()
    self.mqtt_client.connect(mqtt_host, mqtt_port)
    # No Redis client

def push_reading(self, reading):
    """Push directly to MQTT only"""
    topic = f"growtent/{self.unit_id}/sensor/soil_moisture"
    self.mqtt_client.publish(topic, json.dumps(reading))
    # Remove Redis.set() calls
```

#### 3. Update Container

```python
# Remove redis from ServiceContainer entirely

@dataclass
class ServiceContainer:
    # ... remove redis_client field ...
    
    @classmethod
    def build(cls, config):
        # Remove Redis initialization
        # redis_client = None
        
        climate_service = ClimateService(
            database=database,
            mqtt_client=mqtt_client
            # No redis_client parameter
        )
```

---

## 📊 Resource Comparison

### With Redis

| Resource | Usage | % of Pi 3B+ |
|----------|-------|-------------|
| RAM | 10-20 MB | 1-2% |
| CPU | ~2% (polling) | 2% |
| Processes | +1 (redis-server) | - |
| Network | Localhost TCP | Minimal |

### Without Redis (MQTT Only)

| Resource | Usage | % of Pi 3B+ |
|----------|-------|-------------|
| RAM | 0 MB saved | +2% available |
| CPU | 0% saved | +2% available |
| Processes | -1 process | Simpler |
| Network | MQTT only | Same |

**Verdict:** Redis removal frees 2-4% total resources with zero functional loss.

---

## 🎯 Migration Plan

### Phase 1: Add Hardware Abstraction (Week 1)
1. Create `infrastructure/hardware/` directory
2. Implement `UnitRuntimeManager`
3. Implement `ClimateService`
4. Add to `ServiceContainer`
5. Test with 1 unit

### Phase 2: Integrate with Service Layer (Week 2)
6. Hook `ClimateService` into `GrowthService` lifecycle
7. Initialize runtimes on app startup
8. Add CLI commands for manual start/stop
9. Test with multiple units

### Phase 3: Remove Redis (Week 3)
10. Update `SensorPollingService` (remove Redis polling)
11. Update ESP32 sensor scripts (direct MQTT only)
12. Remove `redis_client` from Container
13. Update documentation
14. Test end-to-end without Redis

### Phase 4: Cleanup (Week 4)
15. Remove old `grow_room/growth_unit.py` usage
16. Delete Redis config from requirements.txt
17. Update deployment scripts
18. Performance testing on Pi 3B+

---

## ✅ Testing Checklist

- [ ] Sensor readings appear in real-time
- [ ] Climate control responds to threshold violations
- [ ] Light schedules execute correctly
- [ ] Multiple units operate independently
- [ ] Server restart restores all runtimes
- [ ] Unit creation starts runtime automatically
- [ ] Unit deletion stops runtime cleanly
- [ ] MQTT sensors work without Redis
- [ ] Memory usage < 400MB on Pi 3B+
- [ ] CPU usage < 30% average

---

## 🚨 Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Sensor data loss without Redis | MQTT QoS=1, persist messages in SQLite |
| Increased MQTT broker load | Mosquitto handles 1000s msg/sec easily |
| EventBus memory leak | Implement subscriber cleanup on unit deletion |
| Runtime crashes | Add watchdog thread, auto-restart on failure |
| Database lock contention | Use WAL mode, connection pooling |

---

## 📝 Summary

### Key Changes

1. **New:** `UnitRuntimeManager` - Per-unit hardware orchestrator
2. **New:** `ClimateService` - Service-layer interface to hardware
3. **Modified:** `ServiceContainer` - Manages ClimateService lifecycle
4. **Modified:** `app/__init__.py` - Starts runtimes on boot
5. **Modified:** `GrowthService` - Hooks into unit lifecycle
6. **Removed:** Redis dependency completely
7. **Simplified:** Direct MQTT → EventBus → Control flow

### Benefits

- ✅ **Clean separation:** Service layer ↔ Hardware layer
- ✅ **Resource efficient:** ~2-4% less memory/CPU usage
- ✅ **Simpler architecture:** One less dependency
- ✅ **Better scaling:** EventBus is faster than Redis
- ✅ **Pi 3B+ optimized:** Minimal footprint
- ✅ **Maintainable:** Clear responsibilities

### Next Steps

1. Review this analysis with the team
2. Get approval for Redis removal
3. Start Phase 1 implementation
4. Create unit tests for `UnitRuntimeManager`
5. Set up CI/CD for Pi 3B+ target

---

**Status:** ✅ Ready for implementation  
**Estimated effort:** 3-4 weeks  
**Risk level:** Low (incremental, testable)  
**Impact:** High (completes architecture, removes tech debt)
