#include "ble_service.h"
#include "config.h"

void setupBLE() {
    BLEDevice::init("ESP32-C6-Relay");
    BLEServer *bleServer = BLEDevice::createServer();
    BLEService *relayService = bleServer->createService(BLE_SERVICE_UUID);
    BLECharacteristic *relayCharacteristic = relayService->createCharacteristic(
        BLE_CHARACTERISTIC_UUID, BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_WRITE
    );

    relayCharacteristic->setCallbacks(new RelayBLECallbacks());
    relayService->start();
    BLEAdvertising *advertising = BLEDevice::getAdvertising();
    advertising->addServiceUUID(BLE_SERVICE_UUID);
    advertising->start();

    isBLEActive = true;
    Serial.println("BLE Ready!");
}
