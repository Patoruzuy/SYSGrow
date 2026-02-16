"""Test enum consolidation after standardization"""

import sys
from pathlib import Path

# Add repository root to path.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.enums.device import Protocol, SensorType

print("Enum Consolidation Test")
print("=" * 70)

# Test Protocol enum
print("\nProtocol enum values:")
for p in Protocol:
    print(f"  {p.name:15} = {p.value}")

# Test SensorType enum
print("\nSensorType enum values:")
for s in SensorType:
    print(f"  {s.name:25} = {s.value}")

# Test backward compatibility
print("\n" + "=" * 70)
print("Backward Compatibility Tests:")
print("=" * 70)

# Test zigbee2mqtt protocol value
try:
    zigbee2mqtt_protocol = Protocol("zigbee2mqtt")
    print(f"✓ Protocol('zigbee2mqtt') = {zigbee2mqtt_protocol.name}")
except ValueError as e:
    print(f"✗ Protocol('zigbee2mqtt') failed: {e}")

# Test environment_sensor type value
try:
    env_sensor = SensorType("environment_sensor")
    print(f"✓ SensorType('environment_sensor') = {env_sensor.name}")
except ValueError as e:
    print(f"✗ SensorType('environment_sensor') failed: {e}")

# Test backward compat with _sensor suffix
try:
    soil_sensor = SensorType("soil_moisture_sensor")
    print(f"✓ SensorType('soil_moisture_sensor') = {soil_sensor.name}")
except ValueError as e:
    print(f"✗ SensorType('soil_moisture_sensor') failed: {e}")

# Test non-suffix version
try:
    soil = SensorType("soil_moisture")
    print(f"✓ SensorType('soil_moisture') = {soil.name}")
except ValueError as e:
    print(f"✗ SensorType('soil_moisture') failed: {e}")

print("\n" + "=" * 70)
print("Schema Validation Test:")
print("=" * 70)

# Test schema validation
from app.schemas.device import CreateSensorRequest

test_cases = [
    {
        "name": "Zigbee2MQTT Environment Sensor",
        "data": {
            "name": "Test Env Sensor",
            "model": "GENERIC_ZIGBEE",
            "unit_id": 1,
            "communication_type": "zigbee2mqtt",
            "type": "environment_sensor",
            "mqtt_topic": "zigbee2mqtt/test_env"
        }
    },
    {
        "name": "GPIO Soil Moisture Sensor",
        "data": {
            "name": "Test Soil Sensor",
            "model": "CAPACITIVE_SOIL",
            "unit_id": 1,
            "communication_type": "GPIO",
            "type": "soil_moisture",
            "gpio_pin": 15
        }
    },
    {
        "name": "MQTT Temperature Sensor",
        "data": {
            "name": "Test Temp Sensor",
            "model": "DHT22",
            "unit_id": 1,
            "communication_type": "mqtt",
            "type": "temperature",
            "mqtt_topic": "sensors/temp1"
        }
    }
]

for test in test_cases:
    try:
        schema = CreateSensorRequest(**test["data"])
        print(f"✓ {test['name']}")
        print(f"  Protocol: {schema.communication_type.value}")
        print(f"  Type: {schema.type.value}")
        print(f"  Model: {schema.model.value}")
    except Exception as e:
        print(f"✗ {test['name']}")
        print(f"  Error: {e}")

print("\n" + "=" * 70)
print("✓ All enum consolidation tests completed!")
print("=" * 70)
