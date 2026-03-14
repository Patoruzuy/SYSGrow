"""
Unit Health Endpoints
=====================

Health monitoring endpoints for growth units.
"""
import logging
from flask import Blueprint

from app.utils.time import iso_now
from app.enums.common import HealthLevel

from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
    get_sensor_service as _sensor_service,
    get_actuator_service as _actuator_service,
    get_growth_service as _growth_service,
    get_plant_service as _plant_service,
)

logger = logging.getLogger('health_api')


def register_unit_routes(health_api: Blueprint):
    """Register unit health routes on the blueprint."""

    @health_api.get('/units')
    def get_all_units_health():
        """
        Get health summaries for all units.
        
        Returns:
            {
                "units": [...],
                "summary": {
                    "total": 2,
                    "healthy": 2,
                    "degraded": 0,
                    "offline": 0
                }
            }
        """
        try:
            growth_service = _growth_service()
            sensor_svc = _sensor_service()
            actuator_svc = _actuator_service()
            
            runtimes = growth_service.get_unit_runtimes()
            units_list = []
            healthy_count = 0
            degraded_count = 0
            offline_count = 0
            
            for unit_id, runtime in runtimes.items():
                is_running = runtime.is_hardware_running()
                
                # Get sensor/actuator counts from hardware services
                sensor_count = 0
                actuator_count = 0
                stale_sensor_count = 0
                
                try:
                    sensors = sensor_svc.list_sensors(unit_id)
                    actuators = actuator_svc.list_actuators(unit_id)
                    sensor_count = len(sensors) if sensors else 0
                    actuator_count = len(actuators) if actuators else 0
                except:
                    pass
                
                # Get climate controller health from growth service
                controller = growth_service._climate_controllers.get(unit_id)
                if controller and hasattr(controller, "get_health_status"):
                    controller_health = controller.get_health_status()
                    stale_sensor_count = len(controller_health.get('stale_sensors', []))
                
                # Determine status
                if is_running and stale_sensor_count == 0:
                    status = HealthLevel.HEALTHY
                    healthy_count += 1
                elif is_running:
                    status = HealthLevel.DEGRADED
                    degraded_count += 1
                else:
                    status = HealthLevel.OFFLINE
                    offline_count += 1
                
                # Get plant count and active plant from PlantService (single source of truth)
                plant_service = _plant_service()
                plants = plant_service.list_plants(unit_id)
                plant_count = len(plants)
                active_plant = plant_service.get_active_plant(unit_id)
                
                units_list.append({
                    "unit_id": unit_id,
                    "name": runtime.unit_name,
                    "status": str(status),
                    "hardware_running": is_running,
                    "sensor_count": sensor_count,
                    "actuator_count": actuator_count,
                    "plant_count": plant_count,
                    "active_plant": active_plant.plant_name if active_plant else None,
                    "stale_sensors": stale_sensor_count
                })
            
            return _success({
                "units": units_list,
                "summary": {
                    "total": len(units_list),
                    "healthy": healthy_count,
                    "degraded": degraded_count,
                    "offline": offline_count
                }
            })
            
        except Exception as e:
            logger.exception("Error getting units health")
            return _fail(str(e), 500)

    @health_api.get('/units/<int:unit_id>')
    def get_unit_health(unit_id: int):
        """
        Get detailed health metrics for a specific growth unit.
        
        Args:
            unit_id: The ID of the unit
            
        Returns:
            {
                "unit_id": 1,
                "name": "...",
                "status": "healthy|degraded|offline",
                "hardware_running": true,
                "polling": {...},
                "controller": {...},
                "sensors": [...],
                "actuators": [...],
                "plants": [...],
                "timestamp": "..."
            }
        """
        try:
            growth_service = _growth_service()
            sensor_svc = _sensor_service()
            actuator_svc = _actuator_service()
            
            runtime = growth_service.get_unit_runtime(unit_id)
            if not runtime:
                return _fail(f"Unit {unit_id} not found", 404)
            
            is_running = runtime.is_hardware_running()
            
            # Get hardware health from services
            polling_health = sensor_svc.get_polling_health()
            controller_health = {}
            stale_sensor_count = 0
            
            # Get climate controller health from growth service
            controller = growth_service._climate_controllers.get(unit_id)
            if controller and hasattr(controller, "get_health_status"):
                controller_health = controller.get_health_status()
                stale_sensor_count = len(controller_health.get('stale_sensors', []))
            
            # Get devices from hardware services
            sensors = []
            actuators = []
            try:
                sensors = sensor_svc.list_sensors(unit_id) or []
                actuators = actuator_svc.list_actuators(unit_id) or []
            except:
                pass
                
            # Determine status
            if is_running and stale_sensor_count == 0:
                status = HealthLevel.HEALTHY
            elif is_running:
                status = HealthLevel.DEGRADED
            else:
                status = HealthLevel.OFFLINE
            
            # Get plants and active plant from PlantService (single source of truth)
            plant_service = _plant_service()
            plants = plant_service.list_plants(unit_id)
            active_plant = plant_service.get_active_plant(unit_id)
            
            return _success({
                "unit_id": unit_id,
                "name": runtime.unit_name,
                "status": str(status),
                "hardware_running": is_running,
                "polling": polling_health,
                "controller": controller_health,
                "sensors": sensors,
                "actuators": actuators,
                "plants": [p.to_dict() for p in plants],
                "active_plant": active_plant.to_dict() if active_plant else None,
                "timestamp": iso_now()
            })
            
        except Exception as e:
            logger.exception(f"Error getting health metrics for unit {unit_id}: {e}")
            return _fail(f"Failed to get unit health metrics: {str(e)}", 500)
