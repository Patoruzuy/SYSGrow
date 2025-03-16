#include "ble_service.h"
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>

#define SERVICE_UUID        "12345678-1234-5678-1234-56789abcdef0"
#define CHARACTERISTIC_UUID "12345678-1234-5678-1234-56789abcdef1"

BLEServer* pServer;
BLECharacteristic* pCharacteristic;

void setupBLE() {
    Serial.println("Setting up BLE for ESP32-C6-Sensors...");
    BLEDevice::init("ESP32-C6-Sensors");
    pServer = BLEDevice::createServer();
    BLEService *pService = pServer->createService(SERVICE_UUID);

    pCharacteristic = pService->createCharacteristic(
                        CHARACTERISTIC_UUID,
                        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);

    pService->start();
    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->start();
}

void bleLoop() {
    float temperature = readTemperature();
    float humidity = readHumidity();
    String sensorData = "Temp: " + String(temperature) + "C, Hum: " + String(humidity) + "%";
    pCharacteristic->setValue(sensorData.c_str());
    pCharacteristic->notify();
    Serial.println("BLE Data Sent: " + sensorData);
    delay(5000);
}