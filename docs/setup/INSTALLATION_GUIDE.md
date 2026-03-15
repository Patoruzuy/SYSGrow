# SYSGrow Installation Guide (Raspberry Pi Production)

This guide sets up SYSGrow on Raspberry Pi with:

- local SQLite database
- local Mosquitto MQTT broker
- `systemd` service (auto-start at boot)

If you only need a quick manual run, use [`QUICK_START.md`](QUICK_START.md).

## 0. Assumptions

- Raspberry Pi OS (Bookworm or Bullseye)
- You have `sudo` access
- You want SYSGrow installed at `/opt/sysgrow`

## 1. Install OS Packages

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip python3-dev \
  build-essential pkg-config libsystemd-dev sqlite3 mosquitto mosquitto-clients
```

## 2. Create Service User and Install Directory

```bash
sudo useradd --system --create-home --home-dir /opt/sysgrow --shell /usr/sbin/nologin sysgrow || true
```

## 3. Clone Repository

```bash
sudo git clone https://github.com/Patoruzuy/SYSGrow.git /opt/sysgrow
sudo chown -R sysgrow:sysgrow /opt/sysgrow
```

## 4. Create Virtual Environment and Install Python Dependencies

```bash
sudo -u sysgrow python3 -m venv /opt/sysgrow/.venv
sudo -u sysgrow /opt/sysgrow/.venv/bin/pip install --upgrade pip
sudo -u sysgrow /opt/sysgrow/.venv/bin/pip install -r /opt/sysgrow/requirements.txt
```

## 5. Configure Runtime Environment

Create ops env file from template:

```bash
sudo cp /opt/sysgrow/ops.env.example /opt/sysgrow/ops.env
sudo chown sysgrow:sysgrow /opt/sysgrow/ops.env
```

Append required core variables:

```bash
sudo tee -a /opt/sysgrow/ops.env > /dev/null <<'EOF'
SYSGROW_SECRET_KEY=replace-with-a-random-secret
SYSGROW_HOST=0.0.0.0
SYSGROW_PORT=8000
SYSGROW_DATABASE_PATH=database/sysgrow.db
SYSGROW_ENABLE_MQTT=true
SYSGROW_MQTT_HOST=localhost
SYSGROW_MQTT_PORT=1883
SYSGROW_LOG_LEVEL=WARNING
EOF
```

Generate a strong secret if needed:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## 6. Initialize Database

```bash
sudo -u sysgrow /opt/sysgrow/.venv/bin/python -c "from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler; SQLiteDatabaseHandler('database/sysgrow.db').initialize_database()"
```

## 7. Configure Mosquitto (MQTT)

Enable and start broker:

```bash
sudo systemctl enable --now mosquitto
sudo systemctl status mosquitto --no-pager
```

Basic LAN listener config:

```bash
sudo tee /etc/mosquitto/conf.d/sysgrow.conf > /dev/null <<'EOF'
listener 1883
allow_anonymous true
persistence true
persistence_location /var/lib/mosquitto/
EOF

sudo systemctl restart mosquitto
```

Security note: for internet-exposed deployments, disable anonymous access and configure username/password.

## 8. Install and Enable SYSGrow systemd Service

```bash
sudo cp /opt/sysgrow/deployment/sysgrow.service /etc/systemd/system/sysgrow.service
sudo systemctl daemon-reload
sudo systemctl enable --now sysgrow
```

Check service:

```bash
sudo systemctl status sysgrow --no-pager
journalctl -u sysgrow -f
```

## 9. Verify Endpoints

From the Pi:

```bash
curl -s http://localhost:8000/api/v1/health/ping
```

From another device:

- UI: `http://<pi-ip>:8000`
- API docs: `http://<pi-ip>:8000/api/v1/docs`

## 10. Update Procedure

```bash
sudo systemctl stop sysgrow
sudo -u sysgrow git -C /opt/sysgrow pull
sudo -u sysgrow /opt/sysgrow/.venv/bin/pip install -r /opt/sysgrow/requirements.txt
sudo systemctl start sysgrow
```

## 11. Troubleshooting

### App does not start

```bash
journalctl -u sysgrow -n 200 --no-pager
```

Common causes:

- missing Python dependencies
- bad `SYSGROW_SECRET_KEY`
- invalid `SYSGROW_DATABASE_PATH`

### MQTT connection errors

```bash
sudo systemctl status mosquitto --no-pager
mosquitto_sub -h localhost -t '#' -C 1 -W 2
```

If this fails, fix broker first before debugging SYSGrow.

### Port not reachable on LAN

Check service bind config in `/opt/sysgrow/ops.env`:

- `SYSGROW_HOST=0.0.0.0`
- `SYSGROW_PORT=8000`

Then restart:

```bash
sudo systemctl restart sysgrow
```

## 12. Optional: Run Without systemd (manual)

```bash
cd /opt/sysgrow
source .venv/bin/activate
export SYSGROW_ENABLE_MQTT=true
export SYSGROW_HOST=0.0.0.0
export SYSGROW_PORT=8000
python smart_agriculture_app.py
```
