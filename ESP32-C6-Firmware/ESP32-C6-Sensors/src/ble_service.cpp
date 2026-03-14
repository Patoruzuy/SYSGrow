/**
 * BLE Service - Provisioning and Sensor Data
 * ===========================================
 *
 * Provides BLE functionality for:
 *   - WiFi/MQTT provisioning via writable characteristics
 *   - Sensor data broadcasting via notifications
 *   - Timed pairing mode (30s timeout)
 *
 * Services:
 *   - Sensor Service: Read-only sensor data with notifications
 *   - Config Service: Writable characteristics for provisioning
 *
 * Version: 2.0.0
 */

#include "ble_service.h"
#include "config.h"
#include "sensor_air.h"

#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <ArduinoJson.h>

// ============================================================================
// BLE UUIDs
// ============================================================================

// Sensor Service (read-only sensor data)
#define SENSOR_SERVICE_UUID         BLE_SERVICE_UUID
#define SENSOR_CHAR_UUID            BLE_SENSOR_CHARACTERISTIC_UUID

// Config Service (provisioning)
#define CONFIG_SERVICE_UUID         "4fafc201-1fb5-459e-8fcc-c5c9c331914c"
#define CONFIG_CHAR_UUID            BLE_CONFIG_CHARACTERISTIC_UUID
#define CONFIG_STATUS_CHAR_UUID     "beb5483e-36e1-4688-b7f5-ea07361b26aa"

// ============================================================================
// BLE Objects
// ============================================================================

static BLEServer* pServer = nullptr;
static BLEService* pSensorService = nullptr;
static BLEService* pConfigService = nullptr;
static BLECharacteristic* pSensorCharacteristic = nullptr;
static BLECharacteristic* pConfigCharacteristic = nullptr;
static BLECharacteristic* pStatusCharacteristic = nullptr;
static BLEAdvertising* pAdvertising = nullptr;

// ============================================================================
// State Variables
// ============================================================================

static bool ble_initialized = false;
static bool ble_advertising = false;
static int connected_clients = 0;
static unsigned long last_sensor_update = 0;

// Provisioning data received via BLE
static bool provisioning_received = false;
static String provisioned_ssid = "";
static String provisioned_password = "";
static String provisioned_mqtt_broker = "";
static String provisioned_mqtt_username = "";
static String provisioned_mqtt_password = "";
static String provisioned_friendly_name = "";

// Sensor update interval for BLE notifications
#define BLE_SENSOR_UPDATE_INTERVAL_MS 5000

// ============================================================================
// BLE Callbacks
// ============================================================================

class ServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) override {
        connected_clients++;
        LOG_INFO("BLE client connected (total: " + String(connected_clients) + ")");
    }

    void onDisconnect(BLEServer* pServer) override {
        connected_clients--;
        if (connected_clients < 0) connected_clients = 0;
        LOG_INFO("BLE client disconnected (total: " + String(connected_clients) + ")");

        // Restart advertising if we're in pairing mode
        if (ble_pairing_active && ble_advertising) {
            pAdvertising->start();
        }
    }
};

class ConfigCharacteristicCallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* pCharacteristic) override {
        String value = pCharacteristic->getValue().c_str();

        if (value.length() == 0) {
            LOG_WARN("Empty config received via BLE");
            updateConfigStatus("error", "Empty configuration");
            return;
        }

        LOG_INFO("Received BLE configuration (" + String(value.length()) + " bytes)");
        LOG_DEBUG("Config payload: " + value.substring(0, min((int)value.length(), 100)));

        // Parse JSON configuration
        DynamicJsonDocument doc(512);
        DeserializationError error = deserializeJson(doc, value);

        if (error) {
            LOG_ERROR("Failed to parse BLE config JSON: " + String(error.c_str()));
            updateConfigStatus("error", "Invalid JSON");
            return;
        }

        // Extract configuration values
        bool hasWifi = false;
        bool hasMqtt = false;

        if (doc.containsKey("ssid")) {
            provisioned_ssid = doc["ssid"].as<String>();
            hasWifi = provisioned_ssid.length() > 0;
        }

        if (doc.containsKey("password")) {
            provisioned_password = doc["password"].as<String>();
        }

        if (doc.containsKey("mqtt_broker")) {
            provisioned_mqtt_broker = doc["mqtt_broker"].as<String>();
            hasMqtt = provisioned_mqtt_broker.length() > 0;
        }

        if (doc.containsKey("mqtt_username")) {
            provisioned_mqtt_username = doc["mqtt_username"].as<String>();
        }

        if (doc.containsKey("mqtt_password")) {
            provisioned_mqtt_password = doc["mqtt_password"].as<String>();
        }

        if (doc.containsKey("friendly_name")) {
            provisioned_friendly_name = doc["friendly_name"].as<String>();
        }

        // Validate minimum requirements
        if (!hasWifi) {
            LOG_ERROR("WiFi SSID required for provisioning");
            updateConfigStatus("error", "WiFi SSID required");
            return;
        }

        if (!hasMqtt) {
            LOG_ERROR("MQTT broker required for provisioning");
            updateConfigStatus("error", "MQTT broker required");
            return;
        }

        // Save configuration to EEPROM
        provisioned_ssid.toCharArray(stored_ssid, EEPROM_WIFI_SSID_SIZE);
        provisioned_password.toCharArray(stored_password, EEPROM_WIFI_PASSWORD_SIZE);
        provisioned_mqtt_broker.toCharArray(mqtt_broker, EEPROM_MQTT_BROKER_SIZE);
        provisioned_mqtt_username.toCharArray(mqtt_username, EEPROM_MQTT_USERNAME_SIZE);
        provisioned_mqtt_password.toCharArray(mqtt_password, EEPROM_MQTT_PASSWORD_SIZE);

        if (provisioned_friendly_name.length() > 0) {
            provisioned_friendly_name.toCharArray(stored_friendly_name, EEPROM_FRIENDLY_NAME_SIZE);
            friendly_name = provisioned_friendly_name;
        }

        saveConfiguration();

        provisioning_received = true;

        LOG_INFO("Configuration saved successfully");
        LOG_INFO("  WiFi SSID: " + provisioned_ssid);
        LOG_INFO("  MQTT Broker: " + provisioned_mqtt_broker);

        updateConfigStatus("ok", "Configuration saved. Restarting...");

        // Device will restart in main loop when provisioning_received is detected
    }

    void updateConfigStatus(const char* status, const char* message) {
        if (pStatusCharacteristic == nullptr) {
            return;
        }

        DynamicJsonDocument doc(256);
        doc["status"] = status;
        doc["message"] = message;
        doc["timestamp"] = millis();

        String payload;
        serializeJson(doc, payload);

        pStatusCharacteristic->setValue(payload.c_str());
        pStatusCharacteristic->notify();
    }
};

// ============================================================================
// Setup Functions
// ============================================================================

void setupBLE() {
    if (ble_initialized) {
        LOG_DEBUG("BLE already initialized");
        return;
    }

    LOG_INFO("Initializing BLE...");

    // Create device name
    String deviceName = String(BLE_DEVICE_NAME_PREFIX) + getMACAddressSuffix();

    // Initialize BLE
    BLEDevice::init(deviceName.c_str());

    // Create server
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new ServerCallbacks());

    // -------------------------------------------------------------------------
    // Sensor Service (read-only, with notifications)
    // -------------------------------------------------------------------------
    pSensorService = pServer->createService(SENSOR_SERVICE_UUID);

    pSensorCharacteristic = pSensorService->createCharacteristic(
        SENSOR_CHAR_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
    );

    pSensorCharacteristic->addDescriptor(new BLE2902());  // Enable notifications

    // Set initial value
    pSensorCharacteristic->setValue("{}");

    pSensorService->start();
    LOG_DEBUG("Sensor service started");

    // -------------------------------------------------------------------------
    // Config Service (writable for provisioning)
    // -------------------------------------------------------------------------
    pConfigService = pServer->createService(CONFIG_SERVICE_UUID);

    // Config characteristic (writable)
    pConfigCharacteristic = pConfigService->createCharacteristic(
        CONFIG_CHAR_UUID,
        BLECharacteristic::PROPERTY_WRITE | BLECharacteristic::PROPERTY_WRITE_NR
    );

    pConfigCharacteristic->setCallbacks(new ConfigCharacteristicCallbacks());

    // Status characteristic (read + notify)
    pStatusCharacteristic = pConfigService->createCharacteristic(
        CONFIG_STATUS_CHAR_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY
    );

    pStatusCharacteristic->addDescriptor(new BLE2902());
    pStatusCharacteristic->setValue("{\"status\":\"ready\"}");

    pConfigService->start();
    LOG_DEBUG("Config service started");

    // -------------------------------------------------------------------------
    // Advertising
    // -------------------------------------------------------------------------
    pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SENSOR_SERVICE_UUID);
    pAdvertising->addServiceUUID(CONFIG_SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    pAdvertising->setMinPreferred(0x06);  // Helps with iPhone connection issues
    pAdvertising->setMinPreferred(0x12);

    ble_initialized = true;
    LOG_INFO("BLE initialized as: " + deviceName);

    // Start advertising if in BLE mode
    if (current_mode == BLE_ONLY || ble_pairing_active) {
        startBLEAdvertising();
    }
}

// ============================================================================
// Loop Function
// ============================================================================

void bleLoop() {
    if (!ble_initialized) {
        return;
    }

    unsigned long now = millis();

    // Update sensor data periodically
    if (connected_clients > 0 && (now - last_sensor_update >= BLE_SENSOR_UPDATE_INTERVAL_MS)) {
        updateBLESensorData();
        last_sensor_update = now;
    }

    // Check if provisioning was received
    if (provisioning_received) {
        LOG_INFO("Provisioning complete, restarting in 1 second...");
        delay(1000);
        ESP.restart();
    }
}

// ============================================================================
// Advertising Control
// ============================================================================

void startBLEAdvertising() {
    if (!ble_initialized) {
        setupBLE();
    }

    if (pAdvertising != nullptr && !ble_advertising) {
        pAdvertising->start();
        ble_advertising = true;
        LOG_INFO("BLE advertising started");
    }
}

void stopBLEAdvertising() {
    if (pAdvertising != nullptr && ble_advertising) {
        pAdvertising->stop();
        ble_advertising = false;
        LOG_INFO("BLE advertising stopped");
    }
}

bool isBLEAdvertising() {
    return ble_advertising;
}

// ============================================================================
// Provisioning Functions
// ============================================================================

bool hasProvisioningConfig() {
    return provisioning_received;
}

void clearProvisioningConfig() {
    provisioning_received = false;
    provisioned_ssid = "";
    provisioned_password = "";
    provisioned_mqtt_broker = "";
    provisioned_mqtt_username = "";
    provisioned_mqtt_password = "";
    provisioned_friendly_name = "";
}

String getProvisionedSSID() {
    return provisioned_ssid;
}

String getProvisionedPassword() {
    return provisioned_password;
}

String getProvisionedMQTTBroker() {
    return provisioned_mqtt_broker;
}

String getProvisionedMQTTUsername() {
    return provisioned_mqtt_username;
}

String getProvisionedMQTTPassword() {
    return provisioned_mqtt_password;
}

String getProvisionedFriendlyName() {
    return provisioned_friendly_name;
}

// ============================================================================
// Sensor Data Broadcasting
// ============================================================================

void updateBLESensorData() {
    if (!ble_initialized || pSensorCharacteristic == nullptr) {
        return;
    }

    // Build sensor data JSON
    DynamicJsonDocument doc(512);

    float temp = readTemperature();
    float hum = readHumidity();
    float lux = readLightLevel();
    int co2 = readCO2();
    int aqi = readAirQualityIndex();

    if (!isnan(temp)) doc["temperature"] = round(temp * 10) / 10.0;
    if (!isnan(hum)) doc["humidity"] = round(hum * 10) / 10.0;
    if (!isnan(lux)) doc["lux"] = round(lux);
    if (co2 > 0) doc["co2"] = co2;
    if (aqi > 0) doc["air_quality"] = aqi;

    doc["battery"] = round(getBatteryPercentage());
    doc["uptime"] = millis() / 1000;

    String payload;
    serializeJson(doc, payload);

    // Update characteristic and notify
    pSensorCharacteristic->setValue(payload.c_str());
    pSensorCharacteristic->notify();

    LOG_DEBUG("BLE sensor data updated");
}

int getBLEConnectedCount() {
    return connected_clients;
}

// ============================================================================
// Status Functions
// ============================================================================

bool isBLEReady() {
    return ble_initialized;
}

String getBLEDeviceName() {
    if (!ble_initialized) {
        return "";
    }
    return String(BLE_DEVICE_NAME_PREFIX) + getMACAddressSuffix();
}
