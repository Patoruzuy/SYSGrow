"""Development server with auto-reload and debug mode.

Usage::

    python start_dev.py          # default: 0.0.0.0:8000, debug=True
    SYSGROW_PORT=5000 python start_dev.py
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Sensible dev defaults
os.environ.setdefault("SYSGROW_ENABLE_MQTT", "True")
os.environ.setdefault("DATABASE_PATH", "database/sysgrow.db")
os.environ.setdefault("SYSGROW_DEBUG", "True")

from app import create_app, socketio

app = create_app(bootstrap_runtime=True)

if __name__ == "__main__":
    host = os.environ.get("SYSGROW_HOST", "0.0.0.0")
    port = int(os.environ.get("SYSGROW_PORT", "8000"))

    print(f"\n  🌱  SYSGrow dev server → http://{host}:{port}\n")

    try:
        socketio.run(
            app,
            host=host,
            port=port,
            debug=True,
            use_reloader=True,
            allow_unsafe_werkzeug=True,
        )
    except KeyboardInterrupt:
        print("\n  ⏹  Stopped.")
