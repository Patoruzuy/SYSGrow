"""Minimal server test to diagnose startup issues."""
from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, async_mode='threading')

@app.route('/')
def hello():
    return "Hello World!"

if __name__ == '__main__':
    print("Starting minimal server...")
    try:
        socketio.run(app, host='0.0.0.0', port=8000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)
        print("Server stopped normally")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
