"""
Infrastructure time utilities
=============================

Small helpers for infra/database layers that need ISO8601 timestamps
without depending on app-level utilities.
"""

from datetime import UTC, datetime


def iso_now(*, timespec: str | None = None) -> str:
    """Return current UTC time as a timezone-aware ISO8601 string."""
    now = datetime.now(UTC)
    if timespec:
        return now.isoformat(timespec=timespec)
    return now.isoformat()
