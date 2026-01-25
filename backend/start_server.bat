@echo off
echo.
echo 🌱 Starting SYSGrow Backend...
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ❌ Virtual environment not found
    echo Please run install_windows.bat first
    pause
    exit /b 1
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Start the server
echo 🚀 Launching development server...
python start_dev.py