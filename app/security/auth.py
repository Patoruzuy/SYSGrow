from functools import wraps
from typing import Callable, TypeVar, cast

from flask import flash, jsonify, redirect, session, url_for

F = TypeVar("F", bound=Callable[..., object])


def login_required(view_func: F) -> F:
    """Ensure the user is authenticated before accessing the route (UI pages)."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("auth.login"))
        return view_func(*args, **kwargs)

    return cast(F, wrapped)


def api_login_required(view_func: F) -> F:
    """Ensure the user is authenticated for API endpoints (returns JSON 401)."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return jsonify({
                "ok": False,
                "error": {"message": "Authentication required", "code": "UNAUTHORIZED"}
            }), 401
        return view_func(*args, **kwargs)

    return cast(F, wrapped)


def current_username() -> str | None:
    return session.get("user")
