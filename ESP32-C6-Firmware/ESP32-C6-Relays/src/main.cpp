#include "config.h"
#include "mqtt_service.h"
#include "ble_service.h"
#include "ota_service.h"
#include "power_management.h"
#include "web_server.h"
#include "eeprom_utils.h"
#include "provision_service.h"

void setup() {
    Serial.begin(115200);
    checkProvisioning();  // Start BLE provisioning if needed

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

        // Publish this module as registered
        String registrationTopic = "unit/" + String(unit_id) + "/register_module";
        DynamicJsonDocument doc(256);
        doc["unit_id"] = unit_id;
        doc["device_id"] = device_id;
        doc["module_type"] = "Relay";  // Or change based on device
        doc["friendly_name"] = "ESP32-C6-Relays";  // Custom name

        String payload;
        serializeJson(doc, payload);
        client.publish(registrationTopic.c_str(), payload.c_str());
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
