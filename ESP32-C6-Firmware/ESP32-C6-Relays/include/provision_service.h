#ifndef PROVISION_SERVICE_H
#define PROVISION_SERVICE_H

#include <Arduino.h>

/**
 * Starts BLE provisioning if device is not already configured.
 * Allows user to send SSID, password, unit_id, and device_type via BLE.
 */
void checkProvisioning();

/**
 * Load stored Unit ID from EEPROM.
 * @return String representing the unit ID
 */
String loadUnitID();

/**
 * Load stored Device Type from EEPROM.
 * @return String representing the device type
 */
String loadDeviceType();

/**
 * Clears provisioning data from EEPROM and restarts device.
 */
void clearProvisioning();

#endif // PROVISION_SERVICE_H