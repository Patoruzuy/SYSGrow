# Sensor Integration Guide

## Overview

This guide explains how the **existing sensor implementations** integrate with the **new enterprise architecture**.

## Architecture Integration

### Old vs New

**Old Implementation (Still Available):**
```python
# Direct sensor class usage
from infrastructure.hardware.sensors import ENS160_AHT21Sensor

sensor = ENS160_AHT21Sensor(unit_id="1")
data = sensor.read(push=False)  # Returns raw dict
```

**New Implementation (Recommended):**
```python
# Using enterprise architecture
from infrastructure.hardware.sensors import SensorManager, SensorType, Protocol

manager = SensorManager()
sensor = manager.register_sensor(
    sensor_id=1,
    name="Environment Sensor",
    sensor_type=SensorType.ENVIRONMENT,
    protocol=Protocol.I2C,
    unit_id="1",
    model="ENS160AHT21"
)

reading = manager.read_sensor(1)  # Returns SensorReading object with validation, calibration, enrichment
```

## How It Works

### 1. GPIO Adapter Wraps Old Sensors

The `GPIOSensorAdapter` acts as a bridge between the old sensor classes and the new architecture:

```python
# adapters/gpio_adapter.py
class GPIOSensorAdapter(BaseSensorAdapter):
    def _initialize_sensor(self):
        if self.sensor_model == "ENS160AHT21":
            from infrastructure.hardware.sensors.co2_sensor import ENS160_AHT21Sensor
            self._sensor_impl = ENS160_AHT21Sensor(
                unit_id=unit_id,
                use_mqtt=False,  # Disable direct MQTT publishing
                mqtt_config=None,
                redis_config=None
            )
    
    def read(self):
        # Call old sensor's read() method with push=False
        data = self._sensor_impl.read(push=False)
        return data
```

### 2. Data Flows Through Processing Pipeline

```
Old Sensor → GPIO Adapter → Validation → Calibration → Transformation → Enrichment → SensorReading
```

### 3. EventBus Integration

Instead of each sensor publishing to MQTT/Redis directly, the new `SensorManager` emits events:

```python
# manager.py
reading = sensor.read()  # Adapter wraps old sensor
self.event_bus.emit('sensor_reading', {
    'sensor_id': sensor_id,
    'reading': reading.to_dict()
})
```

## Supported Sensors

### 1. ENS160 + AHT21 (Air Quality + Temp/Humidity)

**Old Usage:**
```python
from infrastructure.hardware.sensors.co2_sensor import ENS160_AHT21Sensor

sensor = ENS160_AHT21Sensor(unit_id="1", use_mqtt=False)
data = sensor.read(push=False)
# Returns: {'eco2': 420, 'tvoc': 35, 'temperature': 24.3, 'humidity': 55.1, 'status': 'OK', 'timestamp': '...'}
```

**New Usage:**
```python
manager = SensorManager()
sensor = manager.register_sensor(
    sensor_id=1,
    name="Grow Tent Air Quality",
    sensor_type=SensorType.ENVIRONMENT,
    protocol=Protocol.I2C,
    unit_id="1",
    model="ENS160AHT21"
)

reading = manager.read_sensor(1)
# Returns: SensorReading(value={'eco2': 420, ...}, status=ReadingStatus.SUCCESS, ...)
```

**Benefits:**
- ✅ Automatic validation (check ranges)
- ✅ Calibration support
- ✅ Anomaly detection
- ✅ Health monitoring
- ✅ Event-driven notifications

---

### 2. TSL2591 (Light Sensor)

**Old Usage:**
```python
from infrastructure.hardware.sensors.light_sensor import TSL2591Driver

sensor = TSL2591Driver(unit_id="1", use_mqtt=False)
data = sensor.read(push=False)
# Returns: {'lux': 550.5, 'full_spectrum': 1200, 'infrared': 450, 'visible': 750, 'timestamp': '...'}
```

**New Usage:**
```python
sensor = manager.register_sensor(
    sensor_id=2,
    name="Grow Light Sensor",
    sensor_type=SensorType.LIGHT,
    protocol=Protocol.I2C,
    unit_id="1",
    model="TSL2591"
)

reading = manager.read_sensor(2)
```

---

### 3. Soil Moisture Sensor (ADS1115 ADC)

**Old Usage:**
```python
from infrastructure.hardware.sensors.soil_moisture_sensor import SoilMoistureSensorV2
import adafruit_ads1x15.ads1115 as ADC

sensor = SoilMoistureSensorV2(adc_channel=ADC.P0, unit_id="1")
data = sensor.read(push_to_redis=False)
# Returns: {'soil_moisture': 52.4, 'adc_raw': 12000, 'voltage': 2.3, 'timestamp': '...', 'status': 'OK'}
```

**New Usage:**
```python
sensor = manager.register_sensor(
    sensor_id=3,
    name="Soil Moisture - Pot 1",
    sensor_type=SensorType.SOIL_MOISTURE,
    protocol=Protocol.GPIO,
    unit_id="1",
    model="Soil-Moisture",
    adc_channel=0  # Will be converted to ADC.P0
)

reading = manager.read_sensor(3)
```

---

### 4. MQ2 (Smoke/Gas Sensor)

**Old Usage:**
```python
from infrastructure.hardware.sensors.mq2_sensor import MQ2Sensor

# Digital mode
sensor = MQ2Sensor(sensor_pin=17, is_digital=True, unit_id="1", use_mqtt=False)
data = sensor.read(push_to_output=False)
# Returns: {'smoke': 0, 'mode': 'digital', 'timestamp': '...', 'status': 'OK'}

# Analog mode
sensor = MQ2Sensor(sensor_pin=17, is_digital=False, channel=0, unit_id="1", use_mqtt=False)
data = sensor.read(push_to_output=False)
# Returns: {'smoke': 16384, 'mode': 'analog', 'timestamp': '...', 'status': 'OK'}
```

**New Usage:**
```python
# Digital mode
sensor = manager.register_sensor(
    sensor_id=4,
    name="Smoke Detector",
    sensor_type=SensorType.SMOKE,
    protocol=Protocol.GPIO,
    unit_id="1",
    model="MQ2",
    gpio_pin=17,
    is_digital=True
)

# Analog mode
sensor = manager.register_sensor(
    sensor_id=5,
    name="Gas Level Sensor",
    sensor_type=SensorType.SMOKE,
    protocol=Protocol.GPIO,
    unit_id="1",
    model="MQ2",
    gpio_pin=17,
    is_digital=False,
    adc_channel=0
)

reading = manager.read_sensor(4)
```

---

### 5. DHT11 (Temperature + Humidity)

**Old Usage:**
```python
from infrastructure.hardware.sensors.dht11_sensor import DHT11Sensor

sensor = DHT11Sensor(pin=4, unit_id="1", use_mqtt=False)
data = sensor.read(retries=3, delay=2, push=False)
# Returns: {'temperature': 23.4, 'humidity': 48.6, 'timestamp': '...', 'status': 'OK'}
```

**New Usage:**
```python
sensor = manager.register_sensor(
    sensor_id=6,
    name="DHT11 Temp/Humidity",
    sensor_type=SensorType.TEMP_HUMIDITY,
    protocol=Protocol.GPIO,
    unit_id="1",
    model="DHT11",
    gpio_pin=4
)

reading = manager.read_sensor(6)
```

---

### 6. BME280 (Temperature + Humidity + Pressure)

**Old Usage:**
```python
from infrastructure.hardware.sensors.temp_humidity_sensor import BME280Sensor

sensor = BME280Sensor(unit_id="1", use_mqtt=False)
data = sensor.read(include_altitude=False, push=False)
# Returns: {'temperature': 24.7, 'humidity': 51.2, 'pressure': 1012.3, 'timestamp': '...', 'status': 'OK'}
```

**New Usage:**
```python
sensor = manager.register_sensor(
    sensor_id=7,
    name="BME280 Weather Station",
    sensor_type=SensorType.TEMP_HUMIDITY,
    protocol=Protocol.I2C,
    unit_id="1",
    model="BME280"
)

reading = manager.read_sensor(7)
```

---

## Migration Strategy

### Phase 1: Coexistence ✅ (Current)

Both old and new implementations work side-by-side:

```python
# Old code continues to work
from infrastructure.hardware.sensors.co2_sensor import ENS160_AHT21Sensor
sensor = ENS160_AHT21Sensor(unit_id="1")

# New code uses SensorManager
from infrastructure.hardware.sensors import SensorManager
manager = SensorManager()
```

### Phase 2: Feature Flag (Next)

Add environment variable to enable new system:

```python
import os
ENABLE_NEW_SENSOR_MANAGER = os.getenv('ENABLE_NEW_SENSOR_MANAGER', 'false').lower() == 'true'

if ENABLE_NEW_SENSOR_MANAGER:
    from infrastructure.hardware.sensors import SensorManager
    sensor_manager = SensorManager()
else:
    # Use old sensor_manager.py
    from infrastructure.hardware.sensor_manager import SensorManager
    sensor_manager = SensorManager()
```

### Phase 3: Gradual Migration

1. Enable for 1 sensor → monitor for 24h
2. Enable for all GPIO sensors → monitor for 1 week
3. Enable for MQTT sensors → monitor for 1 week
4. Enable for all sensors
5. Remove old code

### Phase 4: Deprecation

Mark old sensor classes as deprecated:

```python
import warnings

class ENS160_AHT21Sensor:
    def __init__(self, *args, **kwargs):
        warnings.warn(
            "ENS160_AHT21Sensor is deprecated. Use SensorManager instead.",
            DeprecationWarning,
            stacklevel=2
        )
        # ... existing code
```

---

## Key Differences

### Data Format

**Old:**
```python
data = sensor.read()
# {'temperature': 24.3, 'humidity': 55.1, 'timestamp': '...', 'status': 'OK'}
```

**New:**
```python
reading = manager.read_sensor(1)
# SensorReading(
#     value={'temperature': 24.3, 'humidity': 55.1},
#     status=ReadingStatus.SUCCESS,
#     timestamp=datetime(...),
#     quality_score=0.95,
#     calibration_applied=True,
#     anomalies=[]
# )

# Access data
print(reading.value['temperature'])
print(reading.to_dict())
```

### Publishing

**Old:**
```python
# Each sensor publishes directly to MQTT/Redis
sensor = ENS160_AHT21Sensor(use_mqtt=True, mqtt_config={...})
data = sensor.read(push=True)  # Publishes immediately
```

**New:**
```python
# SensorManager emits events, subscribers handle publishing
manager = SensorManager(mqtt_client=mqtt_client)
reading = manager.read_sensor(1)  # Emits 'sensor_reading' event

# Event handler can publish to MQTT/Redis
def on_sensor_reading(event_data):
    mqtt_client.publish(topic, json.dumps(event_data['reading']))

manager.event_bus.subscribe('sensor_reading', on_sensor_reading)
```

### Error Handling

**Old:**
```python
try:
    data = sensor.read()
    if 'error' in data:
        print(f"Sensor error: {data['error']}")
except Exception as e:
    print(f"Read failed: {e}")
```

**New:**
```python
reading = manager.read_sensor(1)

# Check status
if reading.status == ReadingStatus.ERROR:
    print(f"Error: {reading.error_message}")

# Check health
health = manager.get_sensor_health(1)
if health['level'] == HealthLevel.CRITICAL:
    print(f"Sensor unhealthy: {health['message']}")
```

---

## Advanced Features (New Architecture Only)

### 1. Calibration

```python
from infrastructure.hardware.sensors import CalibrationService

calib_service = CalibrationService()

# Two-point calibration
calibration = calib_service.create_two_point_calibration(
    sensor_id=1,
    point1=(20.0, 19.5),  # (measured, reference)
    point2=(30.0, 29.8),
    unit="°C",
    calibrated_by="admin"
)

manager.apply_calibration(1, calibration)
```

### 2. Anomaly Detection

```python
# Automatic anomaly detection on every read
reading = manager.read_sensor(1)

if reading.anomalies:
    for anomaly in reading.anomalies:
        print(f"Anomaly: {anomaly.type.value} - {anomaly.message}")
```

### 3. Health Monitoring

```python
# System-wide health report
report = manager.get_health_report()

print(f"Total Sensors: {report.total_sensors}")
print(f"Healthy: {report.healthy_sensors}")
print(f"Degraded: {report.degraded_sensors}")
print(f"System Health: {report.system_health_level.value}")

# Individual sensor health
health = manager.get_sensor_health(1)
print(f"Success Rate: {health['success_rate']}%")
print(f"Consecutive Errors: {health['consecutive_errors']}")
```

### 4. Auto-Discovery (Zigbee2MQTT)

```python
# Automatic discovery of new sensors
def on_sensor_discovered(device_info):
    print(f"New sensor found: {device_info['friendly_name']}")
    print(f"Type: {device_info['type']}")
    print(f"Capabilities: {device_info['capabilities']}")

manager.discovery_service.register_discovery_callback(on_sensor_discovered)
```

---

## Testing

### Testing Old Sensors

```python
# Unit test for old sensor
def test_ens160_aht21_sensor():
    sensor = ENS160_AHT21Sensor(unit_id="test")
    data = sensor.read(push=False)
    
    assert 'temperature' in data
    assert 'humidity' in data
    assert 'eco2' in data
```

### Testing New Architecture

```python
# Unit test with new architecture
def test_sensor_manager():
    manager = SensorManager()
    
    sensor = manager.register_sensor(
        sensor_id=1,
        name="Test Sensor",
        sensor_type=SensorType.ENVIRONMENT,
        protocol=Protocol.I2C,
        unit_id="test",
        model="ENS160AHT21"
    )
    
    reading = manager.read_sensor(1)
    
    assert reading.status == ReadingStatus.SUCCESS
    assert 'temperature' in reading.value
    assert reading.quality_score > 0
```

---

## Benefits of New Architecture

### 1. Separation of Concerns
- ✅ Hardware communication (Adapter)
- ✅ Business logic (Domain Entity)
- ✅ Data processing (Processors)
- ✅ Application logic (Services)

### 2. Testability
- ✅ Mock adapters for unit tests
- ✅ No hardware dependency in tests
- ✅ Isolated component testing

### 3. Extensibility
- ✅ Easy to add new sensors
- ✅ Easy to add new protocols
- ✅ Easy to add new processors

### 4. Data Quality
- ✅ Validation
- ✅ Calibration
- ✅ Anomaly detection
- ✅ Quality scoring

### 5. Observability
- ✅ Health monitoring
- ✅ Success rate tracking
- ✅ Event-driven architecture
- ✅ Centralized logging

---

## Backward Compatibility

The old sensor classes remain **fully functional** and can be used directly:

```python
# This will continue to work indefinitely
from infrastructure.hardware.sensors import ENS160_AHT21Sensor, DHT11Sensor

ens_sensor = ENS160_AHT21Sensor(unit_id="1", use_mqtt=False)
dht_sensor = DHT11Sensor(pin=4, unit_id="1", use_mqtt=False)

ens_data = ens_sensor.read(push=False)
dht_data = dht_sensor.read(push=False)
```

No breaking changes for existing code!

---

## Next Steps

1. **Review** this integration guide
2. **Test** new SensorManager with existing sensors
3. **Add** feature flag for gradual rollout
4. **Monitor** health metrics during migration
5. **Document** any issues or edge cases
6. **Plan** actuator refactoring using same patterns

---

## Questions?

See also:
- `docs/SENSOR_MIGRATION_SUMMARY.md` - Complete implementation details
- `docs/SENSOR_MIGRATION_PROGRESS.md` - Progress tracking
- `infrastructure/hardware/sensors/README.md` - API documentation
