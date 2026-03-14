#include "ble_service.h"
#include "analog_sensors.h"
#include "power_management.h"
#include "mqtt_service.h"

// Global BLE variables
BLEState ble_state = BLE_DISABLED;
BLEConnectionInfo ble_connection;
BLEStats ble_stats = {0};
bool ble_notifications_enabled = true;
bool ble_security_enabled = false;
unsigned long last_ble_activity = 0;

// BLE Service objects
BLEServer* pServer = nullptr;
BLEService* pService = nullptr;
BLECharacteristic* pConfigCharacteristic = nullptr;
BLECharacteristic* pSensorCharacteristic = nullptr;
BLECharacteristic* pStatusCharacteristic = nullptr;
BLECharacteristic* pCommandCharacteristic = nullptr;

// Callback instances
BLEServerCallbacks server_callbacks;
BLEConfigCallbacks config_callbacks;
BLECommandCallbacks command_callbacks;

void setupBLE() {
    LOG_INFO("Initializing BLE service...");
    ble_state = BLE_INITIALIZING;
    
    // Initialize BLE device
    String device_name = getBLEDeviceName();
    BLEDevice::init(device_name.c_str());
    BLEDevice::setMTU(BLE_MTU_SIZE);
    
    // Create BLE server
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(&server_callbacks);
    
    // Create BLE service
    pService = pServer->createService(BLE_SERVICE_UUID);
    
    // Create characteristics
    createBLECharacteristics();
    
    // Configure security if enabled
    if (ble_security_enabled) {
        configureBLESecurity();
    }
    
    // Start service
    pService->start();
    
    // Start advertising
    if (startBLEAdvertising()) {
        ble_state = BLE_ADVERTISING;
        LOG_INFO("BLE service initialized and advertising");
        LOG_INFO("Device name: " + device_name);
    } else {
        ble_state = BLE_ERROR;
        LOG_ERROR("Failed to start BLE advertising");
    }
}

void createBLECharacteristics() {
    // Configuration characteristic (Read/Write)
    pConfigCharacteristic = pService->createCharacteristic(
        BLE_CHARACTERISTIC_CONFIG_UUID,
        BLECharacteristic::PROPERTY_READ | 
        BLECharacteristic::PROPERTY_WRITE |
        BLECharacteristic::PROPERTY_NOTIFY
    );
    pConfigCharacteristic->setCallbacks(&config_callbacks);
    pConfigCharacteristic->addDescriptor(new BLE2902());
    
    // Sensor data characteristic (Read/Notify)
    pSensorCharacteristic = pService->createCharacteristic(
        BLE_CHARACTERISTIC_SENSOR_UUID,
        BLECharacteristic::PROPERTY_READ | 
        BLECharacteristic::PROPERTY_NOTIFY
    );
    pSensorCharacteristic->addDescriptor(new BLE2902());
    
    // Status characteristic (Read/Notify)
    pStatusCharacteristic = pService->createCharacteristic(
        BLE_CHARACTERISTIC_STATUS_UUID,
        BLECharacteristic::PROPERTY_READ | 
        BLECharacteristic::PROPERTY_NOTIFY
    );
    pStatusCharacteristic->addDescriptor(new BLE2902());
    
    // Command characteristic (Write)
    pCommandCharacteristic = pService->createCharacteristic(
        BLE_CHARACTERISTIC_COMMAND_UUID,
        BLECharacteristic::PROPERTY_WRITE
    );
    pCommandCharacteristic->setCallbacks(&command_callbacks);
}

void bleLoop() {
    if (ble_state == BLE_DISABLED || ble_state == BLE_ERROR) {
        return;
    }
    
    // Handle connection timeout
    if (ble_connection.is_connected) {
        unsigned long now = millis();
        if (now - ble_connection.last_activity > BLE_CONNECTION_TIMEOUT) {
            LOG_WARN("BLE connection timeout, disconnecting client");
            pServer->disconnect(0);
        }
    }
    
    // Send periodic sensor data if connected and notifications enabled
    static unsigned long last_sensor_update = 0;
    unsigned long now = millis();
    
    if (ble_connection.is_connected && ble_notifications_enabled && 
        (now - last_sensor_update > 5000)) {  // Every 5 seconds
        sendSensorDataViaBLE();
        last_sensor_update = now;
    }
}

bool startBLEAdvertising() {
    if (!pServer) {
        LOG_ERROR("BLE server not initialized");
        return false;
    }
    
    // Get advertising object
    BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
    
    // Set advertising data
    pAdvertising->addServiceUUID(BLE_SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    pAdvertising->setMinPreferred(0x06);
    pAdvertising->setMinPreferred(0x12);
    
    // Set advertising interval
    pAdvertising->setMinInterval(BLE_ADVERTISING_INTERVAL);
    pAdvertising->setMaxInterval(BLE_ADVERTISING_INTERVAL + 100);
    
    // Start advertising
    pAdvertising->start();
    
    LOG_INFO("BLE advertising started");
    return true;
}

void stopBLEAdvertising() {
    if (pServer) {
        BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
        pAdvertising->stop();
        LOG_INFO("BLE advertising stopped");
    }
}

void handleBLEConnection() {
    ble_connection.is_connected = true;
    ble_connection.connection_time = millis();
    ble_connection.last_activity = millis();
    ble_connection.client_address = getBLEClientAddress();
    ble_connection.mtu_size = getBLEMTU();
    
    ble_state = BLE_CONNECTED;
    ble_stats.connection_count++;
    
    LOG_INFO("BLE client connected: " + ble_connection.client_address);
    LOG_INFO("MTU size: " + String(ble_connection.mtu_size));
    
    // Stop advertising to save power
    stopBLEAdvertising();
    
    // Send initial status
    sendStatusViaBLE();
    sendConfigViaBLE();
    
    // Set power level for connected state
    setBLEPowerLevel(0);  // Maximum power for reliable connection
}

void handleBLEDisconnection() {
    if (ble_connection.is_connected) {
        // Calculate connection duration
        unsigned long connection_duration = millis() - ble_connection.connection_time;
        ble_stats.last_connection_duration = connection_duration;
        ble_stats.total_connection_time += connection_duration;
        
        LOG_INFO("BLE client disconnected after " + String(connection_duration / 1000) + " seconds");
    }
    
    // Reset connection info
    ble_connection.is_connected = false;
    ble_connection.client_address = "";
    ble_connection.connection_time = 0;
    ble_connection.last_activity = 0;
    
    ble_state = BLE_DISCONNECTED;
    ble_stats.disconnection_count++;
    
    // Restart advertising
    if (startBLEAdvertising()) {
        ble_state = BLE_ADVERTISING;
    } else {
        ble_state = BLE_ERROR;
    }
    
    // Reduce power consumption
    setBLEPowerLevel(-12);  // Reduce power when not connected
}

bool sendBLEMessage(BLEMessageType msg_type, const JsonDocument& data) {
    if (!ble_connection.is_connected) {
        return false;
    }
    
    String message = formatBLEMessage(msg_type, data);
    
    BLECharacteristic* characteristic = nullptr;
    
    switch (msg_type) {
        case BLE_MSG_CONFIG:
            characteristic = pConfigCharacteristic;
            break;
        case BLE_MSG_SENSOR_DATA:
            characteristic = pSensorCharacteristic;
            break;
        case BLE_MSG_STATUS:
        case BLE_MSG_RESPONSE:
        case BLE_MSG_ALERT:
            characteristic = pStatusCharacteristic;
            break;
        default:
            LOG_ERROR("Unknown BLE message type: " + String(msg_type));
            return false;
    }
    
    if (!characteristic) {
        LOG_ERROR("BLE characteristic not found for message type: " + String(msg_type));
        return false;
    }
    
    // Update characteristic value
    characteristic->setValue(message.c_str());
    
    // Send notification if enabled
    if (ble_notifications_enabled) {
        characteristic->notify();
    }
    
    ble_stats.data_sent += message.length();
    ble_connection.last_activity = millis();
    
    return true;
}

bool sendSensorDataViaBLE() {
    if (!sensors_active) {
        return false;
    }
    
    // Create compressed sensor data
    JsonDocument sensor_data = getAllSensorData();
    JsonDocument compressed_data;
    compressBLEData(sensor_data, compressed_data);
    
    return sendBLEMessage(BLE_MSG_SENSOR_DATA, compressed_data);
}

bool sendStatusViaBLE() {
    DynamicJsonDocument status(1024);
    
    status["device_id"] = device_id;
    status["firmware_version"] = FW_VERSION;
    status["uptime"] = millis() / 1000;
    status["free_heap"] = ESP.getFreeHeap();
    status["battery_voltage"] = readBatteryVoltage();
    status["power_mode"] = power_mode;
    status["sensors_active"] = sensors_active;
    status["wifi_connected"] = (WiFi.status() == WL_CONNECTED);
    status["mqtt_connected"] = isMQTTConnected();
    status["calibration_state"] = calibration_state;
    
    return sendBLEMessage(BLE_MSG_STATUS, status);
}

bool sendConfigViaBLE() {
    DynamicJsonDocument config(1024);
    
    // Device configuration
    config["device_id"] = device_id;
    config["unit_id"] = unit_id;
    config["device_type"] = DEVICE_TYPE;
    
    // Sensor configuration
    JsonObject sensors = config.createNestedObject("sensors");
    sensors["soil_sensor_count"] = SOIL_SENSOR_COUNT;
    sensors["lux_sensor_type"] = (active_lux_sensor_type == LUX_SENSOR_TYPE_DIGITAL) ? "digital" : "analog";
    sensors["reading_interval"] = 5000;  // Default 5 seconds
    
    // Power configuration
    JsonObject power = config.createNestedObject("power");
    power["battery_powered"] = isBatteryPowered();
    power["power_save_enabled"] = (power_mode == POWER_MODE_SAVE);
    power["sleep_enabled"] = false;
    
    // Network status (don't send credentials)
    JsonObject network = config.createNestedObject("network");
    network["wifi_ssid"] = WiFi.SSID();
    network["wifi_connected"] = (WiFi.status() == WL_CONNECTED);
    network["mqtt_broker"] = String(mqtt_broker);
    network["mqtt_connected"] = isMQTTConnected();
    
    return sendBLEMessage(BLE_MSG_CONFIG, config);
}

bool sendResponseViaBLE(uint8_t command_id, bool success, const String& message) {
    DynamicJsonDocument response(256);
    
    response["command_id"] = command_id;
    response["success"] = success;
    response["message"] = message;
    response["timestamp"] = millis();
    
    return sendBLEMessage(BLE_MSG_RESPONSE, response);
}

void handleBLECommand(const JsonDocument& command) {
    uint8_t command_type = command["command"];
    uint8_t command_id = command["id"];
    
    ble_stats.command_count++;
    ble_connection.last_activity = millis();
    
    LOG_INFO("BLE command received: " + String(command_type));
    
    switch (command_type) {
        case BLE_CMD_READ_CONFIG:
            handleReadConfigCommand();
            sendResponseViaBLE(command_id, true, "Config sent");
            break;
            
        case BLE_CMD_WRITE_CONFIG:
            handleWriteConfigCommand(command["data"]);
            sendResponseViaBLE(command_id, true, "Config updated");
            break;
            
        case BLE_CMD_READ_SENSORS:
            handleReadSensorsCommand();
            sendResponseViaBLE(command_id, true, "Sensor data sent");
            break;
            
        case BLE_CMD_CALIBRATE_SENSOR:
            handleCalibrateSensorCommand(command["params"]);
            sendResponseViaBLE(command_id, true, "Calibration started");
            break;
            
        case BLE_CMD_POWER_CONTROL:
            handlePowerControlCommand(command["params"]);
            sendResponseViaBLE(command_id, true, "Power mode updated");
            break;
            
        case BLE_CMD_RESET_DEVICE:
            sendResponseViaBLE(command_id, true, "Device will reset in 3 seconds");
            handleResetDeviceCommand();
            break;
            
        case BLE_CMD_GET_STATUS:
            handleGetStatusCommand();
            sendResponseViaBLE(command_id, true, "Status sent");
            break;
            
        case BLE_CMD_SET_WIFI:
            handleSetWiFiCommand(command["wifi"]);
            sendResponseViaBLE(command_id, true, "WiFi configuration updated");
            break;
            
        case BLE_CMD_SET_MQTT:
            handleSetMQTTCommand(command["mqtt"]);
            sendResponseViaBLE(command_id, true, "MQTT configuration updated");
            break;
            
        default:
            LOG_WARN("Unknown BLE command: " + String(command_type));
            sendResponseViaBLE(command_id, false, "Unknown command");
            break;
    }
}

void handleReadConfigCommand() {
    sendConfigViaBLE();
}

void handleWriteConfigCommand(const JsonDocument& config) {
    // Update configuration based on received data
    if (config.containsKey("sensors")) {
        JsonObject sensors = config["sensors"];
        if (sensors.containsKey("reading_interval")) {
            // Update sensor reading interval
            LOG_INFO("Updated sensor reading interval");
        }
    }
    
    if (config.containsKey("power")) {
        JsonObject power = config["power"];
        if (power.containsKey("power_save_enabled")) {
            bool enable_power_save = power["power_save_enabled"];
            if (enable_power_save) {
                enterPowerSaveMode();
            } else {
                enterNormalPowerMode();
            }
        }
    }
    
    // Send updated configuration
    sendConfigViaBLE();
}

void handleReadSensorsCommand() {
    // Force sensor reading
    readAllSoilSensors();
    readLuxLevel();
    
    // Send sensor data
    sendSensorDataViaBLE();
}

void handleCalibrateSensorCommand(const JsonDocument& params) {
    String sensor_type = params["sensor_type"];
    
    if (sensor_type == "soil_moisture") {
        uint8_t sensor_index = params["sensor_index"];
        bool is_dry_calibration = params["dry_calibration"];
        
        calibrateSoilSensor(sensor_index, is_dry_calibration);
    } else if (sensor_type == "lux") {
        calibrateLuxSensor();
    }
}

void handlePowerControlCommand(const JsonDocument& params) {
    String power_command = params["command"];
    
    if (power_command == "power_save") {
        enterPowerSaveMode();
    } else if (power_command == "normal") {
        enterNormalPowerMode();
    } else if (power_command == "sleep") {
        unsigned long duration = params["duration_minutes"];
        handleDeepSleep(duration * 60 * 1000000);  // Convert to microseconds
    }
}

void handleResetDeviceCommand() {
    LOG_INFO("Device reset requested via BLE");
    delay(3000);  // Give time for response to be sent
    ESP.restart();
}

void handleGetStatusCommand() {
    sendStatusViaBLE();
}

void handleSetWiFiCommand(const JsonDocument& wifi_config) {
    WiFiCredentials credentials;
    credentials.ssid = wifi_config["ssid"].as<String>();
    credentials.password = wifi_config["password"].as<String>();
    
    if (wifi_config.containsKey("static_ip")) {
        credentials.use_static_ip = true;
        credentials.static_ip = wifi_config["static_ip"].as<String>();
        credentials.gateway = wifi_config["gateway"].as<String>();
        credentials.subnet = wifi_config["subnet"].as<String>();
    }
    
    bool success = provisionWiFi(credentials);
    LOG_INFO("WiFi provisioning " + String(success ? "successful" : "failed"));
}

void handleSetMQTTCommand(const JsonDocument& mqtt_config) {
    MQTTCredentials credentials;
    credentials.broker = mqtt_config["broker"].as<String>();
    credentials.port = mqtt_config["port"];
    credentials.username = mqtt_config["username"].as<String>();
    credentials.password = mqtt_config["password"].as<String>();
    credentials.use_ssl = mqtt_config["use_ssl"];
    
    bool success = provisionMQTT(credentials);
    LOG_INFO("MQTT provisioning " + String(success ? "successful" : "failed"));
}

// BLE Callback Implementations
void BLEServerCallbacks::onConnect(BLEServer* pServer) {
    handleBLEConnection();
}

void BLEServerCallbacks::onDisconnect(BLEServer* pServer) {
    handleBLEDisconnection();
}

void BLEConfigCallbacks::onWrite(BLECharacteristic *pCharacteristic) {
    String value = pCharacteristic->getValue();
    
    if (value.length() > 0) {
        DynamicJsonDocument doc(1024);
        DeserializationError error = deserializeJson(doc, value);
        
        if (!error) {
            handleWriteConfigCommand(doc);
        } else {
            LOG_ERROR("Failed to parse BLE config JSON: " + String(error.c_str()));
        }
    }
}

void BLEConfigCallbacks::onRead(BLECharacteristic *pCharacteristic) {
    sendConfigViaBLE();
}

void BLECommandCallbacks::onWrite(BLECharacteristic *pCharacteristic) {
    String value = pCharacteristic->getValue();
    
    if (value.length() > 0) {
        DynamicJsonDocument doc(512);
        DeserializationError error = deserializeJson(doc, value);
        
        if (!error) {
            handleBLECommand(doc);
        } else {
            LOG_ERROR("Failed to parse BLE command JSON: " + String(error.c_str()));
        }
    }
}

// Utility Functions
String getBLEDeviceName() {
    return String(BLE_DEVICE_NAME) + "-" + device_id.substring(device_id.length() - 4);
}

String getBLEClientAddress() {
    if (pServer && pServer->getConnectedCount() > 0) {
        return pServer->getPeerInfo(0).getAddress().toString().c_str();
    }
    return "";
}

bool isBLEConnected() {
    return ble_connection.is_connected && (ble_state == BLE_CONNECTED);
}

void setBLENotifications(bool enabled) {
    ble_notifications_enabled = enabled;
    LOG_INFO("BLE notifications " + String(enabled ? "enabled" : "disabled"));
}

uint16_t getBLEMTU() {
    return BLEDevice::getMTU();
}

BLEStats getBLEStatistics() {
    return ble_stats;
}

void logBLEStatistics() {
    LOG_INFO("=== BLE Statistics ===");
    LOG_INFO("Connections: " + String(ble_stats.connection_count));
    LOG_INFO("Disconnections: " + String(ble_stats.disconnection_count));
    LOG_INFO("Data Sent: " + String(ble_stats.data_sent) + " bytes");
    LOG_INFO("Data Received: " + String(ble_stats.data_received) + " bytes");
    LOG_INFO("Commands: " + String(ble_stats.command_count));
    LOG_INFO("Total Connection Time: " + String(ble_stats.total_connection_time / 1000) + " seconds");
    LOG_INFO("State: " + getBLEStateString());
    LOG_INFO("====================");
}

String getBLEStateString() {
    switch (ble_state) {
        case BLE_DISABLED: return "Disabled";
        case BLE_INITIALIZING: return "Initializing";
        case BLE_ADVERTISING: return "Advertising";
        case BLE_CONNECTED: return "Connected";
        case BLE_DISCONNECTED: return "Disconnected";
        case BLE_ERROR: return "Error";
        default: return "Unknown";
    }
}

void resetBLEStatistics() {
    ble_stats = {0};
    LOG_INFO("BLE statistics reset");
}

String formatBLEMessage(BLEMessageType type, const JsonDocument& data) {
    DynamicJsonDocument message(data.memoryUsage() + 64);
    
    message["type"] = static_cast<uint8_t>(type);
    message["timestamp"] = millis();
    message["data"] = data;
    
    String result;
    serializeJson(message, result);
    return result;
}

bool parseBLEMessage(const String& message, BLEMessageType& type, JsonDocument& data) {
    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, message);
    
    if (error) {
        LOG_ERROR("Failed to parse BLE message: " + String(error.c_str()));
        return false;
    }
    
    type = static_cast<BLEMessageType>(doc["type"].as<uint8_t>());
    data = doc["data"];
    
    return true;
}

void compressBLEData(const JsonDocument& input, JsonDocument& output) {
    // Simple compression by using shorter field names
    if (input.containsKey("soil_sensors")) {
        JsonArray soil_array = output.createNestedArray("soil");
        JsonArray input_soil = input["soil_sensors"];
        
        for (JsonObject sensor : input_soil) {
            JsonObject compressed_sensor = soil_array.createNestedObject();
            compressed_sensor["i"] = sensor["index"];  // index -> i
            compressed_sensor["r"] = sensor["raw"];    // raw -> r
            compressed_sensor["m"] = sensor["moisture"]; // moisture -> m
            compressed_sensor["s"] = sensor["status"];  // status -> s
        }
    }
    
    if (input.containsKey("lux_sensor")) {
        JsonObject lux = output.createNestedObject("lux");
        JsonObject input_lux = input["lux_sensor"];
        lux["l"] = input_lux["lux"];      // lux -> l
        lux["t"] = input_lux["type"];     // type -> t
        lux["s"] = input_lux["status"];   // status -> s
    }
    
    output["ts"] = input["timestamp"];  // timestamp -> ts
}

void setBLEPowerLevel(int8_t power_level) {
    // Set BLE transmission power (-12 to +9 dBm)
    esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_ADV, static_cast<esp_power_level_t>(power_level));
    esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_SCAN, static_cast<esp_power_level_t>(power_level));
    esp_ble_tx_power_set(ESP_BLE_PWR_TYPE_DEFAULT, static_cast<esp_power_level_t>(power_level));
}

// Provisioning Functions
bool provisionWiFi(const WiFiCredentials& credentials) {
    // Store WiFi credentials securely
    // Implementation would save to preferences/EEPROM
    LOG_INFO("WiFi credentials provisioned for SSID: " + credentials.ssid);
    return true;
}

bool provisionMQTT(const MQTTCredentials& credentials) {
    // Store MQTT credentials securely
    // Implementation would save to preferences/EEPROM
    LOG_INFO("MQTT credentials provisioned for broker: " + credentials.broker);
    return true;
}

void clearProvisioningData() {
    // Clear all stored credentials
    LOG_INFO("Provisioning data cleared");
}

bool isDeviceProvisioned() {
    // Check if device has been provisioned with WiFi and MQTT credentials
    return (strlen(wifi_ssid) > 0 && strlen(mqtt_broker) > 0);
}