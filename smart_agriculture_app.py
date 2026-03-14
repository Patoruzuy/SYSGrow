"""WSGI entry point for the SYSGrow backend application."""
from __future__ import annotations

import os
import sys
import traceback

from app import create_app, socketio


def build_app():
    overrides = {}
    secret = os.getenv("SYSGROW_SECRET_KEY")
    if secret:
        overrides["secret_key"] = secret
    return create_app(overrides if overrides else None)


app = build_app()


def main() -> int:
    import logging

    logging.basicConfig(level=logging.DEBUG)

    host = os.getenv("SYSGROW_HOST", "0.0.0.0")
    port = int(os.getenv("SYSGROW_PORT", "8000"))
    print(f"Starting server on {host}:{port}...")
    print(f"SocketIO async_mode: {socketio.async_mode}")

    try:
        socketio.run(
            app,
            host=host,
            port=port,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True,
        )
        print("Server stopped.")
        return 0
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
        return 0
    except Exception as e:
        print(f"ERROR: Failed to start server: {e}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
