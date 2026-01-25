# Energy Monitoring Migration Guide

## Overview

The energy monitoring system has been migrated from the standalone `ZigBeeEnergyMonitor` class to the integrated `EnergyMonitoringService` within `ActuatorManager`.

## What Changed

### Old System (DEPRECATED)
- **Location**: `infrastructure/hardware/devices/zigbee_energy_monitor.py`
- **Class**: `ZigBeeEnergyMonitor`
- **Approach**: Standalone component with manual scheduling
- **Status**: ❌ REMOVED

### New System (CURRENT)
- **Location**: `infrastructure/hardware/actuators/services/energy_monitoring.py`
- **Class**: `EnergyMonitoringService`
- **Approach**: Integrated into `ActuatorManager`
- **Status**: ✅ ACTIVE

## Benefits of New System

1. **Integrated Architecture**: Energy monitoring is now part of the actuator lifecycle
2. **Real-time Updates**: Automatic monitoring via Zigbee2MQTT callbacks
3. **Better Type Safety**: Modern dataclasses (EnergyReading, PowerProfile, ConsumptionStats)
4. **Unified Interface**: Access via `actuator_manager.energy_monitoring` or `actuator_manager.get_energy_stats()`
5. **Power Estimation**: Smart estimation for non-monitored devices using power profiles
6. **Cost Calculations**: Built-in cost tracking and efficiency metrics

## Migration Steps Completed

### 1. ✅ Updated `task_scheduler.py`
- Removed `ZigBeeEnergyMonitor` import
- Removed energy monitoring scheduling methods:
  - `schedule_energy_monitoring()`
  - `_monitor_energy_consumption()`
- Updated docstring to reference new system
- MLDataCollector now accepts `None` for energy_monitor parameter

### 2. ✅ Updated `ml_trainer.py`
- Added comments explaining legacy database tables
- Made `MLDataCollector` energy_monitor parameter optional
- Updated `collect_comprehensive_training_sample()` to handle `None` energy_monitor
- Database tables `ZigBeeEnergyMonitors` and `EnergyConsumption` retained for historical data

### 3. ✅ Deprecated Demo Script
- `scripts/demo_enhanced_features.py` marked as deprecated
- Added exit handler to prevent execution
- Clear documentation pointing to modern alternatives

### 4. ✅ Removed Old Implementation
- Deleted `infrastructure/hardware/devices/zigbee_energy_monitor.py`
- No active code references old ZigBeeEnergyMonitor class

## How to Use New Energy Monitoring

### Basic Usage

```python
from infrastructure.hardware.actuators.actuator_manager import ActuatorManager

# Initialize ActuatorManager (energy monitoring starts automatically)
actuator_manager = ActuatorManager(
    database_handler=db_handler,
    mqtt_client=mqtt_client,
    event_bus=event_bus
)

# Get energy statistics
stats = actuator_manager.get_energy_stats()
print(f"Total consumption: {stats.total_energy_kwh:.2f} kWh")
print(f"Current power: {stats.average_power_w:.1f} W")
print(f"Total cost: ${stats.total_cost:.2f}")

# Get statistics for specific actuator
actuator_stats = actuator_manager.get_energy_stats(actuator_id=123)

# Get real-time power reading
reading = actuator_manager.energy_monitoring.get_current_power(actuator_id=123)
if reading:
    print(f"Power: {reading.power_w:.1f} W")
    print(f"Voltage: {reading.voltage_v:.1f} V")
```

### Power Monitoring with Callbacks

```python
def on_high_power(actuator_id: int, power_w: float):
    print(f"⚠️ High power alert: Actuator {actuator_id} at {power_w:.1f}W")

# Register threshold callback
actuator_manager.energy_monitoring.register_power_threshold_callback(
    actuator_id=123,
    threshold_w=500.0,
    callback=on_high_power
)
```

### Accessing Historical Data

```python
# Legacy database tables are still available
with database_handler.connection() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT timestamp, energy_consumed, power_w 
        FROM EnergyConsumption 
        WHERE monitor_id = ?
        ORDER BY timestamp DESC
        LIMIT 100
    """, (monitor_id,))
    
    historical_data = cursor.fetchall()
```

## Database Schema

### Legacy Tables (READ-ONLY)
These tables contain historical data and should NOT be modified:

```sql
-- Legacy energy monitor registrations
CREATE TABLE ZigBeeEnergyMonitors (
    monitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    zigbee_address TEXT NOT NULL UNIQUE,
    unit_id INTEGER,
    device_name TEXT,
    device_type TEXT,
    registered_date TEXT DEFAULT CURRENT_TIMESTAMP
);

-- Historical energy consumption data
CREATE TABLE EnergyConsumption (
    consumption_id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitor_id INTEGER NOT NULL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    energy_consumed REAL,
    power_w REAL,
    voltage_v REAL,
    current_a REAL,
    FOREIGN KEY (monitor_id) REFERENCES ZigBeeEnergyMonitors(monitor_id)
);
```

### New System (ACTIVE)
Energy data is now tracked in:
- Real-time: In-memory via `EnergyMonitoringService`
- Persistence: Future implementation will use new tables

## Architecture Comparison

### Old Architecture
```
TaskScheduler
    └── schedule_energy_monitoring()
            └── ZigBeeEnergyMonitor
                    ├── read_energy_data()
                    └── estimate_device_consumption()
```

### New Architecture
```
ActuatorManager
    ├── actuators: Dict[int, Actuator]
    └── energy_monitoring: EnergyMonitoringService
            ├── Real-time MQTT callbacks
            ├── Power profile estimation
            ├── Statistics aggregation
            └── Cost calculations
```

## Related Documentation

- **Modern Usage Patterns**: `workers/USAGE_EXAMPLE.md`
- **Energy Monitoring Implementation**: `infrastructure/hardware/actuators/services/energy_monitoring.py`
- **ActuatorManager API**: `infrastructure/hardware/actuators/actuator_manager.py`
- **Architecture Overview**: `ENUMS_SCHEMAS_SUMMARY.md`

## Migration Checklist

- [x] Remove old ZigBeeEnergyMonitor class
- [x] Update task_scheduler.py
- [x] Update ml_trainer.py
- [x] Deprecate demo scripts
- [x] Document migration process
- [x] Preserve historical database tables
- [ ] Update API endpoints (if any use old energy monitor)
- [ ] Update frontend to use new energy stats endpoints
- [ ] Test with actual Zigbee energy monitoring devices

## Need Help?

If you encounter issues during migration:

1. Check `workers/USAGE_EXAMPLE.md` for modern patterns
2. Review `infrastructure/hardware/actuators/services/energy_monitoring.py` for API reference
3. Check logs for energy monitoring initialization
4. Verify Zigbee2MQTT is publishing energy data on correct topics

---

**Last Updated**: 2024
**Status**: ✅ Migration Complete
