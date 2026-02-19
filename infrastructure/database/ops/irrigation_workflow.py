"""Database operations for Irrigation Workflow entities."""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from datetime import timedelta
from typing import Any

from app.utils.time import coerce_datetime, iso_now, utc_now
from infrastructure.database.sql_safety import build_insert_parts, build_set_clause, safe_columns

logger = logging.getLogger(__name__)

# Columns that may be written via upsert_workflow_config.
_WORKFLOW_CONFIG_COLUMNS: frozenset[str] = frozenset(
    {
        "workflow_enabled",
        "auto_irrigation_enabled",
        "manual_mode_enabled",
        "require_approval",
        "default_scheduled_time",
        "delay_increment_minutes",
        "max_delay_hours",
        "expiration_hours",
        "send_reminder_before_execution",
        "reminder_minutes_before",
        "request_feedback_enabled",
        "feedback_delay_minutes",
        "ml_learning_enabled",
        "ml_threshold_adjustment_enabled",
        "ml_response_predictor_enabled",
        "ml_threshold_optimizer_enabled",
        "ml_duration_optimizer_enabled",
        "ml_timing_predictor_enabled",
        "ml_response_predictor_notified_at",
        "ml_threshold_optimizer_notified_at",
        "ml_duration_optimizer_notified_at",
        "ml_timing_predictor_notified_at",
    }
)


class IrrigationWorkflowOperations:
    """Database operations for irrigation workflow management."""

    # ========== PendingIrrigationRequest Operations ==========

    def create_pending_irrigation_request(
        self,
        unit_id: int,
        soil_moisture_detected: float,
        soil_moisture_threshold: float,
        user_id: int = 1,
        plant_id: int | None = None,
        actuator_id: int | None = None,
        actuator_type: str = "water_pump",
        sensor_id: int | None = None,
        scheduled_time: str | None = None,
        expires_at: str | None = None,
        # ML context fields (Phase 1)
        temperature_at_detection: float | None = None,
        humidity_at_detection: float | None = None,
        vpd_at_detection: float | None = None,
        lux_at_detection: float | None = None,
        hours_since_last_irrigation: float | None = None,
        plant_type: str | None = None,
        growth_stage: str | None = None,
    ) -> int | None:
        """Create a new pending irrigation request with ML context."""
        try:
            db = self.get_db()
            cur = db.cursor()
            now = iso_now()
            cur.execute(
                """
                INSERT INTO PendingIrrigationRequest (
                    unit_id, plant_id, user_id, actuator_id, actuator_type,
                    soil_moisture_detected, soil_moisture_threshold, sensor_id,
                    status, detected_at, scheduled_time, expires_at,
                    temperature_at_detection, humidity_at_detection, vpd_at_detection,
                    lux_at_detection, hours_since_last_irrigation,
                    plant_type, growth_stage, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unit_id,
                    plant_id,
                    user_id,
                    actuator_id,
                    actuator_type,
                    soil_moisture_detected,
                    soil_moisture_threshold,
                    sensor_id,
                    now,
                    scheduled_time,
                    expires_at,
                    temperature_at_detection,
                    humidity_at_detection,
                    vpd_at_detection,
                    lux_at_detection,
                    hours_since_last_irrigation,
                    plant_type,
                    growth_stage,
                    now,
                    now,
                ),
            )
            request_id = cur.lastrowid
            db.commit()
            logger.info(f"Created pending irrigation request: {request_id}")
            return request_id
        except sqlite3.Error as exc:
            logger.error(f"Failed to create pending irrigation request: {exc}")
            return None

    def get_pending_irrigation_request(self, request_id: int) -> dict[str, Any] | None:
        """Get a pending irrigation request by ID."""
        try:
            db = self.get_db()
            cur = db.execute("SELECT * FROM PendingIrrigationRequest WHERE request_id = ?", (request_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error(f"Failed to get pending irrigation request: {exc}")
            return None

    def get_pending_requests_for_unit(
        self,
        unit_id: int,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get pending irrigation requests for a unit."""
        try:
            db = self.get_db()
            query = "SELECT * FROM PendingIrrigationRequest WHERE unit_id = ?"
            params: list[Any] = [unit_id]

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY detected_at DESC"
            cur = db.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to get pending requests for unit: {exc}")
            return []

    def get_pending_requests_for_user(
        self,
        user_id: int,
        status: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get pending irrigation requests for a user."""
        try:
            db = self.get_db()
            query = "SELECT * FROM PendingIrrigationRequest WHERE user_id = ?"
            params: list[Any] = [user_id]

            if status:
                query += " AND status = ?"
                params.append(status)

            query += " ORDER BY detected_at DESC LIMIT ?"
            params.append(limit)

            cur = db.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to get pending requests for user: {exc}")
            return []

    def get_requests_due_for_execution(
        self,
        current_time: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get requests that are due for execution (scheduled_time <= now)."""
        try:
            db = self.get_db()
            now = current_time or iso_now()

            # Get requests that are pending/approved and scheduled time has passed
            cur = db.execute(
                """
                SELECT * FROM PendingIrrigationRequest
                WHERE status IN ('pending', 'approved', 'delayed')
                  AND (
                      (scheduled_time IS NOT NULL AND scheduled_time <= ?)
                      OR (delayed_until IS NOT NULL AND delayed_until <= ?)
                  )
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY scheduled_time ASC
                """,
                (now, now, now),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to get requests due for execution: {exc}")
            return []

    def claim_due_requests(
        self,
        current_time: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Atomically claim due requests for execution."""
        db = None
        try:
            db = self.get_db()
            now = current_time or iso_now()
            cur = db.cursor()
            cur.execute("BEGIN IMMEDIATE")
            cur.execute(
                """
                SELECT request_id FROM PendingIrrigationRequest
                WHERE status IN ('pending', 'approved', 'delayed')
                  AND (
                      (scheduled_time IS NOT NULL AND scheduled_time <= ?)
                      OR (delayed_until IS NOT NULL AND delayed_until <= ?)
                  )
                  AND (expires_at IS NULL OR expires_at > ?)
                  AND claimed_at_utc IS NULL
                ORDER BY scheduled_time ASC
                LIMIT ?
                """,
                (now, now, now, limit),
            )
            request_ids = [row[0] for row in cur.fetchall()]
            if not request_ids:
                db.commit()
                return []

            placeholders = ",".join("?" for _ in request_ids)  # nosec B608 — only '?' chars
            params = [now, now, "executing", now, *request_ids]
            cur.execute(
                f"""
                UPDATE PendingIrrigationRequest
                SET claimed_at_utc = ?,
                    last_attempt_at_utc = ?,
                    execution_status = ?,
                    attempt_count = COALESCE(attempt_count, 0) + 1,
                    updated_at = ?
                WHERE request_id IN ({placeholders})
                """,  # nosec B608
                params,
            )
            cur.execute(
                f"SELECT * FROM PendingIrrigationRequest WHERE request_id IN ({placeholders})",  # nosec B608
                request_ids,
            )
            rows = cur.fetchall()
            db.commit()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logger.error(f"Failed to claim due requests: {exc}")
            if db is not None:
                with contextlib.suppress(Exception):
                    db.rollback()
            return []

    def mark_execution_started(
        self,
        request_id: int,
        started_at_utc: str,
        planned_duration_seconds: int,
    ) -> bool:
        """Mark an irrigation request as executing with planned duration."""
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE PendingIrrigationRequest
                SET execution_status = ?,
                    last_attempt_at_utc = ?,
                    execution_duration_seconds = ?,
                    updated_at = ?
                WHERE request_id = ?
                """,
                ("executing", started_at_utc, planned_duration_seconds, started_at_utc, request_id),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to mark execution started: {exc}")
            return False

    def get_executing_requests(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get requests currently executing."""
        try:
            db = self.get_db()
            cur = db.execute(
                """
                SELECT * FROM PendingIrrigationRequest
                WHERE execution_status = 'executing'
                  AND execution_duration_seconds IS NOT NULL
                  AND last_attempt_at_utc IS NOT NULL
                ORDER BY last_attempt_at_utc ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to get executing requests: {exc}")
            return []

    def create_execution_log(
        self,
        *,
        request_id: int | None,
        user_id: int | None,
        unit_id: int,
        plant_id: int | None,
        sensor_id: str | None,
        trigger_reason: str,
        trigger_moisture: float | None,
        threshold_at_trigger: float | None,
        triggered_at_utc: str,
        planned_duration_s: int | None,
        pump_actuator_id: str | None,
        valve_actuator_id: str | None,
        assumed_flow_ml_s: float | None,
        estimated_volume_ml: float | None,
        execution_status: str,
        execution_error: str | None,
        executed_at_utc: str,
        post_moisture_delay_s: int | None,
        created_at_utc: str | None = None,
    ) -> int | None:
        """Create a new irrigation execution log entry."""
        try:
            db = self.get_db()
            now = created_at_utc or iso_now()
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO IrrigationExecutionLog (
                    request_id, user_id, unit_id, plant_id, sensor_id,
                    trigger_reason, trigger_moisture, threshold_at_trigger,
                    triggered_at_utc, planned_duration_s,
                    pump_actuator_id, valve_actuator_id,
                    assumed_flow_ml_s, estimated_volume_ml,
                    execution_status, execution_error,
                    executed_at_utc, post_moisture_delay_s, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    user_id,
                    unit_id,
                    plant_id,
                    sensor_id,
                    trigger_reason,
                    trigger_moisture,
                    threshold_at_trigger,
                    triggered_at_utc,
                    planned_duration_s,
                    pump_actuator_id,
                    valve_actuator_id,
                    assumed_flow_ml_s,
                    estimated_volume_ml,
                    execution_status,
                    execution_error,
                    executed_at_utc,
                    post_moisture_delay_s,
                    now,
                ),
            )
            log_id = cur.lastrowid
            db.commit()
            return log_id
        except sqlite3.Error as exc:
            logger.error(f"Failed to create irrigation execution log: {exc}")
            return None

    def update_execution_log_status(
        self,
        request_id: int,
        *,
        execution_status: str,
        actual_duration_s: int | None = None,
        estimated_volume_ml: float | None = None,
        execution_error: str | None = None,
    ) -> bool:
        """Update execution log status for the most recent request log."""
        try:
            updates = ["execution_status = ?"]
            params: list[Any] = [execution_status]

            if actual_duration_s is not None:
                updates.append("actual_duration_s = ?")
                params.append(actual_duration_s)
            if estimated_volume_ml is not None:
                updates.append("estimated_volume_ml = ?")
                params.append(estimated_volume_ml)
            if execution_error is not None:
                updates.append("execution_error = ?")
                params.append(execution_error)

            params.append(request_id)

            db = self.get_db()
            db.execute(
                f"""
                UPDATE IrrigationExecutionLog
                SET {", ".join(updates)}
                WHERE id = (
                    SELECT id FROM IrrigationExecutionLog
                    WHERE request_id = ?
                    ORDER BY id DESC
                    LIMIT 1
                )
                """,  # nosec B608 — updates list built from hardcoded column names above
                params,
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to update irrigation execution log: {exc}")
            return False

    def get_latest_execution_log_for_request(
        self,
        request_id: int,
    ) -> dict[str, Any] | None:
        """Get the most recent execution log for a request."""
        try:
            db = self.get_db()
            cur = db.execute(
                """
                SELECT * FROM IrrigationExecutionLog
                WHERE request_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (request_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error(f"Failed to get execution log for request {request_id}: {exc}")
            return None

    def get_execution_logs_pending_post_capture(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get completed execution logs pending post-watering moisture capture."""
        try:
            db = self.get_db()
            cur = db.execute(
                """
                SELECT * FROM IrrigationExecutionLog
                WHERE execution_status = 'completed'
                  AND post_moisture IS NULL
                ORDER BY executed_at_utc ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to get pending post-capture logs: {exc}")
            return []

    def update_execution_log_post_moisture(
        self,
        log_id: int,
        *,
        post_moisture: float,
        post_measured_at_utc: str,
        delta_moisture: float | None,
        recommendation: str | None,
    ) -> bool:
        """Update a log entry with post-watering moisture data."""
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE IrrigationExecutionLog
                SET post_moisture = ?,
                    post_measured_at_utc = ?,
                    delta_moisture = ?,
                    recommendation = ?
                WHERE id = ?
                """,
                (post_moisture, post_measured_at_utc, delta_moisture, recommendation, log_id),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to update post-watering moisture log: {exc}")
            return False

    def create_eligibility_trace(
        self,
        *,
        plant_id: int | None,
        unit_id: int,
        sensor_id: str | None,
        moisture: float | None,
        threshold: float | None,
        decision: str,
        skip_reason: str | None,
        evaluated_at_utc: str,
    ) -> int | None:
        """Create an irrigation eligibility trace entry."""
        try:
            db = self.get_db()
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO IrrigationEligibilityTrace (
                    plant_id, unit_id, sensor_id, moisture, threshold,
                    decision, skip_reason, evaluated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plant_id,
                    unit_id,
                    sensor_id,
                    moisture,
                    threshold,
                    decision,
                    skip_reason,
                    evaluated_at_utc,
                ),
            )
            trace_id = cur.lastrowid
            db.commit()
            return trace_id
        except sqlite3.Error as exc:
            logger.error(f"Failed to create irrigation eligibility trace: {exc}")
            return None

    def create_manual_irrigation_log(
        self,
        *,
        user_id: int,
        unit_id: int,
        plant_id: int,
        watered_at_utc: str,
        amount_ml: float | None,
        notes: str | None,
        pre_moisture: float | None,
        pre_moisture_at_utc: str | None,
        settle_delay_min: int,
        created_at_utc: str | None = None,
    ) -> int | None:
        """Create a manual irrigation log entry."""
        try:
            db = self.get_db()
            now = created_at_utc or iso_now()
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO ManualIrrigationLog (
                    user_id, unit_id, plant_id, watered_at_utc, amount_ml, notes,
                    pre_moisture, pre_moisture_at_utc, settle_delay_min, created_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    unit_id,
                    plant_id,
                    watered_at_utc,
                    amount_ml,
                    notes,
                    pre_moisture,
                    pre_moisture_at_utc,
                    settle_delay_min,
                    now,
                ),
            )
            log_id = cur.lastrowid
            db.commit()
            return log_id
        except sqlite3.Error as exc:
            logger.error(f"Failed to create manual irrigation log: {exc}")
            return None

    def get_manual_logs_pending_post_capture(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get manual irrigation logs pending post-watering capture."""
        try:
            db = self.get_db()
            cur = db.execute(
                """
                SELECT * FROM ManualIrrigationLog
                WHERE post_moisture IS NULL
                ORDER BY watered_at_utc ASC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to get pending manual irrigation logs: {exc}")
            return []

    def update_manual_log_post_moisture(
        self,
        log_id: int,
        *,
        post_moisture: float,
        post_moisture_at_utc: str,
        delta_moisture: float | None,
    ) -> bool:
        """Update a manual irrigation log with post-watering moisture."""
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE ManualIrrigationLog
                SET post_moisture = ?,
                    post_moisture_at_utc = ?,
                    delta_moisture = ?
                WHERE id = ?
                """,
                (post_moisture, post_moisture_at_utc, delta_moisture, log_id),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to update manual irrigation log: {exc}")
            return False

    def get_manual_logs_for_plant(
        self,
        plant_id: int,
        *,
        start_ts: str,
        end_ts: str,
    ) -> list[dict[str, Any]]:
        """Fetch manual irrigation logs for a plant within a time window."""
        try:
            db = self.get_db()
            cur = db.execute(
                """
                SELECT watered_at_utc, settle_delay_min
                FROM ManualIrrigationLog
                WHERE plant_id = ?
                  AND watered_at_utc >= ?
                  AND watered_at_utc <= ?
                ORDER BY watered_at_utc ASC
                """,
                (plant_id, start_ts, end_ts),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to fetch manual logs for plant {plant_id}: {exc}")
            return []

    def get_execution_logs_for_plant(
        self,
        plant_id: int,
        *,
        start_ts: str,
        end_ts: str,
    ) -> list[dict[str, Any]]:
        """Fetch irrigation execution logs for a plant within a time window."""
        try:
            db = self.get_db()
            cur = db.execute(
                """
                SELECT executed_at_utc, actual_duration_s, planned_duration_s, post_moisture_delay_s
                FROM IrrigationExecutionLog
                WHERE plant_id = ?
                  AND executed_at_utc >= ?
                  AND executed_at_utc <= ?
                ORDER BY executed_at_utc ASC
                """,
                (plant_id, start_ts, end_ts),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to fetch execution logs for plant {plant_id}: {exc}")
            return []

    def get_execution_logs_for_unit(
        self,
        unit_id: int,
        *,
        start_ts: str,
        end_ts: str,
        limit: int = 200,
        plant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch irrigation execution logs for a unit within a time window."""
        try:
            db = self.get_db()
            query = """
                SELECT *
                FROM IrrigationExecutionLog
                WHERE unit_id = ?
                  AND executed_at_utc >= ?
                  AND executed_at_utc <= ?
                """
            params: list[Any] = [unit_id, start_ts, end_ts]
            if plant_id is not None:
                query += " AND plant_id = ?"
                params.append(plant_id)
            query += " ORDER BY executed_at_utc DESC LIMIT ?"
            params.append(limit)
            cur = db.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to fetch execution logs for unit {unit_id}: {exc}")
            return []

    def get_eligibility_traces_for_unit(
        self,
        unit_id: int,
        *,
        start_ts: str,
        end_ts: str,
        limit: int = 200,
        plant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch irrigation eligibility traces for a unit within a time window."""
        try:
            db = self.get_db()
            query = """
                SELECT *
                FROM IrrigationEligibilityTrace
                WHERE unit_id = ?
                  AND evaluated_at_utc >= ?
                  AND evaluated_at_utc <= ?
                """
            params: list[Any] = [unit_id, start_ts, end_ts]
            if plant_id is not None:
                query += " AND plant_id = ?"
                params.append(plant_id)
            query += " ORDER BY evaluated_at_utc DESC LIMIT ?"
            params.append(limit)
            cur = db.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to fetch eligibility traces for unit {unit_id}: {exc}")
            return []

    def get_manual_logs_for_unit(
        self,
        unit_id: int,
        *,
        start_ts: str,
        end_ts: str,
        limit: int = 200,
        plant_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch manual irrigation logs for a unit within a time window."""
        try:
            db = self.get_db()
            query = """
                SELECT *
                FROM ManualIrrigationLog
                WHERE unit_id = ?
                  AND watered_at_utc >= ?
                  AND watered_at_utc <= ?
                """
            params: list[Any] = [unit_id, start_ts, end_ts]
            if plant_id is not None:
                query += " AND plant_id = ?"
                params.append(plant_id)
            query += " ORDER BY watered_at_utc DESC LIMIT ?"
            params.append(limit)
            cur = db.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to fetch manual logs for unit {unit_id}: {exc}")
            return []

    def get_plant_irrigation_model(self, plant_id: int) -> dict[str, Any] | None:
        """Fetch stored irrigation model for a plant."""
        try:
            db = self.get_db()
            cur = db.execute(
                "SELECT * FROM PlantIrrigationModel WHERE plant_id = ?",
                (plant_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error(f"Failed to fetch irrigation model for plant {plant_id}: {exc}")
            return None

    def upsert_plant_irrigation_model(
        self,
        *,
        plant_id: int,
        drydown_rate_per_hour: float | None,
        sample_count: int,
        confidence: float | None,
        updated_at_utc: str,
    ) -> bool:
        """Insert or update a plant irrigation model row."""
        try:
            db = self.get_db()
            db.execute(
                """
                INSERT INTO PlantIrrigationModel (
                    plant_id, drydown_rate_per_hour, sample_count, confidence, updated_at_utc
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(plant_id) DO UPDATE SET
                    drydown_rate_per_hour = excluded.drydown_rate_per_hour,
                    sample_count = excluded.sample_count,
                    confidence = excluded.confidence,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    plant_id,
                    drydown_rate_per_hour,
                    sample_count,
                    confidence,
                    updated_at_utc,
                ),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to upsert irrigation model for plant {plant_id}: {exc}")
            return False

    def acquire_unit_lock(
        self,
        unit_id: int,
        lock_seconds: int,
        current_time: str | None = None,
    ) -> bool:
        """Acquire a unit-level irrigation lock with a TTL."""
        db = None
        try:
            db = self.get_db()
            now_dt = coerce_datetime(current_time) if current_time else None
            if now_dt is None:
                now_dt = utc_now()
            now = now_dt.isoformat()
            locked_until = (now_dt + timedelta(seconds=lock_seconds)).isoformat()

            cur = db.cursor()
            cur.execute("BEGIN IMMEDIATE")
            cur.execute(
                "SELECT locked_until_utc FROM IrrigationLock WHERE unit_id = ?",
                (unit_id,),
            )
            row = cur.fetchone()

            if row is None:
                cur.execute(
                    "INSERT INTO IrrigationLock (unit_id, locked_until_utc) VALUES (?, ?)",
                    (unit_id, locked_until),
                )
                db.commit()
                return True

            existing_until = row["locked_until_utc"]
            if existing_until and existing_until > now:
                db.rollback()
                return False

            cur.execute(
                """
                UPDATE IrrigationLock
                SET locked_until_utc = ?
                WHERE unit_id = ? AND locked_until_utc = ?
                """,
                (locked_until, unit_id, existing_until),
            )
            if cur.rowcount != 1:
                db.rollback()
                return False

            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to acquire irrigation lock for unit %s: %s", unit_id, exc)
            if db is not None:
                with contextlib.suppress(Exception):
                    db.rollback()
            return False

    def release_unit_lock(self, unit_id: int) -> bool:
        """Release a unit-level irrigation lock."""
        try:
            db = self.get_db()
            db.execute("DELETE FROM IrrigationLock WHERE unit_id = ?", (unit_id,))
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to release irrigation lock for unit %s: %s", unit_id, exc)
            return False

    def get_expired_requests(self, current_time: str | None = None) -> list[dict[str, Any]]:
        """Get requests that have expired."""
        try:
            db = self.get_db()
            now = current_time or iso_now()

            cur = db.execute(
                """
                SELECT * FROM PendingIrrigationRequest
                WHERE status = 'pending'
                  AND expires_at IS NOT NULL
                  AND expires_at <= ?
                """,
                (now,),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to get expired requests: {exc}")
            return []

    def update_request_status(
        self,
        request_id: int,
        status: str,
        user_response: str | None = None,
        delayed_until: str | None = None,
    ) -> bool:
        """Update the status of a pending irrigation request."""
        try:
            db = self.get_db()
            now = iso_now()

            if user_response:
                db.execute(
                    """
                    UPDATE PendingIrrigationRequest
                    SET status = ?, user_response = ?, user_response_at = ?,
                        delayed_until = ?, updated_at = ?
                    WHERE request_id = ?
                    """,
                    (status, user_response, now, delayed_until, now, request_id),
                )
            else:
                db.execute(
                    """
                    UPDATE PendingIrrigationRequest
                    SET status = ?, delayed_until = ?, updated_at = ?
                    WHERE request_id = ?
                    """,
                    (status, delayed_until, now, request_id),
                )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to update request status: {exc}")
            return False

    def record_execution(
        self,
        request_id: int,
        success: bool,
        duration_seconds: int | None = None,
        soil_moisture_after: float | None = None,
        error: str | None = None,
    ) -> bool:
        """Record execution results for a request."""
        try:
            db = self.get_db()
            now = iso_now()

            db.execute(
                """
                UPDATE PendingIrrigationRequest
                SET status = ?, executed_at = ?, execution_duration_seconds = ?,
                    soil_moisture_after = ?, execution_success = ?, execution_error = ?,
                    execution_status = ?, last_attempt_at_utc = ?,
                    updated_at = ?
                WHERE request_id = ?
                """,
                (
                    "executed" if success else "failed",
                    now,
                    duration_seconds,
                    soil_moisture_after,
                    1 if success else 0,
                    error,
                    "completed" if success else "failed",
                    now,
                    now,
                    request_id,
                ),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to record execution: {exc}")
            return False

    def link_notification(self, request_id: int, notification_id: int) -> bool:
        """Link a notification to a pending request."""
        try:
            db = self.get_db()
            db.execute(
                "UPDATE PendingIrrigationRequest SET notification_id = ?, updated_at = ? WHERE request_id = ?",
                (notification_id, iso_now(), request_id),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to link notification: {exc}")
            return False

    def link_feedback(self, request_id: int, feedback_id: int) -> bool:
        """Link feedback to a pending request."""
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE PendingIrrigationRequest
                SET feedback_id = ?, feedback_requested_at = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (feedback_id, iso_now(), iso_now(), request_id),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to link feedback: {exc}")
            return False

    def get_request_by_feedback_id(self, feedback_id: int) -> dict[str, Any] | None:
        """Fetch a pending request associated with a feedback record."""
        try:
            db = self.get_db()
            cur = db.execute(
                "SELECT * FROM PendingIrrigationRequest WHERE feedback_id = ? LIMIT 1",
                (feedback_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error(f"Failed to get request for feedback {feedback_id}: {exc}")
            return None

    def mark_ml_data_collected(self, request_id: int, preference_score: float | None = None) -> bool:
        """Mark that ML data has been collected from this request."""
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE PendingIrrigationRequest
                SET ml_data_collected = 1, ml_preference_score = ?, updated_at = ?
                WHERE request_id = ?
                """,
                (preference_score, iso_now(), request_id),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to mark ML data collected: {exc}")
            return False

    def has_active_request_for_unit(
        self,
        unit_id: int,
        plant_id: int | None = None,
        actuator_id: int | None = None,
    ) -> bool:
        """Check if unit has an active pending request (to avoid duplicates)."""
        try:
            db = self.get_db()
            query = (
                "SELECT COUNT(*) FROM PendingIrrigationRequest "
                "WHERE unit_id = ? AND status IN ('pending', 'approved', 'delayed')"
            )
            params: list[Any] = [unit_id]
            if plant_id is not None:
                query += " AND plant_id = ?"
                params.append(plant_id)
            if actuator_id is not None:
                query += " AND actuator_id = ?"
                params.append(actuator_id)
            cur = db.execute(query, params)
            count = cur.fetchone()[0]
            return count > 0
        except sqlite3.Error as exc:
            logger.error(f"Failed to check active request: {exc}")
            return False

    def get_last_completed_irrigation(
        self,
        unit_id: int,
        plant_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Get the most recent completed irrigation for a unit or plant."""
        try:
            db = self.get_db()
            query = (
                "SELECT * FROM PendingIrrigationRequest "
                "WHERE unit_id = ? AND status = 'executed' AND execution_success = 1"
            )
            params: list[Any] = [unit_id]
            if plant_id is not None:
                query += " AND plant_id = ?"
                params.append(plant_id)
            query += " ORDER BY executed_at DESC LIMIT 1"
            cur = db.execute(query, params)
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error(f"Failed to get last completed irrigation: {exc}")
            return None

    def get_ml_training_data(
        self,
        min_records: int = 20,
        unit_id: int | None = None,
        include_cancelled: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Get irrigation requests with ML context data for training.

        Returns completed requests that have environmental context.
        """
        try:
            db = self.get_db()
            query = """
                SELECT * FROM PendingIrrigationRequest
                WHERE ml_data_collected = 1
                  AND temperature_at_detection IS NOT NULL
            """
            params: list[Any] = []

            if unit_id:
                query += " AND unit_id = ?"
                params.append(unit_id)

            if not include_cancelled:
                query += " AND status != 'cancelled'"

            query += " ORDER BY detected_at DESC"

            cur = db.execute(query, params)
            results = [dict(row) for row in cur.fetchall()]

            # Return empty if not enough data for training
            if len(results) < min_records:
                logger.debug(f"Only {len(results)} ML training records found, need {min_records}")

            return results
        except sqlite3.Error as exc:
            logger.error(f"Failed to get ML training data: {exc}")
            return []

    def count_ml_training_samples(self, unit_id: int | None = None) -> dict[str, int]:
        """
        Count available ML training samples by type.

        Returns dict with counts for each model type:
        - response_predictor: Requests with user response
        - threshold_optimizer: Requests with feedback
        - duration_optimizer: Executed with soil_moisture_after
        - timing_predictor: Delayed requests with context
        """
        try:
            db = self.get_db()
            counts = {}

            # Response predictor: needs user_response and context
            base_where = "WHERE temperature_at_detection IS NOT NULL"
            unit_clause = f" AND unit_id = {unit_id}" if unit_id else ""

            # Response predictor count
            cur = db.execute(f"""
                SELECT COUNT(*) FROM PendingIrrigationRequest
                {base_where} {unit_clause}
                AND user_response IN ('approve', 'delay', 'cancel')
            """)
            counts["response_predictor"] = cur.fetchone()[0]

            # Threshold optimizer count (needs feedback)
            cur = db.execute(f"""
                SELECT COUNT(*) FROM PendingIrrigationRequest p
                LEFT JOIN IrrigationFeedback f ON p.feedback_id = f.feedback_id
                {base_where} {unit_clause}
                AND f.feedback_response IN ('triggered_too_early', 'triggered_too_late')
            """)
            counts["threshold_optimizer"] = cur.fetchone()[0]

            # Duration optimizer count (needs execution result)
            cur = db.execute(f"""
                SELECT COUNT(*)
                FROM PendingIrrigationRequest p
                INNER JOIN IrrigationExecutionLog l
                    ON l.request_id = p.request_id
                {base_where} {unit_clause}
                AND p.status = 'executed'
                AND l.post_moisture IS NOT NULL
            """)
            counts["duration_optimizer"] = cur.fetchone()[0]

            # Timing predictor count (delayed with delay reason)
            cur = db.execute(f"""
                SELECT COUNT(*) FROM PendingIrrigationRequest
                {base_where} {unit_clause}
                AND user_response = 'delay'
                AND hours_since_last_irrigation IS NOT NULL
            """)
            counts["timing_predictor"] = cur.fetchone()[0]

            return counts

        except sqlite3.Error as exc:
            logger.error(f"Failed to count ML training samples: {exc}")
            return {
                "response_predictor": 0,
                "threshold_optimizer": 0,
                "duration_optimizer": 0,
                "timing_predictor": 0,
            }

    # ========== IrrigationWorkflowConfig Operations ==========

    def get_workflow_config(self, unit_id: int) -> dict[str, Any] | None:
        """Get workflow configuration for a unit."""
        try:
            db = self.get_db()
            cur = db.execute("SELECT * FROM IrrigationWorkflowConfig WHERE unit_id = ?", (unit_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error(f"Failed to get workflow config: {exc}")
            return None

    def upsert_workflow_config(self, unit_id: int, config: dict[str, Any]) -> bool:
        """Insert or update workflow configuration for a unit."""
        try:
            cols = safe_columns(config, _WORKFLOW_CONFIG_COLUMNS, context="upsert_workflow_config")
            if not cols:
                return True  # nothing to write

            db = self.get_db()
            existing = self.get_workflow_config(unit_id)
            now = iso_now()

            if existing:
                cols["updated_at"] = now
                set_sql, params = build_set_clause(cols)
                params.append(unit_id)
                db.execute(
                    f"UPDATE IrrigationWorkflowConfig SET {set_sql} WHERE unit_id = ?",  # nosec B608
                    params,
                )
            else:
                cols["unit_id"] = unit_id
                cols["created_at"] = now
                cols["updated_at"] = now
                col_sql, ph_sql, values = build_insert_parts(cols)
                db.execute(
                    f"INSERT INTO IrrigationWorkflowConfig ({col_sql}) VALUES ({ph_sql})",  # nosec B608
                    values,
                )

            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to upsert workflow config: %s", exc)
            return False

    # ========== IrrigationUserPreference Operations ==========

    def get_user_preference(self, user_id: int, unit_id: int | None = None) -> dict[str, Any] | None:
        """Get irrigation preferences for a user (optionally per-unit)."""
        try:
            db = self.get_db()
            if unit_id:
                cur = db.execute(
                    "SELECT * FROM IrrigationUserPreference WHERE user_id = ? AND unit_id = ?", (user_id, unit_id)
                )
            else:
                cur = db.execute(
                    "SELECT * FROM IrrigationUserPreference WHERE user_id = ? AND unit_id IS NULL", (user_id,)
                )
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error(f"Failed to get user preference: {exc}")
            return None

    def update_user_preference_on_response(
        self,
        user_id: int,
        response_type: str,
        response_time_seconds: float,
        unit_id: int | None = None,
    ) -> bool:
        """Update user preference statistics based on their response."""
        try:
            db = self.get_db()
            existing = self.get_user_preference(user_id, unit_id)
            now = iso_now()

            if existing:
                # Update counters based on response type
                update_field = ""
                if response_type == "approve":
                    update_field = "immediate_approvals = immediate_approvals + 1"
                elif response_type == "delay":
                    update_field = "delayed_approvals = delayed_approvals + 1"
                elif response_type == "cancel":
                    update_field = "cancellations = cancellations + 1"
                elif response_type == "auto":
                    update_field = "auto_executions = auto_executions + 1"

                if update_field:
                    if unit_id:
                        db.execute(
                            f"""
                            UPDATE IrrigationUserPreference
                            SET total_requests = total_requests + 1, {update_field},
                                avg_response_time_seconds = (
                                    COALESCE(avg_response_time_seconds, 0) * total_requests + ?
                                ) / (total_requests + 1),
                                updated_at = ?
                            WHERE user_id = ? AND unit_id = ?
                            """,
                            (response_time_seconds, now, user_id, unit_id),
                        )
                    else:
                        db.execute(
                            f"""
                            UPDATE IrrigationUserPreference
                            SET total_requests = total_requests + 1, {update_field},
                                avg_response_time_seconds = (
                                    COALESCE(avg_response_time_seconds, 0) * total_requests + ?
                                ) / (total_requests + 1),
                                updated_at = ?
                            WHERE user_id = ? AND unit_id IS NULL
                            """,
                            (response_time_seconds, now, user_id),
                        )
            else:
                # Insert new preference record
                initial_values = {
                    "total_requests": 1,
                    "immediate_approvals": 1 if response_type == "approve" else 0,
                    "delayed_approvals": 1 if response_type == "delay" else 0,
                    "cancellations": 1 if response_type == "cancel" else 0,
                    "auto_executions": 1 if response_type == "auto" else 0,
                    "avg_response_time_seconds": response_time_seconds,
                }

                db.execute(
                    """
                    INSERT INTO IrrigationUserPreference (
                        user_id, unit_id, total_requests, immediate_approvals,
                        delayed_approvals, cancellations, auto_executions,
                        avg_response_time_seconds, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        unit_id,
                        initial_values["total_requests"],
                        initial_values["immediate_approvals"],
                        initial_values["delayed_approvals"],
                        initial_values["cancellations"],
                        initial_values["auto_executions"],
                        initial_values["avg_response_time_seconds"],
                        now,
                        now,
                    ),
                )

            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to update user preference on response: {exc}")
            return False

    def update_user_moisture_feedback(
        self,
        user_id: int,
        feedback_type: str,
        unit_id: int | None = None,
    ) -> bool:
        """Update user moisture feedback statistics."""
        try:
            db = self.get_db()
            now = iso_now()

            feedback_field = ""
            if feedback_type == "too_little":
                feedback_field = "too_little_feedback_count = too_little_feedback_count + 1"
            elif feedback_type == "just_right":
                feedback_field = "just_right_feedback_count = just_right_feedback_count + 1"
            elif feedback_type == "too_much":
                feedback_field = "too_much_feedback_count = too_much_feedback_count + 1"

            if not feedback_field:
                return False

            if unit_id:
                db.execute(
                    f"""
                    UPDATE IrrigationUserPreference
                    SET moisture_feedback_count = moisture_feedback_count + 1,
                        {feedback_field}, updated_at = ?
                    WHERE user_id = ? AND unit_id = ?
                    """,
                    (now, user_id, unit_id),
                )
            else:
                db.execute(
                    f"""
                    UPDATE IrrigationUserPreference
                    SET moisture_feedback_count = moisture_feedback_count + 1,
                        {feedback_field}, updated_at = ?
                    WHERE user_id = ? AND unit_id IS NULL
                    """,
                    (now, user_id),
                )

            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to update user moisture feedback: {exc}")
            return False

    def get_irrigation_request_history(
        self,
        unit_id: int,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get irrigation request history for a unit."""
        try:
            db = self.get_db()
            cur = db.execute(
                """
                SELECT * FROM PendingIrrigationRequest
                WHERE unit_id = ?
                ORDER BY detected_at DESC
                LIMIT ?
                """,
                (unit_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error(f"Failed to get irrigation request history: {exc}")
            return []

    def update_threshold_belief(
        self,
        user_id: int,
        unit_id: int,
        threshold_mean: float,
        threshold_variance: float,
        sample_count: int,
        belief_json: str,
    ) -> bool:
        """
        Update Bayesian threshold belief for a user/unit.

        Stores the belief parameters and JSON for persistence.
        """
        try:
            db = self.get_db()
            now = iso_now()

            # Update existing or insert new preference
            db.execute(
                """
                INSERT INTO IrrigationUserPreference (
                    user_id, unit_id, preferred_moisture_threshold,
                    threshold_belief_json, threshold_variance, threshold_sample_count,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, unit_id) DO UPDATE SET
                    preferred_moisture_threshold = excluded.preferred_moisture_threshold,
                    threshold_belief_json = excluded.threshold_belief_json,
                    threshold_variance = excluded.threshold_variance,
                    threshold_sample_count = excluded.threshold_sample_count,
                    updated_at = excluded.updated_at
                """,
                (
                    user_id,
                    unit_id,
                    threshold_mean,
                    belief_json,
                    threshold_variance,
                    sample_count,
                    now,
                    now,
                ),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error(f"Failed to update threshold belief: {exc}")
            return False
