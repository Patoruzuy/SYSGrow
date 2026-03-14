"""
Schedule Domain Module
======================

Centralized schedule domain model for managing device schedules.

This module provides:
- Schedule: Main schedule entity supporting multiple schedules per device
- ScheduleRepository: Protocol for schedule persistence
- Photoperiod integration for light-specific schedules

Author: Sebastian Gomez
Date: January 2026
"""
from app.domain.schedules.schedule_entity import (
    Schedule,
    PhotoperiodConfig,
    SunTimesConfig,
)
from app.domain.schedules.repository import ScheduleRepository

__all__ = [
    "Schedule",
    "PhotoperiodConfig",
    "SunTimesConfig",
    "ScheduleRepository",
]
