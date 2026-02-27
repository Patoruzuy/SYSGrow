"""
Schedule Domain Entity
======================

Centralized schedule entity supporting:
- Multiple schedules per device type
- Enable/disable without deletion
- Photoperiod integration for lights
- Future sun times API integration
- Days of week filtering
- Priority for conflict resolution

Author: Sebastian Gomez
Date: January 2026
"""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

from app.enums.growth import (
    PhotoperiodSource,
    ScheduleState,
    ScheduleType,
)

logger = logging.getLogger(__name__)


@dataclass
class SunTimesConfig:
    """Configuration for sun-based photoperiod scheduling.

    This is a placeholder for future integration with a sun times API
    that calculates sunrise, sunset, dawn, dusk based on location.

    Attributes:
        latitude: User's latitude for sun calculations
        longitude: User's longitude for sun calculations
        timezone: Timezone string (e.g., 'America/New_York')
        dawn_offset_minutes: Minutes before sunrise to start (negative = earlier)
        dusk_offset_minutes: Minutes after sunset to end (positive = later)
        use_civil_twilight: Use civil twilight instead of actual sunrise/sunset
    """

    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    dawn_offset_minutes: int = 0
    dusk_offset_minutes: int = 0
    use_civil_twilight: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timezone": self.timezone,
            "dawn_offset_minutes": self.dawn_offset_minutes,
            "dusk_offset_minutes": self.dusk_offset_minutes,
            "use_civil_twilight": self.use_civil_twilight,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> "SunTimesConfig" | None:
        if not data:
            return None
        return SunTimesConfig(
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            timezone=data.get("timezone"),
            dawn_offset_minutes=data.get("dawn_offset_minutes", 0),
            dusk_offset_minutes=data.get("dusk_offset_minutes", 0),
            use_civil_twilight=data.get("use_civil_twilight", False),
        )

    def is_configured(self) -> bool:
        """Check if sun times config has valid coordinates."""
        return self.latitude is not None and self.longitude is not None


@dataclass
class PhotoperiodConfig:
    """Configuration for photoperiod-aware light schedules.

    Attributes:
        source: How to determine day/night (schedule, sensor, sun_api, hybrid)
        sensor_threshold: Lux threshold above which is considered "day"
        sensor_tolerance: Lux tolerance around threshold to avoid rapid toggling
        prefer_sensor: When True, sensor overrides schedule when available
        sun_times: Configuration for sun API integration
        min_light_hours: Minimum light hours to maintain (for supplemental lighting)
        max_light_hours: Maximum light hours allowed
    """

    source: PhotoperiodSource = PhotoperiodSource.SCHEDULE
    sensor_threshold: float = 100.0
    sensor_tolerance: float = 10.0
    prefer_sensor: bool = False
    sun_times: SunTimesConfig | None = None
    min_light_hours: float | None = None
    max_light_hours: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.value,
            "sensor_threshold": self.sensor_threshold,
            "sensor_tolerance": self.sensor_tolerance,
            "prefer_sensor": self.prefer_sensor,
            "sun_times": self.sun_times.to_dict() if self.sun_times else None,
            "min_light_hours": self.min_light_hours,
            "max_light_hours": self.max_light_hours,
        }

    @staticmethod
    def from_dict(data: dict[str, Any] | None) -> "PhotoperiodConfig" | None:
        if not data:
            return None
        return PhotoperiodConfig(
            source=PhotoperiodSource(data.get("source", "schedule")),
            sensor_threshold=data.get("sensor_threshold", 100.0),
            sensor_tolerance=data.get("sensor_tolerance", 10.0),
            prefer_sensor=data.get("prefer_sensor", False),
            sun_times=SunTimesConfig.from_dict(data.get("sun_times")),
            min_light_hours=data.get("min_light_hours"),
            max_light_hours=data.get("max_light_hours"),
        )


@dataclass
class Schedule:
    """
    Centralized schedule entity for device control.

    Supports:
    - Multiple schedules per device type (e.g., fan cycles every 2 hours)
    - Enable/disable without deletion
    - Days of week filtering
    - Photoperiod integration for light schedules
    - Optional actuator linking
    - Priority for conflict resolution

    Attributes:
        schedule_id: Unique identifier (None for new schedules)
        unit_id: Growth unit this schedule belongs to
        name: Human-readable schedule name
        device_type: Type of device ('light', 'fan', 'pump', etc.)
        actuator_id: Optional link to specific actuator
        schedule_type: Type of schedule (simple, interval, photoperiod, automatic)
        interval_minutes: Interval minutes for repeating schedules (optional)
        duration_minutes: Duration minutes per interval cycle (optional)
        start_time: Schedule start time in HH:MM format
        end_time: Schedule end time in HH:MM format
        days_of_week: List of active days (0=Monday, 6=Sunday)
        enabled: Whether schedule is active
        state_when_active: State to set when active ('on', 'off')
        value: Optional value for dimmers/PWM (0-100)
        photoperiod: Photoperiod configuration for light schedules
        priority: Higher priority schedules take precedence (default 0)
        metadata: Additional configuration data
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    # Identity
    schedule_id: int | None = None
    unit_id: int = 0
    name: str = ""

    # Device targeting
    device_type: str = ""
    actuator_id: int | None = None

    # Schedule type
    schedule_type: ScheduleType = ScheduleType.SIMPLE
    interval_minutes: int | None = None
    duration_minutes: int | None = None

    # Time configuration
    start_time: str = "08:00"
    end_time: str = "20:00"
    days_of_week: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])

    # Control parameters
    enabled: bool = True
    state_when_active: ScheduleState = ScheduleState.ON
    value: float | None = None

    # Photoperiod (for light schedules)
    photoperiod: PhotoperiodConfig | None = None

    # Priority for conflict resolution
    priority: int = 0

    # Metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime.datetime = field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = field(default_factory=datetime.datetime.now)

    def __post_init__(self):
        """Ensure enums are proper types after initialization."""
        if isinstance(self.schedule_type, str):
            self.schedule_type = ScheduleType(self.schedule_type)
        if isinstance(self.state_when_active, str):
            self.state_when_active = ScheduleState(self.state_when_active)

    def validate(self) -> bool:
        """
        Validate the schedule configuration.

        Returns:
            bool: True if valid, False otherwise.
        """
        if not self.device_type:
            return False
        if self.unit_id <= 0:
            return False
        try:
            self._parse_time(self.start_time)
            self._parse_time(self.end_time)
        except ValueError:
            return False

        if self.schedule_type == ScheduleType.INTERVAL:
            try:
                interval = int(self.interval_minutes or 0)
                duration = int(self.duration_minutes or 0)
            except (TypeError, ValueError):
                return False
            if interval <= 0 or duration <= 0:
                return False
            if duration > interval:
                return False

        return True

    @staticmethod
    def _parse_time(time_str: str) -> datetime.time:
        """Parse HH:MM string to time object."""
        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError("time must be in HH:MM format")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23):
            raise ValueError("hour must be between 0 and 23")
        if not (0 <= m <= 59):
            raise ValueError("minute must be between 0 and 59")
        return datetime.time(hour=h, minute=m)

    def is_active_at(
        self,
        check_time: datetime.datetime | None = None,
        *,
        timezone: str | None = None,
    ) -> bool:
        """
        Check if schedule should be active at given time.

        Handles:
        - Schedules that span midnight
        - Days of week filtering
        - Enabled/disabled state

        Args:
            check_time: Time to check (defaults to now)
            timezone: Optional IANA timezone string for local evaluation

        Returns:
            True if schedule should be active, False otherwise
        """
        if not self.enabled:
            return False

        now = self._normalize_check_time(check_time, timezone)

        minutes_since_start = self._minutes_since_start(now)
        if minutes_since_start is None:
            return False

        if self.schedule_type == ScheduleType.INTERVAL:
            try:
                interval = int(self.interval_minutes or 0)
                duration = int(self.duration_minutes or 0)
            except (TypeError, ValueError):
                return False
            if interval <= 0 or duration <= 0:
                return False
            return (minutes_since_start % interval) < duration

        return True

    def _minutes_since_start(self, now: datetime.datetime) -> int | None:
        """Return minutes since schedule start if within window; else None."""
        weekday = now.weekday()  # 0=Monday

        try:
            start = self._parse_time(self.start_time)
            end = self._parse_time(self.end_time)
        except ValueError:
            return None

        start_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute
        now_minutes = now.hour * 60 + now.minute

        if start_minutes == end_minutes:
            if weekday not in self.days_of_week:
                return None
            return (now_minutes - start_minutes) % (24 * 60)

        if start_minutes < end_minutes:
            if weekday not in self.days_of_week:
                return None
            if not (start_minutes <= now_minutes < end_minutes):
                return None
            return now_minutes - start_minutes

        if now_minutes >= start_minutes:
            if weekday not in self.days_of_week:
                return None
            return now_minutes - start_minutes

        prev_day = (weekday - 1) % 7
        if prev_day not in self.days_of_week:
            return None
        return (24 * 60 - start_minutes) + now_minutes

    @staticmethod
    def _resolve_timezone(timezone: str | None) -> ZoneInfo | None:
        if not timezone:
            return None
        try:
            return ZoneInfo(timezone)
        except Exception:
            logger.warning("Invalid timezone '%s' for schedule evaluation", timezone)
            return None

    @classmethod
    def _normalize_check_time(
        cls,
        check_time: datetime.datetime | None,
        timezone: str | None,
    ) -> datetime.datetime:
        tz = cls._resolve_timezone(timezone)
        if check_time is None:
            return datetime.datetime.now(tz) if tz else datetime.datetime.now()
        if tz:
            if check_time.tzinfo is None:
                return check_time.replace(tzinfo=tz)
            return check_time.astimezone(tz)
        return check_time

    def duration_hours(self) -> float:
        """Calculate schedule duration in hours."""
        try:
            start = self._parse_time(self.start_time)
            end = self._parse_time(self.end_time)
        except ValueError:
            return 0.0

        start_minutes = start.hour * 60 + start.minute
        end_minutes = end.hour * 60 + end.minute

        if end_minutes < start_minutes:
            end_minutes += 24 * 60  # Add 24 hours for cross-midnight

        return (end_minutes - start_minutes) / 60.0

    def to_dict(self) -> dict[str, Any]:
        """Convert schedule to dictionary for serialization."""
        return {
            "schedule_id": self.schedule_id,
            "unit_id": self.unit_id,
            "name": self.name,
            "device_type": self.device_type,
            "actuator_id": self.actuator_id,
            "schedule_type": self.schedule_type.value,
            "interval_minutes": self.interval_minutes,
            "duration_minutes": self.duration_minutes,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "days_of_week": self.days_of_week,
            "enabled": self.enabled,
            "state_when_active": self.state_when_active.value,
            "value": self.value,
            "photoperiod": self.photoperiod.to_dict() if self.photoperiod else None,
            "priority": self.priority,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Schedule":
        """Create Schedule from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.datetime.now()

        updated_at = data.get("updated_at")
        if isinstance(updated_at, str):
            updated_at = datetime.datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.datetime.now()

        return Schedule(
            schedule_id=data.get("schedule_id"),
            unit_id=data.get("unit_id", 0),
            name=data.get("name", ""),
            device_type=data.get("device_type", ""),
            actuator_id=data.get("actuator_id"),
            schedule_type=ScheduleType(data.get("schedule_type", "simple")),
            interval_minutes=data.get("interval_minutes"),
            duration_minutes=data.get("duration_minutes"),
            start_time=data.get("start_time", "08:00"),
            end_time=data.get("end_time", "20:00"),
            days_of_week=data.get("days_of_week", [0, 1, 2, 3, 4, 5, 6]),
            enabled=data.get("enabled", True),
            state_when_active=ScheduleState(data.get("state_when_active", "on")),
            value=data.get("value"),
            photoperiod=PhotoperiodConfig.from_dict(data.get("photoperiod")),
            priority=data.get("priority", 0),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Schedule):
            return False
        if self.schedule_id and other.schedule_id:
            return self.schedule_id == other.schedule_id
        return (
            self.unit_id == other.unit_id
            and self.device_type == other.device_type
            and self.start_time == other.start_time
            and self.end_time == other.end_time
        )

    def __hash__(self) -> int:
        return hash((self.schedule_id, self.unit_id, self.device_type, self.start_time, self.end_time))
