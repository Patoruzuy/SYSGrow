#include "config.h"
#include "mqtt_service.h"
#include "ble_service.h"
#include "ota_service.h"
#include "power_management.h"
#include "web_server.h"
#include "eeprom_utils.h"

void setup() {
    Serial.begin(115200);
    loadConnectionMode();
    loadWiFiConfig();

    WiFi.mode(WIFI_STA);
    WiFi.begin(stored_ssid, stored_password);

    int wifiTimeout = 10;
    while (WiFi.status() != WL_CONNECTED && wifiTimeout > 0) {
        delay(1000);
        Serial.print(".");
        wifiTimeout--;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nConnected to Wi-Fi");
        startMQTT();
    } else {
        Serial.println("\nWi-Fi Failed. Starting BLE Mode...");
        setupBLE();
    }

    if (!MDNS.begin(device_id)) {
        Serial.println("Error starting mDNS");
    }

    timeClient.begin();
    adjustSleepDuration();
    startWebServer();
}

void loop() {
    if ((selectedMode == WIFI || selectedMode == ZIGBEE) && !client.connected()) {
        client.connect(device_id);
    }
    client.loop();
    MDNS.update();

    if (!isBLEActive && isBatteryPowered()) {
        Serial.println("Running on Battery, Entering Deep Sleep...");
        enterDeepSleep();
    }
}
