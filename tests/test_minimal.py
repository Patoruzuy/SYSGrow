"""Minimal Flask test"""
import os
import pytest
from flask import Flask

# Skip live server run unless explicitly enabled.
if os.getenv("SYSGROW_RUN_LIVE_SERVER_TESTS") != "1":
    pytest.skip("Skipping minimal live server test (requires binding to localhost)", allow_module_level=True)

app = Flask(__name__)

@app.route('/')
def index():
    return "Hello World!"

print("Starting minimal Flask server...")
app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
print("Server stopped")
