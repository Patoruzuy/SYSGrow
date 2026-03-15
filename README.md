# SYSGrow

Raspberry Pi-first smart agriculture platform for monitoring sensors, controlling actuators, and running automation from a local Flask app.

Author: Patoruzuy

## What This Repository Contains

This repository is the deployable SYSGrow backend application:

- Flask web UI + API (`/api/v1/*`)
- SQLite data layer (WAL mode)
- MQTT integration for ESP32 and other IoT devices
- Real-time updates via Socket.IO
- Optional ML/AI modules

## Quick Start (Raspberry Pi Recommended)

These steps are the fastest path to a first working install on Raspberry Pi OS.

### 1. Install system packages

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-dev \
  build-essential pkg-config libsystemd-dev sqlite3 mosquitto mosquitto-clients
```

### 2. Clone and enter backend

```bash
git clone https://github.com/Patoruzuy/SYSGrow.git
cd SYSGrow
```

### 3. Create virtual environment and install dependencies

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

### 5. Ensure MQTT broker is running

```bash
sudo systemctl enable --now mosquitto
sudo systemctl status mosquitto --no-pager
```

### 6. Start SYSGrow

```bash
export SYSGROW_ENABLE_MQTT=true
export SYSGROW_HOST=0.0.0.0
export SYSGROW_PORT=8000
python smart_agriculture_app.py
```

### 7. Open the app

- UI: `http://<your-pi-ip>:8000`
- API docs: `http://<your-pi-ip>:8000/api/v1/docs`

## First-Boot Validation Checklist

After startup, confirm:

1. `database/sysgrow.db` exists.
2. `mosquitto` is active (`systemctl status mosquitto`).
3. `/api/v1/health/ping` returns HTTP 200.
4. UI opens from another device on your LAN.

## Production Setup (systemd + auto-start)

Use the full deployment guide:

- [`docs/setup/INSTALLATION_GUIDE.md`](docs/setup/INSTALLATION_GUIDE.md)

That guide includes:

- service user creation
- `systemd` service setup
- boot-time startup
- environment file configuration
- logs and troubleshooting

## Documentation Map

Start here:

- Quick start: [`docs/setup/QUICK_START.md`](docs/setup/QUICK_START.md)
- Full install guide: [`docs/setup/INSTALLATION_GUIDE.md`](docs/setup/INSTALLATION_GUIDE.md)
- Documentation index: [`docs/INDEX.md`](docs/INDEX.md)

Reference docs:

- Architecture: [`docs/architecture/ARCHITECTURE.md`](docs/architecture/ARCHITECTURE.md)
- API docs summary: [`docs/api/API_UPDATES_SUMMARY.md`](docs/api/API_UPDATES_SUMMARY.md)
- Hardware docs: [`docs/hardware/sensors.md`](docs/hardware/sensors.md)

## Development Commands

```bash
# dev server (auto reload)
python start_dev.py

# production-like local run
python smart_agriculture_app.py

# test suite
pytest
```

## License

MIT. See [`LICENSE`](LICENSE).
