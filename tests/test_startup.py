"""Test script to debug server startup issues."""
import logging
import sys
import traceback
import os
import pytest

# Skip live server startup unless explicitly enabled.
if os.getenv("SYSGROW_RUN_LIVE_SERVER_TESTS") != "1":
    pytest.skip("Skipping startup SocketIO live server test", allow_module_level=True)

# Enable all logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

try:
    print("=" * 80)
    print("Step 1: Importing app module...")
    from app import create_app, socketio
    print("SUCCESS: Import successful")
    
    print("\n" + "=" * 80)
    print("Step 2: Creating Flask app...")
    app = create_app()
    print("SUCCESS: App creation successful")
    
    print("\n" + "=" * 80)
    print("Step 3: Starting SocketIO server...")
    print("Host: 0.0.0.0, Port: 8000")
    
    socketio.run(app, host="0.0.0.0", port=8000, debug=True)
    
except Exception as e:
    print("\n" + "=" * 80)
    print("ERROR OCCURRED:")
    print("=" * 80)
    print(f"Error type: {type(e).__name__}")
    print(f"Error message: {str(e)}")
    print("\nFull traceback:")
    traceback.print_exc()
    sys.exit(1)
