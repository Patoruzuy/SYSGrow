"""Database operations for Notification entities."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from app.utils.time import iso_now

logger = logging.getLogger(__name__)


class NotificationOperations:
    """Database operations for notification settings and messages."""

    # --- Notification Settings ---

    def get_notification_settings(self, user_id: int) -> dict[str, Any] | None:
        """Get notification settings for a user."""
        try:
            db = self.get_db()
            cur = db.execute("SELECT * FROM NotificationSettings WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error("Failed to get notification settings: %s", exc)
            return None

    def upsert_notification_settings(self, user_id: int, settings: dict[str, Any]) -> bool:
        """Insert or update notification settings for a user."""
        try:
            db = self.get_db()
            # Check if settings exist
            cur = db.execute("SELECT id FROM NotificationSettings WHERE user_id = ?", (user_id,))
            existing = cur.fetchone()

            if existing:
                # Update existing settings
                set_clauses = []
                params = []
                for key, value in settings.items():
                    if key not in ("id", "user_id", "created_at"):
                        set_clauses.append(f"{key} = ?")
                        params.append(value)
                set_clauses.append("updated_at = ?")
                params.append(iso_now())
                params.append(user_id)

                if set_clauses:
                    query = f"UPDATE NotificationSettings SET {', '.join(set_clauses)} WHERE user_id = ?"
                    db.execute(query, params)
            else:
                # Insert new settings
                columns = ["user_id"]
                values = [user_id]
                placeholders = ["?"]

                for key, value in settings.items():
                    if key not in ("id", "user_id", "created_at"):
                        columns.append(key)
                        values.append(value)
                        placeholders.append("?")

                query = f"INSERT INTO NotificationSettings ({', '.join(columns)}) VALUES ({', '.join(placeholders)})"
                db.execute(query, values)

            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to upsert notification settings: %s", exc)
            return False

    # --- Notification Messages ---

    def create_notification_message(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        severity: str,
        channel: str,
        source_type: str | None = None,
        source_id: int | None = None,
        unit_id: int | None = None,
        requires_action: bool = False,
        action_type: str | None = None,
        action_data: str | None = None,
        expires_at: str | None = None,
    ) -> int | None:
        """Create a new notification message."""
        try:
            db = self.get_db()
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO NotificationMessage (
                    user_id, notification_type, title, message, severity,
                    channel, source_type, source_id, unit_id,
                    requires_action, action_type, action_data, expires_at,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    notification_type,
                    title,
                    message,
                    severity,
                    channel,
                    source_type,
                    source_id,
                    unit_id,
                    1 if requires_action else 0,
                    action_type,
                    action_data,
                    expires_at,
                    iso_now(),
                ),
            )
            message_id = cur.lastrowid
            db.commit()
            return message_id
        except sqlite3.Error as exc:
            logger.error("Failed to create notification message: %s", exc)
            return None

    def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get notifications for a user."""
        try:
            db = self.get_db()
            query = "SELECT * FROM NotificationMessage WHERE user_id = ?"
            params: list[Any] = [user_id]

            if unread_only:
                query += " AND in_app_read = 0"

            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cur = db.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error("Failed to get user notifications: %s", exc)
            return []

    def get_notification_by_id(self, message_id: int) -> dict[str, Any] | None:
        """Get a notification by ID."""
        try:
            db = self.get_db()
            cur = db.execute("SELECT * FROM NotificationMessage WHERE message_id = ?", (message_id,))
            row = cur.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error("Failed to get notification: %s", exc)
            return None

    def mark_notification_read(self, message_id: int) -> bool:
        """Mark a notification as read."""
        try:
            db = self.get_db()
            db.execute(
                "UPDATE NotificationMessage SET in_app_read = 1, in_app_read_at = ? WHERE message_id = ?",
                (iso_now(), message_id),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to mark notification as read: %s", exc)
            return False

    def mark_all_notifications_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user. Returns count updated."""
        try:
            db = self.get_db()
            cur = db.execute(
                "UPDATE NotificationMessage SET in_app_read = 1, in_app_read_at = ? WHERE user_id = ? AND in_app_read = 0",
                (iso_now(), user_id),
            )
            db.commit()
            return cur.rowcount
        except sqlite3.Error as exc:
            logger.error("Failed to mark all notifications as read: %s", exc)
            return 0

    def update_email_status(
        self,
        message_id: int,
        sent: bool,
        error: str | None = None,
    ) -> bool:
        """Update email delivery status."""
        try:
            db = self.get_db()
            if sent:
                db.execute(
                    "UPDATE NotificationMessage SET email_sent = 1, email_sent_at = ? WHERE message_id = ?",
                    (iso_now(), message_id),
                )
            else:
                db.execute(
                    "UPDATE NotificationMessage SET email_sent = 0, email_error = ? WHERE message_id = ?",
                    (error, message_id),
                )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to update email status: %s", exc)
            return False

    def update_notification_action(
        self,
        message_id: int,
        action_response: str,
    ) -> bool:
        """Record user action on a notification."""
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE NotificationMessage
                SET action_taken = 1, action_response = ?, action_taken_at = ?
                WHERE message_id = ?
                """,
                (action_response, iso_now(), message_id),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to update notification action: %s", exc)
            return False

    def delete_notification(self, message_id: int) -> bool:
        """Delete a notification."""
        try:
            db = self.get_db()
            db.execute(
                "DELETE FROM NotificationMessage WHERE message_id = ?",
                (message_id,),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to delete notification: %s", exc)
            return False

    def clear_user_notifications(self, user_id: int) -> int:
        """Clear all notifications for a user. Returns count deleted."""
        try:
            db = self.get_db()
            cur = db.execute(
                "DELETE FROM NotificationMessage WHERE user_id = ?",
                (user_id,),
            )
            db.commit()
            return cur.rowcount
        except sqlite3.Error as exc:
            logger.error("Failed to clear user notifications: %s", exc)
            return 0

    def get_pending_action_notifications(
        self,
        user_id: int,
        action_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get notifications that require user action."""
        try:
            db = self.get_db()
            query = "SELECT * FROM NotificationMessage WHERE user_id = ? AND requires_action = 1 AND action_taken = 0"
            params: list[Any] = [user_id]

            if action_type:
                query += " AND action_type = ?"
                params.append(action_type)

            query += " ORDER BY created_at DESC"
            cur = db.execute(query, params)
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error("Failed to get pending action notifications: %s", exc)
            return []

    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications for a user."""
        try:
            db = self.get_db()
            cur = db.execute(
                "SELECT COUNT(*) FROM NotificationMessage WHERE user_id = ? AND in_app_read = 0",
                (user_id,),
            )
            return cur.fetchone()[0]
        except sqlite3.Error as exc:
            logger.error("Failed to get unread count: %s", exc)
            return 0

    def purge_old_notifications(self, retention_days: int = 30) -> int:
        """Delete old notifications. Returns count deleted."""
        try:
            from datetime import datetime, timedelta

            cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()

            db = self.get_db()
            cur = db.execute(
                "DELETE FROM NotificationMessage WHERE created_at < ?",
                (cutoff,),
            )
            db.commit()
            return cur.rowcount
        except sqlite3.Error as exc:
            logger.error("Failed to purge old notifications: %s", exc)
            return 0

    # --- Irrigation Feedback ---

    def create_irrigation_feedback(
        self,
        user_id: int,
        unit_id: int,
        plant_id: int | None = None,
        actuator_id: int | None = None,
        soil_moisture_before: float | None = None,
        soil_moisture_after: float | None = None,
        irrigation_duration_seconds: int | None = None,
        feedback_response: str | None = None,
        feedback_notes: str | None = None,
        suggested_adjustment: float | None = None,
    ) -> int | None:
        """Create an irrigation feedback record."""
        try:
            db = self.get_db()
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO IrrigationFeedback (
                    user_id, unit_id, plant_id, actuator_id,
                    soil_moisture_before, soil_moisture_after,
                    irrigation_duration_seconds, feedback_response,
                    feedback_notes, suggested_threshold_adjustment,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    unit_id,
                    plant_id,
                    actuator_id,
                    soil_moisture_before,
                    soil_moisture_after,
                    irrigation_duration_seconds,
                    feedback_response,
                    feedback_notes,
                    suggested_adjustment,
                    iso_now(),
                ),
            )
            feedback_id = cur.lastrowid
            db.commit()
            return feedback_id
        except sqlite3.Error as exc:
            logger.error("Failed to create irrigation feedback: %s", exc)
            return None

    def update_irrigation_feedback(
        self,
        feedback_id: int,
        feedback_response: str,
        feedback_notes: str | None = None,
        suggested_adjustment: float | None = None,
    ) -> bool:
        """Update irrigation feedback response."""
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE IrrigationFeedback
                SET feedback_response = ?, feedback_notes = ?, suggested_threshold_adjustment = ?
                WHERE feedback_id = ?
                """,
                (feedback_response, feedback_notes, suggested_adjustment, feedback_id),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to update irrigation feedback: %s", exc)
            return False

    def get_irrigation_feedback_history(
        self,
        unit_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get irrigation feedback history for a unit."""
        try:
            db = self.get_db()
            cur = db.execute(
                """
                SELECT * FROM IrrigationFeedback
                WHERE unit_id = ? AND feedback_response IS NOT NULL
                ORDER BY created_at DESC LIMIT ?
                """,
                (unit_id, limit),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error("Failed to get irrigation feedback history: %s", exc)
            return []

    def get_pending_irrigation_feedback(self, user_id: int) -> list[dict[str, Any]]:
        """Get irrigation feedback records awaiting user response."""
        try:
            db = self.get_db()
            cur = db.execute(
                """
                SELECT * FROM IrrigationFeedback
                WHERE user_id = ? AND feedback_response IS NULL
                ORDER BY created_at DESC
                """,
                (user_id,),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.Error as exc:
            logger.error("Failed to get pending irrigation feedback: %s", exc)
            return []

    def mark_threshold_adjustment_applied(self, feedback_id: int) -> bool:
        """Mark that a threshold adjustment was applied from feedback."""
        try:
            db = self.get_db()
            db.execute(
                "UPDATE IrrigationFeedback SET threshold_adjustment_applied = 1 WHERE feedback_id = ?",
                (feedback_id,),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to mark threshold adjustment applied: %s", exc)
            return False
