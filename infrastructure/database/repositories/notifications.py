"""Repository for notification-related database operations."""

from __future__ import annotations

from typing import Any

from infrastructure.database.ops.notifications import NotificationOperations


class NotificationRepository:
    """Repository providing typed access to notification-related data."""

    def __init__(self, backend: NotificationOperations) -> None:
        self._backend = backend

    # --- Notification Settings ---

    def get_settings(self, user_id: int) -> dict[str, Any] | None:
        """Get notification settings for a user."""
        return self._backend.get_notification_settings(user_id)

    def save_settings(self, user_id: int, settings: dict[str, Any]) -> bool:
        """Save notification settings for a user."""
        return self._backend.upsert_notification_settings(user_id, settings)

    # --- Notification Messages ---

    def create_message(
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
        return self._backend.create_notification_message(
            user_id=user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            severity=severity,
            channel=channel,
            source_type=source_type,
            source_id=source_id,
            unit_id=unit_id,
            requires_action=requires_action,
            action_type=action_type,
            action_data=action_data,
            expires_at=expires_at,
        )

    def get_user_messages(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get notifications for a user."""
        return self._backend.get_user_notifications(user_id, unread_only, limit, offset)

    def get_message_by_id(self, message_id: int) -> dict[str, Any] | None:
        """Get a notification by ID."""
        return self._backend.get_notification_by_id(message_id)

    def mark_read(self, message_id: int) -> bool:
        """Mark a notification as read."""
        return self._backend.mark_notification_read(message_id)

    def mark_all_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user."""
        return self._backend.mark_all_notifications_read(user_id)

    def update_email_status(
        self,
        message_id: int,
        sent: bool,
        error: str | None = None,
    ) -> bool:
        """Update email delivery status."""
        return self._backend.update_email_status(message_id, sent, error)

    def record_action(self, message_id: int, action_response: str) -> bool:
        """Record user action on a notification."""
        return self._backend.update_notification_action(message_id, action_response)

    def delete_message(self, message_id: int) -> bool:
        """Delete a notification."""
        return self._backend.delete_notification(message_id)

    def clear_user_messages(self, user_id: int) -> int:
        """Clear all notifications for a user."""
        return self._backend.clear_user_notifications(user_id)

    def get_pending_actions(
        self,
        user_id: int,
        action_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get notifications that require user action."""
        return self._backend.get_pending_action_notifications(user_id, action_type)

    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications."""
        return self._backend.get_unread_count(user_id)

    def purge_old(self, retention_days: int = 30) -> int:
        """Purge old notifications."""
        return self._backend.purge_old_notifications(retention_days)

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
        return self._backend.create_irrigation_feedback(
            user_id=user_id,
            unit_id=unit_id,
            plant_id=plant_id,
            actuator_id=actuator_id,
            soil_moisture_before=soil_moisture_before,
            soil_moisture_after=soil_moisture_after,
            irrigation_duration_seconds=irrigation_duration_seconds,
            feedback_response=feedback_response,
            feedback_notes=feedback_notes,
            suggested_adjustment=suggested_adjustment,
        )

    def update_irrigation_feedback(
        self,
        feedback_id: int,
        feedback_response: str,
        feedback_notes: str | None = None,
        suggested_adjustment: float | None = None,
    ) -> bool:
        """Update irrigation feedback response."""
        return self._backend.update_irrigation_feedback(
            feedback_id, feedback_response, feedback_notes, suggested_adjustment
        )

    def get_irrigation_feedback_history(
        self,
        unit_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get irrigation feedback history for a unit."""
        return self._backend.get_irrigation_feedback_history(unit_id, limit)

    def get_pending_irrigation_feedback(self, user_id: int) -> list[dict[str, Any]]:
        """Get irrigation feedback records awaiting user response."""
        return self._backend.get_pending_irrigation_feedback(user_id)

    def mark_threshold_adjustment_applied(self, feedback_id: int) -> bool:
        """Mark that a threshold adjustment was applied from feedback."""
        return self._backend.mark_threshold_adjustment_applied(feedback_id)
