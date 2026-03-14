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
#include <esp_sleep.h>
#include <esp_wifi.h>

// Firmware Configuration
#define FW_VERSION "1.0.0"
#define DEVICE_TYPE "ESP32-C3-Analog-Sensors"
#define DEVICE_MODEL "SYSGrow-Analog-v1"
#define EEPROM_SIZE 512

// Hardware Configuration - ESP32-C3 specific pins
#define SOIL_MOISTURE_PIN_1 A0    // GPIO0 - ADC1_CH0
#define SOIL_MOISTURE_PIN_2 A1    // GPIO1 - ADC1_CH1  
#define SOIL_MOISTURE_PIN_3 A2    // GPIO2 - ADC1_CH2
#define SOIL_MOISTURE_PIN_4 A3    // GPIO3 - ADC1_CH3
#define LUX_SENSOR_PIN A4         // GPIO4 - ADC1_CH4
#define BATTERY_PIN A5            // GPIO5 - ADC2_CH0 for battery monitoring

// Digital pins for sensor power control
#define SENSOR_POWER_PIN 6        // GPIO6 - Power control for sensors
#define STATUS_LED_PIN 7          // GPIO7 - Status LED
#define BUZZER_PIN 8              // GPIO8 - Optional buzzer for alerts

// I2C pins for advanced lux sensor (TSL2591)
#define SDA_PIN 18                // GPIO18 - I2C SDA
#define SCL_PIN 19                // GPIO19 - I2C SCL

// Network Configuration
#define DEFAULT_WIFI_TIMEOUT 30000  // 30 seconds
#define WIFI_RETRY_INTERVAL 5000    // 5 seconds
#define MAX_WIFI_RETRIES 5
#define AP_TIMEOUT 300000           // 5 minutes for AP mode

// MQTT Configuration  
#define MQTT_PORT 8883              // Secure MQTT port
#define MQTT_KEEPALIVE 60
#define MQTT_BUFFER_SIZE 2048
#define MQTT_RETRY_INTERVAL 10000
#define MAX_MQTT_RETRIES 5
#define MQTT_TOPIC_PREFIX "unit/"
#define MQTT_DEVICE_TOPIC_PREFIX "device/"

// Sensor Configuration
#define SENSOR_READ_INTERVAL 60000      // 1 minute for normal operation
#define SENSOR_FAST_INTERVAL 10000      // 10 seconds for calibration mode
#define SENSOR_STABILIZATION_TIME 500   // 500ms for sensor stabilization
#define ADC_RESOLUTION 12               // 12-bit ADC resolution (0-4095)
#define ADC_SAMPLES 10                  // Number of samples for averaging
#define FILTER_SIZE 5                   // Moving average filter size

// Soil Moisture Sensor Configuration
#define SOIL_DRY_VALUE 4095            // ADC value for completely dry soil
#define SOIL_WET_VALUE 1000            // ADC value for completely wet soil
#define SOIL_CALIBRATION_SAMPLES 50    // Samples for calibration
#define SOIL_SENSOR_COUNT 4            // Number of soil moisture sensors

// Lux Sensor Configuration
#define LUX_MAX_ANALOG_VALUE 4095      // Maximum ADC value
#define LUX_MAX_LUX_VALUE 100000       // Maximum lux value for scaling
#define LUX_SENSOR_TYPE_ANALOG 0       // Analog photoresistor
#define LUX_SENSOR_TYPE_TSL2591 1      // Digital TSL2591 sensor

// Power Management
#define LOW_BATTERY_THRESHOLD 3.3      // Volts
#define CRITICAL_BATTERY_THRESHOLD 3.0 // Volts
#define DEEP_SLEEP_DURATION 300e6      // 5 minutes in microseconds
#define LIGHT_SLEEP_DURATION 60e6      // 1 minute in microseconds
#define POWER_SAVE_VOLTAGE 3.5         // Voltage to enter power save mode

// BLE Configuration
#define BLE_SERVICE_UUID        "6ba1e2d0-4c5a-11ec-81d3-0242ac130003"
#define BLE_WIFI_CHAR_UUID      "6ba1e2d1-4c5a-11ec-81d3-0242ac130003"
#define BLE_MQTT_CHAR_UUID      "6ba1e2d2-4c5a-11ec-81d3-0242ac130003"
#define BLE_SENSOR_CHAR_UUID    "6ba1e2d3-4c5a-11ec-81d3-0242ac130003"
#define BLE_DEVICE_NAME "SYSGrow-Analog"
#define BLE_TIMEOUT 300000             // 5 minutes BLE timeout

// OTA Configuration
#define OTA_UPDATE_URL "https://your-ota-server.com/firmware/esp32c3"
#define OTA_CHECK_INTERVAL 86400000    // 24 hours
#define OTA_PARTITION_SIZE 0x1E0000    // OTA partition size

// Web Server Configuration
#define WEB_SERVER_PORT 80
#define WEB_SOCKET_PORT 81

// Communication modes
enum ConnectionMode { 
    WIFI_MQTT = 0, 
    BLE_ONLY = 1, 
    OFFLINE = 2,
    AP_MODE = 3
};

// Power modes
enum PowerMode {
    NORMAL_POWER = 0,
    POWER_SAVE = 1,
    DEEP_SLEEP = 2,
    EMERGENCY = 3
};

// Sensor types
enum SensorType {
    SOIL_MOISTURE = 0,
    LUX_ANALOG = 1,
    LUX_DIGITAL = 2,
    BATTERY = 3
};

// Calibration states
enum CalibrationState {
    NOT_CALIBRATED = 0,
    CALIBRATING = 1,
    CALIBRATED = 2,
    CALIBRATION_FAILED = 3
};

// Global variables declarations
extern String device_id;
extern String unit_id;
extern ConnectionMode current_mode;
extern PowerMode power_mode;
extern bool is_provisioned;
extern bool sensors_active;
extern CalibrationState calibration_state;

// Timing variables
extern unsigned long last_sensor_read;
extern unsigned long last_mqtt_attempt;
extern unsigned long last_ota_check;
extern unsigned long last_heartbeat;
extern unsigned long system_start_time;

// Configuration storage
extern char stored_ssid[64];
extern char stored_password[64];
extern char mqtt_broker[128];
extern char mqtt_username[64];
extern char mqtt_password[64];
extern char device_name[32];

// Sensor calibration data
struct SoilCalibration {
    uint16_t dry_value;
    uint16_t wet_value;
    bool is_calibrated;
    uint32_t last_calibration;
};

struct LuxCalibration {
    uint16_t dark_value;
    uint16_t bright_value;
    float lux_factor;
    bool is_calibrated;
    uint32_t last_calibration;
};

extern SoilCalibration soil_calibration[SOIL_SENSOR_COUNT];
extern LuxCalibration lux_calibration;
extern uint8_t active_lux_sensor_type;

// Function prototypes - Core
void setupDevice();
void setupWiFi();
void setupMQTT();
void setupSensors();
void setupBLE();
void setupWebServer();
void setupOTA();
void setupPowerManagement();

// Loop functions
void mainLoop();
void mqttLoop();
void sensorLoop();
void powerManagementLoop();
void bleLoop();
void webServerLoop();
void otaLoop();
void calibrationLoop();

// Connection management
bool connectWiFi();
bool connectMQTT();
void startAPMode();
void handleConnectionLoss();
void publishSensorData();
void publishHeartbeat();
void publishDeviceStatus();

// Power management
void handleDeepSleep();
void handleLightSleep();
void enterPowerSaveMode();
void exitPowerSaveMode();
float readBatteryVoltage();
bool isBatteryLow();
bool isBatteryCritical();

// Configuration management
void loadConfiguration();
void saveConfiguration();
void resetConfiguration();
bool isConfigured();
void saveCalibrationData();
void loadCalibrationData();

// Sensor management
void initializeSensors();
void powerOnSensors();
void powerOffSensors();
void calibrateSoilSensors();
void calibrateLuxSensor();
bool validateSensorReadings();

// Utility functions
String generateDeviceId();
void blinkStatusLED(int times, int duration = 200);
void playBuzzer(int frequency, int duration);
void handleError(const String& error, bool critical = false);
void logSystemStatus();

// Logging macros with improved formatting
#define LOG_INFO(msg) Serial.println("[INFO] [" + String(millis()) + "] " + String(msg))
#define LOG_ERROR(msg) Serial.println("[ERROR] [" + String(millis()) + "] " + String(msg))
#define LOG_DEBUG(msg) Serial.println("[DEBUG] [" + String(millis()) + "] " + String(msg))
#define LOG_WARN(msg) Serial.println("[WARN] [" + String(millis()) + "] " + String(msg))

// Debug flags
#ifdef DEBUG
    #define DEBUG_PRINT(x) Serial.print(x)
    #define DEBUG_PRINTLN(x) Serial.println(x)
#else
    #define DEBUG_PRINT(x)
    #define DEBUG_PRINTLN(x)
#endif

#endif // CONFIG_H