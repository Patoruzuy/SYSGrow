# ML Energy Monitoring Integration

## Overview
Updated ML training data collection to use the modern `ActuatorManager.energy_monitoring` service instead of the deprecated `ZigBeeEnergyMonitor`.

## Architecture Changes

### Before (Deprecated)
```python
MLDataCollector(
    data_access,
    energy_monitor,  # Deprecated ZigBeeEnergyMonitor
    plant_health_monitor,
    environment_collector
)
```

### After (Modern)
```python
MLDataCollector(
    data_access,
    actuator_manager,  # ActuatorManager with energy_monitoring
    plant_health_monitor,
    environment_collector
)
```

## Energy Data Flow

```
UnitRuntimeManager
  └── ActuatorManager (with energy_monitoring: EnergyMonitoringService)
      └── TaskScheduler
          └── MLDataCollector
              └── Uses actuator_manager.get_current_power(actuator_id)
```

## Key Features

### 1. Real-Time Power Monitoring
```python
def get_power(device_name: str) -> float:
    """Get current power consumption for a device"""
    actuator = actuator_manager.get_actuator_by_name(actuator_name)
    power = actuator_manager.get_current_power(actuator.actuator_id)
    return power if power is not None else 0.0
```

**Data Sources:**
- **Real readings** from Zigbee2MQTT smart switches (if available)
- **Estimated values** from power profiles (fallback)

### 2. Device State Tracking
```python
def _is_device_on(device_name: str) -> int:
    """Check if a device is currently ON (returns 1 or 0)"""
    actuator = actuator_manager.get_actuator_by_name(actuator_name)
    return 1 if actuator.current_state in [ActuatorState.ON, ActuatorState.ACTIVE] else 0
```

**Benefits:**
- Accurate device state for ML training
- Real-time state from ActuatorManager's memory

### 3. Device Mapping
Maps ML training device names to actual actuator names:

| ML Device Name | Actuator Name |
|---------------|--------------|
| `lights` | `Light` |
| `fan` | `Fan` |
| `extractor` | `Extractor` |
| `heater` | `Heater` |
| `humidifier` | `Humidifier` |
| `water_pump` | `Water Pump` |

## Energy Data in Training Samples

### Collected Metrics
```python
sample_data = {
    # Individual device power (watts)
    'lights_power': get_power('lights'),
    'fan_power': get_power('fan'),
    'extractor_power': get_power('extractor'),
    'heater_power': get_power('heater'),
    'humidifier_power': get_power('humidifier'),
    'water_pump_power': get_power('water_pump'),
    
    # Total power consumption
    'total_power_consumption': sum([all device powers]),
    
    # Device states (binary)
    'lights_on': _is_device_on('lights'),
    'fan_on': _is_device_on('fan'),
    'extractor_on': _is_device_on('extractor'),
    'heater_on': _is_device_on('heater'),
    'humidifier_on': _is_device_on('humidifier'),
    'water_pump_on': _is_device_on('water_pump'),
}
```

## Implementation Details

### Updated Files

1. **ai/ml_trainer.py**
   - `MLDataCollector.__init__()` - Now accepts `actuator_manager`
   - `collect_comprehensive_training_sample()` - Uses `ActuatorManager` API
   - `_is_device_on()` - Helper method for device state checking

2. **workers/task_scheduler.py**
   - `__init__()` - Now accepts `actuator_manager` parameter
   - `_init_features()` - Passes `actuator_manager` to `MLDataCollector`

3. **app/models/unit_runtime_manager.py**
   - `__init__()` - Passes `self.actuator_manager` to `TaskScheduler`

### Error Handling
```python
if not self.actuator_manager or not self.actuator_manager.energy_monitoring:
    return 0.0  # Fallback to zero if energy monitoring unavailable
```

## Data Accuracy

### Smart Switch Data (Highest Accuracy)
When Zigbee2MQTT smart switches are used:
- ✅ Real voltage readings
- ✅ Real current readings
- ✅ Real power consumption
- ✅ Power factor
- ✅ Energy accumulation (kWh)

### Estimated Data (Good Accuracy)
When using power profiles:
- ✅ Based on actuator type
- ✅ Considers device state
- ✅ Uses calibrated power curves
- ✅ Accounts for efficiency factors

### Power Profiles Used
From `DEFAULT_POWER_PROFILES`:
- **Grow Light**: 150W rated, 2W standby, 90% efficient
- **Fan**: 30W rated with power curve (0→0.5W, 100%→30W)
- **Water Pump**: 50W rated, 1W standby, 85% efficient
- **Heater**: 1500W rated, 5W standby, 98% efficient
- **Humidifier**: 40W rated, 1W standby, 88% efficient

## Benefits for ML Training

### 1. Real-Time Data
- ✅ Captures actual power consumption at training sample time
- ✅ No lag or synchronization issues
- ✅ Reflects current actuator states

### 2. Accurate Correlations
- ✅ ML can learn true power usage patterns
- ✅ Better climate control predictions
- ✅ Improved energy efficiency recommendations

### 3. Device State Context
- ✅ Knows which devices were ON/OFF during sample
- ✅ Can correlate device states with environmental outcomes
- ✅ Helps predict optimal device combinations

### 4. Cost Awareness
- ✅ ML can optimize for energy cost
- ✅ Can suggest cost-saving strategies
- ✅ Balance performance vs. cost

## Storage

### In-Memory (EnergyMonitoringService)
- Latest readings per actuator
- Last 1000 readings per actuator (configurable)
- Fast access for training data collection

### Database (MLTrainingData table)
- Training samples with energy data
- Historical correlation with environmental conditions
- Used for ML model training

## Migration Notes

### Removed
- ❌ `ZigBeeEnergyMonitor` dependency
- ❌ Manual energy estimation logic
- ❌ Separate energy monitoring initialization

### Added
- ✅ `ActuatorManager` integration
- ✅ Real-time power and state queries
- ✅ Automatic device mapping
- ✅ Cleaner error handling

## Testing

### Verify Energy Data Collection
```python
# In MLDataCollector
collector = MLDataCollector(
    data_access=ml_data,
    actuator_manager=actuator_manager,
    plant_health_monitor=monitor,
    environment_collector=collector
)

# Collect sample
success = collector.collect_comprehensive_training_sample(unit_id=1)

# Check database
# Should see power values for all devices in MLTrainingData
```

### Check Power Values
```python
# Verify actuator manager has energy monitoring
assert actuator_manager.energy_monitoring is not None

# Check power reading
power = actuator_manager.get_current_power(actuator_id=1)
assert power >= 0.0

# Check device state
actuator = actuator_manager.get_actuator_by_name("Light")
assert actuator.current_state in [ActuatorState.ON, ActuatorState.OFF]
```

## Performance

### Before
- ⚠️ Separate database queries for energy data
- ⚠️ Potential synchronization lag
- ⚠️ Additional database connections

### After
- ✅ Direct memory access via ActuatorManager
- ✅ Instant power readings
- ✅ No additional database overhead
- ✅ Real-time device states

## Future Enhancements

### Planned
1. **Energy Analytics Integration** - Export energy data to analytics repository
2. **Power Budget Optimization** - ML suggests power-efficient strategies
3. **Cost Prediction** - Predict electricity costs based on planned operations
4. **Device Efficiency Tracking** - Monitor device efficiency degradation over time

### Optional
- Historical energy data aggregation
- Power usage heatmaps
- Cost vs. performance analysis
- Device recommendation system

## Related Documentation

- `docs/ENERGY_MONITORING_MIGRATION.md` - Legacy migration guide
- `docs/REPOSITORY_PATTERN_MIGRATION.md` - Architecture refactoring
- `infrastructure/hardware/actuators/services/energy_monitoring.py` - EnergyMonitoringService API
- `infrastructure/hardware/actuators/manager.py` - ActuatorManager with energy monitoring

---

**Status**: ✅ **COMPLETED**  
**Integration Date**: December 2024  
**Impact**: ML training now uses real-time energy monitoring from ActuatorManager  
**Breaking Changes**: None (backward compatible through ActuatorManager parameter)
