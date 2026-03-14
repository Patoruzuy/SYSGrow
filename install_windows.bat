@echo off
echo.
echo ========================================
echo   SYSGrow Backend - Windows Installer
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    pause
    exit /b 1
)

echo ✅ Python found
python --version

echo.
echo 📦 Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ❌ Failed to create virtual environment
    pause
    exit /b 1
)

echo ✅ Virtual environment created

echo.
echo 🔧 Activating virtual environment...
call venv\Scripts\activate.bat

echo.
echo 📥 Installing dependencies...
pip install --upgrade pip
pip install -r requirements-essential.txt
if errorlevel 1 (
    echo.
    echo ⚠️  Essential requirements failed, trying minimal install...
    pip install Flask Flask-SocketIO paho-mqtt requests bcrypt pycryptodome schedule python-dateutil pytz
)

echo.
echo 🧪 Testing installation...
python test_deps.py

echo.
echo ========================================
echo   Installation Complete!
echo ========================================
echo.
echo To start the server:
echo   1. Run: venv\Scripts\activate
echo   2. Run: python start_dev.py
echo   3. Open: http://localhost:5000
echo.
echo Or simply double-click: start_server.bat
echo.
pause