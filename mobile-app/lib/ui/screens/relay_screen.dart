import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../services/mqtt_service.dart';
import '../../services/ble_service.dart';
import '../../providers/relay_provider.dart';
import '../../providers/connection_provider.dart';

class RelayScreen extends StatefulWidget {
  @override
  _RelayScreenState createState() => _RelayScreenState();
}

class _RelayScreenState extends State<RelayScreen> {
  final mqttService = MQTTService();
  final bleService = BLEService();
  bool isUsingWiFi = true;
  List<int> relayPins = [2, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21];

  @override
  void initState() {
    super.initState();
    mqttService.connect();
  }

  void toggleRelay(int pin, bool state) {
    if (isUsingWiFi) {
      mqttService.sendRelayCommand(pin, state);
    } else {
      bleService.sendRelayCommand(pin, state);
    }
  }

  void switchMode() {
    setState(() {
      isUsingWiFi = !isUsingWiFi;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text("Relay Control")),
      body: Column(
        children: [
          SwitchListTile(
            title: Text(isUsingWiFi ? "Wi-Fi Mode (MQTT)" : "Bluetooth Mode (BLE)"),
            value: isUsingWiFi,
            onChanged: (_) => switchMode(),
          ),
          Expanded(
            child: ListView.builder(
              itemCount: relayPins.length,
              itemBuilder: (context, index) {
                int pin = relayPins[index];
                return ListTile(
                  title: Text("Relay GPIO $pin"),
                  trailing: Switch(
                    value: Provider.of<RelayProvider>(context).getRelayState(pin),
                    onChanged: (state) {
                      toggleRelay(pin, state);
                      Provider.of<RelayProvider>(context, listen: false).setRelayState(pin, state);
                    },
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
