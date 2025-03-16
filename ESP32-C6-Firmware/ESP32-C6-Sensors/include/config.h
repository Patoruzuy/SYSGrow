#ifndef CONFIG_H
#define CONFIG_H

#define WIFI_SSID "your-ssid"
#define WIFI_PASSWORD "your-password"
#define MQTT_BROKER "mqtt-broker.local"
#define OTA_HOSTNAME "esp32c6-sensors"
#define WEB_SERVER_PORT 80

void setupWiFi();

#endif