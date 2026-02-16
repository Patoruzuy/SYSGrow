"""Flask server that stays alive"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

os.environ["SYSGROW_ENABLE_MQTT"] = "True"
os.environ["DATABASE_PATH"] = "database/sysgrow.db"

from app import create_app, socketio

try:
    from devhost_cli.frameworks.flask import run_flask
except ModuleNotFoundError as exc:
    if (exc.name or "").startswith("devhost_cli"):
        run_flask = None
    else:
        raise

app = create_app(bootstrap_runtime=True)

# Get port from environment or use default
port = int(os.environ.get("FLASK_RUN_PORT", 8000))

print(f"Server starting on http://0.0.0.0:{port}")
print("Press Ctrl+C to stop\n")

if __name__ == "__main__":
    try:
        if run_flask is not None:
            # Use socketio.run() instead of app.run() for WebSocket support
            run_flask(
                app, name="sysgrow", socketio=socketio, debug=False, use_reloader=False, allow_unsafe_werkzeug=True
            )
        else:
            print("devhost_cli not installed; using built-in Flask SocketIO runner.")
            socketio.run(
                app,
                host="0.0.0.0",
                port=port,
                debug=False,
                use_reloader=False,
                allow_unsafe_werkzeug=True,
            )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"\nServer error: {e}")
        import traceback

        traceback.print_exc()
