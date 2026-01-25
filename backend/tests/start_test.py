# Simple startup script for SYSGrow on Windows (no MQTT).
#
# NOTE: This is not a pytest test. It lives under `tests/` for convenience,
# but must never execute on import (pytest collection imports modules).
#
# Run manually:
#   .\.venv\Scripts\python tests\start_test.py

from __future__ import annotations

import os
import secrets


def main() -> None:
    if not os.getenv("SYSGROW_SECRET_KEY") and not os.getenv("FLASK_SECRET_KEY"):
        secret_key = secrets.token_hex(32)
        os.environ["FLASK_SECRET_KEY"] = secret_key
        print(f"Generated development secret key: {secret_key}")

    os.environ.setdefault("FLASK_ENV", "development")
    os.environ.setdefault("FLASK_DEBUG", "True")
    os.environ.setdefault("DATABASE_PATH", "sysgrow_dev.db")

    # Disable MQTT to avoid network errors
    os.environ["SYSGROW_ENABLE_MQTT"] = "False"

    print("Starting SYSGrow Backend...")
    print("Environment variables set:")
    print(f"  FLASK_ENV: {os.getenv('FLASK_ENV')}")
    print(f"  FLASK_DEBUG: {os.getenv('FLASK_DEBUG')}")
    print(f"  DATABASE_PATH: {os.getenv('DATABASE_PATH')}")
    print("  MQTT_ENABLED: False (disabled for testing)")

    try:
        from app import create_app, socketio

        app = create_app()

        print("\nSYSGrow Backend Starting...")
        print("Access the web interface at: http://localhost:5000")
        print("Development mode enabled (localhost only, MQTT disabled)")
        print("\nPress Ctrl+C to stop the server\n")

        socketio.run(
            app,
            host="127.0.0.1",
            port=5000,
            debug=True,
            allow_unsafe_werkzeug=True,
        )
    except ImportError as exc:
        print(f"Import Error: {exc}")
        print("\nMissing dependencies. Please install required packages:")
        print("   pip install -r requirements-windows.txt")
    except Exception as exc:
        print(f"Error starting application: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

