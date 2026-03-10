"""
Security Headers Middleware
===========================

Adds standard HTTP security response headers to every response.
These protect against clickjacking, MIME-type sniffing, XSS, and
information-leakage attacks.

Reference: https://owasp.org/www-project-secure-headers/
"""

from __future__ import annotations

import logging

from flask import Flask

logger = logging.getLogger(__name__)

# Default header values — can be overridden via AppConfig / env vars
_DEFAULT_HEADERS: dict[str, str] = {
    # Prevent clickjacking (framing the app in an iframe)
    "X-Frame-Options": "SAMEORIGIN",
    # Prevent MIME-type sniffing (e.g. treating a JSON response as HTML)
    "X-Content-Type-Options": "nosniff",
    # Legacy XSS filter — modern browsers don't need it but older ones benefit
    "X-XSS-Protection": "1; mode=block",
    # Control what information is sent in the Referer header
    "Referrer-Policy": "strict-origin-when-cross-origin",
    # Restrict browser features the app doesn't need
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    # Prevent caching of sensitive responses by default.
    # Individual routes can override with more permissive headers.
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}

# Content-Security-Policy — allows inline styles/scripts for Jinja2 templates
# and whitelists the CDN domains used by the frontend for Chart.js, Socket.IO,
# Font Awesome, and Google Fonts.
_CDN_SCRIPT_SOURCES = "https://cdnjs.cloudflare.com https://cdn.jsdelivr.net"
_CDN_STYLE_SOURCES = "https://cdnjs.cloudflare.com https://fonts.googleapis.com"
_CDN_FONT_SOURCES = "https://cdnjs.cloudflare.com https://fonts.gstatic.com"

_DEFAULT_CSP = (
    "default-src 'self'; "
    f"script-src 'self' 'unsafe-inline' {_CDN_SCRIPT_SOURCES}; "
    f"style-src 'self' 'unsafe-inline' {_CDN_STYLE_SOURCES}; "
    "img-src 'self' data: blob:; "
    f"font-src 'self' {_CDN_FONT_SOURCES}; "
    f"connect-src 'self' ws: wss: {_CDN_SCRIPT_SOURCES} {_CDN_STYLE_SOURCES}; "
    "frame-ancestors 'self';"
)

# Static asset extensions that should have permissive caching
_STATIC_EXTENSIONS = (".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf")


def init_security_headers(
    app: Flask,
    *,
    enable_hsts: bool = False,
    hsts_max_age: int = 31_536_000,
    custom_csp: str | None = None,
) -> None:
    """Register an after_request handler that adds security headers.

    Args:
        app: The Flask application instance.
        enable_hsts: Whether to add Strict-Transport-Security. Only enable
                     when serving behind TLS (HTTPS). Defaults to False for
                     local Raspberry Pi deployments.
        hsts_max_age: HSTS max-age in seconds (default 1 year).
        custom_csp: Override the default Content-Security-Policy value.
    """
    csp_value = custom_csp or _DEFAULT_CSP

    @app.after_request
    def _add_security_headers(response):
        # Apply standard security headers
        for header, value in _DEFAULT_HEADERS.items():
            # Don't overwrite headers already set by individual routes
            if header not in response.headers:
                response.headers[header] = value

        # Content-Security-Policy
        if "Content-Security-Policy" not in response.headers:
            response.headers["Content-Security-Policy"] = csp_value

        # HSTS — only when explicitly enabled (requires TLS)
        if enable_hsts and "Strict-Transport-Security" not in response.headers:
            response.headers["Strict-Transport-Security"] = f"max-age={hsts_max_age}; includeSubDomains"

        # Static assets: allow browser caching (override the no-store default)
        if response.status_code == 200 and _is_static_response(response):
            response.headers["Cache-Control"] = "public, max-age=3600, immutable"
            response.headers.pop("Pragma", None)

        return response

    logger.info(
        "Security headers middleware initialised (HSTS=%s, CSP=%s)", enable_hsts, "custom" if custom_csp else "default"
    )


def _is_static_response(response) -> bool:
    """Heuristic: check if the response is for a static file."""
    content_type = response.content_type or ""
    return bool(any(ct in content_type for ct in ("text/css", "javascript", "image/", "font/")))
