# SYSGrow Backend Installation & Setup Guide

## 🚀 Quick Start

### Prerequisites
- Python 3.8+ 
- Git
- SQLite3
- Redis (optional, for caching)
- Node.js (for mobile app development)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd SYSGrow/backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/macOS
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   # Basic installation
   pip install -r requirements.txt
   
   # Development installation (includes testing tools)
   pip install -r requirements-dev.txt
   
   # Or install using setup.py
   pip install -e .
   ```

4. **Database setup**
   ```bash
   python -c "from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler; SQLiteDatabaseHandler('sysgrow.db').initialize_database()"
   ```

5. **Run the application**
   ```bash
   python smart_agriculture_app.py
   ```

## 📋 Dependency Categories

### Core Framework
- **Flask**: Web framework for API and web interface
- **Flask-SocketIO**: Real-time communication with frontend
- **Werkzeug**: WSGI utilities

### Communication
- **paho-mqtt**: MQTT client for IoT device communication
- **requests**: HTTP client for REST API calls
- **aiohttp**: Async HTTP client/server

### Database & Storage
- **sqlite3**: Database operations
- **redis**: Caching and session storage

### Security
- **pycryptodome**: Encryption for device communication
- **cryptography**: Security utilities

### Machine Learning & Data Science
- **scikit-learn**: ML algorithms for plant growth prediction
- **pandas**: Data manipulation and analysis
- **numpy**: Numerical computing
- **joblib**: ML model serialization

### IoT & Hardware
- **zigpy**: ZigBee protocol support
- **RPi.GPIO**: Raspberry Pi GPIO control (Linux only)
- **adafruit-circuitpython-ads1x15**: ADC sensor support

### Scheduling & Automation
- **schedule**: Simple job scheduling
- **APScheduler**: Advanced scheduling

### Visualization
- **matplotlib**: Basic plotting
- **plotly**: Interactive visualizations
- **seaborn**: Statistical plotting

### Development & Testing
- **pytest**: Testing framework
- **black**: Code formatting
- **flake8**: Code linting
- **mypy**: Type checking

## 🏗️ Project Structure

```
backend/
├── app/                    # Flask application
│   ├── blueprints/         # Route blueprints
│   ├── security/           # Authentication & security
│   └── services/           # Business logic services
├── ai/                     # Machine learning modules
│   ├── enhanced_ml_trainer.py
│   ├── plant_health_monitor.py
│   └── ml_model.py
├── devices/                # Device controllers
│   ├── zigbee_energy_monitor.py
│   ├── camera_manager.py
│   └── actuator_controller.py
├── environment/            # Environment monitoring
│   ├── environment_collector.py
│   └── control_logic.py
├── infrastructure/         # Core infrastructure
│   └── database/
│       └── sqlite_handler.py
├── app/
│   └── blueprints/api/     # API endpoints
├── templates/              # HTML templates
├── static/                 # CSS, JS, images
├── tests/                  # Test suites
└── requirements.txt        # Dependencies
```

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the backend directory:

```env
# Database
DATABASE_PATH=sysgrow.db

# MQTT
MQTT_BROKER=localhost
MQTT_PORT=1883
MQTT_USERNAME=
MQTT_PASSWORD=

# Redis (optional)
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-32-byte-encryption-key

# ZigBee
ZIGBEE_COORDINATOR_PATH=/dev/ttyUSB0
ZIGBEE_CHANNEL=11

# ML Training
ML_TRAINING_SCHEDULE=02:00
ML_MODEL_PATH=models/

# Flask
FLASK_ENV=development
FLASK_DEBUG=True
```

### ZigBee Configuration
Create `config/zigbee_config.json`:

```json
{
    "coordinator": {
        "path": "/dev/ttyUSB0",
        "baudrate": 115200,
        "channel": 11
    },
    "network": {
        "pan_id": "0x1234",
        "extended_pan_id": "00:12:34:56:78:9a:bc:de",
        "network_key": "01:02:03:04:05:06:07:08:09:0a:0b:0c:0d:0e:0f:10"
    },
    "devices": {
        "energy_monitors": [],
        "sensors": [],
        "actuators": []
    }
}
```

## 🧪 Testing

Run the test suite:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest tests/test_ml_trainer.py

# Run tests in parallel
pytest -n auto
```

## 🚀 Deployment

### Development Server
```bash
python smart_agriculture_app.py
```

### Production Server (using Gunicorn)
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 smart_agriculture_app:app
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "smart_agriculture_app:app"]
```

## 🔍 Troubleshooting

### Common Issues

1. **ZigBee coordinator not found**
   - Check USB device permissions
   - Verify coordinator path in config
   - Install zigpy coordintor-specific library

2. **Redis connection errors**
   - Install and start Redis server
   - Check Redis configuration

3. **SQLite permission errors**
   - Check file permissions
   - Ensure directory exists

4. **MQTT connection failures**
   - Verify broker address and port
   - Check authentication credentials

### Dependency Issues

1. **Platform-specific dependencies**
   ```bash
   # Skip platform-specific packages
   pip install -r requirements.txt --no-deps
   
   # Install manually
   pip install Flask paho-mqtt scikit-learn
   ```

2. **Hardware library conflicts**
   ```bash
   # Skip hardware libraries on non-Pi systems
   pip install -r requirements.txt --ignore-installed RPi.GPIO
   ```

## 📈 Performance Optimization

### Database Optimization
- Regular VACUUM operations
- Proper indexing on frequently queried columns
- Connection pooling for high-load scenarios

### Memory Management
- Monitor ML model memory usage
- Implement model caching strategies
- Use lazy loading for large datasets

### Network Optimization
- MQTT message batching
- Compression for large payloads
- Connection keep-alive optimization

## 🔄 Database Migration

If upgrading from previous versions:

```bash
python -c "from database.schema_upgrade import upgrade_database; upgrade_database()"
```

## 📱 Mobile App Integration

The backend provides REST APIs for the mobile application. Key endpoints:

- `/api/sensors/*` - Sensor data
- `/api/devices/*` - Device control
- `/api/energy/*` - Energy monitoring
- `/api/plants/*` - Plant health data
- `/api/ml/*` - ML predictions

## 🎯 Next Steps

1. Configure your IoT devices (ESP32-C6 modules)
2. Set up ZigBee energy monitors
3. Install mobile application
4. Begin data collection and ML training

For detailed feature documentation, see:
- `ENHANCED_FEATURES_SETUP.md` - Enhanced features guide
- `ESP32-C6-User-Experience-Recommendations.md` - Device setup guide
- `docs/` directory for additional documentation

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section above
2. Review log files in `logs/` directory
3. Run tests to identify specific issues
4. Create issue with detailed error information
