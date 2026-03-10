"""Centralized exception hierarchy for SYSGrow.

All domain and service exceptions inherit from :class:`SysGrowError` so that
callers can catch a single base class when they need a broad safety net, yet
still match on specific subclasses where narrower handling is appropriate.

Blueprint-level error handling (see ``app/utils/http.safe_route``) maps these
to the correct HTTP status codes automatically.

Hierarchy
---------
::

    SysGrowError (base — maps to 500)
    ├── ValidationError          (400 — bad input from caller)
    ├── NotFoundError            (404 — entity does not exist)
    ├── ConflictError            (409 — duplicate / state conflict)
    ├── ServiceError             (500 — business-logic failure)
    │   ├── RepositoryError      (500 — database / persistence)
    │   └── ExternalServiceError (502 — third-party / network)
    ├── DeviceError              (503 — hardware communication)
    └── ConfigurationError       (500 — missing / invalid config)
"""

from __future__ import annotations


class SysGrowError(Exception):
    """Base exception for all SYSGrow application errors.

    Parameters
    ----------
    message:
        Human-readable description (logged server-side, **not** leaked to
        the HTTP client unless the exception class opts in).
    detail:
        Optional machine-readable context dict attached to the error for
        structured logging.
    """

    http_status: int = 500

    def __init__(self, message: str = "", *, detail: dict | None = None) -> None:
        super().__init__(message)
        self.detail = detail or {}


# ── Client errors (4xx) ──────────────────────────────────────────────


class ValidationError(SysGrowError):
    """Caller supplied invalid or incomplete input (HTTP 400)."""

    http_status: int = 400


class NotFoundError(SysGrowError):
    """Requested entity does not exist (HTTP 404)."""

    http_status: int = 404


class ConflictError(SysGrowError):
    """Operation conflicts with existing state (HTTP 409)."""

    http_status: int = 409


# ── Server errors (5xx) ──────────────────────────────────────────────


class ServiceError(SysGrowError):
    """Business-logic failure in a service method (HTTP 500)."""

    http_status: int = 500


class RepositoryError(ServiceError):
    """Database / persistence layer failure (HTTP 500)."""

    http_status: int = 500


class ExternalServiceError(ServiceError):
    """Third-party or network dependency failure (HTTP 502)."""

    http_status: int = 502


class DeviceError(SysGrowError):
    """Hardware communication or device-protocol failure (HTTP 503)."""

    http_status: int = 503


class ConfigurationError(SysGrowError):
    """Missing or invalid application configuration (HTTP 500)."""

    http_status: int = 500
