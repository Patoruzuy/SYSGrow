from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from flask import Response, jsonify

from app.utils.time import iso_now

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Generic user-facing messages — never leak internals
# ---------------------------------------------------------------------------
_GENERIC_MESSAGES: dict[int, str] = {
    400: "Invalid request",
    401: "Authentication required",
    403: "Access denied",
    404: "Resource not found",
    409: "Conflict",
    422: "Unprocessable entity",
    500: "An internal error occurred",
}


def safe_error(
    exc: BaseException,
    status: int = 500,
    *,
    context: str = "",
) -> Response:
    """Return a generic error response while logging the real exception.

    Use this instead of ``error_response(str(e), …)`` to prevent internal
    details (file paths, SQL fragments, class names) from leaking to
    clients.

    Parameters
    ----------
    exc:
        The caught exception — logged server-side, **never** sent to the
        client.
    status:
        HTTP status code for the response (determines the generic message).
    context:
        Optional human-readable context string logged alongside *exc* to
        make server logs easier to triage, e.g. ``"creating growth unit"``.
    """
    _log.error("API error [%s] %s: %s", status, context, exc, exc_info=exc)
    message = _GENERIC_MESSAGES.get(status, _GENERIC_MESSAGES[500])
    return error_response(message, status)


def success_response(
    data: dict | list | None = None,
    status: int = 200,
    *,
    message: str | None = None,
) -> Response:
    payload: dict[str, Any] = {"ok": True, "data": data, "error": None}
    if message is not None:
        payload["message"] = message
    response = jsonify(payload)
    response.status_code = status
    return response


def error_response(
    message: str,
    status: int = 500,
    *,
    details: dict | None = None,
) -> Response:
    payload: dict[str, Any] = {"message": message, "timestamp": iso_now()}
    if details:
        payload.update(details)
    response_body: dict[str, Any] = {
        "ok": False,
        "data": None,
        "error": payload,
        "message": message,
    }
    if details:
        response_body["details"] = details
    response = jsonify(response_body)
    response.status_code = status
    return response


# ---------------------------------------------------------------------------
# Route decorator — eliminates per-route try/except boilerplate
# ---------------------------------------------------------------------------


def safe_route(
    error_message: str = "An internal error occurred",
    *,
    error_status: int = 500,
) -> Callable:
    """Decorator that wraps a Flask route handler with standardized error handling.

    Catches :class:`~app.domain.exceptions.SysGrowError` subclasses and maps
    them to the correct HTTP status via ``exc.http_status``. Any other
    ``Exception`` is logged and returns a generic 500.

    Usage::

        @dashboard_api.get("/sensors/current")
        @safe_route("Failed to get sensor data")
        def get_current_sensor_data():
            svc = _get_service()
            ...

    Parameters
    ----------
    error_message:
        Fallback message returned to the client for untyped 5xx errors.
    error_status:
        Default HTTP status for non-SysGrowError exceptions (default 500).
    """
    from app.domain.exceptions import SysGrowError

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Response:
            try:
                return fn(*args, **kwargs)
            except SysGrowError as exc:
                status = exc.http_status
                if status >= 500:
                    return safe_error(exc, status, context=error_message)
                return error_response(str(exc) or error_message, status)
            except Exception as exc:
                return safe_error(exc, error_status, context=error_message)

        return wrapper

    return decorator
