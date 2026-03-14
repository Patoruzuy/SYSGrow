#ifndef MQTT_SERVICE_H
#define MQTT_SERVICE_H

#include <Arduino.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ============================================================================
// MQTT Service - Zigbee2MQTT-style Implementation
// ============================================================================
// This module implements a Zigbee2MQTT-compatible MQTT protocol for ESP32-C6
// sensor devices. Topics follow the pattern:
//   - sysgrow/<friendly_name>           - Sensor state (JSON)
//   - sysgrow/<friendly_name>/set       - Commands (JSON)
//   - sysgrow/<friendly_name>/get       - On-demand read trigger
//   - sysgrow/<friendly_name>/availability - Online/offline (LWT)
//   - sysgrow/bridge/info               - Bridge status
//   - sysgrow/bridge/health             - Health check
//   - sysgrow/bridge/request/*          - Bridge commands
//   - sysgrow/bridge/response/*         - Bridge responses
// ============================================================================

// ============================================================================
// Core MQTT Functions
// ============================================================================

/**
 * Initialize MQTT client and configure callbacks.
 * Must be called after WiFi is connected.
 */
void setupMQTT();

/**
 * Main MQTT loop - handles reconnection, message processing.
 * Should be called from the main loop().
 */
void mqttLoop();

/**
 * Connect to MQTT broker with LWT configuration.
 * @return true if connected successfully
 */
bool connectMQTT();

/**
 * Check if MQTT is currently connected.
 * @return true if connected
 */
bool isMQTTConnected();

/**
 * Disconnect from MQTT broker gracefully.
 */
void disconnectMQTT();

// ============================================================================
// Publishing Functions
// ============================================================================

/**
 * Publish a message to an MQTT topic.
 * @param topic The MQTT topic
 * @param payload The message payload
 * @param retained Whether to retain the message
 * @return true if published successfully
 */
bool publishMQTTMessage(const char* topic, const char* payload, bool retained = false);

/**
 * Publish all sensor data to sysgrow/<friendly_name>.
 * Builds and publishes the complete sensor state JSON.
 */
void publishSensorData();

/**
 * Publish device availability status.
 * @param online true for "online", false for "offline"
 */
void publishAvailability(bool online);

/**
 * Publish bridge info to sysgrow/bridge/info.
 * Contains firmware version, network info, config, connected devices.
 */
void publishBridgeInfo();

/**
 * Publish bridge health to sysgrow/bridge/health.
 * Contains system health metrics.
 */
void publishBridgeHealth();

/**
 * Publish a bridge response message.
 * @param command The command name (used in topic: sysgrow/bridge/response/<command>)
 * @param status "ok" or "error"
 * @param data Optional JSON data object
 * @param error Optional error message (when status is "error")
 * @param transaction Optional transaction ID for tracking
 */
void publishBridgeResponse(
    const char* command,
    const char* status,
    const JsonObject* data = nullptr,
    const char* error = nullptr,
    const char* transaction = nullptr
);

// ============================================================================
// Topic Builders
// ============================================================================

/**
 * Get the main device state topic.
 * @return Topic string: sysgrow/<friendly_name>
 */
String getDeviceTopic();

/**
 * Get the device command topic.
 * @return Topic string: sysgrow/<friendly_name>/set
 */
String getDeviceSetTopic();

/**
 * Get the device get/trigger topic.
 * @return Topic string: sysgrow/<friendly_name>/get
 */
String getDeviceGetTopic();

/**
 * Get the device availability topic (used for LWT).
 * @return Topic string: sysgrow/<friendly_name>/availability
 */
String getAvailabilityTopic();

/**
 * Get bridge info topic.
 * @return Topic string: sysgrow/bridge/info
 */
String getBridgeInfoTopic();

/**
 * Get bridge health topic.
 * @return Topic string: sysgrow/bridge/health
 */
String getBridgeHealthTopic();

// ============================================================================
// Message Handlers
// ============================================================================

/**
 * Main MQTT message callback - routes to specific handlers.
 * @param topic The received topic
 * @param payload The message payload
 * @param length Payload length
 */
void onMQTTMessage(char* topic, byte* payload, unsigned int length);

/**
 * Handle device /set commands.
 * Supports: polling_interval, friendly_name, calibration, restart, factory_reset
 * @param payload JSON payload
 */
void handleDeviceSetCommand(const char* payload);

/**
 * Handle device /get command - triggers immediate sensor read.
 */
void handleDeviceGetCommand();

// ============================================================================
// Bridge Command Handlers
// ============================================================================

/**
 * Handle permit_join request - enables BLE pairing mode.
 * Topic: sysgrow/bridge/request/permit_join
 * Payload: {"value": true, "time": 30}
 * @param payload JSON payload
 */
void handlePermitJoinCommand(const char* payload);

/**
 * Handle restart request.
 * Topic: sysgrow/bridge/request/restart
 * Payload: {} or {"id": "specific-device"}
 * @param payload JSON payload
 */
void handleRestartCommand(const char* payload);

/**
 * Handle device rename request.
 * Topic: sysgrow/bridge/request/device/rename
 * Payload: {"from": "old-name", "to": "new-name"}
 * @param payload JSON payload
 */
void handleRenameCommand(const char* payload);

/**
 * Handle device remove/factory reset request.
 * Topic: sysgrow/bridge/request/device/remove
 * Payload: {"id": "device-name", "force": false}
 * @param payload JSON payload
 */
void handleRemoveCommand(const char* payload);

/**
 * Handle OTA update request.
 * Topic: sysgrow/bridge/request/device/ota_update/update
 * Payload: {"id": "device-name", "url": "http://..."}
 * @param payload JSON payload
 */
void handleOTAUpdateCommand(const char* payload);

/**
 * Handle health check request.
 * Topic: sysgrow/bridge/request/health_check
 * @param payload JSON payload (usually empty)
 */
void handleHealthCheckCommand(const char* payload);

// ============================================================================
// Payload Builders
// ============================================================================

/**
 * Build the complete sensor state JSON payload.
 * Includes all sensor readings, device info, and metadata.
 * @param doc JsonDocument to populate
 */
void buildSensorPayload(JsonDocument& doc);

/**
 * Build bridge info JSON payload.
 * @param doc JsonDocument to populate
 */
void buildBridgeInfoPayload(JsonDocument& doc);

/**
 * Build bridge health JSON payload.
 * @param doc JsonDocument to populate
 */
void buildBridgeHealthPayload(JsonDocument& doc);

// ============================================================================
// Subscription Management
// ============================================================================

/**
 * Subscribe to all required MQTT topics.
 * Called after successful MQTT connection.
 */
void subscribeToTopics();

/**
 * Unsubscribe from all MQTT topics.
 * Called before disconnection or when changing friendly_name.
 */
void unsubscribeFromTopics();

/**
 * Resubscribe after friendly_name change.
 * Unsubscribes old topics and subscribes to new ones.
 * @param oldName Previous friendly_name
 */
void resubscribeAfterRename(const String& oldName);

#endif // MQTT_SERVICE_H
