import secrets
from typing import Iterable, Set

from flask import Flask, abort, current_app, request, session


class CSRFMiddleware:
    """Minimal CSRF protection without external dependencies."""

    def __init__(
        self,
        *,
        exempt_endpoints: Iterable[str] | None = None,
        exempt_blueprints: Iterable[str] | None = None,
    ) -> None:
        self.exempt_endpoints: Set[str] = set(exempt_endpoints or [])
        self.exempt_blueprints: Set[str] = set(exempt_blueprints or [])

    def init_app(self, app: Flask) -> None:
        app.before_request(self._protect)
        app.context_processor(self._inject_token)

    def generate_token(self) -> str:
        token = secrets.token_urlsafe(32)
        session["_csrf_token"] = token
        return token

    def _protect(self) -> None:
        if current_app.testing or current_app.debug:
            return
        if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            return
        if self._is_exempt():
            return

        session_token = session.get("_csrf_token")
        request_token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
        if not session_token or not request_token or session_token != request_token:
            abort(400, description="CSRF token missing or invalid")

    def _is_exempt(self) -> bool:
        if request.endpoint in self.exempt_endpoints:
            return True
        if request.blueprint and request.blueprint in self.exempt_blueprints:
            return True
        return False

    def _inject_token(self) -> dict[str, str]:
        return {"csrf_token": session.get("_csrf_token") or self.generate_token()}
