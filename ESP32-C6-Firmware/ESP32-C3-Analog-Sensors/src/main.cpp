#include "config.h"
#include "analog_sensors.h"
#include "mqtt_service.h"
#include "ble_service.h"
#include "power_management.h"
#include "web_server.h"
#include "ota_service.h"

// Global variables initialization
String device_id = "";
String unit_id = "";
ConnectionMode current_mode = WIFI_MQTT;
PowerMode power_mode = NORMAL_POWER;
bool is_provisioned = false;
bool sensors_active = false;
CalibrationState calibration_state = NOT_CALIBRATED;

// Timing variables
unsigned long last_sensor_read = 0;
unsigned long last_mqtt_attempt = 0;
unsigned long last_ota_check = 0;
unsigned long last_heartbeat = 0;
unsigned long system_start_time = 0;

// Configuration storage
char stored_ssid[64] = "";
char stored_password[64] = "";
char mqtt_broker[128] = "";
char mqtt_username[64] = "";
char mqtt_password[64] = "";
char device_name[32] = "";

// Sensor calibration data
SoilCalibration soil_calibration[SOIL_SENSOR_COUNT];
LuxCalibration lux_calibration;
uint8_t active_lux_sensor_type = LUX_SENSOR_TYPE_ANALOG;

void setup() {
    Serial.begin(115200);
    delay(2000);  // Allow serial to stabilize
    
    system_start_time = millis();
    
    LOG_INFO("=== SYSGrow ESP32-C3 Analog Sensors Module ===");
    LOG_INFO("Firmware Version: " + String(FW_VERSION));
    LOG_INFO("Device Type: " + String(DEVICE_TYPE));
    LOG_INFO("Starting initialization...");
    
    // Initialize core systems
    setupDevice();
    
    // Load configuration and calibration data
    loadConfiguration();
    loadCalibrationData();
    
    // Generate or load device ID
    if (device_id.isEmpty()) {
        device_id = generateDeviceId();
        LOG_INFO("Generated new device ID: " + device_id);
        saveConfiguration();
    }
    
    // Initialize hardware
    setupPowerManagement();
    setupAnalogSensors();
    
    // Check power status and adjust operation mode
    updateBatteryStatus();
    if (isBatteryCritical()) {
        LOG_ERROR("Critical battery level detected!");
        enterEmergencyMode();
        handleDeepSleep(1800e6);  // 30 minutes emergency sleep
        return;
    }
    
    // Status indication
    blinkStatusLED(3, 300);  // 3 blinks to show startup
    
    // Check if device is provisioned
    if (!isConfigured()) {
        LOG_WARN("Device not configured, starting provisioning mode");
        current_mode = BLE_ONLY;
        setupBLE();
        setupWebServer();
        startAPMode();
        return;
    }
    
    // Attempt WiFi connection
    LOG_INFO("Attempting WiFi connection...");
    if (connectWiFi()) {
        LOG_INFO("WiFi connected successfully");
        LOG_INFO("IP Address: " + WiFi.localIP().toString());
        LOG_INFO("Signal Strength: " + String(WiFi.RSSI()) + " dBm");
        
        current_mode = WIFI_MQTT;
        
        // Initialize network services
        setupMQTT();
        setupOTA();
        setupWebServer();
        
        // Register device with the system
        registerDevice();
        publishDeviceStatus();
        
        // Perform initial sensor readings
        if (sensors_active) {
            readAllSoilSensors();
            readLuxLevel();
            publishSensorData();
        }
        
        blinkStatusLED(5, 100);  // 5 quick blinks for successful connection
        
    } else {
        LOG_ERROR("WiFi connection failed");
        handleConnectionLoss();
    }
    
    // Initialize mDNS for local discovery
    if (MDNS.begin(device_id.c_str())) {
        MDNS.addService("http", "tcp", WEB_SERVER_PORT);
        MDNS.addService("sysgrow", "tcp", WEB_SERVER_PORT);
        LOG_INFO("mDNS responder started: " + device_id + ".local");
    } else {
        LOG_ERROR("Failed to start mDNS responder");
    }
    
    LOG_INFO("Setup completed successfully");
    LOG_INFO("Operation Mode: " + String(current_mode));
    LOG_INFO("Power Mode: " + String(power_mode));
    LOG_INFO("Sensors Active: " + String(sensors_active ? "Yes" : "No"));
    
    logSystemStatus();
}

void loop() {
    unsigned long now = millis();
    
    // Main loop based on current mode
    switch (current_mode) {
        case WIFI_MQTT:
            handleWiFiMQTTMode(now);
            break;
            
        case BLE_ONLY:
            handleBLEMode(now);
            break;
            
        case AP_MODE:
            handleAPMode(now);
            break;
            
        case OFFLINE:
            handleOfflineMode(now);
            break;
    }
    
    // Common loop functions
    powerManagementLoop();
    
    // Watchdog and yield
    yield();
    delay(10);  // Small delay to prevent WDT reset
}

void handleWiFiMQTTMode(unsigned long now) {
    // MQTT maintenance
    mqttLoop();
    
    // Periodic sensor readings
    if (sensors_active && (now - last_sensor_read >= SENSOR_READ_INTERVAL)) {
        LOG_DEBUG("Reading sensors...");
        readAllSoilSensors();
        readLuxLevel();
        
        if (validateAllSensorReadings()) {
            publishSensorData();
            updateSensorStats();
        } else {
            LOG_WARN("Sensor validation failed, skipping publish");
        }
        
        last_sensor_read = now;
    }
    
    // Heartbeat
    if (now - last_heartbeat >= 300000) {  // 5 minutes
        publishHeartbeat();
        publishDeviceStatus();
        last_heartbeat = now;
    }
    
    // OTA updates check
    if (now - last_ota_check >= OTA_CHECK_INTERVAL) {
        otaLoop();
        last_ota_check = now;
    }
    
    // Web server
    webServerLoop();
    
    // Check WiFi connection
    if (WiFi.status() != WL_CONNECTED) {
        LOG_WARN("WiFi connection lost");
        handleConnectionLoss();
    }
    
    // Calibration mode handling
    if (isInCalibrationMode()) {
        calibrationLoop();
    }
}

void handleBLEMode(unsigned long now) {
    bleLoop();
    webServerLoop();
    
    // Still read sensors for local access
    if (sensors_active && (now - last_sensor_read >= SENSOR_READ_INTERVAL)) {
        readAllSoilSensors();
        readLuxLevel();
        last_sensor_read = now;
    }
    
    // Periodically try to connect to WiFi
    if (now - last_mqtt_attempt >= 60000) {  // Try every minute
        if (strlen(stored_ssid) > 0) {
            LOG_INFO("Attempting WiFi reconnection from BLE mode");
            if (connectWiFi()) {
                current_mode = WIFI_MQTT;
                setupMQTT();
                registerDevice();
            }
        }
        last_mqtt_attempt = now;
    }
}

void handleAPMode(unsigned long now) {
    webServerLoop();
    
    // Check if configuration was received
    if (isConfigured()) {
        LOG_INFO("Configuration received, restarting...");
        delay(1000);
        ESP.restart();
    }
    
    // Timeout AP mode after 5 minutes
    if (now - system_start_time > AP_TIMEOUT) {
        LOG_WARN("AP mode timeout, entering BLE mode");
        current_mode = BLE_ONLY;
        setupBLE();
    }
}

void handleOfflineMode(unsigned long now) {
    // Minimal operation mode
    if (now - last_sensor_read >= SENSOR_READ_INTERVAL * 5) {  // Read less frequently
        readAllSoilSensors();
        readLuxLevel();
        last_sensor_read = now;
    }
    
    // Check if we can recover connectivity
    if (now - last_mqtt_attempt >= 300000) {  // Try every 5 minutes
        if (readBatteryVoltage() > POWER_SAVE_VOLTAGE) {
            LOG_INFO("Battery recovered, attempting reconnection");
            if (connectWiFi()) {
                current_mode = WIFI_MQTT;
                setupMQTT();
                registerDevice();
            }
        }
        last_mqtt_attempt = now;
    }
}

void setupDevice() {
    LOG_INFO("Initializing device hardware...");
    
    // Initialize EEPROM
    EEPROM.begin(EEPROM_SIZE);
    
    // Configure GPIO pins
    pinMode(STATUS_LED_PIN, OUTPUT);
    pinMode(SENSOR_POWER_PIN, OUTPUT);
    pinMode(BUZZER_PIN, OUTPUT);
    
    // Initialize status LED (off)
    digitalWrite(STATUS_LED_PIN, LOW);
    
    // Power on sensors
    digitalWrite(SENSOR_POWER_PIN, HIGH);
    delay(100);  // Allow sensors to stabilize
    
    // Configure ADC
    analogReadResolution(ADC_RESOLUTION);
    analogSetAttenuation(ADC_11db);  // Full range voltage input
    
    LOG_INFO("Device hardware initialized");
}

void registerDevice() {
    if (current_mode != WIFI_MQTT) return;
    
    LOG_INFO("Registering device with system...");
    
    String registration_topic = MQTT_TOPIC_PREFIX + unit_id + "/register_device";
    DynamicJsonDocument doc(1024);
    
    doc["device_id"] = device_id;
    doc["device_type"] = DEVICE_TYPE;
    doc["device_model"] = DEVICE_MODEL;
    doc["firmware_version"] = FW_VERSION;
    doc["unit_id"] = unit_id;
    
    // Capabilities
    JsonArray capabilities = doc.createNestedArray("capabilities");
    capabilities.add("soil_moisture_multi");
    capabilities.add("light_level");
    capabilities.add("battery_monitoring");
    capabilities.add("power_management");
    capabilities.add("calibration");
    
    // Sensor information
    JsonObject sensors = doc.createNestedObject("sensors");
    sensors["soil_moisture_count"] = SOIL_SENSOR_COUNT;
    sensors["lux_sensor_type"] = (active_lux_sensor_type == LUX_SENSOR_TYPE_DIGITAL) ? "digital" : "analog";
    
    // Device status
    JsonObject status = doc.createNestedObject("status");
    status["battery_voltage"] = readBatteryVoltage();
    status["battery_percentage"] = calculateBatteryPercentage(readBatteryVoltage());
    status["rssi"] = WiFi.RSSI();
    status["uptime"] = millis() / 1000;
    status["power_mode"] = power_mode;
    status["sensors_active"] = sensors_active;
    status["calibration_state"] = calibration_state;
    
    String payload;
    serializeJson(doc, payload);
    
    if (publishMQTTMessage(registration_topic.c_str(), payload.c_str())) {
        LOG_INFO("Device registered successfully");
        blinkStatusLED(2, 500);
    } else {
        LOG_ERROR("Failed to register device");
    }
}

void handleConnectionLoss() {
    LOG_WARN("Handling connection loss...");
    
    // Check battery level
    if (isBatteryLow()) {
        LOG_WARN("Low battery, entering offline mode");
        current_mode = OFFLINE;
        enterPowerSaveMode();
        return;
    }
    
    // Try to reconnect
    int retry_count = 0;
    while (retry_count < MAX_WIFI_RETRIES) {
        LOG_INFO("Reconnection attempt " + String(retry_count + 1));
        
        if (connectWiFi()) {
            LOG_INFO("Reconnection successful");
            current_mode = WIFI_MQTT;
            setupMQTT();
            registerDevice();
            return;
        }
        
        retry_count++;
        delay(WIFI_RETRY_INTERVAL);
    }
    
    // Fall back to BLE mode
    LOG_WARN("WiFi reconnection failed, switching to BLE mode");
    current_mode = BLE_ONLY;
    setupBLE();
}

String generateDeviceId() {
    String mac = WiFi.macAddress();
    mac.replace(":", "");
    mac.toLowerCase();
    return "esp32c3-analog-" + mac.substring(6);
}

void blinkStatusLED(int times, int duration) {
    for (int i = 0; i < times; i++) {
        digitalWrite(STATUS_LED_PIN, HIGH);
        delay(duration);
        digitalWrite(STATUS_LED_PIN, LOW);
        if (i < times - 1) {
            delay(duration);
        }
    }
}

void playBuzzer(int frequency, int duration) {
    // Simple tone generation for buzzer alerts
    tone(BUZZER_PIN, frequency, duration);
}

void logSystemStatus() {
    LOG_INFO("=== System Status ===");
    LOG_INFO("Device ID: " + device_id);
    LOG_INFO("Unit ID: " + unit_id);
    LOG_INFO("WiFi SSID: " + String(stored_ssid));
    LOG_INFO("MQTT Broker: " + String(mqtt_broker));
    LOG_INFO("Free Heap: " + String(ESP.getFreeHeap()) + " bytes");
    LOG_INFO("Chip Temperature: " + String(temperatureRead()) + "°C");
    LOG_INFO("Battery Voltage: " + String(readBatteryVoltage()) + "V");
    LOG_INFO("Power Mode: " + String(power_mode));
    LOG_INFO("Sensors Active: " + String(sensors_active));
    LOG_INFO("===================");
}