#include "power_management.h"
#include "config.h"

// Power management state
static bool battery_mode = false;
static float last_battery_reading = 0.0;
static unsigned long last_battery_check = 0;
static int sleep_count = 0;

void setupPowerManagement() {
    LOG_INFO("Initializing power management...");
    
    // Configure battery monitoring pin
    pinMode(BATTERY_PIN, INPUT);
    
    // Check initial battery status
    float battery_voltage = readBatteryVoltage();
    LOG_INFO("Initial battery voltage: " + String(battery_voltage) + "V");
    
    // Determine if running on battery
    battery_mode = (battery_voltage < 4.0);  // Assuming USB power is ~5V, battery is <4V
    
    if (battery_mode) {
        LOG_WARN("Running on battery power - enabling power saving mode");
        optimizePowerConsumption();
    } else {
        LOG_INFO("Running on external power");
    }
}

void powerManagementLoop() {
    unsigned long now = millis();
    
    // Check battery status every 30 seconds
    if (now - last_battery_check >= 30000) {
        checkBatteryStatus();
        last_battery_check = now;
    }
    
    // Handle low battery conditions
    if (isBatteryLow()) {
        handleLowBattery();
    }
}

float readBatteryVoltage() {
    // Read ADC value
    int raw_reading = analogRead(BATTERY_PIN);
    
    // Convert to voltage (assuming voltage divider for ESP32 ADC protection)
    // Typical voltage divider might be 100k/100k for 50% scaling
    float voltage = (raw_reading / 4095.0) * VOLTAGE_REFERENCE * 2.0;
    
    return voltage;
}

bool isBatteryLow() {
    return (readBatteryVoltage() < LOW_BATTERY_THRESHOLD);
}

bool isBatteryPowered() {
    return battery_mode;
}

void checkBatteryStatus() {
    float current_voltage = readBatteryVoltage();
    
    // Update battery mode detection
    if (current_voltage > 4.5) {
        if (battery_mode) {
            LOG_INFO("External power detected, disabling battery mode");
            battery_mode = false;
        }
    } else if (current_voltage < 4.0) {
        if (!battery_mode) {
            LOG_WARN("Battery power detected, enabling battery mode");
            battery_mode = true;
        }
    }
    
    // Log significant voltage changes
    if (abs(current_voltage - last_battery_reading) > 0.1) {
        LOG_DEBUG("Battery voltage: " + String(current_voltage) + "V");
        last_battery_reading = current_voltage;
    }
    
    // Check for critical battery levels
    if (current_voltage < 3.0) {
        LOG_ERROR("Critical battery level! Entering emergency shutdown mode");
        handleEmergencyShutdown();
    }
}

void handleLowBattery() {
    LOG_WARN("Low battery detected, implementing power saving measures");
    
    // If WiFi is still connected, send low battery alert
    if (WiFi.status() == WL_CONNECTED && current_mode == WIFI_MQTT) {
        sendLowBatteryAlert();
    }
    
    // Enter deep sleep for longer periods
    handleDeepSleep();
}

void handleEmergencyShutdown() {
    LOG_ERROR("Emergency shutdown - critical battery level");
    
    // Send emergency alert if possible
    if (WiFi.status() == WL_CONNECTED && current_mode == WIFI_MQTT) {
        sendEmergencyAlert();
        delay(1000);  // Give time for message to send
    }
    
    // Force deep sleep with extended duration
    ESP.deepSleep(1800e6);  // 30 minutes deep sleep
}

void handleDeepSleep() {
    if (!battery_mode) {
        return;  // Don't sleep if on external power
    }
    
    LOG_INFO("Entering deep sleep for power conservation");
    
    // Calculate sleep duration based on battery level
    float battery_voltage = readBatteryVoltage();
    unsigned long sleep_duration = DEEP_SLEEP_DURATION;
    
    if (battery_voltage < 3.5) {
        sleep_duration *= 3;  // Sleep 3x longer if battery is very low
    } else if (battery_voltage < 3.8) {
        sleep_duration *= 2;  // Sleep 2x longer if battery is low
    }
    
    sleep_count++;
    LOG_INFO("Sleep count: " + String(sleep_count) + ", Duration: " + String(sleep_duration / 1e6) + "s");
    
    // Configure wake-up sources
    esp_sleep_enable_timer_wakeup(sleep_duration);
    
    // Enter deep sleep
    esp_deep_sleep_start();
}

void enterDeepSleep() {
    handleDeepSleep();
}

void sendLowBatteryAlert() {
    DynamicJsonDocument alert(256);
    alert["device_id"] = device_id;
    alert["alert_type"] = "low_battery";
    alert["battery_voltage"] = readBatteryVoltage();
    alert["timestamp"] = millis();
    alert["severity"] = "warning";
    
    String payload;
    serializeJson(alert, payload);
    
    String topic = "unit/" + unit_id + "/alerts";
    // publishMQTTMessage(topic.c_str(), payload.c_str()); // Uncomment when MQTT is implemented
    
    LOG_WARN("Low battery alert prepared");
}

void sendEmergencyAlert() {
    DynamicJsonDocument alert(256);
    alert["device_id"] = device_id;
    alert["alert_type"] = "critical_battery";
    alert["battery_voltage"] = readBatteryVoltage();
    alert["timestamp"] = millis();
    alert["severity"] = "critical";
    alert["message"] = "Device entering emergency shutdown";
    
    String payload;
    serializeJson(alert, payload);
    
    String topic = "unit/" + unit_id + "/alerts";
    // publishMQTTMessage(topic.c_str(), payload.c_str()); // Uncomment when MQTT is implemented
    
    LOG_ERROR("Emergency battery alert prepared");
}

void optimizePowerConsumption() {
    // Reduce CPU frequency for battery operation
    if (battery_mode) {
        setCpuFrequencyMhz(80);  // Reduce from default 240MHz to 80MHz
        LOG_DEBUG("CPU frequency reduced for power saving");
    } else {
        setCpuFrequencyMhz(240);  // Full speed on external power
    }
    
    // Adjust WiFi power saving
    if (battery_mode && WiFi.status() == WL_CONNECTED) {
        WiFi.setSleep(true);  // Enable WiFi power saving
        LOG_DEBUG("WiFi power saving enabled");
    } else {
        WiFi.setSleep(false);  // Disable WiFi power saving for better performance
    }
}