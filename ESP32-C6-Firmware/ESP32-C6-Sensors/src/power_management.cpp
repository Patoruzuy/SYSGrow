#include "power_management.h"
#include <Arduino.h>

#include "esp_sleep.h"
#include "sensor_co.h"

void enterDeepSleep() {
    Serial.println("💤 Entering Deep Sleep for 10 minutes...");
    esp_sleep_enable_timer_wakeup(10 * 60 * 1000000);  // Sleep for 10 minutes
    esp_deep_sleep_start();
}

void loop() {
    if (!client.connected()) {
        setupMQTT();
    }
    client.loop();

    float coLevel = readCOSensor();

    if (isBatteryPowered()) {
        enterDeepSleep();  // Save power
    }

    delay(60000);  // Send CO data every 60 seconds
}

void setupPowerManagement() {
    Serial.println("Power Management Initialized...");
}

void powerManagementLoop() {
    float voltage = analogRead(36) * 3.3 / 4096.0;
    Serial.print("Battery Voltage: ");
    Serial.println(voltage);
    if (voltage < 3.3) {
        Serial.println("Low battery, entering deep sleep...");
        ESP.deepSleep(60e6);
    }
}