"""
Psychrometric Calculations
==========================

Pure utility functions for air-science derived metrics used in grow environments.

Functions:
- calculate_vpd_kpa: Vapor Pressure Deficit
- calculate_dew_point_c: Dew point temperature
- calculate_heat_index_c: Heat index (apparent temperature)
- calculate_svp_kpa: Saturation vapor pressure (helper)

These are stateless calculations suitable for:
- Enrichment processors (add derived metrics to sensor readings)
- Dashboard/API endpoints (compute on-demand)
- Analytics (historical calculations)

Author: Sebastian Gomez
Date: January 2026
"""
from __future__ import annotations

import math
from numbers import Number
from typing import Any, Dict, Optional, TypeVar, overload, Sequence

_ArrayLike = TypeVar("_ArrayLike")


# =============================================================================
# Core Calculations (scalar-safe, no numpy required for normal runtime)
# =============================================================================

def calculate_svp_kpa(temperature_c: float) -> float:
    """
    Calculate Saturation Vapor Pressure (SVP) in kPa using Magnus formula.
    
    SVP = 0.6108 × exp(17.27 × T / (T + 237.3))
    
    Args:
        temperature_c: Temperature in Celsius
        
    Returns:
        Saturation vapor pressure in kPa
    """
    return 0.6108 * math.exp((17.27 * temperature_c) / (temperature_c + 237.3))


@overload
def calculate_vpd_kpa(temperature_c: None, relative_humidity: object) -> None: ...
@overload
def calculate_vpd_kpa(temperature_c: object, relative_humidity: None) -> None: ...
@overload
def calculate_vpd_kpa(temperature_c: float, relative_humidity: float) -> float: ...
@overload
def calculate_vpd_kpa(temperature_c: _ArrayLike, relative_humidity: _ArrayLike) -> _ArrayLike: ...

def calculate_vpd_kpa(temperature_c, relative_humidity):
    """
    Calculate Vapor Pressure Deficit (VPD) in kPa.

    VPD = SVP × (1 - RH/100)
    
    Optimal VPD ranges for plants:
    - Seedlings/clones: 0.4-0.8 kPa
    - Vegetative: 0.8-1.2 kPa
    - Flowering: 1.0-1.5 kPa
    
    Args:
        temperature_c: Temperature in Celsius
        relative_humidity: Relative humidity percentage (0-100)
        
    Returns:
        VPD in kPa, or None if inputs are None
    """
    if temperature_c is None or relative_humidity is None:
        return None

    if isinstance(temperature_c, Number) and isinstance(relative_humidity, Number):
        temp_c = float(temperature_c)
        humidity = float(relative_humidity)
        svp = calculate_svp_kpa(temp_c)
        return svp * (1 - humidity / 100.0)

    # Vectorized path for numpy/pandas
    import numpy as np
    temp = np.asarray(temperature_c) if isinstance(temperature_c, (list, tuple)) else temperature_c
    humidity = np.asarray(relative_humidity) if isinstance(relative_humidity, (list, tuple)) else relative_humidity
    svp = 0.6108 * np.exp((17.27 * temp) / (temp + 237.3))
    return svp * (1 - humidity / 100.0)


@overload
def calculate_dew_point_c(temperature_c: None, relative_humidity: object) -> None: ...
@overload
def calculate_dew_point_c(temperature_c: object, relative_humidity: None) -> None: ...
@overload
def calculate_dew_point_c(temperature_c: float, relative_humidity: float) -> float: ...

def calculate_dew_point_c(temperature_c, relative_humidity):
    """
    Calculate dew point temperature in Celsius using Magnus-Tetens approximation.
    
    Dew point is the temperature at which air becomes saturated and condensation begins.
    Important for:
    - Preventing mold/mildew (keep leaf temp above dew point)
    - Understanding transpiration limits
    
    Formula:
        gamma = (a * T) / (b + T) + ln(RH/100)
        Td = (b * gamma) / (a - gamma)
        
    Where a = 17.27, b = 237.3 (Magnus constants)
    
    Args:
        temperature_c: Temperature in Celsius
        relative_humidity: Relative humidity percentage (0-100)
        
    Returns:
        Dew point in Celsius, or None if inputs are None
    """
    if temperature_c is None or relative_humidity is None:
        return None
    
    temp_c = float(temperature_c)
    humidity = float(relative_humidity)
    
    # Clamp humidity to valid range
    if humidity <= 0:
        return None
    humidity = min(humidity, 100.0)
    
    a = 17.27
    b = 237.3
    
    gamma = (a * temp_c) / (b + temp_c) + math.log(humidity / 100.0)
    dew_point = (b * gamma) / (a - gamma)
    
    return round(dew_point, 2)


@overload
def calculate_heat_index_c(temperature_c: None, relative_humidity: object) -> None: ...
@overload
def calculate_heat_index_c(temperature_c: object, relative_humidity: None) -> None: ...
@overload
def calculate_heat_index_c(temperature_c: float, relative_humidity: float) -> float: ...

def calculate_heat_index_c(temperature_c, relative_humidity):
    """
    Calculate heat index (apparent temperature) in Celsius.
    
    Uses the Rothfusz regression equation (NOAA).
    Heat index represents "feels like" temperature accounting for humidity.
    
    Important for:
    - Plant stress assessment (high heat index = transpiration stress)
    - Worker safety in grow environments
    
    Note: Only valid for temperatures >= 27°C (80°F) and RH >= 40%.
    Below these thresholds, returns the actual temperature.
    
    Args:
        temperature_c: Temperature in Celsius
        relative_humidity: Relative humidity percentage (0-100)
        
    Returns:
        Heat index in Celsius, or None if inputs are None
    """
    if temperature_c is None or relative_humidity is None:
        return None
    
    temp_c = float(temperature_c)
    humidity = float(relative_humidity)
    
    # Heat index formula is only valid above ~27°C and 40% RH
    if temp_c < 27.0 or humidity < 40.0:
        return round(temp_c, 2)
    
    # Convert to Fahrenheit for Rothfusz equation
    temp_f = temp_c * 9/5 + 32
    
    # Rothfusz regression coefficients
    c1 = -42.379
    c2 = 2.04901523
    c3 = 10.14333127
    c4 = -0.22475541
    c5 = -0.00683783
    c6 = -0.05481717
    c7 = 0.00122874
    c8 = 0.00085282
    c9 = -0.00000199
    
    hi_f = (c1 + c2 * temp_f + c3 * humidity +
            c4 * temp_f * humidity +
            c5 * temp_f ** 2 +
            c6 * humidity ** 2 +
            c7 * temp_f ** 2 * humidity +
            c8 * temp_f * humidity ** 2 +
            c9 * temp_f ** 2 * humidity ** 2)
    
    # Adjustments for edge cases
    if humidity < 13 and 80 <= temp_f <= 112:
        adjustment = ((13 - humidity) / 4) * math.sqrt((17 - abs(temp_f - 95)) / 17)
        hi_f -= adjustment
    elif humidity > 85 and 80 <= temp_f <= 87:
        adjustment = ((humidity - 85) / 10) * ((87 - temp_f) / 5)
        hi_f += adjustment
    
    # Convert back to Celsius
    hi_c = (hi_f - 32) * 5/9
    return round(hi_c, 2)


def compute_derived_metrics(
    temperature_c: Optional[float],
    relative_humidity: Optional[float],
) -> Dict[str, Optional[float]]:
    """
    Compute all derived psychrometric metrics from temperature and humidity.
    
    This is the main entry point for enrichment processors.
    
    Args:
        temperature_c: Temperature in Celsius
        relative_humidity: Relative humidity percentage (0-100)
        
    Returns:
        Dictionary with keys: vpd_kpa, dew_point_c, heat_index_c
        Values are None if inputs are invalid.
    """
    return {
        "vpd_kpa": calculate_vpd_kpa(temperature_c, relative_humidity),
        "dew_point_c": calculate_dew_point_c(temperature_c, relative_humidity),
        "heat_index_c": calculate_heat_index_c(temperature_c, relative_humidity),
    }


# =============================================================================
# Advanced Analytics (require pandas, for historical data processing)
# =============================================================================

def calculate_dif_c(
    temperature_c,
    *,
    day_start: str = "06:00",
    day_end: str = "18:00",
    lux_values: Optional[Sequence[Optional[float]]] = None,
    lux_threshold: float = 100.0,
    prefer_sensor: bool = False,
    schedule_enabled: bool = True,
) -> float:
    """
    Calculate DIF (Day-Night temperature difference) in °C.

    DIF = mean(day temperature) - mean(night temperature)

    Positive DIF (warmer days) promotes stem elongation.
    Negative DIF (cooler days) produces compact growth.

    Day/night is defined by a schedule (day_start/day_end) and can optionally be
    overridden by a lux-based sensor classification.
    
    Args:
        temperature_c: Pandas Series with DatetimeIndex
        day_start: Schedule day start time (HH:MM)
        day_end: Schedule day end time (HH:MM)
        lux_values: Optional light sensor values for day/night detection
        lux_threshold: Lux threshold for "day" classification
        prefer_sensor: If True, prefer sensor over schedule
        schedule_enabled: If False, use sensor-only classification
        
    Returns:
        DIF value in Celsius, or 0.0 if insufficient data
    """
    if temperature_c is None:
        return 0.0

    try:
        import pandas as pd

        if not hasattr(temperature_c, "index") or not isinstance(temperature_c.index, pd.DatetimeIndex):
            return 0.0

        series = temperature_c.sort_index()
        if series.empty:
            return 0.0

        from app.domain.photoperiod import Photoperiod

        timestamps = list(series.index)
        sensor_values = None
        if lux_values is not None:
            sensor_values = list(lux_values)
            if len(sensor_values) != len(timestamps):
                return 0.0

        photoperiod = Photoperiod(
            schedule_day_start=day_start,
            schedule_day_end=day_end,
            schedule_enabled=bool(schedule_enabled),
            sensor_threshold=float(lux_threshold),
            greenhouse_outside=bool(prefer_sensor),
            sensor_enabled=sensor_values is not None,
        )
        resolved = photoperiod.resolve_mask(timestamps, sensor_values=sensor_values)
        day_mask = resolved["final_mask"]

        day_temps = series[day_mask]
        night_temps = series[[not v for v in day_mask]]

        if day_temps.empty or night_temps.empty:
            return 0.0

        return float(day_temps.mean() - night_temps.mean())
    except Exception:
        return 0.0
