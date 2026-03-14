Flashing Guide for ESP32-C6 Modules

This guide provides step-by-step instructions for flashing the correct firmware on each ESP32-C6 module in your project.

ESP32-C6 Modules & Firmware Files

ESP32-C6 Module

Purpose

Firmware to Flash

ESP32-C6-Relays

Controls relays via Zigbee, Wi-Fi, BLE

firmware_relay.bin

ESP32-C6-Sensors

Reads environmental sensors (ENS160, AHT21, MQ2, ZE07-CO)

firmware_sensors.bin

ESP32-C6-SoilLux

Monitors soil moisture sensors & LUX sensor

firmware_soillux.bin

Each ESP32-C6 has its own dedicated firmware.
Flashing the correct firmware ensures proper functionality.

Prerequisites

Before flashing, make sure you have:

PlatformIO installed (Installation Guide)

ESP32-C6 connected to your PC via USB

Correct firmware file for your module

Python 3 installed (for auto-flash script)

Flashing Instructions

Manual Flashing via PlatformIO CLI

Open a terminal and navigate to the firmware directory.

Run the following command based on the ESP32-C6 module:

# Flash ESP32-C6-Relays
cd ESP32-C6-Relays
pio run --target upload

# Flash ESP32-C6-Sensors
cd ../ESP32-C6-Sensors
pio run --target upload

# Flash ESP32-C6-SoilLux
cd ../ESP32-C6-SoilLux
pio run --target upload

This ensures that each ESP32-C6 module has the correct firmware!

Automatic Flashing Script

You can use the provided auto-flash script to detect and flash the correct ESP32-C6 module automatically.

auto_flash.py (Example Auto-Flashing Script)

import os
import serial.tools.list_ports

# Define firmware files for each module
firmware_files = {
    "ESP32-C6-Relays": "firmware_relay.bin",
    "ESP32-C6-Sensors": "firmware_sensors.bin",
    "ESP32-C6-SoilLux": "firmware_soillux.bin",
}

# Detect connected ESP32-C6 devices
ports = [p.device for p in serial.tools.list_ports.comports() if "USB" in p.description]
if not ports:
    print("No ESP32-C6 device detected!")
    exit()

# Ask user which module to flash
print("Detected ESP32-C6 on:", ports[0])
print("Select ESP32-C6 Module to Flash:")
for idx, module in enumerate(firmware_files.keys()):
    print(f"{idx+1}. {module}")
choice = int(input("Enter choice (1-3): ")) - 1

module_name = list(firmware_files.keys())[choice]
firmware_file = firmware_files[module_name]

# Flash the selected module
os.system(f"esptool.py --chip esp32c6 --port {ports[0]} write_flash 0x10000 {firmware_file}")
print(f"Successfully flashed {module_name} with {firmware_file}!")

This script automatically detects the ESP32-C6 and flashes the correct firmware.

Additional Notes

If you experience issues, try resetting the ESP32-C6 before flashing.

For OTA updates, use the OTA update feature in Home Assistant or MQTT.

Check logs with:

pio device monitor --baud 115200

To erase flash memory (if needed):

esptool.py --chip esp32c6 erase_flash


