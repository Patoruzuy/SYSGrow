"""
Plant Journal & Growing Guide
==============================

Endpoints for:
- Plant journal (observations and nutrient records)
- Growing guide reference
- Harvest tracking
- Disease risk assessment

These endpoints support the Plants Hub dashboard.
"""
from __future__ import annotations

from flask import request
from app.utils.time import iso_now
from pathlib import Path
import json
import logging

from . import plants_api
from app.enums.common import RiskLevel
from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
    get_container as _container,
    get_plant_service as _plant_service,
    get_harvest_service as _harvest_service,
    get_growth_service as _growth_service,
    get_plant_journal_service as _journal_service,
    get_analytics_service as _analytics_service,
)

logger = logging.getLogger("plants_api.journal")


# ============================================================================
# PLANT HEALTH AGGREGATION (for Plants Hub)
# ============================================================================

@plants_api.get("/health")
def get_all_plants_health():
    """
    Get health status for all plants across all units.
    
    Returns:
        {
            "plants": [
                {
                    "plant_id": int,
                    "name": str,
                    "plant_type": str,
                    "current_health_status": "healthy|stressed|diseased",
                    "current_stage": str,
                    "days_in_stage": int,
                    "unit_id": int,
                    "unit_name": str
                }
            ],
            "summary": {
                "total": int,
                "healthy": int,
                "stressed": int,
                "diseased": int,
                "unknown": int,
                "health_score": int (0-100),
                "health_status": str
            }
        }
    """
    try:
        units = _growth_service().list_units()
        all_plants = []
        
        for unit in units:
            unit_plants = _plant_service().list_plants_as_dicts(unit["unit_id"])
            for plant in unit_plants:
                plant["unit_name"] = unit.get("unit_name", f"Unit {unit['unit_id']}")
                
                # Add health status from latest journal entry
                try:
                    latest_entries = _container().plant_journal_repo.get_entries(
                        plant_id=plant["plant_id"],
                        limit=1
                    )
                    logger.info(f"Plant {plant['plant_id']} ({plant.get('name')}): {len(latest_entries)} journal entries found")
                    if latest_entries and len(latest_entries) > 0:
                        latest = latest_entries[0]
                        # Journal entries have health_status field from observations
                        health_status = latest.get("health_status", "")
                        logger.info(f"Plant {plant['plant_id']} health_status: '{health_status}'")
                        plant["current_health_status"] = health_status
                    else:
                        plant["current_health_status"] = ""
                except Exception as e:
                    logger.error(f"Could not get health status for plant {plant['plant_id']}: {e}", exc_info=True)
                    plant["current_health_status"] = ""
                
                all_plants.append(plant)
        
        # Calculate summary statistics (previously done in JavaScript)
        total = len(all_plants)
        healthy = sum(1 for p in all_plants if p.get("current_health_status") == "healthy")
        stressed = sum(1 for p in all_plants if p.get("current_health_status") == "stressed")
        diseased = sum(1 for p in all_plants if p.get("current_health_status") == "diseased")
        unknown = total - healthy - stressed - diseased
        
        # Calculate weighted health score (healthy=1.0, stressed=0.5, diseased=0.0)
        if total > 0:
            weighted_score = ((healthy * 1.0) + (stressed * 0.5) + (diseased * 0.0)) / total
            health_score = round(weighted_score * 100)
        else:
            health_score = 100  # No plants = perfect score
        
        # Determine status text
        if health_score >= 80:
            health_status = "Excellent Health"
        elif health_score >= 60:
            health_status = "Some Issues Detected"
        elif health_score >= 40:
            health_status = "Multiple Issues"
        else:
            health_status = "Critical Attention Needed"
        
        return _success({
            "plants": all_plants,
            "summary": {
                "total": total,
                "healthy": healthy,
                "stressed": stressed,
                "diseased": diseased,
                "unknown": unknown,
                "health_score": health_score,
                "health_status": health_status
            }
        })
    except Exception as e:
        logger.error(f"Error fetching all plants health: {e}")
        return _fail("Failed to fetch plants health data", 500)


# ============================================================================
# GROWING GUIDE
# ============================================================================

@plants_api.get("/guide")
def get_plants_guide():
    """
    Get plant growing guide from plants_info.json.
    
    Returns:
        {
            "plants": [
                {
                    "id": str,
                    "common_name": str,
                    "species": str,
                    "pH_range": str,
                    "water_requirements": str,
                    "tips": str,
                    "growth_stages": []
                }
            ]
        }
    """
    try:
        from app.defaults import SystemConfigDefaults
        
        plants_data = []
        
        # Try to load from JSON file first
        try:
            backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
            plants_file = backend_dir / "plants_info.json"
            
            with plants_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                json_plants = data.get("plants_info") or []
                if json_plants:
                    plants_data = json_plants
        except Exception as e:
            logger.warning(f"Failed to load plants_info.json: {e}")
        
        # Fall back to defaults if needed
        if not plants_data:
            plants_data = SystemConfigDefaults.PLANTS_INFO or []
        
        # Normalize shape for consistency
        normalized_plants = []
        for plant in plants_data:
            common_name = plant.get("common_name") or plant.get("name") or "Unknown Plant"
            normalized_plants.append({
                "id": plant.get("id", ""),
                "common_name": common_name,
                "species": plant.get("species") or plant.get("variety") or common_name,
                "pH_range": plant.get("pH_range") or plant.get("ph_range") or "",
                "water_requirements": plant.get("water_requirements") or "",
                "tips": plant.get("tips") or "",
                "growth_stages": plant.get("growth_stages") or [],
            })
        
        return _success({"plants": normalized_plants})
    except Exception as e:
        logger.error(f"Error fetching plants guide: {e}")
        return _fail("Failed to fetch plants guide", 500)


@plants_api.get("/guide/full")
def get_plants_guide_full():
    """
    Get full plant growing guide with all details from plants_info.json.

    Returns complete plant data including:
    - Basic info (species, variety, pH_range, water_requirements)
    - Sensor requirements (soil, CO2, VPD, light spectrum)
    - Yield data (expected yield, difficulty, space requirements)
    - Nutritional info
    - Automation settings
    - Growth stages with conditions
    - Common issues and solutions
    - Companion plants
    - Harvest guide

    Returns:
        {
            "plants": [full plant objects from plants_info.json]
        }
    """
    try:
        plants_data = []

        # Try to load from JSON file first
        try:
            backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
            plants_file = backend_dir / "plants_info.json"

            with plants_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                json_plants = data.get("plants_info") or []
                if json_plants:
                    plants_data = json_plants
        except Exception as e:
            logger.warning(f"Failed to load plants_info.json for full guide: {e}")

        # Fall back to defaults if needed
        if not plants_data:
            from app.defaults import SystemConfigDefaults
            plants_data = SystemConfigDefaults.PLANTS_INFO or []

        return _success({"plants": plants_data})
    except Exception as e:
        logger.error(f"Error fetching full plants guide: {e}")
        return _fail("Failed to fetch full plants guide", 500)


@plants_api.get("/guide/<int:plant_id>")
def get_plant_detail(plant_id: int):
    """
    Get full details for a single plant by ID.

    Args:
        plant_id: The ID of the plant from plants_info.json

    Returns:
        {
            "plant": {full plant object}
        }
    """
    try:
        plants_data = []

        # Try to load from JSON file first
        try:
            backend_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
            plants_file = backend_dir / "plants_info.json"

            with plants_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
                json_plants = data.get("plants_info") or []
                if json_plants:
                    plants_data = json_plants
        except Exception as e:
            logger.warning(f"Failed to load plants_info.json for plant detail: {e}")

        # Fall back to defaults if needed
        if not plants_data:
            from app.defaults import SystemConfigDefaults
            plants_data = SystemConfigDefaults.PLANTS_INFO or []

        # Find plant by ID
        plant = next((p for p in plants_data if p.get("id") == plant_id), None)

        if not plant:
            return _fail(f"Plant with ID {plant_id} not found", 404)

        return _success({"plant": plant})
    except Exception as e:
        logger.error(f"Error fetching plant detail for ID {plant_id}: {e}")
        return _fail("Failed to fetch plant detail", 500)


# ============================================================================
# DISEASE RISK ASSESSMENT
# ============================================================================

@plants_api.get("/disease-risk")
def get_disease_risk():
    """
    Get disease risk assessment by growth unit.
    
    Returns:
        {
            "units": [
                {
                    "unit_id": int,
                    "unit_name": str,
                    "risk_level": "low|moderate|high|critical",
                    "temperature": float,
                    "humidity": float,
                    "risk_factors": []
                }
            ]
        }
    """
    try:
        units = _growth_service().list_units()
        units_risk = []
        
        analytics = _analytics_service()
        
        for unit in units:
            unit_id = unit["unit_id"]
            
            # Get latest sensor reading via service
            temperature = None
            humidity = None
            
            try:
                latest = analytics.get_latest_sensor_reading(unit_id=unit_id)
                if latest:
                    temperature = latest.get("temperature")
                    humidity = latest.get("humidity")
            except Exception as e:
                logger.warning(f"Failed to get sensor readings for unit {unit_id}: {e}")
            
            # Calculate risk level based on environmental conditions
            risk_level = RiskLevel.LOW
            risk_factors = []
            
            if temperature is not None and humidity is not None:
                # High humidity + moderate temperature = fungal risk
                if humidity > 70 and 20 <= temperature <= 30:
                    risk_level = RiskLevel.HIGH
                    risk_factors.append("High humidity with moderate temperature increases fungal disease risk")
                elif humidity > 65 and 18 <= temperature <= 32:
                    risk_level = RiskLevel.MODERATE
                    risk_factors.append("Elevated humidity may promote disease")
                
                # Very high temperature
                if temperature > 35:
                    if risk_level == RiskLevel.LOW:
                        risk_level = RiskLevel.MODERATE
                    risk_factors.append("High temperature stress")
                
                # Very low humidity
                if humidity < 30:
                    if risk_level == RiskLevel.LOW:
                        risk_level = RiskLevel.MODERATE
                    risk_factors.append("Low humidity may cause plant stress")
            
            units_risk.append({
                "unit_id": unit_id,
                "unit_name": unit.get("unit_name", f"Unit {unit_id}"),
                "risk_level": str(risk_level),
                "temperature": round(temperature, 1) if temperature is not None else None,
                "humidity": round(humidity, 1) if humidity is not None else None,
                "risk_factors": risk_factors
            })
        
        return _success({"units": units_risk})
    except Exception as e:
        logger.error(f"Error calculating disease risk: {e}")
        return _fail("Failed to calculate disease risk", 500)


# ============================================================================
# HARVEST TRACKING
# ============================================================================

@plants_api.get("/harvests")
def get_harvests():
    """
    Get recent harvest records.
    
    Query Parameters:
        limit: Maximum number of harvests (default: 50)
        unit_id: Filter by unit ID
        plant_id: Filter by plant ID
    
    Returns:
        {
            "harvests": [
                {
                    "harvest_id": int,
                    "plant_id": int,
                    "plant_name": str,
                    "unit_id": int,
                    "harvest_date": str (ISO),
                    "yield_amount": float,
                    "yield_unit": str,
                    "quality": str,
                    "notes": str
                }
            ]
        }
    """
    try:
        unit_id = request.args.get("unit_id", type=int)
        harvest_service = _harvest_service()
        harvests = harvest_service.get_harvest_reports(unit_id=unit_id)
        
        return _success({"harvests": harvests})
    except Exception as e:
        logger.error(f"Error fetching harvests: {e}")
        # Return empty list if table doesn't exist instead of error
        return _success({"harvests": []})


# ============================================================================
# PLANT JOURNAL
# ============================================================================

@plants_api.get("/journal")
def get_journal_entries():
    """
    Get plant journal entries (observations and nutrients).
    
    Query Parameters:
        limit: Maximum number of entries (default: 100)
        plant_id: Filter by plant ID
        unit_id: Filter by unit ID
        entry_type: Filter by type (observation|nutrient|treatment|note|watering)
        days: Only entries from last N days
    
    Returns:
        {
            "entries": [
                {
                    "entry_id": int,
                    "plant_id": int,
                    "plant_name": str,
                    "entry_type": "observation|nutrient|treatment|note|watering",
                    "observation_type": str (if observation),
                    "nutrient_type": str (if nutrient),
                    "amount": float (if nutrient),
                    "notes": str,
                    "created_at": str (ISO)
                }
            ]
        }
    """
    try:
        limit = int(request.args.get("limit", 100))
        plant_id = request.args.get("plant_id", type=int)
        unit_id = request.args.get("unit_id", type=int)
        entry_type = request.args.get("entry_type")
        days = request.args.get("days", type=int)
        
        entries = _journal_service().get_journal(
            plant_id=plant_id,
            unit_id=unit_id,
            entry_type=entry_type,
            limit=limit,
            days=days
        )
        
        return _success({"entries": entries})
    except Exception as e:
        logger.error(f"Error fetching journal entries: {e}")
        return _fail("Failed to fetch journal entries", 500)


@plants_api.post("/journal/observation")
def create_observation():
    """
    Record a plant observation.
    
    Form Data:
        plant_id: int (required)
        observation_type: str (required) - general|health|growth|pest|disease
        notes: str (required)
        health_status: str (optional) - for health observations
        severity_level: int (optional) - 1-5 scale
        symptoms: str (optional) - comma-separated list
        image_path: str (optional)
    
    Returns:
        {
            "entry_id": int,
            "message": "Observation recorded successfully"
        }
    """
    try:
        plant_id = request.form.get("plant_id", type=int)
        observation_type = request.form.get("observation_type")
        notes = request.form.get("notes", "").strip()
        health_status = request.form.get("health_status")
        severity_level = request.form.get("severity_level", type=int)
        symptoms_str = request.form.get("symptoms", "").strip()
        image_path = request.form.get("image_path")
        
        if not all([plant_id, observation_type, notes]):
            return _fail("Missing required fields: plant_id, observation_type, notes", 400)
        
        # Parse symptoms
        symptoms = [s.strip() for s in symptoms_str.split(",")] if symptoms_str else None
        
        entry_id = _journal_service().record_observation(
            plant_id=plant_id,
            observation_type=observation_type,
            notes=notes,
            health_status=health_status,
            severity_level=severity_level,
            symptoms=symptoms,
            image_path=image_path
        )
        
        if not entry_id:
            return _fail("Failed to record observation", 500)
        
        return _success({
            "entry_id": entry_id,
            "message": "Observation recorded successfully"
        }, 201)
    except Exception as e:
        logger.error(f"Error creating observation: {e}")
        return _fail("Failed to record observation", 500)


@plants_api.post("/journal/nutrients")
def create_nutrient_record():
    """
    Record nutrient application (single plant or bulk).
    
    Form Data:
        application_type: str (required) - single|bulk
        plant_id: int (required if single)
        unit_id: int (required if bulk)
        nutrient_type: str (required) - nitrogen|phosphorus|potassium|calcium|custom
        nutrient_name: str (required) - product name
        amount: float (required)
        unit: str (optional) - ml|g|tsp (default: ml)
        notes: str (optional)
    
    Returns:
        {
            "entries_created": int,
            "message": "Nutrients recorded successfully"
        }
    """
    try:
        application_type = request.form.get("application_type")
        plant_id = request.form.get("plant_id", type=int)
        unit_id = request.form.get("unit_id", type=int)
        nutrient_type = request.form.get("nutrient_type")
        nutrient_name = request.form.get("nutrient_name", "")
        amount = request.form.get("amount", type=float)
        unit = request.form.get("unit", "ml")
        notes = request.form.get("notes", "").strip()
        
        if not all([application_type, nutrient_type, nutrient_name, amount is not None]):
            return _fail("Missing required fields", 400)
        
        if application_type == "single":
            if not plant_id:
                return _fail("plant_id required for single application", 400)
            
            entry_id = _journal_service().record_nutrient_application(
                plant_id=plant_id,
                nutrient_type=nutrient_type,
                nutrient_name=nutrient_name,
                amount=amount,
                unit=unit,
                notes=notes
            )
            
            if not entry_id:
                return _fail("Failed to record nutrient", 500)
            
            return _success({
                "entries_created": 1,
                "entry_ids": [entry_id],
                "message": "Nutrient recorded successfully"
            }, 201)
            
        elif application_type == "bulk":
            if not unit_id:
                return _fail("unit_id required for bulk application", 400)
            
            # Get all plants in unit via service
            unit_plants = _plant_service().list_plants_as_dicts(unit_id)
            plant_ids = [p["plant_id"] for p in unit_plants]
            
            if not plant_ids:
                return _fail(f"No plants found in unit {unit_id}", 404)
            
            result = _journal_service().record_bulk_nutrient_application(
                plant_ids=plant_ids,
                nutrient_type=nutrient_type,
                nutrient_name=nutrient_name,
                amount=amount,
                unit=unit,
                notes=notes
            )
            
            if not result.get("success"):
                return _fail("Failed to record nutrients", 500)
            
            message = f"Nutrients recorded for {result['entries_created']} plant(s)"
            return _success({
                "entries_created": result["entries_created"],
                "entry_ids": result.get("entry_ids", []),
                "message": message
            }, 201)
        else:
            return _fail("Invalid application_type. Use 'single' or 'bulk'", 400)
            
    except Exception as e:
        logger.error(f"Error recording nutrients: {e}")
        return _fail("Failed to record nutrients", 500)


@plants_api.post("/journal/watering")
def create_watering_record():
    """
    Record a manual watering event in the plant journal.

    Form Data:
        plant_id: int (required)
        unit_id: int (optional - will be inferred if missing)
        amount: float (optional)
        unit: str (optional) - ml|l (default: ml)
        notes: str (optional)
        watered_at_utc: str (optional ISO timestamp)
        user_id: int (optional)
    """
    try:
        plant_id = request.form.get("plant_id", type=int)
        unit_id = request.form.get("unit_id", type=int)
        amount = request.form.get("amount", type=float)
        unit = request.form.get("unit", "ml")
        notes = request.form.get("notes", "").strip()
        watered_at_utc = request.form.get("watered_at_utc")
        user_id = request.form.get("user_id", type=int)

        if not plant_id:
            return _fail("plant_id is required", 400)

        if unit_id is None:
            plant = _plant_service().get_plant(plant_id)
            if plant is not None:
                unit_id = getattr(plant, "unit_id", None) or getattr(plant, "unit", None)

        entry_id = _journal_service().record_watering_event(
            plant_id=plant_id,
            unit_id=unit_id,
            amount=amount,
            unit=unit,
            notes=notes,
            user_id=user_id,
            watered_at_utc=watered_at_utc,
        )

        if not entry_id:
            return _fail("Failed to record watering event", 500)

        return _success({
            "entry_id": entry_id,
            "message": "Watering recorded successfully",
        }, 201)
    except Exception as e:
        logger.error(f"Error recording watering event: {e}")
        return _fail("Failed to record watering event", 500)
