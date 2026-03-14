#ifndef POWER_MANAGEMENT_H
#define POWER_MANAGEMENT_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <esp_sleep.h>
#include <esp_wifi.h>
#include <esp_bt.h>
#include "config.h"

// Power management structure
struct PowerStatus {
    float battery_voltage;
    float battery_percentage;
    bool is_charging;
    bool is_battery_powered;
    PowerMode current_mode;
    unsigned long uptime;
    unsigned long total_sleep_time;
    uint32_t wake_count;
    uint32_t deep_sleep_count;
    esp_sleep_wakeup_cause_t last_wake_cause;
};

// Battery monitoring
struct BatteryInfo {
    float voltage;
    float percentage;
    float min_voltage_recorded;
    float max_voltage_recorded;
    bool is_low;
    bool is_critical;
    unsigned long last_check;
    uint32_t low_battery_events;
    uint32_t critical_battery_events;
};

// Function prototypes
void setupPowerManagement();
void powerManagementLoop();

// Battery monitoring functions
float readBatteryVoltage();
float calculateBatteryPercentage(float voltage);
bool isBatteryLow();
bool isBatteryCritical();
bool isBatteryCharging();
bool isBatteryPowered();
void updateBatteryStatus();
BatteryInfo getBatteryInfo();

// Power mode management
void setPowerMode(PowerMode mode);
PowerMode getCurrentPowerMode();
void enterNormalPowerMode();
void enterPowerSaveMode();
void enterEmergencyMode();
void optimizePowerConsumption();

// Sleep management
void handleDeepSleep(unsigned long duration_us = DEEP_SLEEP_DURATION);
void handleLightSleep(unsigned long duration_us = LIGHT_SLEEP_DURATION);
void configureSleepWakeup();
void configureDeepSleepWakeup(unsigned long duration_us);
void configureLightSleepWakeup(unsigned long duration_us);
esp_sleep_wakeup_cause_t getWakeupCause();
String getWakeupCauseString();

// Power saving features
void enableWiFiPowerSave(bool enable);
void enableBluetoothPowerSave(bool enable);
void setCPUFrequency(uint32_t frequency_mhz);
void disableUnusedPeripherals();
void enableUnusedPeripherals();

// Alert and notification functions
void sendLowBatteryAlert();
void sendCriticalBatteryAlert();
void sendPowerModeChangeAlert(PowerMode old_mode, PowerMode new_mode);
void handlePowerEmergency();

// Power consumption estimation
float estimatePowerConsumption();
unsigned long estimateBatteryLife();
void logPowerConsumption();

// Power scheduling
void scheduleDeepSleep(unsigned long delay_ms, unsigned long duration_us);
void schedulePeriodicWakeup(unsigned long interval_us);
void cancelScheduledSleep();

// Advanced power features
void enableSmartPowerManagement(bool enable);
void setAdaptiveSleepDuration(bool enable);
void configurePowerSaveThresholds(float low_voltage, float critical_voltage);
void setMaxSleepDuration(unsigned long max_duration_us);

// Power statistics and monitoring
struct PowerStatistics {
    unsigned long total_uptime;
    unsigned long total_sleep_time;
    uint32_t wake_events;
    uint32_t sleep_events;
    float average_battery_voltage;
    float power_consumption_estimate;
    unsigned long last_reset;
};

PowerStatistics getPowerStatistics();
void resetPowerStatistics();
void savePowerStatistics();
void loadPowerStatistics();

// External power management
bool isExternalPowerConnected();
void handleExternalPowerConnect();
void handleExternalPowerDisconnect();
void configureChargingBehavior();

// Power management configuration
struct PowerConfig {
    bool smart_power_enabled;
    bool adaptive_sleep_enabled;
    float low_battery_threshold;
    float critical_battery_threshold;
    unsigned long max_sleep_duration;
    unsigned long min_sleep_duration;
    uint32_t max_cpu_frequency;
    uint32_t min_cpu_frequency;
    bool wifi_power_save_enabled;
    bool bluetooth_power_save_enabled;
};

void setPowerConfig(const PowerConfig& config);
PowerConfig getPowerConfig();
void savePowerConfig();
void loadPowerConfig();
void resetPowerConfig();

// Sleep timer management
void startSleepTimer(unsigned long duration_ms);
void stopSleepTimer();
bool isSleepTimerActive();
unsigned long getSleepTimerRemaining();

// Wake-up source management
void enableTimerWakeup(unsigned long duration_us);
void enableGPIOWakeup(uint8_t pin, bool level);
void enableTouchWakeup();
void enableULPWakeup();
void disableAllWakeupSources();

// Power event callbacks
typedef void (*PowerEventCallback)(PowerMode mode, float battery_voltage);
void setPowerEventCallback(PowerEventCallback callback);
void triggerPowerEvent(PowerMode mode, float battery_voltage);

// Emergency power functions
void enterEmergencyShutdown();
void prepareForShutdown();
bool canSafelyShutdown();
void forceShutdown();

// Power debugging and diagnostics
void printPowerStatus();
void printBatteryInfo();
void printPowerStatistics();
String getPowerStatusJSON();
void diagnosePowerSystem();

// Global power management variables
extern PowerStatus power_status;
extern BatteryInfo battery_info;
extern PowerConfig power_config;
extern PowerStatistics power_stats;
extern bool power_management_active;
extern bool emergency_mode_active;
extern PowerEventCallback power_event_callback;

// Constants
extern const float BATTERY_MAX_VOLTAGE;
extern const float BATTERY_MIN_VOLTAGE;
extern const float BATTERY_FULL_PERCENTAGE;
extern const float BATTERY_EMPTY_PERCENTAGE;
extern const uint32_t POWER_CHECK_INTERVAL;
extern const uint32_t BATTERY_FILTER_SIZE;

#endif // POWER_MANAGEMENT_H