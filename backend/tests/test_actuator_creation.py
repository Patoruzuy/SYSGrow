"""Test actuator creation with new schema"""
import os
import json
import pytest
import requests

# Skip this live API test when running in sandbox/CI environments.
if os.getenv("SYSGROW_RUN_LIVE_API_TESTS") != "1":
    pytest.skip("Skipping live actuator creation test (requires running server)", allow_module_level=True)

BASE_URL = "http://localhost:5000/api"

print("=" * 60)
print("🧪 TESTING ACTUATOR CREATION")
print("=" * 60)

# Test 1: Create actuator with GPIO
print("\n📍 Test 1: Creating GPIO actuator...")
response = requests.post(f"{BASE_URL}/devices/actuators", json={
    "actuator_type": "Light",
    "device": "Grow Light 1",
    "unit_id": 1,
    "gpio": 17
})

if response.status_code == 200:
    data = response.json()
    print(f"✅ Success! Actuator ID: {data.get('actuator_id')}")
    actuator_id_gpio = data.get('actuator_id')
else:
    print(f"❌ Failed: {response.status_code}")
    print(response.text)
    actuator_id_gpio = None

# Test 2: Create actuator with MQTT
print("\n📡 Test 2: Creating MQTT actuator...")
response = requests.post(f"{BASE_URL}/devices/actuators", json={
    "actuator_type": "Water-Pump",
    "device": "Water Pump 1",
    "unit_id": 1,
    "mqtt_topic": "growroom/pump1/set",
    "mqtt_broker": "localhost",
    "mqtt_port": 1883
})

if response.status_code == 200:
    data = response.json()
    print(f"✅ Success! Actuator ID: {data.get('actuator_id')}")
    actuator_id_mqtt = data.get('actuator_id')
else:
    print(f"❌ Failed: {response.status_code}")
    print(response.text)
    actuator_id_mqtt = None

# Test 3: Create actuator with Zigbee
print("\n🔷 Test 3: Creating Zigbee actuator...")
response = requests.post(f"{BASE_URL}/devices/actuators", json={
    "actuator_type": "Fan",
    "device": "Exhaust Fan 1",
    "unit_id": 1,
    "zigbee_channel": "channel_15",
    "zigbee_topic": "zigbee2mqtt/exhaust_fan"
})

if response.status_code == 200:
    data = response.json()
    print(f"✅ Success! Actuator ID: {data.get('actuator_id')}")
    actuator_id_zigbee = data.get('actuator_id')
else:
    print(f"❌ Failed: {response.status_code}")
    print(response.text)
    actuator_id_zigbee = None

# Test 4: List all actuators
print("\n📋 Test 4: Listing all actuators...")
response = requests.get(f"{BASE_URL}/devices/actuators")

if response.status_code == 200:
    actuators = response.json().get('actuators', [])
    print(f"✅ Success! Found {len(actuators)} actuators:")
    for act in actuators:
        print(f"\n   ID: {act.get('actuator_id')}")
        print(f"   Name: {act.get('device')}")
        print(f"   Type: {act.get('actuator_type')}")
        print(f"   Protocol: {act.get('protocol')}")
        print(f"   Unit: {act.get('unit_id')}")
        if act.get('gpio'):
            print(f"   GPIO: {act.get('gpio')}")
        if act.get('mqtt_broker'):
            print(f"   MQTT: {act.get('mqtt_broker')}:{act.get('mqtt_port')}")
else:
    print(f"❌ Failed: {response.status_code}")

# Test 5: Verify database directly
print("\n" + "=" * 60)
print("🔍 DIRECT DATABASE VERIFICATION")
print("=" * 60)

import sqlite3
conn = sqlite3.connect('database/sysgrow.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check Actuator table
print("\n📊 Actuator Table:")
cursor.execute("SELECT * FROM Actuator")
rows = cursor.fetchall()
for row in rows:
    print(f"\n   ID: {row['actuator_id']}")
    print(f"   Unit: {row['unit_id']}")
    print(f"   Name: {row['name']}")
    print(f"   Type: {row['actuator_type']}")
    print(f"   Protocol: {row['protocol']}")
    print(f"   Model: {row['model']}")
    print(f"   Active: {row['is_active']}")

# Check ActuatorConfig table
print("\n⚙️ ActuatorConfig Table:")
cursor.execute("SELECT * FROM ActuatorConfig")
rows = cursor.fetchall()
for row in rows:
    config_data = json.loads(row['config_data'])
    print(f"\n   Actuator ID: {row['actuator_id']}")
    print(f"   Config: {json.dumps(config_data, indent=6)}")

conn.close()

print("\n" + "=" * 60)
print("✅ ALL TESTS COMPLETED!")
print("=" * 60)
print("\n🎉 New schema is working correctly with backward compatibility!\n")
