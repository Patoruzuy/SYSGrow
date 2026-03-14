# 🌱 SYSGrow - Smart Agriculture

<div align="center">

![SYSGrow Logo](https://img.shields.io/badge/SYSGrow-Smart_Agriculture-green?style=for-the-badge)
[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg?style=flat-square&logo=python)](https://www.python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0+-black.svg?style=flat-square&logo=flask)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

**An intelligent IoT-powered agriculture managementsystem for monitoring and optimizing plant growth environments.**

**An intelligent IoT-powered agriculture management system / Un sistema inteligente de gestión agrícola con IoT**

[English](#english) • [Español](#español) • [Features](#-features) • [Quick Start](#-quick-start)

</div>

---

## 🌐 Choose Your Language / Elige Tu Idioma

### 🇺🇸 English
[Read the English documentation](#english) | [Latest Release Notes](releases/v1.1.0-RELEASE-EN.md)

### 🇪🇸 Español
[Lee la documentación en español](#español) | [Notas de la Última Versión](releases/v1.1.0-RELEASE-ES.md)

---

## English

<div id="english">

### 📖 What's This All About?

SYSGrow is like that friend who remembers to water your plants when you're on vacation, but with more bells and whistles. We combine IoT gadgets, machine learning magic, and real-time monitoring to make your plants happier. Whether you're managing a small indoor garden or a large-scale greenhouse operation, SYSGrow provides the tools you need.

### 🎯 What It Actually Does

- **Growth Unit Management** - Organize and monitor multiple growing spaces (Keep track of your green babies)
- **Real-time Environmental Monitoring** - Track temperature, humidity, soil moisture, CO2, and light levels (Because plants can't talk (yet))
- **Intelligent Device Control** - Automated scheduling for lights, pumps, fans, and more (Schedules so smart they'll make your plants feel pampered)
- **Plant Health Tracking** - Monitor growth stages and detect issues early (Catch problems before your plants start looking sad)
- **ESP32 Integration** - Full support for ESP32-C3/C6 IoT devices (Fancy IoT devices that do the heavy lifting)
- **Machine Learning** - Predictive analytics for optimal growth condition (Fancy algorithms that predict when your plants need a drink)
- **Energy Monitoring** - Save electricity by tracking power consumption and optimizing efficiency
- **Camera Integration** - Spy on your plants 24/7 (they love the attention)

---

## ✨ The Good Stuff

### 🌿 Plant Parenting 2.0
- **Multi-Unit Support** - Because one garden is never enough
- **Dimensions Tracking** - For when you need to know if that giant pumpkin will fit
- **Plant Profiles** - 500+ plant species that won't judge your gardening skills
- **Growth Stage Tracking** - From "tiny seed" to "look at this absolute unit"
- **Custom Grow Cycles** - Because every plant has its own drama

### 🤖 Tech That Doesn't Suck
- **Device Scheduling** - Set it and forget it (like a good asado)
- **Midnight Crossing Support** - For plants that like to party all night
- **Multi-Protocol Support** - WiFi, ZigBee, BLE - we speak all the languages
- **OTA Updates** - Update your devices without getting off the couch
- **Relay Control** - Flipping switches like a professional electrician (but safer)
- **Irrigation Management** - Water your plants while you relax

### 📊 Data Nerd Heaven
- **Real-time Dashboards** - Live environmental data visualization (Pretty graphs that make you look smart)
- **Historical Data** - Remember that one time your temperature sensor went crazy?
- **Energy Profiling** - Find out which device is sucking all the power
- **ML-Powered Insights** - RandomForest models for growth predictions (AI that's actually useful)
- **Health Monitoring** - Disease and pest detection algorithms (Catch plant diseases before they become a telenovela)
- **Performance Metrics** - System health and device status tracking (Numbers that make you feel productive)

---

## 🚀 Let's Get This Party Started

### What You'll Need

- **Python 3.8+** - The magic sauce
- **Git** - For copying stuff from the internet
- **SQLite3** - Comes with Python (like fries with a burger)

### Installation (The Fun Part)

#### 1️⃣ Clone This Thing
```bash
git clone https://github.com/yourusername/SYSGrow.git
cd SYSGrow
```

#### 2️⃣ Create Virtual Environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

#### 3️⃣ Install Dependencies
```bash
# Essential dependencies (recommended for Windows)
pip install -r requirements-essential.txt

# Or full installation
pip install -r requirements.txt

# Or development installation
pip install -e .
```

#### 4️⃣ Initialize Database
```bash
python -c "from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler; SQLiteDatabaseHandler('sysgrow.db').initialize_database()"
```

#### 5️⃣ Run the Application
```bash
# Development server
python start_dev.py

# Or production server
python smart_agriculture_app.py
```

#### 6️⃣ Access the Application
Open your browser and navigate to:
- **Web Interface**: http://localhost:5000
- **API Documentation**: http://localhost:5000/api/docs

### 🎬 Quick Start Scripts

**Windows Users:**
```bash
# One-click installation
install_windows.bat

# One-click server start
start_server.bat
```

**All Platforms:**
```bash
# Development mode with auto-reload
python start_dev.py

# Debug mode with detailed logging
python debug_server.py
```

---

## 📚 Documentation

Comprehensive documentation is available in the [`docs/`](docs/) directory.

### 📖 Essential Reading

| Document | Description |
|----------|-------------|
| **[Quick Start Guide](docs/setup/QUICK_START.md)** | Get running in 5 minutes |
| **[Installation Guide](docs/setup/INSTALLATION_GUIDE.md)** | Detailed setup instructions |
| **[API Documentation](docs/api/API_SUMMARY.md)** | Complete API reference |
| **[Architecture Guide](docs/architecture/ARCHITECTURE.md)** | System design overview |
| **[Repository Guidelines](AGENTS.md)** | Contributor guide, project layout, and workflow |
| **[Development Guide](docs/development/SERVICES.md)** | Contributing guidelines |

### 🗂️ Documentation Structure

```
docs/
├── setup/              # Installation & configuration guides
├── api/                # API documentation & examples
├── architecture/       # System design & architecture
├── development/        # Development guides & standards
└── legacy/            # Historical documentation
```

**Full Index**: See [docs/INDEX.md](docs/INDEX.md) for complete documentation catalog.

---

## 🏗️ Architecture

SYSGrow follows a modern, modular architecture designed for scalability and maintainability.

### System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Web Interface                     │
│            (Flask + Jinja2 Templates)               │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────┐
│              Application Layer (Flask)              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐│
│  │ API Routes   │  │ UI Routes    │  │ WebSocket ││
│  │ (REST/JSON)  │  │ (Templates)  │  │ (SocketIO)││
│  └──────────────┘  └──────────────┘  └───────────┘│
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────┐
│              Service Layer (Business Logic)         │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌─────────┐│
│  │ Growth   │ │ Device   │ │Settings │ │ Climate ││
│  │ Service  │ │ Service  │ │ Service │ │ Service ││
│  └──────────┘ └──────────┘ └─────────┘ └─────────┘│
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────┐
│           Infrastructure Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────┐│
│  │ Database     │  │ MQTT Broker  │  │ EventBus  ││
│  │ (SQLite)     │  │ (IoT Comms)  │  │ (Cache)   ││
│  └──────────────┘  └──────────────┘  └───────────┘│
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────┴────────────────────────────────┐
│              IoT Device Layer                       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐│
│  │ ESP32-C3 │ │ ESP32-C6 │ │ Sensors  │ │ Relays ││
│  │ Sensors  │ │ Irrigation│ │ (DHT22)  │ │ (WiFi) ││
│  └──────────┘ └──────────┘ └──────────┘ └────────┘│
└─────────────────────────────────────────────────────┘
```

### Core Components

#### **Application Layer**
- **Flask Framework** - Web application server
- **Blueprint Architecture** - Modular route organization
- **Jinja2 Templates** - Server-side rendering
- **SocketIO** - Real-time bidirectional communication

#### **Service Layer**
- **GrowthService** - Growth unit management and orchestration
- **DeviceService** - IoT device registration and control
- **PlantService** - Plant profiles and growth tracking
- **EnergyService** - Power monitoring and optimization
- **MLService** - Machine learning model training and inference

#### **Infrastructure Layer**
- **SQLite Database** - Persistent data storage (15+ tables)
- **MQTT Broker** - IoT device communication
- **Event Bus** - Asynchronous event handling

#### **Domain Models**
- **UnitRuntime** - Individual growth unit runtime state
- **DeviceSchedule** - Time-based device automation
- **PlantProfile** - Plant-specific growth requirements
- **SensorReading** - Environmental measurement data

---

## 💾 Database Schema

SYSGrow uses SQLite with a comprehensive schema:

### Core Tables
- **GrowthUnits** - Growth unit configurations
- **Plants** - Plant instances and tracking
- **Users** - User authentication and profiles
- **Settings** - System configuration

### Device Management
- **Devices** - IoT device registry
- **Sensors** - Sensor configurations
- **Relays** - Relay control configurations
- **SensorReadings** - Historical sensor data

### Energy Monitoring
- **ZigBeeEnergyMonitors** - ZigBee device registry
- **EnergyConsumption** - Power usage tracking
- **DeviceEnergyProfiles** - Device power characteristics

### Machine Learning
- **MLTrainingData** - Training dataset
- **MLModelTraining** - Model training history
- **PlantHealthLogs** - Disease/pest detection

### Analytics
- **Analytics** - System-wide analytics data
- **EnvironmentInfo** - Environmental metadata

---

## 🛠️ Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Python 3.8+, Flask 3.0, SQLAlchemy |
| **Database** | SQLite3 |
| **IoT** | MQTT, ESP32-C3/C6, ZigBee, BLE |
| **ML/AI** | scikit-learn, RandomForest, pandas |
| **Frontend** | Jinja2, JavaScript (Vanilla), CSS3 |
| **Real-time** | SocketIO, WebSockets |
| **Testing** | pytest, unittest |
| **Deployment** | Gunicorn, systemd |

---

## 📱 Mobile & Desktop Apps

SYSGrow supports companion applications:

**Features:**
- Real-time monitoring
- Push notifications
- BLE device provisioning
- mDNS service discovery
- Camera controls

### ESP32 Firmware
```bash
cd ../ESP32-C6-Firmware
platformio run --target upload
```

**Modules:**
- **ESP32-C6-Sensors** - Environmental sensing
- **ESP32-C6-Relays** - Relay control
- **ESP32-C3-Analog-Sensors** - Analog input

---

## 🔧 Configuration

### Application Settings

Edit `app/config.py` for advanced configuration:
- Database connection pooling
- MQTT reconnection settings
- Logging levels
- ML model parameters

---

## 🧪 Testing

### Run Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_growth_service.py

# Run with coverage
pytest --cov=app --cov-report=html

# Run integration tests
pytest tests/integration/
```
---

## 🚢 Deployment

### Production Deployment

#### Using Gunicorn
```bash
gunicorn -w 4 -b 0.0.0.0:8000 smart_agriculture_app:app
```

#### Using systemd Service
```bash
sudo cp sysgrow.service /etc/systemd/system/
sudo systemctl enable sysgrow
sudo systemctl start sysgrow
```

#### Docker Deployment
```bash
docker build -t sysgrow-backend .
docker run -d -p 5000:5000 --name sysgrow sysgrow-backend
```

### Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /socket.io {
        proxy_pass http://localhost:5000/socket.io;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## 🤝 Want to Help? You're Awesome!

We love contributions! If you can code, design, or just tell good jokes, we want you

### How to Be a Hero

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/my-awesome-idea
   ```
3. **Make your changes**
4. **Run tests**
   ```bash
   pytest
   ```
5. **Commit your changes**
   ```bash
   git commit -m 'Add amazing feature'
   ```
6. **Push to the branch**
   ```bash
   git push origin feature/my-awesome-idea
   ```
7. **Open a Pull Request**

### Coding Standards

- Follow PEP 8 style guide
- Use type hints for function signatures
- Write docstrings for all public methods
- Add unit tests for new features
- Update documentation for API changes

### Commit Message Convention

```
type(scope): subject

body (optional)

footer (optional)
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

**Example:**
```
feat(growth): add device schedule midnight crossing support

Implement logic to handle schedules that span across midnight
(e.g., 22:00-06:00) for proper device activation.

Closes #123
```

---

## 📋 Roadmap

### v1.2.0 (Planned)
- [ ] Weather API integration
- [ ] Cloud backup and sync
- [ ] Multi-user access control
- [ ] Advanced ML models (LSTM for predictions)

### v1.3.0 (Future)
- [ ] Voice assistant integration (Alexa, Google)
- [ ] Marketplace for plant profiles
- [ ] Community sharing features
- [ ] Advanced analytics dashboard
- [ ] Automated pest control integration

### v2.0.0 (Vision)
- [ ] Mobile application
- [ ] Full irrigation system with nutrients
- [ ] GraphQL API
- [ ] Real-time collaboration
- [ ] AI-powered growth optimization

---

## 🐛 Troubleshooting

### Common Issues

**Issue: Database locked error**
```bash
# Solution: Close all connections and restart
rm sysgrow.db-journal
python smart_agriculture_app.py
```

**Issue: MQTT connection failed**
```bash
# Check MQTT broker is running
sudo systemctl status mosquitto

# Test connection
mosquitto_sub -h localhost -t "test/#"
```

**Issue: Import errors on Windows**
```bash
# Use essential requirements
pip install -r requirements-essential.txt
```

**More Help**: See [Windows Success Guide](docs/setup/WINDOWS_SUCCESS.md)

---

## 📊 Project Status

### Latest Release
**Version:** 1.1.0  
**Release Date:** November 9, 2025  
**Status:**  Ready

### Build Status
![Tests](https://img.shields.io/badge/tests-passing-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-85%25-green)
![Build](https://img.shields.io/badge/build-passing-success)

---

## 📄 Legal Stuff (Boring but Important)

This project is licensed under the MIT License - which basically means "do whatever you want, but don't blame us if your plants die." see the [LICENSE](LICENSE) file for details.

---

## 💬 Community & Support

### Need Help? We Got You

- 📖 [Documentation] The manual you'll actually read (docs/)
- 🐛 [Issue Tracker] For when things go wrong (<https://github.com/yourusername/SYSGrow/issues>)
- 📧 [Email Support] Come chat about plants and stuff(<mailto:patoruzuy@tutanota.com>)


<div align="center">

**Made with 💚, ☕, and the occasional 🍕 for smart agriculture**

[⬆ Back to top](#-sysgrow---smart-agriculture-backend)

</div>
