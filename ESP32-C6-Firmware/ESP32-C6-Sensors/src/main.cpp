#include "config.h"
#include "sensor_co.h"
#include "sensor_air.h"
#include "mqtt_service.h"
#include "ota_service.h"
#include "power_management.h"
#include "ble_service.h"
#include "web_server.h"

void setup() {
    Serial.begin(115200);
    setupWiFi();
    setupMQTT();
    setupSensors();
    setupBLE();
    setupWebServer();
}

void loop() {
    mqttLoop();
    sensorLoop();
    powerManagementLoop();
    bleLoop();
    webServerLoop();
}