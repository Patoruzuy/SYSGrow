"""
Personalized Learning API
=========================
Endpoints for managing user-specific AI learning and recommendations.
"""

import logging
from datetime import datetime
from flask import Blueprint, request

from app.blueprints.api._common import (
    get_container as _container,
    success as _success,
    fail as _fail,
)

logger = logging.getLogger(__name__)

personalized_bp = Blueprint("ml_personalized", __name__, url_prefix="/api/ml/personalized")


def _get_personalized_service():
    """Get personalized learning service from container."""
    container = _container()
    if not container:
        return None
    return getattr(container, 'personalized_learning', None)


# ==============================================================================
# ENVIRONMENT PROFILES
# ==============================================================================

@personalized_bp.get("/profiles/<int:unit_id>")
def get_profile(unit_id: int):
    """
    Get environment profile for a unit.
    
    Returns:
        {
            "profile": {
                "user_id": int,
                "unit_id": int,
                "location_characteristics": {...},
                "equipment_profile": {...},
                "historical_patterns": {...},
                "success_factors": [...],
                "challenge_areas": [...]
            }
        }
    """
    try:
        service = _get_personalized_service()
        
        if not service:
            return _fail("Personalized learning service is not enabled", 503)
        
        profile = service.get_profile(unit_id)
        
        if not profile:
            return _fail(f"Profile for unit {unit_id} not found", 404)
        
        return _success({"profile": profile.to_dict()})
        
    except Exception as e:
        logger.error(f"Error getting profile for unit {unit_id}: {e}", exc_info=True)
        return _fail(str(e), 500)


@personalized_bp.post("/profiles")
def create_profile():
    """
    Create a new environment profile.
    
    Request body:
        {
            "user_id": int,
            "unit_id": int,
            "location_info": {...} (optional),
            "equipment_info": {...} (optional)
        }
    
    Returns:
        {
            "profile": {...}
        }
    """
    try:
        service = _get_personalized_service()
        
        if not service:
            return _fail("Personalized learning service is not enabled", 503)
        
        data = request.get_json() or {}
        
        user_id = data.get('user_id')
        unit_id = data.get('unit_id')
        
        if user_id is None or unit_id is None:
            return _fail("user_id and unit_id are required", 400)
        
        profile = service.create_environment_profile(
            user_id=user_id,
            unit_id=unit_id,
            location_info=data.get('location_info'),
            equipment_info=data.get('equipment_info')
        )
        
        return _success({"profile": profile.to_dict()}, 201)
        
    except Exception as e:
        logger.error(f"Error creating profile: {e}", exc_info=True)
        return _fail(str(e), 500)


@personalized_bp.put("/profiles/<int:unit_id>")
def update_profile(unit_id: int):
    """
    Update an existing environment profile.
    
    Request body:
        {
            "location_characteristics": {...} (optional),
            "equipment_profile": {...} (optional),
            "success_factors": [...] (optional),
            "challenge_areas": [...] (optional)
        }
    
    Returns:
        {
            "updated": true,
            "profile": {...}
        }
    """
    try:
        service = _get_personalized_service()
        
        if not service:
            return _fail("Personalized learning service is not enabled", 503)
        
        data = request.get_json() or {}
        
        service.update_profile(unit_id, data)
        
        # Get updated profile
        profile = service.get_profile(unit_id)
        
        if not profile:
            return _fail(f"Profile for unit {unit_id} not found", 404)
        
        return _success({
            "updated": True,
            "profile": profile.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error updating profile for unit {unit_id}: {e}", exc_info=True)
        return _fail(str(e), 500)


# ==============================================================================
# SUCCESS TRACKING
# ==============================================================================

@personalized_bp.post("/successes")
def record_success():
    """
    Record a growing success (completed grow cycle).
    
    Request body:
        {
            "user_id": int,
            "unit_id": int,
            "plant_type": str,
            "plant_variety": str (optional),
            "start_date": str (ISO 8601),
            "harvest_date": str (ISO 8601),
            "total_yield": float (grams, optional),
            "quality_rating": int (1-5),
            "growth_conditions": {...} (optional),
            "lessons_learned": [...] (optional),
            "would_repeat": bool
        }
    
    Returns:
        {
            "recorded": true,
            "success": {...}
        }
    """
    try:
        from app.services.ai.personalized_learning import GrowingSuccess
        
        service = _get_personalized_service()
        
        if not service:
            return _fail("Personalized learning service is not enabled", 503)
        
        data = request.get_json() or {}
        
        # Validate required fields
        required = ['user_id', 'unit_id', 'plant_type', 'start_date', 'harvest_date', 'quality_rating', 'would_repeat']
        missing = [f for f in required if f not in data]
        if missing:
            return _fail(f"Missing required fields: {', '.join(missing)}", 400)
        
        success = GrowingSuccess(
            user_id=data['user_id'],
            unit_id=data['unit_id'],
            plant_type=data['plant_type'],
            plant_variety=data.get('plant_variety'),
            start_date=datetime.fromisoformat(data['start_date']),
            harvest_date=datetime.fromisoformat(data['harvest_date']),
            total_yield=data.get('total_yield'),
            quality_rating=data['quality_rating'],
            growth_conditions=data.get('growth_conditions', {}),
            lessons_learned=data.get('lessons_learned', []),
            would_repeat=data['would_repeat']
        )
        
        service.record_success(success)
        
        return _success({
            "recorded": True,
            "success": success.to_dict()
        }, 201)
        
    except ValueError as e:
        return _fail(f"Invalid date format: {e}", 400)
    except Exception as e:
        logger.error(f"Error recording success: {e}", exc_info=True)
        return _fail(str(e), 500)




# ==============================================================================
# RECOMMENDATIONS
# ==============================================================================

@personalized_bp.get("/recommendations/<int:unit_id>")
def get_recommendations(unit_id: int):
    """
    Get personalized recommendations for a unit.
    
    Query params:
    - plant_type: Plant type for recommendations
    - growth_stage: Current growth stage
    
    Returns:
        {
            "unit_id": int,
            "recommendations": {
                "climate": {...},
                "watering": {...},
                "lighting": {...},
                "adjustments": [...],
                "confidence": float
            }
        }
    """
    try:
        container = _container()
        service = getattr(container, "personalized_learning", None)
        
        if not service:
            return _success({
                "unit_id": unit_id,
                "recommendations": None,
                "message": "Personalized learning service is not enabled"
            })
        
        plant_type = request.args.get('plant_type', 'tomato')
        growth_stage = request.args.get('growth_stage', 'vegetative')
        
        # Get current conditions from latest sensor data
        latest_data = None
        analytics_service = getattr(container, "analytics_service", None)
        if analytics_service:
            try:
                latest_data = analytics_service.get_latest_sensor_reading(unit_id=unit_id)
            except Exception as exc:
                logger.warning("Failed to load latest sensor data for unit %s: %s", unit_id, exc)

        from app.domain.sensors.fields import SensorField
        
        # Use standardized keys
        lux_value = latest_data.get(SensorField.LUX.value) if isinstance(latest_data, dict) else None
        
        current_conditions = {
            'temperature': latest_data.get(SensorField.TEMPERATURE.value, 25.0) if isinstance(latest_data, dict) else 25.0,
            'humidity': latest_data.get(SensorField.HUMIDITY.value, 60.0) if isinstance(latest_data, dict) else 60.0,
            'soil_moisture': latest_data.get(SensorField.SOIL_MOISTURE.value, 50.0) if isinstance(latest_data, dict) else 50.0,
            'lux': lux_value if lux_value is not None else 500.0
        }
        
        recommendations = service.get_personalized_recommendations(
            unit_id=unit_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            current_conditions=current_conditions
        )
        
        return _success({
            "unit_id": unit_id,
            "plant_type": plant_type,
            "growth_stage": growth_stage,
            "recommendations": recommendations
        })
        
    except Exception as e:
        logger.error(f"Error getting recommendations for unit {unit_id}: {e}", exc_info=True)
        return _fail(str(e), 500)


@personalized_bp.get("/similar-growers/<int:unit_id>")
def get_similar_growers(unit_id: int):
    """
    Find growers with similar environments and successes.
    
    Query params:
    - plant_type: Plant type to compare (optional)
    - limit: Max results (default 5)
    
    Returns:
        {
            "unit_id": int,
            "similar_growers": [
                {
                    "unit_id": int,
                    "similarity_score": float,
                    "shared_success_factors": [...],
                    "key_conditions": {...}
                }
            ]
        }
    """
    try:
        service = _get_personalized_service()
        
        if not service:
            return _success({
                "unit_id": unit_id,
                "similar_growers": [],
                "message": "Personalized learning service is not enabled"
            })
        
        plant_type = request.args.get('plant_type')
        limit = request.args.get('limit', 5, type=int)
        
        similar = service.get_similar_growers(
            unit_id=unit_id,
            plant_type=plant_type,
            limit=limit
        )
        
        return _success({
            "unit_id": unit_id,
            "similar_growers": similar,
            "count": len(similar)
        })
        
    except Exception as e:
        logger.error(f"Error finding similar growers for unit {unit_id}: {e}", exc_info=True)
        return _fail(str(e), 500)
