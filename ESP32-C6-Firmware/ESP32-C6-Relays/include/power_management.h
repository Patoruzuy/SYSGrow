#ifndef POWER_MANAGEMENT_H
#define POWER_MANAGEMENT_H

float readBatteryVoltage();
bool isBatteryPowered();
void enterDeepSleep();
void adjustSleepDuration();
void sendLowBatteryAlert(float voltage);

#endif
// Compare this snippet from Modules/ESP32-C6-Relays/include/ble_service.h:
// #ifndef BLE_SERVICE_H