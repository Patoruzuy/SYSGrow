"""WSGI entry point for the SYSGrow backend application.

This module provides a minimal, robust CLI entrypoint used both in
development and production. It prefers environment configuration and
keeps startup behavior defensive (safe defaults, clear logging).
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from typing import Optional

from app import create_app, socketio


def build_app(secret: Optional[str] = None):
    """Create and return the Flask app.

    We call `create_app(bootstrap_runtime=True)` to ensure runtime
    initialization happens in development as in production. If a
    `secret` is provided via environment, set it on the app config.
    """
    # Keep call signature simple and defensive: use bootstrap flag, then
    # apply any runtime overrides to the app.config. This avoids depending
    # on the internal signature of `create_app`.
    app = create_app(bootstrap_runtime=True)
    if secret:
        try:
            app.config["SECRET_KEY"] = secret
        except Exception:
            # Be defensive: if app isn't fully configured, set environ
            os.environ["SYSGROW_SECRET_KEY"] = secret
    return app


app = build_app(os.getenv("SYSGROW_SECRET_KEY"))


def _env_flag_true(name: str) -> bool:
    v = os.getenv(name)
    return bool(v and v.lower() in ("1", "true", "yes", "on"))


def main() -> int:
    # Configure logging early so other modules pick it up
    level = logging.DEBUG if _env_flag_true("SYSGROW_DEBUG") else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(message)s")

    host = os.getenv("SYSGROW_HOST", "0.0.0.0")
    port = int(os.getenv("SYSGROW_PORT", "8000"))
    debug = _env_flag_true("SYSGROW_DEBUG")

    logging.info("Starting server on %s:%s", host, port)
    logging.info("SocketIO async_mode: %s", socketio.async_mode)

    try:
        socketio.run(
            app,
            host=host,
            port=port,
            debug=debug,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )
        logging.info("Server stopped.")
        return 0
    except KeyboardInterrupt:
        logging.info("Server stopped by user.")
        return 0
    except Exception as exc:  # pragma: no cover - top-level runtime errors
        logging.exception("ERROR: Failed to start server: %s", exc)
        return 1


if __name__ == "__main__":
    # Allow direct execution for development, mirror behavior used by
    # our console script `sysgrow-backend`.
    raise SystemExit(main())
