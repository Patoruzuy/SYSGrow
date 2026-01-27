-- ============================================
-- DATABASE MIGRATION: Add Multi-User Support
-- ============================================
-- Version: 1.0
-- Date: November 6, 2025
-- Purpose: Add user_id, dimensions, custom_image, and timestamps to GrowthUnits
--
-- IMPORTANT: Backup your database before running!
-- SQLite doesn't support ALTER COLUMN, so we recreate the table
-- ============================================

PRAGMA foreign_keys = OFF;

BEGIN TRANSACTION;

-- Step 1: Create new GrowthUnits table with additional columns
CREATE TABLE IF NOT EXISTS GrowthUnits_new (
    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    location TEXT DEFAULT 'Indoor',
    dimensions TEXT,  -- JSON: {"width": 120, "height": 180, "depth": 80}
    custom_image TEXT,
    active_plant_id INTEGER,
    temperature_threshold REAL DEFAULT 24.0,
    humidity_threshold REAL DEFAULT 50.0,
    soil_moisture_threshold REAL DEFAULT 40.0,
    co2_threshold REAL DEFAULT 800.0,
    voc_threshold REAL DEFAULT 0.0,
    lux_threshold INTEGER DEFAULT 500,
    aqi_threshold INTEGER DEFAULT 50,
    light_start_time TEXT DEFAULT '08:00',
    light_end_time TEXT DEFAULT '20:00',
    camera_active INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (active_plant_id) REFERENCES Plants(plant_id),
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
);

-- Step 2: Copy existing data to new table
INSERT INTO GrowthUnits_new (
    unit_id,
    user_id,
    name,
    location,
    active_plant_id,
    temperature_threshold,
    humidity_threshold,
    soil_moisture_threshold,
    co2_threshold,
    voc_threshold,
    lux_threshold,
    aqi_threshold,
    light_start_time,
    light_end_time,
    created_at
)
SELECT 
    unit_id,
    1 as user_id,  -- Assign all existing units to default user
    name,
    location,
    active_plant_id,
    temperature_threshold,
    humidity_threshold,
    soil_moisture_threshold,
    co2_threshold,
    voc_threshold,
    lux_threshold,
    aqi_threshold,
    light_start_time,
    light_end_time,
    CURRENT_TIMESTAMP as created_at
FROM GrowthUnits;

-- Step 3: Drop old table
DROP TABLE GrowthUnits;

-- Step 4: Rename new table
ALTER TABLE GrowthUnits_new RENAME TO GrowthUnits;

-- Step 5: Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_growth_units_user_id ON GrowthUnits(user_id);
CREATE INDEX IF NOT EXISTS idx_growth_units_created_at ON GrowthUnits(created_at DESC);

-- Step 6: Add sample dimensions to existing units (optional)
UPDATE GrowthUnits 
SET dimensions = '{"width": 120, "height": 180, "depth": 80, "volume_liters": 1728}'
WHERE dimensions IS NULL;

COMMIT;

PRAGMA foreign_keys = ON;

-- Verification queries
SELECT 'Migration completed successfully!' as status;
SELECT COUNT(*) as total_units FROM GrowthUnits;
SELECT COUNT(*) as units_with_user_id FROM GrowthUnits WHERE user_id IS NOT NULL;
SELECT COUNT(*) as units_with_dimensions FROM GrowthUnits WHERE dimensions IS NOT NULL;

-- Show new table structure
PRAGMA table_info(GrowthUnits);
