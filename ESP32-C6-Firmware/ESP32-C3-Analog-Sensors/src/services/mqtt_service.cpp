#include "mqtt_service.h"
#include "analog_sensors.h"
#include "power_management.h"

// Global MQTT variables
WiFiClientSecure secure_client;
PubSubClient mqtt_client(secure_client);
MQTTStatus mqtt_status = MQTT_DISCONNECTED;
MQTTStats mqtt_stats = {0};
String mqtt_client_id = "";
bool mqtt_logging_enabled = true;
bool mqtt_security_enabled = true;
unsigned long last_mqtt_ping = 0;
unsigned long last_reconnect_attempt = 0;

// Message queue
std::vector<MQTTMessage> message_queue;
const uint16_t MAX_QUEUE_SIZE = 50;

// TLS certificate storage
const char* root_ca_cert = nullptr;
const char* client_cert = nullptr;
const char* client_key = nullptr;

void setupMQTT() {
    LOG_INFO("Initializing MQTT service...");
    
    // Generate client ID if not set
    if (mqtt_client_id.isEmpty()) {
        mqtt_client_id = device_id + "-" + String(random(1000, 9999));
    }
    
    // Configure MQTT client
    mqtt_client.setServer(mqtt_broker, MQTT_PORT);
    mqtt_client.setCallback(handleIncomingMessage);
    mqtt_client.setBufferSize(MQTT_BUFFER_SIZE);
    mqtt_client.setKeepAlive(MQTT_KEEPALIVE);
    
    // Configure security if enabled
    if (mqtt_security_enabled) {
        configureMQTTSecurity(true);
    }
    
    // Initialize statistics
    mqtt_stats.connection_attempts = 0;
    mqtt_stats.last_connection_time = 0;
    
    LOG_INFO("MQTT service initialized");
    LOG_INFO("Client ID: " + mqtt_client_id);
    LOG_INFO("Broker: " + String(mqtt_broker) + ":" + String(MQTT_PORT));
    LOG_INFO("Security: " + String(mqtt_security_enabled ? "Enabled" : "Disabled"));
}

void mqttLoop() {
    if (!mqtt_client.connected()) {
        if (mqtt_status == MQTT_CONNECTED) {
            LOG_WARN("MQTT connection lost");
            mqtt_status = MQTT_DISCONNECTED;
            mqtt_stats.disconnections++;
        }
        
        // Attempt reconnection
        unsigned long now = millis();
        if (now - last_reconnect_attempt >= MQTT_RETRY_INTERVAL) {
            reconnectMQTT();
            last_reconnect_attempt = now;
        }
    } else {
        mqtt_client.loop();
        
        // Process message queue
        processMessageQueue();
        
        // Send periodic ping
        unsigned long now = millis();
        if (now - last_mqtt_ping >= (MQTT_KEEPALIVE * 1000 / 2)) {
            mqtt_client.loop();  // This includes ping
            last_mqtt_ping = now;
        }
    }
}

bool connectMQTT() {
    if (strlen(mqtt_broker) == 0) {
        LOG_ERROR("MQTT broker not configured");
        return false;
    }
    
    LOG_INFO("Connecting to MQTT broker: " + String(mqtt_broker));
    mqtt_status = MQTT_CONNECTING;
    mqtt_stats.connection_attempts++;
    
    // Prepare connection parameters
    String will_topic = getStatusTopic() + "/online";
    String will_message = "false";
    
    bool connected = false;
    
    if (strlen(mqtt_username) > 0 && strlen(mqtt_password) > 0) {
        // Connect with credentials
        connected = mqtt_client.connect(
            mqtt_client_id.c_str(),
            mqtt_username,
            mqtt_password,
            will_topic.c_str(),
            QOS_1,
            true,
            will_message.c_str()
        );
    } else {
        // Connect without credentials
        connected = mqtt_client.connect(
            mqtt_client_id.c_str(),
            will_topic.c_str(),
            QOS_1,
            true,
            will_message.c_str()
        );
    }
    
    if (connected) {
        LOG_INFO("MQTT connected successfully");
        mqtt_status = MQTT_CONNECTED;
        mqtt_stats.successful_connections++;
        mqtt_stats.last_connection_time = millis();
        
        // Subscribe to device topics
        subscribeToDeviceTopics();
        
        // Publish online status
        publishMQTTMessage((will_topic).c_str(), "true", QOS_1, true);
        
        // Publish device registration
        publishDeviceStatus();
        
        return true;
    } else {
        int error = mqtt_client.state();
        mqtt_status = (error == -2) ? MQTT_AUTH_FAILED : MQTT_CONNECTION_FAILED;
        mqtt_stats.failed_connections++;
        
        LOG_ERROR("MQTT connection failed: " + getMQTTErrorString(error));
        return false;
    }
}

void reconnectMQTT() {
    if (mqtt_status == MQTT_CONNECTING) {
        return;  // Already attempting connection
    }
    
    LOG_INFO("Attempting MQTT reconnection...");
    
    if (connectMQTT()) {
        LOG_INFO("MQTT reconnection successful");
    } else {
        LOG_WARN("MQTT reconnection failed, will retry in " + String(MQTT_RETRY_INTERVAL / 1000) + " seconds");
    }
}

bool publishMQTTMessage(const char* topic, const char* payload, MQTTQoS qos, bool retain) {
    if (!mqtt_client.connected()) {
        // Queue message for later sending
        return queueMessage(String(topic), String(payload), qos, retain, PRIORITY_NORMAL);
    }
    
    bool success = mqtt_client.publish(topic, payload, retain);
    
    if (success) {
        mqtt_stats.messages_sent++;
        mqtt_stats.last_message_time = millis();
        
        if (mqtt_logging_enabled) {
            LOG_DEBUG("MQTT Published: " + String(topic) + " -> " + String(payload).substring(0, 100));
        }
    } else {
        LOG_WARN("Failed to publish MQTT message to: " + String(topic));
        // Queue for retry
        queueMessage(String(topic), String(payload), qos, retain, PRIORITY_HIGH);
    }
    
    return success;
}

bool publishSensorData() {
    if (!sensors_active) {
        return false;
    }
    
    JsonDocument sensor_data = getAllSensorData();
    String payload;
    serializeJson(sensor_data, payload);
    
    String topic = getSensorTopic();
    return publishMQTTMessage(topic.c_str(), payload.c_str(), QOS_1, false);
}

bool publishHeartbeat() {
    DynamicJsonDocument doc(512);
    
    doc["device_id"] = device_id;
    doc["timestamp"] = millis();
    doc["uptime"] = millis() / 1000;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["wifi_rssi"] = WiFi.RSSI();
    doc["battery_voltage"] = readBatteryVoltage();
    doc["power_mode"] = power_mode;
    doc["connection_mode"] = current_mode;
    
    String payload;
    serializeJson(doc, payload);
    
    String topic = getStatusTopic() + "/heartbeat";
    return publishMQTTMessage(topic.c_str(), payload.c_str(), QOS_0, false);
}

bool publishDeviceStatus() {
    DynamicJsonDocument doc(1024);
    
    doc["device_id"] = device_id;
    doc["device_type"] = DEVICE_TYPE;
    doc["firmware_version"] = FW_VERSION;
    doc["timestamp"] = millis();
    doc["status"] = "online";
    
    // Network information
    JsonObject network = doc.createNestedObject("network");
    network["wifi_ssid"] = WiFi.SSID();
    network["wifi_rssi"] = WiFi.RSSI();
    network["ip_address"] = WiFi.localIP().toString();
    network["mac_address"] = WiFi.macAddress();
    
    // Power information
    JsonObject power = doc.createNestedObject("power");
    power["battery_voltage"] = readBatteryVoltage();
    power["battery_percentage"] = calculateBatteryPercentage(readBatteryVoltage());
    power["power_mode"] = power_mode;
    power["is_battery_powered"] = isBatteryPowered();
    
    // System information
    JsonObject system = doc.createNestedObject("system");
    system["free_heap"] = ESP.getFreeHeap();
    system["chip_temperature"] = temperatureRead();
    system["uptime"] = millis() / 1000;
    system["reset_reason"] = ESP.getResetReason();
    
    // Sensor information
    JsonObject sensors = doc.createNestedObject("sensors");
    sensors["soil_sensor_count"] = SOIL_SENSOR_COUNT;
    sensors["lux_sensor_type"] = (active_lux_sensor_type == LUX_SENSOR_TYPE_DIGITAL) ? "digital" : "analog";
    sensors["sensors_active"] = sensors_active;
    sensors["calibration_state"] = calibration_state;
    
    String payload;
    serializeJson(doc, payload);
    
    String topic = getStatusTopic();
    return publishMQTTMessage(topic.c_str(), payload.c_str(), QOS_1, true);
}

bool publishAlert(const String& alert_type, const String& message, MessagePriority priority) {
    DynamicJsonDocument doc(512);
    
    doc["device_id"] = device_id;
    doc["alert_type"] = alert_type;
    doc["message"] = message;
    doc["timestamp"] = millis();
    doc["priority"] = priority;
    doc["battery_voltage"] = readBatteryVoltage();
    
    String payload;
    serializeJson(doc, payload);
    
    String topic = getAlertTopic();
    MQTTQoS qos = (priority >= PRIORITY_HIGH) ? QOS_1 : QOS_0;
    
    return publishMQTTMessage(topic.c_str(), payload.c_str(), qos, false);
}

void subscribeToDeviceTopics() {
    String base_topic = getDeviceTopicPrefix();
    
    // Subscribe to command topics
    subscribeToTopic((base_topic + "/config").c_str());
    subscribeToTopic((base_topic + "/command").c_str());
    subscribeToTopic((base_topic + "/calibrate").c_str());
    subscribeToTopic((base_topic + "/power").c_str());
    subscribeToTopic((base_topic + "/ota").c_str());
    
    LOG_INFO("Subscribed to device command topics");
}

void handleIncomingMessage(char* topic, byte* payload, unsigned int length) {
    // Convert payload to string
    String message;
    for (unsigned int i = 0; i < length; i++) {
        message += (char)payload[i];
    }
    
    String topic_str = String(topic);
    
    mqtt_stats.messages_received++;
    
    if (mqtt_logging_enabled) {
        LOG_INFO("MQTT Received: " + topic_str + " -> " + message);
    }
    
    // Parse JSON payload
    DynamicJsonDocument doc(1024);
    DeserializationError error = deserializeJson(doc, message);
    
    if (error) {
        LOG_ERROR("Failed to parse MQTT message JSON: " + String(error.c_str()));
        return;
    }
    
    // Route message based on topic
    if (topic_str.endsWith("/config")) {
        handleConfigCommand(doc);
    } else if (topic_str.endsWith("/command")) {
        handleSensorCommand(doc);
    } else if (topic_str.endsWith("/calibrate")) {
        handleCalibrationCommand(doc);
    } else if (topic_str.endsWith("/power")) {
        handlePowerCommand(doc);
    } else if (topic_str.endsWith("/ota")) {
        handleOTACommand(doc);
    } else {
        LOG_WARN("Unhandled MQTT topic: " + topic_str);
    }
}

bool queueMessage(const String& topic, const String& payload, MQTTQoS qos, bool retain, MessagePriority priority) {
    if (message_queue.size() >= MAX_QUEUE_SIZE) {
        LOG_WARN("MQTT message queue full, dropping oldest message");
        message_queue.erase(message_queue.begin());
    }
    
    MQTTMessage msg;
    msg.topic = topic;
    msg.payload = payload;
    msg.qos = qos;
    msg.retain = retain;
    msg.priority = priority;
    msg.timestamp = millis();
    msg.retry_count = 0;
    
    // Insert based on priority
    auto insert_pos = message_queue.end();
    for (auto it = message_queue.begin(); it != message_queue.end(); ++it) {
        if (it->priority < priority) {
            insert_pos = it;
            break;
        }
    }
    
    message_queue.insert(insert_pos, msg);
    return true;
}

void processMessageQueue() {
    if (message_queue.empty() || !mqtt_client.connected()) {
        return;
    }
    
    // Process one message per loop iteration to avoid blocking
    MQTTMessage& msg = message_queue.front();
    
    if (mqtt_client.publish(msg.topic.c_str(), msg.payload.c_str(), msg.retain)) {
        mqtt_stats.messages_sent++;
        message_queue.erase(message_queue.begin());
        
        if (mqtt_logging_enabled) {
            LOG_DEBUG("Queued MQTT message sent: " + msg.topic);
        }
    } else {
        msg.retry_count++;
        if (msg.retry_count >= 3) {
            LOG_ERROR("Failed to send queued message after 3 retries: " + msg.topic);
            message_queue.erase(message_queue.begin());
        }
    }
}

String getDeviceTopicPrefix() {
    return MQTT_DEVICE_TOPIC_PREFIX + device_id;
}

String getSensorTopic() {
    return MQTT_TOPIC_PREFIX + unit_id + "/sensors/" + device_id;
}

String getStatusTopic() {
    return getDeviceTopicPrefix() + "/status";
}

String getConfigTopic() {
    return getDeviceTopicPrefix() + "/config";
}

String getCommandTopic() {
    return getDeviceTopicPrefix() + "/command";
}

String getAlertTopic() {
    return MQTT_TOPIC_PREFIX + unit_id + "/alerts";
}

void handleConfigCommand(const JsonDocument& command) {
    String command_type = command["command"];
    
    if (command_type == "update_config") {
        // Handle configuration updates
        if (command.containsKey("sensor_interval")) {
            // Update sensor reading interval
            LOG_INFO("Updating sensor interval to: " + String(command["sensor_interval"].as<int>()));
        }
        
        if (command.containsKey("power_save")) {
            bool enable_power_save = command["power_save"];
            if (enable_power_save) {
                enterPowerSaveMode();
            } else {
                enterNormalPowerMode();
            }
        }
    }
}

void handleCalibrationCommand(const JsonDocument& command) {
    String calibration_type = command["type"];
    
    if (calibration_type == "soil_moisture") {
        uint8_t sensor_index = command["sensor_index"];
        
        if (command["action"] == "start_dry") {
            LOG_INFO("Starting dry calibration for soil sensor " + String(sensor_index + 1));
            calibrateSoilSensor(sensor_index, true);
        } else if (command["action"] == "start_wet") {
            LOG_INFO("Starting wet calibration for soil sensor " + String(sensor_index + 1));
            calibrateSoilSensor(sensor_index, false);
        }
    } else if (calibration_type == "lux") {
        if (command["action"] == "start") {
            LOG_INFO("Starting lux sensor calibration");
            calibrateLuxSensor();
        }
    }
}

void handlePowerCommand(const JsonDocument& command) {
    String power_command = command["command"];
    
    if (power_command == "sleep") {
        unsigned long duration = command["duration_minutes"];
        LOG_INFO("Entering sleep mode for " + String(duration) + " minutes");
        handleDeepSleep(duration * 60 * 1000000);  // Convert to microseconds
    } else if (power_command == "power_save") {
        enterPowerSaveMode();
    } else if (power_command == "normal_power") {
        enterNormalPowerMode();
    }
}

void handleSensorCommand(const JsonDocument& command) {
    String sensor_command = command["command"];
    
    if (sensor_command == "read_all") {
        LOG_INFO("Reading all sensors on command");
        readAllSoilSensors();
        readLuxLevel();
        publishSensorData();
    } else if (sensor_command == "enable_sensors") {
        sensors_active = true;
        powerControlSensors(true);
        LOG_INFO("Sensors enabled");
    } else if (sensor_command == "disable_sensors") {
        sensors_active = false;
        powerControlSensors(false);
        LOG_INFO("Sensors disabled");
    }
}

void handleOTACommand(const JsonDocument& command) {
    String ota_command = command["command"];
    
    if (ota_command == "update") {
        String firmware_url = command["url"];
        LOG_INFO("OTA update requested from: " + firmware_url);
        // Trigger OTA update
        // performOTA(firmware_url);
    }
}

String getMQTTErrorString(int error_code) {
    switch (error_code) {
        case -4: return "Connection timeout";
        case -3: return "Connection lost";
        case -2: return "Connect failed";
        case -1: return "Disconnected";
        case 0: return "Connected";
        case 1: return "Bad protocol version";
        case 2: return "Bad client ID";
        case 3: return "Unavailable";
        case 4: return "Bad credentials";
        case 5: return "Unauthorized";
        default: return "Unknown error (" + String(error_code) + ")";
    }
}

MQTTStats getMQTTStatistics() {
    return mqtt_stats;
}

void logMQTTStatistics() {
    LOG_INFO("=== MQTT Statistics ===");
    LOG_INFO("Messages Sent: " + String(mqtt_stats.messages_sent));
    LOG_INFO("Messages Received: " + String(mqtt_stats.messages_received));
    LOG_INFO("Connection Attempts: " + String(mqtt_stats.connection_attempts));
    LOG_INFO("Successful Connections: " + String(mqtt_stats.successful_connections));
    LOG_INFO("Failed Connections: " + String(mqtt_stats.failed_connections));
    LOG_INFO("Queue Size: " + String(message_queue.size()));
    LOG_INFO("Status: " + getMQTTStatusString());
    LOG_INFO("=====================");
}

String getMQTTStatusString() {
    switch (mqtt_status) {
        case MQTT_DISCONNECTED: return "Disconnected";
        case MQTT_CONNECTING: return "Connecting";
        case MQTT_CONNECTED: return "Connected";
        case MQTT_CONNECTION_FAILED: return "Connection Failed";
        case MQTT_AUTH_FAILED: return "Authentication Failed";
        case MQTT_TIMEOUT: return "Timeout";
        default: return "Unknown";
    }
}

bool isMQTTConnected() {
    return mqtt_client.connected() && (mqtt_status == MQTT_CONNECTED);
}