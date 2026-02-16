# Simple test script to check basic functionality and identify missing dependencies

import os
import sys

print("🔍 SYSGrow Dependency Checker")
print("=" * 50)

# Test core imports
tests = [
    ("Flask", "flask"),
    ("Flask-SocketIO", "flask_socketio"),
    ("MQTT Client", "paho.mqtt.client"),
    ("Requests", "requests"),
    ("BCrypt", "bcrypt"),
    ("Schedule", "schedule"),
    ("SQLite3", "sqlite3"),
    ("DateTime utils", "dateutil"),
    ("Crypto", "Crypto.Cipher"),
]

missing_deps = []
working_deps = []

for name, module in tests:
    try:
        __import__(module)
        print(f"✅ {name:<20} - OK")
        working_deps.append(name)
    except ImportError as e:
        print(f"❌ {name:<20} - MISSING: {e}")
        missing_deps.append((name, module))

print("\n" + "=" * 50)
print(f"✅ Working dependencies: {len(working_deps)}")
print(f"❌ Missing dependencies: {len(missing_deps)}")

if missing_deps:
    print("\n📦 Install missing dependencies:")
    for name, module in missing_deps:
        if module == "dateutil":
            print(f"   pip install python-dateutil")
        elif module == "Crypto.Cipher":
            print(f"   pip install pycryptodome")
        else:
            print(f"   pip install {module.replace('.', '-')}")

# Test basic Flask app
print("\n🧪 Testing basic Flask functionality...")
try:
    from flask import Flask
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'test-key'

    @app.route('/')
    def hello():
        return "SYSGrow Backend is working!"

    print("✅ Basic Flask app creation successful")

    # Test SQLite
    import sqlite3
    conn = sqlite3.connect(':memory:')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE test (id INTEGER PRIMARY KEY)')
    cursor.execute('INSERT INTO test (id) VALUES (1)')
    conn.commit()
    result = cursor.fetchone()
    conn.close()
    print("✅ SQLite database operations working")

except Exception as e:
    print(f"❌ Flask/SQLite test failed: {e}")

print("\n🎯 Next Steps:")
if missing_deps:
    print("1. Install missing dependencies listed above")
    print("2. Run this test again to verify installation")
else:
    print("1. All core dependencies are available!")
    print("2. Try running the application with: python start_dev.py")

print("\n💡 For Windows development, use: pip install -r requirements-essential.txt")
