#ifndef OTA_SERVICE_H
#define OTA_SERVICE_H

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <Update.h>
#include <ArduinoJson.h>

// OTA Configuration
#define OTA_UPDATE_URL            "https://api.sysgrow.com/firmware/"
#define OTA_CHECK_INTERVAL        3600000  // 1 hour
#define OTA_TIMEOUT               30000    // 30 seconds
#define OTA_BUFFER_SIZE           1024
#define OTA_MAX_RETRIES           3
#define OTA_PARTITION_SIZE        1048576  // 1MB

// OTA States
enum OTAState {
    OTA_IDLE,
    OTA_CHECKING,
    OTA_DOWNLOADING,
    OTA_INSTALLING,
    OTA_SUCCESS,
    OTA_ERROR,
    OTA_ROLLBACK
};

// OTA Error Codes
enum OTAError {
    OTA_ERROR_NONE = 0,
    OTA_ERROR_NETWORK = 1,
    OTA_ERROR_SERVER = 2,
    OTA_ERROR_DOWNLOAD = 3,
    OTA_ERROR_VERIFICATION = 4,
    OTA_ERROR_FLASH = 5,
    OTA_ERROR_PARTITION = 6,
    OTA_ERROR_ROLLBACK = 7,
    OTA_ERROR_TIMEOUT = 8,
    OTA_ERROR_INVALID_FIRMWARE = 9
};

// Firmware Information
struct FirmwareInfo {
    String version;
    String build_date;
    String build_hash;
    String download_url;
    size_t file_size;
    String checksum;
    String checksum_type;  // MD5, SHA256
    String release_notes;
    bool is_critical;
    bool is_beta;
};

// OTA Progress Information
struct OTAProgress {
    OTAState state;
    uint32_t bytes_downloaded;
    uint32_t total_bytes;
    uint8_t percentage;
    String current_operation;
    unsigned long start_time;
    unsigned long estimated_time_remaining;
};

// OTA Statistics
struct OTAStats {
    uint32_t update_checks = 0;
    uint32_t successful_updates = 0;
    uint32_t failed_updates = 0;
    uint32_t rollbacks = 0;
    unsigned long last_check_time = 0;
    unsigned long last_update_time = 0;
    String last_error_message = "";
    OTAError last_error_code = OTA_ERROR_NONE;
};

// OTA Configuration
struct OTAConfig {
    bool auto_update_enabled = false;
    bool check_for_updates = true;
    bool allow_beta_updates = false;
    bool require_manual_approval = true;
    String update_server_url = OTA_UPDATE_URL;
    String api_key = "";
    uint32_t check_interval = OTA_CHECK_INTERVAL;
    bool verify_signatures = true;
    bool backup_current_firmware = true;
};

// Global variables
extern OTAState ota_state;
extern OTAProgress ota_progress;
extern OTAStats ota_stats;
extern OTAConfig ota_config;
extern FirmwareInfo available_firmware;
extern FirmwareInfo current_firmware;
extern bool ota_update_available;
extern bool ota_update_in_progress;

// OTA Service Functions
void setupOTA();
void otaLoop();
bool checkForUpdate();
bool downloadAndInstallUpdate();
bool downloadFirmware(const String& url);
bool installFirmware();
void rollbackFirmware();

// Update Check Functions
bool queryUpdateServer();
bool parseUpdateResponse(const String& response);
bool validateFirmwareInfo(const FirmwareInfo& firmware);
bool compareVersions(const String& current_version, const String& available_version);

// Download Functions
bool initializeDownload(const String& url);
bool downloadChunk(uint8_t* buffer, size_t buffer_size, size_t& bytes_read);
bool verifyDownload(const String& checksum, const String& checksum_type);
void updateDownloadProgress(uint32_t bytes_downloaded, uint32_t total_bytes);

// Installation Functions
bool prepareInstallation();
bool writeFlashChunk(const uint8_t* data, size_t size);
bool finalizeInstallation();
bool verifyInstallation();
void handleInstallationError(OTAError error);

// Security Functions
bool verifyFirmwareSignature(const uint8_t* firmware_data, size_t size);
bool validateCertificate();
String calculateChecksum(const uint8_t* data, size_t size, const String& algorithm);
bool isSignedFirmware(const uint8_t* data, size_t size);

// Backup and Recovery
bool createFirmwareBackup();
bool restoreFromBackup();
bool validateBackup();
void cleanupOldBackups();

// Configuration Functions
void setOTAConfig(const OTAConfig& config);
OTAConfig getOTAConfig();
void saveOTAConfig();
void loadOTAConfig();
void resetOTAConfig();

// Progress and Status Functions
OTAProgress getOTAProgress();
OTAStats getOTAStatistics();
String getOTAStateString();
String getOTAErrorString(OTAError error);
void logOTAStatistics();

// Callback Functions
typedef void (*OTAProgressCallback)(const OTAProgress& progress);
typedef void (*OTACompleteCallback)(bool success, const String& message);
typedef void (*OTAErrorCallback)(OTAError error, const String& message);

void setOTAProgressCallback(OTAProgressCallback callback);
void setOTACompleteCallback(OTACompleteCallback callback);
void setOTAErrorCallback(OTAErrorCallback callback);

// Manual Update Functions
bool startManualUpdate(const String& firmware_url);
bool startManualUpdateFromLocal(const uint8_t* firmware_data, size_t size);
void cancelUpdate();
bool pauseUpdate();
bool resumeUpdate();

// System Integration
bool isOTAInProgress();
bool isUpdateAvailable();
void scheduleUpdateCheck();
void scheduleUpdate(unsigned long delay_ms);
bool isOTASafeMode();
void enterOTASafeMode();
void exitOTASafeMode();

// Utility Functions
String getCurrentFirmwareVersion();
String getAvailableFirmwareVersion();
size_t getFreeFlashSpace();
bool hasEnoughSpace(size_t required_space);
void printOTAStatus();
String formatBytes(size_t bytes);
String formatDuration(unsigned long duration_ms);

// Network Helpers
bool isNetworkAvailable();
bool isServerReachable(const String& url);
HTTPClient createSecureClient();
bool downloadFile(const String& url, const String& filename);

// File System Helpers
bool saveToFile(const String& filename, const uint8_t* data, size_t size);
bool loadFromFile(const String& filename, uint8_t* buffer, size_t buffer_size, size_t& bytes_read);
bool deleteFile(const String& filename);
bool fileExists(const String& filename);
size_t getFileSize(const String& filename);

#endif // OTA_SERVICE_H