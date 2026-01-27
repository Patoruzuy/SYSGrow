-- Migration: Sensor Architecture Upgrade
-- Date: 2025-11-15
-- Description: Migrate from old sensor schema to new enterprise architecture

-- Step 1: Rename old tables (backup)
ALTER TABLE Sensor RENAME TO Sensor_OLD;
ALTER TABLE SensorReading RENAME TO SensorReading_OLD;

-- Step 2: Create new sensor tables with improved schema

-- Core sensor table (normalized)
CREATE TABLE IF NOT EXISTS Sensor (
    sensor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    sensor_type VARCHAR(50) NOT NULL,  -- 'environment_sensor', 'soil_moisture_sensor', etc.
    protocol VARCHAR(20) NOT NULL,     -- 'GPIO', 'I2C', 'MQTT', 'ZIGBEE', 'MODBUS'
    model VARCHAR(50) NOT NULL,        -- 'ENS160AHT21', 'TSL2591', 'DHT22'
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE
);

-- Protocol-specific configurations (JSON for flexibility)
CREATE TABLE IF NOT EXISTS SensorConfig (
    config_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    config_data TEXT NOT NULL,  -- JSON: {"gpio_pin": 4, "i2c_bus": 1, "mqtt_topic": "..."}
    FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
);

-- Calibration data (persistent)
CREATE TABLE IF NOT EXISTS SensorCalibration (
    calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    calibration_type VARCHAR(20) DEFAULT 'linear',  -- 'linear', 'polynomial', 'lookup'
    measured_value REAL NOT NULL,
    reference_value REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
);

-- Health tracking (for dashboard)
CREATE TABLE IF NOT EXISTS SensorHealthHistory (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    health_score INTEGER NOT NULL,  -- 0-100
    status VARCHAR(20) NOT NULL,     -- 'healthy', 'degraded', 'critical', 'offline'
    error_rate REAL DEFAULT 0.0,
    total_readings INTEGER DEFAULT 0,
    failed_readings INTEGER DEFAULT 0,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
);

-- Anomaly detection log
CREATE TABLE IF NOT EXISTS SensorAnomaly (
    anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    value REAL NOT NULL,
    mean_value REAL,
    std_deviation REAL,
    z_score REAL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
);

-- Keep SensorReading table but update it
CREATE TABLE IF NOT EXISTS SensorReading (
    reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_id INTEGER NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    reading_data TEXT NOT NULL,  -- JSON: {"temperature": 25.0, "humidity": 60}
    quality_score REAL DEFAULT 1.0,
    FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_sensor_unit_id ON Sensor(unit_id);
CREATE INDEX IF NOT EXISTS idx_sensor_type ON Sensor(sensor_type);
CREATE INDEX IF NOT EXISTS idx_sensor_protocol ON Sensor(protocol);
CREATE INDEX IF NOT EXISTS idx_sensor_health_sensor_id ON SensorHealthHistory(sensor_id);
CREATE INDEX IF NOT EXISTS idx_sensor_anomaly_sensor_id ON SensorAnomaly(sensor_id);
CREATE INDEX IF NOT EXISTS idx_sensor_calibration_sensor_id ON SensorCalibration(sensor_id);
CREATE INDEX IF NOT EXISTS idx_sensor_reading_sensor_id ON SensorReading(sensor_id);
CREATE INDEX IF NOT EXISTS idx_sensor_reading_timestamp ON SensorReading(timestamp);

-- Step 3: Migrate existing data
INSERT INTO Sensor (sensor_id, unit_id, name, sensor_type, protocol, model, is_active, created_at)
SELECT 
    sensor_id,
    COALESCE(unit_id, 1) as unit_id,
    COALESCE(name, 'Sensor_' || sensor_id) as name,
    CASE 
        WHEN sensor_model = 'Soil-Moisture' THEN 'soil_moisture_sensor'
        WHEN sensor_model = 'ENS160AHT21' THEN 'environment_sensor'
        WHEN sensor_model = 'TSL2591' THEN 'light_sensor'
        WHEN sensor_model = 'MQ2' THEN 'smoke_sensor'
        WHEN sensor_model = 'BME280' THEN 'environment_sensor'
        WHEN sensor_model = 'DHT11' THEN 'temp_humidity_sensor'
        WHEN sensor_model = 'DHT22' THEN 'temp_humidity_sensor'
        ELSE 'temperature_sensor'
    END as sensor_type,
    CASE 
        WHEN communication = 'I2C' THEN 'I2C'
        WHEN communication = 'WIRELESS' THEN 'MQTT'
        WHEN gpio IS NOT NULL THEN 'GPIO'
        ELSE 'GPIO'
    END as protocol,
    sensor_model as model,
    1 as is_active,
    CURRENT_TIMESTAMP as created_at
FROM Sensor_OLD;

-- Migrate sensor configs
INSERT INTO SensorConfig (sensor_id, config_data)
SELECT 
    sensor_id,
    json_object(
        'gpio_pin', gpio,
        'ip_address', ip_address,
        'update_interval', update_interval,
        'battery_key', battery_key,
        'redis_keys', redis_keys
    ) as config_data
FROM Sensor_OLD;

-- Migrate sensor readings (convert to JSON format)
INSERT INTO SensorReading (sensor_id, timestamp, reading_data, quality_score)
SELECT 
    sensor_id,
    timestamp,
    json_object(
        'temperature', temperature,
        'humidity', humidity,
        'soil_moisture', soil_moisture,
        'co2_ppm', co2_ppm,
        'voc_ppb', voc_ppb,
        'aqi', aqi,
        'pressure', pressure
    ) as reading_data,
    1.0 as quality_score
FROM SensorReading_OLD;

-- Step 4: Drop old tables (comment out if you want to keep backups)
-- DROP TABLE Sensor_OLD;
-- DROP TABLE SensorReading_OLD;

-- Step 5: Update any foreign key references in other tables
-- (Add any other tables that reference Sensor table here)
