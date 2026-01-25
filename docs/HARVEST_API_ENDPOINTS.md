# Harvest Report API Endpoints

This document describes the REST API endpoints required for the harvest report functionality.

## Endpoints

### 1. Generate Harvest Report and Optional Cleanup

```http
POST /api/plants/<plant_id>/harvest
Content-Type: application/json
```

**Request Body:**
```json
{
  "harvest_weight_grams": 250.5,
  "quality_rating": 5,
  "notes": "Excellent harvest, perfect color and size",
  "delete_plant_data": true
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "harvest_report": {
    "harvest_id": 123,
    "plant_id": 101,
    "plant_name": "Tomato #1",
    "yield": {
      "weight_grams": 250.5,
      "quality_rating": 5,
      "harvested_date": "2024-01-15T10:30:00Z"
    },
    "lifecycle": {
      "planted_date": "2023-11-01T08:00:00Z",
      "harvested_date": "2024-01-15T10:30:00Z",
      "total_days": 75,
      "stages": {
        "seedling": {"days": 14},
        "vegetative": {"days": 35},
        "flowering": {"days": 20},
        "ripening": {"days": 6}
      }
    },
    "energy_consumption": {
      "total_kwh": 45.2,
      "total_cost": 5.65,
      "by_stage": {
        "seedling": 5.2,
        "vegetative": 18.5,
        "flowering": 15.3,
        "ripening": 6.2
      },
      "cost_by_stage": {
        "seedling": 0.65,
        "vegetative": 2.31,
        "flowering": 1.91,
        "ripening": 0.78
      }
    },
    "efficiency_metrics": {
      "grams_per_kwh": 5.54,
      "cost_per_gram": 0.023,
      "cost_per_pound": 10.34,
      "energy_efficiency_rating": "Excellent"
    },
    "environmental_conditions": {
      "temperature": {
        "avg": 24.5,
        "min": 22.0,
        "max": 26.8,
        "optimal_range": "22-26°C"
      },
      "humidity": {
        "avg": 65.2,
        "min": 58.0,
        "max": 72.0,
        "optimal_range": "60-70%"
      },
      "co2": {
        "avg": 850,
        "optimal": "400-1000 ppm"
      }
    },
    "recommendations": {
      "energy": [
        "Excellent energy efficiency (5.54 g/kWh)",
        "Consider maintaining flowering stage conditions for future grows"
      ],
      "cost": [
        "Low production cost: $0.023 per gram",
        "Total cost well below market average"
      ],
      "optimization": [
        "Temperature control was optimal throughout lifecycle",
        "Consider increasing CO2 during flowering for potential yield improvement"
      ]
    }
  },
  "cleanup_performed": true,
  "cleanup_summary": {
    "plant_records_deleted": 1,
    "health_logs_deleted": 45,
    "plant_sensors_removed": 3,
    "unit_plant_associations_removed": 1,
    "preserved_records": {
      "energy_readings": 120,
      "sensor_readings": 3600,
      "actuator_history": 85
    }
  }
}
```

### 2. Get Harvest Report by ID

```http
GET /api/harvests/<harvest_id>
```

**Response (200 OK):**
Returns same structure as harvest report above.

### 3. List All Harvest Reports

```http
GET /api/harvests?unit_id=<unit_id>&limit=50&offset=0
```

**Response (200 OK):**
```json
{
  "total": 25,
  "limit": 50,
  "offset": 0,
  "harvests": [
    {
      "harvest_id": 123,
      "plant_id": 101,
      "plant_name": "Tomato #1",
      "plant_type": "Cherry Tomato",
      "harvested_date": "2024-01-15T10:30:00Z",
      "harvest_weight_grams": 250.5,
      "quality_rating": 5,
      "total_energy_kwh": 45.2,
      "total_cost": 5.65,
      "grams_per_kwh": 5.54,
      "cost_per_gram": 0.023,
      "energy_efficiency_rating": "Excellent"
    }
  ]
}
```

### 4. Get Plants for Unit (Harvest Candidates)

```http
GET /api/units/<unit_id>/plants?stage=ripening
```

**Response (200 OK):**
```json
[
  {
    "plant_id": 101,
    "name": "Tomato #1",
    "plant_type": "Cherry Tomato",
    "current_stage": "ripening",
    "days_in_stage": 6,
    "planted_date": "2023-11-01T08:00:00Z",
    "ready_to_harvest": true
  }
]
```

### 5. Delete Plant After Harvest

```http
DELETE /api/plants/<plant_id>?harvested=true
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Plant data deleted successfully",
  "deleted_records": {
    "plant": 1,
    "health_logs": 45,
    "sensor_associations": 3
  },
  "preserved_records": {
    "energy_readings": 120,
    "sensor_readings": 3600
  }
}
```

## Implementation Notes

### Backend Route Handlers

Add these routes to your Flask/FastAPI application:

```python
# app/routes/harvest_routes.py
from flask import Blueprint, request, jsonify
from app.services.harvest_service import HarvestService

harvest_bp = Blueprint('harvest', __name__)
harvest_service = HarvestService()

@harvest_bp.route('/api/plants/<int:plant_id>/harvest', methods=['POST'])
def create_harvest_report(plant_id):
    """Generate harvest report and optionally cleanup plant data"""
    data = request.get_json()
    
    try:
        result = harvest_service.harvest_and_cleanup(
            plant_id=plant_id,
            harvest_weight_grams=data['harvest_weight_grams'],
            quality_rating=data['quality_rating'],
            notes=data.get('notes', ''),
            delete_plant_data=data.get('delete_plant_data', False)
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@harvest_bp.route('/api/harvests/<int:harvest_id>', methods=['GET'])
def get_harvest_report(harvest_id):
    """Get specific harvest report by ID"""
    try:
        report = harvest_service.get_harvest_by_id(harvest_id)
        if report:
            return jsonify(report), 200
        return jsonify({'error': 'Harvest not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@harvest_bp.route('/api/harvests', methods=['GET'])
def list_harvest_reports():
    """List all harvest reports with optional filtering"""
    unit_id = request.args.get('unit_id', type=int)
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    
    try:
        result = harvest_service.list_harvests(
            unit_id=unit_id,
            limit=limit,
            offset=offset
        )
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@harvest_bp.route('/api/plants/<int:plant_id>', methods=['DELETE'])
def delete_plant(plant_id):
    """Delete plant data (typically after harvest)"""
    harvested = request.args.get('harvested', 'false').lower() == 'true'
    
    try:
        result = harvest_service.cleanup_after_harvest(
            plant_id=plant_id,
            delete_plant_data=True
        )
        return jsonify({
            'success': True,
            'message': 'Plant data deleted successfully',
            'deleted_records': result.get('deleted', {}),
            'preserved_records': result.get('preserved', {})
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Register the Blueprint

```python
# In your main app initialization file
from app.routes.harvest_routes import harvest_bp

app.register_blueprint(harvest_bp)
```

## Error Responses

All endpoints return errors in this format:

```json
{
  "error": "Description of what went wrong",
  "code": "ERROR_CODE",
  "details": {}
}
```

**Common Error Codes:**
- 400: Bad Request (missing parameters, invalid data)
- 404: Not Found (plant or harvest doesn't exist)
- 409: Conflict (plant already harvested)
- 500: Internal Server Error

## Usage Examples

### Example 1: Harvest with Cleanup

```bash
curl -X POST http://localhost:5000/api/plants/101/harvest \
  -H "Content-Type: application/json" \
  -d '{
    "harvest_weight_grams": 250.5,
    "quality_rating": 5,
    "notes": "Perfect harvest!",
    "delete_plant_data": true
  }'
```

### Example 2: Harvest Without Cleanup (Keep Data)

```bash
curl -X POST http://localhost:5000/api/plants/101/harvest \
  -H "Content-Type: application/json" \
  -d '{
    "harvest_weight_grams": 180.3,
    "quality_rating": 4,
    "notes": "Good yield",
    "delete_plant_data": false
  }'
```

### Example 3: Get All Harvests for a Unit

```bash
curl http://localhost:5000/api/harvests?unit_id=1&limit=20
```

### Example 4: Get Specific Harvest Report

```bash
curl http://localhost:5000/api/harvests/123
```

## Testing

Test the endpoints using the provided test file:

```bash
python test_harvest_cleanup.py
```

Or use curl/Postman with the examples above.
