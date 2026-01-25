"""
Notification Service
====================

Comprehensive notification service for SYSGrow smart agriculture platform.
Supports in-app notifications via WebSocket and email notifications via SMTP.

Features:
- Low battery alerts
- Plant needs water notifications
- Irrigation confirmation requests
- Post-irrigation feedback collection
- Threshold exceeded alerts
- Device offline alerts
- Harvest ready notifications
- Plant health warnings

Author: SYSGrow Team
Date: January 2026
"""
from __future__ import annotations

import json
import logging
from dataclasses import field
from datetime import datetime, time, timedelta
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from app.domain.notification_settings import NotificationSettings
from app.enums import (
    NotificationType,
    NotificationSeverity,
    NotificationChannel,
    IrrigationFeedback,
)
from app.utils.time import iso_now, utc_now

if TYPE_CHECKING:
    from infrastructure.database.repositories.notifications import NotificationRepository
    from app.utils.emitters import EmitterService
    from app.services.utilities.email_service import EmailService

logger = logging.getLogger(__name__)


# Backward compatibility alias
IrrigationFeedbackResponse = IrrigationFeedback


class NotificationsService:
    """
    Comprehensive notification service for user alerts.

    Supports:
    - In-app notifications via WebSocket (EmitterService)
    - Email notifications via SMTP (free, no external service)
    - User preferences for notification types
    - Quiet hours
    - Notification throttling
    - Irrigation feedback collection
    """

    def __init__(
        self,
        notification_repo: "NotificationRepository",
        emitter_service: Optional["EmitterService"] = None,
        email_service: Optional["EmailService"] = None,
    ):
        """
        Initialize NotificationsService.

        Args:
            notification_repo: Repository for notification data.
            emitter_service: Optional emitter for WebSocket notifications.
            email_service: Optional email service for email notifications.
        """
        self._repo = notification_repo
        self._emitter = emitter_service
        self._email_service = email_service

        # In-memory throttle cache: key -> last_sent_timestamp
        self._throttle_cache: Dict[str, datetime] = {}
        self._action_handlers: Dict[str, Callable[[str, Dict[str, Any], Optional[Dict[str, Any]]], bool]] = {}

    # --- Settings Management ---

    def get_user_settings(self, user_id: int) -> NotificationSettings:
        """
        Get notification settings for a user.

        Returns default settings if none exist.
        """
        try:
            data = self._repo.get_settings(user_id)
            if data:
                return NotificationSettings.from_dict(data)
            # Return defaults
            return NotificationSettings(user_id=user_id)
        except Exception as e:
            logger.error(f"Error getting notification settings: {e}")
            return NotificationSettings(user_id=user_id)

    def save_user_settings(self, user_id: int, settings: NotificationSettings) -> bool:
        """Save notification settings for a user."""
        try:
            return self._repo.save_settings(user_id, settings.to_dict())
        except Exception as e:
            logger.error(f"Error saving notification settings: {e}")
            return False

    def update_user_settings(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """Update specific notification settings for a user."""
        try:
            current = self.get_user_settings(user_id)
            for key, value in updates.items():
                if hasattr(current, key):
                    setattr(current, key, value)
            return self.save_user_settings(user_id, current)
        except Exception as e:
            logger.error(f"Error updating notification settings: {e}")
            return False

    # --- Core Notification Methods ---

    def send_notification(
        self,
        user_id: int,
        notification_type: str,
        title: str,
        message: str,
        severity: str = NotificationSeverity.INFO,
        source_type: Optional[str] = None,
        source_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        requires_action: bool = False,
        action_type: Optional[str] = None,
        action_data: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Optional[int]:
        """
        Send a notification to a user.

        Respects user preferences, quiet hours, and throttling.

        Args:
            user_id: Target user ID
            notification_type: Type of notification (see NotificationType)
            title: Notification title
            message: Notification message
            severity: Severity level (info, warning, critical)
            source_type: Type of source entity (sensor, actuator, etc.)
            source_id: ID of source entity
            unit_id: Associated growth unit ID
            requires_action: Whether user action is required
            action_type: Type of action required
            action_data: Additional action data (JSON serializable)
            force: Bypass preferences and throttling

        Returns:
            Notification message ID if sent, None otherwise
        """
        try:
            settings = self.get_user_settings(user_id)

            # Check if notification type is enabled (unless forced)
            if not force and not self._is_notification_enabled(settings, notification_type):
                logger.debug(f"Notification type {notification_type} disabled for user {user_id}")
                return None

            # Check quiet hours
            if not force and self._in_quiet_hours(settings):
                logger.debug(f"In quiet hours for user {user_id}")
                return None

            # Check throttling
            throttle_key = f"{user_id}:{notification_type}:{source_type}:{source_id}"
            if not force and self._is_throttled(throttle_key, settings.min_notification_interval_seconds):
                logger.debug(f"Throttled notification for key {throttle_key}")
                return None

            # Determine channel
            channel = self._determine_channel(settings)
            if channel is None:
                logger.debug(f"No notification channels enabled for user {user_id}")
                return None

            # Create notification record
            action_data_json = json.dumps(action_data) if action_data else None
            message_id = self._repo.create_message(
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
                action_data=action_data_json,
            )

            if not message_id:
                logger.error(f"Failed to create notification record")
                return None

            # Update throttle cache
            self._throttle_cache[throttle_key] = utc_now()

            # Send via appropriate channels
            if channel in (NotificationChannel.IN_APP, NotificationChannel.BOTH):
                self._send_in_app(user_id, message_id, notification_type, title, message, severity, unit_id)

            if channel in (NotificationChannel.EMAIL, NotificationChannel.BOTH):
                self._send_email(message_id, settings, title, message, severity)

            logger.info(f"Notification sent: [{severity}] {title} to user {user_id}")
            return message_id

        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            return None

    def _is_notification_enabled(self, settings: NotificationSettings, notification_type: str) -> bool:
        """Check if a notification type is enabled for user."""
        mapping = {
            NotificationType.LOW_BATTERY: settings.notify_low_battery,
            NotificationType.PLANT_NEEDS_WATER: settings.notify_plant_needs_water,
            NotificationType.IRRIGATION_CONFIRM: settings.notify_irrigation_confirm,
            NotificationType.IRRIGATION_FEEDBACK: settings.irrigation_feedback_enabled,
            NotificationType.IRRIGATION_RECOMMENDATION: settings.notify_irrigation_recommendation,
            NotificationType.THRESHOLD_EXCEEDED: settings.notify_threshold_exceeded,
            NotificationType.DEVICE_OFFLINE: settings.notify_device_offline,
            NotificationType.HARVEST_READY: settings.notify_harvest_ready,
            NotificationType.PLANT_HEALTH_WARNING: settings.notify_plant_health_warning,
            NotificationType.SYSTEM_ALERT: True,  # Always enabled
        }
        return mapping.get(notification_type, True)

    def _in_quiet_hours(self, settings: NotificationSettings) -> bool:
        """Check if currently in quiet hours."""
        if not settings.quiet_hours_enabled:
            return False

        if not settings.quiet_hours_start or not settings.quiet_hours_end:
            return False

        try:
            now = datetime.now().time()
            start = datetime.strptime(settings.quiet_hours_start, "%H:%M").time()
            end = datetime.strptime(settings.quiet_hours_end, "%H:%M").time()

            # Handle overnight quiet hours (e.g., 22:00 to 07:00)
            if start <= end:
                return start <= now <= end
            else:
                return now >= start or now <= end
        except Exception:
            return False

    def _is_throttled(self, key: str, interval_seconds: int) -> bool:
        """Check if notification is throttled."""
        last_sent = self._throttle_cache.get(key)
        if not last_sent:
            return False

        elapsed = (utc_now() - last_sent).total_seconds()
        return elapsed < interval_seconds

    def _determine_channel(self, settings: NotificationSettings) -> Optional[str]:
        """Determine which notification channel(s) to use."""
        email_ready = (
            settings.email_enabled
            and settings.email_address
            and settings.smtp_host
        )
        in_app_ready = settings.in_app_enabled

        if email_ready and in_app_ready:
            return NotificationChannel.BOTH
        elif email_ready:
            return NotificationChannel.EMAIL
        elif in_app_ready:
            return NotificationChannel.IN_APP
        return None

    def _send_in_app(
        self,
        user_id: int,
        message_id: int,
        notification_type: str,
        title: str,
        message: str,
        severity: str,
        unit_id: Optional[int] = None,
    ) -> None:
        """Send in-app notification via WebSocket."""
        if not self._emitter:
            logger.debug("No emitter service available for in-app notification")
            return

        try:
            from app.schemas.events import NotificationPayload

            payload = NotificationPayload(
                userId=user_id,
                event="notification",
                notificationType=notification_type,
                title=title,
                message=message,
                severity=severity,
                messageId=message_id,
                unitId=unit_id,
                timestamp=iso_now(),
            )
            self._emitter.emit_notification(payload)
            logger.debug(f"In-app notification sent to user {user_id}")
        except Exception as e:
            logger.error(f"Failed to send in-app notification: {e}")

    def _send_email(
        self,
        message_id: int,
        settings: NotificationSettings,
        title: str,
        message: str,
        severity: str,
    ) -> None:
        """Send email notification via EmailService."""
        if not settings.email_address or not settings.smtp_host:
            return
        
        if not self._email_service:
            logger.warning("Email service not configured, skipping email notification")
            return

        try:
            from app.services.utilities.email_service import EmailConfig
            
            config = EmailConfig(
                smtp_host=settings.smtp_host,
                smtp_port=settings.smtp_port,
                smtp_username=settings.smtp_username,
                smtp_password=settings.smtp_password,
                smtp_use_tls=settings.smtp_use_tls,
            )
            
            success = self._email_service.send_notification_email(
                to_address=settings.email_address,
                title=title,
                message=message,
                severity=severity,
                config=config,
            )
            
            if success:
                self._repo.update_email_status(message_id, sent=True)
            else:
                self._repo.update_email_status(message_id, sent=False, error="Email send failed")

        except Exception as e:
            error_msg = str(e)
            self._repo.update_email_status(message_id, sent=False, error=error_msg)
            logger.error(f"Failed to send email notification: {e}")

    # --- Convenience Methods for Specific Notification Types ---

    def notify_low_battery(
        self,
        user_id: int,
        sensor_name: str,
        battery_level: float,
        sensor_id: Optional[int] = None,
        unit_id: Optional[int] = None,
    ) -> Optional[int]:
        """Send low battery notification for a sensor."""
        title = f"Low Battery: {sensor_name}"
        message = f"The sensor '{sensor_name}' has a low battery level ({battery_level:.1f}%). Please replace or recharge the batteries soon."

        severity = NotificationSeverity.CRITICAL if battery_level < 10 else NotificationSeverity.WARNING

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.LOW_BATTERY,
            title=title,
            message=message,
            severity=severity,
            source_type="sensor",
            source_id=sensor_id,
            unit_id=unit_id,
        )

    def notify_plant_needs_water(
        self,
        user_id: int,
        plant_name: str,
        soil_moisture: float,
        threshold: float,
        plant_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        has_pump: bool = False,
    ) -> Optional[int]:
        """
        Send notification that a plant needs water.

        If a pump actuator is available, includes irrigation confirmation request.
        """
        if has_pump:
            title = f"Water Needed: {plant_name}"
            message = (
                f"The plant '{plant_name}' needs water. "
                f"Soil moisture is {soil_moisture:.1f}% (threshold: {threshold:.1f}%). "
                f"Would you like to start irrigation?"
            )
            return self.send_notification(
                user_id=user_id,
                notification_type=NotificationType.IRRIGATION_CONFIRM,
                title=title,
                message=message,
                severity=NotificationSeverity.WARNING,
                source_type="plant",
                source_id=plant_id,
                unit_id=unit_id,
                requires_action=True,
                action_type="irrigation_confirm",
                action_data={
                    "plant_id": plant_id,
                    "unit_id": unit_id,
                    "soil_moisture": soil_moisture,
                    "threshold": threshold,
                },
            )
        else:
            title = f"Water Needed: {plant_name}"
            message = (
                f"The plant '{plant_name}' needs water. "
                f"Soil moisture is {soil_moisture:.1f}% (threshold: {threshold:.1f}%)."
            )
            return self.send_notification(
                user_id=user_id,
                notification_type=NotificationType.PLANT_NEEDS_WATER,
                title=title,
                message=message,
                severity=NotificationSeverity.WARNING,
                source_type="plant",
                source_id=plant_id,
                unit_id=unit_id,
            )

    def request_irrigation_feedback(
        self,
        user_id: int,
        unit_id: int,
        plant_id: Optional[int] = None,
        plant_name: Optional[str] = None,
        soil_moisture_before: Optional[float] = None,
        soil_moisture_after: Optional[float] = None,
        irrigation_duration: Optional[int] = None,
        actuator_id: Optional[int] = None,
    ) -> Optional[int]:
        """
        Request irrigation feedback from user after watering.

        Also creates a pending feedback record in the database.
        """
        # Create feedback record
        feedback_id = self._repo.create_irrigation_feedback(
            user_id=user_id,
            unit_id=unit_id,
            plant_id=plant_id,
            actuator_id=actuator_id,
            soil_moisture_before=soil_moisture_before,
            soil_moisture_after=soil_moisture_after,
            irrigation_duration_seconds=irrigation_duration,
        )

        if not feedback_id:
            logger.error("Failed to create irrigation feedback record")
            return None

        plant_display = plant_name or f"Unit {unit_id}"
        title = f"Irrigation Feedback: {plant_display}"
        message = (
            f"Irrigation completed for '{plant_display}'. "
            f"Was the amount of water appropriate? "
            f"Your feedback helps adjust soil moisture thresholds."
        )

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.IRRIGATION_FEEDBACK,
            title=title,
            message=message,
            severity=NotificationSeverity.INFO,
            source_type="irrigation",
            source_id=feedback_id,
            unit_id=unit_id,
            requires_action=True,
            action_type="irrigation_feedback",
            action_data={
                "feedback_id": feedback_id,
                "plant_id": plant_id,
                "unit_id": unit_id,
                "soil_moisture_before": soil_moisture_before,
                "soil_moisture_after": soil_moisture_after,
            },
        )

    def notify_threshold_exceeded(
        self,
        user_id: int,
        metric_name: str,
        current_value: float,
        threshold_value: float,
        unit_id: Optional[int] = None,
        is_above: bool = True,
    ) -> Optional[int]:
        """Send notification when a threshold is exceeded."""
        direction = "above" if is_above else "below"
        title = f"{metric_name.title()} Alert"
        message = (
            f"{metric_name.title()} is {direction} threshold: "
            f"current {current_value:.1f}, threshold {threshold_value:.1f}"
        )

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.THRESHOLD_EXCEEDED,
            title=title,
            message=message,
            severity=NotificationSeverity.WARNING,
            unit_id=unit_id,
        )

    def notify_device_offline(
        self,
        user_id: int,
        device_name: str,
        device_type: str,
        device_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        last_seen: Optional[str] = None,
    ) -> Optional[int]:
        """Send notification when a device goes offline."""
        title = f"Device Offline: {device_name}"
        message = f"The {device_type} '{device_name}' is offline and not responding."
        if last_seen:
            message += f" Last seen: {last_seen}."

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.DEVICE_OFFLINE,
            title=title,
            message=message,
            severity=NotificationSeverity.WARNING,
            source_type=device_type,
            source_id=device_id,
            unit_id=unit_id,
        )

    def notify_harvest_ready(
        self,
        user_id: int,
        plant_name: str,
        plant_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        estimated_yield: Optional[float] = None,
    ) -> Optional[int]:
        """Send notification when a plant is ready for harvest."""
        title = f"Harvest Ready: {plant_name}"
        message = f"The plant '{plant_name}' is ready for harvest!"
        if estimated_yield:
            message += f" Estimated yield: {estimated_yield:.1f}g."

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.HARVEST_READY,
            title=title,
            message=message,
            severity=NotificationSeverity.INFO,
            source_type="plant",
            source_id=plant_id,
            unit_id=unit_id,
        )

    def notify_plant_health_warning(
        self,
        user_id: int,
        plant_name: str,
        health_issue: str,
        recommendations: Optional[str] = None,
        plant_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        severity: str = NotificationSeverity.WARNING,
    ) -> Optional[int]:
        """Send notification about plant health issues."""
        title = f"Health Alert: {plant_name}"
        message = f"Health issue detected for '{plant_name}': {health_issue}"
        if recommendations:
            message += f"\n\nRecommendations: {recommendations}"

        return self.send_notification(
            user_id=user_id,
            notification_type=NotificationType.PLANT_HEALTH_WARNING,
            title=title,
            message=message,
            severity=severity,
            source_type="plant",
            source_id=plant_id,
            unit_id=unit_id,
        )

    # --- Notification Management ---

    def get_user_notifications(
        self,
        user_id: int,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get notifications for a user."""
        try:
            return self._repo.get_user_messages(user_id, unread_only, limit, offset)
        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return []

    def mark_notification_read(self, message_id: int) -> bool:
        """Mark a notification as read."""
        try:
            return self._repo.mark_read(message_id)
        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False

    def mark_all_read(self, user_id: int) -> int:
        """Mark all notifications as read for a user."""
        try:
            return self._repo.mark_all_read(user_id)
        except Exception as e:
            logger.error(f"Error marking all notifications as read: {e}")
            return 0

    def delete_notification(self, message_id: int) -> bool:
        """Delete a notification."""
        try:
            return self._repo.delete_message(message_id)
        except Exception as e:
            logger.error(f"Error deleting notification: {e}")
            return False

    def clear_user_notifications(self, user_id: int) -> int:
        """Clear all notifications for a user."""
        try:
            return self._repo.clear_user_messages(user_id)
        except Exception as e:
            logger.error(f"Error clearing user notifications: {e}")
            return 0

    def get_unread_count(self, user_id: int) -> int:
        """Get count of unread notifications for a user."""
        try:
            return self._repo.get_unread_count(user_id)
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0

    def get_pending_actions(
        self,
        user_id: int,
        action_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get notifications requiring user action."""
        try:
            return self._repo.get_pending_actions(user_id, action_type)
        except Exception as e:
            logger.error(f"Error getting pending actions: {e}")
            return []

    def register_action_handler(
        self,
        action_type: str,
        handler: Callable[[str, Dict[str, Any], Optional[Dict[str, Any]]], bool],
    ) -> None:
        """Register a handler for notification action responses."""
        if not action_type:
            return
        self._action_handlers[action_type] = handler

    def respond_to_action(
        self,
        message_id: int,
        action_response: str,
    ) -> bool:
        """Record user response to an action notification."""
        try:
            message = self._repo.get_message_by_id(message_id)
            if not message:
                logger.debug("Notification message %s not found", message_id)
                return False

            action_type = message.get("action_type")
            action_data = message.get("action_data")
            if isinstance(action_data, str) and action_data:
                try:
                    action_data = json.loads(action_data)
                except json.JSONDecodeError:
                    action_data = {}
            if not isinstance(action_data, dict):
                action_data = {}

            handler = self._action_handlers.get(action_type)
            if handler:
                handled = handler(action_response, action_data, message)
                if not handled:
                    return False

            return self._repo.record_action(message_id, action_response)
        except Exception as e:
            logger.error(f"Error recording action response: {e}")
            return False

    # --- Irrigation Feedback Management ---

    def submit_irrigation_feedback(
        self,
        feedback_id: int,
        response: str,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Submit irrigation feedback.

        Args:
            feedback_id: Feedback record ID
            response: One of 'too_little', 'just_right', 'too_much',
                'triggered_too_early', 'triggered_too_late', 'skipped'
            notes: Optional user notes

        Returns:
            True if successful
        """
        valid_responses = {
            IrrigationFeedbackResponse.TOO_LITTLE,
            IrrigationFeedbackResponse.JUST_RIGHT,
            IrrigationFeedbackResponse.TOO_MUCH,
            IrrigationFeedbackResponse.TRIGGERED_TOO_EARLY,
            IrrigationFeedbackResponse.TRIGGERED_TOO_LATE,
            IrrigationFeedbackResponse.SKIPPED,
        }

        if response not in valid_responses:
            logger.error(f"Invalid irrigation feedback response: {response}")
            return False

        try:
            # Calculate suggested threshold adjustment based on feedback
            suggested_adjustment = None
            if response == IrrigationFeedbackResponse.TRIGGERED_TOO_EARLY:
                suggested_adjustment = -5.0  # Trigger later by lowering threshold
            elif response == IrrigationFeedbackResponse.TRIGGERED_TOO_LATE:
                suggested_adjustment = 5.0  # Trigger earlier by raising threshold

            return self._repo.update_irrigation_feedback(
                feedback_id=feedback_id,
                feedback_response=response,
                feedback_notes=notes,
                suggested_adjustment=suggested_adjustment,
            )
        except Exception as e:
            logger.error(f"Error submitting irrigation feedback: {e}")
            return False

    def get_pending_irrigation_feedback(self, user_id: int) -> List[Dict[str, Any]]:
        """Get pending irrigation feedback requests for a user."""
        try:
            return self._repo.get_pending_irrigation_feedback(user_id)
        except Exception as e:
            logger.error(f"Error getting pending irrigation feedback: {e}")
            return []

    def get_irrigation_feedback_history(
        self,
        unit_id: int,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get irrigation feedback history for a unit."""
        try:
            return self._repo.get_irrigation_feedback_history(unit_id, limit)
        except Exception as e:
            logger.error(f"Error getting irrigation feedback history: {e}")
            return []

    def apply_threshold_adjustment(self, feedback_id: int) -> bool:
        """Mark that a threshold adjustment from feedback was applied."""
        try:
            return self._repo.mark_threshold_adjustment_applied(feedback_id)
        except Exception as e:
            logger.error(f"Error marking threshold adjustment applied: {e}")
            return False

    # --- Maintenance ---

    def purge_old_notifications(self, retention_days: int = 30) -> int:
        """Purge old notifications."""
        try:
            return self._repo.purge_old(retention_days)
        except Exception as e:
            logger.error(f"Error purging old notifications: {e}")
            return 0
