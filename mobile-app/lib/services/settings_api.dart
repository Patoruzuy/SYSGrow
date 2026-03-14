import 'dart:convert';

import 'package:http/http.dart' as http;

import '../environment.dart';

class SettingsApi {
  SettingsApi({http.Client? client, String? baseUrl})
      : _client = client ?? http.Client(),
        _baseUrl = baseUrl ?? EnvironmentConfig.apiBaseUrl;

  final http.Client _client;
  final String _baseUrl;

  Uri _uri(String path) => Uri.parse('$_baseUrl$path');

  Future<Map<String, dynamic>?> _getJson(String path) async {
    final response = await _client.get(_uri(path));
    if (response.statusCode == 404) return null;
    _ensureSuccess(response);
    if (response.body.isEmpty) return null;
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> _putJson(
    String path,
    Map<String, dynamic> payload,
  ) async {
    final response = await _client.put(
      _uri(path),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    _ensureSuccess(response);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> _postJson(
    String path,
    Map<String, dynamic> payload,
  ) async {
    final response = await _client.post(
      _uri(path),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    );
    _ensureSuccess(response);
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  void _ensureSuccess(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    final message = response.body.isNotEmpty
        ? (jsonDecode(response.body)['error'] ?? response.body)
        : 'Request failed (${response.statusCode})';
    throw SettingsApiException(message.toString(), response.statusCode);
  }

  Future<Map<String, dynamic>?> fetchEnvironment() =>
      _getJson('/api/settings/environment');

  Future<Map<String, dynamic>> updateEnvironment({
    required double temperatureThreshold,
    required double humidityThreshold,
    required double soilMoistureThreshold,
  }) {
    return _putJson('/api/settings/environment', {
      'temperature_threshold': temperatureThreshold,
      'humidity_threshold': humidityThreshold,
      'soil_moisture_threshold': soilMoistureThreshold,
    });
  }

  // Device schedules now use the Growth API with unit_id
  // Use fetchDeviceSchedules and updateDeviceSchedule instead
  
  Future<Map<String, dynamic>?> fetchDeviceSchedules(int unitId) =>
      _getJson('/api/growth/v2/units/$unitId/schedules');

  Future<Map<String, dynamic>?> fetchDeviceSchedule(int unitId, String deviceType) =>
      _getJson('/api/growth/units/$unitId/schedules/$deviceType');

  Future<Map<String, dynamic>> updateDeviceSchedule({
    required int unitId,
    required String deviceType,
    required String startTime,
    required String endTime,
    bool enabled = true,
  }) {
    return _postJson('/api/growth/v2/units/$unitId/schedules', {
      'device_type': deviceType,
      'start_time': startTime,
      'end_time': endTime,
      'enabled': enabled,
    });
  }

  Future<void> deleteDeviceSchedule(int unitId, String deviceType) async {
    final response = await _client.delete(
      _uri('/api/growth/v2/units/$unitId/schedules/$deviceType'),
    );
    _ensureSuccess(response);
  }

  Future<Map<String, dynamic>?> fetchHotspot() =>
      _getJson('/api/settings/hotspot');

  Future<Map<String, dynamic>> updateHotspot({
    required String ssid,
    String? password,
  }) {
    final payload = <String, dynamic>{'ssid': ssid};
    if (password != null && password.isNotEmpty) {
      payload['password'] = password;
    }
    return _putJson('/api/settings/hotspot', payload);
  }

  Future<Map<String, dynamic>?> fetchCamera() =>
      _getJson('/api/settings/camera');

  Future<Map<String, dynamic>> updateCamera({
    required String cameraType,
    String? ipAddress,
    int? usbCamIndex,
    int? resolution,
    int? quality,
    int? brightness,
    int? contrast,
    int? saturation,
    int? flip,
  }) {
    final payload = <String, dynamic>{
      'camera_type': cameraType,
    };
    void addIfNotNull(String key, Object? value) {
      if (value != null) payload[key] = value;
    }

    addIfNotNull('ip_address', ipAddress?.isNotEmpty == true ? ipAddress : null);
    addIfNotNull('usb_cam_index', usbCamIndex);
    addIfNotNull('resolution', resolution);
    addIfNotNull('quality', quality);
    addIfNotNull('brightness', brightness);
    addIfNotNull('contrast', contrast);
    addIfNotNull('saturation', saturation);
    addIfNotNull('flip', flip);

    return _putJson('/api/settings/camera', payload);
  }
}

class SettingsApiException implements Exception {
  SettingsApiException(this.message, this.statusCode);

  final String message;
  final int statusCode;

  @override
  String toString() => 'SettingsApiException($statusCode): $message';
}
