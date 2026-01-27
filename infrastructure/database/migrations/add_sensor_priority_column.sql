-- Phase 6: Sensor Priority Migration
-- Date: 2025-12-19
-- Description: Add priority column to Sensor table for dashboard display ordering

-- Step 1: Add priority column (if not exists)
-- SQLite doesn't support IF NOT EXISTS for ALTER TABLE, so we check first
-- This will fail gracefully if column already exists

BEGIN TRANSACTION;

-- Add priority column with default value 30 (medium priority)
ALTER TABLE Sensor ADD COLUMN priority INTEGER DEFAULT 30;

COMMIT;

-- Step 2: Update priorities for existing sensors based on sensor type

BEGIN TRANSACTION;

-- HIGH PRIORITY (0-10): Dedicated sensors
-- These are sensors with single purpose (temperature-only, humidity-only)
UPDATE Sensor 
SET priority = 5 
WHERE sensor_type IN ('temp_humidity_sensor', 'environment_sensor', 'temperature', 'humidity', 'temperature_sensor', 'humidity_sensor')
  AND name NOT LIKE '%combo%'
  AND name NOT LIKE '%multi%'
  AND protocol IN ('GPIO', 'I2C');

-- MEDIUM PRIORITY (11-50): Multi-value sensors
-- These are sensors with multiple readings but still specialized
UPDATE Sensor 
SET priority = 20 
WHERE sensor_type IN ('soil_moisture', 'light', 'lux_sensor', 'soil_moisture_sensor', 'light_sensor')
  AND name NOT LIKE '%combo%'
  AND name NOT LIKE '%multi%';

-- MEDIUM-LOW PRIORITY (30-50): MQTT/Zigbee sensors
-- These are wireless sensors (typically combo sensors)
UPDATE Sensor 
SET priority = 40 
WHERE protocol IN ('mqtt', 'zigbee', 'zigbee2mqtt', 'MQTT', 'ZIGBEE', 'ZIGBEE2MQTT')
  AND name NOT LIKE '%combo%'
  AND name NOT LIKE '%multi%';

-- LOW PRIORITY (51-100): Combo/Multi sensors
-- These are sensors bundled together (e.g., soil moisture + temperature in same device)
UPDATE Sensor 
SET priority = 60 
WHERE name LIKE '%combo%' 
   OR name LIKE '%multi%'
   OR sensor_type = 'combo_sensor';

COMMIT;

-- Step 3: Verify changes
SELECT 
    sensor_id,
    name,
    sensor_type,
    protocol,
    priority,
    CASE 
        WHEN priority <= 10 THEN 'HIGH (Dedicated)'
        WHEN priority <= 50 THEN 'MEDIUM (Multi-value)'
        ELSE 'LOW (Combo)'
    END as priority_category
FROM Sensor 
ORDER BY priority ASC, sensor_id ASC;

-- Expected Results:
-- - Dedicated GPIO sensors: priority 5
-- - Multi-value sensors: priority 20
-- - MQTT/Zigbee sensors: priority 40
-- - Combo sensors: priority 60
-- - Default (unmapped): priority 30

-- Note: Lower priority = higher importance for dashboard display
