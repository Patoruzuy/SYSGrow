import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;

import '../environment.dart';

class SensorStatusDashboard extends StatefulWidget {
  @override
  _SensorStatusDashboardState createState() => _SensorStatusDashboardState();
}

class _SensorStatusDashboardState extends State<SensorStatusDashboard> {
  Map<String, dynamic> sensorData = {};
  bool loading = true;

  @override
  void initState() {
    super.initState();
    fetchStatus();
    // Auto-refresh every 30s
    Future.periodic(Duration(seconds: 30), (_) => fetchStatus());
  }

  Future<void> fetchStatus() async {
    try {
      final response =
          await http.get(Uri.parse('${EnvironmentConfig.apiBaseUrl}/status'));
      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          sensorData = data['sensors'] ?? {};
          loading = false;
        });
      }
    } catch (e) {
      print('Error fetching status: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) return Center(child: CircularProgressIndicator());

    return ListView(
      children: sensorData.entries.map((entry) {
        final name = entry.key;
        final status = entry.value;
        return ListTile(
          title: Text(name),
          subtitle: Text("Last seen: ${status['last_seen']}"),
          trailing: Text(
            status['status'],
            style: TextStyle(
              color: status['status'] == 'online' ? Colors.green : Colors.red,
              fontWeight: FontWeight.bold,
            ),
          ),
        );
      }).toList(),
    );
  }
}
