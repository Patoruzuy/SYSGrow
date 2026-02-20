"""
Notification Settings API
=========================

Endpoints for managing user notification preferences.
Supports email notifications (via SMTP), in-app notifications (via WebSocket),
and user preferences for different notification types.

Author: SYSGrow Team
Date: January 2026
"""

from __future__ import annotations

import logging

from flask import Response, request, session

from app.blueprints.api._common import fail, get_container, success
from app.blueprints.api.settings import settings_api
from app.enums import (
    IrrigationFeedback,
    NotificationSeverity,
    NotificationType,
)
from app.utils.http import safe_route

# Backward compatibility alias - keep function names for minimal changes
success_response = success
error_response = fail
IrrigationFeedbackResponse = IrrigationFeedback

logger = logging.getLogger(__name__)


def _get_current_user_id() -> int:
    """Get current user ID from session or default to 1."""
    return session.get("user_id", 1)


# --- Notification Settings Endpoints ---


@settings_api.get("/notifications")
@safe_route("Failed to get notification settings")
def get_notification_settings() -> Response:
    """
    Get notification settings for the current user.

    Returns:
        JSON response with notification settings including:
        - email_enabled: Whether email notifications are enabled
        - in_app_enabled: Whether in-app notifications are enabled
        - SMTP configuration (if email enabled)
        - Notification type preferences
        - Quiet hours settings
        - Throttling settings

    Example Response:
        {
            "ok": true,
            "data": {
                "email_enabled": false,
                "in_app_enabled": true,
                "email_address": null,
                "notify_low_battery": true,
                "notify_plant_needs_water": true,
                "notify_irrigation_confirm": true,
                "notify_threshold_exceeded": true,
                "notify_device_offline": true,
                "notify_harvest_ready": true,
                "notify_plant_health_warning": true,
                "irrigation_feedback_enabled": true,
                "irrigation_feedback_delay_minutes": 30,
                "quiet_hours_enabled": false,
                "quiet_hours_start": null,
                "quiet_hours_end": null,
                "min_notification_interval_seconds": 300
            }
        }
    """
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    user_id = _get_current_user_id()
    settings = notifications_service.get_user_settings(user_id)

    return success_response(settings.to_dict())


@settings_api.put("/notifications")
@safe_route("Failed to update notification settings")
def update_notification_settings() -> Response:
    """
    Update notification settings for the current user.

    Supports partial updates - only provided fields will be updated.

    Request Body (all fields optional):
        {
            "email_enabled": true,
            "in_app_enabled": true,
            "email_address": "user@example.com",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_username": "user@example.com",
            "smtp_password": "app_password",
            "smtp_use_tls": true,
            "notify_low_battery": true,
            "notify_plant_needs_water": true,
            "notify_irrigation_confirm": true,
            "notify_threshold_exceeded": true,
            "notify_device_offline": true,
            "notify_harvest_ready": true,
            "notify_plant_health_warning": true,
            "irrigation_feedback_enabled": true,
            "irrigation_feedback_delay_minutes": 30,
            "quiet_hours_enabled": false,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
            "min_notification_interval_seconds": 300
        }

    Returns:
        JSON response with updated settings
    """
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    data = request.get_json()
    if not data:
        return error_response("Request body is required", 400)

    user_id = _get_current_user_id()

    # Validate email address format if provided
    email_address = data.get("email_address")
    if email_address and "@" not in email_address:
        return error_response("Invalid email address format", 400)

    # Validate SMTP port if provided
    smtp_port = data.get("smtp_port")
    if smtp_port is not None and (not isinstance(smtp_port, int) or smtp_port < 1 or smtp_port > 65535):
        return error_response("Invalid SMTP port: must be between 1 and 65535", 400)

    # Validate quiet hours format if provided
    quiet_hours_start = data.get("quiet_hours_start")
    quiet_hours_end = data.get("quiet_hours_end")
    if quiet_hours_start:
        try:
            from datetime import datetime

            datetime.strptime(quiet_hours_start, "%H:%M")
        except ValueError:
            return error_response("Invalid quiet_hours_start: use HH:MM format", 400)
    if quiet_hours_end:
        try:
            from datetime import datetime

            datetime.strptime(quiet_hours_end, "%H:%M")
        except ValueError:
            return error_response("Invalid quiet_hours_end: use HH:MM format", 400)

    # Validate interval if provided
    interval = data.get("min_notification_interval_seconds")
    if interval is not None and (not isinstance(interval, int) or interval < 0):
        return error_response("Invalid interval: must be a non-negative integer", 400)

    # Update settings
    success = notifications_service.update_user_settings(user_id, data)
    if not success:
        return error_response("Failed to update notification settings", 500)

    # Return updated settings
    updated_settings = notifications_service.get_user_settings(user_id)
    return success_response(updated_settings.to_dict(), message="Notification settings updated successfully")


@settings_api.post("/notifications/test-email")
@safe_route("Failed to send test email notification")
def test_email_notification() -> Response:
    """
    Send a test email notification to verify SMTP configuration.

    Uses the user's configured email settings to send a test message.

    Returns:
        JSON response indicating success or failure with error details
    """
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    user_id = _get_current_user_id()
    settings = notifications_service.get_user_settings(user_id)

    if not settings.email_enabled:
        return error_response("Email notifications are not enabled", 400)

    if not settings.email_address:
        return error_response("Email address not configured", 400)

    if not settings.smtp_host:
        return error_response("SMTP host not configured", 400)

    # Send test notification (force=True bypasses preferences)
    message_id = notifications_service.send_notification(
        user_id=user_id,
        notification_type=NotificationType.SYSTEM_ALERT,
        title="Test Notification",
        message="This is a test notification from your SYSGrow system. If you received this email, your notification settings are configured correctly!",
        severity=NotificationSeverity.INFO,
        force=True,
    )

    if message_id:
        return success_response(
            {"message_id": message_id}, message="Test notification sent successfully. Check your email."
        )
    else:
        return error_response("Failed to send test notification", 500)


# --- Notification Messages Endpoints ---


@settings_api.get("/notifications/messages")
@safe_route("Failed to get notifications")
def get_notifications() -> Response:
    """
    Get notifications for the current user.

    Query Parameters:
        - unread_only: If true, only return unread notifications (default: false)
        - limit: Maximum number of notifications to return (default: 50, max: 200)
        - offset: Pagination offset (default: 0)

    Returns:
        JSON response with list of notifications
    """
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    user_id = _get_current_user_id()
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    limit = min(request.args.get("limit", 50, type=int), 200)
    offset = request.args.get("offset", 0, type=int)

    notifications = notifications_service.get_user_notifications(
        user_id=user_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    unread_count = notifications_service.get_unread_count(user_id)

    return success_response(
        {
            "notifications": notifications,
            "unread_count": unread_count,
            "pagination": {
                "limit": limit,
                "offset": offset,
            },
        }
    )


@settings_api.post("/notifications/messages/<int:message_id>/read")
@safe_route("Failed to mark notification as read")
def mark_notification_read(message_id: int) -> Response:
    """Mark a notification as read."""
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    success = notifications_service.mark_notification_read(message_id)
    if success:
        return success_response({"message_id": message_id}, message="Notification marked as read")
    else:
        return error_response("Failed to mark notification as read", 500)


@settings_api.post("/notifications/messages/read-all")
@safe_route("Failed to mark all notifications as read")
def mark_all_notifications_read() -> Response:
    """Mark all notifications as read for the current user."""
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    user_id = _get_current_user_id()
    count = notifications_service.mark_all_read(user_id)

    return success_response({"marked_read": count}, message=f"Marked {count} notifications as read")


@settings_api.delete("/notifications/messages/<int:message_id>")
@safe_route("Failed to delete notification")
def delete_notification(message_id: int) -> Response:
    """Delete a notification."""
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    success = notifications_service.delete_notification(message_id)
    if success:
        return success_response(None, message="Notification deleted")
    else:
        return error_response("Failed to delete notification", 500)


@settings_api.delete("/notifications/messages")
@safe_route("Failed to clear notifications")
def clear_all_notifications() -> Response:
    """Clear all notifications for the current user."""
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    user_id = _get_current_user_id()
    count = notifications_service.clear_user_notifications(user_id)

    return success_response({"deleted": count}, message=f"Deleted {count} notifications")


# --- Action Notifications Endpoints ---


@settings_api.get("/notifications/actions")
@safe_route("Failed to get pending actions")
def get_pending_actions() -> Response:
    """
    Get notifications that require user action.

    Query Parameters:
        - action_type: Filter by action type (optional)

    Returns:
        JSON response with list of notifications requiring action
    """
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    user_id = _get_current_user_id()
    action_type = request.args.get("action_type")

    actions = notifications_service.get_pending_actions(user_id, action_type)

    return success_response({"pending_actions": actions})


@settings_api.post("/notifications/actions/<int:message_id>/respond")
@safe_route("Failed to respond to action")
def respond_to_action(message_id: int) -> Response:
    """
    Respond to an action notification.

    Request Body:
        {
            "response": "confirm" | "cancel" | other action-specific response
        }

    Returns:
        JSON response indicating success
    """
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    data = request.get_json()
    if not data or "response" not in data:
        return error_response("Response is required", 400)

    response = data["response"]
    success = notifications_service.respond_to_action(message_id, response)

    if success:
        return success_response(
            {"message_id": message_id, "response": response}, message="Action recorded successfully"
        )
    else:
        return error_response("Failed to record action response", 500)


# --- Irrigation Feedback Endpoints ---


@settings_api.get("/notifications/irrigation-feedback")
@safe_route("Failed to get irrigation feedback")
def get_irrigation_feedback() -> Response:
    """
    Get pending irrigation feedback requests for the current user.

    Returns:
        JSON response with list of pending feedback requests
    """
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    user_id = _get_current_user_id()
    pending = notifications_service.get_pending_irrigation_feedback(user_id)

    return success_response({"pending_feedback": pending})


@settings_api.post("/notifications/irrigation-feedback/<int:feedback_id>")
@safe_route("Failed to submit irrigation feedback")
def submit_irrigation_feedback(feedback_id: int) -> Response:
    """
    Submit irrigation feedback.

    Request Body:
        {
            "response": "too_little" | "just_right" | "too_much" |
                "triggered_too_early" | "triggered_too_late" | "skipped",
            "notes": "Optional notes about the irrigation" (optional)
        }

    Returns:
        JSON response indicating success
    """
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    data = request.get_json()
    if not data or "response" not in data:
        return error_response("Response is required", 400)

    response = data["response"]
    valid_responses = {
        IrrigationFeedbackResponse.TOO_LITTLE,
        IrrigationFeedbackResponse.JUST_RIGHT,
        IrrigationFeedbackResponse.TOO_MUCH,
        IrrigationFeedbackResponse.TRIGGERED_TOO_EARLY,
        IrrigationFeedbackResponse.TRIGGERED_TOO_LATE,
        IrrigationFeedbackResponse.SKIPPED,
    }
    if response not in valid_responses:
        return error_response(f"Invalid response. Must be one of: {', '.join(valid_responses)}", 400)

    notes = data.get("notes")
    success = notifications_service.submit_irrigation_feedback(
        feedback_id=feedback_id,
        response=response,
        notes=notes,
    )

    if success:
        irrigation_service = getattr(container, "irrigation_workflow_service", None)
        if irrigation_service:
            try:
                irrigation_service.handle_feedback_for_feedback_id(
                    feedback_id=feedback_id,
                    feedback_response=response,
                    user_id=_get_current_user_id(),
                    notes=notes,
                )
            except Exception as e:
                logger.warning(
                    "Failed to apply irrigation feedback for feedback_id %s: %s",
                    feedback_id,
                    e,
                )
        return success_response(
            {"feedback_id": feedback_id, "response": response}, message="Feedback submitted successfully"
        )
    else:
        return error_response("Failed to submit feedback", 500)


@settings_api.get("/notifications/irrigation-feedback/history/<int:unit_id>")
@safe_route("Failed to get irrigation feedback history")
def get_irrigation_feedback_history(unit_id: int) -> Response:
    """
    Get irrigation feedback history for a growth unit.

    Query Parameters:
        - limit: Maximum number of records (default: 20)

    Returns:
        JSON response with feedback history
    """
    container = get_container()
    if not container:
        return error_response("Service container not available", 500)

    notifications_service = getattr(container, "notifications_service", None)
    if not notifications_service:
        return error_response("Notification service not available", 503)

    limit = request.args.get("limit", 20, type=int)
    history = notifications_service.get_irrigation_feedback_history(unit_id, limit)

    return success_response({"feedback_history": history})
