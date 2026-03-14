import 'package:flutter/material.dart';
import 'dart:convert';
import 'package:http/http.dart' as http;

class HarvestScreen extends StatefulWidget {
  @override
  State<HarvestScreen> createState() => _HarvestScreenState();
}

class _HarvestScreenState extends State<HarvestScreen> {
  List<dynamic> _units = [];
  List<dynamic> _plants = [];
  int? _selectedUnitId;
  int? _selectedPlantId;
  Map<String, dynamic>? _plantInfo;
  Map<String, dynamic>? _harvestReport;
  bool _isLoading = false;
  bool _showReport = false;
  
  // Form controllers
  final TextEditingController _weightController = TextEditingController();
  final TextEditingController _notesController = TextEditingController();
  int _qualityRating = 5;
  bool _deletePlantData = false;

  @override
  void initState() {
    super.initState();
    _loadUnits();
  }

  Future<void> _loadUnits() async {
    setState(() => _isLoading = true);
    try {
      final response = await http.get(Uri.parse('${Environment.baseUrl}/api/units'));
      if (response.statusCode == 200) {
        setState(() {
          _units = json.decode(response.body);
          _isLoading = false;
        });
      }
    } catch (e) {
      _showError('Failed to load growth units: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _loadPlantsForUnit(int unitId) async {
    setState(() => _isLoading = true);
    try {
      final response = await http.get(Uri.parse('${Environment.baseUrl}/api/units/$unitId/plants'));
      if (response.statusCode == 200) {
        setState(() {
          _plants = json.decode(response.body);
          _selectedPlantId = null;
          _plantInfo = null;
          _isLoading = false;
        });
      }
    } catch (e) {
      _showError('Failed to load plants: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _loadPlantInfo(int plantId) async {
    setState(() => _isLoading = true);
    try {
      final response = await http.get(Uri.parse('${Environment.baseUrl}/api/plants/$plantId'));
      if (response.statusCode == 200) {
        setState(() {
          _plantInfo = json.decode(response.body);
          _isLoading = false;
        });
      }
    } catch (e) {
      _showError('Failed to load plant info: $e');
      setState(() => _isLoading = false);
    }
  }

  Future<void> _generateHarvestReport() async {
    if (_weightController.text.isEmpty) {
      _showError('Please enter harvest weight');
      return;
    }

    setState(() => _isLoading = true);
    try {
      final response = await http.post(
        Uri.parse('${Environment.baseUrl}/api/plants/$_selectedPlantId/harvest'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'harvest_weight_grams': double.parse(_weightController.text),
          'quality_rating': _qualityRating,
          'notes': _notesController.text,
          'delete_plant_data': _deletePlantData,
        }),
      );

      if (response.statusCode == 200) {
        final result = json.decode(response.body);
        setState(() {
          _harvestReport = result['harvest_report'] ?? result;
          _showReport = true;
          _isLoading = false;
        });
      } else {
        throw Exception('Failed to generate harvest report');
      }
    } catch (e) {
      _showError('Failed to generate harvest report: $e');
      setState(() => _isLoading = false);
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: Colors.red),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('🌾 Harvest Report'),
        actions: [
          if (_showReport)
            IconButton(
              icon: const Icon(Icons.add),
              onPressed: () {
                setState(() {
                  _showReport = false;
                  _harvestReport = null;
                  _weightController.clear();
                  _notesController.clear();
                  _qualityRating = 5;
                });
              },
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _showReport
              ? _buildReportView()
              : _buildHarvestForm(),
    );
  }

  Widget _buildHarvestForm() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Unit Selection
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('Select Growth Unit', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  DropdownButton<int>(
                    isExpanded: true,
                    value: _selectedUnitId,
                    hint: const Text('Choose a unit...'),
                    items: _units.map((unit) {
                      return DropdownMenuItem<int>(
                        value: unit['unit_id'],
                        child: Text(unit['name'] ?? 'Unit ${unit['unit_id']}'),
                      );
                    }).toList(),
                    onChanged: (value) {
                      setState(() {
                        _selectedUnitId = value;
                        if (value != null) _loadPlantsForUnit(value);
                      });
                    },
                  ),
                ],
              ),
            ),
          ),

          if (_plants.isNotEmpty) ...[
            const SizedBox(height: 16),
            // Plant Selection
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Select Plant to Harvest', style: TextStyle(fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    DropdownButton<int>(
                      isExpanded: true,
                      value: _selectedPlantId,
                      hint: const Text('Choose a plant...'),
                      items: _plants.map((plant) {
                        return DropdownMenuItem<int>(
                          value: plant['plant_id'],
                          child: Text('${plant['name']} (${plant['current_stage']})'),
                        );
                      }).toList(),
                      onChanged: (value) {
                        setState(() {
                          _selectedPlantId = value;
                          if (value != null) _loadPlantInfo(value);
                        });
                      },
                    ),
                  ],
                ),
              ),
            ),
          ],

          if (_plantInfo != null) ...[
            const SizedBox(height: 16),
            // Plant Info Card
            Card(
              color: Colors.blue[50],
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.eco, color: Colors.green),
                        const SizedBox(width: 8),
                        Text(
                          _plantInfo!['name'] ?? 'Unknown',
                          style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ],
                    ),
                    const Divider(),
                    _buildInfoRow('Type', _plantInfo!['plant_type'] ?? 'N/A'),
                    _buildInfoRow('Stage', _plantInfo!['current_stage'] ?? 'N/A'),
                    _buildInfoRow('Days Growing', '${_plantInfo!['days_in_stage'] ?? 'N/A'}'),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),
            // Harvest Input Form
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Record Harvest', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 16),
                    
                    TextField(
                      controller: _weightController,
                      decoration: const InputDecoration(
                        labelText: 'Harvest Weight (grams) *',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.scale),
                      ),
                      keyboardType: TextInputType.number,
                    ),
                    
                    const SizedBox(height: 16),
                    const Text('Quality Rating', style: TextStyle(fontWeight: FontWeight.bold)),
                    Slider(
                      value: _qualityRating.toDouble(),
                      min: 1,
                      max: 5,
                      divisions: 4,
                      label: '${"⭐" * _qualityRating} ($_qualityRating)',
                      onChanged: (value) {
                        setState(() => _qualityRating = value.round());
                      },
                    ),
                    Center(
                      child: Text(
                        "${"⭐" * _qualityRating} ${_getRatingLabel(_qualityRating)}",
                        style: const TextStyle(fontSize: 16),
                      ),
                    ),
                    
                    const SizedBox(height: 16),
                    SwitchListTile(
                      title: const Text('Delete plant data after harvest'),
                      subtitle: const Text('Remove plant-specific records (keeps shared environmental data)'),
                      value: _deletePlantData,
                      onChanged: (value) {
                        setState(() => _deletePlantData = value);
                      },
                    ),
                    
                    const SizedBox(height: 16),
                    TextField(
                      controller: _notesController,
                      decoration: const InputDecoration(
                        labelText: 'Notes (optional)',
                        border: OutlineInputBorder(),
                        prefixIcon: Icon(Icons.notes),
                      ),
                      maxLines: 3,
                    ),
                    
                    const SizedBox(height: 24),
                    ElevatedButton.icon(
                      onPressed: _generateHarvestReport,
                      icon: const Icon(Icons.assessment),
                      label: const Text('Generate Harvest Report'),
                      style: ElevatedButton.styleFrom(
                        minimumSize: const Size.fromHeight(50),
                        backgroundColor: Colors.green,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildReportView() {
    if (_harvestReport == null) return const SizedBox();

    final yield_ = _harvestReport!['yield'];
    final energy = _harvestReport!['energy_consumption'];
    final efficiency = _harvestReport!['efficiency_metrics'];
    final lifecycle = _harvestReport!['lifecycle'];

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Summary Cards
          Row(
            children: [
              Expanded(child: _buildSummaryCard('Weight', '${yield_['weight_grams'].toStringAsFixed(1)}g', Icons.scale, Colors.green)),
              const SizedBox(width: 8),
              Expanded(child: _buildSummaryCard('Energy', '${energy['total_kwh'].toStringAsFixed(2)}kWh', Icons.bolt, Colors.orange)),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(child: _buildSummaryCard('Efficiency', '${efficiency['grams_per_kwh'].toStringAsFixed(2)}g/kWh', Icons.trending_up, Colors.blue)),
              const SizedBox(width: 8),
              Expanded(child: _buildSummaryCard('Cost', '\$${energy['total_cost'].toStringAsFixed(2)}', Icons.attach_money, Colors.red)),
            ],
          ),

          const SizedBox(height: 16),
          // Lifecycle Card
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.calendar_today, color: Colors.blue),
                      SizedBox(width: 8),
                      Text('Lifecycle Timeline', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                    ],
                  ),
                  const Divider(),
                  ..._buildLifecycleStages(lifecycle['stages']),
                  const SizedBox(height: 8),
                  Text(
                    'Total: ${lifecycle['total_days']} days',
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),
          // Energy Chart
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.bar_chart, color: Colors.orange),
                      SizedBox(width: 8),
                      Text('Energy by Stage', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                    ],
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    height: 200,
                    child: _buildEnergyChart(energy['by_stage']),
                  ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16),
          // Efficiency Metrics
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(Icons.speed, color: Colors.green),
                      SizedBox(width: 8),
                      Text('Efficiency Metrics', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                    ],
                  ),
                  const Divider(),
                  _buildEfficiencyBadge(efficiency['energy_efficiency_rating']),
                  const SizedBox(height: 8),
                  _buildInfoRow('Yield Efficiency', '${efficiency['grams_per_kwh'].toStringAsFixed(2)} g/kWh'),
                  _buildInfoRow('Cost per Gram', '\$${efficiency['cost_per_gram'].toStringAsFixed(3)}'),
                  _buildInfoRow('Cost per Pound', '\$${efficiency['cost_per_pound'].toStringAsFixed(2)}'),
                ],
              ),
            ),
          ),

          if (_harvestReport!['recommendations'] != null) ...[
            const SizedBox(height: 16),
            Card(
              color: Colors.blue[50],
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.lightbulb, color: Colors.amber),
                        SizedBox(width: 8),
                        Text('Recommendations', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                      ],
                    ),
                    const Divider(),
                    ..._buildRecommendations(_harvestReport!['recommendations']),
                  ],
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildSummaryCard(String title, String value, IconData icon, Color color) {
    return Card(
      elevation: 4,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            Icon(icon, color: color, size: 32),
            const SizedBox(height: 8),
            Text(title, style: const TextStyle(fontSize: 12, color: Colors.grey)),
            const SizedBox(height: 4),
            Text(value, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: Colors.grey)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  List<Widget> _buildLifecycleStages(Map<String, dynamic> stages) {
    return stages.entries.map((entry) {
      return ListTile(
        leading: const Icon(Icons.eco, color: Colors.green),
        title: Text(entry.key[0].toUpperCase() + entry.key.substring(1)),
        trailing: Text('${entry.value['days']} days', style: const TextStyle(fontWeight: FontWeight.bold)),
      );
    }).toList();
  }

  Widget _buildEnergyChart(Map<String, dynamic> byStage) {
    final entries = byStage.entries.toList();
    return BarChart(
      BarChartData(
        alignment: BarChartAlignment.spaceAround,
        maxY: entries.map((e) => e.value as num).reduce((a, b) => a > b ? a : b).toDouble() * 1.2,
        barGroups: entries.asMap().entries.map((entry) {
          return BarChartGroupData(
            x: entry.key,
            barRods: [
              BarChartRodData(
                toY: (entry.value.value as num).toDouble(),
                color: _getStageColor(entry.value.key),
                width: 20,
              ),
            ],
          );
        }).toList(),
        titlesData: FlTitlesData(
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) {
                if (value.toInt() < entries.length) {
                  return Text(entries[value.toInt()].key.substring(0, 3).toUpperCase());
                }
                return const Text('');
              },
            ),
          ),
          leftTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (value, meta) => Text('${value.toInt()}'),
            ),
          ),
          topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
      ),
    );
  }

  Color _getStageColor(String stage) {
    switch (stage.toLowerCase()) {
      case 'seedling': return Colors.green;
      case 'vegetative': return Colors.lightGreen;
      case 'flowering': return Colors.amber;
      case 'ripening': return Colors.orange;
      default: return Colors.blue;
    }
  }

  Widget _buildEfficiencyBadge(String rating) {
    Color color;
    switch (rating) {
      case 'Excellent': color = Colors.green; break;
      case 'Good': color = Colors.lightGreen; break;
      case 'Average': color = Colors.amber; break;
      default: color = Colors.red;
    }
    
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        rating,
        style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold),
      ),
    );
  }

  List<Widget> _buildRecommendations(Map<String, dynamic> recommendations) {
    final List<Widget> widgets = [];
    recommendations.forEach((category, items) {
      if (items is List) {
        for (var item in items) {
          widgets.add(
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 4),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.check_circle, color: Colors.green, size: 20),
                  const SizedBox(width: 8),
                  Expanded(child: Text(item.toString())),
                ],
              ),
            ),
          );
        }
      } else {
        widgets.add(
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.check_circle, color: Colors.green, size: 20),
                const SizedBox(width: 8),
                Expanded(child: Text(items.toString())),
              ],
            ),
          ),
        );
      }
    });
    return widgets;
  }

  String _getRatingLabel(int rating) {
    switch (rating) {
      case 5: return 'Excellent';
      case 4: return 'Good';
      case 3: return 'Average';
      case 2: return 'Below Average';
      case 1: return 'Poor';
      default: return 'Unknown';
    }
  }

  @override
  void dispose() {
    _weightController.dispose();
    _notesController.dispose();
    super.dispose();
  }
}
