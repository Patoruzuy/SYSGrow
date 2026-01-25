# Sensor Management Quick Reference Guide

## Enterprise Architecture Overview

```
Application Layer → SensorManager → Adapters → Drivers → Hardware
                         ↓
                    EventBus (Publishing)
                         ↓
              Processors & Services
           (Calibration, Anomaly Detection)
```

---

## Quick Start

### 1. Initialize SensorManager

```python
from infrastructure.hardware.sensors import SensorManager, SensorType, Protocol

# Create manager instance
manager = SensorManager()
```

### 2. Register Sensors

#### GPIO/I2C Sensors (ENS160+AHT21)
```python
sensor = manager.register_sensor(
    sensor_id=1,
    name="Air Quality Sensor",
    sensor_type=SensorType.ENVIRONMENT,
    protocol=Protocol.I2C,
    unit_id="1",
    model="ENS160AHT21"
)
```

#### GPIO Sensors (DHT11)
```python
sensor = manager.register_sensor(
    sensor_id=2,
    name="DHT11 Temp/Humidity",
    sensor_type=SensorType.TEMPERATURE,
    protocol=Protocol.GPIO,
    unit_id="1",
    model="DHT11",
    gpio_pin=4  # BCM numbering
)
```

#### ADC Sensors (Soil Moisture)
```python
sensor = manager.register_sensor(
    sensor_id=3,
    name="Soil Moisture",
    sensor_type=SensorType.SOIL_MOISTURE,
    protocol=Protocol.GPIO,  # Uses GPIO adapter with ADC
    unit_id="1",
    model="Soil-Moisture",
    adc_channel=0  # ADS1115 channel
)
```

#### Light Sensors (TSL2591)
```python
sensor = manager.register_sensor(
    sensor_id=4,
    name="Light Sensor",
    sensor_type=SensorType.LIGHT,
    protocol=Protocol.I2C,
    unit_id="1",
    model="TSL2591"
)
```

#### Gas Sensors (MQ2)
```python
# Digital mode
sensor = manager.register_sensor(
    sensor_id=5,
    name="Smoke Detector",
    sensor_type=SensorType.GAS,
    protocol=Protocol.GPIO,
    unit_id="1",
    model="MQ2",
    gpio_pin=17,
    is_digital=True
)

# Analog mode (via ADC)
sensor = manager.register_sensor(
    sensor_id=6,
    name="Gas Concentration",
    sensor_type=SensorType.GAS,
    protocol=Protocol.GPIO,
    unit_id="1",
    model="MQ2",
    is_digital=False,
    adc_channel=1
)
```

#### Weather Sensors (BME280)
```python
sensor = manager.register_sensor(
    sensor_id=7,
    name="Weather Station",
    sensor_type=SensorType.WEATHER,
    protocol=Protocol.I2C,
    unit_id="1",
    model="BME280"
)
```

### 3. Read Sensor Data

```python
# Read single sensor
reading = manager.read_sensor(sensor_id=1)

# Access reading data
print(f"Sensor: {reading.sensor_id}")
print(f"Value: {reading.value}")
print(f"Status: {reading.status}")
print(f"Timestamp: {reading.timestamp}")
print(f"Metadata: {reading.metadata}")

# Convert to dict
data = reading.to_dict()
```

### 4. Bulk Operations

```python
# Read all sensors
all_readings = manager.read_all_sensors()
for reading in all_readings:
    print(f"{reading.sensor_id}: {reading.value}")

# Get sensors by type
env_sensors = manager.get_sensors_by_type(SensorType.ENVIRONMENT)
```

---

## Automatic Features (Built-in)

### ✅ Calibration (Automatic)
Readings are automatically calibrated based on sensor configuration:
- Linear calibration
- Polynomial calibration (2nd/3rd order)
- Lookup table calibration
- Custom calibration functions

### ✅ Anomaly Detection (Automatic)
Anomalies are detected automatically:
- Z-score (statistical outliers)
- Moving average deviation
- Rate of change
- Range validation
- Time-based patterns
- Inter-sensor consistency

Anomalies are flagged in `reading.metadata['anomaly_detected']`.

### ✅ Health Monitoring (Automatic)
Health is tracked per sensor:
- Consecutive failures
- Last successful read
- Error rates
- Health level (EXCELLENT, GOOD, FAIR, POOR, CRITICAL, FAILED)

### ✅ EventBus Publishing (Automatic)
Events are automatically published:
- `sensor_reading`: New reading available
- `sensor_error`: Read failure
- `sensor_registered`: New sensor registered

---

## Advanced Usage

### Calibration Configuration

```python
from infrastructure.hardware.sensors import CalibrationData, CalibrationType

calibration = CalibrationData(
    calibration_type=CalibrationType.LINEAR,
    parameters={
        'slope': 1.05,
        'offset': -0.5
    },
    last_calibrated=datetime.utcnow()
)

# Apply during registration
sensor = manager.register_sensor(
    sensor_id=1,
    # ... other params
    calibration=calibration
)
```

### Retrieve Health Status

```python
sensor = manager.get_sensor(sensor_id=1)
health = sensor.health_status

print(f"Health Level: {health.level}")
print(f"Consecutive Failures: {health.consecutive_failures}")
print(f"Last Success: {health.last_successful_read}")
print(f"Is Available: {health.is_available()}")
```

### Subscribe to EventBus

```python
from app.utils.event_bus import EventBus

event_bus = EventBus.get_instance()

def handle_reading(event_data):
    print(f"New reading: {event_data}")

event_bus.subscribe('sensor_reading', handle_reading)
```

---

## Supported Sensor Models

| Model | Type | Protocol | Features |
|-------|------|----------|----------|
| ENS160AHT21 | Environment | I2C | eCO2, TVOC, Temp, Humidity |
| TSL2591 | Light | I2C | Lux, Full Spectrum, IR, Visible |
| Soil-Moisture | Soil | ADC | Moisture %, Voltage, Raw ADC |
| DHT11 | Temperature | GPIO | Temperature, Humidity |
| MQ2 | Gas | GPIO/ADC | Smoke, Gas detection |
| BME280 | Weather | I2C | Temp, Humidity, Pressure, Altitude |

---

## Protocol Types

```python
from infrastructure.hardware.sensors import Protocol

Protocol.GPIO          # Digital GPIO pins
Protocol.I2C           # I2C bus communication
Protocol.MQTT          # MQTT network sensors
Protocol.ZIGBEE        # Zigbee direct communication
Protocol.ZIGBEE2MQTT   # Zigbee via MQTT bridge
Protocol.MODBUS        # Modbus RTU/TCP
```

---

## Sensor Types

```python
from infrastructure.hardware.sensors import SensorType

SensorType.TEMPERATURE    # Temperature sensors
SensorType.HUMIDITY       # Humidity sensors
SensorType.PRESSURE       # Pressure sensors
SensorType.LIGHT          # Light/illumination
SensorType.SOIL_MOISTURE  # Soil moisture
SensorType.CO2            # CO2 concentration
SensorType.GAS            # Gas detection
SensorType.ENVIRONMENT    # Multi-environmental (CO2+temp+humidity)
SensorType.WEATHER        # Weather stations (temp+humidity+pressure)
SensorType.MOTION         # Motion detection
SensorType.DOOR           # Door/window sensors
SensorType.LEAK           # Water leak detection
```

---

## Error Handling

```python
from infrastructure.hardware.sensors import AdapterError

try:
    reading = manager.read_sensor(sensor_id=1)
    print(reading.value)
except AdapterError as e:
    print(f"Sensor error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## Best Practices

### ✅ DO:
- Use `SensorManager` for all sensor operations
- Register sensors at application startup
- Handle `AdapterError` exceptions
- Subscribe to EventBus for real-time updates
- Check `reading.status` before using values
- Monitor sensor health via `health_status`

### ❌ DON'T:
- Import drivers directly (`from drivers.co2_sensor import ...`)
- Call driver methods directly
- Bypass the SensorManager
- Ignore calibration data
- Skip error handling

---

## Example: Complete Workflow

```python
from infrastructure.hardware.sensors import (
    SensorManager, SensorType, Protocol,
    CalibrationData, CalibrationType
)
from app.utils.event_bus import EventBus
from datetime import datetime

# 1. Initialize
manager = SensorManager()
event_bus = EventBus.get_instance()

# 2. Setup calibration
calibration = CalibrationData(
    calibration_type=CalibrationType.LINEAR,
    parameters={'slope': 1.0, 'offset': 0.0},
    last_calibrated=datetime.utcnow()
)

# 3. Register sensor
sensor = manager.register_sensor(
    sensor_id=1,
    name="Environment Monitor",
    sensor_type=SensorType.ENVIRONMENT,
    protocol=Protocol.I2C,
    unit_id="1",
    model="ENS160AHT21",
    calibration=calibration
)

# 4. Subscribe to events
def on_reading(data):
    print(f"📊 Reading: {data['value']}")

event_bus.subscribe('sensor_reading', on_reading)

# 5. Read sensor (triggers automatic calibration & anomaly detection)
reading = manager.read_sensor(sensor_id=1)

# 6. Check results
if reading.status == ReadingStatus.SUCCESS:
    print(f"✅ Value: {reading.value}")
    if reading.metadata.get('anomaly_detected'):
        print(f"⚠️ Anomaly: {reading.metadata['anomaly_type']}")
else:
    print(f"❌ Failed: {reading.error}")

# 7. Monitor health
health = sensor.health_status
print(f"Health: {health.level} ({health.consecutive_failures} failures)")
```

---

## Troubleshooting

### Sensor Not Initializing
- Check hardware connections (I2C, GPIO pins)
- Verify I2C address (use `i2cdetect -y 1`)
- Ensure correct GPIO pin numbering (BCM mode)
- Check `dmesg` for kernel errors

### Reading Returns None
- Check sensor health: `sensor.health_status`
- Verify sensor is available: `sensor.is_available()`
- Check for hardware errors in logs
- Try reinitialization: `manager.configure_sensor(sensor_id, {'reinitialize': True})`

### Calibration Not Applied
- Verify calibration data: `sensor.calibration_data`
- Check calibration type matches sensor requirements
- Ensure calibration parameters are correct
- Review calibration processor logs

### Events Not Publishing
- Check EventBus initialization
- Verify subscribers are registered before reading
- Check event names match exactly
- Review EventBus logs for errors

---

## Further Documentation

- Architecture Overview: `REFACTORING_COMPLETE.md`
- Integration Guide: `SENSOR_INTEGRATION_GUIDE.md`
- Migration Summary: `docs/SENSOR_MIGRATION_SUMMARY.md`

---

**Need Help?** Check the logs in `infrastructure/hardware/sensors/*.log` or enable debug logging:

```python
import logging
logging.getLogger('infrastructure.hardware.sensors').setLevel(logging.DEBUG)
```
