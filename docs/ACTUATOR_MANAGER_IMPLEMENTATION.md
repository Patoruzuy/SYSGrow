# ActuatorManager Implementation

Complete implementation of ActuatorManager following the SensorManager pattern.

## Overview

The ActuatorManager provides domain-driven actuator management with multi-protocol support, matching the architecture of SensorManager for consistency.

## Architecture

### Directory Structure

```
infrastructure/hardware/actuators/
├── __init__.py              # Module exports
├── domain.py                # Domain entities and enums
├── manager.py               # ActuatorManager class
├── factory.py               # ActuatorFactory
├── services.py              # Supporting services
└── adapters/                # Protocol adapters
    ├── __init__.py
    ├── mqtt_adapter.py
    ├── zigbee_adapter.py
    └── modbus_adapter.py
```

## Domain Model

### Enums

```python
class ActuatorType(Enum):
    WATER_PUMP = "water_pump"
    FAN = "fan"
    EXHAUST_FAN = "exhaust_fan"
    LIGHT = "light"
    GROW_LIGHT = "grow_light"
    HEATER = "heater"
    COOLER = "cooler"
    HUMIDIFIER = "humidifier"
    DEHUMIDIFIER = "dehumidifier"
    VALVE = "valve"
    SOLENOID = "solenoid"
    RELAY = "relay"
    MOTOR = "motor"
    UNKNOWN = "unknown"

class ActuatorState(Enum):
    OFF = "off"
    ON = "on"
    PARTIAL = "partial"  # For PWM/dimming
    ERROR = "error"
    UNKNOWN = "unknown"

class Protocol(Enum):
    GPIO = "gpio"
    MQTT = "mqtt"
    ZIGBEE = "zigbee"
    ZIGBEE2MQTT = "zigbee2mqtt"
    WIFI = "wifi"
    MODBUS = "modbus"
    HTTP = "http"

class ControlMode(Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    AUTOMATIC = "automatic"
    PWM = "pwm"
```

### Entities

**ActuatorEntity**: Rich domain entity with state management, control methods, and event emission

**ActuatorConfig**: Configuration dataclass for actuator setup

**ActuatorReading**: State reading with timestamp and metrics

**ActuatorCommand**: Command object for control operations

**Schedule**: Time-based automation configuration

## ActuatorManager Features

### Core Capabilities

1. **Multi-Protocol Support**
   - GPIO (Raspberry Pi direct control)
   - MQTT (message-based control)
   - WiFi/HTTP (network-based devices)
   - Zigbee2MQTT (Zigbee devices)
   - Modbus TCP (industrial devices)

2. **State Management**
   - Memory-first architecture
   - Real-time state tracking
   - Runtime statistics
   - Cycle counting

3. **Control Methods**
   - `turn_on()` - Turn actuator ON
   - `turn_off()` - Turn actuator OFF
   - `toggle()` - Toggle state
   - `set_level(value)` - PWM/dimming control (0-100)
   - `pulse(duration)` - Timed activation
   - `get_state()` - Current state query

4. **Scheduling**
   - Time-based schedules (start/end time)
   - Day-of-week filtering
   - Multiple schedules per actuator
   - Background execution

5. **Safety Features**
   - Interlocks (mutual exclusion)
   - Runtime limits
   - Cooldown periods
   - Power limits

6. **Event System**
   - `actuator_registered` - New actuator added
   - `actuator_unregistered` - Actuator removed
   - `actuator_command` - Control command executed

## Services

### SchedulingService

Automatic time-based control:

```python
# Set schedule
schedule = Schedule(
    actuator_id=1,
    start_time="08:00",
    end_time="20:00",
    days_of_week=[0, 1, 2, 3, 4],  # Mon-Fri
    command="on"
)
manager.set_schedule(1, schedule)
manager.start_scheduling()
```

### SafetyService

Safety interlocks and limits:

```python
# Add interlock (heater and cooler can't run together)
manager.add_interlock(heater_id, cooler_id)

# Set limits
manager.safety_service.set_max_runtime(pump_id, 3600)  # 1 hour max
manager.safety_service.set_cooldown(pump_id, 600)      # 10 min cooldown
manager.safety_service.set_max_total_power(5000)       # 5kW total limit
```

### StateTrackingService

Runtime statistics and history:

```python
# Get statistics
stats = manager.get_runtime_stats(actuator_id)
# Returns: {
#   'total_runtime_seconds': 12345,
#   'total_runtime_hours': 3.43,
#   'cycle_count': 42,
#   'uptime_24h_pct': 35.5,
#   'state_changes_24h': 84
# }

# Get history
history = manager.state_tracking_service.get_history(
    actuator_id,
    since=datetime.now() - timedelta(hours=24)
)
```

## Usage Examples

### Basic Registration

```python
from infrastructure.hardware.actuators import (
    ActuatorManager,
    ActuatorType,
    Protocol
)

# Initialize manager
manager = ActuatorManager(mqtt_client, event_bus)

# Register GPIO actuator
manager.register_actuator(
    actuator_id=1,
    name="Grow Light",
    actuator_type=ActuatorType.GROW_LIGHT,
    protocol=Protocol.GPIO,
    config={
        'gpio_pin': 17,
        'power_watts': 300
    }
)

# Register MQTT actuator
manager.register_actuator(
    actuator_id=2,
    name="Exhaust Fan",
    actuator_type=ActuatorType.EXHAUST_FAN,
    protocol=Protocol.MQTT,
    config={
        'mqtt_topic': 'devices/fan1/set',
        'power_watts': 50
    }
)
```

### Control Operations

```python
# Simple on/off
manager.turn_on(1)
manager.turn_off(1)
manager.toggle(1)

# PWM/Dimming
manager.set_level(1, 75)  # 75% brightness

# Timed pulse
manager.pulse(pump_id, 30)  # Run pump for 30 seconds

# Check state
state = manager.get_state(1)
print(f"State: {state.state.value}, Value: {state.value}%")
```

### Scheduling

```python
# Daily schedule (8 AM - 8 PM)
schedule = Schedule(
    actuator_id=1,
    start_time="08:00",
    end_time="20:00",
    enabled=True,
    days_of_week=[0, 1, 2, 3, 4, 5, 6],  # All days
    command="on"
)

manager.set_schedule(1, schedule)
manager.start_scheduling()

# Clear schedule
manager.clear_schedule(1)
```

### Safety Interlocks

```python
# Heater and cooler can't run together
manager.add_interlock(heater_id, cooler_id)

# Try to turn on cooler when heater is on
manager.turn_on(heater_id)  # ✓ Success
manager.turn_on(cooler_id)  # ✗ Blocked by interlock

# Remove interlock
manager.remove_interlock(heater_id, cooler_id)
```

### Querying Actuators

```python
# Get all actuators
all_actuators = manager.get_all_actuators()

# Get by type
lights = manager.get_actuators_by_type(ActuatorType.GROW_LIGHT)
fans = manager.get_actuators_by_type(ActuatorType.FAN)

# Get specific actuator
actuator = manager.get_actuator(1)
if actuator:
    print(f"Name: {actuator.name}")
    print(f"State: {actuator.current_state.value}")
    print(f"Runtime: {actuator.total_runtime_seconds}s")
```

## Integration with Existing Relay Infrastructure

The ActuatorManager integrates existing relay classes:

```python
# GPIO relays use existing GPIORelay
from infrastructure.hardware.relays.gpio_relay import GPIORelay

# WiFi relays use existing WiFiRelay
from infrastructure.hardware.relays.wifi_relay import WiFiRelay

# Wireless relays use existing WirelessRelay
from infrastructure.hardware.relays.wireless_relay import WirelessRelay
```

All relay classes already support:
- `turn_on()` / `turn_off()` methods
- EventBus integration
- Device name tracking

## Event System

The manager emits events for monitoring and integration:

```python
# Listen to events
event_bus.on('actuator_registered', lambda data: 
    print(f"New actuator: {data['name']} ({data['type']})")
)

event_bus.on('actuator_command', lambda data:
    print(f"Command {data['command']} sent to {data['actuator_id']}")
)

event_bus.on('actuator_unregistered', lambda data:
    print(f"Actuator {data['actuator_id']} removed")
)
```

## Memory-First Architecture

Like SensorManager, ActuatorManager prioritizes runtime state:

```python
# Runtime state is authoritative
actuator = manager.get_actuator(1)
state = actuator.get_state()  # Always current

# Database is for persistence
# device_service should check manager first:
actuator = manager.get_actuator(actuator_id)
if actuator:
    return actuator.to_dict()  # Runtime state
else:
    return db.query(...)  # Fallback to database
```

## Next Steps

### Integration with ServiceContainer

```python
# app/services/container.py
class ServiceContainer:
    def __init__(self):
        self.actuator_manager = ActuatorManager(
            mqtt_client=self.mqtt_client,
            event_bus=self.event_bus
        )
```

### Update device_service

```python
# app/services/device_service.py
def list_actuators(self, unit_id):
    # Check runtime manager first (memory-first)
    runtime_actuators = self.actuator_manager.get_all_actuators()
    
    # Filter by unit_id
    unit_actuators = [
        a for a in runtime_actuators 
        if a.unit_id == unit_id
    ]
    
    # If empty, fallback to database
    if not unit_actuators:
        unit_actuators = self.db.get_actuators(unit_id)
    
    return unit_actuators
```

### API Integration

The combined devices endpoint already supports device_type:

```python
# GET /api/devices/all/unit/<unit_id>
{
    "unit_id": 1,
    "sensors": [
        {"id": 1, "name": "Temperature", "device_type": "sensor", ...}
    ],
    "actuators": [
        {"id": 2, "name": "Grow Light", "device_type": "actuator", ...}
    ]
}
```

## Testing

```python
# Test basic control
manager = ActuatorManager()
actuator_id = manager.register_actuator(
    actuator_id=1,
    name="Test Light",
    actuator_type=ActuatorType.LIGHT,
    protocol=Protocol.GPIO,
    config={'gpio_pin': 17}
)

# Test on/off
result = manager.turn_on(1)
assert result.state == ActuatorState.ON

result = manager.turn_off(1)
assert result.state == ActuatorState.OFF

# Test PWM
result = manager.set_level(1, 50)
assert result.value == 50.0
assert result.state == ActuatorState.PARTIAL

# Test scheduling
schedule = Schedule(
    actuator_id=1,
    start_time="08:00",
    end_time="20:00"
)
manager.set_schedule(1, schedule)
assert manager.scheduling_service.get_schedules(1)

# Test interlocks
manager.register_actuator(2, "Test Fan", ActuatorType.FAN, Protocol.GPIO, {'gpio_pin': 18})
manager.add_interlock(1, 2)
manager.turn_on(1)
result = manager.turn_on(2)  # Should be blocked
assert result.state == ActuatorState.ERROR
```

## Summary

The ActuatorManager implementation provides:

✅ **Complete domain-driven architecture** matching SensorManager
✅ **Multi-protocol support** (GPIO, MQTT, WiFi, Zigbee, Modbus)
✅ **Rich control methods** (on/off/toggle/level/pulse)
✅ **Automatic scheduling** with time-based control
✅ **Safety features** (interlocks, limits, cooldowns)
✅ **State tracking** (runtime stats, cycle counts, history)
✅ **Event-driven** architecture with EventBus
✅ **Factory pattern** for protocol-agnostic creation
✅ **Service layer** for cross-cutting concerns
✅ **Integration** with existing relay infrastructure

The implementation is ready for integration with ServiceContainer and device_service.
