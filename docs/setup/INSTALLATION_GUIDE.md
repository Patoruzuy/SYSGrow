# SYSGrow Installation Guide

This guide covers the supported ways to run the SYSGrow backend, with the
Raspberry Pi path first.

## Recommended Path: Raspberry Pi Native Install

This is the best fit for a dedicated grow controller.

### Supported Target

- Raspberry Pi 3B+ or newer
- Raspberry Pi OS Bookworm or newer
- Local network access

### What the Installer Configures

Running `scripts/install_linux.sh` on a Raspberry Pi now does all of this:

1. Installs Python, build tools, `rsync`, Mosquitto, and Mosquitto clients
2. Creates the `sysgrow` system user
3. Adds `sysgrow` to common hardware groups:
   `gpio`, `i2c`, `spi`, and `dialout` when present
4. Enables I2C and SPI through `raspi-config` when available
5. Copies the backend to `/opt/sysgrow`
6. Creates `/opt/sysgrow/.venv`
7. Installs the backend dependencies and Raspberry Pi extras
8. Creates `/opt/sysgrow/ops.env` if missing
9. Generates a random `SYSGROW_SECRET_KEY`
10. Sets production defaults for the Pi install
11. Configures Mosquitto to listen on port `1883`
12. Installs `sysgrow.service`
13. Enables and starts both `mosquitto` and `sysgrow`

### Install Commands

```bash
git clone https://github.com/Patoruzuy/SYSGrow.git
cd SYSGrow/backend
chmod +x scripts/install_linux.sh
sudo ./scripts/install_linux.sh
```

### After Installation

Check that the services are running:

```bash
sudo systemctl status sysgrow
sudo systemctl status mosquitto
```

Check that they will start at boot:

```bash
sudo systemctl is-enabled sysgrow
sudo systemctl is-enabled mosquitto
```

Open the UI:

```text
http://<pi-ip>:8000
```

Point ESP32 devices or Zigbee bridges at:

```text
mqtt://<pi-ip>:1883
```

### Files Installed on the Pi

- App code: `/opt/sysgrow`
- Runtime config: `/opt/sysgrow/ops.env`
- SQLite database: `/opt/sysgrow/database/sysgrow.db`
- App logs: `/opt/sysgrow/logs/`
- Systemd unit: `/etc/systemd/system/sysgrow.service`
- Mosquitto config: `/etc/mosquitto/conf.d/sysgrow.conf`

## Production Configuration

The installer generates a usable `ops.env`, but you should still review it:

```bash
sudo nano /opt/sysgrow/ops.env
```

Important keys:

```env
SYSGROW_ENV=production
SYSGROW_SECRET_KEY=<generated-by-installer>
SYSGROW_DATABASE_PATH=database/sysgrow.db
SYSGROW_DEBUG=False
SYSGROW_LOG_LEVEL=WARNING
SYSGROW_ENABLE_MQTT=True
SYSGROW_MQTT_HOST=localhost
SYSGROW_MQTT_PORT=1883
```

Notes:

- `SYSGROW_MQTT_HOST=localhost` is correct for the backend because Mosquitto
  runs on the same Pi.
- External devices must use the Raspberry Pi IP, not `localhost`.
- If you want to use an external MQTT broker, change `SYSGROW_MQTT_HOST` and
  restart both the app and the devices that publish/subscribe to that broker.

## Service Management

```bash
sudo systemctl restart sysgrow
sudo systemctl stop sysgrow
sudo systemctl start sysgrow
sudo systemctl status sysgrow
sudo systemctl disable sysgrow
sudo systemctl enable sysgrow
```

Logs:

```bash
journalctl -u sysgrow -f
journalctl -u mosquitto -f
```

## MQTT and Mosquitto Notes

The installer writes a Mosquitto config that opens port `1883` on the local
network and allows anonymous clients. That is the simplest path for ESP32 and
Zigbee integrations on a trusted LAN.

Do not expose that broker directly to the internet without adding:

- authentication
- TLS
- firewall rules

If your network is untrusted, replace the generated Mosquitto config with a
password-protected setup before onboarding devices.

## Updating an Existing Pi Install

From the source checkout:

```bash
cd SYSGrow/backend
git pull
sudo ./scripts/install_linux.sh
```

The installer preserves an existing `/opt/sysgrow/ops.env` and fills in missing
core keys if needed.

## Manual Linux Install

Use this only if you do not want the automated script.

### 1. Install Packages

```bash
sudo apt update
sudo apt install -y \
  python3 python3-dev python3-venv python3-pip \
  build-essential pkg-config libffi-dev libssl-dev libsystemd-dev \
  rsync mosquitto mosquitto-clients
```

### 2. Copy the App

```bash
sudo mkdir -p /opt/sysgrow
sudo rsync -a ./ /opt/sysgrow/
sudo useradd --system --home-dir /opt/sysgrow --shell /usr/sbin/nologin sysgrow || true
sudo chown -R sysgrow:sysgrow /opt/sysgrow
```

### 3. Create the Virtual Environment

```bash
cd /opt/sysgrow
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements-essential.txt
pip install '.[zigbee,raspberry,linux]'
```

### 4. Create `ops.env`

Use `/opt/sysgrow/ops.env.example` as the base.
At minimum set:

```env
SYSGROW_ENV=production
SYSGROW_SECRET_KEY=<your-random-secret>
SYSGROW_DATABASE_PATH=database/sysgrow.db
SYSGROW_ENABLE_MQTT=True
SYSGROW_MQTT_HOST=localhost
SYSGROW_MQTT_PORT=1883
```

Generate a secret key:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Initialize the Database

```bash
/opt/sysgrow/.venv/bin/python -c "from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler; SQLiteDatabaseHandler('/opt/sysgrow/database/sysgrow.db').initialize_database()"
```

### 6. Install the Services

```bash
sudo cp /opt/sysgrow/deployment/sysgrow.service /etc/systemd/system/sysgrow.service
sudo systemctl daemon-reload
sudo systemctl enable --now mosquitto
sudo systemctl enable --now sysgrow
```

## Development Install

For desktop development:

```bash
git clone https://github.com/Patoruzuy/SYSGrow.git
cd SYSGrow/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-essential.txt
python start_dev.py
```

Open:

```text
http://localhost:8000
```

## Troubleshooting

### `sysgrow` is enabled but not running

```bash
sudo systemctl status sysgrow --no-pager
journalctl -u sysgrow -n 100 --no-pager
```

### Mosquitto is running but devices cannot connect

Check that port `1883` is listening:

```bash
ss -ltn | grep 1883
```

Check the broker logs:

```bash
journalctl -u mosquitto -n 100 --no-pager
```

### GPIO or I2C devices are not detected

Check group membership and reboot once if you just installed:

```bash
id sysgrow
sudo reboot
```

### The app starts but MQTT features are disabled

Review:

```bash
grep '^SYSGROW_ENABLE_MQTT=' /opt/sysgrow/ops.env
grep '^SYSGROW_MQTT_HOST=' /opt/sysgrow/ops.env
grep '^SYSGROW_MQTT_PORT=' /opt/sysgrow/ops.env
```

Then restart:

```bash
sudo systemctl restart sysgrow
```
