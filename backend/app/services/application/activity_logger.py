"""Activity logging service for tracking system events and user actions.

This service uses EventBus for activity events and logs to a file for efficiency.
Database logging is reserved for critical auditable events only.
"""

import json
import logging
from typing import Any

from app.utils.event_bus import EventBus
from app.utils.time import iso_now
from infrastructure.database.repositories.activity_log import ActivityRepository

logger = logging.getLogger(__name__)

# Configure activity file logger
activity_file_logger = logging.getLogger("activity_log")
activity_file_logger.setLevel(logging.INFO)
activity_handler = logging.FileHandler("activity.log")
activity_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
activity_file_logger.addHandler(activity_handler)


class ActivityLogger:
    """Service for logging system activities and events via EventBus."""

    # Activity type constants (map to ActivityEvent enum)
    PLANT_CREATED = "plant_added"
    PLANT_ADDED = PLANT_CREATED  # Backward-compatible alias
    PLANT_REMOVED = "plant_removed"
    PLANT_UPDATED = "plant_updated"
    UNIT_CREATED = "unit_created"
    UNIT_UPDATED = "unit_updated"
    UNIT_DELETED = "unit_deleted"
    DEVICE_CONNECTED = "device_connected"
    DEVICE_DISCONNECTED = "device_disconnected"
    DEVICE_CONFIGURED = "device_configured"
    HARVEST_RECORDED = "harvest_recorded"
    HARVEST_UPDATED = "harvest_updated"
    THRESHOLD_OVERRIDE = "threshold_override"
    MANUAL_CONTROL = "manual_control"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"

    # Severity levels
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    # Events that should be stored in database (critical audit trail)
    DB_LOGGED_EVENTS = {
        PLANT_REMOVED,
        UNIT_DELETED,
        SYSTEM_STARTUP,
        SYSTEM_SHUTDOWN,
        USER_LOGIN,
        USER_LOGOUT,
        THRESHOLD_OVERRIDE,
    }

    def __init__(self, repo: ActivityRepository):
        """Initialize the activity logger.

        Args:
            repo: ActivityRepository instance (for critical events only)
        """
        self.event_bus = EventBus()
        self._repo = repo

    def log_activity(
        self,
        activity_type: str,
        description: str,
        user_id: int | None = None,
        severity: str = INFO,
        entity_type: str | None = None,
        entity_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        """Log an activity event via EventBus and optionally to database.

        Args:
            activity_type: Type of activity (use class constants)
            description: Human-readable description of the activity
            user_id: ID of the user who performed the action (optional)
            severity: Severity level (info, warning, error)
            entity_type: Type of entity affected (e.g., 'plant', 'sensor', 'actuator')
            entity_id: ID of the affected entity
            metadata: Additional metadata as a dictionary

        Returns:
            int: The ID of the created activity log entry (0 if only file logged)
        """
        # Validate inputs
        valid_severities = {self.INFO, self.WARNING, self.ERROR}
        if severity not in valid_severities:
            severity = self.INFO

        # Build activity data
        activity_data = {
            "timestamp": iso_now(),
            "user_id": user_id,
            "activity_type": activity_type,
            "severity": severity,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "description": description,
            "metadata": metadata or {},
        }

        # Log to file (always)
        log_message = f"[{severity.upper()}] {activity_type}: {description}"
        if entity_type and entity_id:
            log_message += f" (entity: {entity_type}#{entity_id})"
        if user_id:
            log_message += f" [user:{user_id}]"
        if metadata:
            log_message += f" | {json.dumps(metadata)}"

        if severity == self.ERROR:
            activity_file_logger.error(log_message)
        elif severity == self.WARNING:
            activity_file_logger.warning(log_message)
        else:
            activity_file_logger.info(log_message)

        # Publish to EventBus
        try:
            event_key = f"activity.{activity_type}"
            self.event_bus.publish(event_key, activity_data)
        except Exception as e:
            logger.warning("Failed to publish activity event: %s", e)

        # Log to database only for critical events
        activity_id = 0
        if activity_type in self.DB_LOGGED_EVENTS:
            try:
                activity_id = self._log_to_database(activity_data)
            except Exception as e:
                logger.error("Failed to log critical activity to database: %s", e)

        return activity_id

    def _log_to_database(self, activity_data: dict[str, Any]) -> int:
        """Store critical activity in database for audit trail."""
        json.dumps(activity_data.get("metadata", {})) if activity_data.get("metadata") else None

        try:
            aid = self._repo.insert(activity_data)
            return aid or 0
        except Exception as e:
            logger.error("Database logging failed: %s", e)
            return 0

    def get_recent_activities(
        self,
        limit: int = 50,
        activity_type: str | None = None,
        severity: str | None = None,
        user_id: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent activity logs from database (critical events only).

        Note: This only returns database-logged activities.
        For full activity history, read the activity.log file.

        Args:
            limit: Maximum number of activities to return
            activity_type: Filter by activity type (optional)
            severity: Filter by severity level (optional)
            user_id: Filter by user ID (optional)

        Returns:
            List of activity dictionaries
        """
        query = "SELECT * FROM ActivityLog WHERE 1=1"
        params = []

        if activity_type:
            query += " AND activity_type = ?"
            params.append(activity_type)

        if severity:
            query += " AND severity = ?"
            params.append(severity)

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        try:
            return self._repo.recent(limit=limit, activity_type=activity_type, severity=severity, user_id=user_id)
        except Exception as e:
            logger.error("Failed to retrieve activities: %s", e)
            return []

    def get_activities_for_entity(self, entity_type: str, entity_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """Get activities related to a specific entity (from database only)."""
        try:
            return self._repo.for_entity(entity_type, entity_id, limit)
        except Exception as e:
            logger.error("Failed to retrieve entity activities: %s", e)
            return []

    def get_activity_statistics(self) -> dict[str, Any]:
        """Get statistics about system activities (from database only)."""
        try:
            return self._repo.statistics()
        except Exception as e:
            logger.error("Failed to retrieve activity statistics: %s", e)
            return {"total": 0, "by_type": {}, "by_severity": {}}


# ---------------------------------------------------------------------------
# Convenience helper to reduce boilerplate in services
# ---------------------------------------------------------------------------


def log_if_available(
    activity_logger: ActivityLogger | None,
    activity_type: str,
    description: str,
    **kwargs,
) -> None:
    """Log an activity only when an ``ActivityLogger`` is available.

    Eliminates the repetitive pattern::

        if self.activity_logger:
            self.activity_logger.log_activity(activity_type, description, ...)

    Extra keyword arguments are forwarded to
    :meth:`ActivityLogger.log_activity` (``user_id``, ``severity``,
    ``entity_type``, ``entity_id``, ``metadata``).
    """
    if activity_logger is not None:
        activity_logger.log_activity(activity_type, description, **kwargs)
