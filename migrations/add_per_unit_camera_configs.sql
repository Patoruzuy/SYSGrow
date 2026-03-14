-- Migration: Add per-unit camera configuration support
-- Date: 2025-12-20
-- Description: Creates camera_configs table to support multiple cameras per growth unit

-- ============================================
-- Step 1: Create camera_configs table
-- ============================================
-- This table stores camera configuration for each growth unit
-- Replaces the global camera settings approach

CREATE TABLE IF NOT EXISTS camera_configs (
    camera_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    camera_type TEXT NOT NULL CHECK(camera_type IN ('esp32', 'usb')),
    ip_address TEXT,  -- Required for ESP32 cameras
    port INTEGER DEFAULT 81,  -- Port for ESP32 stream
    device_index INTEGER,  -- USB camera device index (0, 1, etc.)
    resolution TEXT DEFAULT '640x480',
    quality INTEGER DEFAULT 10,  -- JPEG quality (0-63, lower is better)
    brightness INTEGER DEFAULT 0,  -- Brightness (-2 to 2)
    contrast INTEGER DEFAULT 0,  -- Contrast (-2 to 2)
    saturation INTEGER DEFAULT 0,  -- Saturation (-2 to 2)
    flip INTEGER DEFAULT 0,  -- Flip mode (0=normal, 1=horizontal, 2=vertical, 3=both)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure one camera config per unit
    UNIQUE(unit_id),
    
    -- Foreign key to growth units
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE
);

-- ============================================
-- Step 2: Create index for performance
-- ============================================
CREATE INDEX IF NOT EXISTS idx_camera_configs_unit_id ON camera_configs(unit_id);

-- ============================================
-- Step 3: Migrate existing data (if applicable)
-- ============================================
-- If there are existing camera_enabled units, create default configs
-- This assumes ESP32 cameras with default settings

INSERT INTO camera_configs (unit_id, camera_type, ip_address, port)
SELECT 
    unit_id,
    'esp32' as camera_type,
    '192.168.1.100' as ip_address,  -- Default IP, should be updated
    81 as port
FROM GrowthUnits
WHERE camera_enabled = 1
AND unit_id NOT IN (SELECT unit_id FROM camera_configs);

-- ============================================
-- Step 4: Add trigger to update timestamp
-- ============================================
CREATE TRIGGER IF NOT EXISTS update_camera_config_timestamp 
AFTER UPDATE ON camera_configs
BEGIN
    UPDATE camera_configs SET updated_at = CURRENT_TIMESTAMP WHERE camera_id = NEW.camera_id;
END;

-- ============================================
-- Notes:
-- ============================================
-- 1. The camera_enabled column in GrowthUnits is kept for backward compatibility
-- 2. If a unit has camera_enabled=1 but no camera_configs entry, the system will use defaults
-- 3. Multiple units can now have their own independent cameras
-- 4. ESP32 cameras require ip_address, USB cameras require device_index
