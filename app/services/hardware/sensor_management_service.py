"""
Sensor Management Service
==========================
Unified service managing ALL sensors across ALL growth units.

This service provides a complete interface for sensor operations, combining
hardware management with application-layer features. Uses memory-first
architecture with TTL caching to minimize database queries.

Responsibilities:
- Sensor lifecycle (register, unregister)
- Runtime storage and indexing (by ID, type, protocol)
- Reading sensor data with anomaly detection
- Calibration management
- Sensor polling coordination
- Memory caching of sensor metadata
- Health monitoring integration
- Zigbee2MQTT auto-discovery

Architecture:
    SensorManagementService (singleton)
      ├─ SensorFactory (creates sensor entities)
      ├─ SensorPollingService (polling coordinator)
      ├─ CalibrationService (sensor calibration)
      ├─ AnomalyDetectionService (anomaly detection)
      ├─ SystemHealthService (health monitoring)
      └─ TTLCache (sensor metadata cache)

Memory-First:
    Sensor configurations cached in memory (TTL 60s) to reduce DB queries.
    Perfect for Raspberry Pi environments with limited I/O bandwidth.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from typing import TYPE_CHECKING, Any

from app.domain.sensors import (
    Protocol,
    SensorEntity,
    SensorReading,
    SensorType,
)
from app.domain.sensors.sensor_config import SensorConfig
from app.enums.events import DeviceEvent
from app.hardware.sensors.factory import SensorFactory
from app.hardware.sensors.processors.base_processor import IDataProcessor
from app.schemas.events import SensorReadingPayload
from app.services.hardware.sensor_polling_service import SensorPollingService
from app.services.utilities.anomaly_detection_service import AnomalyDetectionService
from app.services.utilities.calibration_service import CalibrationService
from app.utils.cache import CacheRegistry, TTLCache
from app.utils.emitters import EmitterService
from app.utils.event_bus import EventBus

if TYPE_CHECKING:
    from app.services.application.zigbee_management_service import ZigbeeManagementService
    from app.services.utilities.system_health_service import SystemHealthService
    from infrastructure.database.repositories.devices import DeviceRepository

logger = logging.getLogger(__name__)


class SensorManagementService:
    """
    Unified service for global sensor management.

    This service manages ALL sensors across ALL units, providing:
    - Runtime sensor storage and indexing
    - Memory-first sensor metadata caching
    - Unified sensor operations (read, calibrate, etc.)
    - Automatic polling coordination
    - Anomaly detection
    - Health monitoring integration
    - Zigbee2MQTT auto-discovery

    Example:
        # Direct sensor reading (no unit_id needed - sensor knows its unit)
        reading = sensor_service.read_sensor(sensor_id=1)

        # List sensors for a specific unit
        unit_sensors = sensor_service.list_sensors(unit_id=1)

        # Register new sensor in runtime
        sensor_service.register_sensor(sensor_id=5, **config)
    """

    def __init__(
        self,
        repository: DeviceRepository,
        emitter: EmitterService,
        processor: IDataProcessor,
        mqtt_client: Any | None = None,
        event_bus: EventBus | None = None,
        system_health_service: SystemHealthService | None = None,
        zigbee_service: "ZigbeeManagementService" | None = None,
        cache_ttl_seconds: int = 60,
        cache_maxsize: int = 256,
    ):
        """
        Initialize sensor management service.

        Args:
            repository: Device repository for database operations
            emitter: EmitterService for WebSocket emission
            processor: Data processor pipeline
            mqtt_client: Optional MQTT client for wireless sensors
            event_bus: Event bus for sensor events
            system_health_service: Health monitoring service
            zigbee_service: Zigbee management service for discovery
            cache_ttl_seconds: TTL for sensor metadata cache (default 60s)
            cache_maxsize: Maximum cached sensors (default 256)
        """
        self.repository = repository
        self.emitter = emitter
        self.processor = processor
        self.event_bus = event_bus or EventBus()
        self.mqtt_client = mqtt_client

        # ==================== Runtime Sensor Storage ====================
        # Primary storage: sensor_id -> SensorEntity
        self._sensors: dict[int, SensorEntity] = {}
        # Index by sensor type for fast lookups
        self._sensors_by_type: dict[SensorType, list[SensorEntity]] = {}
        # Index for GPIO sensors (require polling)
        self._gpio_sensors: dict[int, SensorEntity] = {}
        # Index for wireless sensors (MQTT/Zigbee)
        self._wireless_sensors: dict[int, SensorEntity] = {}
        # Thread safety for sensor dict operations
        self._sensors_lock = threading.RLock()

        # ==================== Sub-services ====================
        # Factory for creating sensor entities
        self.factory = SensorFactory(mqtt_client=mqtt_client)
        # Calibration service
        self.calibration_service = CalibrationService()
        # Anomaly detection service
        self.anomaly_service = AnomalyDetectionService()
        # Health monitoring (injected, shared across services)
        self.health_service = system_health_service
        # Zigbee discovery service
        self._zigbee_service = zigbee_service

        # Register Zigbee discovery callback
        if self._zigbee_service:
            self._zigbee_service.register_discovery_callback(self._on_sensor_discovered)

        # Single global polling service (provides emitter and processor)
        self.polling_service = SensorPollingService(
            sensor_manager=self,  # Pass self instead of SensorManager
            emitter=emitter,
            processor=processor,
        )

        # Memory cache for sensor metadata (reduces DB queries)
        self._sensor_cache = TTLCache(enabled=True, ttl_seconds=cache_ttl_seconds, maxsize=cache_maxsize)
        # Register cache for monitoring
        with contextlib.suppress(ValueError):
            CacheRegistry.get_instance().register("sensor_management.sensors", self._sensor_cache)

        # Track which sensors are registered in runtime (for compatibility)
        self._registered_sensors: set[int] = set()

        logger.info(
            f"SensorManagementService initialized (cache_ttl={cache_ttl_seconds}s, cache_maxsize={cache_maxsize})"
        )

    # ==================== Core Sensor Operations ====================

    def create_sensor(
        self,
        *,
        unit_id: int,
        name: str,
        sensor_type: str,
        protocol: str,
        model: str,
        config: dict[str, Any] | None = None,
        register_runtime: bool = True,
    ) -> int:
        """
        Create a sensor in the database and optionally register it in runtime.

        Returns the created sensor_id.
        """
        sensor_id = self.repository.create_sensor(
            unit_id=unit_id,
            name=name,
            sensor_type=sensor_type,
            protocol=protocol,
            model=model,
            config_data=config or {},
        )
        if sensor_id is None:
            raise ValueError("Failed to create sensor")

        if register_runtime:
            self.register_sensor(
                sensor_id=int(sensor_id),
                name=name,
                sensor_type=sensor_type,
                protocol=protocol,
                unit_id=unit_id,
                model=model,
                config=config or {},
            )

        # Notify listeners (e.g. MQTTSensorService) to refresh any friendly-name caches.
        with contextlib.suppress(Exception):
            self.event_bus.publish(DeviceEvent.SENSOR_CREATED, {"sensor_id": int(sensor_id), "unit_id": unit_id})

        return int(sensor_id)

    def delete_sensor(self, sensor_id: int, *, remove_from_zigbee: bool = False) -> None:
        """
        Delete a sensor from runtime and the database.

        Args:
            sensor_id: Sensor identifier
            remove_from_zigbee: If True and sensor is Zigbee/Zigbee2MQTT, also remove
                               from the Zigbee network via ZigbeeManagementService.
        """
        # Get sensor info before deletion for Zigbee removal
        sensor_info = None
        if remove_from_zigbee:
            sensor_info = self.get_sensor(sensor_id)

        try:
            self.unregister_sensor(sensor_id)
        finally:
            self.repository.delete_sensor(sensor_id)
            self._sensor_cache.invalidate(f"sensor_{sensor_id}")

            # Remove from Zigbee network if requested
            if remove_from_zigbee and sensor_info and self._zigbee_service:
                protocol = sensor_info.get("protocol", "")
                if protocol.lower() in ("zigbee", "zigbee2mqtt"):
                    friendly_name = sensor_info.get("config", {}).get("friendly_name")
                    if friendly_name:
                        try:
                            self._zigbee_service.remove_device(friendly_name=friendly_name)
                            logger.info("Removed sensor %s from Zigbee network: %s", sensor_id, friendly_name)
                        except Exception as e:
                            logger.warning("Failed to remove sensor %s from Zigbee network: %s", sensor_id, e)

            with contextlib.suppress(Exception):
                self.event_bus.publish(DeviceEvent.SENSOR_DELETED, {"sensor_id": int(sensor_id)})

    def read_sensor(self, sensor_id: int) -> SensorReading | None:
        """
        Read data from a sensor with anomaly detection.

        Args:
            sensor_id: Sensor identifier

        Returns:
            SensorReading object or None if sensor not found/failed

        Raises:
            ValueError: If sensor_id is invalid
        """
        if sensor_id <= 0:
            raise ValueError(f"Invalid sensor_id: {sensor_id}")

        try:
            # Check if sensor is registered in runtime
            with self._sensors_lock:
                sensor = self._sensors.get(sensor_id)

            if not sensor:
                logger.warning("Sensor %s not registered in runtime, attempting auto-registration", sensor_id)
                # Attempt auto-registration
                if not self._auto_register_sensor(sensor_id):
                    logger.error("Failed to auto-register sensor %s", sensor_id)
                    return None

                with self._sensors_lock:
                    sensor = self._sensors.get(sensor_id)

                if not sensor:
                    return None

            # Read using sensor's processing pipeline
            reading = sensor.read()

            # Check for anomalies (supports multi-value readings)
            anomalies = []
            expected_range = None
            if sensor.config.min_threshold is not None and sensor.config.max_threshold is not None:
                expected_range = (float(sensor.config.min_threshold), float(sensor.config.max_threshold))

            for field_name, value in (reading.data or {}).items():
                if not isinstance(value, int | float):
                    continue
                anomaly = self.anomaly_service.check_reading(
                    sensor_id=sensor_id,
                    value=float(value),
                    field_name=str(field_name),
                    expected_range=expected_range,
                )
                if anomaly:
                    anomalies.append(anomaly)

            # Publish reading event with multi-value support
            self.event_bus.publish(
                DeviceEvent.SENSOR_READING,
                SensorReadingPayload(
                    sensor_id=sensor_id,
                    readings=reading.data,
                    timestamp=reading.timestamp.isoformat() if reading.timestamp else None,
                ),
            )

            # Log anomalies
            for anomaly in anomalies:
                logger.warning(
                    f"Anomaly detected in sensor {sensor_id}: {anomaly.anomaly_type.value} - {anomaly.description}"
                )

            logger.debug("Sensor %s reading: %s", sensor_id, reading.data)
            return reading

        except Exception as e:
            logger.error("Error reading sensor %s: %s", sensor_id, e, exc_info=True)

            # Emit error event
            self.event_bus.publish("sensor_error", {"sensor_id": sensor_id, "error": str(e)})

            return None

    def read_all_sensors(self) -> dict[int, SensorReading]:
        """
        Read all registered sensors.

        Returns:
            Dict of sensor_id -> SensorReading
        """
        readings = {}

        with self._sensors_lock:
            sensor_ids = list(self._sensors.keys())

        for sensor_id in sensor_ids:
            reading = self.read_sensor(sensor_id)
            if reading:
                readings[sensor_id] = reading

        return readings

    def register_sensor(
        self,
        *,
        sensor_id: int,
        name: str,
        sensor_type: str,
        protocol: str,
        unit_id: int,
        model: str = "Unknown",
        config: dict[str, Any] | None = None,
    ) -> bool:
        """
        Register sensor in runtime (memory-first).

        This creates the sensor entity and makes it available for reading.
        Sensor metadata is cached for fast access.

        Args:
            sensor_id: Sensor identifier
            name: Sensor name
            sensor_type: Type of sensor (e.g., 'TEMPERATURE', 'HUMIDITY')
            protocol: Communication protocol ('GPIO', 'MQTT', 'ZIGBEE')
            unit_id: Growth unit this sensor belongs to
            model: Hardware model identifier
            config: Protocol-specific configuration

        Returns:
            True if registration successful

        Example:
            sensor_service.register_sensor(
                sensor_id=1,
                name='Temp Sensor',
                sensor_type='TEMPERATURE',
                protocol='GPIO',
                unit_id=1,
                gpio_pin=17
            )
        """
        try:
            # Validate inputs
            if sensor_id <= 0:
                raise ValueError(f"Invalid sensor_id: {sensor_id}")
            if unit_id <= 0:
                raise ValueError(f"Invalid unit_id: {unit_id}")

            # Check if already registered
            with self._sensors_lock:
                if sensor_id in self._sensors:
                    logger.warning("Sensor %s already registered", sensor_id)
                    return True

            protocol_obj = Protocol(protocol)
            sensor_type_obj = SensorType(sensor_type)

            sensor_config_dict = config or {}
            sensor_config_fields = {
                key: value for key, value in sensor_config_dict.items() if key in SensorConfig.__dataclass_fields__
            }
            sensor_config = SensorConfig(**sensor_config_fields)

            # Extract adapter params (exclude metadata fields)
            adapter_params = {
                k: v
                for k, v in sensor_config_dict.items()
                if k not in {"sensor_id", "name", "sensor_type", "protocol", "unit_id", "model", "config"}
            }

            # Create sensor using factory
            sensor = self.factory.create_sensor(
                sensor_id,
                name,
                sensor_type_obj,
                protocol_obj,
                sensor_config,
                unit_id=unit_id,
                model=model,
                adapter_params=adapter_params,
            )

            # Store sensor in runtime
            with self._sensors_lock:
                self._sensors[sensor_id] = sensor

                # Index by type
                if sensor_type_obj not in self._sensors_by_type:
                    self._sensors_by_type[sensor_type_obj] = []
                self._sensors_by_type[sensor_type_obj].append(sensor)

                # Index by protocol
                if protocol_obj == Protocol.GPIO:
                    self._gpio_sensors[sensor_id] = sensor
                elif protocol_obj in (Protocol.MQTT, Protocol.ZIGBEE, Protocol.ZIGBEE2MQTT):
                    self._wireless_sensors[sensor_id] = sensor

            # Track registration
            self._registered_sensors.add(sensor_id)

            # Register with health monitoring
            if self.health_service:
                self.health_service.register_sensor(sensor)

            # Cache sensor metadata (includes unit_id)
            sensor_metadata = {
                "sensor_id": sensor_id,
                "name": name,
                "sensor_type": sensor_type,
                "protocol": protocol,
                "unit_id": unit_id,
                "model": model,
                "config": sensor_config_dict,
            }
            self._sensor_cache.set(f"sensor_{sensor_id}", sensor_metadata)

            # Emit event
            self.event_bus.publish(
                "sensor_registered", {"sensor_id": sensor_id, "name": name, "type": sensor_type, "protocol": protocol}
            )

            logger.info(
                "Registered sensor %s (type=%s, protocol=%s, unit=%s)", sensor_id, sensor_type, protocol, unit_id
            )

            return True

        except Exception as e:
            logger.error("Error registering sensor %s: %s", sensor_id, e, exc_info=True)
            return False

    def register_sensor_config(self, sensor_config: dict[str, Any]) -> bool:
        """
        Register a sensor from a repository config dictionary.

        Expected keys: sensor_id, name, sensor_type, protocol, unit_id, model, config
        """
        return self.register_sensor(
            sensor_id=int(sensor_config["sensor_id"]),
            name=str(sensor_config.get("name") or f"Sensor {sensor_config.get('sensor_id')}"),
            sensor_type=str(sensor_config.get("sensor_type") or ""),
            protocol=str(sensor_config.get("protocol") or ""),
            unit_id=int(sensor_config.get("unit_id") or 0),
            model=str(sensor_config.get("model") or "Unknown"),
            config=dict(sensor_config.get("config") or {}),
        )

    def unregister_sensor(self, sensor_id: int) -> bool:
        """
        Remove sensor from runtime.

        Args:
            sensor_id: Sensor identifier

        Returns:
            True if unregistration successful
        """
        try:
            # If this sensor was never registered, treat as no-op success
            if sensor_id not in self._registered_sensors:
                self._sensor_cache.invalidate(f"sensor_{sensor_id}")
                logger.info("Sensor %s not registered in runtime; skipping unregister", sensor_id)
                return True

            with self._sensors_lock:
                sensor = self._sensors.get(sensor_id)
                if not sensor:
                    self._registered_sensors.discard(sensor_id)
                    return True

                # Cleanup adapter resources (unsubscribe MQTT topics, release GPIO, etc.)
                if sensor._adapter is not None:
                    try:
                        sensor._adapter.cleanup()
                        logger.debug("Cleaned up adapter for sensor %s", sensor_id)
                    except Exception as e:
                        logger.warning("Adapter cleanup failed for sensor %s: %s", sensor_id, e)

                # Remove from type index
                if sensor.sensor_type in self._sensors_by_type:
                    with contextlib.suppress(ValueError):
                        self._sensors_by_type[sensor.sensor_type].remove(sensor)

                # Remove from protocol index
                if sensor_id in self._gpio_sensors:
                    del self._gpio_sensors[sensor_id]
                if sensor_id in self._wireless_sensors:
                    del self._wireless_sensors[sensor_id]

                # Remove from main storage
                del self._sensors[sensor_id]

            # Remove from tracking
            self._registered_sensors.discard(sensor_id)

            # Remove from health monitoring
            if self.health_service:
                self.health_service.unregister_sensor(sensor_id)

            # Invalidate cache
            self._sensor_cache.invalidate(f"sensor_{sensor_id}")

            # Emit event
            self.event_bus.publish("sensor_unregistered", {"sensor_id": sensor_id})

            logger.info("Unregistered sensor %s", sensor_id)
            return True

        except Exception as e:
            logger.error("Error unregistering sensor %s: %s", sensor_id, e, exc_info=True)
            return False

    # ==================== Sensor Polling ====================

    def start_polling(self, sensor_ids: list[int] | None = None, interval_seconds: int = 60) -> bool:
        """
        Start polling for sensors.

        Args:
            sensor_ids: List of sensor IDs to poll (None = all registered)
            interval_seconds: Polling interval in seconds

        Returns:
            True if polling started successfully
        """
        try:
            # SensorPollingService polls all sensors registered in SensorManager.
            # sensor_ids and interval_seconds are currently not applied.
            _ = sensor_ids
            _ = interval_seconds
            started = self.polling_service.start_polling()

            sensor_count = len(sensor_ids) if sensor_ids else len(self._registered_sensors)
            if started:
                logger.info("Started sensor polling for %s sensors (interval=%ss)", sensor_count, interval_seconds)
            else:
                logger.info(
                    "Sensor polling not started (no GPIO/I2C/ADC/SPI sensors registered). "
                    f"registered_sensors={sensor_count}"
                )

            return started

        except Exception as e:
            logger.error("Error starting sensor polling: %s", e, exc_info=True)
            return False

    def stop_polling(self) -> bool:
        """
        Stop all sensor polling.

        Returns:
            True if polling stopped successfully
        """
        try:
            self.polling_service.stop_polling()
            logger.info("Stopped sensor polling")
            return True
        except Exception as e:
            logger.error("Error stopping sensor polling: %s", e, exc_info=True)
            return False

    # ==================== Queries (Memory-First) ====================

    def get_sensor(self, sensor_id: int) -> dict[str, Any] | None:
        """
        Get sensor metadata (memory-first with DB fallback).

        Args:
            sensor_id: Sensor identifier

        Returns:
            Sensor metadata dictionary or None
        """
        try:
            # Try cache first
            cache_key = f"sensor_{sensor_id}"
            cached = self._sensor_cache.get(cache_key)

            if cached:
                logger.debug("Sensor %s metadata from cache", sensor_id)
                return cached

            # Fallback to database
            sensor = self.repository.find_sensor_config_by_id(sensor_id)

            if sensor:
                # Cache for next time
                self._sensor_cache.set(cache_key, sensor)

                logger.debug("Sensor %s metadata from database (cached)", sensor_id)
                return sensor

            logger.warning("Sensor %s not found", sensor_id)
            return None

        except Exception as e:
            logger.error("Error getting sensor %s: %s", sensor_id, e, exc_info=True)
            return None

    def list_sensors(self, unit_id: int | None = None) -> list[dict[str, Any]]:
        """
        List all sensors, optionally filtered by unit.

        Args:
            unit_id: Optional unit ID to filter sensors

        Returns:
            List of sensor metadata dictionaries
        """
        try:
            return self.repository.list_sensor_configs(unit_id=unit_id)

        except Exception as e:
            logger.error("Error listing sensors: %s", e, exc_info=True)
            return []

    def get_registered_sensor_ids(self) -> list[int]:
        """
        Get list of all registered sensor IDs.

        Returns:
            List of sensor IDs currently registered in runtime
        """
        return list(self._registered_sensors)

    # ==================== Health & Diagnostics ====================

    def get_sensor_entity(self, sensor_id: int) -> SensorEntity | None:
        """
        Get sensor entity by ID.

        Args:
            sensor_id: Sensor ID

        Returns:
            SensorEntity or None
        """
        with self._sensors_lock:
            return self._sensors.get(sensor_id)

    def get_sensors_by_type(self, sensor_type: SensorType) -> list[SensorEntity]:
        """
        Get all sensors of a specific type.

        Args:
            sensor_type: Sensor type

        Returns:
            List of SensorEntity
        """
        with self._sensors_lock:
            return list(self._sensors_by_type.get(sensor_type, []))

    def get_all_sensors(self) -> list[SensorEntity]:
        """
        Get all registered sensor entities.

        Returns:
            List of SensorEntity
        """
        with self._sensors_lock:
            return list(self._sensors.values())

    def get_sensor_by_friendly_name(self, friendly_name: str) -> SensorEntity | None:
        """
        Get sensor entity by Zigbee2MQTT friendly name.

        Searches through registered sensors for one matching the friendly name
        either by sensor name or by zigbee_friendly_name in config.

        Args:
            friendly_name: The Zigbee2MQTT friendly name

        Returns:
            SensorEntity if found, None otherwise
        """
        if not friendly_name:
            return None

        with self._sensors_lock:
            for sensor in self._sensors.values():
                # Check sensor name
                if sensor.name == friendly_name:
                    return sensor

                # Check zigbee_friendly_name in config
                cfg = getattr(sensor, "config", None)
                if cfg:
                    zigbee_name = getattr(cfg, "zigbee_friendly_name", None)
                    if zigbee_name == friendly_name:
                        return sensor

                    # Also check extra_config and connection_params
                    extra = getattr(cfg, "extra_config", None) or {}
                    if extra.get("friendly_name") == friendly_name:
                        return sensor

                    conn = getattr(cfg, "connection_params", None) or {}
                    mqtt_topic = conn.get("mqtt_topic", "")
                    if friendly_name in mqtt_topic:
                        return sensor

        return None

    def apply_calibration(self, sensor_id: int, calibration_data) -> bool:
        """
        Apply calibration to a sensor.

        Args:
            sensor_id: Sensor ID
            calibration_data: CalibrationData instance

        Returns:
            True if applied successfully
        """
        with self._sensors_lock:
            sensor = self._sensors.get(sensor_id)

        if not sensor:
            return False

        sensor.set_calibration(calibration_data)

        # Emit event
        self.event_bus.publish(
            "sensor_calibrated", {"sensor_id": sensor_id, "calibration_type": calibration_data.type.value}
        )

        logger.info("Applied calibration to sensor %s", sensor_id)
        return True

    def send_command(self, sensor_id: int, command: dict[str, Any]) -> bool:
        """
        Send a command to a sensor's hardware adapter.

        Only supported for sensors with adapters that have send_command capability
        (e.g., Zigbee2MQTT sensors).

        Args:
            sensor_id: Sensor ID
            command: Command dictionary to send (e.g., {"identify": True})

        Returns:
            True if command sent successfully, False otherwise
        """
        sensor = self.get_sensor_entity(sensor_id)
        if not sensor:
            logger.warning("Sensor %s not found for send_command", sensor_id)
            return False

        adapter = sensor._adapter
        if not adapter:
            logger.warning("Sensor %s has no adapter for send_command", sensor_id)
            return False

        if not hasattr(adapter, "send_command"):
            logger.warning(
                "Adapter for sensor %s (%s) does not support send_command", sensor_id, type(adapter).__name__
            )
            return False

        try:
            return adapter.send_command(command)
        except Exception as e:
            logger.error("Error sending command to sensor %s: %s", sensor_id, e)
            return False

    def send_command_by_name(self, friendly_name: str, command: dict[str, Any]) -> bool:
        """
        Send a command to a sensor by its friendly name (Zigbee2MQTT name).

        This is a convenience method for sending commands when you only have
        the device's friendly name (as used in Zigbee2MQTT).

        Args:
            friendly_name: The Zigbee2MQTT friendly name of the device
            command: Command dictionary to send

        Returns:
            True if command sent successfully, False otherwise
        """
        # Find sensor by name
        with self._sensors_lock:
            for sensor in self._sensors.values():
                # Check if sensor name matches or mqtt_topic contains the name
                if sensor.name == friendly_name:
                    return self.send_command(sensor.id, command)

                # Also check mqtt_topic in config (Zigbee2MQTT sensors use this)
                mqtt_topic = sensor.config.connection_params.get("mqtt_topic", "")
                if friendly_name in mqtt_topic:
                    return self.send_command(sensor.id, command)

        logger.warning("No sensor found with friendly name: %s", friendly_name)
        return False

    def identify_sensor(self, sensor_id: int, duration: int = 10) -> bool:
        """
        Trigger identification on a sensor (e.g., flash LED).

        Args:
            sensor_id: Sensor ID
            duration: Identification duration in seconds

        Returns:
            True if identify command sent successfully
        """
        sensor = self.get_sensor_entity(sensor_id)
        if not sensor or not sensor._adapter:
            logger.warning("Sensor %s not found or has no adapter", sensor_id)
            return False

        if hasattr(sensor._adapter, "identify"):
            try:
                return sensor._adapter.identify(duration)
            except Exception as e:
                logger.error("Error identifying sensor %s: %s", sensor_id, e)
                return False

        # Fallback: try send_command with identify
        if hasattr(sensor._adapter, "send_command"):
            return sensor._adapter.send_command({"identify": duration})

        logger.warning("Sensor %s does not support identification", sensor_id)
        return False

    def get_sensor_device_info(self, sensor_id: int) -> dict[str, Any] | None:
        """
        Get device information for a sensor.

        Args:
            sensor_id: Sensor ID

        Returns:
            Device info dictionary or None
        """
        sensor = self.get_sensor_entity(sensor_id)
        if not sensor or not sensor._adapter:
            return None

        if hasattr(sensor._adapter, "get_device_info"):
            try:
                return sensor._adapter.get_device_info()
            except Exception as e:
                logger.error("Error getting device info for sensor %s: %s", sensor_id, e)
                return None

        # Return basic info from sensor entity
        return sensor.to_dict()

    def get_sensor_state(self, sensor_id: int) -> dict[str, Any] | None:
        """
        Get current state for a sensor.

        Args:
            sensor_id: Sensor ID

        Returns:
            State dictionary or None
        """
        sensor = self.get_sensor_entity(sensor_id)
        if not sensor:
            return None

        if sensor._adapter and hasattr(sensor._adapter, "get_state"):
            try:
                return sensor._adapter.get_state()
            except Exception as e:
                logger.error("Error getting state for sensor %s: %s", sensor_id, e)

        # Fallback to last reading
        if sensor._last_reading:
            return {
                "sensor_id": sensor_id,
                "last_reading": sensor._last_reading.to_dict(),
                "last_read_time": sensor._last_read_time.isoformat() if sensor._last_read_time else None,
                "health": sensor._health_status.to_dict() if sensor._health_status else None,
            }

        return None

    def rename_sensor_device(self, sensor_id: int, new_name: str) -> bool:
        """
        Rename sensor device on its network (e.g., Zigbee2MQTT).

        This renames the device on the network level. You should also
        update the sensor name in the database separately.

        Args:
            sensor_id: Sensor ID
            new_name: New device name

        Returns:
            True if rename command sent successfully
        """
        sensor = self.get_sensor_entity(sensor_id)
        if not sensor or not sensor._adapter:
            logger.warning("Sensor %s not found or has no adapter", sensor_id)
            return False

        if hasattr(sensor._adapter, "rename"):
            try:
                return sensor._adapter.rename(new_name)
            except Exception as e:
                logger.error("Error renaming sensor %s: %s", sensor_id, e)
                return False

        logger.warning("Sensor %s does not support rename", sensor_id)
        return False

    def remove_sensor_from_network(self, sensor_id: int) -> bool:
        """
        Remove sensor device from its network (e.g., Zigbee network).

        This removes the device from the network level. The device will
        need to be re-paired to rejoin the network.

        Args:
            sensor_id: Sensor ID

        Returns:
            True if remove command sent successfully
        """
        sensor = self.get_sensor_entity(sensor_id)
        if not sensor or not sensor._adapter:
            logger.warning("Sensor %s not found or has no adapter", sensor_id)
            return False

        if hasattr(sensor._adapter, "remove_from_network"):
            try:
                return sensor._adapter.remove_from_network()
            except Exception as e:
                logger.error("Error removing sensor %s from network: %s", sensor_id, e)
                return False

        logger.warning("Sensor %s does not support network removal", sensor_id)
        return False

    def get_health_report(self):
        """
        Get system-wide health report.

        Returns:
            SystemHealthReport or None
        """
        if self.health_service:
            return self.health_service.generate_health_report()
        return None

    def get_sensor_health(self, sensor_id: int) -> dict | None:
        """
        Get health status for specific sensor.

        Args:
            sensor_id: Sensor ID

        Returns:
            Health status dict or None
        """
        if self.health_service:
            return self.health_service.get_sensor_health(sensor_id)
        return None

    def get_sensor_status(self, sensor_id: int) -> dict[str, Any]:
        """
        Get sensor status and diagnostics.

        Args:
            sensor_id: Sensor identifier

        Returns:
            Status dictionary with registration, health, last reading, etc.
        """
        try:
            status = {
                "sensor_id": sensor_id,
                "registered": sensor_id in self._registered_sensors,
                "metadata_cached": self._sensor_cache.get(f"sensor_{sensor_id}") is not None,
            }

            # Get metadata
            metadata = self.get_sensor(sensor_id)
            if metadata:
                status["unit_id"] = metadata.get("unit_id")
                status["sensor_type"] = metadata.get("sensor_type")
                status["protocol"] = metadata.get("protocol")

            # Get last reading (in-memory)
            sensor_entity = self.get_sensor_entity(sensor_id)
            last_reading = sensor_entity.get_last_reading() if sensor_entity else None
            if last_reading:
                status["last_reading"] = {
                    "readings": last_reading.data,
                    "timestamp": last_reading.timestamp.isoformat(),
                }

            # Get polling health info
            health = self.polling_service.get_health_status(sensor_id)
            if health:
                status["health"] = health

            return status

        except Exception as e:
            logger.error("Error getting sensor %s status: %s", sensor_id, e, exc_info=True)
            return {"sensor_id": sensor_id, "error": str(e)}

    # ==================== Internal Helpers ====================

    def _auto_register_sensor(self, sensor_id: int) -> bool:
        """
        Automatically register sensor from database.

        Args:
            sensor_id: Sensor identifier

        Returns:
            True if auto-registration successful
        """
        try:
            # Load from database
            sensor = self.repository.find_sensor_config_by_id(sensor_id)

            if not sensor:
                logger.error("Sensor %s not found in database", sensor_id)
                return False

            # Register in runtime
            return self.register_sensor_config(sensor)

        except Exception as e:
            logger.error("Error auto-registering sensor %s: %s", sensor_id, e, exc_info=True)
            return False

    def _on_sensor_discovered(self, device_info):
        """
        Callback for auto-discovered sensors (Zigbee2MQTT).

        Args:
            device_info: Discovered device information
        """
        try:
            # Support both dict payloads and DiscoveredDevice dataclass instances
            if hasattr(device_info, "to_dict"):
                data = device_info.to_dict()
            elif isinstance(device_info, dict):
                data = device_info
            else:
                # Fallback to attribute access if no to_dict available
                data = {
                    "friendly_name": getattr(device_info, "friendly_name", "unknown"),
                    "type": getattr(device_info, "device_type", getattr(device_info, "type", "unknown")),
                }

            friendly = data.get("friendly_name", "unknown")
            dev_type = data.get("type", data.get("device_type", "unknown"))

            logger.info("Auto-discovered sensor: %s (%s)", friendly, dev_type)
        except Exception as exc:
            logger.error("Failed to handle sensor discovery payload: %s", exc, exc_info=True)
            return

        # Emit event for user notification
        self.event_bus.publish("sensor_discovered", data)

    # ==================== Operational Health ====================

    def get_polling_health(self) -> dict[str, Any]:
        """
        Get polling service operational health metrics.

        Returns:
            Dictionary with polling health data including:
            - mqtt_last_seen: Timestamp of last MQTT sensor messages
            - sensor_health: Health status per sensor
            - backoff_seconds_remaining: Backoff timers for failed sensors
            - pending_coalesced: Pending MQTT messages
        """
        if not hasattr(self.polling_service, "get_health_snapshot"):
            return {}
        return self.polling_service.get_health_snapshot()

    # ==================== Lifecycle ====================

    def shutdown(self) -> None:
        """
        Shutdown sensor management service.

        Stops polling, clears cache, releases resources.
        """
        try:
            logger.info("Shutting down SensorManagementService...")

            # Stop polling
            self.stop_polling()

            # Clear cache
            self._sensor_cache.clear()

            # Clear registrations
            self._registered_sensors.clear()

            # Clear sensor storage
            with self._sensors_lock:
                self._sensors.clear()
                self._sensors_by_type.clear()
                self._gpio_sensors.clear()
                self._wireless_sensors.clear()

            logger.info("SensorManagementService shutdown complete")

        except Exception as e:
            logger.error("Error during SensorManagementService shutdown: %s", e, exc_info=True)


__all__ = ["SensorManagementService"]
