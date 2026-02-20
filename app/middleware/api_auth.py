"""
API Write-Protection Middleware
===============================
Enforces authentication on all mutating API requests (POST, PUT, DELETE, PATCH).

Instead of decorating every individual endpoint, this middleware hooks into
Flask's ``before_request`` pipeline and rejects unauthenticated writes with a
401 JSON response.  Read-only methods (GET, HEAD, OPTIONS) pass through.

Endpoints that must remain public (login, register, health checks) are
exempted by blueprint name or explicit endpoint name.

Usage in ``create_app``::

    from app.middleware.api_auth import init_api_write_protection

    init_api_write_protection(flask_app)
"""

from __future__ import annotations

import logging

from flask import Flask, request, session

from app.utils.http import error_response

logger = logging.getLogger(__name__)

# HTTP methods that mutate state — these require authentication.
_WRITE_METHODS = frozenset({"POST", "PUT", "DELETE", "PATCH"})

# Blueprints that are completely exempt from write-protection.
# Health/help/blog are public.  Auth needs login/register to work.
_EXEMPT_BLUEPRINTS: frozenset[str] = frozenset(
    {
        "auth",  # login, register, reset-password, recover
        "health_api",  # readiness / liveness probes
        "help_api",  # public help articles
        "blog_api",  # public blog posts
    }
)

# Individual endpoints that are exempt even inside protected blueprints.
_EXEMPT_ENDPOINTS: frozenset[str] = frozenset(
    {
        # Add specific endpoint names here if needed, e.g.:
        # "devices_api.public_webhook",
    }
)


def init_api_write_protection(app: Flask) -> None:
    """Register a ``before_request`` hook that protects API write endpoints.

    Parameters
    ----------
    app:
        The Flask application instance.
    """

    @app.before_request
    def _enforce_api_auth():
        # Only gate mutating methods
        if request.method not in _WRITE_METHODS:
            return None

        # Let exempted blueprints through (auth, health, etc.)
        if request.blueprint in _EXEMPT_BLUEPRINTS:
            return None

        # Let explicitly exempted endpoints through
        if request.endpoint in _EXEMPT_ENDPOINTS:
            return None

        # Only protect API routes (url starts with /api/)
        if not request.path.startswith("/api/"):
            return None

        # Authenticated? Let through.
        if "user" in session:
            return None

        # Reject with 401 JSON
        logger.warning(
            "Blocked unauthenticated %s to %s from %s",
            request.method,
            request.path,
            request.remote_addr,
        )
        return error_response(
            "Authentication required",
            status=401,
            details={"code": "UNAUTHORIZED"},
        )
