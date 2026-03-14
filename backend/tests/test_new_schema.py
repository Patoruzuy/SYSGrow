#!/usr/bin/env python3
"""Test the new sensor schema by creating a test sensor."""
import os
import sqlite3
import json
import pytest

# Skip when running without access to the legacy database path.
if os.getenv("SYSGROW_RUN_DB_MUTATION_TESTS") != "1":
    pytest.skip("Skipping legacy DB mutation test in sandbox", allow_module_level=True)

db_path = os.getenv("SYSGROW_DATABASE_PATH", "database/grow_tent.db")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

print("=" * 60)
print("Testing New Sensor Schema")
print("=" * 60)

# Create a test sensor
print("\n1️⃣ Creating test sensor...")
cursor = conn.execute("""
    INSERT INTO Sensor (unit_id, name, sensor_type, protocol, model, is_active)
    VALUES (?, ?, ?, ?, ?, ?)
""", (1, "Test Environment Sensor", "environment_sensor", "I2C", "ENS160AHT21", 1))
sensor_id = cursor.lastrowid
conn.commit()
print(f"✅ Created sensor ID: {sensor_id}")

# Add sensor config
print("\n2️⃣ Adding sensor configuration...")
config_data = json.dumps({
    "gpio_pin": 4,
    "i2c_bus": 1,
    "i2c_address": "0x53"
})
conn.execute("""
    INSERT INTO SensorConfig (sensor_id, config_data)
    VALUES (?, ?)
""", (sensor_id, config_data))
conn.commit()
print("✅ Configuration added")

# Add calibration point
print("\n3️⃣ Adding calibration point...")
conn.execute("""
    INSERT INTO SensorCalibration (sensor_id, measured_value, reference_value, calibration_type)
    VALUES (?, ?, ?, ?)
""", (sensor_id, 24.8, 25.0, "linear"))
conn.commit()
print("✅ Calibration point added")

# Add health snapshot
print("\n4️⃣ Adding health snapshot...")
conn.execute("""
    INSERT INTO SensorHealthHistory (sensor_id, health_score, status, error_rate, total_readings, failed_readings)
    VALUES (?, ?, ?, ?, ?, ?)
""", (sensor_id, 0.95, "healthy", 0.02, 100, 2))
conn.commit()
print("✅ Health snapshot added")

# Query the sensor with all related data
print("\n5️⃣ Querying sensor with config...")
result = conn.execute("""
    SELECT 
        s.sensor_id,
        s.name,
        s.sensor_type,
        s.protocol,
        s.model,
        sc.config_data
    FROM Sensor s
    LEFT JOIN SensorConfig sc ON s.sensor_id = sc.sensor_id
    WHERE s.sensor_id = ?
""", (sensor_id,)).fetchone()

print(f"""
✅ Sensor retrieved:
   ID: {result['sensor_id']}
   Name: {result['name']}
   Type: {result['sensor_type']}
   Protocol: {result['protocol']}
   Model: {result['model']}
   Config: {result['config_data']}
""")

# Query calibration history
print("6️⃣ Querying calibration history...")
calibrations = conn.execute("""
    SELECT measured_value, reference_value, calibration_type, created_at
    FROM SensorCalibration
    WHERE sensor_id = ?
    ORDER BY created_at DESC
""", (sensor_id,)).fetchall()
print(f"✅ Found {len(calibrations)} calibration point(s)")

# Query health history
print("\n7️⃣ Querying health history...")
health = conn.execute("""
    SELECT health_score, status, error_rate, recorded_at
    FROM SensorHealthHistory
    WHERE sensor_id = ?
    ORDER BY recorded_at DESC
""", (sensor_id,)).fetchall()
print(f"✅ Found {len(health)} health snapshot(s)")

print("\n" + "=" * 60)
print("✅ All tests passed! New schema is working correctly.")
print("=" * 60)

conn.close()
