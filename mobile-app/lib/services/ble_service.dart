import 'package:flutter_blue_plus/flutter_blue_plus.dart';

class BLEService {
  static const String relayServiceUUID = "12345678-1234-5678-1234-56789abcdef0";
  static const String relayCharUUID = "12345678-1234-5678-1234-56789abcdef1";

  late BluetoothDevice device;
  late BluetoothCharacteristic characteristic;

  Future<void> connect(BluetoothDevice selectedDevice) async {
    device = selectedDevice;
    await device.connect();
    var services = await device.discoverServices();
    for (var service in services) {
      if (service.uuid.toString() == relayServiceUUID) {
        for (var char in service.characteristics) {
          if (char.uuid.toString() == relayCharUUID) {
            characteristic = char;
          }
        }
      }
    }
  }

  Future<void> sendRelayCommand(int pin, bool state) async {
    String command = "$pin,${state ? 1 : 0}";
    await characteristic.write(command.codeUnits);
  }
}
