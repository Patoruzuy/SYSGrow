# SYSGrow Raspberry Pi Quick Start

Use this path if you want SYSGrow running on a Raspberry Pi with:

- the web app starting automatically at boot
- a local Mosquitto broker for ESP32 and Zigbee integrations
- a production-ready `ops.env` generated for you

## 1. Prepare the Pi

- Install Raspberry Pi OS Bookworm or newer.
- Connect the Pi to your local network.
- Log in as a sudo-capable user.

Optional but recommended:

```bash
sudo apt update && sudo apt upgrade -y
sudo reboot
```

## 2. Clone the Project

```bash
git clone https://github.com/Patoruzuy/SYSGrow.git
cd SYSGrow/backend
```

## 3. Run the Installer

```bash
chmod +x scripts/install_linux.sh
sudo ./scripts/install_linux.sh
```

The installer will:

1. Copy the backend to `/opt/sysgrow`
2. Create a Python virtual environment
3. Install Python and system packages needed on Raspberry Pi
4. Install and start Mosquitto on port `1883`
5. Generate `/opt/sysgrow/ops.env` with a random `SYSGROW_SECRET_KEY`
6. Install `sysgrow.service`
7. Enable and start SYSGrow immediately

## 4. Verify the Install

Check that both services are active:

```bash
sudo systemctl status sysgrow
sudo systemctl status mosquitto
```

Check that SYSGrow is enabled for boot:

```bash
sudo systemctl is-enabled sysgrow
sudo systemctl is-enabled mosquitto
```

Expected result for both:

```text
enabled
```

## 5. Open the App

Find the Pi IP address:

```bash
hostname -I
```

Open this in a browser on the same network:

```text
http://<pi-ip>:8000
```

If the system asks you to register first, create the first account there.

## 6. Point Devices at MQTT

Use the Raspberry Pi IP address as the MQTT broker for ESP32 or Zigbee bridge devices:

```text
Host: <pi-ip>
Port: 1883
```

SYSGrow itself talks to the local broker through `localhost:1883`.

## 7. Important Files

- App install: `/opt/sysgrow`
- Runtime config: `/opt/sysgrow/ops.env`
- Systemd unit: `/etc/systemd/system/sysgrow.service`
- Mosquitto config added by installer: `/etc/mosquitto/conf.d/sysgrow.conf`

## 8. Useful Commands

```bash
sudo systemctl restart sysgrow
sudo systemctl restart mosquitto
journalctl -u sysgrow -f
journalctl -u mosquitto -f
sudo nano /opt/sysgrow/ops.env
```

## 9. Troubleshooting

If the web UI does not load:

```bash
sudo systemctl status sysgrow --no-pager
journalctl -u sysgrow -n 100 --no-pager
```

If MQTT devices cannot connect:

```bash
sudo systemctl status mosquitto --no-pager
journalctl -u mosquitto -n 100 --no-pager
ss -ltn | grep 1883
```

If you use GPIO, I2C, SPI, or a Zigbee USB coordinator, the installer adds the
`sysgrow` service user to the common Raspberry Pi hardware groups. Reboot once
after installation if Linux has not applied those group memberships yet.

## Next

For the full Raspberry Pi setup, environment variables, update workflow, and
manual install steps, continue with [INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md).
