"""Simple test runner for debugging the Flask app"""
from app import create_app, socketio
import os

if __name__ == "__main__":
    try:
        app = create_app(bootstrap_runtime=True)
        print("App created successfully")
        
        # Try to start the server
        host = os.getenv("SYSGROW_HOST", "0.0.0.0")
        port = int(os.getenv("SYSGROW_PORT", "8001"))
        
        print(f"Starting server on {host}:{port}")
        
        socketio.run(
            app,
            host=host,
            port=port,
            debug=True,
            allow_unsafe_werkzeug=True
        )
        
    except Exception as e:
        print(f"Error starting server: {e}")
        import traceback
        traceback.print_exc()
