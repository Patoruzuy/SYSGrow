/**
 * MQTT Service - Zigbee2MQTT-style Implementation
 * ================================================
 *
 * Implements a Zigbee2MQTT-compatible MQTT protocol for ESP32-C6 sensor devices.
 *
 * Topics:
 *   - sysgrow/<friendly_name>           - Sensor state (JSON)
 *   - sysgrow/<friendly_name>/set       - Commands (JSON)
 *   - sysgrow/<friendly_name>/get       - On-demand read trigger
 *   - sysgrow/<friendly_name>/availability - Online/offline (LWT)
 *   - sysgrow/bridge/info               - Bridge status
 *   - sysgrow/bridge/health             - Health check
 *   - sysgrow/bridge/request/*          - Bridge commands
 *   - sysgrow/bridge/response/*         - Bridge responses
 *
 * Author: SYSGrow Team
 * Version: 2.0.0
 */

#include "mqtt_service.h"
#include "config.h"
#include "sensor_air.h"
#include "sensor_co.h"
#include "ota_service.h"
#include "ble_service.h"

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ============================================================================
// MQTT Client Setup
// ============================================================================

WiFiClient espClient;
PubSubClient mqttClient(espClient);

// Connection state
static bool mqtt_initialized = false;
static unsigned long last_reconnect_attempt = 0;
static int reconnect_attempts = 0;
static unsigned long last_bridge_info_publish = 0;

// Bridge info publish interval (every 5 minutes)
#define BRIDGE_INFO_INTERVAL_MS 300000

// ============================================================================
// Setup Functions
// ============================================================================

void setupMQTT() {
    if (strlen(mqtt_broker) == 0) {
        LOG_ERROR("MQTT broker not configured");
        return;
    }

    LOG_INFO("Setting up MQTT service...");
    LOG_INFO("  Broker: " + String(mqtt_broker));
    LOG_INFO("  Friendly Name: " + friendly_name);

    mqttClient.setServer(mqtt_broker, MQTT_PORT);
    mqttClient.setBufferSize(MQTT_BUFFER_SIZE);
    mqttClient.setKeepAlive(MQTT_KEEPALIVE);
    mqttClient.setCallback(onMQTTMessage);

    mqtt_initialized = true;
    LOG_INFO("MQTT service initialized");
}

// ============================================================================
// Connection Management
// ============================================================================

bool connectMQTT() {
    if (!mqtt_initialized) {
        LOG_ERROR("MQTT not initialized");
        return false;
    }

    if (mqttClient.connected()) {
        return true;
    }

    // Build client ID from friendly_name
    String clientId = friendly_name;

    // Build availability topic for LWT
    String availabilityTopic = getAvailabilityTopic();

    LOG_INFO("Connecting to MQTT broker as: " + clientId);
    LOG_DEBUG("LWT Topic: " + availabilityTopic);

    bool connected = false;

    // Connect with credentials if provided, otherwise without
    if (strlen(mqtt_username) > 0 && strlen(mqtt_password) > 0) {
        connected = mqttClient.connect(
            clientId.c_str(),
            mqtt_username,
            mqtt_password,
            availabilityTopic.c_str(),   // LWT topic
            MQTT_QOS,                     // LWT QoS
            true,                         // LWT retain
            "offline"                     // LWT message
        );
    } else {
        connected = mqttClient.connect(
            clientId.c_str(),
            nullptr,                      // No username
            nullptr,                      // No password
            availabilityTopic.c_str(),   // LWT topic
            MQTT_QOS,                     // LWT QoS
            true,                         // LWT retain
            "offline"                     // LWT message
        );
    }

    if (connected) {
        LOG_INFO("MQTT connected successfully!");
        reconnect_attempts = 0;

        // Subscribe to topics
        subscribeToTopics();

        // Publish online status
        publishAvailability(true);

        // Publish initial bridge info
        publishBridgeInfo();

        return true;
    } else {
        int state = mqttClient.state();
        LOG_ERROR("MQTT connection failed, rc=" + String(state));
        reconnect_attempts++;
        return false;
    }
}

bool isMQTTConnected() {
    return mqttClient.connected();
}

void disconnectMQTT() {
    if (mqttClient.connected()) {
        // Publish offline status before disconnecting
        publishAvailability(false);
        mqttClient.disconnect();
        LOG_INFO("MQTT disconnected");
    }
}

// ============================================================================
// Main Loop
// ============================================================================

void mqttLoop() {
    if (!mqtt_initialized) {
        return;
    }

    if (!mqttClient.connected()) {
        unsigned long now = millis();

        // Reconnect with exponential backoff
        unsigned long backoff = MQTT_RETRY_INTERVAL * (1 << min(reconnect_attempts, 5));

        if (now - last_reconnect_attempt >= backoff) {
            last_reconnect_attempt = now;

            if (reconnect_attempts < MAX_MQTT_RETRIES) {
                LOG_INFO("Attempting MQTT reconnection...");
                connectMQTT();
            } else {
                LOG_WARN("Max MQTT retries reached, will keep trying slowly");
                // Reset counter but keep trying at max backoff
                reconnect_attempts = MAX_MQTT_RETRIES;
            }
        }
        return;
    }

    // Process incoming messages
    mqttClient.loop();

    // Periodic bridge info publishing
    unsigned long now = millis();
    if (now - last_bridge_info_publish >= BRIDGE_INFO_INTERVAL_MS) {
        publishBridgeInfo();
        last_bridge_info_publish = now;
    }
}

// ============================================================================
// Topic Builders
// ============================================================================

String getDeviceTopic() {
    return String(MQTT_TOPIC_PREFIX) + "/" + friendly_name;
}

String getDeviceSetTopic() {
    return String(MQTT_TOPIC_PREFIX) + "/" + friendly_name + "/set";
}

String getDeviceGetTopic() {
    return String(MQTT_TOPIC_PREFIX) + "/" + friendly_name + "/get";
}

String getAvailabilityTopic() {
    return String(MQTT_TOPIC_PREFIX) + "/" + friendly_name + "/availability";
}

String getBridgeInfoTopic() {
    return String(MQTT_BRIDGE_PREFIX) + "/info";
}

String getBridgeHealthTopic() {
    return String(MQTT_BRIDGE_PREFIX) + "/health";
}

// ============================================================================
// Subscription Management
// ============================================================================

void subscribeToTopics() {
    // Subscribe to device-specific topics
    String setTopic = getDeviceSetTopic();
    String getTopic = getDeviceGetTopic();

    mqttClient.subscribe(setTopic.c_str(), MQTT_QOS);
    LOG_DEBUG("Subscribed to: " + setTopic);

    mqttClient.subscribe(getTopic.c_str(), MQTT_QOS);
    LOG_DEBUG("Subscribed to: " + getTopic);

    // Subscribe to bridge request topics
    mqttClient.subscribe("sysgrow/bridge/request/permit_join", MQTT_QOS);
    mqttClient.subscribe("sysgrow/bridge/request/restart", MQTT_QOS);
    mqttClient.subscribe("sysgrow/bridge/request/device/rename", MQTT_QOS);
    mqttClient.subscribe("sysgrow/bridge/request/device/remove", MQTT_QOS);
    mqttClient.subscribe("sysgrow/bridge/request/device/ota_update/update", MQTT_QOS);
    mqttClient.subscribe("sysgrow/bridge/request/health_check", MQTT_QOS);

    LOG_INFO("Subscribed to all MQTT topics");
}

void unsubscribeFromTopics() {
    String setTopic = getDeviceSetTopic();
    String getTopic = getDeviceGetTopic();

    mqttClient.unsubscribe(setTopic.c_str());
    mqttClient.unsubscribe(getTopic.c_str());

    LOG_DEBUG("Unsubscribed from device topics");
}

void resubscribeAfterRename(const String& oldName) {
    // Unsubscribe from old topics
    String oldSetTopic = String(MQTT_TOPIC_PREFIX) + "/" + oldName + "/set";
    String oldGetTopic = String(MQTT_TOPIC_PREFIX) + "/" + oldName + "/get";

    mqttClient.unsubscribe(oldSetTopic.c_str());
    mqttClient.unsubscribe(oldGetTopic.c_str());

    // Publish offline on old availability topic
    String oldAvailTopic = String(MQTT_TOPIC_PREFIX) + "/" + oldName + "/availability";
    mqttClient.publish(oldAvailTopic.c_str(), "offline", true);

    // Subscribe to new topics
    subscribeToTopics();

    // Publish online on new availability topic
    publishAvailability(true);

    LOG_INFO("Resubscribed after rename from: " + oldName);
}

// ============================================================================
// Publishing Functions
// ============================================================================

bool publishMQTTMessage(const char* topic, const char* payload, bool retained) {
    if (!mqttClient.connected()) {
        LOG_WARN("MQTT not connected, cannot publish");
        return false;
    }

    bool success = mqttClient.publish(topic, payload, retained);

    if (success) {
        LOG_DEBUG("Published to " + String(topic));
    } else {
        LOG_ERROR("Failed to publish to " + String(topic));
    }

    return success;
}

void publishAvailability(bool online) {
    String topic = getAvailabilityTopic();
    const char* status = online ? "online" : "offline";
    publishMQTTMessage(topic.c_str(), status, true);
    LOG_INFO("Published availability: " + String(status));
}

void publishSensorData() {
    if (!mqttClient.connected()) {
        LOG_WARN("MQTT not connected, skipping sensor publish");
        return;
    }

    // Build sensor payload
    DynamicJsonDocument doc(1024);
    buildSensorPayload(doc);

    // Serialize to string
    String payload;
    serializeJson(doc, payload);

    // Publish to device topic
    String topic = getDeviceTopic();
    if (publishMQTTMessage(topic.c_str(), payload.c_str(), false)) {
        LOG_INFO("Published sensor data to " + topic);
    }
}

void publishBridgeInfo() {
    if (!mqttClient.connected()) {
        return;
    }

    DynamicJsonDocument doc(1024);
    buildBridgeInfoPayload(doc);

    String payload;
    serializeJson(doc, payload);

    String topic = getBridgeInfoTopic();
    publishMQTTMessage(topic.c_str(), payload.c_str(), true);
    LOG_DEBUG("Published bridge info");
}

void publishBridgeHealth() {
    if (!mqttClient.connected()) {
        return;
    }

    DynamicJsonDocument doc(512);
    buildBridgeHealthPayload(doc);

    String payload;
    serializeJson(doc, payload);

    String topic = getBridgeHealthTopic();
    publishMQTTMessage(topic.c_str(), payload.c_str(), false);
    LOG_DEBUG("Published bridge health");
}

void publishBridgeResponse(
    const char* command,
    const char* status,
    const JsonObject* data,
    const char* error,
    const char* transaction
) {
    if (!mqttClient.connected()) {
        return;
    }

    DynamicJsonDocument doc(512);
    doc["status"] = status;

    if (data != nullptr) {
        doc["data"] = *data;
    }

    if (error != nullptr) {
        doc["error"] = error;
    }

    if (transaction != nullptr) {
        doc["transaction"] = transaction;
    }

    String payload;
    serializeJson(doc, payload);

    String topic = String(MQTT_BRIDGE_PREFIX) + "/response/" + command;
    publishMQTTMessage(topic.c_str(), payload.c_str(), false);
    LOG_DEBUG("Published bridge response for: " + String(command));
}

// ============================================================================
// Payload Builders
// ============================================================================

void buildSensorPayload(JsonDocument& doc) {
    // Sensor readings
    float temp = readTemperature();
    float hum = readHumidity();
    float smoke = readSmoke();
    float lux = readLightLevel();

    // Add sensor values (null if invalid)
    if (!isnan(temp)) {
        doc["temperature"] = round(temp * 10) / 10.0;
    } else {
        doc["temperature"] = nullptr;
    }

    if (!isnan(hum)) {
        doc["humidity"] = round(hum * 10) / 10.0;
    } else {
        doc["humidity"] = nullptr;
    }

    // Soil moisture - keep null for this device type (future expansion)
    doc["soil_moisture"] = nullptr;

    // ENS160 readings (CO2, AQI, VOC)
    int co2 = readCO2();
    if (co2 > 0) {
        doc["co2"] = co2;
    } else {
        doc["co2"] = nullptr;
    }

    int aqi = readAirQualityIndex();
    if (aqi > 0 && aqi <= 5) {
        doc["air_quality"] = aqi;
    } else {
        doc["air_quality"] = nullptr;
    }

    int voc = readVOC();
    if (voc >= 0) {
        doc["voc"] = voc;
    } else {
        doc["voc"] = nullptr;
    }

    // MQ2 smoke/gas reading
    if (!isnan(smoke)) {
        doc["smoke"] = round(smoke * 10) / 10.0;
    } else {
        doc["smoke"] = nullptr;
    }

    // Pressure - keep null (future BME280 support)
    doc["pressure"] = nullptr;

    // TSL2591 light readings
    if (!isnan(lux)) {
        doc["lux"] = round(lux);
    } else {
        doc["lux"] = nullptr;
    }

    // Extended light readings from TSL2591
    uint16_t fullSpectrum = readFullSpectrum();
    uint16_t infrared = readInfrared();
    uint16_t visible = readVisible();

    if (fullSpectrum > 0) {
        doc["full_spectrum"] = fullSpectrum;
        doc["infrared"] = infrared;
        doc["visible"] = visible;
    } else {
        doc["full_spectrum"] = nullptr;
        doc["infrared"] = nullptr;
        doc["visible"] = nullptr;
    }

    // Power source and battery
    doc["power_source"] = getPowerSource();

    float batteryVoltage = readBatteryVoltage();
    if (batteryVoltage > 0) {
        doc["battery_percentage"] = round(getBatteryPercentage());
        doc["battery_voltage"] = round(batteryVoltage * 100) / 100.0;
    } else {
        doc["battery_percentage"] = nullptr;
        doc["battery_voltage"] = nullptr;
    }

    // Network info
    doc["rssi"] = WiFi.RSSI();
    doc["linkquality"] = map(constrain(WiFi.RSSI(), -100, -30), -100, -30, 0, 100);

    // Device info
    doc["uptime"] = millis() / 1000;
    doc["firmware_version"] = FW_VERSION;
    doc["device_type"] = DEVICE_TYPE;
    doc["mac_address"] = WiFi.macAddress();

    // Sensor status
    JsonObject sensorStatus = doc.createNestedObject("sensors_status");
    sensorStatus["ens160_aht21"] = areSensorsHealthy() ? "ok" : "error";
    sensorStatus["mq2"] = "ok";  // MQ2 is analog, always "ok" if reading
    sensorStatus["tsl2591"] = (fullSpectrum > 0) ? "ok" : "error";
}

void buildBridgeInfoPayload(JsonDocument& doc) {
    doc["version"] = FW_VERSION;
    doc["commit"] = FW_COMMIT;

    // Coordinator info
    JsonObject coordinator = doc.createNestedObject("coordinator");
    coordinator["type"] = DEVICE_TYPE;
    coordinator["mac"] = WiFi.macAddress();

    // Network info
    JsonObject network = doc.createNestedObject("network");
    network["wifi_ssid"] = stored_ssid;
    network["rssi"] = WiFi.RSSI();
    network["ip"] = WiFi.localIP().toString();

    // Config
    JsonObject config = doc.createNestedObject("config");
    config["polling_interval"] = polling_interval_ms;
    config["ble_pairing_enabled"] = ble_pairing_active;

    // Devices list (this device only for now)
    JsonArray devices = doc.createNestedArray("devices");
    JsonObject thisDevice = devices.createNestedObject();
    thisDevice["friendly_name"] = friendly_name;
    thisDevice["type"] = DEVICE_TYPE;

    JsonArray sensors = thisDevice.createNestedArray("sensors");
    sensors.add("ens160_aht21");
    sensors.add("mq2");
    sensors.add("tsl2591");
}

void buildBridgeHealthPayload(JsonDocument& doc) {
    doc["status"] = "ok";
    doc["uptime"] = millis() / 1000;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["wifi_connected"] = (WiFi.status() == WL_CONNECTED);
    doc["mqtt_connected"] = mqttClient.connected();
    doc["sensors_ok"] = areSensorsHealthy();
}

// ============================================================================
// Message Handler
// ============================================================================

void onMQTTMessage(char* topic, byte* payload, unsigned int length) {
    // Convert payload to string
    char message[length + 1];
    memcpy(message, payload, length);
    message[length] = '\0';

    String topicStr = String(topic);
    LOG_DEBUG("MQTT message received on: " + topicStr);

    // Route to appropriate handler based on topic
    if (topicStr == getDeviceSetTopic()) {
        handleDeviceSetCommand(message);
    }
    else if (topicStr == getDeviceGetTopic()) {
        handleDeviceGetCommand();
    }
    else if (topicStr == "sysgrow/bridge/request/permit_join") {
        handlePermitJoinCommand(message);
    }
    else if (topicStr == "sysgrow/bridge/request/restart") {
        handleRestartCommand(message);
    }
    else if (topicStr == "sysgrow/bridge/request/device/rename") {
        handleRenameCommand(message);
    }
    else if (topicStr == "sysgrow/bridge/request/device/remove") {
        handleRemoveCommand(message);
    }
    else if (topicStr == "sysgrow/bridge/request/device/ota_update/update") {
        handleOTAUpdateCommand(message);
    }
    else if (topicStr == "sysgrow/bridge/request/health_check") {
        handleHealthCheckCommand(message);
    }
    else {
        LOG_WARN("Unknown topic: " + topicStr);
    }
}

// ============================================================================
// Device Command Handlers
// ============================================================================

void handleDeviceSetCommand(const char* payload) {
    LOG_INFO("Processing /set command");

    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, payload);

    if (error) {
        LOG_ERROR("Failed to parse /set JSON: " + String(error.c_str()));
        return;
    }

    bool configChanged = false;

    // Handle polling_interval
    if (doc.containsKey("polling_interval")) {
        uint32_t newInterval = doc["polling_interval"].as<uint32_t>();
        if (newInterval >= 5000 && newInterval <= 3600000) {  // 5s to 1h
            polling_interval_ms = newInterval;
            configChanged = true;
            LOG_INFO("Polling interval set to: " + String(polling_interval_ms) + "ms");
        }
    }

    // Handle friendly_name change
    if (doc.containsKey("friendly_name")) {
        String newName = doc["friendly_name"].as<String>();
        if (newName.length() > 0 && newName.length() < EEPROM_FRIENDLY_NAME_SIZE) {
            String oldName = friendly_name;
            friendly_name = newName;
            newName.toCharArray(stored_friendly_name, EEPROM_FRIENDLY_NAME_SIZE);
            configChanged = true;

            // Resubscribe with new name
            resubscribeAfterRename(oldName);

            LOG_INFO("Friendly name changed to: " + friendly_name);
        }
    }

    // Handle temperature calibration
    if (doc.containsKey("temperature_calibration")) {
        calibration_data.temperature_offset = doc["temperature_calibration"].as<float>();
        configChanged = true;
        LOG_INFO("Temperature calibration set to: " + String(calibration_data.temperature_offset));
    }

    // Handle humidity calibration
    if (doc.containsKey("humidity_calibration")) {
        calibration_data.humidity_offset = doc["humidity_calibration"].as<float>();
        configChanged = true;
        LOG_INFO("Humidity calibration set to: " + String(calibration_data.humidity_offset));
    }

    // Handle restart command
    if (doc.containsKey("restart") && doc["restart"].as<bool>()) {
        LOG_INFO("Restart requested via /set command");
        saveConfiguration();
        delay(100);
        ESP.restart();
    }

    // Handle factory reset command
    if (doc.containsKey("factory_reset") && doc["factory_reset"].as<bool>()) {
        LOG_WARN("Factory reset requested via /set command");
        resetConfiguration();
        delay(100);
        ESP.restart();
    }

    // Save configuration if changed
    if (configChanged) {
        saveConfiguration();
        // Publish updated bridge info
        publishBridgeInfo();
    }
}

void handleDeviceGetCommand() {
    LOG_INFO("On-demand sensor read requested");
    publishSensorData();
}

// ============================================================================
// Bridge Command Handlers
// ============================================================================

void handlePermitJoinCommand(const char* payload) {
    LOG_INFO("Permit join command received");

    DynamicJsonDocument doc(256);
    DeserializationError error = deserializeJson(doc, payload);

    bool enable = true;
    int timeout = 30;  // Default 30 seconds

    if (!error) {
        if (doc.containsKey("value")) {
            enable = doc["value"].as<bool>();
        }
        if (doc.containsKey("time")) {
            timeout = doc["time"].as<int>();
            timeout = constrain(timeout, 0, 300);  // Max 5 minutes
        }
    }

    if (enable && timeout > 0) {
        // Start BLE pairing mode
        startBLEPairing();
        LOG_INFO("BLE pairing enabled for " + String(timeout) + " seconds");

        // Publish success response
        DynamicJsonDocument respDoc(256);
        JsonObject data = respDoc.createNestedObject("data");
        data["pairing_enabled"] = true;
        data["timeout"] = timeout;
        publishBridgeResponse("permit_join", "ok", &data);
    } else {
        // Stop BLE pairing mode
        stopBLEPairing();
        LOG_INFO("BLE pairing disabled");
        publishBridgeResponse("permit_join", "ok");
    }

    // Update bridge info
    publishBridgeInfo();
}

void handleRestartCommand(const char* payload) {
    LOG_INFO("Restart command received");

    DynamicJsonDocument doc(256);
    deserializeJson(doc, payload);

    // Check if this command is for this specific device
    if (doc.containsKey("id")) {
        String targetId = doc["id"].as<String>();
        if (targetId != friendly_name && targetId != WiFi.macAddress()) {
            LOG_DEBUG("Restart command not for this device");
            return;
        }
    }

    // Publish response before restarting
    publishBridgeResponse("restart", "ok");
    publishAvailability(false);

    delay(100);
    LOG_INFO("Restarting device...");
    ESP.restart();
}

void handleRenameCommand(const char* payload) {
    LOG_INFO("Rename command received");

    DynamicJsonDocument doc(256);
    DeserializationError error = deserializeJson(doc, payload);

    if (error) {
        LOG_ERROR("Failed to parse rename JSON");
        publishBridgeResponse("device/rename", "error", nullptr, "Invalid JSON payload");
        return;
    }

    if (!doc.containsKey("from") || !doc.containsKey("to")) {
        LOG_ERROR("Missing 'from' or 'to' in rename command");
        publishBridgeResponse("device/rename", "error", nullptr, "Missing 'from' or 'to' field");
        return;
    }

    String fromName = doc["from"].as<String>();
    String toName = doc["to"].as<String>();

    // Check if this rename is for this device
    if (fromName != friendly_name) {
        LOG_DEBUG("Rename command not for this device");
        return;
    }

    // Validate new name
    if (toName.length() == 0 || toName.length() >= EEPROM_FRIENDLY_NAME_SIZE) {
        publishBridgeResponse("device/rename", "error", nullptr, "Invalid new name length");
        return;
    }

    // Perform rename
    String oldName = friendly_name;
    friendly_name = toName;
    toName.toCharArray(stored_friendly_name, EEPROM_FRIENDLY_NAME_SIZE);
    saveConfiguration();

    // Resubscribe with new name
    resubscribeAfterRename(oldName);

    // Publish success response
    DynamicJsonDocument respDoc(256);
    JsonObject data = respDoc.createNestedObject("data");
    data["from"] = oldName;
    data["to"] = friendly_name;
    publishBridgeResponse("device/rename", "ok", &data);

    // Update bridge info
    publishBridgeInfo();

    LOG_INFO("Device renamed from '" + oldName + "' to '" + friendly_name + "'");
}

void handleRemoveCommand(const char* payload) {
    LOG_INFO("Remove/factory reset command received");

    DynamicJsonDocument doc(256);
    DeserializationError error = deserializeJson(doc, payload);

    if (error) {
        publishBridgeResponse("device/remove", "error", nullptr, "Invalid JSON payload");
        return;
    }

    // Check if this command is for this device
    String targetId = doc["id"] | "";
    if (targetId.length() > 0 && targetId != friendly_name && targetId != WiFi.macAddress()) {
        LOG_DEBUG("Remove command not for this device");
        return;
    }

    // Publish response before reset
    publishBridgeResponse("device/remove", "ok");
    publishAvailability(false);

    LOG_WARN("Performing factory reset...");
    delay(100);

    // Reset configuration
    resetConfiguration();

    // Restart into provisioning mode
    ESP.restart();
}

void handleOTAUpdateCommand(const char* payload) {
    LOG_INFO("OTA update command received");

    DynamicJsonDocument doc(512);
    DeserializationError error = deserializeJson(doc, payload);

    if (error) {
        publishBridgeResponse("device/ota_update/update", "error", nullptr, "Invalid JSON payload");
        return;
    }

    // Check if this command is for this device
    String targetId = doc["id"] | "";
    if (targetId.length() > 0 && targetId != friendly_name && targetId != WiFi.macAddress()) {
        LOG_DEBUG("OTA command not for this device");
        return;
    }

    // Get firmware URL
    if (!doc.containsKey("url")) {
        publishBridgeResponse("device/ota_update/update", "error", nullptr, "Missing firmware URL");
        return;
    }

    String firmwareUrl = doc["url"].as<String>();
    LOG_INFO("Starting OTA update from: " + firmwareUrl);

    // Publish acknowledgment
    DynamicJsonDocument respDoc(256);
    JsonObject data = respDoc.createNestedObject("data");
    data["status"] = "downloading";
    data["url"] = firmwareUrl;
    publishBridgeResponse("device/ota_update/update", "ok", &data);

    // Perform OTA update (this function should be implemented in ota_service.cpp)
    bool success = performOTAUpdate(firmwareUrl.c_str());

    if (!success) {
        publishBridgeResponse("device/ota_update/update", "error", nullptr, "OTA update failed");
    }
    // If successful, device will restart
}

void handleHealthCheckCommand(const char* payload) {
    LOG_DEBUG("Health check requested");
    publishBridgeHealth();
}
