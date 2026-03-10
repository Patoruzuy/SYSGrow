# SYSGrow Deployment Guide

Three deployment options: **Raspberry Pi native** (recommended for edge installs), **Docker**, or **generic Linux**.

---

## 1. Docker

The fastest way to get SYSGrow running anywhere.

### Prerequisites
- Docker Engine 24+ and Docker Compose v2

### Quick Start

```bash
# Clone and enter the repo
cd sysgrow/backend

# Create your environment config
cp ops.env.example ops.env
nano ops.env                     # edit as needed

# Build and start
docker compose up -d

# Check status
docker compose ps
docker compose logs -f sysgrow
```

The app is available at **http://localhost:8000**.

### Build with Zigbee Support

```bash
docker compose build --build-arg INSTALL_ZIGBEE=true
docker compose up -d
```

### Volumes

| Host Path       | Container Path     | Purpose                      |
|-----------------|--------------------|------------------------------|
| `./database/`   | `/app/database`    | SQLite database files        |
| `./data/`       | `/app/data`        | Training data, user profiles |
| `./logs/`       | `/app/logs`        | Application logs             |

### MQTT Broker

The compose file includes an Eclipse Mosquitto sidecar. The SYSGrow
container connects to it automatically via `SYSGROW_MQTT_HOST=mosquitto`.

To use an **external MQTT broker** instead, remove the `mosquitto` service
from `docker-compose.yml` and set `SYSGROW_MQTT_HOST` in `ops.env`.

---

## 2. Raspberry Pi Native Install (Recommended for Pi)

Best for dedicated grow-tent controllers running Raspberry Pi OS.

### Prerequisites
- Raspberry Pi 3B+ or newer (Pi 4/5 recommended)
- Raspberry Pi OS (64-bit recommended)
- Python 3.11+

### Automated Install

```bash
# Clone the repo
git clone https://github.com/Patoruzuy/SYSGrow.git /tmp/sysgrow-src
cd /tmp/sysgrow-src/backend

# Run the installer (installs to /opt/sysgrow)
chmod +x scripts/install_linux.sh
sudo ./scripts/install_linux.sh
```

The installer will:
1. Create a `sysgrow` system user
2. Copy the project to `/opt/sysgrow`
3. Create a Python venv and install all dependencies (including GPIO + Zigbee)
4. Install and start Mosquitto for local-network MQTT traffic
5. Initialize the SQLite database
6. Generate `/opt/sysgrow/ops.env` with production-ready defaults
7. Install, enable, and start the systemd service for boot-time startup

### Post-Install

```bash
# Review your configuration
sudo nano /opt/sysgrow/ops.env

# Check it's running
sudo systemctl status sysgrow
journalctl -u sysgrow -f
sudo systemctl status mosquitto
journalctl -u mosquitto -f

# Confirm boot startup
sudo systemctl is-enabled sysgrow
sudo systemctl is-enabled mosquitto

# Open in browser
# http://<pi-ip-address>:8000
#
# MQTT for ESP32 / Zigbee bridge devices:
# <pi-ip-address>:1883
```

Before calling the install production-ready, run the
**[Pre-Production Checklist](../docs/setup/PRE_PRODUCTION_CHECKLIST.md)**.

### Managing the Service

```bash
sudo systemctl start sysgrow      # Start app
sudo systemctl stop sysgrow       # Stop app
sudo systemctl restart sysgrow    # Restart app
sudo systemctl status sysgrow     # App status
sudo systemctl disable sysgrow    # Disable boot-time start
sudo systemctl enable sysgrow     # Re-enable boot-time start

sudo systemctl start mosquitto    # Start broker
sudo systemctl stop mosquitto     # Stop broker
sudo systemctl restart mosquitto  # Restart broker
sudo systemctl status mosquitto   # Broker status
```

### MQTT Broker (Mosquitto)

The installer now installs Mosquitto and writes:

```text
/etc/mosquitto/conf.d/sysgrow.conf
```

That config opens port `1883` on the local network and allows anonymous
connections so ESP32 devices can connect immediately.

The backend itself still talks to the broker through:

```env
SYSGROW_MQTT_HOST=localhost
SYSGROW_MQTT_PORT=1883
```

If you want to use an external MQTT broker instead:

1. Edit `/opt/sysgrow/ops.env`
2. Change `SYSGROW_MQTT_HOST` and `SYSGROW_MQTT_PORT`
3. Restart `sysgrow`

If you do not want the Pi to host MQTT at all, you can stop and disable Mosquitto:

```bash
sudo systemctl disable --now mosquitto
```

Do not expose the generated anonymous broker directly to the internet without
adding authentication and TLS.

---

## 3. Generic Linux Server

Same as Raspberry Pi but without GPIO/hardware extras.

```bash
sudo ./scripts/install_linux.sh
```

The installer auto-detects whether it's running on a Pi and adjusts
the installed extras accordingly.

---

## Environment Variable Reference

All configuration is via environment variables. Set them in `ops.env`
(native) or pass via `docker compose` environment/env_file.

### Core

| Variable                   | Default           | Description                              |
|----------------------------|-------------------|------------------------------------------|
| `SYSGROW_ENV`              | `development`     | `development` or `production`            |
| `SYSGROW_SECRET_KEY`       | (dev key)         | Flask secret key — **change in prod!**   |
| `SYSGROW_HOST`             | `0.0.0.0`         | Bind address                             |
| `SYSGROW_PORT`             | `8000`            | HTTP port                                |
| `SYSGROW_DEBUG`            | `False`           | Enable debug mode                        |
| `SYSGROW_LOG_LEVEL`        | (auto)            | `DEBUG`, `INFO`, `WARNING`, `ERROR`      |

### Database

| Variable                     | Default                    | Description                    |
|------------------------------|----------------------------|--------------------------------|
| `SYSGROW_DATABASE_PATH`      | `database/sysgrow.db`      | SQLite file path               |
| `SYSGROW_DB_CACHE_SIZE_KB`   | `8000`                     | SQLite PRAGMA cache_size (KB)  |
| `SYSGROW_DB_MMAP_SIZE_BYTES` | `33554432`                 | SQLite PRAGMA mmap_size (32MB) |

### MQTT

| Variable                 | Default     | Description                |
|--------------------------|-------------|----------------------------|
| `SYSGROW_ENABLE_MQTT`    | `True`      | Enable MQTT client         |
| `SYSGROW_MQTT_HOST`      | `localhost` | MQTT broker hostname       |
| `SYSGROW_MQTT_PORT`      | `1883`      | MQTT broker port           |

### Caching

| Variable               | Default | Description                   |
|------------------------|---------|-------------------------------|
| `SYSGROW_CACHE_ENABLED`| `True`  | Enable in-memory TTL cache    |
| `SYSGROW_CACHE_TTL`    | `30`    | Cache TTL in seconds          |

### Real-time

| Variable                  | Default | Description                  |
|---------------------------|---------|------------------------------|
| `SYSGROW_SOCKETIO_CORS`   | `*`     | Socket.IO CORS origins       |

### AI / LLM (Optional)

| Variable              | Default | Description                            |
|-----------------------|---------|----------------------------------------|
| `LLM_PROVIDER`        | `none`  | `none`, `openai`, `anthropic`, `local` |
| `LLM_API_KEY`         | —       | API key for cloud LLM provider         |
| `LLM_MODEL`           | —       | Model name (e.g. `gpt-4o-mini`)        |

### Security

| Variable                   | Default | Description                          |
|----------------------------|---------|--------------------------------------|
| `SYSGROW_AES_KEY`          | —       | 256-bit hex key for ESP32 encryption |
| `SYSGROW_MAX_UPLOAD_MB`    | `16`    | Max file upload size                 |
