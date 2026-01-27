"""Debug socketio"""
import os
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ['SYSGROW_ENABLE_MQTT'] = 'False'
os.environ['SYSGROW_ENABLE_REDIS'] = 'False'
os.environ['DATABASE_PATH'] = 'database/sysgrow.db'

from app import create_app, socketio

app = create_app(bootstrap_runtime=True)

print(f"SocketIO async_mode: {socketio.async_mode}")
print(f"SocketIO server: {socketio.server}")
print(f"App has socketio: {hasattr(app, 'socketio')}")

print("\nTrying to start server...")
try:
    # Try with explicit parameters
    socketio.run(
        app, 
        host='0.0.0.0', 
        port=5000, 
        debug=False, 
        use_reloader=False,
        log_output=True,
        allow_unsafe_werkzeug=True  # In case of Werkzeug version issue
    )
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("Server stopped")
