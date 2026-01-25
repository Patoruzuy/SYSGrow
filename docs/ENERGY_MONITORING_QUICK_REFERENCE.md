# Quick Reference: Energy Monitoring & Zigbee2MQTT

## API Endpoints Quick Reference

### Power Monitoring
```
GET  /api/devices/actuators/{id}/power          - Current power consumption
GET  /api/devices/actuators/{id}/energy         - Energy statistics (24h default)
GET  /api/devices/actuators/{id}/cost           - Cost estimates
GET  /api/devices/actuators/total-power         - Total system power
```

### Zigbee2MQTT Discovery
```
GET  /api/devices/zigbee2mqtt/devices           - All discovered devices
GET  /api/devices/zigbee2mqtt/devices/unit/{id} - Devices for specific unit
POST /api/devices/zigbee2mqtt/command           - Send command to device
```

## Python Usage Examples

### Access ActuatorManager
```python
# From growth service
runtime = growth_service.get_unit_runtime(unit_id)
actuator_manager = runtime.hardware_manager.actuator_manager
```

### Get Power Consumption
```python
# Current power for actuator
power = actuator_manager.get_power_consumption(actuator_id)
print(f"Current power: {power}W")

# Total power across all actuators
total = actuator_manager.get_total_power()
print(f"Total power: {total}W")
```

### Energy Statistics
```python
# Get 24-hour stats
stats = actuator_manager.get_energy_stats(actuator_id, hours=24)
print(f"Energy used: {stats['total_energy_kwh']}kWh")
print(f"Average power: {stats['average_power_watts']}W")
print(f"Cost: ${stats['cost_estimate']}")
```

### Cost Estimates
```python
# Get monthly cost
cost = actuator_manager.get_cost_estimate(actuator_id, period='monthly')
print(f"Monthly cost: ${cost['cost']}")
print(f"Monthly energy: {cost['energy_kwh']}kWh")
```

### Register Custom Power Profile
```python
if actuator_manager.energy_monitoring:
    actuator_manager.energy_monitoring.register_power_profile(
        actuator_type='custom_device',
        rated_power_watts=100.0,
        standby_power_watts=2.0,
        efficiency_factor=0.90
    )
```

### Get Discovered Devices
```python
# Get all discovered Zigbee2MQTT devices
devices = actuator_manager.get_discovered_devices()
for device in devices:
    print(f"{device['friendly_name']}: {device['model']}")
    print(f"  Power monitoring: {device['supports_power_monitoring']}")
```

### Send Command to Device
```python
# Turn on smart plug
success = actuator_manager.send_zigbee2mqtt_command(
    friendly_name='grow_light_plug',
    command={'state': 'ON'}
)
```

### Record Power Reading
```python
from infrastructure.hardware.actuators import EnergyReading

reading = EnergyReading(
    actuator_id=1,
    voltage=230.0,
    current=0.65,
    power=150.0,
    energy=3.5
)

actuator_manager.record_power_reading(reading)
```

## MQTT Topics

### Zigbee2MQTT Topics
```
zigbee2mqtt/bridge/devices          → Device list
zigbee2mqtt/bridge/info             → Bridge info
zigbee2mqtt/{device}                → Device data (power included)
zigbee2mqtt/{device}/set            → Send commands
```

### Subscribe Example
```python
mqtt_client.subscribe('zigbee2mqtt/smart_plug_1', callback)
```

### Publish Command
```python
import json
topic = 'zigbee2mqtt/smart_plug_1/set'
payload = json.dumps({'state': 'ON'})
mqtt_client.publish(topic, payload)
```

## Configuration

### UnitRuntimeManager Initialization
```python
actuator_manager = ActuatorManager(
    mqtt_client=mqtt_client,
    event_bus=event_bus,
    enable_energy_monitoring=True,      # Enable power tracking
    enable_zigbee2mqtt_discovery=True,  # Enable device discovery
    electricity_rate_kwh=0.12           # $0.12 per kWh
)
```

### Change Electricity Rate
```python
if actuator_manager.energy_monitoring:
    actuator_manager.energy_monitoring.electricity_rate = 0.15  # $0.15 per kWh
```

## Default Power Profiles

```python
from infrastructure.hardware.actuators import DEFAULT_POWER_PROFILES

# Available profiles:
DEFAULT_POWER_PROFILES['grow_light']    # 150W rated
DEFAULT_POWER_PROFILES['water_pump']    # 50W rated
DEFAULT_POWER_PROFILES['fan']           # 30W rated (with curve)
DEFAULT_POWER_PROFILES['heater']        # 1500W rated
DEFAULT_POWER_PROFILES['humidifier']    # 40W rated
```

## Common Patterns

### Check if Power Monitoring Enabled
```python
if actuator_manager.energy_monitoring:
    # Energy monitoring is enabled
    power = actuator_manager.get_power_consumption(actuator_id)
else:
    # Energy monitoring is disabled
    pass
```

### Check if Device Discovery Enabled
```python
if actuator_manager.zigbee2mqtt_discovery:
    # Discovery is enabled
    devices = actuator_manager.get_discovered_devices()
else:
    # Discovery is disabled
    pass
```

### Handle Discovery Callback
```python
def on_device_discovered(device):
    print(f"New device: {device.friendly_name}")
    if device.supports_power_monitoring:
        print("  Has power monitoring!")

actuator_manager.register_discovery_callback(on_device_discovered)
```

## Testing Commands

### cURL Examples

```bash
# Get power consumption
curl http://localhost:5000/api/devices/actuators/1/power

# Get energy stats (48 hours)
curl http://localhost:5000/api/devices/actuators/1/energy?hours=48

# Get yearly cost estimate
curl http://localhost:5000/api/devices/actuators/1/cost?period=yearly

# Get total system power
curl http://localhost:5000/api/devices/actuators/total-power

# List discovered devices
curl http://localhost:5000/api/devices/zigbee2mqtt/devices

# Send command to device
curl -X POST http://localhost:5000/api/devices/zigbee2mqtt/command \
  -H "Content-Type: application/json" \
  -d '{
    "unit_id": 1,
    "friendly_name": "smart_plug_1",
    "command": {"state": "ON"}
  }'
```

## Troubleshooting

### Enable Debug Logging
```python
import logging
logging.getLogger('infrastructure.hardware.actuators').setLevel(logging.DEBUG)
```

### Check MQTT Connection
```python
if actuator_manager.mqtt_client:
    print("MQTT client connected")
else:
    print("No MQTT client")
```

### Verify Power Data
```python
# Check latest reading
reading = actuator_manager.energy_monitoring.get_latest_reading(actuator_id)
if reading:
    print(f"Latest power: {reading.power}W at {reading.timestamp}")
else:
    print("No power readings yet")
```

### Check Discovery Status
```python
if actuator_manager.zigbee2mqtt_discovery:
    devices = actuator_manager.get_discovered_devices()
    print(f"Discovered {len(devices)} devices")
```
