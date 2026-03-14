"""
Device Health Service.

Pure delegator for device health monitoring operations.

Post-refactoring architecture (Jan 2025):
- Pure delegator to utility services (CalibrationService, AnomalyDetectionService)
- Direct service access (no wrapper patterns)
- NO legacy hardware_manager code
- NO runtime manager access

Responsibilities:
- Sensor health monitoring, calibration, statistics, and anomaly detection
- Actuator health monitoring, calibration, and anomaly detection
- Historical data retrieval for health metrics
- Publishing health events

Architecture:
    DeviceHealthService → Utility Services (calibration, anomaly_detection)
                       → Repository (persistence)
                       → Hardware Services (sensor_service, actuator_service)
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.application.alert_service import AlertService
    from app.services.hardware import SensorManagementService, ActuatorManagementService

from app.enums.events import DeviceEvent
from app.schemas.events import (
    ActuatorAnomalyPayload,
    ActuatorCalibrationPayload,
    ActuatorAnomalyResolvedPayload,
)
from app.services.utilities.calibration_service import CalibrationService
from app.services.utilities.anomaly_detection_service import AnomalyDetectionService
from app.services.application.zigbee_management_service import ZigbeeManagementService
from app.utils.event_bus import EventBus
from infrastructure.database.repositories.devices import DeviceRepository

logger = logging.getLogger(__name__)


class DeviceHealthService:
    """
    Pure delegator for device health monitoring.
    
    All health operations delegated to:
    - CalibrationService (sensor/actuator calibration)
    - AnomalyDetectionService (anomaly detection)
    - Hardware services (sensor_service, actuator_service)
    - Repository (persistence)
    """
    
    def __init__(
        self,
        repository: DeviceRepository,
        event_bus: Optional[EventBus] = None,
        mqtt_client: Optional[Any] = None,
        alert_service: Optional["AlertService"] = None,
        system_health_service: Optional[Any] = None,
        sensor_management_service: Optional["SensorManagementService"] = None,
        actuator_management_service: Optional["ActuatorManagementService"] = None,
        zigbee_service: Optional[Any] = None,  # Shared ZigbeeManagementService
        offline_threshold_minutes: int = 15,
    ):
        """
        Initialize DeviceHealthService.
        
        Args:
            repository: Device repository for database operations
            event_bus: Optional event bus for publishing health events
            mqtt_client: Optional MQTT client for discovery service
            alert_service: Alert service for health alerts
            system_health_service: System health service for sensor health tracking
            sensor_management_service: Sensor management service (new architecture)
            actuator_management_service: Actuator management service (new architecture)
            zigbee_service: Shared ZigbeeManagementService to prevent duplicate MQTT subscriptions
        """
        self.repository = repository
        self.event_bus = event_bus or EventBus()
        self.alert_service = alert_service
        self.system_health_service = system_health_service
        
        # Hardware services (singleton, memory-first)
        self.sensor_service = sensor_management_service
        self.actuator_service = actuator_management_service
        
        # Utility services
        self.calibration_service = CalibrationService(repository=repository)
        self.anomaly_service = AnomalyDetectionService()
        # Use shared zigbee_service to prevent duplicate MQTT subscriptions
        self.discovery_service = zigbee_service
        # Threshold (minutes) to consider a device offline when no recent readings
        self.offline_threshold_minutes = int(offline_threshold_minutes or 15)
        
        logger.info("DeviceHealthService initialized (pure delegator)")
    
    def _get_sensor_unit_id(self, sensor_id: int) -> Optional[int]:
        """Find which unit a sensor belongs to."""
        sensor = self.repository.find_sensor_config_by_id(sensor_id)
        return int(sensor.get("unit_id")) if sensor and sensor.get("unit_id") is not None else None
    
    def _get_actuator_unit_id(self, actuator_id: int) -> Optional[int]:
        """Find which unit an actuator belongs to."""
        actuator = self.repository.find_actuator_config_by_id(actuator_id)
        return int(actuator.get("unit_id")) if actuator and actuator.get("unit_id") is not None else None
    
    # ==================== Sensor Health Operations ====================
    
    def calibrate_sensor(
        self,
        sensor_id: int,
        reference_value: float,
        calibration_type: str = "linear"
    ) -> Dict[str, Any]:
        """
        Calibrate a sensor with a known reference value.
        
        Calls calibration service directly (no UnitRuntimeManager wrapper).
        
        Args:
            sensor_id: ID of sensor to calibrate
            reference_value: Known correct value for current reading
            calibration_type: Type of calibration (linear, polynomial, lookup)
            
        Returns:
            dict: Result with success status and details
        """
        try:
            # Validate inputs
            if not isinstance(sensor_id, int) or sensor_id <= 0:
                raise ValueError(f"Invalid sensor_id: {sensor_id}")
            if not isinstance(reference_value, (int, float)):
                raise ValueError(f"Invalid reference_value: {reference_value}")
            if calibration_type not in ['linear', 'polynomial', 'lookup']:
                logger.warning(f"Unknown calibration_type '{calibration_type}', using 'linear'")
                calibration_type = 'linear'
            
            # Find unit and verify sensor exists
            unit_id = self._get_sensor_unit_id(sensor_id)
            if not unit_id:
                return {
                    "success": False,
                    "error": f"Sensor {sensor_id} not found",
                    "error_type": "not_found"
                }
            
            # Read current sensor value from sensor service
            if not self.sensor_service:
                return {
                    "success": False,
                    "error": "Sensor service not available",
                    "error_type": "service_unavailable"
                }
            
            reading = self.sensor_service.read_sensor(sensor_id)
            if not reading:
                raise RuntimeError(f"Failed to read sensor {sensor_id}")
            
            measured_value = (
                reading.value 
                if not isinstance(reading.value, dict) 
                else list(reading.value.values())[0]
            )
            
            if not isinstance(measured_value, (int, float)):
                raise ValueError(f"Invalid measured value: {measured_value}")
            
            # Add calibration point to utility service
            self.calibration_service.add_calibration_point(
                sensor_id=sensor_id,
                measured_value=float(measured_value),
                reference_value=float(reference_value)
            )
            
            # Persist to database (already done by CalibrationService with repository)
            
            logger.info(f"Calibrated sensor {sensor_id}: measured={measured_value}, reference={reference_value}")
            
            return {
                "success": True,
                "sensor_id": sensor_id,
                "measured_value": measured_value,
                "reference_value": reference_value,
                "calibration_type": calibration_type
            }
            
        except ValueError as ve:
            logger.error(f"Validation error calibrating sensor {sensor_id}: {ve}")
            return {"success": False, "error": str(ve), "error_type": "validation"}
        except Exception as e:
            logger.error(f"Error calibrating sensor {sensor_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e), "error_type": "runtime"}
    
    def get_sensor_health(self, sensor_id: int) -> Dict[str, Any]:
        """
        Get health status for a sensor.
        
        Calls health monitoring service directly (no UnitRuntimeManager wrapper).
        
        Args:
            sensor_id: ID of sensor to check
            
        Returns:
            dict: Health information including score, status, error_rate, etc.
        """
        try:
            # Validate input
            if not isinstance(sensor_id, int) or sensor_id <= 0:
                raise ValueError(f"Invalid sensor_id: {sensor_id}")
            
            # Verify sensor exists
            unit_id = self._get_sensor_unit_id(sensor_id)
            if not unit_id:
                return {
                    "success": False,
                    "error": f"Sensor {sensor_id} not found",
                    "error_type": "not_found"
                }
            
            # Get health from system health service
            raw_health = None
            if self.system_health_service:
                raw_health = self.system_health_service.get_sensor_health(sensor_id)

            # Fallback to last persisted snapshot when no live data is available
            if not raw_health:
                history = self.repository.get_health_history(sensor_id, limit=1)
                if history:
                    latest = history[0]
                    total_readings = int(latest.get("total_readings", 0) or 0)
                    
                    # Only use history if it has actual readings data
                    # Otherwise treat as no data (avoids false alerts from empty history rows)
                    if total_readings > 0:
                        return {
                            "success": True,
                            "sensor_id": sensor_id,
                            "health_score": float(latest.get("health_score", 0)),
                            "status": latest.get("status", "unknown"),
                            "last_reading": latest.get("recorded_at"),
                            "error_rate": float(latest.get("error_rate", 0.0) or 0.0),
                            "total_readings": total_readings,
                            "failed_readings": int(latest.get("failed_readings", 0) or 0),
                            "source": "history_cache",
                        }

                return {
                    "success": True,
                    "sensor_id": sensor_id,
                    # Use None for missing health values so callers can distinguish
                    # between genuinely bad health (0%) and no data available.
                    "health_score": None,
                    "status": "unknown",
                    "last_reading": None,
                    "error_rate": None,
                    "total_readings": 0,
                    "failed_readings": 0,
                    "message": f"No health data available for sensor {sensor_id}",
                    "source": "empty",
                }

            # Normalize health payload (dict or dataclass)
            if isinstance(raw_health, dict):
                health_dict = raw_health
            else:
                health_dict = {
                    "status": getattr(raw_health, "status", None),
                    "health_score": getattr(raw_health, "health_score", None),
                    "last_reading": getattr(raw_health, "last_reading_time", None),
                    "error_rate": getattr(raw_health, "error_rate", None),
                    "total_reads": getattr(raw_health, "total_reads", None),
                    "failed_reads": getattr(raw_health, "failed_reads", None),
                    "success_rate": getattr(raw_health, "success_rate", None),
                }

            status_value = health_dict.get("level") or health_dict.get("status") or "unknown"
            if hasattr(status_value, "value"):
                status_value = status_value.value

            last_reading = health_dict.get("last_reading") or health_dict.get("last_reading_time") or health_dict.get("last_check")
            if hasattr(last_reading, "isoformat"):
                last_reading = last_reading.isoformat()

            total_reads = health_dict.get("total_reads")
            if total_reads is None:
                total_reads = health_dict.get("total_readings")
            total_reads = int(total_reads or 0)

            failed_reads = health_dict.get("failed_reads")
            if failed_reads is None:
                failed_reads = health_dict.get("failed_readings")
            failed_reads = int(failed_reads or 0)

            success_reads = health_dict.get("successful_reads", None)
            success_rate = health_dict.get("success_rate")
            if success_rate is None and success_reads is not None and total_reads:
                success_rate = (float(success_reads) / float(total_reads)) * 100.0

            health_score = health_dict.get("health_score", success_rate)
            # Convert fractional scores (0-1) to percentage when applicable
            if isinstance(health_score, (int, float)) and 0 < health_score <= 1:
                health_score = health_score * 100.0
            health_score = float(health_score or 0.0)
            health_score = max(0.0, min(health_score, 100.0))

            error_rate = health_dict.get("error_rate")
            if error_rate is None and total_reads:
                if success_reads is not None:
                    error_rate = max(0.0, 1.0 - (float(success_reads) / float(total_reads)))
                else:
                    error_rate = float(failed_reads) / float(total_reads)
            error_rate = float(error_rate or 0.0)
            error_rate = max(0.0, min(error_rate, 1.0))

            # Build health data response
            health_data = {
                "success": True,
                "sensor_id": sensor_id,
                "health_score": health_score,
                "status": str(status_value),
                "last_reading": last_reading,
                "error_rate": error_rate,
                "total_readings": total_reads,
                "failed_readings": failed_reads,
                "source": "live",
            }
            
            # Persist health snapshot to database
            try:
                health_score_int = int(round(health_score))
                health_score_int = max(0, min(100, health_score_int))  # Clamp to 0-100
                
                total_for_snapshot = total_reads
                failed_for_snapshot = failed_reads or (int(total_reads * error_rate) if total_reads > 0 else 0)
                
                self.repository.save_health_snapshot(
                    sensor_id=sensor_id,
                    health_score=health_score_int,
                    status=health_data['status'],
                    error_rate=error_rate,
                    total_readings=total_for_snapshot,
                    failed_readings=failed_for_snapshot
                )
            except Exception as db_error:
                logger.warning(f"Failed to persist health snapshot: {db_error}")
                # Don't fail the whole operation if DB save fails
            
            logger.debug(f"Retrieved health for sensor {sensor_id}: {health_data['status']}")
            return health_data
            
        except ValueError as ve:
            logger.error(f"Validation error getting health for sensor {sensor_id}: {ve}")
            return {"success": False, "error": str(ve), "error_type": "validation"}
        except Exception as e:
            logger.error(f"Error getting health for sensor {sensor_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e), "error_type": "runtime"}
    
    def check_sensor_anomalies(self, sensor_id: int) -> Dict[str, Any]:
        """
        Check if a sensor's recent readings contain anomalies.
        
        Calls anomaly detection service directly (no UnitRuntimeManager wrapper).
        
        Args:
            sensor_id: ID of sensor to check
            
        Returns:
            dict: Anomaly detection results
        """
        try:
            # Validate input
            if not isinstance(sensor_id, int) or sensor_id <= 0:
                raise ValueError(f"Invalid sensor_id: {sensor_id}")
            
            # Verify sensor exists
            unit_id = self._get_sensor_unit_id(sensor_id)
            if not unit_id:
                return {
                    "success": False,
                    "error": f"Sensor {sensor_id} not found",
                    "error_type": "not_found"
                }
            
            # Read current value from sensor service
            if not self.sensor_service:
                return {
                    "success": False,
                    "error": "Sensor service not available",
                    "error_type": "service_unavailable"
                }
            
            reading = self.sensor_service.read_sensor(sensor_id)
            if not reading:
                return {
                    "success": False,
                    "error": f"Failed to read sensor {sensor_id}",
                    "error_type": "read_error"
                }
            
            value = (
                reading.value 
                if not isinstance(reading.value, dict) 
                else list(reading.value.values())[0]
            )
            
            if not isinstance(value, (int, float)):
                raise ValueError(f"Invalid sensor value: {value}")
            
            # Check for anomalies using utility service
            is_anomaly = self.anomaly_service.detect_anomaly(sensor_id, float(value))
            stats = self.anomaly_service.get_statistics(sensor_id) or {}
            
            # If anomaly detected, log to database and create alert
            if is_anomaly:
                try:
                    mean = float(stats.get('mean', 0.0))
                    std_dev = float(stats.get('std_dev', 0.0))
                    
                    if std_dev > 0.0:
                        z_score = abs((value - mean) / std_dev)
                        
                        self.repository.log_anomaly(
                            sensor_id=sensor_id,
                            value=float(value),
                            mean_value=mean,
                            std_deviation=std_dev,
                            z_score=z_score
                        )
                        
                        # Create alert for sensor anomaly
                        if self.alert_service:
                            try:
                                sensor_info = self.repository.find_sensor_config_by_id(sensor_id)
                                sensor_name = sensor_info.get('name', f'Sensor {sensor_id}') if sensor_info else f'Sensor {sensor_id}'
                                
                                # Determine severity based on z-score
                                if z_score > 5.0:
                                    severity = 'critical'
                                elif z_score > 4.0:
                                    severity = 'warning'
                                else:
                                    severity = 'info'
                                
                                try:
                                    logger.info("Creating alert for sensor anomaly: sensor_id=%s, z_score=%.2f", sensor_id, z_score)
                                    alert_id = self.alert_service.create_alert(
                                        alert_type=self.alert_service.SENSOR_ANOMALY,
                                        severity=severity,
                                        title=f"Sensor Anomaly Detected: {sensor_name}",
                                        message=f"Sensor reading ({value:.2f}) deviates significantly from expected range (mean: {mean:.2f}, z-score: {z_score:.2f})",
                                        source_type='sensor',
                                        source_id=sensor_id,
                                        unit_id=unit_id,
                                        metadata={'z_score': z_score, 'value': value, 'mean': mean, 'std_dev': std_dev}
                                    )
                                    logger.info("AlertService.create_alert returned id=%s for sensor %s", alert_id, sensor_id)
                                except Exception as alert_error:
                                    logger.warning(f"Failed to create alert for sensor anomaly: {alert_error}")
                            except Exception as alert_error:
                                logger.warning(f"Failed to prepare alert for sensor anomaly: {alert_error}")
                    else:
                        logger.warning(
                            "Insufficient statistics to compute z-score for sensor %s: std_dev=%s, stats=%s",
                            sensor_id,
                            std_dev,
                            stats,
                        )
                except Exception as log_error:
                    logger.warning(f"Failed to log anomaly for sensor {sensor_id}: {log_error}")

            logger.debug(f"Checked anomalies for sensor {sensor_id}: anomaly={is_anomaly}")
            result = {
                "success": True,
                "sensor_id": sensor_id,
                "is_anomaly": bool(is_anomaly),
                "current_value": float(value),
                "mean": float(stats.get('mean', 0.0)),
                "std_dev": float(stats.get('std_dev', 0.0)),
                "min": float(stats.get('min', 0.0)),
                "max": float(stats.get('max', 0.0)),
                "count": int(stats.get('count', 0)),
                "threshold": float(getattr(self.anomaly_service, 'threshold', 3.0))
            }
            return result
            
        except ValueError as ve:
            logger.error(f"Validation error checking anomalies for sensor {sensor_id}: {ve}")
            return {"success": False, "error": str(ve), "error_type": "validation"}
        except Exception as e:
            logger.error(f"Error checking anomalies for sensor {sensor_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e), "error_type": "runtime"}
    
    def get_sensor_statistics(self, sensor_id: int) -> Dict[str, Any]:
        """
        Get statistical analysis of sensor readings.
        
        Calls anomaly service directly for statistics (no UnitRuntimeManager wrapper).
        
        Args:
            sensor_id: ID of sensor to analyze
            
        Returns:
            dict: Statistical metrics (mean, std_dev, min, max, etc.)
        """
        try:
            # Validate input
            if not isinstance(sensor_id, int) or sensor_id <= 0:
                raise ValueError(f"Invalid sensor_id: {sensor_id}")
            
            # Verify sensor exists
            unit_id = self._get_sensor_unit_id(sensor_id)
            if not unit_id:
                return {
                    "success": False,
                    "error": f"Sensor {sensor_id} not found",
                    "error_type": "not_found"
                }
            
            # Get statistics from utility service
            stats = self.anomaly_service.get_statistics(sensor_id)
            
            if not stats:
                return {
                    "success": False,
                    "error": f"No statistics available for sensor {sensor_id}",
                    "error_type": "no_data"
                }
            
            result = {
                "success": True,
                "sensor_id": sensor_id,
                **stats
            }
            
            logger.debug(f"Retrieved statistics for sensor {sensor_id}")
            return result
            
        except ValueError as ve:
            logger.error(f"Validation error getting statistics for sensor {sensor_id}: {ve}")
            return {"success": False, "error": str(ve), "error_type": "validation"}
        except Exception as e:
            logger.error(f"Error getting statistics for sensor {sensor_id}: {e}", exc_info=True)
            return {"success": False, "error": str(e), "error_type": "runtime"}
    
    def get_sensor_calibration_history(
        self,
        sensor_id: int,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get calibration history for a sensor.
        
        Calls repository directly (no UnitRuntimeManager wrapper).
        
        Args:
            sensor_id: ID of sensor
            limit: Maximum number of records to return
            
        Returns:
            list: Calibration history records
        """
        try:
            # Validate inputs
            if not isinstance(sensor_id, int) or sensor_id <= 0:
                logger.warning(f"Invalid sensor_id: {sensor_id}, returning empty history")
                return []
            
            if not isinstance(limit, int) or limit <= 0:
                logger.warning(f"Invalid limit: {limit}, using default 20")
                limit = 20
            
            # Verify sensor exists
            unit_id = self._get_sensor_unit_id(sensor_id)
            if not unit_id:
                logger.warning(f"Sensor {sensor_id} not found, returning empty history")
                return []
            
            # Get history from repository
            history = self.repository.get_calibrations(sensor_id, limit)
            
            if not isinstance(history, list):
                logger.warning(f"Repository returned non-list: {type(history)}")
                return []
            
            logger.debug(f"Retrieved {len(history)} calibration records for sensor {sensor_id}")
            return history
            
        except Exception as e:
            logger.error(f"Error getting calibration history for sensor {sensor_id}: {e}", exc_info=True)
            return []
    
    def get_sensor_health_history(
        self,
        sensor_id: int,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get health history for a sensor.
        
        Calls repository directly (no UnitRuntimeManager wrapper).
        
        Args:
            sensor_id: ID of sensor
            limit: Maximum number of records to return
            
        Returns:
            list: Health history records
        """
        try:
            # Validate inputs
            if not isinstance(sensor_id, int) or sensor_id <= 0:
                logger.warning(f"Invalid sensor_id: {sensor_id}, returning empty history")
                return []
            
            if not isinstance(limit, int) or limit <= 0:
                logger.warning(f"Invalid limit: {limit}, using default 100")
                limit = 100
            
            # Verify sensor exists
            unit_id = self._get_sensor_unit_id(sensor_id)
            if not unit_id:
                logger.warning(f"Sensor {sensor_id} not found, returning empty history")
                return []
            
            # Get history from repository
            history = self.repository.get_health_history(sensor_id, limit)
            
            if not isinstance(history, list):
                logger.warning(f"Repository returned non-list: {type(history)}")
                return []
            
            logger.debug(f"Retrieved {len(history)} health records for sensor {sensor_id}")
            return history
            
        except Exception as e:
            logger.error(f"Error getting health history for sensor {sensor_id}: {e}", exc_info=True)
            return []
            return []
    
    def get_sensor_anomaly_history(
        self,
        sensor_id: int,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get anomaly history for a sensor.
        
        Args:
            sensor_id: ID of sensor
            limit: Maximum number of records to return
            
        Returns:
            list: Anomaly history records
        """
        try:
            # Validate inputs
            if not isinstance(sensor_id, int) or sensor_id <= 0:
                raise ValueError("Invalid sensor_id")
            if not isinstance(limit, int) or limit <= 0:
                raise ValueError("Invalid limit")
            
            # Verify sensor exists
            sensor = self.repository.get_sensor_by_id(sensor_id)
            if not sensor:
                logger.warning(f"Sensor {sensor_id} not found")
                return []
            
            # Call repository directly for historical data (no utility service needed)
            history = self.repository.get_anomaly_history(sensor_id, limit)
            logger.debug(f"Retrieved {len(history)} anomaly records for sensor {sensor_id}")
            return history
            
        except ValueError as ve:
            logger.warning(f"Validation error in get_sensor_anomaly_history: {ve}")
            return []
        except Exception as e:
            logger.error(f"Error getting anomaly history for sensor {sensor_id}: {e}", exc_info=True)
            return []
    
    # ==================== Actuator Health Operations ====================
    
    def save_actuator_health(
        self,
        actuator_id: int,
        health_score: int,
        status: str,
        total_operations: int = 0,
        failed_operations: int = 0,
        average_response_time: float = 0.0
    ) -> Optional[int]:
        """
        Save actuator health monitoring snapshot.
        
        Args:
            actuator_id: Actuator identifier
            health_score: Health score (0-100)
            status: Health status ('healthy', 'degraded', 'critical', 'offline')
            total_operations: Total operations count
            failed_operations: Failed operations count
            average_response_time: Average response time in milliseconds
            
        Returns:
            History ID or None
        """
        try:
            history_id = self.repository.save_actuator_health_snapshot(
                actuator_id=actuator_id,
                health_score=health_score,
                status=status,
                total_operations=total_operations,
                failed_operations=failed_operations,
                average_response_time=average_response_time
            )
            logger.info(f"Saved health snapshot for actuator {actuator_id}: {status} ({health_score}/100)")
            return history_id
        except Exception as e:
            logger.error(f"Error saving actuator health for {actuator_id}: {e}", exc_info=True)
            return None
    
    def get_actuator_health_history(self, actuator_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get health history for an actuator.
        
        Args:
            actuator_id: Actuator identifier
            limit: Maximum number of records to return
            
        Returns:
            List of health history records
        """
        try:
            history = self.repository.get_actuator_health_history(actuator_id, limit)
            logger.debug(f"Retrieved {len(history)} health records for actuator {actuator_id}")
            return history
        except Exception as e:
            logger.error(f"Error getting health history for actuator {actuator_id}: {e}", exc_info=True)
            return []
    
    # ==================== Actuator Anomaly Detection ====================
    
    def log_actuator_anomaly(
        self,
        actuator_id: int,
        anomaly_type: str,
        severity: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Log detected actuator anomaly.
        
        Args:
            actuator_id: Actuator identifier
            anomaly_type: Type of anomaly ('stuck_on', 'stuck_off', 'power_spike', 'no_response', etc.)
            severity: Severity level ('low', 'medium', 'high', 'critical')
            details: Additional details as dictionary
            
        Returns:
            Anomaly ID or None
        """
        try:
            anomaly_id = self.repository.log_actuator_anomaly(
                actuator_id=actuator_id,
                anomaly_type=anomaly_type,
                severity=severity,
                details=details
            )
            logger.warning(f"Logged actuator anomaly {anomaly_id}: {anomaly_type} (severity: {severity})")
            
            # Create alert for actuator anomaly
            if self.alert_service:
                try:
                    actuator_info = self.repository.find_actuator_config_by_id(actuator_id)
                    actuator_name = actuator_info.get('name', f'Actuator {actuator_id}') if actuator_info else f'Actuator {actuator_id}'
                    unit_id = actuator_info.get('unit_id') if actuator_info else None
                    
                    # Map severity to alert severity
                    alert_severity = 'critical' if severity in ['critical', 'high'] else 'warning' if severity == 'medium' else 'info'
                    
                    self.alert_service.create_alert(
                        alert_type=self.alert_service.ACTUATOR_FAILURE,
                        severity=alert_severity,
                        title=f"Actuator Anomaly: {actuator_name}",
                        message=f"Actuator {actuator_name} experienced {anomaly_type} anomaly",
                        source_type='actuator',
                        source_id=actuator_id,
                        unit_id=unit_id,
                        metadata={'anomaly_type': anomaly_type, 'severity': severity, 'details': details}
                    )
                    logger.info(f"Created alert for actuator {actuator_id} anomaly: {anomaly_type}")
                except Exception as alert_error:
                    logger.warning(f"Failed to create alert for actuator anomaly: {alert_error}")
            
            # Publish event for real-time alerts (typed payload)
            self.event_bus.publish(
                DeviceEvent.ACTUATOR_ANOMALY_DETECTED,
                ActuatorAnomalyPayload(
                    actuator_id=actuator_id,
                    anomaly_id=anomaly_id,
                    anomaly_type=anomaly_type,
                    severity=severity,
                    details=details,
                ),
            )
            
            return anomaly_id
        except Exception as e:
            logger.error(f"Error logging actuator anomaly for {actuator_id}: {e}", exc_info=True)
            return None
    
    def get_actuator_anomalies(self, actuator_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get anomaly history for an actuator.
        
        Args:
            actuator_id: Actuator identifier
            limit: Maximum number of records to return
            
        Returns:
            List of anomaly records
        """
        try:
            anomalies = self.repository.get_actuator_anomalies(actuator_id, limit)
            logger.debug(f"Retrieved {len(anomalies)} anomalies for actuator {actuator_id}")
            return anomalies
        except Exception as e:
            logger.error(f"Error getting anomalies for actuator {actuator_id}: {e}", exc_info=True)
            return []
    
    def resolve_actuator_anomaly(self, anomaly_id: int) -> bool:
        """
        Mark an actuator anomaly as resolved.
        
        Args:
            anomaly_id: Anomaly identifier
            
        Returns:
            True if resolved successfully
        """
        try:
            success = self.repository.resolve_actuator_anomaly(anomaly_id)
            if success:
                logger.info(f"Resolved actuator anomaly {anomaly_id}")
                self.event_bus.publish(
                    DeviceEvent.ACTUATOR_ANOMALY_RESOLVED,
                    ActuatorAnomalyResolvedPayload(anomaly_id=anomaly_id),
                )
            return success
        except Exception as e:
            logger.error(f"Error resolving actuator anomaly {anomaly_id}: {e}", exc_info=True)
            return False
    
    # ==================== Actuator Calibration ====================
    
    def save_actuator_calibration(
        self,
        actuator_id: int,
        calibration_type: str,
        calibration_data: Dict[str, Any]
    ) -> Optional[int]:
        """
        Save actuator calibration profile.
        
        Args:
            actuator_id: Actuator identifier
            calibration_type: Type of calibration ('power_profile', 'pwm_curve', 'timing')
            calibration_data: Calibration parameters as dictionary
            
        Returns:
            Calibration ID or None
        """
        try:
            calibration_id = self.repository.save_actuator_calibration(
                actuator_id=actuator_id,
                calibration_type=calibration_type,
                calibration_data=calibration_data
            )
            logger.info(f"Saved {calibration_type} calibration for actuator {actuator_id}")

            # Publish event for actuator manager to update (typed payload)
            self.event_bus.publish(
                DeviceEvent.ACTUATOR_CALIBRATION_UPDATED,
                ActuatorCalibrationPayload(
                    actuator_id=actuator_id,
                    calibration_type=calibration_type,
                    calibration_data=calibration_data,
                ),
            )
            
            return calibration_id
        except Exception as e:
            logger.error(f"Error saving calibration for actuator {actuator_id}: {e}", exc_info=True)
            return None
    
    def get_actuator_calibrations(self, actuator_id: int) -> List[Dict[str, Any]]:
        """
        Get all calibrations for an actuator.
        
        Args:
            actuator_id: Actuator identifier
            
        Returns:
            List of calibration records
        """
        try:
            calibrations = self.repository.get_actuator_calibrations(actuator_id)
            logger.debug(f"Retrieved {len(calibrations)} calibrations for actuator {actuator_id}")
            return calibrations
        except Exception as e:
            logger.error(f"Error getting calibrations for actuator {actuator_id}: {e}", exc_info=True)
            return []
    
    # ==================== Actuator Power Readings ====================
    
    def save_actuator_power_reading(
        self,
        actuator_id: int,
        power_watts: float,
        voltage: Optional[float] = None,
        current: Optional[float] = None,
        energy_kwh: Optional[float] = None,
        power_factor: Optional[float] = None,
        frequency: Optional[float] = None,
        temperature: Optional[float] = None,
        is_estimated: bool = False
    ) -> Optional[int]:
        """
        Save actuator power reading to database.
        
        Args:
            actuator_id: Actuator identifier
            power_watts: Power consumption in watts
            voltage: Voltage in volts
            current: Current in amps
            energy_kwh: Cumulative energy in kWh
            power_factor: Power factor (0-1)
            frequency: Frequency in Hz
            temperature: Device temperature in Celsius
            is_estimated: Whether power is estimated vs measured
            
        Returns:
            Reading ID or None
        """
        try:
            reading_id = self.repository.save_actuator_power_reading(
                actuator_id=actuator_id,
                power_watts=power_watts,
                voltage=voltage,
                current=current,
                energy_kwh=energy_kwh,
                power_factor=power_factor,
                frequency=frequency,
                temperature=temperature,
                is_estimated=is_estimated
            )
            logger.debug(f"Saved power reading for actuator {actuator_id}: {power_watts}W")
            return reading_id
        except Exception as e:
            logger.error(f"Error saving power reading for actuator {actuator_id}: {e}", exc_info=True)
            return None
    
    def get_actuator_power_readings(
        self,
        actuator_id: int,
        limit: int = 1000,
        hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get power readings for an actuator.
        
        Args:
            actuator_id: Actuator identifier
            limit: Maximum number of records to return
            hours: Optional time window in hours
            
        Returns:
            List of power reading records
        """
        try:
            readings = self.repository.get_actuator_power_readings(actuator_id, limit, hours)
            logger.debug(f"Retrieved {len(readings)} power readings for actuator {actuator_id}")
            return readings
        except Exception as e:
            logger.error(f"Error getting power readings for actuator {actuator_id}: {e}", exc_info=True)
            return []
    
    # ==================== Health Monitoring & Alerting ====================
    #TODO: implement periodic checks for device health and create alerts accordingly in the scheduler
    # I need to implement the actuator health checks as well in the future.
    def check_all_devices_health_and_alert(self, unit_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Check health of all devices and create alerts for critical issues.
        
        This method should be called periodically (e.g., every 5-10 minutes) to monitor
        device health and automatically create alerts for:
        - Sensors with critical health status
        - Sensors that haven't reported in a while (offline)
        - Actuators with high error rates
        
        Args:
            unit_id: Optional unit ID to check specific unit, or None for all units
            
        Returns:
            dict: Summary of health checks and alerts created
        """
        if not self.alert_service:
            logger.warning("Alert service not available, skipping health checks")
            return {"success": False, "error": "Alert service not configured"}
        
        try:
            alerts_created = 0
            sensors_checked = 0
            critical_sensors = []
            offline_sensors = []
            
            # Get all sensors (optionally filtered by unit)
            if unit_id:
                sensors = self.repository.get_sensors_by_unit(unit_id)
            else:
                sensors = self.repository.list_sensors()
            
            for sensor in sensors:
                sensor_id = sensor.get('sensor_id')
                sensor_name = sensor.get('name', f'Sensor {sensor_id}')
                sensor_unit_id = sensor.get('unit_id')
                
                sensors_checked += 1
                
                # Check sensor health
                health = self.get_sensor_health(sensor_id)
                
                if not health.get('success'):
                    continue
                
                # health_score may be None when no data; preserve None to indicate "unknown"
                health_score = health.get('health_score', None)
                status = health.get('status', 'unknown')
                error_rate = health.get('error_rate', None)
                last_reading = health.get('last_reading')
                
                # Check if sensor is offline (no reading in last N minutes)
                is_offline = False
                if last_reading:
                    try:
                        from datetime import datetime, timedelta, timezone

                        # Parse ISO timestamps robustly: prefer dateutil if available
                        last_read_time = None
                        if isinstance(last_reading, str):
                            try:
                                from dateutil import parser as dateutil_parser
                                last_read_time = dateutil_parser.isoparse(last_reading)
                            except Exception:
                                try:
                                    last_read_time = datetime.fromisoformat(last_reading.replace('Z', '+00:00'))
                                except Exception as iso_parse_error:
                                    logger.debug(f"Could not parse last_reading time with fallback: {iso_parse_error}")
                                    last_read_time = None
                        elif hasattr(last_reading, 'tzinfo') or hasattr(last_reading, 'year'):
                            # Already a datetime-like object
                            last_read_time = last_reading

                        if last_read_time is not None:
                            # Normalize to timezone-aware UTC for safe comparisons
                            if last_read_time.tzinfo is None:
                                last_read_time = last_read_time.replace(tzinfo=timezone.utc)
                            now = datetime.now(tz=timezone.utc)
                            time_since_reading = now - last_read_time.astimezone(timezone.utc)
                            if time_since_reading > timedelta(minutes=self.offline_threshold_minutes):
                                is_offline = True
                                offline_sensors.append(sensor_name)
                    except Exception as parse_error:
                        logger.debug(f"Could not parse last_reading time: {parse_error}")
                
                # Create alert for offline sensor
                if is_offline:
                    try:
                        logger.info("Creating offline alert for sensor %s (last_reading=%s)", sensor_id, last_reading)
                        alert_id = self.alert_service.create_alert(
                            alert_type=self.alert_service.DEVICE_OFFLINE,
                            severity='warning',
                            title=f"Sensor Offline: {sensor_name}",
                            message=(
                                f"Sensor {sensor_name} has not reported data in over "
                                f"{self.offline_threshold_minutes} minutes"
                            ),
                            source_type='sensor',
                            source_id=sensor_id,
                            unit_id=sensor_unit_id,
                            metadata={'last_reading': last_reading, 'status': status}
                        )
                        alerts_created += 1
                        logger.info("AlertService.create_alert returned id=%s for offline sensor %s", alert_id, sensor_id)
                    except Exception as alert_error:
                        logger.warning(f"Failed to create offline alert: {alert_error}")
                
                # Create alert for critical health status. Only consider numeric
                # health/error values; if missing, treat as "unknown" and avoid
                # creating a critical alert purely because of absent data.
                # Skip sensors with no data or only default/empty values (source: "empty" or "unknown")
                source = health.get('source', '')
                total_readings = health.get('total_readings', 0)
                
                # Only alert if we have actual sensor data (not just empty/default values)
                # Sensors with 0 total_readings haven't sent data yet and shouldn't trigger alerts
                if source not in ['empty', 'unknown'] and total_readings > 0:
                    if (
                        (health_score is not None and health_score < 50)
                        or (error_rate is not None and error_rate > 0.5)
                        or status in ['critical', 'unhealthy']
                    ):
                        critical_sensors.append(sensor_name)
                        
                        # Determine severity
                        if (
                            (health_score is not None and health_score < 25)
                            or (error_rate is not None and error_rate > 0.75)
                            or status == 'critical'
                        ):
                            severity = 'critical'
                        else:
                            severity = 'warning'
                        
                        try:
                            logger.info("Creating health alert for sensor %s (score=%s)", sensor_id, health_score)
                            alert_id = self.alert_service.create_alert(
                                alert_type=self.alert_service.DEVICE_MALFUNCTION,
                                severity=severity,
                                title=f"Sensor Health Critical: {sensor_name}",
                                # Format health/error strings safely when values may be None
                                message=(
                                    f"Sensor {sensor_name} health score is "
                                    f"{(f'{health_score:.0f}%' if health_score is not None else 'N/A')} "
                                    f"with {(f'{error_rate*100:.1f}%' if error_rate is not None else 'N/A')} error rate"
                                ),
                                source_type='sensor',
                                source_id=sensor_id,
                                unit_id=sensor_unit_id,
                                metadata={'health_score': health_score, 'error_rate': error_rate, 'status': status}
                            )
                            alerts_created += 1
                            logger.info("AlertService.create_alert returned id=%s for health alert sensor %s", alert_id, sensor_id)
                        except Exception as alert_error:
                            logger.warning(f"Failed to create health alert: {alert_error}")
            
            return {
                "success": True,
                "sensors_checked": sensors_checked,
                "alerts_created": alerts_created,
                "critical_sensors": critical_sensors,
                "offline_sensors": offline_sensors
            }
            
        except Exception as e:
            logger.error(f"Error checking device health: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ==================== Health Score Interpretation ====================

    def interpret_health_score(self, score: float) -> str:
        """
        Convert health score (0-100) to human-readable status string.
        
        Score ranges:
        - 80-100: healthy - System operating normally
        - 60-79: good - Minor issues, monitoring recommended
        - 40-59: fair - Degraded performance, action recommended
        - 0-39: poor - Critical issues, immediate action required
        
        Args:
            score: Health score from 0-100
            
        Returns:
            Status string: 'healthy', 'good', 'fair', or 'poor'
        """
        if score >= 80:
            return 'healthy'
        elif score >= 60:
            return 'good'
        elif score >= 40:
            return 'fair'
        else:
            return 'poor'

    def evaluate_sensor_status(
        self,
        value: Optional[float],
        sensor_type: str,
        thresholds: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Evaluate sensor reading against thresholds to determine status.
        
        Uses default thresholds if none provided. Custom thresholds should come
        from unit settings for production use.
        
        Default thresholds by sensor type:
        - temperature: 18-28°C
        - humidity: 40-80%
        - soil_moisture: 30-70%
        - lux: 200-1500 lux
        - co2: 300-800 ppm
        - energy_usage: 0-5W (special case for energy monitoring)
        
        Args:
            value: Sensor reading value (None returns 'Unknown')
            sensor_type: Type of sensor (temperature, humidity, etc.)
            thresholds: Optional custom thresholds dict with 'min' and 'max' keys
            
        Returns:
            Status string: 'Low', 'Normal', 'High', or 'Unknown'
        """
        if value is None:
            return 'Unknown'
        
        # Use custom thresholds if provided, otherwise use defaults
        if thresholds:
            threshold = thresholds
        else:
            # Default thresholds (should eventually come from database/unit settings)
            default_thresholds = {
                'temperature': {'min': 18.0, 'max': 28.0},
                'humidity': {'min': 40.0, 'max': 80.0},
                'soil_moisture': {'min': 30.0, 'max': 70.0},
                'lux': {'min': 200.0, 'max': 1500.0},
                'co2': {'min': 300.0, 'max': 800.0},
                'energy_usage': {'min': 0.0, 'max': 5.0}
            }
            threshold = default_thresholds.get(sensor_type, {'min': 0.0, 'max': 100.0})
        
        min_val = threshold.get('min', float('-inf'))
        max_val = threshold.get('max', float('inf'))
        
        if value < min_val:
            return 'Low'
        elif value > max_val:
            return 'High'
        else:
            return 'Normal'

    def calculate_system_health(
        self,
        vpd_status: Optional[str] = None,
        plant_health_avg: Optional[float] = None,
        critical_alerts: int = 0,
        warning_alerts: int = 0,
        devices_active: int = 0,
        devices_total: int = 0
    ) -> Dict[str, Any]:
        """
        Calculate overall system health score from multiple factors.
        
        NOTE: This method computes a composite "system status" that includes both
        device health AND environmental/plant metrics. While this provides a useful
        overview score for dashboards, it mixes concerns. Consider refactoring to:
        - Move this to a dedicated SystemStatusService or AnalyticsService
        - Separate device health (sensors/actuators) from environmental health (VPD, plants)
        - Create distinct metrics: device_health, environmental_health, plant_health
        
        Health factors and weights:
        - VPD status: 100 (optimal), 70 (sub-optimal), 40 (poor) [Environmental metric]
        - Plant health average: Uses actual average score (0-100) [Cultivation metric]
        - Alert impact: 100 (none), 70 (warnings), 40 (critical) [System metric]
        - Device availability: (active/total) * 100 [Device metric]
        
        The final score is the average of all contributing factors.
        
        Args:
            vpd_status: VPD status ('optimal', 'low', 'high', etc.)
            plant_health_avg: Average plant health score (0-100)
            critical_alerts: Number of critical alerts
            warning_alerts: Number of warning alerts
            devices_active: Number of active devices
            devices_total: Total number of devices
            
        Returns:
            Dictionary with:
                - health_score: Overall system health (0-100)
                - status: Human-readable status
                - factors: Breakdown of individual factor scores
        """
        health_factors = []
        factor_details = {}
        
        # Factor 1: VPD status (environmental conditions)
        # NOTE: Environmental metric - consider moving to separate environmental_health calculation
        if vpd_status:
            if vpd_status == 'optimal':
                vpd_score = 100.0
            elif vpd_status in ['low', 'high', 'seedling', 'vegetative', 'flowering']:
                # Sub-optimal but acceptable zones
                vpd_score = 70.0
            else:
                # Too low or too high
                vpd_score = 40.0
            
            health_factors.append(vpd_score)
            factor_details['vpd'] = vpd_score
        
        # Factor 2: Plant health average
        # NOTE: Cultivation metric - consider moving to separate plant_health calculation
        if plant_health_avg is not None and plant_health_avg >= 0:
            health_factors.append(float(plant_health_avg))
            factor_details['plants'] = float(plant_health_avg)
        
        # Factor 3: Alert impact
        if critical_alerts > 0:
            alert_score = 40.0
        elif warning_alerts > 0:
            alert_score = 70.0
        else:
            alert_score = 100.0
        
        health_factors.append(alert_score)
        factor_details['alerts'] = alert_score
        
        # Factor 4: Device availability
        if devices_total > 0:
            device_score = (devices_active / devices_total) * 100.0
            health_factors.append(device_score)
            factor_details['devices'] = round(device_score, 1)
        
        # Calculate overall health score
        if health_factors:
            avg_score = sum(health_factors) / len(health_factors)
            health_score = round(avg_score, 1)
        else:
            # No data available
            health_score = 0.0
        
        # Interpret score
        status = self.interpret_health_score(health_score)
        
        return {
            'health_score': health_score,
            'status': status,
            'factors': factor_details
        }
