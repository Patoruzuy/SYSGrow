"""
Schedule Repository Protocol
=============================

Defines the interface for schedule persistence.
Implementations can use SQLite, PostgreSQL, or other storage.

Author: Sebastian Gomez
Date: January 2026
"""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol

from app.domain.schedules.schedule_entity import Schedule


class ScheduleRepository(Protocol):
    """Protocol for schedule persistence operations."""

    @abstractmethod
    def create(self, schedule: Schedule) -> Schedule:
        """
        Create a new schedule.

        Args:
            schedule: Schedule to create (schedule_id should be None)

        Returns:
            Created schedule with assigned schedule_id
        """
        ...

    @abstractmethod
    def get_by_id(self, schedule_id: int) -> Schedule | None:
        """
        Get schedule by ID.

        Args:
            schedule_id: Schedule ID

        Returns:
            Schedule if found, None otherwise
        """
        ...

    @abstractmethod
    def get_by_unit(self, unit_id: int) -> list[Schedule]:
        """
        Get all schedules for a growth unit.

        Args:
            unit_id: Growth unit ID

        Returns:
            List of schedules for the unit
        """
        ...

    @abstractmethod
    def get_by_device_type(self, unit_id: int, device_type: str) -> list[Schedule]:
        """
        Get all schedules for a specific device type in a unit.

        Args:
            unit_id: Growth unit ID
            device_type: Device type (e.g., 'light', 'fan')

        Returns:
            List of schedules for the device type
        """
        ...

    @abstractmethod
    def get_by_actuator(self, actuator_id: int) -> list[Schedule]:
        """
        Get all schedules for a specific actuator.

        Args:
            actuator_id: Actuator ID

        Returns:
            List of schedules for the actuator
        """
        ...

    @abstractmethod
    def update(self, schedule: Schedule) -> Schedule | None:
        """
        Update an existing schedule.

        Args:
            schedule: Schedule with updated values (must have schedule_id)

        Returns:
            Updated schedule if found, None otherwise
        """
        ...

    @abstractmethod
    def delete(self, schedule_id: int) -> bool:
        """
        Delete a schedule.

        Args:
            schedule_id: Schedule ID

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    def delete_by_unit(self, unit_id: int) -> int:
        """
        Delete all schedules for a growth unit.

        Args:
            unit_id: Growth unit ID

        Returns:
            Number of schedules deleted
        """
        ...

    @abstractmethod
    def set_enabled(self, schedule_id: int, enabled: bool) -> bool:
        """
        Enable or disable a schedule.

        Args:
            schedule_id: Schedule ID
            enabled: True to enable, False to disable

        Returns:
            True if updated, False if not found
        """
        ...

    @abstractmethod
    def get_active_schedules(self, unit_id: int) -> list[Schedule]:
        """
        Get schedules that are currently active (enabled and within time window).

        Args:
            unit_id: Growth unit ID

        Returns:
            List of currently active schedules
        """
        ...
