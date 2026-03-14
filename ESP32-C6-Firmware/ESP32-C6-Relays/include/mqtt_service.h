#ifndef MQTT_SERVICE_H
#define MQTT_SERVICE_H

void startMQTT();
void mqtt_callback(char* topic, byte* payload, unsigned int length);
void publishMQTT(String topic, String message);

#endif
