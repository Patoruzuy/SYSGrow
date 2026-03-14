#include "eeprom_utils.h"
#include "crypto_utils.h"
#include "logging.h"
#include <EEPROM.h>

void loadWiFiConfig(char* ssid, char* password) {
    EEPROM.begin(EEPROM_SIZE);
    char encrypted_ssid[32], encrypted_password[32];

    for (int i = 0; i < 32; i++) {
        encrypted_ssid[i] = EEPROM.read(i);
        encrypted_password[i] = EEPROM.read(i + 32);
    }

    decryptAES(encrypted_ssid, ssid, 32);
    decryptAES(encrypted_password, password, 32);

    EEPROM.end();
    LOG_INFO("Wi-Fi Config Loaded.");
}

void saveWiFiConfig(const char* ssid, const char* password) {
    EEPROM.begin(EEPROM_SIZE);
    char encrypted_ssid[32], encrypted_password[32];

    encryptAES(ssid, encrypted_ssid, 32);
    encryptAES(password, encrypted_password, 32);

    for (int i = 0; i < 32; i++) {
        EEPROM.write(i, encrypted_ssid[i]);
        EEPROM.write(i + 32, encrypted_password[i]);
    }

    EEPROM.commit();
    EEPROM.end();
    LOG_INFO("Wi-Fi Config Saved.");
}
