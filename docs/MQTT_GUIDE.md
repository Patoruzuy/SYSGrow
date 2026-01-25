
It refers to:

* The official **CP210x driver** from Silicon Labs and Sonoff notes for the dongle. ([silabs.com][1])
* The **Mosquitto** MQTT broker downloads and install guides for Windows and Raspberry Pi. ([Eclipse Mosquitto][2])
* The **Node.js LTS** download page and npm docs (needed for Zigbee2MQTT). ([Node.js][3])
* The official **Zigbee2MQTT installation / getting-started docs** and a Raspberry Pi tutorial. ([zigbee2mqtt.io][4])

---

````markdown
# Sonoff Zigbee 3.0 USB Dongle Plus – Beginner Setup Guide
_For Windows & Raspberry Pi • Zigbee2MQTT + MQTT + Grow Tent app_

---

## 1. What this does

- The **Sonoff Zigbee USB dongle** talks to your Zigbee sensors/lights.
- **Zigbee2MQTT** converts Zigbee messages into **MQTT topics**.
- An **MQTT broker** (Mosquitto) delivers those messages.
- The **Grow Tent application** connects to the same MQTT broker and reads those topics.

You will set up:

1. USB dongle driver  
2. MQTT broker (Mosquitto)  
3. Zigbee2MQTT  
4. Point the Grow Tent app to the MQTT broker  

---

## 2. What you need

- **Sonoff Zigbee 3.0 USB Dongle Plus** (ZBDongle-P or ZBDongle-E)
- A computer:
  - **Windows 10/11 PC** _or_
  - **Raspberry Pi** with Raspberry Pi OS
- **Internet access** (to download software)
- The **Grow Tent application** (already installed)

---

## 3. Windows Setup (short version)

### 3.1 Install the USB driver

1. Plug the **Sonoff dongle** into your Windows PC.
2. If Windows does **not** recognise it correctly:
   - Download the **CP210x USB to UART Bridge VCP driver** from Silicon Labs:  
     👉 https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers
   - Install the driver and unplug/re-plug the dongle.
3. Open **Device Manager → Ports (COM & LPT)** and note the COM port  
   (e.g. `COM3`, `COM5`). You’ll need this later.

> If your dongle is a newer **V2** and CP210x does not work, check Sonoff’s official guide for your exact model.

---

### 3.2 Install an MQTT broker (Mosquitto) on Windows

1. Go to the Mosquitto download page:  
   👉 https://mosquitto.org/download/
2. Download the **Windows installer** (`mosquitto-*-install-windows-x64.exe`).
3. Run the installer and accept the defaults.  
4. For a detailed step-by-step Windows walkthrough, you can also follow:  
   👉 https://www.steves-internet-guide.com/install-mosquitto-broker/

After installation, Mosquitto will usually listen on:

- **Host:** `localhost`  
- **Port:** `1883`

---

### 3.3 Install Node.js (needed for Zigbee2MQTT)

1. Go to the Node.js download page:  
   👉 https://nodejs.org/en/download
2. Download the **LTS** version (labelled “LTS”).
3. Run the installer and keep the default options.

If you want an extra explanation about installing Node.js and npm:  
👉 https://docs.npmjs.com/downloading-and-installing-node-js-and-npm/

---

### 3.4 Install Zigbee2MQTT on Windows

1. Open the Zigbee2MQTT **Getting Started** page:  
   👉 https://www.zigbee2mqtt.io/guide/getting-started/
2. Scroll to **Installation → Windows** or go directly here:  
   👉 https://www.zigbee2mqtt.io/guide/installation/  
3. Follow the Windows instructions (they will tell you to:
   - install **Git** (if needed)
   - download Zigbee2MQTT
   - install dependencies
   - start Zigbee2MQTT

When Zigbee2MQTT starts, it will show you an **onboarding / web interface** (by default on `http://localhost:8080`).



---

### 3.5 Configure Zigbee2MQTT (Windows)

You can use the Zigbee2MQTT web UI, but here is the idea in simple words:

1. **Serial / dongle settings**
   - In the config (or UI), set:
     - **Port**: your COM port (e.g. `COM5`)
     - **Adapter**:
       - `zstack` for most **ZBDongle-P** units
       - `ember` for most **ZBDongle-E (V2)** units

2. **MQTT settings**
   - Point Zigbee2MQTT to your Mosquitto broker:
     - **Server**: `mqtt://localhost:1883`
     - If you don’t use username/password in Mosquitto, you can leave them blank.
   - Set **base topic** to something like:
     - `zigbee2mqtt`

3. Restart Zigbee2MQTT and confirm it starts without errors.

If you want a more detailed Zigbee2MQTT Windows configuration guide, check:  
👉 https://www.zigbee2mqtt.io/guide/configuration/

Note: If you have not used the Sonoff dongle before, you may need to update its firmware. Check the Zigbee2MQTT docs for **flashing firmware** instructions, check:
👉 https://dongle.sonoff.tech/sonoff-dongle-flasher
---

## 4. Raspberry Pi Setup (short version)

### 4.1 Plug in the dongle

1. Plug the Sonoff dongle into a USB port on your Raspberry Pi.
2. Optional but recommended: use a **short USB extension cable** so the dongle is away from the Pi and Wi-Fi antennas (less interference).

To see the device name, run in a terminal:

```bash
dmesg | tail -n 20
````

Look for something like `ttyACM0` or `ttyUSB0`.
Typical device path: `/dev/ttyACM0` or `/dev/ttyUSB0`.

---

### 4.2 Install Mosquitto (MQTT broker) on Raspberry Pi

In a terminal:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto
```

A nice beginner step-by-step guide with screenshots:
👉 [https://randomnerdtutorials.com/how-to-install-mosquitto-broker-on-raspberry-pi/](https://randomnerdtutorials.com/how-to-install-mosquitto-broker-on-raspberry-pi/)

Or another guide here:
👉 [https://cedalo.com/blog/mqtt-broker-raspberry-pi-installation-guide/](https://cedalo.com/blog/mqtt-broker-raspberry-pi-installation-guide/)

Mosquitto will listen on:

* **Host:** the Pi’s IP address (e.g. `192.168.1.50`)
* **Port:** `1883`

---

### 4.3 Install Node.js & Zigbee2MQTT on Raspberry Pi

The **official Zigbee2MQTT docs** explain installation on Linux (including Raspberry Pi):
👉 [https://www.zigbee2mqtt.io/guide/installation/](https://www.zigbee2mqtt.io/guide/installation/)

You can also follow a Pi-specific tutorial like this:
👉 [https://pimylifeup.com/raspberry-pi-zigbee2mqtt/](https://pimylifeup.com/raspberry-pi-zigbee2mqtt/)

In short, the steps are:

1. Install a compatible **Node.js LTS** version.
2. Download Zigbee2MQTT (usually into `/opt/zigbee2mqtt`).
3. Install its dependencies.
4. Start it with `npm start` or `yarn start`.

---

### 4.4 Configure Zigbee2MQTT (Raspberry Pi)

In the Zigbee2MQTT config file (often `/opt/zigbee2mqtt/data/configuration.yaml`) or via the web UI, set:

1. **Serial / dongle**

```yaml
serial:
  port: /dev/ttyACM0  # or /dev/ttyUSB0, depending on what you saw in dmesg

  # Choose **one** adapter line:
  # adapter: zstack   # for most ZBDongle-P
  # adapter: ember    # for most ZBDongle-E (V2)
```

2. **MQTT**

```yaml
mqtt:
  server: mqtt://localhost:1883
  base_topic: zigbee2mqtt
```

3. Restart Zigbee2MQTT and open its web UI in a browser:

   * `http://<raspberry-pi-ip>:8080`

---

## 5. Pair your Zigbee devices

1. Open the Zigbee2MQTT **web UI**.
2. Click **“Permit join (All)”**.
3. Put your Zigbee sensor/light in **pairing mode** (check its manual).
4. After a few seconds, it should appear in the Zigbee2MQTT device list.
5. The device will also start sending MQTT messages like:

* `zigbee2mqtt/<device_name>/state`
* `zigbee2mqtt/<device_name>/...`

---

## 6. Connect the Grow Tent application

In your Grow Tent app **MQTT settings**, use:

* **MQTT host**

  * On Windows (all on same PC): `localhost`
  * On Raspberry Pi (app on another machine): the Pi’s IP, e.g. `192.168.1.50`
* **MQTT port**: `1883`
* **Username / password**:

  * Leave empty if your Mosquitto broker doesn’t use authentication.
* **Topic / subscription**:

  * Start with `zigbee2mqtt/#` so the app sees all Zigbee2MQTT devices.

Once saved, the app should begin receiving Zigbee device data via MQTT.

---

## 7. Quick troubleshooting (very short)

* **Zigbee2MQTT says “no adapter found”**

  * Check the serial **port name** (`COMx` on Windows, `/dev/ttyACM0` on Pi).
  * Try switching `adapter: zstack` ↔ `adapter: ember` based on your dongle.

* **No data in the app**

  * Verify Zigbee2MQTT is running and you can see devices in its web UI.
  * Check the app’s MQTT settings match the broker (host, port, username/password).
  * Confirm you subscribe to the right topic, e.g. `zigbee2mqtt/#`.

If you can see devices in Zigbee2MQTT and your app is connected to the same MQTT broker, your Grow Tent application should start receiving data from the Sonoff Zigbee dongle.

```
::contentReference[oaicite:4]{index=4}
```

[1]: https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers?utm_source=chatgpt.com "CP210x USB to UART Bridge VCP Drivers"
[2]: https://mosquitto.org/download/?utm_source=chatgpt.com "Download"
[3]: https://nodejs.org/en/download?utm_source=chatgpt.com "Download Node.js"
[4]: https://www.zigbee2mqtt.io/guide/getting-started/?utm_source=chatgpt.com "Getting started"
