-- Migration: Add activity logging system
-- Date: 2024
-- Description: Creates ActivityLog table for tracking system events and user actions

CREATE TABLE IF NOT EXISTS ActivityLog (
    activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    activity_type TEXT NOT NULL CHECK(activity_type IN (
        'plant_added', 'plant_removed', 'plant_updated',
        'unit_created', 'unit_updated', 'unit_deleted',
        'device_connected', 'device_disconnected', 'device_configured',
        'sensor_reading', 'actuator_triggered',
        'harvest_recorded', 'harvest_updated',
        'threshold_override', 'manual_control',
        'system_startup', 'system_shutdown',
        'user_login', 'user_logout'
    )),
    severity TEXT NOT NULL DEFAULT 'info' CHECK(severity IN ('info', 'warning', 'error')),
    entity_type TEXT,
    entity_id INTEGER,
    description TEXT NOT NULL,
    metadata TEXT,
    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE SET NULL
);

-- Index for efficient querying by timestamp
CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON ActivityLog(timestamp DESC);

-- Index for filtering by activity type
CREATE INDEX IF NOT EXISTS idx_activity_type ON ActivityLog(activity_type);

-- Index for filtering by user
CREATE INDEX IF NOT EXISTS idx_activity_user ON ActivityLog(user_id);

-- Index for entity lookups
CREATE INDEX IF NOT EXISTS idx_activity_entity ON ActivityLog(entity_type, entity_id);
