# SYSGrow Pre-Production Checklist

Use this as the final ship gate before deploying SYSGrow to real users.

This checklist is split into:

- repo-side checks you can run from the codebase
- Raspberry Pi validation that must be proven on real hardware

## 1. Run the Repo Preflight

From `backend/`:

```bash
python scripts/pre_production_check.py
```

If you already have the project virtual environment, prefer:

```bash
.venv/bin/python scripts/pre_production_check.py
```

On Windows:

```powershell
.venv\Scripts\python.exe scripts\pre_production_check.py
```

The script checks:

- deployment/service file expectations
- installer shell syntax
- Ruff lint and format checks
- Bandit security scan
- targeted pytest release gate
- authenticated route smoke for the main UI pages

## 2. Raspberry Pi Release Validation

These items are mandatory before a real production launch.

### Clean Install

- Flash a fresh Raspberry Pi OS image
- Clone the repo and run:

```bash
cd SYSGrow/backend
sudo ./scripts/install_linux.sh
```

- Confirm both services are active:

```bash
sudo systemctl status sysgrow --no-pager
sudo systemctl status mosquitto --no-pager
```

### Boot and Recovery

- Reboot the Pi once
- Confirm both services auto-start:

```bash
sudo systemctl is-enabled sysgrow
sudo systemctl is-enabled mosquitto
sudo systemctl is-active sysgrow
sudo systemctl is-active mosquitto
```

- Verify the UI still loads after reboot at `http://<pi-ip>:8000`

### MQTT / Device Integration

- Connect at least one real ESP32 sensor device
- Connect the Zigbee bridge if Zigbee is part of the release
- Confirm devices can publish to `mqtt://<pi-ip>:1883`
- Confirm readings appear in the UI and on the dashboard

### Failure Modes

- Stop Mosquitto and confirm the app degrades cleanly
- Restart Mosquitto and confirm recovery without reinstall
- Disconnect one device and confirm alerts/status update correctly
- Simulate power loss or hard reboot and verify recovery

### Database Safety

- Create a backup
- Restore that backup to a test copy
- Start the app against the restored database
- Confirm dashboards, plants, and notifications still load

### Soak Test

- Leave the Pi running for 12 to 24 hours
- Watch:
  - memory growth
  - CPU load
  - database size
  - MQTT reconnect stability
  - scheduled task execution

### Browser QA

- Pi Chromium
- Android Chrome
- iPhone Safari if mobile users are expected

Check:

- login
- dashboard
- units
- devices
- device health
- plants
- sensor analytics
- notifications
- settings

## 3. Release Sign-Off

Do not ship until all of these are true:

- repo preflight passes
- clean Pi install is proven
- reboot startup is proven
- MQTT devices work on the LAN
- backup and restore are proven
- soak test is clean
- browser QA is complete
- production secrets and `ops.env` are reviewed

## 4. Record the Release Candidate

For each release candidate, record:

- git commit SHA
- Pi model and Raspberry Pi OS version
- install date
- tester
- whether Mosquitto was local or external
- devices used in validation
- pass/fail notes for each section above
