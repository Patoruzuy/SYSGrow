"""
Utility functions for managing device schedules in growth units.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DeviceSchedule:
    """Simple device schedule data holder.
    Supports scheduling any device (lights, fans, heaters, extractors, etc.)
    with start/end times and enable/disable functionality.
    """
    device_type: str  # e.g., 'light', 'fan', 'heater', 'extractor', 'pump'
    start_time: str   # HH:MM format (24-hour)
    end_time: str     # HH:MM format (24-hour)
    enabled: bool = True  # Whether this schedule is active

    def validate(self) -> bool:
        """
        Validate the schedule configuration.
        
        Returns:
            bool: True if valid, False otherwise.
        """
        if not self.device_type:
            return False
        try:
            datetime.datetime.strptime(self.start_time, "%H:%M")
            datetime.datetime.strptime(self.end_time, "%H:%M")
            return True
        except ValueError:
            return False

    def is_active_at(self, current_time: str) -> bool:
        """
        Check if device should be active at given time.
        
        Args:
            current_time: Time in HH:MM format
            
        Returns:
            True if device should be active, False otherwise
        """
        if not self.enabled:
            return False
        try:
            current = datetime.datetime.strptime(current_time, "%H:%M")
            start = datetime.datetime.strptime(self.start_time, "%H:%M")
            end = datetime.datetime.strptime(self.end_time, "%H:%M")
        except ValueError:
            return False

        if end < start:
            return current >= start or current <= end
        return start <= current <= end

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_type": self.device_type,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "enabled": self.enabled,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> Optional["DeviceSchedule"]:
        if not data or not data.get("device_type"):
            return None
        return DeviceSchedule(
            device_type=data.get("device_type", ""),
            start_time=data.get("start_time", "08:00"),
            end_time=data.get("end_time", "20:00"),
            enabled=data.get("enabled", True),
        )


def get_schedule(device_schedules: Optional[Dict[str, Any]], device_type: str) -> Optional[DeviceSchedule]:
    """
    Retrieve a schedule for a specific device type.
    Args:
        device_schedules: Dictionary of schedules keyed by device_type
        device_type: The device type to retrieve the schedule for
    Returns:
        DeviceSchedule instance or None if not found/invalid
    """
    if not device_schedules:
        return None
    schedule_dict = device_schedules.get(device_type)
    if not isinstance(schedule_dict, dict):
        return None
    return DeviceSchedule.from_dict({**schedule_dict, "device_type": device_type})

def get_light_hours(device_schedules: Optional[Dict[str, Any]]) -> int:
    """
    Calculate total light hours from the light schedule.
    Returns 0 if no valid schedule is found.
    """
    schedule = get_schedule(device_schedules, "light")
    if not schedule or not schedule.validate():
        return 0

    start = datetime.datetime.strptime(schedule.start_time, "%H:%M")
    end = datetime.datetime.strptime(schedule.end_time, "%H:%M")

    if end < start:
        delta = (end + datetime.timedelta(days=1)) - start
    else:
        delta = end - start

    return int(delta.total_seconds() // 3600)

def set_schedule(
    device_schedules: Optional[Dict[str, Any]],
    device_type: str,
    start_time: str,
    end_time: str,
    enabled: bool = True,
) -> Dict[str, Any]:
    """
    Store or update a schedule using the DeviceSchedule dataclass for validation.
    Keeps the persisted shape (dict payload keyed by device_type) used across the app.
    """
    schedule = DeviceSchedule(
        device_type=device_type,
        start_time=start_time,
        end_time=end_time,
        enabled=enabled,
    )
    if not schedule.validate():
        raise ValueError(f"Invalid schedule for {device_type}")

    schedules = dict(device_schedules) if device_schedules else {}
    payload = schedule.to_dict()
    # Persist without duplicating the outer key
    payload.pop("device_type", None)
    schedules[device_type] = payload
    return schedules


def remove_schedule(device_schedules: Optional[Dict[str, Any]], device_type: str) -> Dict[str, Any]:
    """
    Remove a schedule for a specific device type.
    """
    schedules = dict(device_schedules) if device_schedules else {}
    schedules.pop(device_type, None)
    return schedules


def all_schedules(device_schedules: Optional[Dict[str, Any]]) -> List[DeviceSchedule]:
    """
    Retrieve all device schedules as a list of DeviceSchedule instances.
    """
    if not device_schedules:
        return []
    result: List[DeviceSchedule] = []
    for device_type, payload in device_schedules.items():
        if isinstance(payload, dict):
            schedule = DeviceSchedule.from_dict({**payload, "device_type": device_type})
            if schedule:
                result.append(schedule)
    return result
