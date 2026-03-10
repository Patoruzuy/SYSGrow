"""
Plant irrigation model service.

Estimates dry-down rate from moisture readings, excluding watering windows,
and provides simple predictions for next irrigation timing.
"""

from __future__ import annotations

import itertools
import logging
import os
import statistics
from datetime import timedelta
from typing import Any

from app.utils.time import coerce_datetime, iso_now, utc_now

logger = logging.getLogger(__name__)


class PlantIrrigationModelService:
    """Estimate and persist plant dry-down models."""

    def __init__(
        self,
        *,
        irrigation_repo: Any,
        analytics_repo: Any,
    ) -> None:
        self._repo = irrigation_repo
        self._analytics = analytics_repo

        self._lookback_hours = int(os.getenv("SYSGROW_IRRIGATION_DRYDOWN_LOOKBACK_HOURS", "72"))
        self._min_samples = int(os.getenv("SYSGROW_IRRIGATION_DRYDOWN_MIN_SAMPLES", "4"))
        self._max_gap_hours = float(os.getenv("SYSGROW_IRRIGATION_DRYDOWN_MAX_GAP_HOURS", "24"))

    def update_drydown_model(
        self,
        plant_id: int,
        *,
        lookback_hours: int | None = None,
    ) -> dict[str, Any]:
        """Compute dry-down rate for a plant and persist the model."""
        lookback = int(lookback_hours or self._lookback_hours)
        end_dt = utc_now()
        start_dt = end_dt - timedelta(hours=lookback)

        readings = self._analytics.get_plant_moisture_readings_in_window(
            plant_id,
            start_ts=start_dt.isoformat(),
            end_ts=end_dt.isoformat(),
        )
        if len(readings) < 2:
            self._repo.upsert_plant_irrigation_model(
                plant_id=plant_id,
                drydown_rate_per_hour=None,
                sample_count=0,
                confidence=0.0,
                updated_at_utc=iso_now(),
            )
            return {
                "ok": False,
                "reason": "insufficient_readings",
                "sample_count": 0,
            }

        watering_windows = self._collect_watering_windows(
            plant_id,
            start_ts=start_dt.isoformat(),
            end_ts=end_dt.isoformat(),
        )

        slopes = self._compute_slopes(readings, watering_windows)
        if len(slopes) < self._min_samples:
            self._repo.upsert_plant_irrigation_model(
                plant_id=plant_id,
                drydown_rate_per_hour=None,
                sample_count=len(slopes),
                confidence=0.0,
                updated_at_utc=iso_now(),
            )
            return {
                "ok": False,
                "reason": "insufficient_slope_samples",
                "sample_count": len(slopes),
            }

        drydown_rate = statistics.median(slopes)
        confidence = min(1.0, len(slopes) / 10.0)

        self._repo.upsert_plant_irrigation_model(
            plant_id=plant_id,
            drydown_rate_per_hour=drydown_rate,
            sample_count=len(slopes),
            confidence=confidence,
            updated_at_utc=iso_now(),
        )

        return {
            "ok": True,
            "drydown_rate_per_hour": drydown_rate,
            "sample_count": len(slopes),
            "confidence": confidence,
        }

    def predict_next_irrigation(
        self,
        *,
        plant_id: int,
        threshold: float,
        now_moisture: float,
        drydown_rate: float | None = None,
    ) -> dict[str, Any]:
        """Predict when the plant will hit the threshold based on dry-down."""
        if drydown_rate is None:
            model = self._repo.get_plant_irrigation_model(plant_id)
            drydown_rate = model.get("drydown_rate_per_hour") if model else None
            confidence = model.get("confidence") if model else 0.0
        else:
            confidence = None

        if drydown_rate is None or drydown_rate >= 0:
            return {"ok": False, "reason": "insufficient_data"}

        deficit = float(now_moisture) - float(threshold)
        if deficit <= 0:
            return {
                "ok": True,
                "predicted_at_utc": iso_now(),
                "hours_until_threshold": 0.0,
                "confidence": confidence or 0.0,
            }

        hours_until = deficit / abs(float(drydown_rate))
        predicted_at = utc_now() + timedelta(hours=hours_until)

        return {
            "ok": True,
            "predicted_at_utc": predicted_at.isoformat(),
            "hours_until_threshold": round(hours_until, 2),
            "confidence": confidence if confidence is not None else 0.5,
        }

    def _collect_watering_windows(
        self,
        plant_id: int,
        *,
        start_ts: str,
        end_ts: str,
    ) -> list[tuple[Any, Any]]:
        """Collect watering windows to exclude from dry-down slope fitting."""
        windows: list[tuple[Any, Any]] = []

        manual_logs = self._repo.get_manual_logs_for_plant(
            plant_id,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        for log in manual_logs:
            start = coerce_datetime(log.get("watered_at_utc"))
            if start is None:
                continue
            delay = int(log.get("settle_delay_min") or 15)
            end = start + timedelta(minutes=delay)
            windows.append((start, end))

        execution_logs = self._repo.get_execution_logs_for_plant(
            plant_id,
            start_ts=start_ts,
            end_ts=end_ts,
        )
        for log in execution_logs:
            start = coerce_datetime(log.get("executed_at_utc"))
            if start is None:
                continue
            duration = log.get("actual_duration_s") or log.get("planned_duration_s") or 0
            delay = log.get("post_moisture_delay_s") or 900
            end = start + timedelta(seconds=int(duration) + int(delay))
            windows.append((start, end))

        return windows

    def _compute_slopes(
        self,
        readings: list[dict[str, Any]],
        watering_windows: list[tuple[Any, Any]],
    ) -> list[float]:
        """Compute dry-down slopes excluding watering windows."""
        slopes: list[float] = []
        for prev, curr in itertools.pairwise(readings):
            prev_ts = coerce_datetime(prev.get("timestamp"))
            curr_ts = coerce_datetime(curr.get("timestamp"))
            if prev_ts is None or curr_ts is None or curr_ts <= prev_ts:
                continue

            gap_hours = (curr_ts - prev_ts).total_seconds() / 3600.0
            if gap_hours <= 0 or gap_hours > self._max_gap_hours:
                continue

            if self._overlaps_watering_window(prev_ts, curr_ts, watering_windows):
                continue

            prev_m = prev.get("soil_moisture")
            curr_m = curr.get("soil_moisture")
            if prev_m is None or curr_m is None:
                continue

            slope = (float(curr_m) - float(prev_m)) / gap_hours
            if slope < 0:
                slopes.append(slope)

        return slopes

    @staticmethod
    def _overlaps_watering_window(
        start: Any,
        end: Any,
        windows: list[tuple[Any, Any]],
    ) -> bool:
        """Check if a time range overlaps any watering window."""
        return any(start <= win_end and end >= win_start for win_start, win_end in windows)
