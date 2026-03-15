# SYSGrow Quick Start (Raspberry Pi)

Use this guide for a first working installation on Raspberry Pi OS.

## Prerequisites

- Raspberry Pi 3B+/4/5 with Raspberry Pi OS
- Internet access
- A user with `sudo` permissions

## 1. Install System Dependencies

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-dev \
  build-essential pkg-config libsystemd-dev sqlite3 mosquitto mosquitto-clients
```

## 2. Clone Repository

```bash
git clone https://github.com/Patoruzuy/SYSGrow.git
cd SYSGrow
```

## 3. Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Initialize Database

```bash
python -c "from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler; SQLiteDatabaseHandler('database/sysgrow.db').initialize_database()"
```

## 5. Start MQTT Broker

```bash
sudo systemctl enable --now mosquitto
sudo systemctl status mosquitto --no-pager
```

## 6. Start the Application

```bash
export SYSGROW_ENABLE_MQTT=true
export SYSGROW_HOST=0.0.0.0
export SYSGROW_PORT=8000
python smart_agriculture_app.py
```

## 7. Verify

From the Pi:

```bash
curl -s http://localhost:8000/api/v1/health/ping
```

From another device on your network:

- UI: `http://<pi-ip>:8000`
- API docs: `http://<pi-ip>:8000/api/v1/docs`

## 8. Stop the App

Press `Ctrl+C` in the terminal where the app is running.

## Next Step

For boot-time startup and production deployment, continue with:

- [`INSTALLATION_GUIDE.md`](INSTALLATION_GUIDE.md)
