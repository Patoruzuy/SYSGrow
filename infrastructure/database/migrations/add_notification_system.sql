-- Migration: Add notification settings and messages
-- Date: January 2026
-- Description: Creates tables for user notification preferences and message tracking

-- User Notification Preferences
CREATE TABLE IF NOT EXISTS NotificationSettings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,

    -- Notification channels
    email_enabled BOOLEAN DEFAULT 0,
    in_app_enabled BOOLEAN DEFAULT 1,

    -- Email configuration (optional SMTP settings)
    email_address TEXT,
    smtp_host TEXT,
    smtp_port INTEGER DEFAULT 587,
    smtp_username TEXT,
    smtp_password_encrypted TEXT,
    smtp_use_tls BOOLEAN DEFAULT 1,

    -- Alert type preferences (what to notify about)
    notify_low_battery BOOLEAN DEFAULT 1,
    notify_plant_needs_water BOOLEAN DEFAULT 1,
    notify_irrigation_confirm BOOLEAN DEFAULT 1,
    notify_threshold_exceeded BOOLEAN DEFAULT 1,
    notify_device_offline BOOLEAN DEFAULT 1,
    notify_harvest_ready BOOLEAN DEFAULT 1,
    notify_plant_health_warning BOOLEAN DEFAULT 1,

    -- Irrigation feedback preferences
    irrigation_feedback_enabled BOOLEAN DEFAULT 1,
    irrigation_feedback_delay_minutes INTEGER DEFAULT 30,

    -- Quiet hours (don't send notifications)
    quiet_hours_enabled BOOLEAN DEFAULT 0,
    quiet_hours_start TIME,
    quiet_hours_end TIME,

    -- Throttling
    min_notification_interval_seconds INTEGER DEFAULT 300,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
    UNIQUE(user_id)
);

-- Notification Messages (history/queue)
CREATE TABLE IF NOT EXISTS NotificationMessage (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,

    -- Message content
    notification_type TEXT NOT NULL CHECK(notification_type IN (
        'low_battery', 'plant_needs_water', 'irrigation_confirm',
        'irrigation_feedback', 'threshold_exceeded', 'device_offline',
        'harvest_ready', 'plant_health_warning', 'system_alert'
    )),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'critical')),

    -- Source context
    source_type TEXT,
    source_id INTEGER,
    unit_id INTEGER,

    -- Delivery status
    channel TEXT NOT NULL CHECK(channel IN ('email', 'in_app', 'both')),
    email_sent BOOLEAN DEFAULT 0,
    email_sent_at TIMESTAMP,
    email_error TEXT,
    in_app_sent BOOLEAN DEFAULT 0,
    in_app_read BOOLEAN DEFAULT 0,
    in_app_read_at TIMESTAMP,

    -- Action handling (for irrigation confirmation/feedback)
    requires_action BOOLEAN DEFAULT 0,
    action_type TEXT,
    action_data TEXT,
    action_taken BOOLEAN DEFAULT 0,
    action_response TEXT,
    action_taken_at TIMESTAMP,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE SET NULL
);

-- Irrigation Feedback Records (learning from user feedback)
CREATE TABLE IF NOT EXISTS IrrigationFeedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    unit_id INTEGER NOT NULL,
    plant_id INTEGER,

    -- Context at irrigation time
    soil_moisture_before REAL,
    soil_moisture_after REAL,
    irrigation_duration_seconds INTEGER,
    actuator_id INTEGER,

    -- User feedback
    feedback_response TEXT CHECK(feedback_response IN (
        'too_little', 'just_right', 'too_much',
        'triggered_too_early', 'triggered_too_late',
        'skipped'
    )),
    feedback_notes TEXT,

    -- Threshold adjustment suggestion
    suggested_threshold_adjustment REAL,
    threshold_adjustment_applied BOOLEAN DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE,
    FOREIGN KEY (plant_id) REFERENCES Plants(plant_id) ON DELETE SET NULL,
    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE SET NULL
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_notification_settings_user ON NotificationSettings(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_message_user ON NotificationMessage(user_id);
CREATE INDEX IF NOT EXISTS idx_notification_message_unread ON NotificationMessage(user_id, in_app_read, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notification_message_action ON NotificationMessage(requires_action, action_taken, user_id);
CREATE INDEX IF NOT EXISTS idx_notification_message_type ON NotificationMessage(notification_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_irrigation_feedback_unit ON IrrigationFeedback(unit_id, created_at DESC);
