#ifndef BLE_SERVICE_H
#define BLE_SERVICE_H

#include <Arduino.h>
#include <ArduinoJson.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <vector>

// BLE Service UUIDs
#define BLE_SERVICE_UUID              "12345678-1234-5678-9abc-123456789abc"
#define BLE_CHARACTERISTIC_CONFIG_UUID "12345678-1234-5678-9abc-123456789abd"
#define BLE_CHARACTERISTIC_SENSOR_UUID "12345678-1234-5678-9abc-123456789abe"
#define BLE_CHARACTERISTIC_STATUS_UUID "12345678-1234-5678-9abc-123456789abf"
#define BLE_CHARACTERISTIC_COMMAND_UUID "12345678-1234-5678-9abc-123456789ac0"

// BLE Configuration
#define BLE_DEVICE_NAME           "SysGrow-AnalogSensor"
#define BLE_ADVERTISING_INTERVAL  1600  // 1 second (1600 * 0.625ms)
#define BLE_CONNECTION_TIMEOUT    30000  // 30 seconds
#define BLE_MAX_CONNECTIONS       1
#define BLE_MTU_SIZE             512

// BLE States
enum BLEState {
    BLE_DISABLED,
    BLE_INITIALIZING,
    BLE_ADVERTISING,
    BLE_CONNECTED,
    BLE_DISCONNECTED,
    BLE_ERROR
};

// BLE Connection Info
struct BLEConnectionInfo {
    bool is_connected = false;
    String client_address = "";
    unsigned long connection_time = 0;
    unsigned long last_activity = 0;
    uint16_t mtu_size = 23;
};

// BLE Statistics
struct BLEStats {
    uint32_t connection_count = 0;
    uint32_t disconnection_count = 0;
    uint32_t data_sent = 0;
    uint32_t data_received = 0;
    uint32_t command_count = 0;
    unsigned long total_connection_time = 0;
    unsigned long last_connection_duration = 0;
};

// BLE Message Types
enum BLEMessageType {
    BLE_MSG_CONFIG = 0x01,
    BLE_MSG_SENSOR_DATA = 0x02,
    BLE_MSG_STATUS = 0x03,
    BLE_MSG_COMMAND = 0x04,
    BLE_MSG_RESPONSE = 0x05,
    BLE_MSG_ALERT = 0x06
};

// BLE Command Types
enum BLECommandType {
    BLE_CMD_READ_CONFIG = 0x01,
    BLE_CMD_WRITE_CONFIG = 0x02,
    BLE_CMD_READ_SENSORS = 0x03,
    BLE_CMD_CALIBRATE_SENSOR = 0x04,
    BLE_CMD_POWER_CONTROL = 0x05,
    BLE_CMD_RESET_DEVICE = 0x06,
    BLE_CMD_GET_STATUS = 0x07,
    BLE_CMD_SET_WIFI = 0x08,
    BLE_CMD_SET_MQTT = 0x09
};

// Global BLE variables
extern BLEState ble_state;
extern BLEConnectionInfo ble_connection;
extern BLEStats ble_stats;
extern bool ble_notifications_enabled;
extern bool ble_security_enabled;
extern unsigned long last_ble_activity;

// BLE Service objects
extern BLEServer* pServer;
extern BLEService* pService;
extern BLECharacteristic* pConfigCharacteristic;
extern BLECharacteristic* pSensorCharacteristic;
extern BLECharacteristic* pStatusCharacteristic;
extern BLECharacteristic* pCommandCharacteristic;

// BLE Callback classes
class BLEServerCallbacks: public BLEServerCallbacks {
public:
    void onConnect(BLEServer* pServer) override;
    void onDisconnect(BLEServer* pServer) override;
};

class BLEConfigCallbacks: public BLECharacteristicCallbacks {
public:
    void onWrite(BLECharacteristic *pCharacteristic) override;
    void onRead(BLECharacteristic *pCharacteristic) override;
};

class BLECommandCallbacks: public BLECharacteristicCallbacks {
public:
    void onWrite(BLECharacteristic *pCharacteristic) override;
};

// BLE Service Functions
void setupBLE();
void bleLoop();
bool startBLEAdvertising();
void stopBLEAdvertising();
void handleBLEConnection();
void handleBLEDisconnection();

// BLE Communication Functions
bool sendBLEMessage(BLEMessageType msg_type, const JsonDocument& data);
bool sendSensorDataViaBLE();
bool sendStatusViaBLE();
bool sendConfigViaBLE();
bool sendResponseViaBLE(uint8_t command_id, bool success, const String& message = "");

// BLE Command Handlers
void handleBLECommand(const JsonDocument& command);
void handleReadConfigCommand();
void handleWriteConfigCommand(const JsonDocument& config);
void handleReadSensorsCommand();
void handleCalibrateSensorCommand(const JsonDocument& params);
void handlePowerControlCommand(const JsonDocument& params);
void handleResetDeviceCommand();
void handleGetStatusCommand();
void handleSetWiFiCommand(const JsonDocument& wifi_config);
void handleSetMQTTCommand(const JsonDocument& mqtt_config);

// BLE Security Functions
void configureBLESecurity();
bool authenticateBLEClient(const String& client_address);
void encryptBLEData(String& data);
void decryptBLEData(String& data);

// BLE Utility Functions
String getBLEDeviceName();
String getBLEClientAddress();
bool isBLEConnected();
void setBLENotifications(bool enabled);
uint16_t getBLEMTU();
BLEStats getBLEStatistics();
void logBLEStatistics();
String getBLEStateString();
void resetBLEStatistics();

// BLE Data Formatting
String formatBLEMessage(BLEMessageType type, const JsonDocument& data);
bool parseBLEMessage(const String& message, BLEMessageType& type, JsonDocument& data);
void compressBLEData(const JsonDocument& input, JsonDocument& output);

// BLE Power Management
void enableBLEPowerSave();
void disableBLEPowerSave();
void setBLEPowerLevel(int8_t power_level);

// BLE Provisioning
struct WiFiCredentials {
    String ssid;
    String password;
    bool use_static_ip = false;
    String static_ip;
    String gateway;
    String subnet;
    String dns1;
    String dns2;
};

struct MQTTCredentials {
    String broker;
    uint16_t port = 1883;
    String username;
    String password;
    String client_id;
    bool use_ssl = false;
    String ca_cert;
    String client_cert;
    String client_key;
};

bool provisionWiFi(const WiFiCredentials& credentials);
bool provisionMQTT(const MQTTCredentials& credentials);
void clearProvisioningData();
bool isDeviceProvisioned();

#endif // BLE_SERVICE_H