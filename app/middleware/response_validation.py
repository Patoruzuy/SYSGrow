"""
Response Envelope Validation Middleware
========================================
Flask middleware to enforce consistent API response structure.

All API responses must follow the envelope format:
- Success: {"ok": True, "data": Any, "error": None}
- Error: {"ok": False, "data": None, "error": {"message": str, "timestamp": str, ...}}

This middleware validates API responses and logs inconsistencies.

Author: SYSGrow Team
Date: December 2025
"""

import logging

from flask import Flask, Response, request

logger = logging.getLogger(__name__)


def init_response_validation(app: Flask, *, strict_mode: bool = False) -> None:
    """
    Initialize response envelope validation middleware.

    Args:
        app: Flask application instance
        strict_mode: If True, return 500 for invalid responses (default: False, log warning only)
    """

    @app.after_request
    def validate_response_envelope(response: Response) -> Response:
        """Validate that API responses follow the standard envelope format."""

        # Only validate JSON responses from /api/* endpoints
        if not _should_validate(request.path, response.content_type):
            return response

        # Try to parse JSON response
        try:
            data = response.get_json()

            # Allow empty responses (204 No Content, etc.)
            if data is None:
                return response

            # Validate envelope structure
            validation_errors = _validate_envelope(data)

            if validation_errors:
                error_msg = (
                    f"Invalid API response format on {request.method} {request.path}: {', '.join(validation_errors)}"
                )
                logger.warning(error_msg)

                if strict_mode:
                    # In strict mode, return 500 with proper error envelope
                    from app.utils.http import error_response

                    return error_response(
                        "Internal server error: Invalid response format",
                        status=500,
                        details={"validation_errors": validation_errors},
                    )
                else:
                    # In permissive mode, just log the warning
                    # Add header to help identify problematic responses in development
                    response.headers["X-Envelope-Validation"] = "FAILED"
            else:
                # Valid envelope, add header to confirm
                response.headers["X-Envelope-Validation"] = "PASSED"

        except (ValueError, TypeError) as e:
            # JSON parsing failed - not a valid JSON response
            logger.debug(f"Skipping validation for non-JSON response: {e}")

        return response

    logger.info(f"Response validation middleware initialized (strict_mode={strict_mode})")


def _should_validate(path: str, content_type: str | None) -> bool:
    """
    Determine if response should be validated.

    Args:
        path: Request path
        content_type: Response content type

    Returns:
        True if response should be validated
    """
    # Only validate /api/* endpoints
    if not path.startswith("/api/"):
        return False

    # Skip health check endpoints (avoid circular validation)
    if path.startswith("/api/health"):
        return False

    # Only validate JSON responses
    if content_type is None or "application/json" not in content_type:
        return False

    return True


def _validate_envelope(data: dict) -> list[str]:
    """
    Validate response envelope structure.

    Args:
        data: Parsed JSON response

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check if data is a dict
    if not isinstance(data, dict):
        errors.append("Response must be a JSON object")
        return errors

    # Check required fields
    if "ok" not in data:
        errors.append("Missing required field 'ok'")
    elif not isinstance(data["ok"], bool):
        errors.append("Field 'ok' must be a boolean")

    if "data" not in data:
        errors.append("Missing required field 'data'")

    if "error" not in data:
        errors.append("Missing required field 'error'")

    # If we have errors, no need to check consistency
    if errors:
        return errors

    # Check consistency: ok=True should have data, ok=False should have error
    if data["ok"]:
        if data["error"] is not None:
            errors.append("Success responses (ok=True) must have error=None")
    else:
        if data["error"] is None:
            errors.append("Error responses (ok=False) must have non-null error object")
        elif not isinstance(data["error"], dict):
            errors.append("Error field must be an object/dict")
        elif "message" not in data["error"]:
            errors.append("Error object must contain 'message' field")

    return errors
