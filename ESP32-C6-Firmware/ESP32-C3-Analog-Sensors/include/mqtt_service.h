#ifndef MQTT_SERVICE_H
#define MQTT_SERVICE_H

#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "config.h"

// MQTT connection status
enum MQTTStatus {
    MQTT_DISCONNECTED = 0,
    MQTT_CONNECTING = 1,
    MQTT_CONNECTED = 2,
    MQTT_CONNECTION_FAILED = 3,
    MQTT_AUTH_FAILED = 4,
    MQTT_TIMEOUT = 5
};

// MQTT quality of service levels
enum MQTTQoS {
    QOS_0 = 0,  // At most once
    QOS_1 = 1,  // At least once
    QOS_2 = 2   // Exactly once
};

// Message priorities
enum MessagePriority {
    PRIORITY_LOW = 0,
    PRIORITY_NORMAL = 1,
    PRIORITY_HIGH = 2,
    PRIORITY_CRITICAL = 3
};

// Message queue structure
struct MQTTMessage {
    String topic;
    String payload;
    MQTTQoS qos;
    bool retain;
    MessagePriority priority;
    unsigned long timestamp;
    uint8_t retry_count;
};

// MQTT statistics
struct MQTTStats {
    uint32_t messages_sent;
    uint32_t messages_received;
    uint32_t connection_attempts;
    uint32_t successful_connections;
    uint32_t failed_connections;
    uint32_t disconnections;
    unsigned long total_connected_time;
    unsigned long last_connection_time;
    unsigned long last_message_time;
};

// Function prototypes
void setupMQTT();
void mqttLoop();
bool connectMQTT();
void disconnectMQTT();
void reconnectMQTT();

// Connection management
bool isMQTTConnected();
MQTTStatus getMQTTStatus();
String getMQTTStatusString();
void setMQTTCredentials(const char* broker, const char* username, const char* password);
void setMQTTClientId(const String& client_id);

// Publishing functions
bool publishMQTTMessage(const char* topic, const char* payload, MQTTQoS qos = QOS_1, bool retain = false);
bool publishSensorData();
bool publishHeartbeat();
bool publishDeviceStatus();
bool publishAlert(const String& alert_type, const String& message, MessagePriority priority = PRIORITY_NORMAL);

// Subscription management
bool subscribeToTopic(const char* topic, MQTTQoS qos = QOS_1);
bool unsubscribeFromTopic(const char* topic);
void subscribeToDeviceTopics();
void handleIncomingMessage(char* topic, byte* payload, unsigned int length);

// Message queue management
bool queueMessage(const String& topic, const String& payload, MQTTQoS qos = QOS_1, bool retain = false, MessagePriority priority = PRIORITY_NORMAL);
void processMessageQueue();
void clearMessageQueue();
uint16_t getQueueSize();

// Topic management
String getDeviceTopicPrefix();
String getSensorTopic();
String getStatusTopic();
String getConfigTopic();
String getCommandTopic();
String getAlertTopic();

// Command handling
void handleConfigCommand(const JsonDocument& command);
void handleCalibrationCommand(const JsonDocument& command);
void handlePowerCommand(const JsonDocument& command);
void handleSensorCommand(const JsonDocument& command);
void handleOTACommand(const JsonDocument& command);

// Security and certificates
void configureMQTTSecurity(bool use_tls = true);
void setRootCA(const char* root_ca);
void setClientCertificate(const char* client_cert, const char* client_key);

// Statistics and monitoring
MQTTStats getMQTTStatistics();
void resetMQTTStatistics();
void logMQTTStatistics();

// Advanced features
void enableMQTTKeepAlive(bool enable, uint16_t interval = 60);
void setMQTTBufferSize(uint16_t size);
void enableMQTTLogging(bool enable);
void setMQTTTimeout(uint32_t timeout_ms);

// Error handling
void handleMQTTError(int error_code);
String getMQTTErrorString(int error_code);

// Global MQTT variables
extern WiFiClientSecure secure_client;
extern PubSubClient mqtt_client;
extern MQTTStatus mqtt_status;
extern MQTTStats mqtt_stats;
extern String mqtt_client_id;
extern bool mqtt_logging_enabled;
extern bool mqtt_security_enabled;
extern unsigned long last_mqtt_ping;
extern unsigned long last_reconnect_attempt;

// Message queue
extern std::vector<MQTTMessage> message_queue;
extern const uint16_t MAX_QUEUE_SIZE;

// TLS certificate storage
extern const char* root_ca_cert;
extern const char* client_cert;
extern const char* client_key;

#endif // MQTT_SERVICE_H