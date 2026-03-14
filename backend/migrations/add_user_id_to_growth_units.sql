-- ============================================
-- DATABASE MIGRATION SCRIPT
-- Add Multi-User Support to Growth Units
-- ============================================
-- Version: 1.0
-- Date: November 2025
-- Purpose: Enable multi-tenant support for growth units
-- 
-- This script adds user_id foreign key and related columns
-- to support the new service-based architecture
-- ============================================

-- Step 1: Add new columns to growth_units table
-- ============================================

-- Add user_id column (nullable initially for existing data)
ALTER TABLE growth_units ADD COLUMN user_id INTEGER;

-- Add dimensions column (stores JSON: width, length, height, volume)
ALTER TABLE growth_units ADD COLUMN dimensions TEXT;

-- Add custom_image column (stores file path or URL)
ALTER TABLE growth_units ADD COLUMN custom_image TEXT;

-- Add timestamp columns for audit trail
ALTER TABLE growth_units ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE growth_units ADD COLUMN updated_at TIMESTAMP;

-- Add is_active flag if it doesn't exist
-- (Check if column exists first - skip if already present)
-- ALTER TABLE growth_units ADD COLUMN is_active INTEGER DEFAULT 1;

-- Step 2: Migrate existing data
-- ============================================

-- IMPORTANT: Assign all existing units to default user (user_id = 1)
-- Adjust this if you have a different default user
UPDATE growth_units 
SET user_id = 1 
WHERE user_id IS NULL;

-- Set default created_at for existing units (use current timestamp)
UPDATE growth_units 
SET created_at = CURRENT_TIMESTAMP 
WHERE created_at IS NULL;

-- Step 3: Add constraints and indexes
-- ============================================

-- Create index on user_id for fast user queries
CREATE INDEX idx_growth_units_user_id ON growth_units(user_id);

-- Create index on is_active for filtering active units
CREATE INDEX idx_growth_units_active ON growth_units(is_active);

-- Create composite index for common queries (user_id + is_active)
CREATE INDEX idx_growth_units_user_active ON growth_units(user_id, is_active);

-- Add foreign key constraint (if users table exists)
-- Note: SQLite doesn't support ALTER TABLE ADD CONSTRAINT for foreign keys
-- This would need to be done during table creation or via table recreation
-- See alternative approach below if needed

-- Step 4: Make user_id NOT NULL
-- ============================================

-- After migration, make user_id required
-- Note: SQLite doesn't support ALTER COLUMN directly
-- We need to recreate the table. See Step 5 if needed.

-- Step 5: Create new table with proper constraints (if needed)
-- ============================================
-- This is the "SQLite way" to add NOT NULL and foreign keys

-- Create new table with all constraints
CREATE TABLE growth_units_new (
    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    location TEXT,
    dimensions TEXT,
    custom_image TEXT,
    is_active INTEGER DEFAULT 1,
    camera_active INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- Copy data from old table to new table
INSERT INTO growth_units_new 
    (unit_id, user_id, name, location, dimensions, custom_image, 
     is_active, camera_active, created_at, updated_at)
SELECT 
    unit_id, user_id, name, location, dimensions, custom_image,
    is_active, camera_active, created_at, updated_at
FROM growth_units;

-- Drop old table
DROP TABLE growth_units;

-- Rename new table to original name
ALTER TABLE growth_units_new RENAME TO growth_units;

-- Recreate indexes on new table
CREATE INDEX idx_growth_units_user_id ON growth_units(user_id);
CREATE INDEX idx_growth_units_active ON growth_units(is_active);
CREATE INDEX idx_growth_units_user_active ON growth_units(user_id, is_active);

-- Step 6: Create device_unit_links table (if not exists)
-- ============================================
-- This table links sensors/actuators to growth units

CREATE TABLE IF NOT EXISTS device_unit_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    device_id TEXT NOT NULL,
    device_type TEXT NOT NULL, -- 'sensor' or 'actuator'
    device_name TEXT,
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES growth_units(unit_id) ON DELETE CASCADE
);

-- Create indexes for device lookups
CREATE INDEX IF NOT EXISTS idx_device_links_unit ON device_unit_links(unit_id);
CREATE INDEX IF NOT EXISTS idx_device_links_device ON device_unit_links(device_id);
CREATE INDEX IF NOT EXISTS idx_device_links_type ON device_unit_links(device_type);

-- Step 7: Update plants table to support unit_id (if not already present)
-- ============================================

-- Check if unit_id exists in plants table, add if missing
-- ALTER TABLE plants ADD COLUMN unit_id INTEGER;

-- Add foreign key to link plants to units
-- (This requires table recreation in SQLite - similar to Step 5)

-- Create index on unit_id for fast queries
CREATE INDEX IF NOT EXISTS idx_plants_unit_id ON plants(unit_id);
CREATE INDEX IF NOT EXISTS idx_plants_active ON plants(active);

-- Step 8: Create plant_sensor_links table (if not exists)
-- ============================================
-- This table links individual plants to their sensors

CREATE TABLE IF NOT EXISTS plant_sensor_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id INTEGER NOT NULL,
    sensor_id TEXT NOT NULL,
    sensor_type TEXT, -- 'moisture', 'temperature', etc.
    linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (plant_id) REFERENCES plants(plant_id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_plant_sensor_plant ON plant_sensor_links(plant_id);
CREATE INDEX IF NOT EXISTS idx_plant_sensor_sensor ON plant_sensor_links(sensor_id);

-- Step 9: Add sample data for testing (OPTIONAL)
-- ============================================

-- Insert sample dimensions for existing units (if none exist)
UPDATE growth_units 
SET dimensions = '{"width": 120, "length": 180, "height": 80, "volume": 1728}'
WHERE dimensions IS NULL;

-- Step 10: Verification queries
-- ============================================

-- Verify migration success
SELECT 'Growth Units Count' as check_name, COUNT(*) as count FROM growth_units;
SELECT 'Units with User ID' as check_name, COUNT(*) as count FROM growth_units WHERE user_id IS NOT NULL;
SELECT 'Units with Dimensions' as check_name, COUNT(*) as count FROM growth_units WHERE dimensions IS NOT NULL;

-- Show updated table structure
PRAGMA table_info(growth_units);

-- Show indexes
SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='growth_units';

-- ============================================
-- ROLLBACK SCRIPT (if needed)
-- ============================================
-- Save this separately as rollback.sql

/*
-- Drop new tables
DROP TABLE IF EXISTS device_unit_links;
DROP TABLE IF EXISTS plant_sensor_links;

-- Drop indexes
DROP INDEX IF EXISTS idx_growth_units_user_id;
DROP INDEX IF EXISTS idx_growth_units_active;
DROP INDEX IF EXISTS idx_growth_units_user_active;

-- Recreate original growth_units table structure
CREATE TABLE growth_units_original (
    unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    location TEXT,
    is_active INTEGER DEFAULT 1,
    camera_active INTEGER DEFAULT 0
);

-- Copy data back (excluding new columns)
INSERT INTO growth_units_original (unit_id, name, location, is_active, camera_active)
SELECT unit_id, name, location, is_active, camera_active
FROM growth_units;

-- Replace table
DROP TABLE growth_units;
ALTER TABLE growth_units_original RENAME TO growth_units;
*/

-- ============================================
-- END OF MIGRATION SCRIPT
-- ============================================

-- Notes:
-- 1. Backup your database before running this script!
-- 2. Test on a copy first
-- 3. Adjust user_id default value (currently 1) as needed
-- 4. Some columns may already exist - comment out those ALTER statements
-- 5. Foreign keys require PRAGMA foreign_keys = ON;

-- Enable foreign keys (run this first!)
PRAGMA foreign_keys = ON;

-- Check current foreign key status
PRAGMA foreign_keys;
