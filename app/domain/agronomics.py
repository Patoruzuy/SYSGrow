from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Sequence

logger = logging.getLogger(__name__)


def stage_temperature_min_c(
    growth_stages: Sequence[Dict[str, Any]],
    *,
    stage_name: str,
) -> Optional[float]:
    """
    Return the configured minimum temperature (°C) for a growth stage, if present.

    Expects the plant dataset shape used in `plants_info.json`:
      stage.conditions.temperature_C.min
    """
    if not growth_stages or not stage_name:
        return None

    target = str(stage_name).strip().lower()
    for stage in growth_stages:
        name = str(stage.get("stage", "")).strip().lower()
        if name != target:
            continue

        conditions = stage.get("conditions", {}) or {}
        temp_c = conditions.get("temperature_C", {}) or {}
        value = temp_c.get("min")
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    return None


def infer_gdd_base_temp_c(
    growth_stages: Sequence[Dict[str, Any]],
    *,
    stage_name: str,
    default: float = 10.0,
) -> float:
    """
    Infer a reasonable GDD base temperature from plant stage configuration.

    Uses the stage's configured minimum temperature as a pragmatic default.
    """
    inferred = stage_temperature_min_c(growth_stages, stage_name=stage_name)
    if inferred is None:
        return float(default)
    return float(inferred)


def calculate_gdd_degree_days(
    temperature_c,
    *,
    base_temp_c: float,
    interval_hours: Optional[float] = None,
) -> float:
    """
    Calculate Growing Degree Days (GDD) / thermal time in degree-days.

    GDD = Σ max(T - base_temp, 0) × Δt_days

    If `temperature_c` is a pandas Series with a DatetimeIndex, Δt is derived from
    successive timestamps (time-weighted).
    Otherwise, provide `interval_hours` to treat samples as uniformly spaced.
    """
    if temperature_c is None:
        return 0.0

    base = float(base_temp_c)

    try:
        import pandas as pd

        if hasattr(temperature_c, "index") and isinstance(temperature_c.index, pd.DatetimeIndex):
            series = temperature_c.sort_index()
            if series.empty:
                return 0.0

            index = series.index
            deltas = index.to_series().shift(-1) - index.to_series()
            delta_seconds = deltas.dt.total_seconds()

            fallback = 0.0
            non_null = delta_seconds.iloc[:-1].dropna()
            if not non_null.empty:
                fallback = float(non_null.median())

            delta_seconds = delta_seconds.fillna(fallback).clip(lower=0.0)

            above = series - base
            above = above.clip(lower=0.0)

            degree_days = above * (delta_seconds / 86400.0)
            return float(degree_days.sum())

    except Exception as exc:
        logger.debug("Failed to compute time-weighted GDD: %s", exc)

    if interval_hours is None:
        return 0.0

    try:
        interval_days = float(interval_hours) / 24.0
    except Exception:
        return 0.0

    try:
        import numpy as np

        arr = np.asarray(temperature_c, dtype=float)
        above = arr - base
        above[above < 0] = 0.0
        return float(above.sum() * interval_days)
    except Exception as exc:
        logger.debug("Failed to compute uniform-interval GDD: %s", exc)
        return 0.0

