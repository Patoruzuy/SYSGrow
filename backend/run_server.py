"""Flask server that stays alive"""
import os
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

os.environ['SYSGROW_ENABLE_MQTT'] = 'True'
os.environ['DATABASE_PATH'] = 'database/sysgrow.db'

from app import create_app, socketio

app = create_app(bootstrap_runtime=True)

# Get port from environment or use default
port = int(os.environ.get('FLASK_RUN_PORT', 8000))

print(f"Server starting on http://0.0.0.0:{port}")
print("Press Ctrl+C to stop\n")

if __name__ == '__main__':
    try:
        # Use socketio.run() instead of app.run() for WebSocket support
        socketio.run(
            app,
            host='0.0.0.0',
            port=port,
            debug=False,
            use_reloader=False,
            allow_unsafe_werkzeug=True
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"\nServer error: {e}")
        import traceback
        traceback.print_exc()
