#include <ArduinoJson.h>
#include "Crypto.h"

extern const byte aes_key[16];  // Must match what your Python/Flask app uses

void wifi_config(byte* payload, unsigned int length) {
    char decrypted[64];  // Buffer for decrypted output
    Crypto::AES_Decrypt(aes_key, payload, decrypted, length);

    DynamicJsonDocument doc(256);
    DeserializationError error = deserializeJson(doc, decrypted);
    
    if (error) {
        Serial.println("Failed to parse decrypted Wi-Fi credentials.");
        return;
    }

    const char* new_ssid = doc["ssid"];
    const char* new_password = doc["password"];

    if (new_ssid && new_password) {
        Serial.printf("Updating Wi-Fi to SSID: %s\n", new_ssid);
        saveWiFiConfig(new_ssid, new_password);  // You must define this elsewhere
        ESP.restart();
    } else {
        Serial.println("Incomplete Wi-Fi config received.");
    }
}
