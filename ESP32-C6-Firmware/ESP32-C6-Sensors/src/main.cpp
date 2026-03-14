/**
 * SYSGrow ESP32-C6 Sensor Module
 * ==============================
 *
 * Main entry point for the ESP32-C6-Sensors firmware.
 * Implements Zigbee2MQTT-style MQTT protocol for sensor devices.
 *
 * Features:
 *   - ENS160+AHT21 (Temperature, Humidity, CO2, AQI, VOC)
 *   - MQ2 (Smoke/Gas detection)
 *   - TSL2591 (Light: Lux, Full Spectrum, Infrared, Visible)
 *   - BLE provisioning with physical button support
 *   - WiFi/MQTT communication
 *   - OTA updates
 *   - Power management with battery monitoring
 *
 * Version: 2.0.0
 */

#include "config.h"
#include "sensor_co.h"
#include "sensor_air.h"
#include "mqtt_service.h"
#include "ota_service.h"
#include "power_management.h"
#include "ble_service.h"
#include "web_server.h"
#include <esp_task_wdt.h>
#include <esp_sleep.h>

// ============================================================================
// RTC Memory Storage (survives deep sleep)
// ============================================================================
RTC_DATA_ATTR RTCData rtc_data;

// ============================================================================
// mDNS State
// ============================================================================
static bool mdns_running = false;

// ============================================================================
// Global Variables
// ============================================================================

// Device identity
String friendly_name;

// Connection state
ConnectionMode current_mode = WIFI_MQTT;
bool is_provisioned = false;

// BLE pairing state
bool ble_pairing_active = false;
unsigned long ble_pairing_start_time = 0;

// Timing variables
unsigned long last_sensor_read = 0;
unsigned long last_mqtt_attempt = 0;
unsigned long last_ota_check = 0;

// Button state
unsigned long button_press_start_time = 0;
bool button_pressed = false;
static bool button_state_last = HIGH;  // Button uses pull-up, LOW when pressed

// Configuration storage
char stored_ssid[EEPROM_WIFI_SSID_SIZE] = "";
char stored_password[EEPROM_WIFI_PASSWORD_SIZE] = "";
char mqtt_broker[EEPROM_MQTT_BROKER_SIZE] = "";
char mqtt_username[EEPROM_MQTT_USERNAME_SIZE] = "";
char mqtt_password[EEPROM_MQTT_PASSWORD_SIZE] = "";
char stored_friendly_name[EEPROM_FRIENDLY_NAME_SIZE] = "";
uint32_t polling_interval_ms = DEFAULT_POLLING_INTERVAL_MS;
uint32_t config_flags = 0;
CalibrationData calibration_data = {0.0f, 0.0f, 1.0f, 1.0f, {0, 0, 0, 0}};

// LED blink state
static unsigned long last_led_toggle = 0;
static bool led_state = false;

// ============================================================================
// Setup Function
// ============================================================================

void setup() {
    Serial.begin(115200);
    delay(1000);

    LOG_INFO("========================================");
    LOG_INFO("SYSGrow ESP32-C6 Sensor Module v" + String(FW_VERSION));
    LOG_INFO("========================================");

    // Initialize watchdog timer
    setupWatchdog();

    // Initialize RTC data if coming from power-on reset
    initRTCData();

    // Initialize EEPROM
    EEPROM.begin(EEPROM_SIZE);

    // Check for EEPROM version and migrate if needed
    migrateEEPROM();

    // Load configuration
    loadConfiguration();

    // Generate or load friendly_name
    if (strlen(stored_friendly_name) > 0) {
        friendly_name = String(stored_friendly_name);
    } else {
        friendly_name = generateFriendlyName();
        friendly_name.toCharArray(stored_friendly_name, EEPROM_FRIENDLY_NAME_SIZE);
        saveConfiguration();
    }

    LOG_INFO("Friendly Name: " + friendly_name);
    LOG_INFO("Polling Interval: " + String(polling_interval_ms) + "ms");

    // Initialize hardware
    setupButton();
    setupStatusLED();
    setupSensors();
    setupPowerManagement();

    // Check if device is provisioned
    if (!isConfigured()) {
        LOG_WARN("Device not configured, starting BLE provisioning mode");
        current_mode = BLE_ONLY;
        setupBLE();
        setupWebServer();
        return;
    }

    is_provisioned = true;

    // Check battery level
    if (isBatteryCritical()) {
        LOG_WARN("Battery critical, entering deep sleep");
        current_mode = OFFLINE;
        handleDeepSleep();
        return;
    }

    // Attempt WiFi connection
    if (connectWiFi()) {
        LOG_INFO("WiFi connected successfully");
        current_mode = WIFI_MQTT;
        resetWifiBackoff();  // Reset backoff on successful connection

        // Initialize mDNS for device discovery
        setupMDNS();

        // Initialize services
        setupMQTT();
        setupOTA();
        setupWebServer();

        // Connect to MQTT
        if (connectMQTT()) {
            // Perform initial sensor reading
            publishSensorData();
        }
    } else {
        LOG_ERROR("WiFi connection failed, falling back to BLE mode");
        current_mode = BLE_ONLY;
        setupBLE();
        setupWebServer();
    }

    LOG_INFO("Setup completed, mode: " + String(current_mode));
}

// ============================================================================
// Main Loop
// ============================================================================

void loop() {
    unsigned long now = millis();

    // Handle button input (always active)
    buttonLoop();

    // Handle BLE pairing timeout
    handleBLEPairingTimeout();

    // Update status LED
    statusLEDLoop();

    // Handle different operation modes
    switch (current_mode) {
        case WIFI_MQTT:
            mqttLoop();

            // Periodic sensor readings
            if (now - last_sensor_read >= polling_interval_ms) {
                publishSensorData();
                last_sensor_read = now;
            }

            // OTA updates check
            if (now - last_ota_check >= OTA_CHECK_INTERVAL) {
                otaLoop();
                last_ota_check = now;
            }

            webServerLoop();
            break;

        case BLE_ONLY:
            bleLoop();
            webServerLoop();

            // Still read sensors for local access
            if (now - last_sensor_read >= polling_interval_ms) {
                sensorLoop();
                last_sensor_read = now;
            }

            // Check if WiFi credentials were provisioned
            if (isConfigured() && !is_provisioned) {
                LOG_INFO("Configuration received, restarting...");
                delay(500);
                ESP.restart();
            }
            break;

        case BLE_PAIRING:
            // Temporary pairing mode (from button press or MQTT command)
            bleLoop();
            mqttLoop();  // Keep MQTT running during pairing

            // Check timeout (handled in handleBLEPairingTimeout)
            break;

        case OFFLINE:
            // Minimal operation, check if we can recover
            if (now - last_mqtt_attempt >= MQTT_RETRY_INTERVAL * 5) {
                if (readBatteryVoltage() > LOW_BATTERY_THRESHOLD + 0.2) {
                    LOG_INFO("Battery recovered, attempting reconnection");
                    ESP.restart();
                }
                last_mqtt_attempt = now;
            }
            break;
    }

    // Power management
    powerManagementLoop();

    // Feed watchdog timer (critical!)
    feedWatchdog();

    // Yield for background tasks
    yield();
}

// ============================================================================
// WiFi Connection
// ============================================================================

bool connectWiFi() {
    if (strlen(stored_ssid) == 0) {
        LOG_ERROR("No WiFi credentials stored");
        return false;
    }

    // Get current backoff delay
    uint32_t backoff_delay = getWifiBackoffDelay();
    if (backoff_delay > WIFI_BACKOFF_BASE_MS) {
        LOG_INFO("WiFi backoff delay: " + String(backoff_delay) + "ms");
        delay(backoff_delay);
    }

    LOG_INFO("Connecting to WiFi: " + String(stored_ssid));
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);  // Enable auto-reconnect
    WiFi.begin(stored_ssid, stored_password);

    unsigned long start_time = millis();
    int retry_count = 0;

    while (WiFi.status() != WL_CONNECTED && retry_count < MAX_WIFI_RETRIES) {
        // Feed watchdog during connection attempts
        feedWatchdog();

        if (millis() - start_time >= DEFAULT_WIFI_TIMEOUT) {
            LOG_WARN("WiFi connection timeout (attempt " + String(retry_count + 1) + "/" + String(MAX_WIFI_RETRIES) + ")");
            WiFi.disconnect();

            // Apply exponential backoff between retries
            uint32_t retry_delay = min(WIFI_BACKOFF_BASE_MS * (1 << retry_count), (uint32_t)WIFI_BACKOFF_MAX_MS);
            LOG_INFO("Waiting " + String(retry_delay) + "ms before retry...");
            delay(retry_delay);
            feedWatchdog();

            WiFi.begin(stored_ssid, stored_password);
            start_time = millis();
            retry_count++;
        }

        // Blink LED while connecting
        if (millis() - last_led_toggle >= LED_BLINK_CONNECTING) {
            led_state = !led_state;
            digitalWrite(STATUS_LED_PIN, led_state ? HIGH : LOW);
            last_led_toggle = millis();
        }

        delay(100);
        Serial.print(".");
    }

    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        LOG_INFO("WiFi connected! IP: " + WiFi.localIP().toString());
        LOG_INFO("MAC Address: " + WiFi.macAddress());
        LOG_INFO("RSSI: " + String(WiFi.RSSI()) + " dBm");
        resetWifiBackoff();  // Reset backoff on success
        return true;
    } else {
        incrementWifiBackoff();  // Increase backoff for next attempt
        LOG_ERROR("WiFi connection failed after " + String(MAX_WIFI_RETRIES) + " retries");
        return false;
    }
}

// ============================================================================
// Device Identity Functions
// ============================================================================

String generateFriendlyName() {
    String suffix = getMACAddressSuffix();
    return "sysgrow-" + suffix;
}

String getMACAddressSuffix() {
    String mac = WiFi.macAddress();
    // Get last 4 bytes (8 characters) of MAC, remove colons
    mac.replace(":", "");
    return mac.substring(mac.length() - 8);
}

// ============================================================================
// Button Handling
// ============================================================================

void setupButton() {
    pinMode(BLE_BUTTON_PIN, INPUT_PULLUP);
    LOG_DEBUG("Button configured on GPIO" + String(BLE_BUTTON_PIN));
}

void buttonLoop() {
    bool button_state = digitalRead(BLE_BUTTON_PIN);

    // Button pressed (LOW with pull-up)
    if (button_state == LOW && button_state_last == HIGH) {
        button_press_start_time = millis();
        button_pressed = true;
        LOG_DEBUG("Button pressed");
    }

    // Button released
    if (button_state == HIGH && button_state_last == LOW && button_pressed) {
        unsigned long press_duration = millis() - button_press_start_time;
        button_pressed = false;

        LOG_DEBUG("Button released after " + String(press_duration) + "ms");

        if (press_duration >= LONG_PRESS_MS) {
            handleLongPress();
        } else if (press_duration >= 100) {  // Debounce
            handleShortPress();
        }
    }

    button_state_last = button_state;
}

void handleShortPress() {
    LOG_INFO("Short press detected - enabling BLE pairing mode");
    startBLEPairing();
}

void handleLongPress() {
    LOG_WARN("Long press detected - performing factory reset");

    // Visual feedback - rapid blink
    for (int i = 0; i < 10; i++) {
        digitalWrite(STATUS_LED_PIN, HIGH);
        delay(100);
        digitalWrite(STATUS_LED_PIN, LOW);
        delay(100);
    }

    // Perform factory reset
    resetConfiguration();
    delay(100);
    ESP.restart();
}

// ============================================================================
// BLE Pairing Mode
// ============================================================================

void startBLEPairing() {
    if (ble_pairing_active) {
        LOG_DEBUG("BLE pairing already active");
        return;
    }

    LOG_INFO("Starting BLE pairing mode (30s timeout)");
    ble_pairing_active = true;
    ble_pairing_start_time = millis();

    // Store previous mode if not already in BLE mode
    if (current_mode != BLE_ONLY && current_mode != BLE_PAIRING) {
        // Initialize BLE if not already running
        setupBLE();
    }

    // Switch to BLE pairing mode (temporary)
    if (current_mode == WIFI_MQTT) {
        current_mode = BLE_PAIRING;
    }
}

void stopBLEPairing() {
    if (!ble_pairing_active) {
        return;
    }

    LOG_INFO("Stopping BLE pairing mode");
    ble_pairing_active = false;
    ble_pairing_start_time = 0;

    // Return to previous mode
    if (current_mode == BLE_PAIRING) {
        if (isMQTTConnected()) {
            current_mode = WIFI_MQTT;
        } else if (isConfigured()) {
            current_mode = WIFI_MQTT;
            connectMQTT();
        } else {
            current_mode = BLE_ONLY;
        }
    }
}

bool isBLEPairingActive() {
    return ble_pairing_active;
}

void handleBLEPairingTimeout() {
    if (!ble_pairing_active) {
        return;
    }

    if (millis() - ble_pairing_start_time >= BLE_PAIRING_TIMEOUT_MS) {
        LOG_INFO("BLE pairing timeout");
        stopBLEPairing();
    }
}

// ============================================================================
// Status LED
// ============================================================================

void setupStatusLED() {
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);
    LOG_DEBUG("Status LED configured on GPIO" + String(STATUS_LED_PIN));
}

void statusLEDLoop() {
    unsigned long now = millis();
    unsigned long blink_interval = 0;

    // Determine blink pattern based on state
    if (ble_pairing_active) {
        blink_interval = LED_BLINK_PAIRING;  // Fast blink
    } else if (current_mode == BLE_ONLY) {
        blink_interval = LED_BLINK_PAIRING;  // Fast blink
    } else if (current_mode == WIFI_MQTT && !isMQTTConnected()) {
        blink_interval = LED_BLINK_CONNECTING;  // Slow blink
    } else if (current_mode == WIFI_MQTT && isMQTTConnected()) {
        // Solid on when connected
        digitalWrite(STATUS_LED_PIN, HIGH);
        return;
    } else {
        // Off when offline
        digitalWrite(STATUS_LED_PIN, LOW);
        return;
    }

    // Blink LED
    if (now - last_led_toggle >= blink_interval) {
        led_state = !led_state;
        digitalWrite(STATUS_LED_PIN, led_state ? HIGH : LOW);
        last_led_toggle = now;
    }
}

// ============================================================================
// Configuration Management
// ============================================================================

void loadConfiguration() {
    LOG_DEBUG("Loading configuration from EEPROM...");

    // Read WiFi credentials
    for (int i = 0; i < EEPROM_WIFI_SSID_SIZE; i++) {
        stored_ssid[i] = EEPROM.read(EEPROM_WIFI_SSID_OFFSET + i);
    }
    stored_ssid[EEPROM_WIFI_SSID_SIZE - 1] = '\0';

    for (int i = 0; i < EEPROM_WIFI_PASSWORD_SIZE; i++) {
        stored_password[i] = EEPROM.read(EEPROM_WIFI_PASSWORD_OFFSET + i);
    }
    stored_password[EEPROM_WIFI_PASSWORD_SIZE - 1] = '\0';

    // Read MQTT broker
    for (int i = 0; i < EEPROM_MQTT_BROKER_SIZE; i++) {
        mqtt_broker[i] = EEPROM.read(EEPROM_MQTT_BROKER_OFFSET + i);
    }
    mqtt_broker[EEPROM_MQTT_BROKER_SIZE - 1] = '\0';

    // Read friendly name
    for (int i = 0; i < EEPROM_FRIENDLY_NAME_SIZE; i++) {
        stored_friendly_name[i] = EEPROM.read(EEPROM_FRIENDLY_NAME_OFFSET + i);
    }
    stored_friendly_name[EEPROM_FRIENDLY_NAME_SIZE - 1] = '\0';

    // Read MQTT credentials
    for (int i = 0; i < EEPROM_MQTT_USERNAME_SIZE; i++) {
        mqtt_username[i] = EEPROM.read(EEPROM_MQTT_USERNAME_OFFSET + i);
    }
    mqtt_username[EEPROM_MQTT_USERNAME_SIZE - 1] = '\0';

    for (int i = 0; i < EEPROM_MQTT_PASSWORD_SIZE; i++) {
        mqtt_password[i] = EEPROM.read(EEPROM_MQTT_PASSWORD_OFFSET + i);
    }
    mqtt_password[EEPROM_MQTT_PASSWORD_SIZE - 1] = '\0';

    // Read polling interval
    EEPROM.get(EEPROM_POLLING_INTERVAL_OFFSET, polling_interval_ms);
    if (polling_interval_ms < 5000 || polling_interval_ms > 3600000) {
        polling_interval_ms = DEFAULT_POLLING_INTERVAL_MS;
    }

    // Read config flags
    EEPROM.get(EEPROM_CONFIG_FLAGS_OFFSET, config_flags);

    // Read calibration data
    EEPROM.get(EEPROM_CALIBRATION_OFFSET, calibration_data);

    LOG_DEBUG("Configuration loaded");
    LOG_DEBUG("  SSID: " + String(stored_ssid));
    LOG_DEBUG("  MQTT Broker: " + String(mqtt_broker));
    LOG_DEBUG("  Friendly Name: " + String(stored_friendly_name));
}

void saveConfiguration() {
    LOG_DEBUG("Saving configuration to EEPROM...");

    // Write WiFi credentials
    for (int i = 0; i < EEPROM_WIFI_SSID_SIZE; i++) {
        EEPROM.write(EEPROM_WIFI_SSID_OFFSET + i, stored_ssid[i]);
    }

    for (int i = 0; i < EEPROM_WIFI_PASSWORD_SIZE; i++) {
        EEPROM.write(EEPROM_WIFI_PASSWORD_OFFSET + i, stored_password[i]);
    }

    // Write MQTT broker
    for (int i = 0; i < EEPROM_MQTT_BROKER_SIZE; i++) {
        EEPROM.write(EEPROM_MQTT_BROKER_OFFSET + i, mqtt_broker[i]);
    }

    // Write friendly name
    for (int i = 0; i < EEPROM_FRIENDLY_NAME_SIZE; i++) {
        EEPROM.write(EEPROM_FRIENDLY_NAME_OFFSET + i, stored_friendly_name[i]);
    }

    // Write MQTT credentials
    for (int i = 0; i < EEPROM_MQTT_USERNAME_SIZE; i++) {
        EEPROM.write(EEPROM_MQTT_USERNAME_OFFSET + i, mqtt_username[i]);
    }

    for (int i = 0; i < EEPROM_MQTT_PASSWORD_SIZE; i++) {
        EEPROM.write(EEPROM_MQTT_PASSWORD_OFFSET + i, mqtt_password[i]);
    }

    // Write polling interval
    EEPROM.put(EEPROM_POLLING_INTERVAL_OFFSET, polling_interval_ms);

    // Write config flags
    EEPROM.put(EEPROM_CONFIG_FLAGS_OFFSET, config_flags);

    // Write calibration data
    EEPROM.put(EEPROM_CALIBRATION_OFFSET, calibration_data);

    // Write EEPROM version
    uint16_t version = EEPROM_CURRENT_VERSION;
    EEPROM.put(EEPROM_VERSION_OFFSET, version);

    // Calculate and write checksum
    uint16_t checksum = calculateEEPROMChecksum();
    EEPROM.put(EEPROM_CHECKSUM_OFFSET, checksum);

    EEPROM.commit();
    LOG_DEBUG("Configuration saved");
}

bool isConfigured() {
    return (strlen(stored_ssid) > 0 &&
            strlen(stored_password) > 0 &&
            strlen(mqtt_broker) > 0);
}

void resetConfiguration() {
    LOG_WARN("Resetting all configuration to defaults...");

    memset(stored_ssid, 0, sizeof(stored_ssid));
    memset(stored_password, 0, sizeof(stored_password));
    memset(mqtt_broker, 0, sizeof(mqtt_broker));
    memset(mqtt_username, 0, sizeof(mqtt_username));
    memset(mqtt_password, 0, sizeof(mqtt_password));
    memset(stored_friendly_name, 0, sizeof(stored_friendly_name));

    polling_interval_ms = DEFAULT_POLLING_INTERVAL_MS;
    config_flags = 0;

    calibration_data = {0.0f, 0.0f, 1.0f, 1.0f, {0, 0, 0, 0}};

    saveConfiguration();
    is_provisioned = false;

    LOG_INFO("Configuration reset complete");
}

void migrateEEPROM() {
    uint16_t stored_version = 0;
    EEPROM.get(EEPROM_VERSION_OFFSET, stored_version);

    if (stored_version == EEPROM_CURRENT_VERSION) {
        LOG_DEBUG("EEPROM version current (" + String(EEPROM_CURRENT_VERSION) + ")");
        return;
    }

    LOG_INFO("Migrating EEPROM from version " + String(stored_version) + " to " + String(EEPROM_CURRENT_VERSION));

    // Version 0 or 1: Old layout, need full reset
    if (stored_version < 2) {
        LOG_WARN("Old EEPROM format detected, performing clean migration");

        // Try to preserve WiFi credentials if they look valid
        char temp_ssid[64] = "";
        char temp_pass[64] = "";
        char temp_broker[128] = "";

        // Read from old offsets (version 1 layout)
        for (int i = 0; i < 64 && i < EEPROM_SIZE; i++) {
            temp_ssid[i] = EEPROM.read(i);
        }
        for (int i = 0; i < 64 && (64 + i) < EEPROM_SIZE; i++) {
            temp_pass[i] = EEPROM.read(64 + i);
        }
        for (int i = 0; i < 128 && (128 + i) < EEPROM_SIZE; i++) {
            temp_broker[i] = EEPROM.read(128 + i);
        }

        // Check if they look valid (printable ASCII)
        bool ssid_valid = strlen(temp_ssid) > 0 && temp_ssid[0] >= 32 && temp_ssid[0] < 127;
        bool pass_valid = strlen(temp_pass) > 0 && temp_pass[0] >= 32 && temp_pass[0] < 127;
        bool broker_valid = strlen(temp_broker) > 0 && temp_broker[0] >= 32 && temp_broker[0] < 127;

        // Clear EEPROM
        for (int i = 0; i < EEPROM_SIZE; i++) {
            EEPROM.write(i, 0);
        }

        // Restore valid credentials to new layout
        if (ssid_valid) {
            strncpy(stored_ssid, temp_ssid, EEPROM_WIFI_SSID_SIZE - 1);
        }
        if (pass_valid) {
            strncpy(stored_password, temp_pass, EEPROM_WIFI_PASSWORD_SIZE - 1);
        }
        if (broker_valid) {
            // Broker was at offset 128 with 128 bytes, now at 128 with 64 bytes
            strncpy(mqtt_broker, temp_broker, EEPROM_MQTT_BROKER_SIZE - 1);
        }

        // Set defaults
        polling_interval_ms = DEFAULT_POLLING_INTERVAL_MS;
        config_flags = 0;
        calibration_data = {0.0f, 0.0f, 1.0f, 1.0f, {0, 0, 0, 0}};

        // Save with new format
        saveConfiguration();

        LOG_INFO("EEPROM migration complete");
    }
}

uint16_t calculateEEPROMChecksum() {
    uint16_t checksum = 0;
    for (int i = 0; i < EEPROM_CHECKSUM_OFFSET; i++) {
        checksum += EEPROM.read(i);
    }
    return checksum;
}

bool verifyEEPROMChecksum() {
    uint16_t stored_checksum;
    EEPROM.get(EEPROM_CHECKSUM_OFFSET, stored_checksum);
    uint16_t calculated = calculateEEPROMChecksum();
    return stored_checksum == calculated;
}

// ============================================================================
// Power Management Stubs (implemented in power_management.cpp)
// ============================================================================

// These functions should be implemented in power_management.cpp
// Stubs provided here for completeness if power_management.cpp doesn't exist

#ifndef POWER_MANAGEMENT_IMPLEMENTED

float readBatteryVoltage() {
    int raw = analogRead(BATTERY_PIN);
    // Assuming voltage divider: actual = raw * (3.3 / 4095) * 2
    return (raw / 4095.0) * 3.3 * 2.0;
}

bool isBatteryLow() {
    return readBatteryVoltage() < LOW_BATTERY_THRESHOLD;
}

bool isBatteryCritical() {
    return readBatteryVoltage() < CRITICAL_BATTERY_THRESHOLD;
}

float getBatteryPercentage() {
    float voltage = readBatteryVoltage();
    // Map 3.0V (0%) to 4.2V (100%) for typical Li-ion
    float percentage = (voltage - 3.0) / (4.2 - 3.0) * 100.0;
    return constrain(percentage, 0, 100);
}

String getPowerSource() {
    float voltage = readBatteryVoltage();
    if (voltage > 4.3) {
        return "usb";  // USB powered (voltage higher than battery max)
    } else if (voltage > 0) {
        return "battery";
    }
    return "unknown";
}

void handleDeepSleep() {
    LOG_INFO("Entering deep sleep for " + String(DEEP_SLEEP_DURATION / 1e6) + " seconds");
    esp_deep_sleep(DEEP_SLEEP_DURATION);
}

void setupPowerManagement() {
    analogReadResolution(12);
    pinMode(BATTERY_PIN, INPUT);
}

void powerManagementLoop() {
    // Check for low battery periodically
    static unsigned long last_check = 0;
    if (millis() - last_check >= 60000) {  // Check every minute
        if (isBatteryCritical() && current_mode != OFFLINE) {
            LOG_WARN("Battery critical, entering low power mode");
            current_mode = OFFLINE;
            disconnectMQTT();
            handleDeepSleep();
        }
        last_check = millis();
    }
}

#endif // POWER_MANAGEMENT_IMPLEMENTED

// ============================================================================
// Watchdog Timer Functions
// ============================================================================

void setupWatchdog() {
#if WATCHDOG_ENABLED
    LOG_INFO("Initializing watchdog timer (" + String(WATCHDOG_TIMEOUT_MS / 1000) + "s timeout)");

    // Configure the Task Watchdog Timer (TWDT)
    esp_task_wdt_config_t twdt_config = {
        .timeout_ms = WATCHDOG_TIMEOUT_MS,
        .idle_core_mask = (1 << portNUM_PROCESSORS) - 1,  // Watch all cores
        .trigger_panic = true  // Trigger panic on timeout
    };

    esp_err_t err = esp_task_wdt_init(&twdt_config);
    if (err == ESP_OK) {
        // Subscribe the current task to the watchdog
        esp_task_wdt_add(NULL);
        LOG_INFO("Watchdog timer initialized successfully");
    } else if (err == ESP_ERR_INVALID_STATE) {
        // Already initialized, just add current task
        esp_task_wdt_add(NULL);
        LOG_DEBUG("Watchdog already initialized, task subscribed");
    } else {
        LOG_ERROR("Failed to initialize watchdog: " + String(err));
    }
#else
    LOG_DEBUG("Watchdog timer disabled");
#endif
}

void feedWatchdog() {
#if WATCHDOG_ENABLED
    esp_task_wdt_reset();
#endif
}

void disableWatchdog() {
#if WATCHDOG_ENABLED
    esp_task_wdt_delete(NULL);
    LOG_INFO("Watchdog timer disabled");
#endif
}

// ============================================================================
// mDNS Functions
// ============================================================================

void setupMDNS() {
    if (mdns_running) {
        LOG_DEBUG("mDNS already running");
        return;
    }

    // Use friendly_name without the "sysgrow-" prefix as hostname
    String hostname = friendly_name;
    hostname.replace("-", "");  // Remove dashes for valid hostname

    LOG_INFO("Starting mDNS service as: " + hostname + ".local");

    if (MDNS.begin(hostname.c_str())) {
        // Add service for discovery
        MDNS.addService(MDNS_SERVICE_NAME, MDNS_SERVICE_PROTOCOL, MDNS_SERVICE_PORT);

        // Add TXT records for device info
        MDNS.addServiceTxt(MDNS_SERVICE_NAME, MDNS_SERVICE_PROTOCOL, "friendly_name", friendly_name.c_str());
        MDNS.addServiceTxt(MDNS_SERVICE_NAME, MDNS_SERVICE_PROTOCOL, "device_type", DEVICE_TYPE);
        MDNS.addServiceTxt(MDNS_SERVICE_NAME, MDNS_SERVICE_PROTOCOL, "firmware_version", FW_VERSION);
        MDNS.addServiceTxt(MDNS_SERVICE_NAME, MDNS_SERVICE_PROTOCOL, "mac", WiFi.macAddress().c_str());
        MDNS.addServiceTxt(MDNS_SERVICE_NAME, MDNS_SERVICE_PROTOCOL, "mqtt_topic", (String(MQTT_TOPIC_PREFIX) + "/" + friendly_name).c_str());

        mdns_running = true;
        LOG_INFO("mDNS service started: " + hostname + ".local");
        LOG_INFO("  Service: " + String(MDNS_SERVICE_NAME) + "." + String(MDNS_SERVICE_PROTOCOL));
    } else {
        LOG_ERROR("Failed to start mDNS service");
        mdns_running = false;
    }
}

void updateMDNSService() {
    if (!mdns_running) {
        return;
    }

    // Update TXT records if needed (e.g., after friendly_name change)
    MDNS.end();
    mdns_running = false;
    setupMDNS();
}

bool isMDNSRunning() {
    return mdns_running;
}

// ============================================================================
// RTC Memory / Sensor History Buffer Functions
// ============================================================================

void initRTCData() {
    // Check if RTC data is valid (survived from deep sleep)
    if (rtc_data.valid_marker != RTC_VALID_MARKER) {
        LOG_INFO("Initializing RTC data (fresh start or first boot)");
        memset(&rtc_data, 0, sizeof(RTCData));
        rtc_data.valid_marker = RTC_VALID_MARKER;
        rtc_data.history_index = 0;
        rtc_data.history_count = 0;
        rtc_data.wifi_retry_count = 0;
    } else {
        LOG_DEBUG("RTC data preserved from deep sleep (history count: " + String(rtc_data.history_count) + ")");
    }
}

void saveToHistory(float temp, float hum, uint16_t co2, uint8_t aqi, float smoke, float lux, uint8_t battery) {
    if (rtc_data.valid_marker != RTC_VALID_MARKER) {
        initRTCData();
    }

    // Save to circular buffer
    SensorHistoryEntry* entry = &rtc_data.history[rtc_data.history_index];
    entry->timestamp = (uint32_t)(millis() / 1000);  // Simple relative timestamp
    entry->temperature = temp;
    entry->humidity = hum;
    entry->co2 = co2;
    entry->air_quality = aqi;
    entry->smoke = smoke;
    entry->lux = lux;
    entry->battery_percent = battery;

    // Update circular buffer index
    rtc_data.history_index = (rtc_data.history_index + 1) % SENSOR_HISTORY_SIZE;
    if (rtc_data.history_count < SENSOR_HISTORY_SIZE) {
        rtc_data.history_count++;
    }

    LOG_DEBUG("Saved reading to history buffer (index: " + String(rtc_data.history_index) + ", count: " + String(rtc_data.history_count) + ")");
}

bool getHistoryEntry(uint8_t index, SensorHistoryEntry* entry) {
    if (index >= rtc_data.history_count || rtc_data.valid_marker != RTC_VALID_MARKER) {
        return false;
    }

    // Calculate actual index in circular buffer (oldest first)
    uint8_t actual_index;
    if (rtc_data.history_count < SENSOR_HISTORY_SIZE) {
        actual_index = index;
    } else {
        actual_index = (rtc_data.history_index + index) % SENSOR_HISTORY_SIZE;
    }

    *entry = rtc_data.history[actual_index];
    return true;
}

uint8_t getHistoryCount() {
    if (rtc_data.valid_marker != RTC_VALID_MARKER) {
        return 0;
    }
    return rtc_data.history_count;
}

void clearHistory() {
    rtc_data.history_index = 0;
    rtc_data.history_count = 0;
    memset(rtc_data.history, 0, sizeof(rtc_data.history));
    LOG_INFO("Sensor history buffer cleared");
}

String getHistoryJSON() {
    StaticJsonDocument<2048> doc;
    JsonArray arr = doc.to<JsonArray>();

    for (uint8_t i = 0; i < rtc_data.history_count; i++) {
        SensorHistoryEntry entry;
        if (getHistoryEntry(i, &entry)) {
            JsonObject obj = arr.createNestedObject();
            obj["ts"] = entry.timestamp;
            obj["t"] = entry.temperature;
            obj["h"] = entry.humidity;
            obj["co2"] = entry.co2;
            obj["aqi"] = entry.air_quality;
            obj["smoke"] = entry.smoke;
            obj["lux"] = entry.lux;
            obj["bat"] = entry.battery_percent;
        }
    }

    String result;
    serializeJson(doc, result);
    return result;
}

bool isRTCDataValid() {
    return rtc_data.valid_marker == RTC_VALID_MARKER;
}

// ============================================================================
// WiFi Exponential Backoff Functions
// ============================================================================

uint32_t getWifiBackoffDelay() {
    if (rtc_data.valid_marker != RTC_VALID_MARKER) {
        initRTCData();
    }

    if (rtc_data.wifi_retry_count == 0) {
        return 0;
    }

    // Exponential backoff: base * 2^retry_count, capped at max
    uint32_t delay = WIFI_BACKOFF_BASE_MS * (1 << min((int)rtc_data.wifi_retry_count, 6));
    return min(delay, (uint32_t)WIFI_BACKOFF_MAX_MS);
}

void resetWifiBackoff() {
    if (rtc_data.valid_marker != RTC_VALID_MARKER) {
        initRTCData();
    }
    rtc_data.wifi_retry_count = 0;
    LOG_DEBUG("WiFi backoff counter reset");
}

void incrementWifiBackoff() {
    if (rtc_data.valid_marker != RTC_VALID_MARKER) {
        initRTCData();
    }
    if (rtc_data.wifi_retry_count < 10) {  // Cap at 10 retries
        rtc_data.wifi_retry_count++;
    }
    LOG_DEBUG("WiFi backoff incremented to " + String(rtc_data.wifi_retry_count));
}
