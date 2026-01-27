-- Migration: Clean up old camera implementation
-- Date: 2025-12-20
-- Description: Removes obsolete CameraSettings table and deprecates old camera columns

-- ============================================
-- Step 1: Drop old CameraSettings table
-- ============================================
-- This table stored global camera settings
-- Now replaced by per-unit camera_configs table

DROP TABLE IF EXISTS CameraSettings;

-- ============================================
-- Step 2: Add notes about deprecated columns
-- ============================================
-- The following columns in GrowthUnits are kept for backward compatibility
-- but are no longer actively used:
-- - camera_enabled (INT) - Replaced by camera_configs table entries
-- - camera_active (INT) - No longer used, camera state tracked in CameraService

-- To fully deprecate (optional, future migration):
-- ALTER TABLE GrowthUnits DROP COLUMN camera_enabled;
-- ALTER TABLE GrowthUnits DROP COLUMN camera_active;

-- ============================================
-- Step 3: Verify new camera_configs table exists
-- ============================================
-- This ensures the migration can only run if the new table is in place

SELECT COUNT(*) as table_check FROM camera_configs LIMIT 1;

-- ============================================
-- Notes:
-- ============================================
-- 1. CameraSettings table is completely removed
-- 2. camera_enabled and camera_active columns remain for backward compatibility
-- 3. All new camera functionality uses camera_configs table
-- 4. SettingsRepository and SettingsOperations camera methods are now obsolete
