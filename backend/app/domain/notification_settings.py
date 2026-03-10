"""
Notification Settings Domain Object
====================================

User notification preferences dataclass.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class NotificationSettings:
    """User notification preferences."""

    user_id: int
    email_enabled: bool = False
    in_app_enabled: bool = True
    email_address: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    notify_low_battery: bool = True
    notify_plant_needs_water: bool = True
    notify_irrigation_confirm: bool = True
    notify_irrigation_recommendation: bool = True
    notify_threshold_exceeded: bool = True
    notify_device_offline: bool = True
    notify_harvest_ready: bool = True
    notify_plant_health_warning: bool = True
    irrigation_feedback_enabled: bool = True
    irrigation_feedback_delay_minutes: int = 30
    quiet_hours_enabled: bool = False
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    min_notification_interval_seconds: int = 300

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NotificationSettings":
        """Create settings from dictionary."""
        return cls(
            user_id=data.get("user_id", 1),
            email_enabled=bool(data.get("email_enabled", False)),
            in_app_enabled=bool(data.get("in_app_enabled", True)),
            email_address=data.get("email_address"),
            smtp_host=data.get("smtp_host"),
            smtp_port=int(data.get("smtp_port", 587)),
            smtp_username=data.get("smtp_username"),
            smtp_password=data.get("smtp_password_encrypted"),
            smtp_use_tls=bool(data.get("smtp_use_tls", True)),
            notify_low_battery=bool(data.get("notify_low_battery", True)),
            notify_plant_needs_water=bool(data.get("notify_plant_needs_water", True)),
            notify_irrigation_confirm=bool(data.get("notify_irrigation_confirm", True)),
            notify_irrigation_recommendation=bool(data.get("notify_irrigation_recommendation", True)),
            notify_threshold_exceeded=bool(data.get("notify_threshold_exceeded", True)),
            notify_device_offline=bool(data.get("notify_device_offline", True)),
            notify_harvest_ready=bool(data.get("notify_harvest_ready", True)),
            notify_plant_health_warning=bool(data.get("notify_plant_health_warning", True)),
            irrigation_feedback_enabled=bool(data.get("irrigation_feedback_enabled", True)),
            irrigation_feedback_delay_minutes=int(data.get("irrigation_feedback_delay_minutes", 30)),
            quiet_hours_enabled=bool(data.get("quiet_hours_enabled", False)),
            quiet_hours_start=data.get("quiet_hours_start"),
            quiet_hours_end=data.get("quiet_hours_end"),
            min_notification_interval_seconds=int(data.get("min_notification_interval_seconds", 300)),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "email_enabled": self.email_enabled,
            "in_app_enabled": self.in_app_enabled,
            "email_address": self.email_address,
            "smtp_host": self.smtp_host,
            "smtp_port": self.smtp_port,
            "smtp_username": self.smtp_username,
            "smtp_password_encrypted": self.smtp_password,
            "smtp_use_tls": self.smtp_use_tls,
            "notify_low_battery": self.notify_low_battery,
            "notify_plant_needs_water": self.notify_plant_needs_water,
            "notify_irrigation_confirm": self.notify_irrigation_confirm,
            "notify_irrigation_recommendation": self.notify_irrigation_recommendation,
            "notify_threshold_exceeded": self.notify_threshold_exceeded,
            "notify_device_offline": self.notify_device_offline,
            "notify_harvest_ready": self.notify_harvest_ready,
            "notify_plant_health_warning": self.notify_plant_health_warning,
            "irrigation_feedback_enabled": self.irrigation_feedback_enabled,
            "irrigation_feedback_delay_minutes": self.irrigation_feedback_delay_minutes,
            "quiet_hours_enabled": self.quiet_hours_enabled,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "min_notification_interval_seconds": self.min_notification_interval_seconds,
        }
