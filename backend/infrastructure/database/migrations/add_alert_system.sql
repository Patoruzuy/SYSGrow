-- Migration: Add alerts and notification system
-- Date: 2024
-- Description: Creates Alert table for tracking system alerts and notifications

CREATE TABLE IF NOT EXISTS Alert (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    alert_type TEXT NOT NULL CHECK(alert_type IN (
        'device_offline', 'device_malfunction',
        'sensor_anomaly', 'actuator_failure',
        'threshold_exceeded', 'plant_health_warning',
        'low_battery', 'connection_lost',
        'system_error', 'maintenance_required',
        'harvest_ready', 'water_low'
    )),
    severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'critical')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    source_type TEXT,
    source_id INTEGER,
    unit_id INTEGER,
    acknowledged BOOLEAN DEFAULT 0,
    acknowledged_at DATETIME,
    acknowledged_by INTEGER,
    resolved BOOLEAN DEFAULT 0,
    resolved_at DATETIME,
    metadata TEXT,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE,
    FOREIGN KEY (acknowledged_by) REFERENCES Users(id) ON DELETE SET NULL
);

-- Index for efficient querying of active alerts
CREATE INDEX IF NOT EXISTS idx_alert_active ON Alert(resolved, acknowledged, severity, timestamp DESC);

-- Index for alert type filtering
CREATE INDEX IF NOT EXISTS idx_alert_type ON Alert(alert_type);

-- Index for unit-specific alerts
CREATE INDEX IF NOT EXISTS idx_alert_unit ON Alert(unit_id);

-- Index for source lookups
CREATE INDEX IF NOT EXISTS idx_alert_source ON Alert(source_type, source_id);

-- Index for timestamp-based queries
CREATE INDEX IF NOT EXISTS idx_alert_timestamp ON Alert(timestamp DESC);
