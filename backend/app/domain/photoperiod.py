"""Photoperiod domain model. 

Author: Sebastian Gomez
Date: 6/12/2024
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional, Dict, Iterable, List, Sequence, Any


def _parse_time(t: str) -> time:
    """Parse HH:MM string to time.
    Accepts 'HH:MM' or 'H:MM'.
    """
    parts = t.split(":")
    if len(parts) != 2:
        raise ValueError("time must be in HH:MM format")
    h, m = int(parts[0]), int(parts[1])
    if not (0 <= h <= 23):
        raise ValueError("hour must be between 0 and 23")
    if not (0 <= m <= 59):
        raise ValueError("minute must be between 0 and 59")
    return time(hour=h, minute=m)


def _schedule_duration_hours(start_time: str, end_time: str) -> float:
    start = _parse_time(start_time)
    end = _parse_time(end_time)

    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute

    if end_minutes < start_minutes:
        end_minutes += 24 * 60

    return (end_minutes - start_minutes) / 60.0


def _sum_mask_duration_hours(timestamps: Sequence[datetime], mask: Sequence[bool]) -> float:
    if not timestamps or not mask or len(timestamps) != len(mask):
        return 0.0

    if len(timestamps) == 1:
        return 0.0

    deltas: List[float] = []
    for i in range(len(timestamps) - 1):
        dt = timestamps[i + 1] - timestamps[i]
        deltas.append(max(dt.total_seconds(), 0.0))

    fallback = deltas[-1] if deltas else 0.0

    total_seconds = 0.0
    for i, is_day in enumerate(mask):
        if not is_day:
            continue
        seconds = deltas[i] if i < len(deltas) else fallback
        total_seconds += seconds

    return total_seconds / 3600.0


def _find_transition_time(
    timestamps: Sequence[datetime],
    mask: Sequence[bool],
    *,
    from_value: bool,
    to_value: bool,
) -> Optional[datetime]:
    if not timestamps or not mask or len(timestamps) != len(mask):
        return None

    prev = mask[0]
    for ts, value in zip(timestamps[1:], mask[1:]):
        if prev == from_value and value == to_value:
            return ts
        prev = value

    return None


def _time_of_day_offset_minutes(schedule_time: Optional[datetime], sensor_time: Optional[datetime]) -> Optional[float]:
    """
    Calculate offset in minutes between two times based on time-of-day only.
    
    This compares only the HH:MM portion, ignoring the date.
    Result is in range [-720, 720] (half day in either direction).
    Positive = sensor is later than schedule.
    """
    if schedule_time is None or sensor_time is None:
        return None
    
    # Extract time of day in minutes since midnight
    schedule_minutes = schedule_time.hour * 60 + schedule_time.minute + schedule_time.second / 60.0
    sensor_minutes = sensor_time.hour * 60 + sensor_time.minute + sensor_time.second / 60.0
    
    offset = sensor_minutes - schedule_minutes
    
    # Normalize to [-720, 720] range (handle wrap-around midnight)
    if offset > 720:
        offset -= 1440
    elif offset < -720:
        offset += 1440
    
    return offset


@dataclass
class Photoperiod:
    """Determine day/night using a fixed schedule and optionally a light sensor.

    - schedule_day_start/schedule_day_end: 'HH:MM' strings that define the scheduled day period.
    - sensor_threshold: numeric threshold (lux or relative) above which the sensor reports "day".
    - schedule_enabled: whether the light schedule should be used.
    - greenhouse_outside: when True and a sensor value is provided, the sensor result takes precedence.
    - sensor_enabled: whether the light sensor should be used (if a value is provided).
    """

    schedule_day_start: str = "06:00"
    schedule_day_end: str = "18:00"
    schedule_enabled: bool = True
    sensor_threshold: float = 100.0
    greenhouse_outside: bool = False
    sensor_enabled: bool = True

    @classmethod
    def from_schedule(cls, sched: Any) -> Photoperiod:
        """Create a Photoperiod instance from a DeviceSchedule."""
        p = cls()
        p.schedule_day_start = sched.start_time
        p.schedule_day_end = sched.end_time
        p.schedule_enabled = sched.enabled
        return p

    def schedule_duration_hours(self) -> float:
        return _schedule_duration_hours(self.schedule_day_start, self.schedule_day_end)

    def is_schedule_day(self, ts: datetime) -> bool:
        start = _parse_time(self.schedule_day_start)
        end = _parse_time(self.schedule_day_end)
        local_ts = ts.astimezone() if ts.tzinfo is not None else ts
        t = local_ts.time()
        if start <= end:
            return start <= t < end
        # wraps midnight
        return t >= start or t < end

    def is_sensor_day(self, sensor_value: Optional[float]) -> Optional[bool]:
        if not self.sensor_enabled:
            return None
        if sensor_value is None:
            return None
        return sensor_value >= self.sensor_threshold

    def schedule_mask(self, timestamps: Iterable[datetime]) -> List[bool]:
        return [self.is_schedule_day(ts) for ts in timestamps]

    def sensor_mask(self, sensor_values: Iterable[Optional[float]]) -> List[Optional[bool]]:
        return [self.is_sensor_day(value) for value in sensor_values]

    def resolve_mask(
        self,
        timestamps: Sequence[datetime],
        *,
        sensor_values: Optional[Sequence[Optional[float]]] = None,
    ) -> Dict[str, Any]:
        """Resolve a day/night mask for a timeseries.

        Returns a dict with keys:
        - schedule_mask: List[bool]
        - sensor_mask: Optional[List[Optional[bool]]]
        - final_mask: List[bool]
        - agreement_rate: Optional[float] (0-1, None if no sensor values)
        """
        schedule_mask = self.schedule_mask(timestamps)

        sensor_mask: Optional[List[Optional[bool]]] = None
        if sensor_values is not None:
            sensor_mask = self.sensor_mask(sensor_values)

        final_mask: List[bool] = []
        agreements = 0
        comparable = 0

        for i, schedule_day in enumerate(schedule_mask):
            sensor_day = sensor_mask[i] if sensor_mask is not None else None

            if self.greenhouse_outside and sensor_day is not None:
                final = bool(sensor_day)
            elif self.schedule_enabled:
                final = bool(schedule_day)
            elif sensor_day is not None:
                final = bool(sensor_day)
            else:
                final = bool(schedule_day)

            final_mask.append(final)

            if sensor_day is not None:
                comparable += 1
                if bool(sensor_day) == bool(schedule_day):
                    agreements += 1

        agreement_rate = None
        if comparable:
            agreement_rate = agreements / comparable

        return {
            "schedule_mask": schedule_mask,
            "sensor_mask": sensor_mask,
            "final_mask": final_mask,
            "agreement_rate": agreement_rate,
        }

    def analyze_alignment(
        self,
        timestamps: Sequence[datetime],
        sensor_values: Sequence[Optional[float]],
    ) -> Dict[str, Optional[float]]:
        """
        Compare schedule vs sensor day/night over a window.

        Intended for diagnostics/feature engineering (agreement + transition offsets).
        Returns only numeric values (or None when unavailable).
        """
        resolved = self.resolve_mask(timestamps, sensor_values=sensor_values)
        schedule_mask: List[bool] = resolved["schedule_mask"]

        sensor_mask_opt = resolved.get("sensor_mask")
        if not sensor_mask_opt:
            return {
                "agreement_rate": None,
                "schedule_light_hours": None,
                "sensor_light_hours": None,
                "start_offset_minutes": None,
                "end_offset_minutes": None,
            }

        sensor_mask: List[Optional[bool]] = sensor_mask_opt
        sensor_mask_bool = [bool(v) if v is not None else False for v in sensor_mask]

        schedule_light_hours = _sum_mask_duration_hours(timestamps, schedule_mask)
        sensor_light_hours = _sum_mask_duration_hours(timestamps, sensor_mask_bool)

        schedule_start = _find_transition_time(timestamps, schedule_mask, from_value=False, to_value=True)
        schedule_end = _find_transition_time(timestamps, schedule_mask, from_value=True, to_value=False)
        sensor_start = _find_transition_time(timestamps, sensor_mask_bool, from_value=False, to_value=True)
        sensor_end = _find_transition_time(timestamps, sensor_mask_bool, from_value=True, to_value=False)

        # Use time-of-day comparison to avoid cross-day offset errors
        start_offset_minutes = _time_of_day_offset_minutes(schedule_start, sensor_start)
        end_offset_minutes = _time_of_day_offset_minutes(schedule_end, sensor_end)

        return {
            "agreement_rate": resolved.get("agreement_rate"),
            "schedule_light_hours": schedule_light_hours,
            "sensor_light_hours": sensor_light_hours,
            "start_offset_minutes": start_offset_minutes,
            "end_offset_minutes": end_offset_minutes,
        }

    def evaluate(self, ts: Optional[datetime] = None, sensor_value: Optional[float] = None) -> Dict[str, Optional[object]]:
        """Evaluate day/night and return details.

        Returns a dict with keys:
        - schedule: bool (day according to schedule)
        - sensor: Optional[bool] (day according to sensor or None if no sensor_value)
        - final: bool (the value to use for plants)
        - correlated: Optional[bool] (whether schedule and sensor agree, None if sensor missing)
        """
        if ts is None:
            ts = datetime.now()
        schedule_day = self.is_schedule_day(ts)
        sensor_day = self.is_sensor_day(sensor_value)

        if self.greenhouse_outside and sensor_day is not None:
            final = sensor_day
        elif self.schedule_enabled:
            final = schedule_day
        elif sensor_day is not None:
            final = sensor_day
        else:
            final = schedule_day

        correlated = None
        if sensor_day is not None:
            correlated = (sensor_day == schedule_day)

        return {
            "schedule": schedule_day,
            "sensor": sensor_day,
            "final": final,
            "correlated": correlated,
        }


__all__ = ["Photoperiod"]
