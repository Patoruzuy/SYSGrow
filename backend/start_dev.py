# Simple startup script for SYSGrow on Windows
# This sets basic environment variables and starts the application

import os
import secrets

# Set required environment variables if not already set
if not os.getenv('SYSGROW_SECRET_KEY') and not os.getenv('FLASK_SECRET_KEY'):
    # Generate a random secret key for development
    secret_key = secrets.token_hex(32)
    os.environ['FLASK_SECRET_KEY'] = secret_key
    print(f"Generated development secret key: {secret_key}")

# Set other default environment variables
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('FLASK_DEBUG', 'True')
os.environ.setdefault('DATABASE_PATH', 'sysgrow_dev.db')

print("Starting SYSGrow Backend...")
print("Environment variables set:")
print(f"  FLASK_ENV: {os.getenv('FLASK_ENV')}")
print(f"  FLASK_DEBUG: {os.getenv('FLASK_DEBUG')}")
print(f"  DATABASE_PATH: {os.getenv('DATABASE_PATH')}")

# Import and start the application
try:
    from app import create_app, socketio
    
    app = create_app(bootstrap_runtime=True)
    
    print("\n🌱 SYSGrow Backend Starting...")
    print("📊 Access the web interface at: http://localhost:5000")
    print("🔧 Development mode enabled")
    print("\nPress Ctrl+C to stop the server\n")
    
    # Run the application
    try:
        socketio.run(app, host='0.0.0.0', port=5000, debug=True)
    except Exception as run_error:
        print(f"\n❌ Server runtime error: {run_error}")
        import traceback
        traceback.print_exc()
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("\n💡 Missing dependencies. Please install required packages:")
    print("   pip install -r requirements-windows.txt")
    
except Exception as e:
    print(f"❌ Error starting application: {e}")
    print("\n💡 Check the error message above and install missing dependencies")
