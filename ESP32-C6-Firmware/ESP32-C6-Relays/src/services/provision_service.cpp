// provision_service.cpp
#include "provision_service.h"
#include <WiFi.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define PROVISION_SERVICE_UUID        "abcdef01-1234-5678-9abc-def012345678"
#define PROVISION_CHARACTERISTIC_UUID "abcdef02-1234-5678-9abc-def012345678"

BLEServer* pServer;
BLECharacteristic* pCharacteristic;
bool deviceProvisioned = false;

void checkProvisioning() {
    if (!isProvisioned()) {
        Serial.println("Device not provisioned. Starting provisioning mode...");
        startProvisioningMode();
    } else {
        Serial.println("Device already provisioned.");
    }
}

void startProvisioningMode() {
    BLEDevice::init("ESP32-Setup");
    pServer = BLEDevice::createServer();
    BLEService *service = pServer->createService(PROVISION_SERVICE_UUID);

    pCharacteristic = service->createCharacteristic(
        PROVISION_CHARACTERISTIC_UUID,
        BLECharacteristic::PROPERTY_WRITE
    );

    pCharacteristic->setCallbacks(new class : public BLECharacteristicCallbacks {
        void onWrite(BLECharacteristic* characteristic) {
            String value = characteristic->getValue().c_str();
            Serial.println("Received provisioning payload: " + value);

            DynamicJsonDocument doc(256);
            deserializeJson(doc, value);

            String ssid = doc["ssid"];
            String password = doc["password"];
            String unit_id = doc["unit_id"];
            String device_type = doc["device_type"];

            WiFi.begin(ssid.c_str(), password.c_str());

            int retry = 10;
            while (WiFi.status() != WL_CONNECTED && retry > 0) {
                delay(1000);
                retry--;
            }

            if (WiFi.status() == WL_CONNECTED) {
                Serial.println("WiFi Connected");
                saveUnitID(unit_id);
                saveDeviceType(device_type);
                ESP.restart();
            } else {
                Serial.println("WiFi Failed");
            }
        }
    });

    service->start();
    BLEAdvertising *advertising = BLEDevice::getAdvertising();
    advertising->addServiceUUID(PROVISION_SERVICE_UUID);
    advertising->start();
    Serial.println("Provisioning BLE active...");
}

String loadUnitID() {
    EEPROM.begin(EEPROM_SIZE);
    char buffer[MAX_UNIT_ID_LEN];
    for (int i = 0; i < MAX_UNIT_ID_LEN; i++) {
        buffer[i] = EEPROM.read(UNIT_ID_ADDR + i);
    }
    EEPROM.end();
    return String(buffer);
}

String loadDeviceType() {
    EEPROM.begin(EEPROM_SIZE);
    char buffer[MAX_DEVICE_TYPE_LEN];
    for (int i = 0; i < MAX_DEVICE_TYPE_LEN; i++) {
        buffer[i] = EEPROM.read(DEVICE_TYPE_ADDR + i);
    }
    EEPROM.end();
    return String(buffer);
}

void saveUnitID(const String &unit_id) {
    EEPROM.begin(EEPROM_SIZE);
    for (int i = 0; i < unit_id.length(); i++) {
        EEPROM.write(UNIT_ID_ADDR + i, unit_id[i]);
    }
    EEPROM.write(UNIT_ID_ADDR + unit_id.length(), '\0');
    EEPROM.commit();
    EEPROM.end();
}

void saveDeviceType(const String &device_type) {
    EEPROM.begin(EEPROM_SIZE);
    for (int i = 0; i < device_type.length(); i++) {
        EEPROM.write(DEVICE_TYPE_ADDR + i, device_type[i]);
    }
    EEPROM.write(DEVICE_TYPE_ADDR + device_type.length(), '\0');
    EEPROM.commit();
    EEPROM.end();
}

void clearProvisioning() {
    EEPROM.begin(EEPROM_SIZE);
    for (int i = UNIT_ID_ADDR; i < UNIT_ID_ADDR + MAX_UNIT_ID_LEN; i++) {
        EEPROM.write(i, 0);
    }
    for (int i = DEVICE_TYPE_ADDR; i < DEVICE_TYPE_ADDR + MAX_DEVICE_TYPE_LEN; i++) {
        EEPROM.write(i, 0);
    }
    EEPROM.commit();
    EEPROM.end();
}

bool isProvisioned() {
    String unit_id = loadUnitID();
    return unit_id.length() > 0;
}
