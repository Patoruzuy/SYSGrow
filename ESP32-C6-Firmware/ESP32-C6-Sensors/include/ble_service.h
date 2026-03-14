#ifndef BLE_SERVICE_H
#define BLE_SERVICE_H

#include <Arduino.h>

// ============================================================================
// BLE Service - Provisioning and Sensor Data
// ============================================================================
// Provides BLE functionality for:
//   - WiFi/MQTT provisioning via writable characteristics
//   - Sensor data broadcasting via notifications
//   - Timed pairing mode (30s timeout)
// ============================================================================

// ============================================================================
// Setup and Loop Functions
// ============================================================================

/**
 * Initialize BLE server, services, and characteristics.
 * Sets up advertising and callbacks.
 */
void setupBLE();

/**
 * Main BLE loop - handles pairing timeout and data broadcasting.
 */
void bleLoop();

// ============================================================================
// Pairing Mode Control
// ============================================================================

/**
 * Start BLE advertising for pairing.
 * Advertising will stop after BLE_PAIRING_TIMEOUT_MS.
 */
void startBLEAdvertising();

/**
 * Stop BLE advertising.
 */
void stopBLEAdvertising();

/**
 * Check if BLE is currently advertising.
 * @return true if advertising is active
 */
bool isBLEAdvertising();

// ============================================================================
// Provisioning Functions
// ============================================================================

/**
 * Check if a provisioning configuration was received.
 * @return true if new config is waiting to be processed
 */
bool hasProvisioningConfig();

/**
 * Clear the provisioning config flag.
 */
void clearProvisioningConfig();

/**
 * Get provisioned WiFi SSID.
 * @return SSID string or empty if not set
 */
String getProvisionedSSID();

/**
 * Get provisioned WiFi password.
 * @return Password string or empty if not set
 */
String getProvisionedPassword();

/**
 * Get provisioned MQTT broker address.
 * @return Broker address or empty if not set
 */
String getProvisionedMQTTBroker();

/**
 * Get provisioned MQTT username (optional).
 * @return Username or empty if not set
 */
String getProvisionedMQTTUsername();

/**
 * Get provisioned MQTT password (optional).
 * @return Password or empty if not set
 */
String getProvisionedMQTTPassword();

/**
 * Get provisioned friendly name (optional).
 * @return Friendly name or empty if not set
 */
String getProvisionedFriendlyName();

// ============================================================================
// Sensor Data Broadcasting
// ============================================================================

/**
 * Update sensor characteristic with current readings.
 * Notifies connected clients of new data.
 */
void updateBLESensorData();

/**
 * Get number of connected BLE clients.
 * @return Number of connected clients
 */
int getBLEConnectedCount();

// ============================================================================
// Status Functions
// ============================================================================

/**
 * Check if BLE is initialized and ready.
 * @return true if BLE is ready
 */
bool isBLEReady();

/**
 * Get BLE device name.
 * @return BLE device name string
 */
String getBLEDeviceName();

#endif // BLE_SERVICE_H
