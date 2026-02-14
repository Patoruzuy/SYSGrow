"""
Plant CRUD Operations
=====================

Endpoints for creating, reading, updating, and deleting plants within growth units.
"""
from __future__ import annotations

from flask import request
from pydantic import ValidationError
from app.utils.plant_json_handler import PlantJsonHandler
import logging

from . import plants_api
from app.enums.growth import PlantStage
from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
    get_growth_service as _growth_service,
    get_plant_service as _plant_service,
)
from app.schemas import AddPlantToCrudRequest, ModifyPlantCrudRequest

logger = logging.getLogger("plants_api.crud")


# ============================================================================
# PLANT CRUD OPERATIONS
# ============================================================================

@plants_api.get("/units/<int:unit_id>/plants")
def list_plants(unit_id: int):
    """List all plants in a growth unit"""
    logger.info(f"Listing plants for growth unit {unit_id}")
    try:
        # Verify unit exists
        if not _growth_service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)
        
        plant_service = _plant_service()
        plants = plant_service.list_plants(unit_id)
        logger.info(f"Found {len(plants)} plants in unit {unit_id}")
        
        return _success({"plants": plants, "count": len(plants)})
        
    except Exception as e:
        logger.exception(f"Error listing plants for unit {unit_id}: {e}")
        return _fail("Failed to list plants", 500)


@plants_api.post("/units/<int:unit_id>/plants")
def add_plant(unit_id: int):
    """Add a new plant to a growth unit"""
    logger.info(f"Adding plant to growth unit {unit_id}")
    try:
        raw = request.get_json() or {}
        
        try:
            body = AddPlantToCrudRequest(**raw)
        except ValidationError as ve:
            return _fail("Invalid request", 400, details={"errors": ve.errors()})
        
        # Verify unit exists
        if not _growth_service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)
        
        plant_service = _plant_service()
        plant = plant_service.create_plant(
            unit_id=unit_id,
            plant_name=body.name,
            plant_type=body.plant_type,
            current_stage=body.current_stage or str(PlantStage.SEEDLING),
            days_in_stage=body.days_in_stage,
            moisture_level=body.moisture_level,
            sensor_ids=body.sensor_ids,
            condition_profile_id=body.condition_profile_id,
            condition_profile_mode=body.condition_profile_mode,
            condition_profile_name=body.condition_profile_name,
            pot_size_liters=body.pot_size_liters,
            pot_material=body.pot_material,
            growing_medium=body.growing_medium,
            medium_ph=body.medium_ph,
            strain_variety=body.strain_variety,
            expected_yield_grams=body.expected_yield_grams,
            light_distance_cm=body.light_distance_cm,
        )
        
        if plant:
            logger.info(f"Created plant {plant.get('plant_id')} in unit {unit_id}")
            return _success(plant, 201)
        else:
            logger.error(f"Failed to create plant in unit {unit_id}")
            return _fail("Failed to create plant", 500)
            
    except ValueError as e:
        logger.warning(f"Validation error adding plant: {e}")
        return _fail(str(e), 400)
    except Exception as e:
        logger.exception(f"Error adding plant to unit {unit_id}: {e}")
        return _fail("Failed to add plant", 500)


@plants_api.get("/plants/<int:unit_id>/<int:plant_id>")
def get_plant(unit_id: int, plant_id: int):
    """Get a specific plant by ID"""
    logger.info(f"Getting plant {plant_id} from unit {unit_id}")
    try:
        plant_service = _plant_service()
        plant = plant_service.get_plant(plant_id, unit_id)
        plant = plant.to_dict() if plant else None
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)
        
        logger.info(f"Retrieved plant {plant_id}: {plant.get('plant_name')}")
        return _success(plant)
        
    except Exception as e:
        logger.exception(f"Error getting plant {plant_id}: {e}")
        return _fail("Failed to get plant", 500)


@plants_api.get("/plants/<int:plant_id>")
def get_plant_by_id(plant_id: int):
    """Get a specific plant by ID (unit resolved automatically)."""
    logger.info("Getting plant %s", plant_id)
    try:
        plant_service = _plant_service()
        plant = plant_service.get_plant(plant_id)
        plant = plant.to_dict()
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)

        logger.info("Retrieved plant %s: %s", plant_id, plant.get("plant_name"))
        return _success(plant)

    except Exception as e:
        logger.exception("Error getting plant %s: %s", plant_id, e)
        return _fail("Failed to get plant", 500)


@plants_api.put("/plants/<int:plant_id>")
def update_plant(plant_id: int):
    """Update plant information"""
    logger.info(f"Updating plant {plant_id}")
    try:
        raw = request.get_json() or {}
        
        if not raw:
            return _fail("No update data provided", 400)
        
        try:
            body = ModifyPlantCrudRequest(**raw)
        except ValidationError as ve:
            return _fail("Invalid request", 400, details={"errors": ve.errors()})
        
        plant_service = _plant_service()

        # Verify plant exists
        if not plant_service.get_plant(plant_id):
            return _fail(f"Plant {plant_id} not found", 404)

        # Update plant using service method
        plant = plant_service.update_plant(
            plant_id=plant_id,
            plant_name=body.name,
            plant_type=body.plant_type,
            pot_size_liters=body.pot_size_liters,
            medium_ph=body.medium_ph,
            strain_variety=body.strain_variety,
            expected_yield_grams=body.expected_yield_grams,
            light_distance_cm=body.light_distance_cm,
        )

        if body.soil_moisture_threshold_override is not None:
            plant_service.update_soil_moisture_threshold(
                plant_id=plant_id,
                threshold=body.soil_moisture_threshold_override,
            )

        # Handle stage update separately (if provided)
        if body.current_stage:
            plant_service.update_plant_stage(
                plant_id=plant_id,
                new_stage=body.current_stage,
                days_in_stage=body.days_in_stage or 0
            )
            plant = plant_service.get_plant(plant_id)
        
        if plant:
            return _success(plant)
        else:
            return _fail("Failed to update plant", 500)
            
    except ValueError as e:
        logger.warning(f"Validation error updating plant: {e}")
        return _fail(str(e), 400)
    except Exception as e:
        logger.exception(f"Error updating plant {plant_id}: {e}")
        return _fail("Failed to update plant", 500)


@plants_api.post("/plants/<int:plant_id>/apply-profile")
def apply_condition_profile_to_plant(plant_id: int):
    """
    Apply a condition profile to a live plant.

    Body:
        - profile_id (required)
        - mode (optional): active or template
        - name (optional): name for cloned profile
        - user_id (optional)
    """
    try:
        raw = request.get_json() or {}
        profile_id = raw.get("profile_id")
        if not profile_id:
            return _fail("profile_id is required", 400)

        plant_service = _plant_service()
        user_id = raw.get("user_id")
        mode = raw.get("mode")
        name = raw.get("name")

        result = plant_service.apply_condition_profile_to_plant(
            plant_id=plant_id,
            profile_id=profile_id,
            mode=mode,
            name=name,
            user_id=user_id,
        )
        if not result:
            return _fail("Failed to apply condition profile", 500)
        return _success(result)
    except ValueError as e:
        return _fail(str(e), 400)
    except Exception as e:
        logger.exception("Error applying condition profile to plant %s: %s", plant_id, e)
        return _fail("Failed to apply condition profile", 500)


@plants_api.delete("/units/<int:unit_id>/plants/<int:plant_id>")
def remove_plant(unit_id: int, plant_id: int):
    """Remove a plant from a growth unit"""
    logger.info(f"Removing plant {plant_id} from growth unit {unit_id}")
    try:
        # Verify unit exists
        if not _growth_service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)
        
        plant_service = _plant_service()
        
        # Verify plant exists (idempotent delete: missing plant returns success)
        plant = plant_service.get_plant(plant_id)
        if not plant:
            logger.info(
                "Plant %s already removed or not found for unit %s",
                plant_id,
                unit_id,
            )
            return _success(
                {"plant_id": plant_id, "unit_id": unit_id, "removed": False},
                message="Plant already removed",
            )
        
        # Verify plant belongs to unit
        if plant.get('unit_id') != unit_id:
            return _fail(f"Plant {plant_id} does not belong to unit {unit_id}", 400)

        success = plant_service.remove_plant(unit_id, plant_id)
        
        if success:
            return _success({"plant_id": plant_id, "unit_id": unit_id})
        else:
            return _fail("Failed to remove plant", 500)
            
    except Exception as e:
        logger.exception(f"Error removing plant {plant_id}: {e}")
        return _fail("Failed to remove plant", 500)


# ============================================================================
# PLANT CATALOG
# ============================================================================

@plants_api.get("/catalog")
def get_plant_catalog():
    """
    Get available plants from catalog.
    
    Returns catalog data suitable for dropdown selection and auto-fill.
    """
    logger.info("Loading plant catalog")
    try:
        handler = PlantJsonHandler()
        plants = handler.get_plants_info()
        
        # Transform for frontend use
        catalog = []
        for plant in plants:
            # Extract sensor requirements (handle nested structure)
            sensor_reqs = plant.get("sensor_requirements", {})
            soil_moisture_range = sensor_reqs.get("soil_moisture_range", {})
            temp_range = sensor_reqs.get("soil_temperature_C", {})
            
            # Extract yield data
            yield_data = plant.get("yield_data", {})
            expected_yield = yield_data.get("expected_yield_per_plant", {})
            
            # Parse pH range string (e.g., "6.0-7.0" -> [6.0, 7.0])
            ph_range_str = plant.get("pH_range", "")
            ph_range = None
            if ph_range_str and "-" in ph_range_str:
                try:
                    parts = ph_range_str.split("-")
                    ph_range = [float(parts[0]), float(parts[1])]
                except (ValueError, IndexError):
                    ph_range = None

            gdd_base_temp_c = plant.get("gdd_base_temp_c")
            if gdd_base_temp_c is None:
                thermal_time = plant.get("thermal_time") or {}
                if isinstance(thermal_time, dict):
                    gdd_base_temp_c = thermal_time.get("base_temp_c")
            
            catalog_entry = {
                "id": str(plant.get("id", "")),  # Convert to string for select value
                "common_name": plant.get("common_name"),
                "species": plant.get("species"),
                "variety": plant.get("variety"),
                "aliases": plant.get("aliases", []),
                
                # Requirements for auto-fill
                "ph_range": ph_range,
                "water_requirements": plant.get("water_requirements"),
                
                # Sensor thresholds for requirements display
                "sensor_requirements": {
                    "soil_moisture_min": soil_moisture_range.get("min"),
                    "soil_moisture_max": soil_moisture_range.get("max"),
                    "temperature_min": temp_range.get("min"),
                    "temperature_max": temp_range.get("max"),
                },
                
                # Metadata
                "difficulty_level": yield_data.get("difficulty_level", "medium"),
                "average_yield": expected_yield.get("max", 0),  # Use max as average
                "growth_stages": plant.get("growth_stages", []),
                "gdd_base_temp_c": gdd_base_temp_c,
                
                # Tips
                "tips": plant.get("tips"),
                "companion_plants": plant.get("companion_plants", {}).get("beneficial", []),
            }
            catalog.append(catalog_entry)
        
        logger.info(f"Loaded {len(catalog)} plants from catalog")
        return _success(catalog)
        
    except FileNotFoundError:
        logger.warning("plants_info.json not found")
        return _success([])  # Return empty array if file doesn't exist
    except Exception as e:
        logger.exception(f"Error loading plant catalog: {e}")
        return _fail("Failed to load plant catalog", 500)


@plants_api.post("/catalog/custom")
def add_custom_plant_to_catalog():
    """
    Add a custom plant to the catalog for future use.
    
    Expects JSON with plant data following plants_info.json schema.
    """
    logger.info("Adding custom plant to catalog")
    try:
        data = request.get_json()
        
        if not data:
            return _fail("No data provided", 400)
        
        # Validate required fields
        required_fields = ["common_name", "species", "variety"]
        missing = [f for f in required_fields if not data.get(f)]
        if missing:
            return _fail(f"Missing required fields: {', '.join(missing)}", 400)
        
        handler = PlantJsonHandler()
        
        # Check if plant already exists
        if handler.plant_exists(data["common_name"]):
            return _fail(f"Plant '{data['common_name']}' already exists in catalog", 409)
        
        # Add plant to catalog
        success = handler.add_plant(data)
        
        if success:
            logger.info(f"Added custom plant '{data['common_name']}' to catalog")
            return _success({"message": "Plant added to catalog", "plant_name": data["common_name"]}, 201)
        else:
            return _fail("Failed to add plant to catalog", 500)
            
    except Exception as e:
        logger.exception(f"Error adding custom plant to catalog: {e}")
        return _fail("Failed to add plant to catalog", 500)
