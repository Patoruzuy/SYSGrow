#include <Wire.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <HardwareSerial.h>

// Wi-Fi & MQTT Configuration
#define WIFI_SSID "YourWiFiSSID"
#define WIFI_PASSWORD "YourWiFiPassword"
#define MQTT_BROKER "mqtt-broker.local"
#define MQTT_PORT 1883
#define SENSOR_TOPIC "homeassistant/sensor/esp32c6_co/state"

// User selects CO sensor (0 = MQ7, 1 = ZE07-CO)
#define USE_ZE07_CO 1  // Set to 0 if using MQ7

#if USE_ZE07_CO
    // ZE07-CO (UART) - Uses GPIO 16 (RX) & GPIO 17 (TX)
    HardwareSerial ze07Serial(1);
    #define ZE07_RX 16
    #define ZE07_TX 17
#else
    // MQ7 (Analog)
    #define MQ7_PIN 34  // Use ADC pin for analog readings
#endif

// Wi-Fi & MQTT Clients
WiFiClient espClient;
PubSubClient client(espClient);

// Function to connect to Wi-Fi
void setupWiFi() {
    Serial.print("Connecting to Wi-Fi...");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(1000);
        Serial.print(".");
    }
    Serial.println("\n✅ Connected to Wi-Fi!");
}

// Function to connect to MQTT Broker
void setupMQTT() {
    client.setServer(MQTT_BROKER, MQTT_PORT);
    Serial.print("Connecting to MQTT...");
    while (!client.connected()) {
        if (client.connect("ESP32-C6-CO")) {
            Serial.println("\n✅ Connected to MQTT!");
        } else {
            Serial.print(".");
            delay(1000);
        }
    }
}

// Function to read ZE07-CO Sensor (UART Mode)
float readZE07CO() {
    if (ze07Serial.available() >= 9) {
        byte buffer[9];
        ze07Serial.readBytes(buffer, 9);
        
        if (buffer[0] == 0xFF && buffer[1] == 0x86) { // Check valid frame
            int ppm = (buffer[2] << 8) | buffer[3];
            Serial.print("🔥 ZE07-CO Level: ");
            Serial.print(ppm);
            Serial.println(" ppm");
            return ppm;
        }
    }
    return -1;  // No valid data
}

// Function to read MQ7 Sensor (Analog Mode)
float readMQ7() {
    int rawValue = analogRead(MQ7_PIN);
    float voltage = rawValue * (3.3 / 4095.0);  // Convert ADC value to voltage
    Serial.print("🔥 MQ7 CO Level: ");
    Serial.print(voltage);
    Serial.println("V");
    return voltage;
}

// Read Selected CO Sensor and Send to MQTT
void readCOSensor() {
    float coLevel = USE_ZE07_CO ? readZE07CO() : readMQ7();

    // Create JSON payload
    StaticJsonDocument<128> jsonDoc;
    jsonDoc["co_level"] = coLevel;

    // Convert to string & publish to MQTT
    char buffer[128];
    serializeJson(jsonDoc, buffer);
    client.publish(SENSOR_TOPIC, buffer);
}

void setup() {
    Serial.begin(115200);
    setupWiFi();
    setupMQTT();

    if (USE_ZE07_CO) {
        ze07Serial.begin(9600, SERIAL_8N1, ZE07_RX, ZE07_TX);
        Serial.println("✅ ZE07-CO Initialized (UART Mode)");
    } else {
        pinMode(MQ7_PIN, INPUT);
        Serial.println("✅ MQ7 Initialized (Analog Mode)");
    }
}

void loop() {
    if (!client.connected()) {
        setupMQTT();
    }
    client.loop();

    readCOSensor();
    delay(60000);  // Send sensor data every 60 seconds
}

#include "sensor_co.h"
void setupCO() {
    Serial.println("Initializing CO Sensors...");
}
float readCO() {
    return analogRead(A0) * 0.1;  // Simulated sensor reading
}