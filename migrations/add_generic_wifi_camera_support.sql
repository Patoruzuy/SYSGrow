-- Migration: Add support for generic WiFi cameras
-- Date: 2025-12-20
-- Description: Extends camera_configs to support RTSP and generic MJPEG streams

-- ============================================
-- Step 1: Update camera_type constraint
-- ============================================
-- Recreate the table with expanded camera type options

-- Backup existing data
CREATE TEMP TABLE camera_configs_backup AS SELECT * FROM camera_configs;

-- Drop old table
DROP TABLE camera_configs;

-- Recreate with new constraints
CREATE TABLE camera_configs (
    camera_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    camera_type TEXT NOT NULL CHECK(camera_type IN ('esp32', 'usb', 'rtsp', 'mjpeg', 'http')),
    stream_url TEXT,  -- Full URL for RTSP, MJPEG, or HTTP streams
    ip_address TEXT,  -- For ESP32 cameras (backward compatibility)
    port INTEGER DEFAULT 81,  -- Port for ESP32 stream
    device_index INTEGER,  -- USB camera device index (0, 1, etc.)
    username TEXT,  -- Authentication for WiFi cameras
    password TEXT,  -- Authentication for WiFi cameras (should be encrypted)
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

-- Restore data with new columns
INSERT INTO camera_configs (
    camera_id, unit_id, camera_type, ip_address, port, device_index, 
    resolution, quality, brightness, contrast, saturation, flip, 
    created_at, updated_at
)
SELECT 
    camera_id, unit_id, camera_type, ip_address, port, device_index, 
    resolution, quality, brightness, contrast, saturation, flip, 
    created_at, updated_at
FROM camera_configs_backup;

-- Clean up
DROP TABLE camera_configs_backup;

-- ============================================
-- Step 2: Recreate index
-- ============================================
CREATE INDEX IF NOT EXISTS idx_camera_configs_unit_id ON camera_configs(unit_id);

-- ============================================
-- Step 3: Recreate trigger
-- ============================================
CREATE TRIGGER IF NOT EXISTS update_camera_config_timestamp 
AFTER UPDATE ON camera_configs
BEGIN
    UPDATE camera_configs SET updated_at = CURRENT_TIMESTAMP WHERE camera_id = NEW.camera_id;
END;

-- ============================================
-- Notes:
-- ============================================
-- Camera types now supported:
-- - 'esp32': ESP32-CAM with MJPEG stream (uses ip_address + port)
-- - 'usb': USB camera connected to server (uses device_index)
-- - 'rtsp': RTSP stream (uses stream_url, username, password)
-- - 'mjpeg': Generic MJPEG stream (uses stream_url, username, password)
-- - 'http': Generic HTTP/HTTPS stream (uses stream_url, username, password)
--
-- Examples:
-- - ESP32: camera_type='esp32', ip_address='192.168.1.100', port=81
-- - USB: camera_type='usb', device_index=0
-- - RTSP: camera_type='rtsp', stream_url='rtsp://192.168.1.50:554/stream'
-- - MJPEG: camera_type='mjpeg', stream_url='http://192.168.1.51/mjpeg/1'
-- - Generic: camera_type='http', stream_url='http://camera.local/video'
