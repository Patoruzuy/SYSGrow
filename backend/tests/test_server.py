"""Quick test server without SocketIO - Unicode safe for Windows"""
import os
import sys
import pytest

# Skip live server tests unless explicitly enabled.
if os.getenv("SYSGROW_RUN_LIVE_SERVER_TESTS") != "1":
    pytest.skip("Skipping Flask server test (requires binding to localhost)", allow_module_level=True)

# Fix Unicode output on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

# Disable external services
os.environ['SYSGROW_ENABLE_MQTT'] = 'False'
os.environ['SYSGROW_ENABLE_REDIS'] = 'False'
os.environ['DATABASE_PATH'] = 'database/sysgrow.db'

print("Loading Flask app...")
from app import create_app

app = create_app()
print("[SUCCESS] App loaded!")
print("Starting server on http://localhost:5000")
print("Press Ctrl+C to stop\n")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
