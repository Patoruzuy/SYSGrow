"""Test pure Flask server."""
import os
import pytest
from flask import Flask

# Skip live server tests unless explicitly enabled.
if os.getenv("SYSGROW_RUN_LIVE_SERVER_TESTS") != "1":
    pytest.skip("Skipping pure Flask live server test", allow_module_level=True)

app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello World!"

if __name__ == '__main__':
    print("Starting Flask server...")
    app.run(host='0.0.0.0', port=8000, debug=False, use_reloader=False)
    print("Server stopped")
