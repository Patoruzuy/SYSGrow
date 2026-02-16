"""Security Settings API
=========================

Backend endpoints for security-related user settings:
- Get recovery code count
- Generate new recovery codes (requires password confirmation)

Recovery codes are one-time codes for offline password recovery.
"""

from __future__ import annotations

import logging

from flask import request, session

from app.blueprints.api._common import (
    fail as _fail,
    get_container as _get_container,
    success as _success,
)
from app.blueprints.api.settings import settings_api
from app.security.auth import api_login_required

logger = logging.getLogger(__name__)


@settings_api.get("/security/recovery-codes/count")
@api_login_required
def get_recovery_code_count():
    """Get the count of remaining (unused) recovery codes for the current user.

    Returns:
        {"ok": true, "data": {"count": 8, "total": 10}}
    """
    try:
        container = _get_container()
        if not container:
            return _fail("Service container not available", 500)

        user_id = session.get("user_id")
        if not user_id:
            return _fail("User not authenticated", 401)

        auth_manager = container.auth_manager
        count = auth_manager.get_recovery_code_count(user_id)

        return _success(
            {
                "count": count,
                "total": 10,  # RECOVERY_CODE_COUNT
            }
        )

    except Exception as exc:
        logger.exception("Error getting recovery code count")
        return _fail(f"Failed to get recovery code count: {exc}", 500)


@settings_api.post("/security/recovery-codes/generate")
@api_login_required
def generate_recovery_codes():
    """Generate new recovery codes for the current user.

    Requires password confirmation for security.
    Invalidates any existing codes.

    Request JSON:
        {"current_password": "..."}

    Returns:
        {"ok": true, "data": {"codes": ["ABCD-1234", ...], "count": 10}}
    """
    try:
        container = _get_container()
        if not container:
            return _fail("Service container not available", 500)

        user_id = session.get("user_id")
        if not user_id:
            return _fail("User not authenticated", 401)

        payload = request.get_json(silent=True) or {}
        current_password = payload.get("current_password", "")

        if not current_password:
            return _fail("Current password is required to generate recovery codes", 400)

        # Verify current password
        auth_manager = container.auth_manager
        username = session.get("user")

        if not auth_manager.authenticate_user(username, current_password):
            return _fail("Invalid password", 403)

        # Generate new codes
        codes = auth_manager.generate_recovery_codes(user_id)

        if codes is None:
            return _fail("Failed to generate recovery codes", 500)

        return _success(
            {"codes": codes, "count": len(codes)},
            message="Recovery codes generated successfully. Save these codes in a secure location.",
        )

    except Exception as exc:
        logger.exception("Error generating recovery codes")
        return _fail(f"Failed to generate recovery codes: {exc}", 500)
