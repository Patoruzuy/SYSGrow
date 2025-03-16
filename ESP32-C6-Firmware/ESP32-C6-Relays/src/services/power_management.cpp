#include "power_management.h"
#include "mqtt_service.h"
#include "logging.h"

float readBatteryVoltage() {
    int raw = analogRead(BATTERY_PIN);
    float voltage = (raw / 4095.0) * 3.3 * (100.0 + 47.0) / 47.0;
    LOG_INFO("Battery Voltage: " + String(voltage) + "V");

    if (voltage < 3.7) {
        LOG_WARN(" Low battery detected. Sending alert...");
        sendLowBatteryAlert(voltage);
    }

    return voltage;
}

bool isBatteryPowered() {
    float voltage = readBatteryVoltage();
    if (voltage < 4.5) {
        LOG_WARN("Low power mode activated. Running on battery.");
        return true;
    }
    return false;
}

void enterDeepSleep() {
    LOG_INFO("Entering Deep Sleep...");
    ESP.deepSleep(DEFAULT_SLEEP_DURATION);
}

// Adjust sleep duration based on time
void adjustSleepDuration() {
    timeClient.update();
    int hour = timeClient.getHours();
    SLEEP_DURATION = (hour >= 18 || hour < 6) ? 1800e6 : DEFAULT_SLEEP_DURATION;  // 30 minutes at night, 5 minutes during the day
}

void sendLowBatteryAlert(float voltage) {
    String topic = "zigbee2mqtt/ESP32-C6-Relay/battery_warning";
    String message = "{\"device\": \"ESP32-C6\", \"voltage\": \"" + String(voltage) + "\"}";

    publishMQTT(topic, message);
}