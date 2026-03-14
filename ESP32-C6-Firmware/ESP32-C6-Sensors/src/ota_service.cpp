#include "ota_service.h"
#include <ArduinoOTA.h>

void setupOTA() {
    ArduinoOTA.setHostname("esp32c6-sensors");
    ArduinoOTA.begin();
    Serial.println("OTA Update Service Started...");
}

void otaLoop() {
    ArduinoOTA.handle();
}