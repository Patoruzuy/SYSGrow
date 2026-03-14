#ifndef BLE_SERVICE_H
#define BLE_SERVICE_H

#include "config.h"

void setupBLE();

class RelayBLECallbacks : public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic* pCharacteristic) override;
};

#endif
