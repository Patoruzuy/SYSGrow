#include "mqtt_service.h"
#include <PubSubClient.h>
#include <WiFi.h>

WiFiClient espClient;
PubSubClient client(espClient);

void setupMQTT() {
    client.setServer("mqtt-broker.local", 1883);
    Serial.println("MQTT initialized.");
}

void mqttLoop() {
    if (!client.connected()) {
        Serial.println("MQTT Reconnecting...");
        if (client.connect("ESP32-C6-Sensors")) {
            Serial.println("MQTT Connected.");
        }
    }
    client.loop();
}