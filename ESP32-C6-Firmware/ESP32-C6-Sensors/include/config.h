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
#include <WiFiClientSecure.h>

// ============================================================================
// Firmware Configuration
// ============================================================================
#define FW_VERSION "2.0.0"
#define FW_COMMIT "dev"
#define DEVICE_TYPE "ESP32-C6-Sensors"

// ============================================================================
// EEPROM Layout (512 bytes total)
// ============================================================================
// Offset   Size   Field
// 0        64     wifi_ssid
// 64       64     wifi_password
// 128      64     mqtt_broker
// 192      32     friendly_name
// 224      64     mqtt_username
// 288      64     mqtt_password
// 352      4      polling_interval_ms (uint32_t)
// 356      4      config_flags (calibration enabled, etc.)
// 360      36     calibration_data (temperature_offset, humidity_offset, etc.)
// 396      4      reserved_1
// 400      4      reserved_2
// 404      104    reserved_future
// 508      2      eeprom_version (uint16_t, for migration)
// 510      2      checksum (uint16_t, CRC16)
// ============================================================================

#define EEPROM_SIZE 512

// EEPROM Offsets
#define EEPROM_WIFI_SSID_OFFSET         0
#define EEPROM_WIFI_PASSWORD_OFFSET     64
#define EEPROM_MQTT_BROKER_OFFSET       128
#define EEPROM_FRIENDLY_NAME_OFFSET     192
#define EEPROM_MQTT_USERNAME_OFFSET     224
#define EEPROM_MQTT_PASSWORD_OFFSET     288
#define EEPROM_POLLING_INTERVAL_OFFSET  352
#define EEPROM_CONFIG_FLAGS_OFFSET      356
#define EEPROM_CALIBRATION_OFFSET       360
#define EEPROM_VERSION_OFFSET           508
#define EEPROM_CHECKSUM_OFFSET          510

// EEPROM Field Sizes
#define EEPROM_WIFI_SSID_SIZE           64
#define EEPROM_WIFI_PASSWORD_SIZE       64
#define EEPROM_MQTT_BROKER_SIZE         64
#define EEPROM_FRIENDLY_NAME_SIZE       32
#define EEPROM_MQTT_USERNAME_SIZE       64
#define EEPROM_MQTT_PASSWORD_SIZE       64
#define EEPROM_CALIBRATION_SIZE         36

// EEPROM Version for migrations
#define EEPROM_CURRENT_VERSION          2

// Config Flags Bitmask
#define CONFIG_FLAG_CALIBRATION_ENABLED (1 << 0)
#define CONFIG_FLAG_POWER_SAVE_ENABLED  (1 << 1)
#define CONFIG_FLAG_BLE_ALWAYS_ON       (1 << 2)
#define CONFIG_FLAG_DEBUG_MODE          (1 << 3)

// ============================================================================
// Watchdog Timer Configuration
// ============================================================================
#define WATCHDOG_TIMEOUT_MS     30000   // 30 seconds watchdog timeout
#define WATCHDOG_ENABLED        true    // Enable hardware watchdog

// ============================================================================
// Network Configuration
// ============================================================================
#define DEFAULT_WIFI_TIMEOUT    30000   // 30 seconds
#define WIFI_RETRY_INTERVAL     5000    // 5 seconds
#define MAX_WIFI_RETRIES        5
#define WIFI_BACKOFF_BASE_MS    1000    // 1 second base for exponential backoff
#define WIFI_BACKOFF_MAX_MS     60000   // Maximum 60 seconds between retries

// ============================================================================
// MQTT Configuration (Zigbee2MQTT-style)
// ============================================================================
#define MQTT_PORT               1883    // Non-secure MQTT port (use 8883 for TLS)
#define MQTT_SECURE_PORT        8883    // Secure MQTT port
#define MQTT_KEEPALIVE          60
#define MQTT_BUFFER_SIZE        1024
#define MQTT_RETRY_INTERVAL     5000
#define MAX_MQTT_RETRIES        3
#define MQTT_QOS                1       // QoS 1 for better performance

// MQTT Topic Prefixes (Zigbee2MQTT-style)
#define MQTT_TOPIC_PREFIX       "sysgrow"
#define MQTT_BRIDGE_PREFIX      "sysgrow/bridge"

// Default polling interval in milliseconds
#define DEFAULT_POLLING_INTERVAL_MS     30000   // 30 seconds

// ============================================================================
// BLE Configuration
// ============================================================================
#define BLE_SERVICE_UUID                "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define BLE_SENSOR_CHARACTERISTIC_UUID  "beb5483e-36e1-4688-b7f5-ea07361b26a8"
#define BLE_CONFIG_CHARACTERISTIC_UUID  "beb5483e-36e1-4688-b7f5-ea07361b26a9"
#define BLE_DEVICE_NAME_PREFIX          "SYSGrow-"

// BLE Pairing Button Configuration (GPIO9 = Boot button on ESP32-C6 dev boards)
#define BLE_BUTTON_PIN          9
#define SHORT_PRESS_MS          3000    // < 3 seconds = enable BLE pairing
#define LONG_PRESS_MS           5000    // > 5 seconds = factory reset
#define BLE_PAIRING_TIMEOUT_MS  30000   // 30 seconds BLE advertising window

// ============================================================================
// Sensor Pin Configuration
// ============================================================================
// ENS160 + AHT21 (I2C)
#define I2C_SDA_PIN             21
#define I2C_SCL_PIN             22

// MQ2 Gas Sensor (Analog)
#define MQ2_ANALOG_PIN          4       // ADC1_CH4

// TSL2591 Light Sensor (I2C) - shares I2C bus with ENS160+AHT21

// ============================================================================
// Sensor Configuration
// ============================================================================
#define SENSOR_READ_INTERVAL    30000   // 30 seconds (matches polling interval)

// ============================================================================
// Power Management
// ============================================================================
#define BATTERY_PIN             6       // ADC pin for battery voltage
#define LOW_BATTERY_THRESHOLD   3.3     // Volts
#define CRITICAL_BATTERY_THRESHOLD  3.0 // Volts - force deep sleep
#define DEEP_SLEEP_DURATION     300e6   // 5 minutes in microseconds

// ============================================================================
// OTA Configuration
// ============================================================================
#define OTA_CHECK_INTERVAL      3600000 // 1 hour

// ============================================================================
// mDNS Configuration
// ============================================================================
#define MDNS_SERVICE_NAME       "_sysgrow"
#define MDNS_SERVICE_PROTOCOL   "_tcp"
#define MDNS_SERVICE_PORT       80

// ============================================================================
// RTC Memory Sensor History Buffer
// ============================================================================
#define SENSOR_HISTORY_SIZE     10      // Number of readings to keep in RTC memory
#define RTC_VALID_MARKER        0xDEAD  // Marker to validate RTC data

// Sensor reading structure for history buffer
struct SensorHistoryEntry {
    uint32_t timestamp;         // Unix timestamp (seconds)
    float temperature;
    float humidity;
    uint16_t co2;
    uint8_t air_quality;
    float smoke;
    float lux;
    uint8_t battery_percent;
};

// RTC memory structure (survives deep sleep)
struct RTCData {
    uint16_t valid_marker;      // RTC_VALID_MARKER if data is valid
    uint8_t history_index;      // Current index in circular buffer
    uint8_t history_count;      // Number of valid entries
    uint8_t wifi_retry_count;   // Exponential backoff counter
    uint8_t reserved[3];        // Padding for alignment
    SensorHistoryEntry history[SENSOR_HISTORY_SIZE];
};

// ============================================================================
// LED Status Indicator
// ============================================================================
#define STATUS_LED_PIN          8       // Built-in LED on most ESP32-C6 boards
#define LED_BLINK_PAIRING       500     // Fast blink during BLE pairing
#define LED_BLINK_CONNECTING    1000    // Slow blink during WiFi/MQTT connect
#define LED_ON_CONNECTED        0       // Solid on when connected

// ============================================================================
// Communication Modes
// ============================================================================
enum ConnectionMode {
    WIFI_MQTT = 0,      // Normal operation via WiFi/MQTT
    BLE_ONLY = 1,       // BLE provisioning/pairing mode
    OFFLINE = 2,        // Low power, no communication
    BLE_PAIRING = 3     // Temporary BLE pairing mode (30s timeout)
};

// ============================================================================
// Calibration Data Structure
// ============================================================================
struct CalibrationData {
    float temperature_offset;       // Offset in Celsius
    float humidity_offset;          // Offset in percentage
    float mq2_calibration_factor;   // MQ2 calibration multiplier
    float lux_calibration_factor;   // TSL2591 calibration multiplier
    uint32_t reserved[4];           // Reserved for future sensors
};

// ============================================================================
// Global Variables (extern declarations)
// ============================================================================
extern String friendly_name;        // Device friendly name (e.g., sysgrow-AABBCCDD)
extern ConnectionMode current_mode;
extern bool is_provisioned;
extern bool ble_pairing_active;
extern unsigned long ble_pairing_start_time;
extern unsigned long last_sensor_read;
extern unsigned long last_mqtt_attempt;
extern unsigned long last_ota_check;
extern unsigned long button_press_start_time;
extern bool button_pressed;

// WiFi/MQTT credentials (loaded from EEPROM)
extern char stored_ssid[EEPROM_WIFI_SSID_SIZE];
extern char stored_password[EEPROM_WIFI_PASSWORD_SIZE];
extern char mqtt_broker[EEPROM_MQTT_BROKER_SIZE];
extern char mqtt_username[EEPROM_MQTT_USERNAME_SIZE];
extern char mqtt_password[EEPROM_MQTT_PASSWORD_SIZE];
extern char stored_friendly_name[EEPROM_FRIENDLY_NAME_SIZE];
extern uint32_t polling_interval_ms;
extern uint32_t config_flags;
extern CalibrationData calibration_data;

// ============================================================================
// Function Prototypes - Setup
// ============================================================================
void setupWiFi();
void setupMQTT();
void setupSensors();
void setupBLE();
void setupWebServer();
void setupOTA();
void setupButton();
void setupStatusLED();
void setupPowerManagement();

// ============================================================================
// Function Prototypes - Loop Functions
// ============================================================================
void mqttLoop();
void sensorLoop();
void powerManagementLoop();
void bleLoop();
void webServerLoop();
void otaLoop();
void buttonLoop();
void statusLEDLoop();

// ============================================================================
// Function Prototypes - Connection
// ============================================================================
bool connectWiFi();
bool connectMQTT();

// ============================================================================
// Function Prototypes - MQTT Publishing
// ============================================================================
void publishSensorData();
void publishAvailability(bool online);
void publishBridgeInfo();
void publishBridgeHealth();
bool publishMQTTMessage(const char* topic, const char* payload, bool retained = false);

// ============================================================================
// Function Prototypes - Power Management
// ============================================================================
void handleDeepSleep();
float readBatteryVoltage();
bool isBatteryLow();
bool isBatteryCritical();
float getBatteryPercentage();
String getPowerSource();

// ============================================================================
// Function Prototypes - Configuration Management
// ============================================================================
void loadConfiguration();
void saveConfiguration();
void resetConfiguration();
bool isConfigured();
void migrateEEPROM();
uint16_t calculateEEPROMChecksum();
bool verifyEEPROMChecksum();

// ============================================================================
// Function Prototypes - BLE Pairing
// ============================================================================
void startBLEPairing();
void stopBLEPairing();
bool isBLEPairingActive();
void handleBLEPairingTimeout();

// ============================================================================
// Function Prototypes - Button Handling
// ============================================================================
void handleButtonPress();
void handleShortPress();
void handleLongPress();

// ============================================================================
// Function Prototypes - Device Identity
// ============================================================================
String generateFriendlyName();
String getMACAddressSuffix();
String getDeviceTopic();
String getDeviceSetTopic();
String getDeviceGetTopic();
String getAvailabilityTopic();

// ============================================================================
// Function Prototypes - Watchdog Timer
// ============================================================================
void setupWatchdog();
void feedWatchdog();
void disableWatchdog();

// ============================================================================
// Function Prototypes - mDNS
// ============================================================================
void setupMDNS();
void updateMDNSService();
bool isMDNSRunning();

// ============================================================================
// Function Prototypes - Sensor History Buffer
// ============================================================================
void initRTCData();
void saveToHistory(float temp, float hum, uint16_t co2, uint8_t aqi, float smoke, float lux, uint8_t battery);
bool getHistoryEntry(uint8_t index, SensorHistoryEntry* entry);
uint8_t getHistoryCount();
void clearHistory();
String getHistoryJSON();
bool isRTCDataValid();

// ============================================================================
// Function Prototypes - WiFi Reconnection with Backoff
// ============================================================================
uint32_t getWifiBackoffDelay();
void resetWifiBackoff();
void incrementWifiBackoff();

// ============================================================================
// Logging Macros
// ============================================================================
#define LOG_INFO(msg)  Serial.println("[INFO] " + String(msg))
#define LOG_ERROR(msg) Serial.println("[ERROR] " + String(msg))
#define LOG_DEBUG(msg) Serial.println("[DEBUG] " + String(msg))
#define LOG_WARN(msg)  Serial.println("[WARN] " + String(msg))

#endif // CONFIG_H
