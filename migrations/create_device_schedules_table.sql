-- Migration: Create DeviceSchedules table for centralized scheduling
-- Date: January 2026
-- Description: Creates the DeviceSchedules table to support multiple schedules per device type

CREATE TABLE IF NOT EXISTS DeviceSchedules (
    schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    name TEXT DEFAULT '',
    device_type TEXT NOT NULL,
    actuator_id INTEGER,
    schedule_type TEXT NOT NULL DEFAULT 'simple',
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    interval_minutes INTEGER,
    duration_minutes INTEGER,
    days_of_week TEXT DEFAULT '[0,1,2,3,4,5,6]',
    enabled BOOLEAN DEFAULT 1,
    state_when_active TEXT DEFAULT 'on',
    value REAL,
    photoperiod_config TEXT,
    priority INTEGER DEFAULT 0,
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE,
    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE SET NULL
);

-- Indexes for DeviceSchedules
CREATE INDEX IF NOT EXISTS idx_device_schedules_unit ON DeviceSchedules(unit_id);
CREATE INDEX IF NOT EXISTS idx_device_schedules_device_type ON DeviceSchedules(unit_id, device_type);
CREATE INDEX IF NOT EXISTS idx_device_schedules_actuator ON DeviceSchedules(actuator_id);
CREATE INDEX IF NOT EXISTS idx_device_schedules_enabled ON DeviceSchedules(unit_id, enabled);
