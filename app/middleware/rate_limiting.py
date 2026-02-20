"""
Rate Limiting Middleware
========================

Simple in-memory rate limiter optimized for Raspberry Pi deployment.
No external dependencies (Redis, etc.) - uses threading-safe dictionary.

Usage:
    from app.middleware.rate_limiting import rate_limit, RateLimiter

    # As decorator on routes:
    @app.route('/api/resource')
    @rate_limit(max_requests=30, window_seconds=60)
    def resource():
        return {"data": "..."}

    # Or initialize globally:
    limiter = RateLimiter()
    limiter.init_app(app, default_limits=["60/minute"])

Author: SYSGrow Team
Date: January 2026
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable

from flask import Flask, Response, current_app, g, request

from app.utils.http import error_response

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    enabled: bool = True
    default_limit: int = 60  # requests per window
    default_window: int = 60  # seconds
    burst_limit: int = 10  # extra requests allowed in burst
    cleanup_interval: int = 300  # clean old entries every 5 minutes
    exempt_paths: list[str] = field(
        default_factory=lambda: [
            "/api/health/ping",
            "/api/health/system",
            "/socket.io",
            "/static/",
        ]
    )
    exempt_methods: list[str] = field(default_factory=lambda: ["OPTIONS"])


class RateLimiter:
    """
    Simple in-memory rate limiter for Raspberry Pi.

    Uses a sliding window algorithm to track requests per client IP.
    Thread-safe and memory-efficient with automatic cleanup.
    """

    def __init__(self, config: RateLimitConfig | None = None):
        self.config = config or RateLimitConfig()
        self._requests: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self._app: Flask | None = None

    def init_app(self, app: Flask, default_limits: list[str] | None = None) -> None:
        """
        Initialize rate limiter with Flask app.

        Args:
            app: Flask application instance
            default_limits: List of default limits like ["60/minute", "1000/hour"]
        """
        self._app = app

        # Parse default limits
        if default_limits:
            for limit in default_limits:
                parsed = self._parse_limit(limit)
                if parsed:
                    self.config.default_limit, self.config.default_window = parsed
                    break  # Use first valid limit

        # Register before_request hook
        @app.before_request
        def check_rate_limit():
            if not self.config.enabled:
                return None

            if current_app.testing or current_app.debug:
                return None

            # Skip exempt paths
            path = request.path
            for exempt in self.config.exempt_paths:
                if path.startswith(exempt):
                    return None

            # Skip exempt methods
            if request.method in self.config.exempt_methods:
                return None

            # Get client identifier
            client_key = self._get_client_key()

            # Check rate limit
            allowed, remaining, reset_time = self.is_allowed(
                client_key, max_requests=self.config.default_limit, window_seconds=self.config.default_window
            )

            # Store info for response headers
            g.rate_limit_remaining = remaining
            g.rate_limit_reset = reset_time
            g.rate_limit_limit = self.config.default_limit + max(0, self.config.burst_limit)

            if not allowed:
                logger.warning("Rate limit exceeded for %s", client_key)
                return self._rate_limit_response(reset_time)

            return None

        # Register after_request hook for headers
        @app.after_request
        def add_rate_limit_headers(response: Response) -> Response:
            if hasattr(g, "rate_limit_remaining"):
                response.headers["X-RateLimit-Limit"] = str(g.rate_limit_limit)
                response.headers["X-RateLimit-Remaining"] = str(g.rate_limit_remaining)
                response.headers["X-RateLimit-Reset"] = str(int(g.rate_limit_reset))
            return response

        logger.info(
            f"Rate limiter initialized: {self.config.default_limit} requests per {self.config.default_window} seconds"
        )

    def _parse_limit(self, limit: str) -> tuple[int, int] | None:
        """Parse limit string like '60/minute' into (count, seconds)."""
        try:
            parts = limit.lower().split("/")
            if len(parts) != 2:
                return None

            count = int(parts[0])
            period = parts[1]

            period_seconds = {
                "second": 1,
                "minute": 60,
                "hour": 3600,
                "day": 86400,
            }

            seconds = period_seconds.get(period)
            if seconds is None:
                return None

            return (count, seconds)
        except (ValueError, IndexError):
            return None

    def _get_client_key(self) -> str:
        """Get unique identifier for the client."""
        # Use X-Forwarded-For if behind proxy, else use remote_addr
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First IP in the chain is the original client
            return forwarded.split(",")[0].strip()
        return request.remote_addr or "unknown"

    def is_allowed(self, key: str, max_requests: int = 60, window_seconds: int = 60) -> tuple[bool, int, float]:
        """
        Check if request is allowed within rate limit.

        Args:
            key: Client identifier (typically IP address)
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (allowed: bool, remaining: int, reset_time: float)
        """
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            # Clean old entries periodically
            if now - self._last_cleanup > self.config.cleanup_interval:
                self._cleanup_old_entries(window_start)
                self._last_cleanup = now

            # Get requests in current window
            requests = self._requests[key]

            # Remove old requests outside window
            requests[:] = [ts for ts in requests if ts > window_start]

            # Check limit
            current_count = len(requests)
            effective_limit = max_requests + max(0, self.config.burst_limit)
            remaining = max(0, effective_limit - current_count)
            if requests:
                reset_time = requests[0] + window_seconds
            else:
                reset_time = now + window_seconds

            if current_count >= effective_limit:
                return (False, 0, reset_time)

            # Add current request
            requests.append(now)
            return (True, max(0, remaining - 1), reset_time)

    def _cleanup_old_entries(self, window_start: float) -> None:
        """Remove old entries to prevent memory growth."""
        keys_to_remove = []

        for key, timestamps in self._requests.items():
            # Remove timestamps older than window
            timestamps[:] = [ts for ts in timestamps if ts > window_start]
            # Mark empty keys for removal
            if not timestamps:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._requests[key]

        if keys_to_remove:
            logger.debug("Rate limiter cleanup: removed %s stale entries", len(keys_to_remove))

    def _rate_limit_response(self, reset_time: float) -> Response:
        """Generate rate limit exceeded response with standard envelope."""
        retry_after = max(1, int(reset_time - time.time()))
        response = error_response(
            "Rate limit exceeded. Please try again later.",
            status=429,
            details={
                "code": "RATE_LIMIT_EXCEEDED",
                "retry_after_seconds": retry_after,
            },
        )
        response.headers["Retry-After"] = str(retry_after)
        return response

    def get_stats(self) -> dict[str, any]:
        """Get rate limiter statistics."""
        with self._lock:
            active_clients = len(self._requests)
            total_tracked = sum(len(ts) for ts in self._requests.values())

        return {
            "enabled": self.config.enabled,
            "active_clients": active_clients,
            "total_tracked_requests": total_tracked,
            "default_limit": self.config.default_limit,
            "default_window_seconds": self.config.default_window,
            "exempt_paths": self.config.exempt_paths,
        }


# Global limiter instance
_limiter: RateLimiter | None = None


def get_limiter() -> RateLimiter:
    """Get or create global rate limiter instance."""
    global _limiter
    if _limiter is None:
        _limiter = RateLimiter()
    return _limiter


def rate_limit(max_requests: int = 60, window_seconds: int = 60, key_func: Callable[[], str] | None = None):
    """
    Decorator for rate limiting specific endpoints.

    Usage:
        @app.route('/api/expensive-operation')
        @rate_limit(max_requests=10, window_seconds=60)
        def expensive_operation():
            return {"result": "..."}

    Args:
        max_requests: Maximum requests allowed in window
        window_seconds: Time window in seconds
        key_func: Optional function to generate rate limit key (default: client IP)

    Returns:
        Decorated function
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args, **kwargs):
            limiter = get_limiter()

            if not limiter.config.enabled:
                return f(*args, **kwargs)

            # Get client key
            if key_func:
                client_key = key_func()
            else:
                client_key = limiter._get_client_key()

            # Add endpoint to key for endpoint-specific limiting
            endpoint_key = f"{client_key}:{request.endpoint}"

            allowed, remaining, reset_time = limiter.is_allowed(
                endpoint_key, max_requests=max_requests, window_seconds=window_seconds
            )

            # Store for headers
            g.rate_limit_remaining = remaining
            g.rate_limit_reset = reset_time
            g.rate_limit_limit = max_requests + max(0, limiter.config.burst_limit)

            if not allowed:
                logger.warning("Rate limit exceeded for %s on %s", client_key, request.endpoint)
                return limiter._rate_limit_response(reset_time)

            return f(*args, **kwargs)

        return wrapped

    return decorator


def init_rate_limiting(app: Flask, enabled: bool = True) -> RateLimiter:
    """
    Initialize rate limiting for the Flask app.

    Args:
        app: Flask application
        enabled: Whether rate limiting is enabled

    Returns:
        Configured RateLimiter instance
    """
    config = RateLimitConfig(
        enabled=enabled,
        default_limit=60,
        default_window=60,
    )

    limiter = get_limiter()
    limiter.config = config
    limiter.init_app(app)

    return limiter
