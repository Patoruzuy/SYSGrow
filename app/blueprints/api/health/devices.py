"""
Device Health Endpoints
=======================

Health monitoring endpoints for sensors and actuators.
"""
import logging
from flask import Blueprint, request

from app.utils.time import iso_now

from app.blueprints.api._common import (
    get_container as _container,
    success as _success,
    fail as _fail,
    get_sensor_service as _sensor_service,
    get_actuator_service as _actuator_service,
    get_growth_service as _growth_service,
    get_device_health_service as _device_health_service,
)

logger = logging.getLogger('health_api')


def register_device_routes(health_api: Blueprint):
    """Register device health routes on the blueprint."""

    @health_api.get('/devices')
    def get_devices_health():
        """
        Get aggregated device-level health across all units.
        
        Returns:
            {
                "sensors": {
                    "total": 10,
                    "healthy": 8,
                    "degraded": 1,
                    "offline": 1
                },
                "actuators": {
                    "total": 6,
                    "operational": 5,
                    "failed": 1
                },
                "by_unit": {...}
            }
        """
        try:
            container = _container()
            growth_service = getattr(container, "growth_service", None)
            device_health_service = getattr(container, "device_health_service", None)
            
            if not growth_service:
                return _fail("Required services not available", 503)
            
            runtimes = growth_service.get_unit_runtimes()
            
            total_sensors = 0
            healthy_sensors = 0
            degraded_sensors = 0
            offline_sensors = 0
            
            total_actuators = 0
            operational_actuators = 0
            failed_actuators = 0
            
            by_unit = {}
            
            for unit_id, runtime in runtimes.items():
                try:
                    # Use hardware services directly
                    sensor_svc = _sensor_service()
                    actuator_svc = _actuator_service()
                    sensors = sensor_svc.list_sensors(unit_id) or []
                    actuators = actuator_svc.list_actuators(unit_id) or []
                    
                    unit_healthy = 0
                    unit_degraded = 0
                    unit_offline = 0
                    
                    # Check sensor health
                    for sensor in sensors:
                        sensor_id = sensor.get('id') or sensor.get('sensor_id')
                        if sensor_id and device_health_service:
                            try:
                                health_result = device_health_service.get_sensor_health(sensor_id)
                                if health_result.get('success'):
                                    health_score = health_result.get('health_score', 0)
                                    if health_score >= 80:
                                        unit_healthy += 1
                                        healthy_sensors += 1
                                    elif health_score >= 50:
                                        unit_degraded += 1
                                        degraded_sensors += 1
                                    else:
                                        unit_offline += 1
                                        offline_sensors += 1
                                else:
                                    unit_offline += 1
                                    offline_sensors += 1
                            except Exception:
                                unit_offline += 1
                                offline_sensors += 1
                        else:
                            unit_offline += 1
                            offline_sensors += 1
                    
                    total_sensors += len(sensors)
                    
                    # Check actuator status
                    unit_operational = 0
                    unit_failed = 0
                    
                    for actuator in actuators:
                        status = actuator.get('status', 'unknown')
                        if status in ['on', 'off', 'operational']:
                            unit_operational += 1
                            operational_actuators += 1
                        else:
                            unit_failed += 1
                            failed_actuators += 1
                    
                    total_actuators += len(actuators)
                    
                    by_unit[str(unit_id)] = {
                        "sensors": {
                            "total": len(sensors),
                            "healthy": unit_healthy,
                            "degraded": unit_degraded,
                            "offline": unit_offline
                        },
                        "actuators": {
                            "total": len(actuators),
                            "operational": unit_operational,
                            "failed": unit_failed
                        }
                    }
                except Exception as e:
                    logger.warning(f"Error processing unit {unit_id} devices: {e}")
                    continue
            
            return _success({
                "sensors": {
                    "total": total_sensors,
                    "healthy": healthy_sensors,
                    "degraded": degraded_sensors,
                    "offline": offline_sensors
                },
                "actuators": {
                    "total": total_actuators,
                    "operational": operational_actuators,
                    "failed": failed_actuators
                },
                "by_unit": by_unit,
                "timestamp": iso_now()
            })
            
        except Exception as e:
            logger.exception("Error getting devices health")
            return _fail(str(e), 500)

    @health_api.get('/sensors/<int:sensor_id>')
    def get_sensor_health(sensor_id: int):
        """
        Get health status for a specific sensor.
        
        Args:
            sensor_id: The ID of the sensor
            
        Returns:
            {
                "success": true,
                "sensor_id": 1,
                "health_score": 95,
                "status": "operational",
                ...
            }
        """
        try:
            from app.blueprints.api.devices.utils import _device_health_service
            device_health = _device_health_service()
            result = device_health.get_sensor_health(sensor_id)
            
            if result.get('success'):
                return _success(result)
            else:
                error_msg = result.get('error', 'Failed to get health')
                error_type = result.get('error_type', 'unknown')
                
                logger.warning(f"Sensor health check failed for sensor {sensor_id}: {error_msg} (type: {error_type})")
                
                if error_type == 'not_found':
                    return _fail(error_msg, 404)
                elif error_type in ['service_unavailable', 'runtime_unavailable']:
                    return _fail(error_msg, 503)
                elif error_type == 'invalid_state':
                    return _fail(error_msg, 400)
                elif error_type == 'no_data':
                    return _fail(error_msg, 404)
                else:
                    return _fail(error_msg, 400)
                    
        except Exception as e:
            logger.error(f"Exception in get_sensor_health for sensor {sensor_id}: {e}", exc_info=True)
            return _fail(str(e), 500)

    @health_api.get('/actuators/<int:actuator_id>')
    def get_actuator_health(actuator_id: int):
        """
        Get health history for an actuator.
        
        Args:
            actuator_id: The ID of the actuator
            limit: Number of history records to return (default: 100)
            
        Returns:
            {
                "actuator_id": 1,
                "health_history": [...],
                "count": 100
            }
        """
        try:
            limit = request.args.get('limit', 100, type=int)
            
            device_health = _device_health_service()
            history = device_health.get_actuator_health_history(actuator_id, limit)
            
            return _success({
                "actuator_id": actuator_id,
                "health_history": history,
                "count": len(history)
            })
            
        except Exception as e:
            return _fail(str(e), 500)

    @health_api.post('/actuators/<int:actuator_id>')
    def save_actuator_health(actuator_id: int):
        """
        Save actuator health snapshot.
        
        Args:
            actuator_id: The ID of the actuator
            
        Request Body:
            {
                "health_score": 95,
                "status": "operational",
                "total_operations": 1000,
                "failed_operations": 5,
                "average_response_time": 0.05
            }
            
        Returns:
            {
                "history_id": 123,
                "message": "Health snapshot saved"
            }
        """
        try:
            data = request.get_json()
            
            health_score = data.get('health_score')
            status = data.get('status')
            total_operations = data.get('total_operations', 0)
            failed_operations = data.get('failed_operations', 0)
            average_response_time = data.get('average_response_time', 0.0)
            
            if health_score is None or status is None:
                return _fail("health_score and status are required", 400)
            device_health = _device_health_service()
            history_id = device_health.save_actuator_health(
                actuator_id=actuator_id,
                health_score=health_score,
                status=status,
                total_operations=total_operations,
                failed_operations=failed_operations,
                average_response_time=average_response_time
            )
            
            if history_id:
                return _success({
                    "history_id": history_id,
                    "message": "Health snapshot saved successfully"
                }, 201)
            else:
                return _fail("Failed to save health snapshot", 500)
                
        except Exception as e:
            logger.exception(f"Error saving actuator health for actuator {actuator_id}: {e}")
            return _fail(str(e), 500)
