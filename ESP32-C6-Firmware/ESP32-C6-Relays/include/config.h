#ifndef CONFIG_H
#define CONFIG_H

#include <WiFi.h>
#include <WiFiUdp.h>
#include <NTPClient.h>
#include <PubSubClient.h>
#include <EEPROM.h>
#include <ArduinoJson.h>
#include <ESPmDNS.h>
#include <HTTPClient.h>
#include <Update.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define FW_VERSION "1.0.0"
#define EEPROM_SIZE 128
#define AP_SSID "ESP32-Setup"
#define AP_PASSWORD "12345678"
#define BATTERY_PIN 6
#define DEFAULT_SLEEP_DURATION 300e6  // 5 minutes deep sleep

// Relay GPIOs
const int relayPins[] = {2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21};

// BLE Configuration
#define BLE_SERVICE_UUID        "12345678-1234-5678-1234-56789abcdef0"
#define BLE_CHARACTERISTIC_UUID "12345678-1234-5678-1234-56789abcdef1"

// User-selected communication method
enum ConnectionMode { ZIGBEE, WIFI, BLE };
extern ConnectionMode selectedMode;

// Wi-Fi & MQTT
extern WiFiClient espClient;
extern PubSubClient client;
extern WiFiUDP ntpUDP;
extern NTPClient timeClient;
extern String mqtt_broker, ota_url;
extern const int mqtt_port;
extern const char* device_id;
extern bool isBLEActive;

// Function Prototypes
void loadConnectionMode();
void saveConnectionMode(ConnectionMode mode);
void loadWiFiConfig();
void saveWiFiConfig(const char* ssid, const char* password);

#endif
