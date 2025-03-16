import 'package:flutter/material.dart';
import 'mdns_service.dart';
import 'device_storage.dart';

class DiscoverDevicesScreen extends StatefulWidget {
  @override
  _DiscoverDevicesScreenState createState() => _DiscoverDevicesScreenState();
}

class _DiscoverDevicesScreenState extends State<DiscoverDevicesScreen> {
  List<Map<String, String>> devices = [];

  @override
  void initState() {
    super.initState();
    _startDiscovery();
  }

  void _startDiscovery() {
    MDNSService().startDiscovery((name, ip) {
      setState(() {
        devices.add({"name": name, "ip": ip});
      });
    });
  }

  void _addDevice(String name, String ip) {
    DeviceStorage.saveDevice(name, ip);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Device $name added!")));
    Navigator.pop(context);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text("Discover ESP32 Devices")),
      body: ListView(
        children: devices.map((device) {
          return ListTile(
            title: Text(device["name"]!),
            subtitle: Text("IP: ${device["ip"]}"),
            trailing: ElevatedButton(
              onPressed: () => _addDevice(device["name"]!, device["ip"]!),
              child: Text("Add"),
            ),
          );
        }).toList(),
      ),
    );
  }
}
