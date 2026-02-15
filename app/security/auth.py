from functools import wraps
from typing import Callable, TypeVar, cast

from flask import flash, redirect, session, url_for
from app.utils.http import error_response

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
            return error_response(
                "Authentication required",
                status=401,
                details={"code": "UNAUTHORIZED"},
            )
        return view_func(*args, **kwargs)

    return cast(F, wrapped)


def current_username() -> str | None:
    return session.get("user")
