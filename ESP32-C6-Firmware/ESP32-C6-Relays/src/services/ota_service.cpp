#include "ota_service.h"
#include "logging.h"
#include "config.h"

void performOTA() {
    std::string latestVersion = getLatestFirmwareVersion();
    if (latestVersion == FW_VERSION) {
        LOG_INFO("No update needed. Already on latest version.");
        return;
    }

    LOG_INFO("Fetching firmware from OTA server...");
    HTTPClient http;
    http.begin(ota_url);
    int httpCode = http.GET();

    if (httpCode == HTTP_CODE_OK) {
        WiFiClient* stream = http.getStreamPtr();
        if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
            LOG_ERROR("Update initialization failed.");
            return;
        }

        size_t written = Update.writeStream(*stream);
        if (written == Update.size()) {
            LOG_INFO("Firmware update successful. Restarting...");
            Update.end();
            ESP.restart();
        } else {
            LOG_ERROR("Firmware update failed. Written bytes do not match.");
        }
    } else {
        LOG_ERROR("Failed to fetch firmware. HTTP Code: " + String(httpCode));
    }

    http.end();
}
