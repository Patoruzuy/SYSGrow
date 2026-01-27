"""Test if server stays up"""
import os
import sys
import time
import pytest

# Skip live server run unless explicitly enabled.
if os.getenv("SYSGROW_RUN_LIVE_SERVER_TESTS") != "1":
    pytest.skip("Skipping SocketIO live server test (requires binding to localhost)", allow_module_level=True)

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

os.environ['SYSGROW_ENABLE_MQTT'] = 'False'
os.environ['SYSGROW_ENABLE_REDIS'] = 'False'
os.environ['DATABASE_PATH'] = 'database/sysgrow.db'

print("Loading app...")
from app import create_app, socketio

app = create_app()
print("[OK] App created")

print("About to call socketio.run()...")
print("Server will be at: http://localhost:5000")

socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, log_output=True)

print("socketio.run() returned - this should not happen unless server stopped")
