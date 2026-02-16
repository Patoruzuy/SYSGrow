"""
Login Rate Limiter — brute-force & account-lockout protection
=============================================================

In-memory tracker that limits login attempts per IP address.
After ``max_attempts`` consecutive failures within the lockout window
the IP is temporarily locked out for ``lockout_minutes``.

A successful login resets the counter for that IP.

Design decisions
----------------
* **IP-based only** – the single-user Raspberry Pi use-case doesn't
  need per-username tracking (there is typically one account).
* **In-memory dict** – survives only while the process runs, which is
  acceptable for a Pi; no external dependency required.
* Expired entries are lazily purged to keep memory bounded.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _AttemptRecord:
    """Tracks consecutive failures for a single IP."""

    count: int = 0
    first_failure: float = 0.0
    locked_until: float = 0.0


# ---------------------------------------------------------------------------
# Limiter
# ---------------------------------------------------------------------------


class LoginLimiter:
    """Thread-safe, in-memory login rate limiter."""

    def __init__(self, max_attempts: int = 5, lockout_minutes: int = 15) -> None:
        self._max_attempts = max(1, max_attempts)
        self._lockout_seconds = max(1, lockout_minutes) * 60
        self._records: dict[str, _AttemptRecord] = {}
        self._lock = Lock()

    # -- public API --------------------------------------------------------

    def is_locked(self, ip: str) -> tuple[bool, int]:
        """Return ``(locked, remaining_seconds)`` for *ip*.

        If the IP is not locked, ``remaining_seconds`` is ``0``.
        """
        with self._lock:
            rec = self._records.get(ip)
            if rec is None:
                return False, 0
            now = time.monotonic()
            if rec.locked_until and now < rec.locked_until:
                remaining = int(rec.locked_until - now) + 1
                return True, remaining
            # Lockout expired → reset
            if rec.locked_until and now >= rec.locked_until:
                del self._records[ip]
                return False, 0
            return False, 0

    def record_failure(self, ip: str) -> tuple[bool, int]:
        """Record a failed login attempt for *ip*.

        Returns ``(now_locked, remaining_seconds)``.  If the failure
        count reaches the threshold the IP is immediately locked.
        """
        with self._lock:
            now = time.monotonic()
            rec = self._records.get(ip)

            if rec is None:
                rec = _AttemptRecord(count=1, first_failure=now)
                self._records[ip] = rec
            else:
                # If a previous lockout expired, start fresh
                if rec.locked_until and now >= rec.locked_until:
                    rec.count = 1
                    rec.first_failure = now
                    rec.locked_until = 0.0
                else:
                    rec.count += 1

            if rec.count >= self._max_attempts:
                rec.locked_until = now + self._lockout_seconds
                remaining = self._lockout_seconds
                logger.warning(
                    "Login rate-limit: IP %s locked out for %d min after %d failures",
                    ip,
                    self._lockout_seconds // 60,
                    rec.count,
                )
                return True, remaining

            return False, 0

    def record_success(self, ip: str) -> None:
        """Clear the failure counter for *ip* after a successful login."""
        with self._lock:
            self._records.pop(ip, None)

    def reset(self) -> None:
        """Clear all tracked records (useful for tests)."""
        with self._lock:
            self._records.clear()

    # -- housekeeping ------------------------------------------------------

    def purge_expired(self) -> int:
        """Remove entries whose lockout has expired.  Returns count purged."""
        now = time.monotonic()
        with self._lock:
            expired = [
                ip
                for ip, rec in self._records.items()
                if rec.locked_until and now >= rec.locked_until
            ]
            for ip in expired:
                del self._records[ip]
            return len(expired)
