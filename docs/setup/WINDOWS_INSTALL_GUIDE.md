# 🪟 SYSGrow Backend - Windows Installation Guide

## 🚀 Quick Start for Windows Users

This guide will help you install and run the SYSGrow backend on Windows 10/11.

### ✅ Prerequisites

- **Python 3.11+** (Recommended: Python 3.11 or 3.12)
- **Git** (to clone the repository)
- **PowerShell** or **Command Prompt** with administrator privileges

### 📦 Step-by-Step Installation

#### 1. **Clone the Repository**
```powershell
git clone <repository-url>
cd SYSGrow\backend
```

#### 2. **Create Virtual Environment**
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate

# You should see (venv) in your prompt
```

#### 3. **Install Core Dependencies**
```powershell
# Install essential dependencies (works on Windows)
pip install -r requirements-essential.txt

# OR install manually if needed:
pip install Flask>=2.3.0 Flask-SocketIO>=5.3.0 bcrypt pycryptodome paho-mqtt requests schedule python-dateutil pytz pytest
```

#### 4. **Start the Development Server**
```powershell
# Use the development starter script
python start_dev.py
```

You should see:
```
🌱 SYSGrow Backend Starting...
📊 Access the web interface at: http://localhost:5000
🔧 Development mode enabled
```

#### 5. **Access the Application**
Open your web browser and go to: **http://localhost:5000**

---

## 🔧 Troubleshooting

### Common Issues and Solutions

#### ❌ **Issue**: "No module named 'bcrypt'"
**Solution:**
```powershell
pip install bcrypt
```

#### ❌ **Issue**: "No module named 'Crypto'"
**Solution:**
```powershell
pip install pycryptodome
```

#### ❌ **Issue**: Dependencies won't install
**Solutions:**
1. **Update pip first:**
   ```powershell
   python -m pip install --upgrade pip
   ```

2. **Use essential requirements:**
   ```powershell
   pip install -r requirements-essential.txt
   ```

3. **Install manually one by one:**
   ```powershell
   pip install Flask
   pip install Flask-SocketIO
   pip install paho-mqtt
   pip install requests
   pip install bcrypt
   pip install pycryptodome
   ```

#### ❌ **Issue**: "sqlite3.Connection object has no attribute 'fetchall'"
**Solution:** This is fixed in the latest version. Make sure you have the updated code.

#### ❌ **Issue**: "Missing SECRET_KEY environment variable"
**Solution:** Use the `start_dev.py` script which automatically sets development keys.

#### ❌ **Issue**: Platform-specific dependencies fail
**Solution:** These are optional on Windows:
- `RPi.GPIO` - Only needed for Raspberry Pi
- `zigpy` libraries - Only needed for ZigBee hardware
- `adafruit-*` libraries - Only needed for specific sensors

---

## 📋 Available Requirements Files

### `requirements-essential.txt` ✅ **Recommended for Windows**
- Core dependencies that work reliably on Windows
- Perfect for development and testing
- Minimal set needed to run the application

### `requirements-windows.txt` 🔧 **For Production**
- More complete set of dependencies
- Includes visualization and advanced features
- May require additional setup

### `requirements-minimal.txt` 🧪 **For Testing**
- Absolute minimum dependencies
- Use for troubleshooting

### `requirements.txt` ⚠️ **Full Feature Set**
- Complete dependencies including hardware-specific ones
- Some may not work on Windows without additional setup

---

## 🧪 Testing Your Installation

Run the dependency checker:
```powershell
python test_deps.py
```

This will show you:
- ✅ Working dependencies
- ❌ Missing dependencies
- 🧪 Basic functionality tests

---

## 🎯 Development Setup

For development work, you may want additional tools:

```powershell
# Install development dependencies (optional)
pip install pytest black flake8 mypy

# Or use the development requirements (may have compatibility issues)
pip install -r requirements-dev-windows.txt
```

---

## 🌐 Using the Application

### Web Interface
- **Main Dashboard**: http://localhost:5000
- **Settings**: http://localhost:5000/settings
- **Device Management**: http://localhost:5000/devices

### API Endpoints
- **Sensor Data**: http://localhost:5000/api/sensors
- **Device Control**: http://localhost:5000/api/devices
- **Energy Monitoring**: http://localhost:5000/api/energy

---

## 📁 Project Structure (Windows Paths)

```
E:\Work\SYSGrow\backend\
├── app\                    # Flask application
├── templates\              # HTML templates
├── static\                 # CSS, JS, images
├── infrastructure\         # Database and core services
├── devices\               # Device controllers
├── ai\                    # Machine learning modules
├── start_dev.py           # Windows development starter
├── test_deps.py           # Dependency checker
├── requirements-essential.txt  # Windows-compatible deps
└── sysgrow_dev.db         # SQLite database (created automatically)
```

---

## 🔒 Security Notes

- The development server uses auto-generated secret keys
- For production, set proper environment variables:
  ```powershell
  set FLASK_SECRET_KEY=your-production-secret-key
  set FLASK_ENV=production
  ```

---

## 🆘 Getting Help

### If you encounter issues:

1. **Check dependencies:**
   ```powershell
   python test_deps.py
   ```

2. **Check Python version:**
   ```powershell
   python --version
   # Should be 3.8 or higher
   ```

3. **Try minimal installation:**
   ```powershell
   pip install Flask Flask-SocketIO paho-mqtt
   python start_dev.py
   ```

4. **Check for errors in the terminal output**

### Common Commands

```powershell
# Activate virtual environment
venv\Scripts\activate

# Deactivate virtual environment
deactivate

# Update pip
python -m pip install --upgrade pip

# Install specific package
pip install package-name

# List installed packages
pip list

# Start development server
python start_dev.py

# Run tests
python test_deps.py
```

---

## 🎉 Success!

If you see this message, you're ready to go:

```
🌱 SYSGrow Backend Starting...
📊 Access the web interface at: http://localhost:5000
🔧 Development mode enabled
```

**Next Steps:**
1. Open http://localhost:5000 in your browser
2. Configure your devices in the settings
3. Start monitoring your plants! 🌱

---

## 📈 Optional: Advanced Features

After the basic installation works, you can add:

### Machine Learning Features
```powershell
pip install numpy pandas scikit-learn
```

### Visualization
```powershell
pip install matplotlib plotly seaborn
```

### Computer Vision
```powershell
pip install opencv-python Pillow
```

### ZigBee Support (Linux/Raspberry Pi only)
```powershell
# Skip on Windows - not supported
```

---

*Happy growing! 🌱*
