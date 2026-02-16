"""
Growth-related Enumerations
============================

This module contains all enums related to growth units and plants.
"""

from enum import Enum


class LocationType(str, Enum):
    """Location types for growth units"""

    INDOOR = "Indoor"
    OUTDOOR = "Outdoor"
    GREENHOUSE = "Greenhouse"
    HYDROPONICS = "Hydroponics"

    def __str__(self):
        return self.value


class PlantStage(str, Enum):
    """Growth stages for plants"""

    SEED = "Seed"
    GERMINATION = "Germination"  # Alias for seed stage in growth predictions
    SEEDLING = "Seedling"
    VEGETATIVE = "Vegetative"
    FLOWERING = "Flowering"
    FRUITING = "Fruiting"
    HARVEST = "Harvest"

    def __str__(self):
        return self.value


class GrowthPhase(str, Enum):
    """Phases in the growth cycle"""

    GERMINATION = "Germination"
    EARLY_GROWTH = "Early Growth"
    RAPID_GROWTH = "Rapid Growth"
    MATURATION = "Maturation"
    HARVEST_READY = "Harvest Ready"

    def __str__(self):
        return self.value


# =============================================================================
# Schedule Enumerations
# =============================================================================


class ScheduleType(str, Enum):
    """Type of device schedule.

    - SIMPLE: Basic on/off schedule with start/end time
    - INTERVAL: Repeating schedule (e.g., every 2 hours for 30 minutes)
    - PHOTOPERIOD: Light schedule with sensor integration for day/night detection
    - AUTOMATIC: Auto-generated from active plant's growth stage requirements
    """

    SIMPLE = "simple"
    INTERVAL = "interval"
    PHOTOPERIOD = "photoperiod"
    AUTOMATIC = "automatic"

    def __str__(self):
        return self.value


class ScheduleState(str, Enum):
    """State to set when schedule activates."""

    ON = "on"
    OFF = "off"

    def __str__(self):
        return self.value


class PhotoperiodSource(str, Enum):
    """Source for determining day/night in photoperiod schedules.

    - SCHEDULE: Use fixed start/end times only
    - SENSOR: Use lux sensor threshold
    - SUN_API: Use sunrise/sunset from location-based API (future)
    - HYBRID: Use sensor with schedule as fallback
    """

    SCHEDULE = "schedule"
    SENSOR = "sensor"
    SUN_API = "sun_api"
    HYBRID = "hybrid"

    def __str__(self):
        return self.value


class DayOfWeek(int, Enum):
    """Day of week (ISO weekday: Monday=0, Sunday=6)."""

    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6
