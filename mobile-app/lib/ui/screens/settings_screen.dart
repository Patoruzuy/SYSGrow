import 'package:flutter/material.dart';

import '../../services/settings_api.dart';

class SettingsScreen extends StatefulWidget {
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final SettingsApi _api = SettingsApi();

  final TextEditingController _temperatureController = TextEditingController();
  final TextEditingController _humidityController = TextEditingController();
  final TextEditingController _soilController = TextEditingController();

  final TextEditingController _lightStartController = TextEditingController();
  final TextEditingController _lightEndController = TextEditingController();

  final TextEditingController _fanStartController = TextEditingController();
  final TextEditingController _fanEndController = TextEditingController();

  final TextEditingController _hotspotSsidController = TextEditingController();
  final TextEditingController _hotspotPasswordController =
      TextEditingController();

  String _cameraType = 'esp32';
  final TextEditingController _cameraIpController = TextEditingController();
  final TextEditingController _cameraUsbIndexController =
      TextEditingController();
  final TextEditingController _cameraResolutionController =
      TextEditingController();
  final TextEditingController _cameraQualityController =
      TextEditingController();
  final TextEditingController _cameraBrightnessController =
      TextEditingController();
  final TextEditingController _cameraContrastController =
      TextEditingController();
  final TextEditingController _cameraSaturationController =
      TextEditingController();
  String _cameraFlip = '0';

  bool _loading = true;
  bool _hotspotPasswordRequired = true;
  String? _statusMessage;
  bool _statusError = false;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  @override
  void dispose() {
    _temperatureController.dispose();
    _humidityController.dispose();
    _soilController.dispose();
    _lightStartController.dispose();
    _lightEndController.dispose();
    _fanStartController.dispose();
    _fanEndController.dispose();
    _hotspotSsidController.dispose();
    _hotspotPasswordController.dispose();
    _cameraIpController.dispose();
    _cameraUsbIndexController.dispose();
    _cameraResolutionController.dispose();
    _cameraQualityController.dispose();
    _cameraBrightnessController.dispose();
    _cameraContrastController.dispose();
    _cameraSaturationController.dispose();
    super.dispose();
  }

  Future<void> _loadSettings() async {
    setState(() {
      _loading = true;
      _statusMessage = null;
    });

    try {
      final environment = await _api.fetchEnvironment();
      if (environment != null) {
        _temperatureController.text =
            environment['temperature_threshold']?.toString() ?? '';
        _humidityController.text =
            environment['humidity_threshold']?.toString() ?? '';
        _soilController.text =
            environment['soil_moisture_threshold']?.toString() ?? '';
      }

      final light = await _api.fetchLightSchedule();
      _lightStartController.text = light?['start_time'] ?? '08:00';
      _lightEndController.text = light?['end_time'] ?? '20:00';

      final fan = await _api.fetchFanSchedule();
      _fanStartController.text = fan?['start_time'] ?? '07:00';
      _fanEndController.text = fan?['end_time'] ?? '19:00';

      final hotspot = await _api.fetchHotspot();
      if (hotspot != null) {
        _hotspotSsidController.text = hotspot['ssid'] ?? '';
        _hotspotPasswordRequired =
            !(hotspot['password_present'] as bool? ?? false);
      } else {
        _hotspotPasswordRequired = true;
      }
      _hotspotPasswordController.clear();

      final camera = await _api.fetchCamera();
      if (camera != null) {
        _cameraType = camera['camera_type'] ?? 'esp32';
        _cameraIpController.text = camera['ip_address'] ?? '';
        _cameraUsbIndexController.text =
            camera['usb_cam_index']?.toString() ?? '';
        _cameraResolutionController.text =
            camera['resolution']?.toString() ?? '';
        _cameraQualityController.text =
            camera['quality']?.toString() ?? '';
        _cameraBrightnessController.text =
            camera['brightness']?.toString() ?? '';
        _cameraContrastController.text =
            camera['contrast']?.toString() ?? '';
        _cameraSaturationController.text =
            camera['saturation']?.toString() ?? '';
        _cameraFlip = (camera['flip']?.toString() ?? '0');
      } else {
        _cameraType = 'esp32';
        _cameraFlip = '0';
      }

      setState(() {
        _loading = false;
      });
    } on SettingsApiException catch (e) {
      setState(() {
        _loading = false;
        _statusMessage = e.message;
        _statusError = true;
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _statusMessage = e.toString();
        _statusError = true;
      });
    }
  }

  void _showStatus(String message, {bool error = false}) {
    setState(() {
      _statusMessage = message;
      _statusError = error;
    });
  }

  Future<void> _saveEnvironment() async {
    try {
      await _api.updateEnvironment(
        temperatureThreshold: double.parse(_temperatureController.text),
        humidityThreshold: double.parse(_humidityController.text),
        soilMoistureThreshold: double.parse(_soilController.text),
      );
      _showStatus('Environment thresholds saved.');
    } catch (e) {
      _showStatus('Failed to save environment thresholds: $e', error: true);
    }
  }

  Future<void> _saveLight() async {
    try {
      await _api.updateLightSchedule(
        startTime: _lightStartController.text,
        endTime: _lightEndController.text,
      );
      _showStatus('Light schedule saved.');
    } catch (e) {
      _showStatus('Failed to save light schedule: $e', error: true);
    }
  }

  Future<void> _saveFan() async {
    try {
      await _api.updateFanSchedule(
        startTime: _fanStartController.text,
        endTime: _fanEndController.text,
      );
      _showStatus('Fan schedule saved.');
    } catch (e) {
      _showStatus('Failed to save fan schedule: $e', error: true);
    }
  }

  Future<void> _saveHotspot() async {
    final ssid = _hotspotSsidController.text.trim();
    final password = _hotspotPasswordController.text.trim();
    if (ssid.isEmpty) {
      _showStatus('SSID is required.', error: true);
      return;
    }
    if (_hotspotPasswordRequired && password.isEmpty) {
      _showStatus('Password is required for initial setup.', error: true);
      return;
    }
    try {
      await _api.updateHotspot(
        ssid: ssid,
        password: password.isNotEmpty ? password : null,
      );
      _hotspotPasswordController.clear();
      _hotspotPasswordRequired = false;
      _showStatus('Hotspot settings saved.');
    } catch (e) {
      _showStatus('Failed to save hotspot settings: $e', error: true);
    }
  }

  Future<void> _saveCamera() async {
    try {
      int? parseInt(String text) =>
          text.trim().isEmpty ? null : int.tryParse(text.trim());

      await _api.updateCamera(
        cameraType: _cameraType,
        ipAddress: _cameraIpController.text.trim().isEmpty
            ? null
            : _cameraIpController.text.trim(),
        usbCamIndex: parseInt(_cameraUsbIndexController.text),
        resolution: parseInt(_cameraResolutionController.text),
        quality: parseInt(_cameraQualityController.text),
        brightness: parseInt(_cameraBrightnessController.text),
        contrast: parseInt(_cameraContrastController.text),
        saturation: parseInt(_cameraSaturationController.text),
        flip: int.tryParse(_cameraFlip),
      );
      _showStatus('Camera settings saved.');
    } catch (e) {
      _showStatus('Failed to save camera settings: $e', error: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Settings'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loading ? null : _loadSettings,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (_statusMessage != null)
                    Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: _statusError
                            ? Colors.red.withOpacity(0.1)
                            : Colors.green.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        _statusMessage!,
                        style: TextStyle(
                          color: _statusError ? Colors.red : Colors.green[800],
                        ),
                      ),
                    ),
                  _buildCard(
                    title: 'Environment Thresholds',
                    children: [
                      _buildNumberField(
                        controller: _temperatureController,
                        label: 'Temperature (°C)',
                      ),
                      _buildNumberField(
                        controller: _humidityController,
                        label: 'Humidity (%)',
                      ),
                      _buildNumberField(
                        controller: _soilController,
                        label: 'Soil moisture (%)',
                      ),
                      _buildActionButton(
                        label: 'Save Thresholds',
                        onPressed: _saveEnvironment,
                      ),
                    ],
                  ),
                  _buildCard(
                    title: 'Light Schedule',
                    children: [
                      _buildTimeField(
                        controller: _lightStartController,
                        label: 'Start time',
                      ),
                      _buildTimeField(
                        controller: _lightEndController,
                        label: 'End time',
                      ),
                      _buildActionButton(
                        label: 'Save Light Schedule',
                        onPressed: _saveLight,
                      ),
                    ],
                  ),
                  _buildCard(
                    title: 'Fan Schedule',
                    children: [
                      _buildTimeField(
                        controller: _fanStartController,
                        label: 'Start time',
                      ),
                      _buildTimeField(
                        controller: _fanEndController,
                        label: 'End time',
                      ),
                      _buildActionButton(
                        label: 'Save Fan Schedule',
                        onPressed: _saveFan,
                      ),
                    ],
                  ),
                  _buildCard(
                    title: 'Wi-Fi Hotspot',
                    children: [
                      _buildTextField(
                        controller: _hotspotSsidController,
                        label: 'SSID',
                      ),
                      _buildTextField(
                        controller: _hotspotPasswordController,
                        label: _hotspotPasswordRequired
                            ? 'Password (required)'
                            : 'Password (leave blank to keep current)',
                        obscureText: true,
                      ),
                      _buildActionButton(
                        label: 'Save Hotspot Settings',
                        onPressed: _saveHotspot,
                      ),
                    ],
                  ),
                  _buildCard(
                    title: 'Camera Settings',
                    children: [
                      DropdownButtonFormField<String>(
                        value: _cameraType,
                        items: const [
                          DropdownMenuItem(
                            value: 'esp32',
                            child: Text('ESP32 Wireless'),
                          ),
                          DropdownMenuItem(
                            value: 'usb',
                            child: Text('USB Camera'),
                          ),
                        ],
                        onChanged: (value) {
                          if (value == null) return;
                          setState(() {
                            _cameraType = value;
                          });
                        },
                        decoration: const InputDecoration(
                          labelText: 'Camera Type',
                        ),
                      ),
                      if (_cameraType == 'esp32')
                        _buildTextField(
                          controller: _cameraIpController,
                          label: 'ESP32 IP address',
                        ),
                      if (_cameraType == 'usb')
                        _buildTextField(
                          controller: _cameraUsbIndexController,
                          label: 'USB camera index',
                          keyboardType: TextInputType.number,
                        ),
                      _buildTextField(
                        controller: _cameraResolutionController,
                        label: 'Resolution',
                        keyboardType: TextInputType.number,
                      ),
                      _buildTextField(
                        controller: _cameraQualityController,
                        label: 'Quality',
                        keyboardType: TextInputType.number,
                      ),
                      _buildTextField(
                        controller: _cameraBrightnessController,
                        label: 'Brightness',
                        keyboardType: TextInputType.number,
                      ),
                      _buildTextField(
                        controller: _cameraContrastController,
                        label: 'Contrast',
                        keyboardType: TextInputType.number,
                      ),
                      _buildTextField(
                        controller: _cameraSaturationController,
                        label: 'Saturation',
                        keyboardType: TextInputType.number,
                      ),
                      DropdownButtonFormField<String>(
                        value: _cameraFlip,
                        items: const [
                          DropdownMenuItem(
                            value: '0',
                            child: Text('Normal'),
                          ),
                          DropdownMenuItem(
                            value: '1',
                            child: Text('Flipped'),
                          ),
                        ],
                        onChanged: (value) {
                          if (value == null) return;
                          setState(() {
                            _cameraFlip = value;
                          });
                        },
                        decoration: const InputDecoration(
                          labelText: 'Orientation',
                        ),
                      ),
                      _buildActionButton(
                        label: 'Save Camera Settings',
                        onPressed: _saveCamera,
                      ),
                    ],
                  ),
                ],
              ),
            ),
    );
  }

  Widget _buildCard({
    required String title,
    required List<Widget> children,
  }) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              title,
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            ...children,
          ],
        ),
      ),
    );
  }

  Widget _buildNumberField({
    required TextEditingController controller,
    required String label,
  }) {
    return _buildTextField(
      controller: controller,
      label: label,
      keyboardType: const TextInputType.numberWithOptions(decimal: true),
    );
  }

  Widget _buildTimeField({
    required TextEditingController controller,
    required String label,
  }) {
    return _buildTextField(
      controller: controller,
      label: label,
      keyboardType: TextInputType.datetime,
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    TextInputType keyboardType = TextInputType.text,
    bool obscureText = false,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: TextField(
        controller: controller,
        keyboardType: keyboardType,
        obscureText: obscureText,
        decoration: InputDecoration(
          labelText: label,
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }

  Widget _buildActionButton({
    required String label,
    required VoidCallback onPressed,
  }) {
    return Align(
      alignment: Alignment.centerRight,
      child: ElevatedButton(
        onPressed: onPressed,
        child: Text(label),
      ),
    );
  }
}
