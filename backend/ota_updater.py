import requests
import time
import json
import paho.mqtt.client as mqtt
import logging
from utils.event_bus import EventBus

logging.basicConfig(level=logging.INFO, filename="devices_system.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

# ESP32 OTA Configuration
ESP32_IP = "http://esp32-c6.local"
FIRMWARE_URL = "http://ota-server.local:5000/firmware.bin"
VERSION_URL = "http://ota-server.local:5000/version"
CHECK_VERSION_URL = f"{ESP32_IP}/firmware_version"
OTA_TRIGGER_URL = f"{ESP32_IP}/ota_update"

def get_latest_version():
    """Fetch latest firmware version from OTA server."""
    try:
        response = requests.get(VERSION_URL, timeout=5)
        response.raise_for_status()
        return response.json().get("version", "0.0.0")
    except requests.RequestException as e:
        print(f"❌ Failed to fetch latest version: {e}")
        return None

def get_esp32_version():
    """Fetch the current firmware version running on ESP32."""
    try:
        response = requests.get(CHECK_VERSION_URL, timeout=5)
        response.raise_for_status()
        return response.json().get("version", "0.0.0")
    except requests.RequestException as e:
        print(f"❌ Failed to fetch ESP32 version: {e}")
        return None

def trigger_ota_update():
    """Trigger OTA update on ESP32."""
    try:
        response = requests.post(OTA_TRIGGER_URL, json={"url": FIRMWARE_URL}, timeout=5)
        response.raise_for_status()
        print("✅ OTA update started successfully.")
    except requests.RequestException as e:
        print(f"❌ Failed to trigger OTA update: {e}")

def main():
    print("🔄 Checking for firmware updates...")
    latest_version = get_latest_version()
    esp32_version = get_esp32_version()

    if not latest_version or not esp32_version:
        print("⚠️ Could not determine version numbers. Exiting.")
        return

    print(f"📌 Latest version: {latest_version}, ESP32 Version: {esp32_version}")

    if latest_version == esp32_version:
        print("✅ ESP32 is already up to date. No update needed.")
    else:
        print("🚀 Updating ESP32 firmware...")
        trigger_ota_update()
        time.sleep(10)  # Wait for update to complete
        new_version = get_esp32_version()
        if new_version == latest_version:
            print("🎉 Update successful!")
        else:
            print("❌ Update failed. Please check logs.")

if __name__ == "__main__":
    main()

def main():
    print("🔄 Checking for firmware updates...")
    latest_version = get_latest_version()
    esp32_version = get_esp32_version()

    if not latest_version or not esp32_version:
        print("⚠️ Could not determine version numbers. Exiting.")
        return

    print(f"📌 Latest version: {latest_version}, ESP32 Version: {esp32_version}")

    if latest_version == esp32_version:
        print("✅ ESP32 is already up to date. No update needed.")
    else:
        print("🚀 Updating ESP32 firmware...")
        trigger_ota_update()
        time.sleep(10)  # Wait for update to complete
        new_version = get_esp32_version()
        if new_version == latest_version:
            print("🎉 Update successful!")
        else:
            print("❌ Update failed. Please check logs.")

if __name__ == "__main__":
    main()
