<div align="center">

# 🌱 SYSGrow

**Raspberry Pi-first smart agriculture platform for local monitoring, automation, and control**

[![Author](https://img.shields.io/badge/author-Patoruzuy-2f855a)](https://github.com/Patoruzuy)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-3.x-000000?logo=flask)](https://flask.palletsprojects.com/)
[![SQLite](https://img.shields.io/badge/database-SQLite%20(WAL)-003B57?logo=sqlite)](https://sqlite.org/)
[![MQTT](https://img.shields.io/badge/protocol-MQTT-660066?logo=eclipsemosquitto)](https://mosquitto.org/)
[![Raspberry Pi](https://img.shields.io/badge/target-Raspberry%20Pi-C51A4A?logo=raspberrypi)](https://www.raspberrypi.com/)
[![License](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

[Quick Start](#-quick-start-raspberry-pi) · [Install Guide](docs/setup/INSTALLATION_GUIDE.md) · [Docs Index](docs/INDEX.md)

</div>

---

## ✨ Overview

SYSGrow turns a Raspberry Pi into a local smart-grow controller:

- 🌡️ Sensor monitoring
- 🔌 Actuator control
- 📡 MQTT integration for ESP32 devices
- 📈 Real-time dashboards (Socket.IO)
- 🧠 Optional ML/AI modules

Main API namespace: `/api/v1/*`

Author: **Patoruzuy**

## 🌟 Features

### 🌱 Grow Operations

- Multi-unit management from one dashboard
- Plant lifecycle tracking and journal records
- Configurable thresholds and schedules
- Harvest reporting and historical records

### 🔌 Devices and Hardware

- ESP32 integration over MQTT
- Sensor ingestion and calibration flows
- Actuator control (relays, pumps, fans, lights)
- Device health and infrastructure health endpoints

### 📊 Real-Time Monitoring

- Live dashboard updates through Socket.IO
- Environmental trends and analytics views
- Unit/device/system health breakdowns
- Alerting and notifications pipeline

### 🧠 AI/ML (Optional)

- Irrigation and growth-support ML services
- Plant health scoring and prediction endpoints
- Retraining and monitoring modules
- Analytics APIs for model and system insights

## 🏗️ Architecture Snapshot

```text
UI + API Blueprints
        ↓
Application Services
        ↓
Domain + Hardware Services
        ↓
Infrastructure (SQLite, repositories, MQTT)
```

## 🧰 Tech Stack

- Backend: Flask 3.x + Flask-SocketIO
- Data: SQLite (WAL mode)
- Messaging: MQTT (Mosquitto)
- Runtime: Python 3.11+
- Target: Raspberry Pi 3B+/4/5

## 🚀 Quick Start (Raspberry Pi)

### 1. Install system packages

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-dev \
  build-essential pkg-config libsystemd-dev sqlite3 mosquitto mosquitto-clients
```

### 2. Clone and enter project

```bash
git clone https://github.com/Patoruzuy/SYSGrow.git
cd SYSGrow
```

### 3. Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Initialize database

```bash
python -c "from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler; SQLiteDatabaseHandler('database/sysgrow.db').initialize_database()"
```

### 5. Start MQTT broker

```bash
sudo systemctl enable --now mosquitto
sudo systemctl status mosquitto --no-pager
```

### 6. Run SYSGrow

```bash
export SYSGROW_ENABLE_MQTT=true
export SYSGROW_HOST=0.0.0.0
export SYSGROW_PORT=8000
python smart_agriculture_app.py
```

### 7. Open in browser

- UI: `http://<your-pi-ip>:8000`
- API docs: `http://<your-pi-ip>:8000/api/v1/docs`

## ✅ First-Boot Checklist

1. `database/sysgrow.db` exists.
2. `mosquitto` is active.
3. `curl http://localhost:8000/api/v1/health/ping` returns 200.
4. UI loads from another device on your LAN.

## 🛠️ Production Deployment

For `systemd` boot-time startup and production setup:

- [`docs/setup/INSTALLATION_GUIDE.md`](docs/setup/INSTALLATION_GUIDE.md)

## 📚 Documentation

Start here:

- [`docs/setup/QUICK_START.md`](docs/setup/QUICK_START.md)
- [`docs/setup/INSTALLATION_GUIDE.md`](docs/setup/INSTALLATION_GUIDE.md)
- [`docs/INDEX.md`](docs/INDEX.md)

Technical references:

- [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md)
- [`docs/api/API_UPDATES_SUMMARY.md`](docs/api/API_UPDATES_SUMMARY.md)
- [`docs/hardware/sensors.md`](docs/hardware/sensors.md)

## 🧪 Development Commands

```bash
# Development server (auto-reload)
python start_dev.py

# Production-like local run
python smart_agriculture_app.py

# Tests
pytest
```

## 📄 License

MIT — see [`LICENSE`](LICENSE).
