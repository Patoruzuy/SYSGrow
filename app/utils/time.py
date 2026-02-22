"""Utility functions for time handling.

All timestamps should be UTC and timezone-aware. Persist UTC timestamps as
ISO-8601 strings with timezone offsets (e.g., "+00:00") via iso_now().
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    """Return current UTC time as an aware datetime."""
    return datetime.now(timezone.utc)


def iso_now(*, timespec: str | None = None) -> str:
    """Return current UTC time as an ISO8601 string (timezone-aware)."""
    now = utc_now()
    if timespec:
        return now.isoformat(timespec=timespec)
    return now.isoformat()


def get_current_utc_time() -> datetime:
    """Backward-compatible alias for retrieving UTC now."""
    return utc_now()


def convert_utc_to_local(utc_dt: datetime) -> datetime:
    """Convert a UTC datetime (aware or naive) to the local timezone."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone()


def format_datetime(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S %Z") -> str:
    """Format a datetime into a string based on the given format."""
    return dt.strftime(fmt)


def sqlite_timestamp(dt: datetime) -> str:
    """Format a datetime for safe use with SQLite datetime() comparisons."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def coerce_datetime(value: Any) -> datetime | None:
    """
    Coerce value to datetime, returning None on failure.

    Args:
        value: String or datetime to coerce

    Returns:
        Datetime in timezone.utc or None if invalid
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc)
    else:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed
