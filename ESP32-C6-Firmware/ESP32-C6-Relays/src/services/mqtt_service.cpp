#include "mqtt_service.h"
#include "logging.h"
#include <WiFiClientSecure.h>

WiFiClientSecure secureClient;
PubSubClient client(secureClient);

void startMQTT() {
    secureClient.setCACert(CA_CERT);
    client.setServer(mqtt_broker.c_str(), 8883);
    client.setCallback(mqtt_callback);
    
    LOG_INFO("Connecting to secure MQTT...");
    if (client.connect(device_id)) {
        LOG_INFO("Connected to MQTT with TLS.");
    } else {
        LOG_ERROR("MQTT TLS Connection Failed.");
    }
}

void mqtt_callback(char* topic, byte* payload, unsigned int length) {
    String topicStr = String(topic);
    LOG_INFO("Received MQTT message on topic: " + topicStr);

    if (topicStr == "zigbee2mqtt/" + String(device_id) + "/wifi_config") {
        wifi_config(payload, length);
    } else if (topicStr == "zigbee2mqtt/" + String(device_id) + "/ota_update") {
        performOTA();
    } else {
        int lastSlash = topicStr.lastIndexOf('/');
        int pin = topicStr.substring(lastSlash + 1).toInt();

        for (int pinNum : relayPins) {
            if (pin == pinNum) {
                digitalWrite(pin, (String((char*)payload) == "ON") ? HIGH : LOW);
                LOG_INFO("Relay GPIO " + String(pin) + " set to " + (payload[0] == 'O' ? "ON" : "OFF"));
            }
        }
    }
}
