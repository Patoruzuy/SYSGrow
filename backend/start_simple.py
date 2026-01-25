"""Simple server startup without debug mode"""
import os
import secrets

# Set environment
os.environ['FLASK_SECRET_KEY'] = secrets.token_hex(32)
os.environ['FLASK_ENV'] = 'development'
os.environ['DATABASE_PATH'] = 'sysgrow_dev.db'
os.environ['SYSGROW_ENABLE_MQTT'] = 'False'

from app import create_app, socketio

print("\n🌱 Starting SYSGrow Backend...")
print("📊 http://localhost:5000/static/harvest_report.html")
print("⏳ Loading...\n")

app = create_app(bootstrap_runtime=True)
socketio.run(app, host='127.0.0.1', port=5000, debug=False, allow_unsafe_werkzeug=True)
