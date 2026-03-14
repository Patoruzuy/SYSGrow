#ifndef WEB_SERVER_H
#define WEB_SERVER_H

#include <Arduino.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <AsyncTCP.h>
#include <ArduinoJson.h>
#include <SPIFFS.h>

// Web Server Configuration
#define WEB_SERVER_PORT           80
#define WEB_SOCKET_PORT           81
#define WEB_MAX_CLIENTS           4
#define WEB_AUTH_TIMEOUT          3600000  // 1 hour
#define WEB_SESSION_TIMEOUT       1800000  // 30 minutes
#define WEB_API_RATE_LIMIT        100      // requests per minute

// Web Server States
enum WebServerState {
    WEB_DISABLED,
    WEB_INITIALIZING,
    WEB_RUNNING,
    WEB_ERROR,
    WEB_MAINTENANCE
};

// Authentication levels
enum AuthLevel {
    AUTH_NONE = 0,
    AUTH_READ = 1,
    AUTH_WRITE = 2,
    AUTH_ADMIN = 3
};

// API Endpoints
struct APIEndpoint {
    String path;
    HTTPMethod method;
    AuthLevel auth_required;
    std::function<void(AsyncWebServerRequest*)> handler;
};

// Client Session
struct ClientSession {
    String session_id;
    String client_ip;
    AuthLevel auth_level;
    unsigned long created_time;
    unsigned long last_activity;
    bool is_active;
};

// Web Server Statistics
struct WebServerStats {
    uint32_t total_requests = 0;
    uint32_t successful_requests = 0;
    uint32_t failed_requests = 0;
    uint32_t auth_attempts = 0;
    uint32_t auth_failures = 0;
    uint32_t websocket_connections = 0;
    uint32_t api_calls = 0;
    unsigned long uptime_start = 0;
};

// Rate limiting
struct RateLimitEntry {
    String client_ip;
    uint32_t request_count;
    unsigned long window_start;
};

// Global variables
extern WebServerState web_server_state;
extern WebServerStats web_stats;
extern AsyncWebServer web_server;
extern AsyncWebSocket web_socket;
extern std::vector<ClientSession> active_sessions;
extern std::vector<RateLimitEntry> rate_limit_table;
extern bool web_authentication_enabled;
extern String web_admin_username;
extern String web_admin_password;

// Web Server Functions
void setupWebServer();
void webServerLoop();
bool startWebServer();
void stopWebServer();
bool isWebServerRunning();

// Authentication Functions
bool authenticateRequest(AsyncWebServerRequest* request, AuthLevel required_level);
String createSession(const String& client_ip, AuthLevel auth_level);
bool validateSession(const String& session_id);
void cleanupExpiredSessions();
AuthLevel getSessionAuthLevel(const String& session_id);
void logoutSession(const String& session_id);

// Rate Limiting
bool checkRateLimit(const String& client_ip);
void updateRateLimit(const String& client_ip);
void cleanupRateLimitTable();

// Request Handlers
void handleRoot(AsyncWebServerRequest* request);
void handleLogin(AsyncWebServerRequest* request);
void handleLogout(AsyncWebServerRequest* request);
void handleAPI(AsyncWebServerRequest* request);
void handleNotFound(AsyncWebServerRequest* request);

// API Handlers
void handleAPIStatus(AsyncWebServerRequest* request);
void handleAPISensors(AsyncWebServerRequest* request);
void handleAPIConfig(AsyncWebServerRequest* request);
void handleAPICalibration(AsyncWebServerRequest* request);
void handleAPIPower(AsyncWebServerRequest* request);
void handleAPINetwork(AsyncWebServerRequest* request);
void handleAPISystem(AsyncWebServerRequest* request);
void handleAPILog(AsyncWebServerRequest* request);

// WebSocket Functions
void setupWebSocket();
void handleWebSocketEvent(AsyncWebSocket* server, AsyncWebSocketClient* client, 
                         AwsEventType type, void* arg, uint8_t* data, size_t len);
void broadcastSensorData();
void broadcastStatus();
void sendWebSocketMessage(uint32_t client_id, const String& message);
void sendWebSocketMessage(AsyncWebSocketClient* client, const String& message);

// File System Functions
bool setupFileSystem();
String getContentType(const String& filename);
bool handleFileRequest(AsyncWebServerRequest* request);

// Security Functions
String generateSessionId();
String hashPassword(const String& password);
bool verifyPassword(const String& password, const String& hash);
void setupCORS(AsyncWebServerResponse* response);
bool isValidJSON(const String& json);

// Utility Functions
String getClientIP(AsyncWebServerRequest* request);
void logWebRequest(AsyncWebServerRequest* request, int response_code);
String formatWebResponse(bool success, const String& message, const JsonDocument& data = JsonDocument());
WebServerStats getWebServerStatistics();
void logWebServerStatistics();
String getWebServerStateString();

// HTML Templates (if not using SPIFFS)
extern const char* web_index_html;
extern const char* web_login_html;
extern const char* web_config_html;
extern const char* web_sensors_html;
extern const char* web_style_css;
extern const char* web_script_js;

// Configuration
struct WebServerConfig {
    bool enable_authentication = true;
    bool enable_cors = true;
    bool enable_rate_limiting = true;
    bool enable_websocket = true;
    bool enable_file_system = true;
    String admin_username = "admin";
    String admin_password = "sysgrow123";
    uint16_t port = WEB_SERVER_PORT;
    uint16_t websocket_port = WEB_SOCKET_PORT;
    uint8_t max_clients = WEB_MAX_CLIENTS;
};

extern WebServerConfig web_config;

// API Response helpers
void sendJSONResponse(AsyncWebServerRequest* request, int code, const JsonDocument& doc);
void sendErrorResponse(AsyncWebServerRequest* request, int code, const String& message);
void sendSuccessResponse(AsyncWebServerRequest* request, const String& message, const JsonDocument& data = JsonDocument());

// Form data helpers
bool parseJSONBody(AsyncWebServerRequest* request, JsonDocument& doc);
String getFormParameter(AsyncWebServerRequest* request, const String& name, const String& default_value = "");

#endif // WEB_SERVER_H