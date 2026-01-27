"""Debug Flask run"""
import os
import sys
import pytest
from flask import Flask

# Skip live server run in sandbox/CI unless explicitly enabled.
if os.getenv("SYSGROW_RUN_LIVE_SERVER_TESTS") != "1":
    pytest.skip("Skipping live Flask run test (requires binding to localhost)", allow_module_level=True)

os.environ["SYSGROW_ENABLE_MQTT"] = "False"
os.environ["SYSGROW_ENABLE_REDIS"] = "False"
os.environ["DATABASE_PATH"] = "database/sysgrow.db"

# Create minimal app
app = Flask(__name__)

@app.route("/")
def home():
    return "Working!"

print("Step 1: App created")
print("Step 2: About to call app.run()...")
print("Step 3: If you see this BEFORE 'Running on...', there's a problem")

app.run(host="localhost", port=5000, debug=False, use_reloader=False)

print("Step 4: app.run() returned - server stopped")
