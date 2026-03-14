-- Migration: Add Irrigation Workflow Tables
-- Description: Adds tables for irrigation standby/notification/approval workflow
-- Date: January 2026

-- =============================================================================
-- PendingIrrigationRequest Table
-- =============================================================================
-- Stores pending irrigation requests awaiting user approval or scheduled execution.
-- When soil moisture drops below threshold, instead of immediate irrigation,
-- a pending request is created and user is notified for approval.

CREATE TABLE IF NOT EXISTS PendingIrrigationRequest (
    request_id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    plant_id INTEGER,
    user_id INTEGER NOT NULL DEFAULT 1,

    -- Actuator to control
    actuator_id INTEGER,
    actuator_type TEXT DEFAULT 'water_pump',

    -- Sensor data at detection time
    soil_moisture_detected REAL NOT NULL,
    soil_moisture_threshold REAL NOT NULL,
    sensor_id INTEGER,

    -- Request status: 'pending', 'approved', 'delayed', 'executed', 'expired', 'cancelled'
    status TEXT NOT NULL DEFAULT 'pending',
    execution_status TEXT,
    claimed_at_utc TEXT,
    attempt_count INTEGER DEFAULT 0,
    last_attempt_at_utc TEXT,

    -- Scheduling
    detected_at TEXT NOT NULL,  -- When irrigation need was detected
    scheduled_time TEXT,         -- Default execution time (e.g., 21:00)
    delayed_until TEXT,          -- If user delayed, the new scheduled time
    expires_at TEXT,             -- When the request expires (e.g., 24h after detection)

    -- User response
    user_response TEXT,          -- 'approve', 'delay', 'cancel', 'auto' (no response)
    user_response_at TEXT,
    notification_id INTEGER,     -- Link to notification message

    -- Execution details
    executed_at TEXT,
    execution_duration_seconds INTEGER,
    soil_moisture_after REAL,
    execution_success INTEGER DEFAULT 0,
    execution_error TEXT,

    -- Feedback (post-irrigation)
    feedback_id INTEGER,         -- Link to IrrigationFeedback table
    feedback_requested_at TEXT,

    -- ML learning data
    ml_data_collected INTEGER DEFAULT 0,
    ml_preference_score REAL,    -- Learned preference: -1 (cancel) to +1 (immediate approve)
    temperature_at_detection REAL,
    humidity_at_detection REAL,
    vpd_at_detection REAL,
    lux_at_detection REAL,
    hours_since_last_irrigation REAL,
    plant_type TEXT,
    growth_stage TEXT,

    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT,

    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
    FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
    FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id),
    FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id),
    FOREIGN KEY (notification_id) REFERENCES NotificationMessage(message_id),
    FOREIGN KEY (feedback_id) REFERENCES IrrigationFeedback(feedback_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_pending_irrigation_unit ON PendingIrrigationRequest(unit_id);
CREATE INDEX IF NOT EXISTS idx_pending_irrigation_user ON PendingIrrigationRequest(user_id);
CREATE INDEX IF NOT EXISTS idx_pending_irrigation_status ON PendingIrrigationRequest(status);
CREATE INDEX IF NOT EXISTS idx_pending_irrigation_scheduled ON PendingIrrigationRequest(scheduled_time);
CREATE INDEX IF NOT EXISTS idx_pending_irrigation_detected ON PendingIrrigationRequest(detected_at);


-- =============================================================================
-- IrrigationWorkflowConfig Table
-- =============================================================================
-- Per-unit configuration for the irrigation workflow

CREATE TABLE IF NOT EXISTS IrrigationWorkflowConfig (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL UNIQUE,

    -- Workflow behavior
    workflow_enabled INTEGER NOT NULL DEFAULT 1,    -- Enable standby/approval workflow
    auto_irrigation_enabled INTEGER NOT NULL DEFAULT 0, -- Fallback to auto if no response
    manual_mode_enabled INTEGER NOT NULL DEFAULT 0, -- Skip auto checks, manual logging only
    require_approval INTEGER NOT NULL DEFAULT 1,    -- Require user approval before irrigation

    -- Scheduling defaults
    default_scheduled_time TEXT DEFAULT '21:00',    -- Default execution time (24h format)
    delay_increment_minutes INTEGER DEFAULT 60,     -- How much to delay when user clicks "delay"
    max_delay_hours INTEGER DEFAULT 24,             -- Maximum delay allowed
    expiration_hours INTEGER DEFAULT 48,            -- Request expires after this time

    -- Notification settings
    send_reminder_before_execution INTEGER DEFAULT 1, -- Send reminder N minutes before scheduled time
    reminder_minutes_before INTEGER DEFAULT 30,       -- Minutes before execution to send reminder

    -- Feedback collection
    request_feedback_enabled INTEGER DEFAULT 1,       -- Request feedback after irrigation
    feedback_delay_minutes INTEGER DEFAULT 30,        -- Wait N minutes after irrigation to request feedback

    -- ML learning
    ml_learning_enabled INTEGER DEFAULT 1,            -- Learn from user responses
    ml_threshold_adjustment_enabled INTEGER DEFAULT 0, -- Auto-adjust thresholds based on feedback
    ml_response_predictor_enabled INTEGER DEFAULT 0,
    ml_threshold_optimizer_enabled INTEGER DEFAULT 0,
    ml_duration_optimizer_enabled INTEGER DEFAULT 0,
    ml_timing_predictor_enabled INTEGER DEFAULT 0,
    ml_response_predictor_notified_at TEXT,
    ml_threshold_optimizer_notified_at TEXT,
    ml_duration_optimizer_notified_at TEXT,
    ml_timing_predictor_notified_at TEXT,

    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT,

    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_irrigation_workflow_config_unit ON IrrigationWorkflowConfig(unit_id);


-- =============================================================================
-- IrrigationUserPreference Table
-- =============================================================================
-- Tracks user preferences learned from responses (for ML)

CREATE TABLE IF NOT EXISTS IrrigationUserPreference (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    unit_id INTEGER,

    -- Time-based preferences
    preferred_irrigation_time TEXT,           -- Learned preferred time
    preferred_day_of_week INTEGER,            -- If user tends to approve on certain days

    -- Response patterns
    total_requests INTEGER DEFAULT 0,
    immediate_approvals INTEGER DEFAULT 0,
    delayed_approvals INTEGER DEFAULT 0,
    cancellations INTEGER DEFAULT 0,
    auto_executions INTEGER DEFAULT 0,        -- No response, auto-executed

    -- Calculated scores
    approval_rate REAL,                       -- (immediate + delayed) / total
    responsiveness_score REAL,                -- How quickly user responds
    avg_response_time_seconds REAL,

    -- Moisture preference (learned from feedback)
    preferred_moisture_threshold REAL,
    threshold_belief_json TEXT,
    threshold_variance REAL,
    threshold_sample_count INTEGER DEFAULT 0,
    moisture_feedback_count INTEGER DEFAULT 0,
    too_little_feedback_count INTEGER DEFAULT 0,
    just_right_feedback_count INTEGER DEFAULT 0,
    too_much_feedback_count INTEGER DEFAULT 0,

    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT,

    UNIQUE(user_id, unit_id),
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_irrigation_user_pref_user ON IrrigationUserPreference(user_id);
CREATE INDEX IF NOT EXISTS idx_irrigation_user_pref_unit ON IrrigationUserPreference(unit_id);


-- =============================================================================
-- IrrigationExecutionLog Table
-- =============================================================================
-- Stores execution telemetry for auditing and attribution.

CREATE TABLE IF NOT EXISTS IrrigationExecutionLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER,
    user_id INTEGER,
    unit_id INTEGER NOT NULL,
    plant_id INTEGER,
    sensor_id TEXT,
    trigger_reason TEXT NOT NULL,
    trigger_moisture REAL,
    threshold_at_trigger REAL,
    triggered_at_utc TEXT NOT NULL,
    planned_duration_s INTEGER,
    actual_duration_s INTEGER,
    pump_actuator_id TEXT,
    valve_actuator_id TEXT,
    assumed_flow_ml_s REAL,
    estimated_volume_ml REAL,
    execution_status TEXT NOT NULL,
    execution_error TEXT,
    executed_at_utc TEXT NOT NULL,
    post_moisture REAL,
    post_moisture_delay_s INTEGER,
    post_measured_at_utc TEXT,
    delta_moisture REAL,
    recommendation TEXT,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES PendingIrrigationRequest(request_id),
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
    FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
    FOREIGN KEY (user_id) REFERENCES Users(id)
);

CREATE INDEX IF NOT EXISTS idx_irrigation_execution_unit_time ON IrrigationExecutionLog(unit_id, executed_at_utc);
CREATE INDEX IF NOT EXISTS idx_irrigation_execution_plant_time ON IrrigationExecutionLog(plant_id, executed_at_utc);
CREATE INDEX IF NOT EXISTS idx_irrigation_execution_request ON IrrigationExecutionLog(request_id);


-- =============================================================================
-- IrrigationEligibilityTrace Table
-- =============================================================================
-- Records eligibility decisions and skip reasons.

CREATE TABLE IF NOT EXISTS IrrigationEligibilityTrace (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plant_id INTEGER,
    unit_id INTEGER NOT NULL,
    sensor_id TEXT,
    moisture REAL,
    threshold REAL,
    decision TEXT NOT NULL,
    skip_reason TEXT,
    evaluated_at_utc TEXT NOT NULL,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
    FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
);

CREATE INDEX IF NOT EXISTS idx_irrigation_eligibility_unit_time ON IrrigationEligibilityTrace(unit_id, evaluated_at_utc);
CREATE INDEX IF NOT EXISTS idx_irrigation_eligibility_plant_time ON IrrigationEligibilityTrace(plant_id, evaluated_at_utc);


-- =============================================================================
-- ManualIrrigationLog Table
-- =============================================================================
-- Manual watering events for sensor-only units.

CREATE TABLE IF NOT EXISTS ManualIrrigationLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    unit_id INTEGER NOT NULL,
    plant_id INTEGER NOT NULL,
    watered_at_utc TEXT NOT NULL,
    amount_ml REAL,
    notes TEXT,
    pre_moisture REAL,
    pre_moisture_at_utc TEXT,
    post_moisture REAL,
    post_moisture_at_utc TEXT,
    settle_delay_min INTEGER DEFAULT 15,
    delta_moisture REAL,
    created_at_utc TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES Users(id),
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
    FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
);

CREATE INDEX IF NOT EXISTS idx_manual_irrigation_plant_time ON ManualIrrigationLog(plant_id, watered_at_utc);


-- =============================================================================
-- PlantIrrigationModel Table
-- =============================================================================
-- Stores per-plant dry-down learning state.

CREATE TABLE IF NOT EXISTS PlantIrrigationModel (
    plant_id INTEGER PRIMARY KEY,
    drydown_rate_per_hour REAL,
    sample_count INTEGER DEFAULT 0,
    confidence REAL,
    updated_at_utc TEXT NOT NULL,
    FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
);


-- =============================================================================
-- IrrigationLock Table
-- =============================================================================
-- Unit-level lock to prevent concurrent irrigation execution.

CREATE TABLE IF NOT EXISTS IrrigationLock (
    unit_id INTEGER PRIMARY KEY,
    locked_until_utc TEXT NOT NULL,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
);
