# Workers Enhanced Architecture - Usage Guide

## Overview

The workers module has been refactored with modern architectural patterns:

- **Dependency Injection**: All dependencies injected via constructors
- **Type Safety**: ActuatorType enum instead of string names
- **Health Monitoring**: Comprehensive metrics and feedback validation
- **Configurability**: PID parameters and thresholds easily adjustable
- **Testability**: Loosely coupled components, easy to mock

---

## Quick Start Example

```python
from infrastructure.hardware.actuators.manager import ActuatorManager
from infrastructure.hardware.actuators.domain import ActuatorType, Protocol
from workers.control_logic import ControlLogic, ControlConfig
from workers.climate_controller import ClimateController
from app.utils.event_bus import EventBus

# 1. Initialize ActuatorManager
event_bus = EventBus()
actuator_manager = ActuatorManager(
    mqtt_client=mqtt_client,
    event_bus=event_bus,
    enable_energy_monitoring=True
)

# 2. Register actuators with type-safe enums
heater_id = actuator_manager.register_actuator(
    actuator_id=1,
    name="Grow Tent Heater",
    actuator_type=ActuatorType.HEATER,
    protocol=Protocol.GPIO,
    config={'gpio_pin': 17, 'power_watts': 150}
)

fan_id = actuator_manager.register_actuator(
    actuator_id=2,
    name="Exhaust Fan",
    actuator_type=ActuatorType.FAN,
    protocol=Protocol.GPIO,
    config={'gpio_pin': 18, 'power_watts': 50}
)

humidifier_id = actuator_manager.register_actuator(
    actuator_id=3,
    name="Ultrasonic Humidifier",
    actuator_type=ActuatorType.HUMIDIFIER,
    protocol=Protocol.MQTT,
    config={
        'mqtt_topic': 'zigbee2mqtt/humidifier_1',
        'power_watts': 30
    }
)

pump_id = actuator_manager.register_actuator(
    actuator_id=4,
    name="Water Pump",
    actuator_type=ActuatorType.WATER_PUMP,
    protocol=Protocol.GPIO,
    config={'gpio_pin': 19}
)

# 3. Configure control parameters
config = ControlConfig(
    # Temperature control
    temp_setpoint=24.0,
    temp_kp=1.0,
    temp_ki=0.1,
    temp_kd=0.05,
    temp_deadband=0.5,  # ±0.5°C tolerance
    
    # Humidity control
    humidity_setpoint=60.0,
    humidity_kp=1.0,
    humidity_ki=0.1,
    humidity_kd=0.05,
    humidity_deadband=2.0,  # ±2% tolerance
    
    # Soil moisture control
    moisture_setpoint=30.0,
    moisture_kp=1.0,
    moisture_ki=0.1,
    moisture_kd=0.05,
    moisture_deadband=3.0,  # ±3% tolerance
    
    # Safety settings
    min_cycle_time=60.0,  # 60 seconds minimum between actions
    feedback_timeout=5.0,
    max_consecutive_errors=3
)

# 4. Initialize ControlLogic with dependency injection
def control_feedback(data):
    """Callback for control actions"""
    print(f"Control action: {data['command']} actuator {data['actuator_id']}")
    print(f"Success: {data['success']}, Response time: {data['response_time']:.2f}s")

control_logic = ControlLogic(
    actuator_manager=actuator_manager,
    config=config,
    database_manager=db_manager,
    use_ml_control=False,  # Use PID control
    feedback_callback=control_feedback
)

# 5. Register actuators with ControlLogic using type-safe enums
control_logic.register_actuator(ActuatorType.HEATER, heater_id)
control_logic.register_actuator(ActuatorType.FAN, fan_id)
control_logic.register_actuator(ActuatorType.HUMIDIFIER, humidifier_id)
control_logic.register_actuator(ActuatorType.WATER_PUMP, pump_id)

# 6. Initialize ClimateController with dependency injection
climate_controller = ClimateController(
    control_logic=control_logic,
    polling_service=sensor_polling_service,
    repo_analytics=analytics_repo,
    event_bus=event_bus
)

# 7. Start the system
climate_controller.start()
print("Climate control system started!")
```

---

## Advanced Configuration

### Dynamic PID Tuning

```python
# Update PID parameters at runtime (for tuning)
control_logic.update_pid_parameters(
    controller_name='temperature',
    kp=1.2,
    ki=0.15,
    kd=0.08
)

# Update setpoints
control_logic.update_thresholds({
    'temperature': 26.0,  # Change to 26°C
    'humidity': 65.0,     # Change to 65%
    'soil_moisture': 35.0 # Change to 35%
})
```

### Health Monitoring

```python
# Get comprehensive health status
health = climate_controller.get_health_status()
print(f"Started: {health['started']}")
print(f"Sensor updates: {health['sensor_updates']}")
print(f"Control actions: {health['control_actions']}")
print(f"Stale sensors: {health['stale_sensors']}")

# Get control metrics
metrics = control_logic.get_metrics()
for strategy, data in metrics.items():
    print(f"{strategy}:")
    print(f"  Success rate: {data['success_rate']:.1f}%")
    print(f"  Avg response: {data['average_response_time']:.3f}s")
    print(f"  Total actions: {data['total_actions']}")
```

### Enable/Disable Control

```python
# Temporarily disable control (for manual override)
control_logic.disable()

# Re-enable
control_logic.enable()

# Reset metrics
control_logic.reset_metrics()
```

---

## Key Improvements

### 1. Type-Safe Actuator Mapping

**Before (string-based):**
```python
control_logic.register_actuator("Heater", 1)  # Prone to typos
```

**After (enum-based):**
```python
control_logic.register_actuator(ActuatorType.HEATER, 1)  # Type-safe
```

### 2. Configurable Parameters

**Before (hardcoded):**
```python
self.temp_controller = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=24.0)
```

**After (configurable):**
```python
config = ControlConfig(
    temp_setpoint=24.0,
    temp_kp=1.0,
    temp_ki=0.1,
    temp_kd=0.05,
    temp_deadband=0.5
)
control_logic = ControlLogic(actuator_manager, config=config)
```

### 3. Feedback Validation

**Before (fire and forget):**
```python
self.actuator_manager.turn_on(heater_id)  # No validation
```

**After (with validation):**
```python
success = self._execute_actuator_command(heater_id, 'on', ControlStrategy.HEATING)
# Tracks success, response time, consecutive errors
# Automatically disables control after too many errors
```

### 4. Deadband Logic

**Before (always reacts):**
```python
if control_signal > 0:
    turn_on_heater()  # Reacts to tiny changes
```

**After (with deadband):**
```python
error = abs(temperature - setpoint)
if error < deadband:
    return  # Ignore small deviations, prevent oscillation
```

### 5. Cycle Time Enforcement

**Before (can rapid-cycle):**
```python
turn_on(actuator)
turn_off(actuator)  # Immediate, can damage relay
```

**After (with minimum cycle time):**
```python
if not self._can_act(actuator_id):
    return  # Enforces 60-second minimum between actions
```

### 6. Health Monitoring

**Before (no metrics):**
```python
# No visibility into control loop performance
```

**After (comprehensive metrics):**
```python
metrics = control_logic.get_metrics()
# Shows success rate, response time, error counts per strategy
# Automatically detects stale sensors
```

---

## Testing Example

```python
import unittest
from unittest.mock import Mock, MagicMock

class TestControlLogic(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures with mocks"""
        self.mock_actuator_manager = Mock()
        self.mock_actuator_manager.turn_on = Mock(return_value=Mock(
            state=ActuatorState.ON,
            error_message=None
        ))
        
        self.config = ControlConfig(
            temp_setpoint=24.0,
            temp_deadband=0.5,
            min_cycle_time=1.0  # Short for testing
        )
        
        self.control_logic = ControlLogic(
            actuator_manager=self.mock_actuator_manager,
            config=self.config
        )
        
        # Register mock actuator
        self.control_logic.register_actuator(ActuatorType.HEATER, 1)
    
    def test_temperature_control_with_deadband(self):
        """Test deadband prevents unnecessary actions"""
        # Temperature within deadband
        result = self.control_logic.control_temperature({
            'temperature': 24.3,  # Within ±0.5°C
            'unit_id': 1
        })
        
        # Should return success but not call actuator
        self.assertTrue(result)
        self.mock_actuator_manager.turn_on.assert_not_called()
    
    def test_temperature_control_outside_deadband(self):
        """Test control activates outside deadband"""
        # Temperature outside deadband
        result = self.control_logic.control_temperature({
            'temperature': 22.0,  # More than 0.5°C below setpoint
            'unit_id': 1
        })
        
        # Should activate heater
        self.assertTrue(result)
        self.mock_actuator_manager.turn_on.assert_called_once_with(1)
    
    def test_metrics_tracking(self):
        """Test metrics are tracked correctly"""
        self.control_logic.control_temperature({
            'temperature': 20.0,
            'unit_id': 1
        })
        
        metrics = self.control_logic.get_metrics()
        heating_metrics = metrics['heating']
        
        self.assertEqual(heating_metrics['total_actions'], 1)
        self.assertEqual(heating_metrics['successful_actions'], 1)
        self.assertGreater(heating_metrics['success_rate'], 0)

if __name__ == '__main__':
    unittest.main()
```

---

## Migration Guide

### From Old API to New API

**Step 1: Update imports**
```python
# Old
from workers.control_logic import ControlLogic

# New
from workers.control_logic import ControlLogic, ControlConfig
from infrastructure.hardware.actuators.domain import ActuatorType
```

**Step 2: Create ControlConfig**
```python
# New - define configuration
config = ControlConfig(
    temp_setpoint=24.0,
    humidity_setpoint=60.0,
    moisture_setpoint=30.0
)
```

**Step 3: Update ControlLogic initialization**
```python
# Old
control_logic = ControlLogic(actuator_manager)

# New
control_logic = ControlLogic(actuator_manager, config=config)
```

**Step 4: Update actuator registration**
```python
# Old
control_logic.register_actuator("Heater", heater_id)

# New
control_logic.register_actuator(ActuatorType.HEATER, heater_id)
```

**Step 5: Update ClimateController initialization**
```python
# Old
climate_controller = ClimateController(
    actuator_manager,
    polling_service,
    repo_analytics
)

# New
climate_controller = ClimateController(
    control_logic,      # Inject ControlLogic
    polling_service,
    repo_analytics
)
```

---

## Best Practices

1. **Always use ActuatorType enum** - Never use string names
2. **Configure deadbands appropriately** - Prevent oscillation
3. **Monitor metrics regularly** - Watch for declining success rates
4. **Test with mocks** - Use dependency injection for easy testing
5. **Set min_cycle_time wisely** - Protect relays from rapid switching
6. **Handle feedback callbacks** - Log or alert on control failures
7. **Tune PID parameters** - Use control metrics to optimize
8. **Check health status** - Detect stale sensors and control issues

---

## Troubleshooting

### Control not working?

1. Check if control logic is enabled:
   ```python
   status = control_logic.get_status()
   print(status['enabled'])  # Should be True
   ```

2. Check actuator registration:
   ```python
   print(status['registered_actuators'])
   # Should show all your actuators
   ```

3. Check metrics for errors:
   ```python
   metrics = control_logic.get_metrics()
   for strategy, data in metrics.items():
       if data['failed_actions'] > 0:
           print(f"{strategy} has {data['failed_actions']} failures")
   ```

### Rapid cycling?

Increase `min_cycle_time` in config:
```python
config.min_cycle_time = 120.0  # 2 minutes
```

### Oscillating temperature?

Increase deadband:
```python
config.temp_deadband = 1.0  # ±1°C tolerance
```

Or tune PID parameters:
```python
control_logic.update_pid_parameters(
    'temperature',
    kp=0.8,   # Reduce proportional gain
    ki=0.05,  # Reduce integral gain
    kd=0.1    # Increase derivative gain
)
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    EventBus (Pub/Sub)                        │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ sensor_update events
                              │
┌─────────────────────────────┴───────────────────────────────┐
│              ClimateController                               │
│  - Listens to sensor events                                 │
│  - Delegates control to ControlLogic                        │
│  - Logs to database                                         │
│  - Monitors sensor health                                   │
└─────────────────────────────┬───────────────────────────────┘
                              │ delegates control
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                 ControlLogic                                 │
│  - PID/ML controllers                                       │
│  - Deadband logic                                           │
│  - Cycle time enforcement                                   │
│  - Feedback validation                                      │
│  - Metrics tracking                                         │
└─────────────────────────────┬───────────────────────────────┘
                              │ commands
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              ActuatorManager                                 │
│  - Turn on/off actuators                                    │
│  - Hardware abstraction                                     │
│  - Multi-protocol support                                   │
│  - Energy monitoring                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## Summary of Enhancements

✅ **Type Safety**: ActuatorType enum instead of strings  
✅ **Dependency Injection**: Loosely coupled, testable components  
✅ **Configurable**: All parameters adjustable via ControlConfig  
✅ **Health Monitoring**: Comprehensive metrics and stale sensor detection  
✅ **Feedback Validation**: Verify actuator commands succeeded  
✅ **Deadband Logic**: Prevent oscillation and unnecessary actions  
✅ **Cycle Time Enforcement**: Protect hardware from rapid switching  
✅ **Error Recovery**: Automatic disable after consecutive failures  
✅ **Performance Tracking**: Success rate, response time per strategy  
✅ **Better Testing**: Easy to mock dependencies and test logic  

The enhanced architecture provides a robust, maintainable, and scalable foundation for climate control! 🌱
