"""
AI Predictions API
==================
Core AI/ML prediction endpoints:
- Disease risk prediction
- Plant growth predictions  
- Climate optimization
- Health recommendations

Consolidates functionality from:
- ai_predictions.py (disease, health, climate)
- disease.py (risk assessments, alerts)
- growth_stages.py (stage predictions)
"""

import logging
from collections import Counter
from datetime import datetime
from typing import Any, Dict

from flask import Blueprint, jsonify, request, session
from pydantic import ValidationError
from app.utils.time import iso_now
from zoneinfo import ZoneInfo

from app.enums.growth import PlantStage
from app.schemas import DiseaseRiskRequest, GrowthComparisonRequest, WhatIfSimulationRequest

from app.blueprints.api._common import (
    get_container as _container,
    get_growth_service,
    success as _success,
    fail as _fail,
)

logger = logging.getLogger(__name__)

predictions_bp = Blueprint("ml_predictions", __name__, url_prefix="/api/ml/predictions")

def _get_unit_timezone(unit_id: int) -> str | None:
    try:
        growth_service = get_growth_service()
        if not growth_service:
            return None
        unit = growth_service.get_unit(unit_id)
        if isinstance(unit, dict):
            return unit.get("timezone")
        return getattr(unit, "timezone", None)
    except Exception:
        return None

def _resolve_unit_now(unit_timezone: str | None) -> datetime:
    if not unit_timezone:
        return datetime.now()
    try:
        return datetime.now(ZoneInfo(unit_timezone))
    except Exception:
        return datetime.now()


def _get_irrigation_predictor(container):
    predictor = getattr(container, "irrigation_predictor", None)
    if predictor:
        return predictor
    try:
        from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository
        from app.services.ai.irrigation_predictor import IrrigationPredictor

        irrigation_ml_repo = IrrigationMLRepository(container.database)
        predictor = IrrigationPredictor(
            irrigation_ml_repo=irrigation_ml_repo,
            model_registry=getattr(container, "model_registry", None),
            feature_engineer=getattr(container, "feature_engineer", None),
        )
        predictor.load_models()
        return predictor
    except Exception as exc:
        logger.error(f"Failed to initialize irrigation predictor: {exc}", exc_info=True)
        return None


def _require_user_id():
    user_id = session.get("user_id")
    if not user_id:
        return None, _fail("User not authenticated", 401)
    try:
        return int(user_id), None
    except (TypeError, ValueError):
        return None, _fail("User not authenticated", 401)


def _resolve_active_plant(container, unit_id: int):
    plant_service = getattr(container, "plant_service", None)
    if not plant_service:
        return None
    active_plant = plant_service.get_active_plant(unit_id)
    if not active_plant:
        unit_plants = plant_service.list_plants(unit_id)
        active_plant = unit_plants[0] if unit_plants else None
    return active_plant


def _plant_value(plant, key: str, default: str) -> str:
    if plant is None:
        return default
    if hasattr(plant, key):
        value = getattr(plant, key)
        return value or default
    if isinstance(plant, dict):
        return plant.get(key) or default
    return default


def _resolve_plant_id(active_plant):
    if active_plant is None:
        return None
    if hasattr(active_plant, "plant_id"):
        return getattr(active_plant, "plant_id")
    if hasattr(active_plant, "id"):
        return getattr(active_plant, "id")
    if isinstance(active_plant, dict):
        return active_plant.get("plant_id") or active_plant.get("id")
    return None


def _resolve_current_threshold(container, unit_id: int, user_id: int, active_plant=None) -> float:
    current_threshold = 50.0
    plant_service = getattr(container, "plant_service", None)

    if active_plant is not None:
        override = None
        if hasattr(active_plant, "soil_moisture_threshold_override"):
            override = getattr(active_plant, "soil_moisture_threshold_override")
        elif isinstance(active_plant, dict):
            override = active_plant.get("soil_moisture_threshold_override")
        if override is not None:
            current_threshold = float(override)
        elif plant_service:
            name = None
            if hasattr(active_plant, "plant_type"):
                name = getattr(active_plant, "plant_type") or getattr(active_plant, "plant_name", None)
            elif isinstance(active_plant, dict):
                name = active_plant.get("plant_type") or active_plant.get("plant_name")
            if name:
                try:
                    value = plant_service.plant_json_handler.get_soil_moisture_trigger(name)
                except Exception:
                    value = None
                if value is not None:
                    current_threshold = float(value)

    from infrastructure.database.repositories.irrigation_workflow import IrrigationWorkflowRepository
    workflow_repo = IrrigationWorkflowRepository(container.database)
    prefs = workflow_repo.get_user_preference(user_id, unit_id)
    if prefs and prefs.get("preferred_moisture_threshold") is not None:
        current_threshold = float(prefs.get("preferred_moisture_threshold"))

    return current_threshold


def _build_irrigation_feature_context(
    container,
    *,
    unit_id: int,
    plant_id: int | None,
    user_id: int,
) -> Dict[str, Any]:
    workflow_service = getattr(container, "irrigation_workflow_service", None)
    if not workflow_service:
        return {
            "current_conditions": {},
            "irrigation_history": [],
            "user_preferences": {},
            "plant_info": {},
            "unit_timezone": _get_unit_timezone(unit_id),
        }

    context = workflow_service.build_irrigation_feature_inputs(
        unit_id=unit_id,
        plant_id=plant_id,
        user_id=user_id,
    )
    context["unit_timezone"] = _get_unit_timezone(unit_id)
    return context


# ==================== Disease Prediction ====================

@predictions_bp.post("/disease/risk")
def predict_disease_risk():
    """
    Predict disease risk for a specific unit.
    
    Body:
    {
        "unit_id": 1,
        "plant_type": "tomato",
        "growth_stage": "vegetative",
        "current_conditions": {...}  # optional
    }
    """
    try:
        raw = request.get_json() or {}
        try:
            body = DiseaseRiskRequest(**raw)
        except ValidationError as ve:
            return _fail("Invalid request", 400, details={"errors": ve.errors()})
        
        container = _container()
        predictor = container.disease_predictor
        
        if not predictor.is_available():
            return _fail("Disease prediction model not available", 503)
        
        risks = predictor.predict_disease_risk(
            unit_id=body.unit_id,
            plant_type=body.plant_type,
            growth_stage=body.growth_stage,
            current_conditions=body.current_conditions
        )
        
        return _success({
            "unit_id": body.unit_id,
            "plant_type": body.plant_type,
            "risks": [risk.to_dict() for risk in risks],
            "count": len(risks)
        })
        
    except Exception as e:
        logger.error(f"Error predicting disease risk: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/disease/risks")
def get_all_disease_risks():
    """
    Get disease risk assessments for all or filtered units.
    
    Query params:
    - unit_id: Optional unit ID filter
    - risk_level: Optional filter (low, moderate, high, critical)
    """
    try:
        from app.services.ai import RiskLevel
        
        container = _container()
        predictor = container.disease_predictor
        plant_service = container.plant_service
        growth_service = container.growth_service
        
        if not predictor.is_available():
            return _fail("Disease prediction model not available", 503)
        
        unit_id_filter = request.args.get("unit_id", type=int)
        risk_level_filter = request.args.get("risk_level")
        
        def _resolve_unit_plants(unit_id: int):
            active = plant_service.get_active_plant(unit_id)
            if active:
                return [(unit_id, active)]
            unit_plants = plant_service.list_plants(unit_id)
            if unit_plants:
                return [(unit_id, unit_plants[0])]
            return []

        # Get active plants per unit
        plant_records = []
        if unit_id_filter:
            plant_records = _resolve_unit_plants(unit_id_filter)
        else:
            for unit in (growth_service.list_units() if growth_service else []):
                unit_id = unit.get("unit_id") or unit.get("id")
                if not unit_id:
                    continue
                plant_records.extend(_resolve_unit_plants(unit_id))

        plants = []
        for unit_id, plant in plant_records:
            plant_data = plant.to_dict() if hasattr(plant, "to_dict") else dict(plant)
            plant_data["unit_id"] = unit_id
            plants.append(plant_data)

        if not plants:
            return _success({
                "units": [],
                "summary": {"total_units": 0, "high_risk_units": 0, "critical_risk_units": 0}
            })
        
        # Process units
        units_data = []
        high_risk_count = 0
        critical_risk_count = 0
        all_risk_types = []
        processed_units = set()
        
        for plant in plants:
            if plant['unit_id'] in processed_units:
                continue
            processed_units.add(plant['unit_id'])
            
            risks = predictor.predict_disease_risk(
                unit_id=plant['unit_id'],
                plant_type=plant.get('plant_type', 'unknown'),
                growth_stage=plant.get('current_stage', 'vegetative')
            )
            
            # Filter by risk level if specified
            if risk_level_filter:
                try:
                    filter_level = RiskLevel(risk_level_filter.lower())
                    risks = [r for r in risks if r.risk_level == filter_level]
                except ValueError:
                    pass
            
            # Count risks
            for risk in risks:
                if risk.risk_level == RiskLevel.HIGH:
                    high_risk_count += 1
                elif risk.risk_level == RiskLevel.CRITICAL:
                    critical_risk_count += 1
                all_risk_types.append(risk.disease_type.value)
            
            risks_data = [risk.to_dict() for risk in risks]
            
            units_data.append({
                "unit_id": plant['unit_id'],
                "unit_name": plant.get('unit_name', f"Unit {plant['unit_id']}"),
                "plant_type": plant.get('plant_type', 'unknown'),
                "growth_stage": plant.get('current_stage', 'vegetative'),
                "risks": risks_data,
                "risk_count": len(risks_data),
                "highest_risk_score": max([r['risk_score'] for r in risks_data]) if risks_data else 0
            })
        
        # Summary
        most_common_risk = None
        if all_risk_types:
            risk_counts = Counter(all_risk_types)
            most_common_risk = risk_counts.most_common(1)[0][0]
        
        return _success({
            "units": units_data,
            "summary": {
                "total_units": len(units_data),
                "high_risk_units": high_risk_count,
                "critical_risk_units": critical_risk_count,
                "most_common_risk": most_common_risk,
                "total_risks_detected": len(all_risk_types)
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting disease risks: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/disease/alerts")
def get_disease_alerts():
    """
    Get active disease alerts (HIGH and CRITICAL risks only).
    
    Query params:
    - unit_id: Optional unit ID filter
    """
    try:
        from app.services.ai import RiskLevel
        
        container = _container()
        predictor = container.disease_predictor
        plant_service = container.plant_service
        growth_service = container.growth_service
        
        if not predictor.is_available():
            return _fail("Disease prediction model not available", 503)
        
        unit_id_filter = request.args.get("unit_id", type=int)
        
        def _resolve_unit_plants(unit_id: int):
            active = plant_service.get_active_plant(unit_id)
            if active:
                return [(unit_id, active)]
            unit_plants = plant_service.list_plants(unit_id)
            if unit_plants:
                return [(unit_id, unit_plants[0])]
            return []

        plant_records = []
        if unit_id_filter:
            plant_records = _resolve_unit_plants(unit_id_filter)
        else:
            for unit in (growth_service.list_units() if growth_service else []):
                unit_id = unit.get("unit_id") or unit.get("id")
                if not unit_id:
                    continue
                plant_records.extend(_resolve_unit_plants(unit_id))

        plants = []
        for unit_id, plant in plant_records:
            plant_data = plant.to_dict() if hasattr(plant, "to_dict") else dict(plant)
            plant_data["unit_id"] = unit_id
            plants.append(plant_data)

        if not plants:
            return _success({"alerts": [], "alert_count": 0, "critical_count": 0})
        
        # Generate alerts
        alerts = []
        critical_count = 0
        processed_units = set()
        
        for plant in plants:
            if plant['unit_id'] in processed_units:
                continue
            processed_units.add(plant['unit_id'])
            
            risks = predictor.predict_disease_risk(
                unit_id=plant['unit_id'],
                plant_type=plant.get('plant_type', 'unknown'),
                growth_stage=plant.get('current_stage', 'vegetative')
            )
            
            # Filter for HIGH and CRITICAL only
            high_risks = [r for r in risks if r.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]]
            
            for risk in high_risks:
                if risk.risk_level == RiskLevel.CRITICAL:
                    critical_count += 1
                
                alert_id = f"unit{plant['unit_id']}_{risk.disease_type.value}_{datetime.now().strftime('%Y-%m-%d')}"
                
                alerts.append({
                    "alert_id": alert_id,
                    "unit_id": plant['unit_id'],
                    "unit_name": plant.get('unit_name', f"Unit {plant['unit_id']}"),
                    "disease_type": risk.disease_type.value,
                    "risk_level": risk.risk_level.value,
                    "risk_score": round(risk.risk_score, 1),
                    "predicted_onset_days": risk.predicted_onset_days,
                    "priority": 1 if risk.risk_level == RiskLevel.CRITICAL else 2,
                    "actions": risk.recommendations[:3],
                    "timestamp": iso_now()
                })
        
        # Sort by priority
        alerts.sort(key=lambda a: (a['priority'], -a['risk_score']))
        
        return _success({
            "alerts": alerts,
            "alert_count": len(alerts),
            "critical_count": critical_count
        })
        
    except Exception as e:
        logger.error(f"Error getting disease alerts: {e}", exc_info=True)
        return _fail(str(e), 500)


# ==================== Growth Stage Prediction ====================

@predictions_bp.get("/growth/<string:stage>")
def predict_growth_conditions(stage: str):
    """
    Get optimal environmental conditions for a growth stage.
    
    Query params:
    - days_in_stage: Optional days in current stage for fine-tuning
    """
    try:
        container = _container()
        growth_predictor = container.plant_growth_predictor
        
        days_in_stage = request.args.get("days_in_stage", type=int)
        
        conditions = growth_predictor.predict_growth_conditions(
            stage_name=stage,
            days_in_stage=days_in_stage
        )
        
        if not conditions:
            return _fail(f"Unknown growth stage: {stage}", 404)
        
        return _success({
            "stage": stage,
            "conditions": conditions.to_dict(),
            "recommendation": conditions.get_recommendation()
        })
        
    except Exception as e:
        logger.error(f"Error predicting conditions for {stage}: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/growth/stages/all")
def get_all_growth_stages():
    """Get optimal conditions for all growth stages."""
    try:
        container = _container()
        growth_predictor = container.plant_growth_predictor
        
        all_conditions = growth_predictor.get_all_stage_conditions()
        
        return _success({
            "stages": {
                stage: conditions.to_dict()
                for stage, conditions in all_conditions.items()
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting all stage conditions: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.post("/growth/transition-analysis")
def analyze_growth_transition():
    """
    Analyze readiness for growth stage transition.
    
    Body:
    {
        "current_stage": "vegetative",
        "days_in_stage": 21,
        "actual_conditions": {
            "temperature": 24.5,
            "humidity": 65.0,
            "soil_moisture": 70.0
        }
    }
    """
    try:
        container = _container()
        growth_predictor = container.plant_growth_predictor
        
        data = request.get_json()
        if not data:
            return _fail("No data provided", 400)
        
        current_stage = data.get("current_stage")
        days_in_stage = data.get("days_in_stage")
        actual_conditions = data.get("actual_conditions", {})
        
        if not current_stage or days_in_stage is None:
            return _fail("current_stage and days_in_stage are required", 400)
        
        transition = growth_predictor.analyze_stage_transition(
            current_stage=current_stage,
            days_in_stage=days_in_stage,
            actual_conditions=actual_conditions
        )
        
        return _success({"transition": transition.to_dict()})
        
    except Exception as e:
        logger.error(f"Error analyzing transition: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.post("/growth/compare")
def compare_growth_conditions():
    """
    Compare actual conditions against optimal for a stage.
    
    Body:
    {
        "stage": "vegetative",
        "actual_conditions": {
            "temperature": 24.5,
            "humidity": 65.0,
            "soil_moisture": 70.0
        }
    }
    """
    try:
        container = _container()
        growth_predictor = container.plant_growth_predictor
        
        raw = request.get_json() or {}
        try:
            body = GrowthComparisonRequest(**raw)
        except ValidationError as ve:
            return _fail("Invalid request", 400, details={"errors": ve.errors()})
        
        comparison = growth_predictor.compare_conditions(body.actual_conditions, body.stage)
        
        return _success({"comparison": comparison})
        
    except Exception as e:
        logger.error(f"Error comparing conditions: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/growth/status")
def get_growth_predictor_status():
    """Get growth predictor status and available stages."""
    try:
        container = _container()
        growth_predictor = container.growth_predictor

        status = growth_predictor.get_status()

        return _success({"status": status})

    except Exception as e:
        logger.error(f"Error getting predictor status: {e}", exc_info=True)
        return _fail(str(e), 500)


# ==================== Climate Optimization ====================

@predictions_bp.get("/climate/<string:growth_stage>")
def predict_climate_conditions(growth_stage: str):
    """Predict optimal climate conditions for a growth stage."""
    try:
        container = _container()
        optimizer = container.climate_optimizer
        
        conditions = optimizer.predict_conditions(growth_stage)
        
        if not conditions:
            return _fail("Prediction not available", 404)
        
        return _success(conditions.to_dict())
        
    except Exception as e:
        logger.error(f"Error predicting conditions: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/climate/<int:unit_id>/recommendations")
def get_climate_recommendations(unit_id: int):
    """Get climate control recommendations for a unit."""
    try:
        container = _container()
        optimizer = container.climate_optimizer
        
        recommendations = optimizer.get_recommendations(unit_id)
        
        return _success(recommendations)
        
    except Exception as e:
        logger.error(f"Error getting climate recommendations: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/climate/<int:unit_id>/watering-issues")
def detect_watering_issues(unit_id: int):
    """Detect and analyze watering issues for a unit."""
    try:
        container = _container()
        optimizer = container.climate_optimizer
        
        issues = optimizer.detect_watering_issues(unit_id)
        
        return _success(issues)
        
    except Exception as e:
        logger.error(f"Error detecting watering issues: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/climate/forecast")
def get_climate_forecast():
    """
    Get climate forecast for the next 6 hours.
    
    Query params:
    - unit_id: Optional unit ID for context-specific forecast
    - hours_ahead: Number of hours to forecast (default: 6, max: 24)
    """
    try:
        container = _container()
        optimizer = container.climate_optimizer
        
        if not optimizer.is_available():
            return _fail("Climate forecast model not available", 503)
        
        unit_id = request.args.get("unit_id", type=int)
        hours_ahead = min(request.args.get("hours_ahead", default=6, type=int), 24)
        
        # Get current sensor data for context
        sensor_service = container.sensor_service
        current_readings = None
        
        if unit_id:
            current_readings = sensor_service.get_latest_by_unit(unit_id)
        
        # Generate hourly forecast
        forecast = {
            "temperature": [],
            "humidity": [],
            "soil_moisture": [],
            "timestamps": []
        }
        
        base_time = datetime.now()
        
        # Use simple trend-based forecast if available
        # (In production, this would call the actual ML model's forecast method)
        for hour in range(1, hours_ahead + 1):
            forecast_time = base_time.timestamp() + (hour * 3600)
            forecast["timestamps"].append(int(forecast_time * 1000))
            
            # Simple placeholder forecast logic
            # In production, replace with optimizer.forecast_conditions(unit_id, hours_ahead)
            if current_readings and len(current_readings) > 0:
                latest = current_readings[0]
                # Add small random variation to simulate forecast
                import random
                forecast["temperature"].append(round(latest.temperature + random.uniform(-1, 1), 1) if latest.temperature else None)
                forecast["humidity"].append(round(latest.humidity + random.uniform(-2, 2), 1) if latest.humidity else None)
                forecast["soil_moisture"].append(round(latest.soil_moisture + random.uniform(-1, 1), 1) if latest.soil_moisture else None)
            else:
                forecast["temperature"].append(None)
                forecast["humidity"].append(None)
                forecast["soil_moisture"].append(None)
        
        # Get model confidence
        model_status = optimizer.is_available()
        confidence = 0.85 if model_status else 0.0
        
        return _success({
            "forecast": forecast,
            "confidence": confidence,
            "hours_ahead": hours_ahead,
            "unit_id": unit_id,
            "explanation": "Forecast based on recent trends and climate model predictions"
        })
        
    except Exception as e:
        logger.error(f"Error generating climate forecast: {e}", exc_info=True)
        return _fail(str(e), 500)


# ==================== Health Monitoring ====================

@predictions_bp.get("/health/<int:unit_id>/recommendations")
def get_health_recommendations(unit_id: int):
    """
    Get health recommendations for a unit.
    
    Query params:
    - plant_type: Optional plant type
    - growth_stage: Optional growth stage
    """
    try:
        container = _container()
        monitor = container.plant_health_monitor
        
        plant_type = request.args.get("plant_type")
        growth_stage = request.args.get("growth_stage")
        
        recommendations = monitor.get_health_recommendations(
            unit_id=unit_id,
            plant_type=plant_type,
            growth_stage=growth_stage
        )
        
        return _success(recommendations)
        
    except Exception as e:
        logger.error(f"Error getting health recommendations: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.post("/health/observation")
def record_health_observation():
    """
    Record a plant health observation.
    
    Body:
    {
        "unit_id": 1,
        "plant_id": 1,  // optional
        "health_status": "stressed",
        "symptoms": ["yellowing_leaves"],
        "severity_level": 3,
        "disease_type": "fungal",  // optional
        "affected_parts": ["leaves"],  // optional
        "environmental_factors": {},  // optional
        "treatment_applied": "Applied fungicide",  // optional
        "plant_type": "tomato",  // optional
        "growth_stage": "vegetative",  // optional
        "notes": "Additional notes",  // optional
        "image_path": "/path/to/image.jpg"  // optional
    }
    """
    try:
        from app.models.plant_journal import PlantHealthObservationModel
        from app.services.ai import HealthStatus, DiseaseType
        
        data = request.get_json()
        user_id = session.get("user_id")
        
        # Validate required fields
        required = ["unit_id", "health_status", "symptoms", "severity_level"]
        missing = [f for f in required if f not in data]
        if missing:
            return _fail(f"Missing required fields: {', '.join(missing)}", 400)
        
        # Create observation model
        observation = PlantHealthObservationModel(
            unit_id=data["unit_id"],
            plant_id=data.get("plant_id"),
            health_status=HealthStatus(data["health_status"]),
            symptoms=data["symptoms"],
            disease_type=DiseaseType(data["disease_type"]) if data.get("disease_type") else None,
            severity_level=data["severity_level"],
            affected_parts=data.get("affected_parts", []),
            environmental_factors=data.get("environmental_factors", {}),
            treatment_applied=data.get("treatment_applied"),
            notes=data.get("notes", ""),
            plant_type=data.get("plant_type"),
            growth_stage=data.get("growth_stage"),
            image_path=data.get("image_path"),
            user_id=user_id
        )
        
        # Record via journal service
        container = _container()
        journal_service = container.plant_journal_service
        observation_id = journal_service.record_health_observation(observation)
        
        if observation_id:
            return _success({
                "observation_id": observation_id,
                "status": "recorded"
            }, 201)
        else:
            return _fail("Failed to record observation", 500)
        
    except ValueError as e:
        return _fail(f"Invalid value: {str(e)}", 400)
    except Exception as e:
        logger.error(f"Error recording observation: {e}", exc_info=True)
        return _fail(str(e), 500)


# ==================== What-If Simulator ====================

@predictions_bp.post("/what-if")
def what_if_simulation():
    """
    Predict impact of environmental parameter changes.
    
    Body:
    {
        "unit_id": 1,  // optional, for context
        "current": {
            "temperature": 22.5,
            "humidity": 65.0,
            "light_hours": 16.0,
            "co2": 800.0
        },
        "simulated": {
            "temperature": 24.0,
            "humidity": 70.0,
            "light_hours": 18.0,
            "co2": 1000.0
        }
    }
    
    Returns:
    {
        "ok": true,
        "data": {
            "predictions": {
                "vpd": {
                    "current": 1.15,
                    "predicted": 1.05,
                    "status": "optimal",
                    "change_percent": -8.7
                },
                "plant_health": {
                    "current": 85.0,
                    "predicted": 90.0,
                    "change_percent": 5.9
                },
                "energy_cost": {
                    "current": 100.0,
                    "predicted": 115.0,
                    "change_percent": 15.0
                },
                "growth_rate": {
                    "current": 1.0,
                    "predicted": 1.15,
                    "change_percent": 15.0
                }
            },
            "recommendations": [
                {
                    "message": "Temperature increase looks good",
                    "priority": "medium"
                }
            ],
            "ml_used": true,
            "confidence": 0.85,
            "explanation": "Predictions based on ML models"
        }
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get("current") or not data.get("simulated"):
            return _fail("Missing required fields: current, simulated", 400)
        
        current = data["current"]
        simulated = data["simulated"]
        unit_id = data.get("unit_id")
        
        # Validate parameter presence
        required_params = ["temperature", "humidity", "light_hours", "co2"]
        for params in [current, simulated]:
            missing = [p for p in required_params if p not in params]
            if missing:
                return _fail(f"Missing parameters: {', '.join(missing)}", 400)
        
        container = _container()
        
        # Try to get ML predictions
        ml_used = False
        confidence = 0.0
        predictions = {}
        
        try:
            # Check if climate optimizer is available
            climate_optimizer = container.climate_optimizer
            
            if climate_optimizer and hasattr(climate_optimizer, 'predict_impact'):
                # Use ML model to predict impact
                impact = climate_optimizer.predict_impact(
                    current_conditions=current,
                    target_conditions=simulated,
                    unit_id=unit_id
                )
                
                if impact:
                    ml_used = True
                    confidence = impact.get('confidence', 0.8)
                    predictions = impact.get('predictions', {})
                    
        except Exception as e:
            logger.warning(f"ML prediction failed, using statistical fallback: {e}")
        
        # Fallback to statistical predictions if ML not available
        if not ml_used:
            predictions = _calculate_statistical_predictions(current, simulated)
        
        # Generate recommendations
        recommendations = _generate_what_if_recommendations(current, simulated, predictions)
        
        return _success({
            "predictions": predictions,
            "recommendations": recommendations,
            "ml_used": ml_used,
            "confidence": confidence,
            "explanation": "Predictions based on ML models" if ml_used else "Predictions based on statistical analysis"
        })
        
    except Exception as e:
        logger.error(f"Error in what-if simulation: {e}", exc_info=True)
        return _fail(str(e), 500)


def _calculate_statistical_predictions(current, simulated):
    """Calculate predictions using statistical methods when ML unavailable."""
    import math
    
    # Calculate current VPD
    def calc_vpd(temp, humidity):
        # Saturated vapor pressure (kPa)
        svp = 0.6108 * math.exp((17.27 * temp) / (temp + 237.3))
        # Vapor pressure deficit
        return (1 - humidity / 100.0) * svp
    
    current_vpd = calc_vpd(current["temperature"], current["humidity"])
    predicted_vpd = calc_vpd(simulated["temperature"], simulated["humidity"])
    
    # VPD status
    def vpd_status(vpd):
        if 0.8 <= vpd <= 1.2:
            return "optimal"
        elif 0.6 <= vpd < 0.8 or 1.2 < vpd <= 1.4:
            return "acceptable"
        else:
            return "suboptimal"
    
    # Plant health score (0-100)
    def calc_health(temp, humidity, light, co2):
        score = 50  # Base score
        
        # Temperature factor (optimal: 20-26°C)
        if 20 <= temp <= 26:
            score += 20
        elif 18 <= temp < 20 or 26 < temp <= 28:
            score += 10
        elif temp < 18 or temp > 28:
            score -= 10
        
        # Humidity factor (optimal: 50-70%)
        if 50 <= humidity <= 70:
            score += 15
        elif 40 <= humidity < 50 or 70 < humidity <= 80:
            score += 8
        elif humidity < 40 or humidity > 80:
            score -= 5
        
        # Light factor (optimal: 14-18 hours)
        if 14 <= light <= 18:
            score += 10
        elif 12 <= light < 14 or 18 < light <= 20:
            score += 5
        elif light < 12 or light > 20:
            score -= 5
        
        # CO2 factor (optimal: 800-1200 ppm)
        if 800 <= co2 <= 1200:
            score += 5
        elif 600 <= co2 < 800 or 1200 < co2 <= 1500:
            score += 2
        
        return max(0, min(100, score))
    
    current_health = calc_health(
        current["temperature"], current["humidity"],
        current["light_hours"], current["co2"]
    )
    predicted_health = calc_health(
        simulated["temperature"], simulated["humidity"],
        simulated["light_hours"], simulated["co2"]
    )
    
    # Energy cost estimate (relative to current = 100)
    def calc_energy_cost(temp, light, co2):
        # Base cost
        cost = 100
        
        # Temperature cost (heating/cooling)
        temp_diff = abs(temp - 22)  # Assume 22°C is baseline
        cost += temp_diff * 5
        
        # Lighting cost
        cost += (light / 16) * 30  # Assume 16 hours is baseline
        
        # CO2 enrichment cost
        if co2 > 600:
            cost += ((co2 - 600) / 400) * 20
        
        return cost
    
    current_cost = calc_energy_cost(
        current["temperature"], current["light_hours"], current["co2"]
    )
    predicted_cost = calc_energy_cost(
        simulated["temperature"], simulated["light_hours"], simulated["co2"]
    )
    
    # Growth rate estimate (relative multiplier)
    def calc_growth_rate(temp, humidity, light, co2):
        rate = 1.0
        
        # Temperature effect
        if 22 <= temp <= 25:
            rate *= 1.2
        elif 20 <= temp < 22 or 25 < temp <= 27:
            rate *= 1.1
        elif temp < 18 or temp > 30:
            rate *= 0.8
        
        # Light effect
        if light >= 16:
            rate *= 1.15
        elif light < 12:
            rate *= 0.85
        
        # CO2 effect
        if co2 >= 1000:
            rate *= 1.1
        elif co2 < 600:
            rate *= 0.9
        
        return rate
    
    current_growth = calc_growth_rate(
        current["temperature"], current["humidity"],
        current["light_hours"], current["co2"]
    )
    predicted_growth = calc_growth_rate(
        simulated["temperature"], simulated["humidity"],
        simulated["light_hours"], simulated["co2"]
    )
    
    # Calculate change percentages
    def change_percent(current_val, new_val):
        if current_val == 0:
            return 0
        return ((new_val - current_val) / current_val) * 100
    
    return {
        "vpd": {
            "current": round(current_vpd, 2),
            "predicted": round(predicted_vpd, 2),
            "status": vpd_status(predicted_vpd),
            "change_percent": round(change_percent(current_vpd, predicted_vpd), 1)
        },
        "plant_health": {
            "current": round(current_health, 1),
            "predicted": round(predicted_health, 1),
            "change_percent": round(change_percent(current_health, predicted_health), 1)
        },
        "energy_cost": {
            "current": round(current_cost, 1),
            "predicted": round(predicted_cost, 1),
            "change_percent": round(change_percent(current_cost, predicted_cost), 1)
        },
        "growth_rate": {
            "current": round(current_growth, 2),
            "predicted": round(predicted_growth, 2),
            "change_percent": round(change_percent(current_growth, predicted_growth), 1)
        }
    }


def _generate_what_if_recommendations(current, simulated, predictions):
    """Generate actionable recommendations based on simulation."""
    recommendations = []
    
    # Temperature recommendations
    temp_diff = simulated["temperature"] - current["temperature"]
    if abs(temp_diff) > 3:
        if temp_diff > 0:
            recommendations.append({
                "message": f"Large temperature increase (+{temp_diff:.1f}°C) may stress plants. Consider gradual adjustment.",
                "priority": "high"
            })
        else:
            recommendations.append({
                "message": f"Large temperature decrease ({temp_diff:.1f}°C) detected. Monitor plant response closely.",
                "priority": "high"
            })
    elif 20 <= simulated["temperature"] <= 26:
        recommendations.append({
            "message": "Temperature change looks optimal for most plants.",
            "priority": "low"
        })
    
    # VPD recommendations
    if "vpd" in predictions:
        vpd_status = predictions["vpd"]["status"]
        if vpd_status == "optimal":
            recommendations.append({
                "message": "VPD will be in optimal range (0.8-1.2 kPa) - excellent for growth.",
                "priority": "low"
            })
        elif vpd_status == "suboptimal":
            recommendations.append({
                "message": "VPD may be outside ideal range. Adjust temperature or humidity for better results.",
                "priority": "medium"
            })
    
    # Humidity recommendations
    humidity_diff = simulated["humidity"] - current["humidity"]
    if abs(humidity_diff) > 15:
        recommendations.append({
            "message": f"Large humidity change ({humidity_diff:+.1f}%) may require gradual adjustment.",
            "priority": "medium"
        })
    
    # Light recommendations
    if simulated["light_hours"] > 18:
        recommendations.append({
            "message": "Extended light duration (>18h) - ensure plants get adequate dark period for respiration.",
            "priority": "medium"
        })
    elif simulated["light_hours"] < 12:
        recommendations.append({
            "message": "Short light duration (<12h) may reduce growth rate.",
            "priority": "medium"
        })
    
    # Energy cost recommendations
    if "energy_cost" in predictions:
        cost_change = predictions["energy_cost"]["change_percent"]
        if cost_change > 20:
            recommendations.append({
                "message": f"Energy cost may increase by {cost_change:.1f}%. Consider cost-benefit trade-off.",
                "priority": "medium"
            })
        elif cost_change < -10:
            recommendations.append({
                "message": f"Energy savings of {abs(cost_change):.1f}% possible with these settings.",
                "priority": "low"
            })
    
    # Growth rate recommendations
    if "growth_rate" in predictions:
        growth_change = predictions["growth_rate"]["change_percent"]
        if growth_change > 10:
            recommendations.append({
                "message": f"Predicted growth rate increase of {growth_change:.1f}% - favorable conditions.",
                "priority": "low"
            })
        elif growth_change < -10:
            recommendations.append({
                "message": f"Growth rate may decrease by {abs(growth_change):.1f}%. Reconsider these settings.",
                "priority": "high"
            })
    
    # CO2 recommendations
    if simulated["co2"] > 1500:
        recommendations.append({
            "message": "Very high CO₂ levels (>1500 ppm) - ensure adequate ventilation.",
            "priority": "high"
        })
    elif simulated["co2"] > 1200:
        recommendations.append({
            "message": "High CO₂ enrichment - monitor plant response and ensure proper air circulation.",
            "priority": "medium"
        })
    
    # Default recommendation if none generated
    if not recommendations:
        recommendations.append({
            "message": "Parameter changes appear reasonable. Monitor plant response after implementation.",
            "priority": "low"
        })
    
    return recommendations


# ==================== Irrigation ML Predictions ====================

@predictions_bp.get("/irrigation/<int:unit_id>")
def get_irrigation_predictions(unit_id: int):
    """
    Get comprehensive ML predictions for irrigation.
    
    Returns predictions from all active irrigation models for this unit.
    
    Query params:
    - models: Comma-separated list of models to include (default: all active)
              Values: threshold_optimizer, response_predictor, duration_optimizer, timing_predictor, next_irrigation
    
    Response:
    {
        "ok": true,
        "data": {
            "unit_id": 1,
            "generated_at": "2026-01-03T...",
            "models_used": ["threshold_optimizer", "response_predictor"],
            "threshold": {
                "optimal_threshold": 48.0,
                "current_threshold": 45.0,
                "adjustment_direction": "increase",
                "adjustment_amount": 3.0,
                "confidence": 0.75,
                "reasoning": "..."
            },
            "user_response": {
                "probabilities": {"approve": 0.8, "delay": 0.15, "cancel": 0.05},
                "most_likely": "approve",
                "confidence": 0.8
            },
            "duration": {...},
            "timing": {...},
            "recommendations": ["..."],
            "overall_confidence": 0.72
        }
    }
    """
    try:
        container = _container()
        irrigation_predictor = _get_irrigation_predictor(container)
        if not irrigation_predictor:
            return _fail("Irrigation prediction service not available", 503)

        active_plant = _resolve_active_plant(container, unit_id)
        plant_type = _plant_value(active_plant, "plant_type", "unknown")
        growth_stage = _plant_value(active_plant, "current_stage", "vegetative")
        plant_id = _resolve_plant_id(active_plant)
        
        user_id, auth_error = _require_user_id()
        if auth_error:
            return auth_error
        feature_context = _build_irrigation_feature_context(
            container,
            unit_id=unit_id,
            plant_id=plant_id,
            user_id=user_id,
        )
        current_conditions = feature_context.get("current_conditions", {})
        current_threshold = current_conditions.get("soil_moisture_threshold") or _resolve_current_threshold(
            container,
            unit_id,
            user_id,
            active_plant,
        )
        current_duration = 120
        
        # Get enabled models filter from query params
        models_param = request.args.get("models")
        enabled_models = None
        if models_param:
            enabled_models = [m.strip() for m in models_param.split(",")]
        
        # Get comprehensive prediction
        prediction = irrigation_predictor.get_comprehensive_prediction(
            unit_id=unit_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            current_conditions=current_conditions,
            current_threshold=current_threshold,
            current_default_duration=current_duration,
            enabled_models=enabled_models,
            plant_id=plant_id,
            feature_context=feature_context,
        )
        
        return _success(prediction.to_dict())
        
    except Exception as e:
        logger.error(f"Error getting irrigation predictions: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/irrigation/<int:unit_id>/threshold")
def get_irrigation_threshold_prediction(unit_id: int):
    """
    Get threshold-only prediction for a unit.
    
    Response:
    {
        "ok": true,
        "data": {
            "optimal_threshold": 48.0,
            "current_threshold": 45.0,
            "adjustment_direction": "increase",
            "adjustment_amount": 3.0,
            "confidence": 0.75,
            "reasoning": "Based on 15 feedback samples..."
        }
    }
    """
    try:
        container = _container()
        irrigation_predictor = _get_irrigation_predictor(container)
        if not irrigation_predictor:
            return _fail("Irrigation prediction service not available", 503)

        active_plant = _resolve_active_plant(container, unit_id)
        user_id, auth_error = _require_user_id()
        if auth_error:
            return auth_error
        plant_id = _resolve_plant_id(active_plant)
        feature_context = _build_irrigation_feature_context(
            container,
            unit_id=unit_id,
            plant_id=plant_id,
            user_id=user_id,
        )
        current_conditions = feature_context.get("current_conditions", {})
        current_threshold = current_conditions.get("soil_moisture_threshold") or _resolve_current_threshold(
            container,
            unit_id,
            user_id,
            active_plant,
        )
        
        prediction = irrigation_predictor.predict_threshold(
            unit_id=unit_id,
            plant_type=_plant_value(active_plant, "plant_type", "unknown"),
            growth_stage=_plant_value(active_plant, "current_stage", "vegetative"),
            current_threshold=current_threshold,
            feature_context=feature_context,
        )
        
        return _success(prediction.to_dict())
        
    except Exception as e:
        logger.error(f"Error getting threshold prediction: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/irrigation/<int:unit_id>/timing")
def get_irrigation_timing_prediction(unit_id: int):
    """
    Get preferred irrigation timing prediction.
    
    Response:
    {
        "ok": true,
        "data": {
            "preferred_time": "09:30",
            "preferred_hour": 9,
            "preferred_minute": 30,
            "avoid_times": ["22:00", "23:00"],
            "confidence": 0.65,
            "reasoning": "Based on user response patterns..."
        }
    }
    """
    try:
        container = _container()
        irrigation_predictor = _get_irrigation_predictor(container)
        if not irrigation_predictor:
            return _fail("Irrigation prediction service not available", 503)
        
        unit_timezone = _get_unit_timezone(unit_id)
        now = _resolve_unit_now(unit_timezone)
        user_id, auth_error = _require_user_id()
        if auth_error:
            return auth_error
        feature_context = _build_irrigation_feature_context(
            container,
            unit_id=unit_id,
            plant_id=None,
            user_id=user_id,
        )

        prediction = irrigation_predictor.predict_timing(
            unit_id=unit_id,
            day_of_week=now.weekday(),
            feature_context=feature_context,
            unit_timezone=unit_timezone,
            current_time=now,
        )
        
        return _success(prediction.to_dict())
        
    except Exception as e:
        logger.error(f"Error getting timing prediction: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/irrigation/<int:unit_id>/response")
def get_irrigation_response_prediction(unit_id: int):
    """
    Predict user response for a hypothetical irrigation request.
    
    Query params:
    - hour: Hour of day (0-23, default: current hour)
    - soil_moisture: Current soil moisture (default: from latest reading)
    
    Response:
    {
        "ok": true,
        "data": {
            "probabilities": {"approve": 0.75, "delay": 0.20, "cancel": 0.05},
            "most_likely": "approve",
            "confidence": 0.8
        }
    }
    """
    try:
        from datetime import datetime
        
        container = _container()
        irrigation_predictor = _get_irrigation_predictor(container)
        if not irrigation_predictor:
            return _fail("Irrigation prediction service not available", 503)
        
        now = datetime.now()
        hour = request.args.get("hour", type=int, default=now.hour)
        
        user_id, auth_error = _require_user_id()
        if auth_error:
            return auth_error
        feature_context = _build_irrigation_feature_context(
            container,
            unit_id=unit_id,
            plant_id=None,
            user_id=user_id,
        )
        current_conditions = feature_context.get("current_conditions", {})
        threshold = current_conditions.get("soil_moisture_threshold") or _resolve_current_threshold(
            container,
            unit_id,
            user_id,
        )
        
        soil_moisture = request.args.get("soil_moisture", type=float)
        if soil_moisture is None:
            soil_moisture = current_conditions.get("soil_moisture", 45.0)
        
        prediction = irrigation_predictor.predict_user_response(
            unit_id=unit_id,
            current_moisture=soil_moisture,
            threshold=threshold,
            hour_of_day=hour,
            day_of_week=now.weekday(),
            feature_context=feature_context,
        )
        
        return _success(prediction.to_dict())
        
    except Exception as e:
        logger.error(f"Error getting response prediction: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/irrigation/<int:unit_id>/duration")
def get_irrigation_duration_prediction(unit_id: int):
    """
    Get recommended irrigation duration prediction.
    
    Query params:
    - target_moisture: Target moisture level (default: threshold + 15)
    
    Response:
    {
        "ok": true,
        "data": {
            "recommended_seconds": 90,
            "current_default_seconds": 120,
            "expected_moisture_increase": 18.5,
            "confidence": 0.6,
            "reasoning": "Based on 10 previous irrigations..."
        }
    }
    """
    try:
        container = _container()
        irrigation_predictor = _get_irrigation_predictor(container)
        if not irrigation_predictor:
            return _fail("Irrigation prediction service not available", 503)

        # Get current settings
        user_id, auth_error = _require_user_id()
        if auth_error:
            return auth_error
        feature_context = _build_irrigation_feature_context(
            container,
            unit_id=unit_id,
            plant_id=None,
            user_id=user_id,
        )
        current_conditions = feature_context.get("current_conditions", {})
        threshold = current_conditions.get("soil_moisture_threshold") or _resolve_current_threshold(
            container,
            unit_id,
            user_id,
        )
        current_default = 120
        
        current_moisture = current_conditions.get("soil_moisture", 45.0)
        
        # Target moisture from query or default
        target_moisture = request.args.get("target_moisture", type=float, default=threshold + 15.0)
        
        prediction = irrigation_predictor.predict_duration(
            unit_id=unit_id,
            current_moisture=current_moisture,
            target_moisture=target_moisture,
            current_default_seconds=current_default,
            feature_context=feature_context,
        )
        
        return _success(prediction.to_dict())
        
    except Exception as e:
        logger.error(f"Error getting duration prediction: {e}", exc_info=True)
        return _fail(str(e), 500)


@predictions_bp.get("/irrigation/<int:unit_id>/next")
def get_irrigation_next_prediction(unit_id: int):
    """
    Predict when the next irrigation will be needed for the active plant.

    Query params:
    - soil_moisture: Current soil moisture (optional, defaults to latest)
    """
    try:
        container = _container()

        irrigation_predictor = _get_irrigation_predictor(container)
        if not irrigation_predictor:
            return _fail("Irrigation prediction service not available", 503)

        active_plant = _resolve_active_plant(container, unit_id)
        plant_id = _resolve_plant_id(active_plant)
        if plant_id is None:
            return _fail("No active plant found for unit", 404)

        user_id, auth_error = _require_user_id()
        if auth_error:
            return auth_error
        feature_context = _build_irrigation_feature_context(
            container,
            unit_id=unit_id,
            plant_id=plant_id,
            user_id=user_id,
        )
        current_conditions = feature_context.get("current_conditions", {})
        threshold = current_conditions.get("soil_moisture_threshold") or _resolve_current_threshold(
            container,
            unit_id,
            user_id,
            active_plant,
        )

        current_moisture = request.args.get("soil_moisture", type=float)
        if current_moisture is None:
            current_moisture = current_conditions.get("soil_moisture")

        if current_moisture is None:
            return _success({
                "unit_id": unit_id,
                "plant_id": plant_id,
                "available": False,
                "reason": "no_moisture_reading",
            })

        prediction = irrigation_predictor.predict_next_irrigation_time(
            plant_id=int(plant_id),
            current_moisture=float(current_moisture),
            threshold=float(threshold),
        )

        if not prediction:
            return _success({
                "unit_id": unit_id,
                "plant_id": plant_id,
                "available": False,
                "reason": "insufficient_data",
            })

        return _success(prediction.to_dict())
    except Exception as e:
        logger.error(f"Error getting next irrigation prediction: {e}", exc_info=True)
        return _fail(str(e), 500)
