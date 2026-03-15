"""Debug server startup"""
import os
import secrets
import traceback

try:
    os.environ['FLASK_SECRET_KEY'] = secrets.token_hex(32)
    os.environ['FLASK_ENV'] = 'development'
    os.environ['DATABASE_PATH'] = 'sysgrow_dev.db'
    os.environ['SYSGROW_ENABLE_MQTT'] = 'False'

    print("Importing app...")
    from app import create_app, socketio

    print("Creating app...")
    app = create_app(bootstrap_runtime=True)
    
    print("Starting server on http://localhost:5000")
    socketio.run(app, host='127.0.0.1', port=5000, debug=False, allow_unsafe_werkzeug=True)
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    traceback.print_exc()
    input("\nPress Enter to exit...")
