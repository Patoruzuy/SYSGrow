"""
Actuator Management Service
============================
Unified service managing ALL actuators across ALL growth units.

This service provides a complete interface for actuator operations including:
- Hardware layer (runtime state, factory, adapters)
- Service layer (caching, DB operations, health monitoring)

Architecture (Unified):
    ActuatorManagementService (singleton)
      ├─ ActuatorFactory (creates hardware adapters)
      ├─ SchedulingService (schedule management)
      ├─ SafetyService (interlocks)
      ├─ StateTrackingService (state persistence)
      ├─ EnergyMonitoringService (power tracking)
      └─ TTLCache (actuator metadata cache)

Memory-First:
    Actuator configurations cached in memory (TTL 60s) to reduce DB queries.
    Runtime state stored in-memory with RLock for thread safety.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from app.domain.actuators import (
    ActuatorConfig,
    ActuatorEntity,
    ActuatorReading,
    ActuatorState,
    ActuatorType,
    ControlMode,
    Protocol,
)
from app.domain.schedules import Schedule as DeviceSchedule
from app.enums.events import DeviceEvent
from app.hardware.actuators.factory import ActuatorFactory
from app.hardware.compat.enums import (
    app_to_infra_actuator_type,
    app_to_infra_protocol,
    infra_to_app_actuator_type,
    infra_to_app_protocol,
)
from app.schemas.events import (
    ActuatorLifecyclePayload,
    ActuatorStatePayload,
    DeviceCommandPayload,
)
from app.services.hardware.energy_monitoring import (
    DEFAULT_POWER_PROFILES,
    EnergyMonitoringService,
    EnergyReading,
)
from app.services.hardware.safety_service import SafetyService
from app.services.hardware.scheduling_service import SchedulingService
from app.services.hardware.state_tracking_service import StateTrackingService
from app.utils.cache import CacheRegistry, TTLCache
from app.utils.concurrency import synchronized
from app.utils.event_bus import EventBus
from app.utils.time import iso_now

if TYPE_CHECKING:
    from app.services.application.device_health_service import DeviceHealthService
    from app.services.application.zigbee_management_service import (
        DiscoveredDevice,
        ZigbeeManagementService,
    )
    from infrastructure.database.repositories.analytics import AnalyticsRepository
    from infrastructure.database.repositories.devices import DeviceRepository

logger = logging.getLogger(__name__)


class ActuatorManagementService:
    """
    Unified service for global actuator management.

    This service manages ALL actuators across ALL units, providing:
    - Runtime actuator storage with thread-safe access
    - Hardware control via protocol-specific adapters
    - Memory-first actuator metadata caching
    - Automatic state tracking and persistence
    - Health monitoring integration
    - Energy/power consumption tracking
    - Zigbee2MQTT device discovery
    - Safety interlocks and scheduling

    Bidirectional Dependencies:
        - device_health_service: Set by ContainerBuilder for actuator health monitoring

    Example:
        # Direct actuator control (no unit_id needed - actuator knows its unit)
        actuator_service.set_actuator_state(actuator_id=1, state=True)

        # List actuators for a specific unit
        unit_actuators = actuator_service.list_actuators(unit_id=1)

        # Register new actuator in runtime
        actuator_service.register_actuator(actuator_id=5, **config)
    """

    def __init__(
        self,
        repository: DeviceRepository,
        analytics_repository: AnalyticsRepository | None = None,
        mqtt_client: Any | None = None,
        event_bus: EventBus | None = None,
        device_health_service: DeviceHealthService | None = None,
        zigbee_service: "ZigbeeManagementService" | None = None,
        schedule_repository: Any | None = None,
        cache_ttl_seconds: int = 60,
        cache_maxsize: int = 256,
        enable_energy_monitoring: bool = True,
        electricity_rate_kwh: float = 0.12,
    ):
        """
        Initialize actuator management service.

        Args:
            repository: Device repository for database operations
            analytics_repository: Analytics repository for energy monitoring persistence
            mqtt_client: Optional MQTT client for wireless actuators
            event_bus: Event bus for actuator events
            device_health_service: Health monitoring service
            zigbee_service: Shared ZigbeeManagementService for discovery
            schedule_repository: ScheduleRepository for schedule persistence
            cache_ttl_seconds: TTL for actuator metadata cache (default 60s)
            cache_maxsize: Maximum cached actuators (default 256)
            enable_energy_monitoring: Enable power consumption tracking
            electricity_rate_kwh: Cost per kWh for energy cost calculations
        """
        # Database layer
        self.repository = repository
        self.analytics_repository = analytics_repository
        self.event_bus = event_bus or EventBus()
        self.device_health_service = device_health_service
        self.schedule_repository = schedule_repository
        self.mqtt_client = mqtt_client

        # ========== HARDWARE LAYER (inlined from ActuatorManager) ==========

        # Factory for creating actuators
        self.factory = ActuatorFactory(mqtt_client, self.event_bus)

        # Runtime actuator storage (Dict for O(1) lookup)
        self._actuators: dict[int, ActuatorEntity] = {}
        self._actuators_by_type: dict[ActuatorType, list[ActuatorEntity]] = {}

        # Thread safety
        self._lock = threading.RLock()

        # Hardware services
        self.scheduling_service = SchedulingService(repository=schedule_repository)
        self.safety_service = SafetyService(self)
        self.state_tracking_service = StateTrackingService(self)

        # Health tracking state
        self._operation_counts: dict[int, int] = {}
        self._error_counts: dict[int, int] = {}
        self._last_health_check: dict[int, datetime] = {}

        # Energy monitoring
        self.energy_monitoring: EnergyMonitoringService | None = None
        if enable_energy_monitoring:
            self.energy_monitoring = EnergyMonitoringService(
                electricity_rate_kwh=electricity_rate_kwh,
                analytics_repo=analytics_repository,
            )
            self._register_default_power_profiles()
            logger.info("Energy monitoring enabled (persistence: %s)", analytics_repository is not None)

        # Zigbee2MQTT discovery
        self.zigbee2mqtt_discovery: "ZigbeeManagementService" | None = None
        if zigbee_service:
            self.zigbee2mqtt_discovery = zigbee_service
            self.zigbee2mqtt_discovery.register_discovery_callback(self._on_device_discovered)
            self.zigbee2mqtt_discovery.request_device_list()
            logger.info("Zigbee2MQTT discovery enabled (shared service)")

        # Discovery callbacks
        self.discovery_callbacks: list[Callable] = []

        # ========== SERVICE LAYER ==========

        # Memory cache for actuator metadata (reduces DB queries)
        self._actuator_cache = TTLCache(enabled=True, ttl_seconds=cache_ttl_seconds, maxsize=cache_maxsize)
        # Register cache for monitoring
        with contextlib.suppress(ValueError):
            CacheRegistry.get_instance().register("actuator_management.actuators", self._actuator_cache)

        # Track which actuators are registered in runtime
        self._registered_actuators: set[int] = set()

        logger.info(
            f"ActuatorManagementService initialized (cache_ttl={cache_ttl_seconds}s, cache_maxsize={cache_maxsize})"
        )

    # ==================== Core Actuator Operations ====================

    def create_actuator(
        self,
        *,
        unit_id: int,
        name: str,
        actuator_type: ActuatorType,
        protocol: Protocol,
        model: str = "Generic",
        config: dict[str, Any] | None = None,
        register_runtime: bool = True,
    ) -> int:
        """
        Create an actuator in the database and optionally register it in runtime.

        Returns the created actuator_id.
        """
        actuator_id = self.repository.create_actuator(
            unit_id=unit_id,
            name=name,
            actuator_type=actuator_type,
            protocol=protocol,
            model=model,
            config_data=config or {},
        )
        if actuator_id is None:
            raise ValueError("Failed to create actuator")

        if register_runtime:
            self.register_actuator(
                actuator_id=actuator_id,
                name=name,
                actuator_type=actuator_type,
                protocol=protocol,
                unit_id=unit_id,
                model=model,
                config=config or {},
            )

        return int(actuator_id)

    def delete_actuator(self, actuator_id: int, *, remove_from_zigbee: bool = False) -> None:
        """
        Delete an actuator from runtime and the database.

        Args:
            actuator_id: Actuator identifier
            remove_from_zigbee: If True and actuator is Zigbee/Zigbee2MQTT, also remove
                               from the Zigbee network via ZigbeeManagementService.
        """
        # Get actuator info before deletion for Zigbee removal
        actuator_info = None
        if remove_from_zigbee:
            actuator_info = self.get_actuator(actuator_id)

        try:
            self.unregister_actuator(actuator_id)
        finally:
            self.repository.delete_actuator(actuator_id)
            self._actuator_cache.invalidate(f"actuator_{actuator_id}")

            # Remove from Zigbee network if requested
            if remove_from_zigbee and actuator_info and self.zigbee2mqtt_discovery:
                protocol = actuator_info.get("protocol", "")
                if protocol.lower() in ("zigbee", "zigbee2mqtt"):
                    friendly_name = actuator_info.get("config", {}).get("friendly_name")
                    if not friendly_name:
                        # Try zigbee_id fallback
                        friendly_name = actuator_info.get("config", {}).get("zigbee_id")
                    if friendly_name:
                        try:
                            self.zigbee2mqtt_discovery.remove_device(friendly_name=friendly_name)
                            logger.info("Removed actuator %s from Zigbee network: %s", actuator_id, friendly_name)
                        except Exception as e:
                            logger.warning("Failed to remove actuator %s from Zigbee network: %s", actuator_id, e)

    @synchronized
    def set_actuator_state(
        self, actuator_id: int, state: bool, user_id: int | None = None, reason: str = "manual"
    ) -> bool:
        """
        Set actuator state (ON/OFF).

        Args:
            actuator_id: Actuator identifier
            state: Desired state (True=ON, False=OFF)
            user_id: Optional user who triggered the change
            reason: Reason for state change (manual, schedule, automation, etc.)

        Returns:
            True if state change successful

        Raises:
            ValueError: If actuator_id is invalid
        """
        if actuator_id <= 0:
            raise ValueError(f"Invalid actuator_id: {actuator_id}")

        try:
            # Check if actuator is registered in runtime
            if actuator_id not in self._registered_actuators:
                logger.warning("Actuator %s not registered in runtime, attempting auto-registration", actuator_id)
                if not self._auto_register_actuator(actuator_id):
                    logger.error("Failed to auto-register actuator %s", actuator_id)
                    return False

            if state:
                result = self.turn_on(actuator_id)
                return result.state == ActuatorState.ON

            result = self.turn_off(actuator_id)
            return result.state == ActuatorState.OFF

        except Exception as e:
            logger.error("Error setting actuator %s state: %s", actuator_id, e, exc_info=True)
            return False

    @synchronized
    def get_actuator_state(self, actuator_id: int) -> bool | None:
        """
        Get current actuator state.

        Args:
            actuator_id: Actuator identifier

        Returns:
            Current state (True=ON, False=OFF) or None if unavailable
        """
        try:
            if actuator_id not in self._registered_actuators:
                logger.warning("Actuator %s not registered", actuator_id)
                return None

            reading = self.get_state(actuator_id)
            if reading.state == ActuatorState.ON:
                return True
            if reading.state == ActuatorState.OFF:
                return False
            return None

        except Exception as e:
            logger.error("Error getting actuator %s state: %s", actuator_id, e, exc_info=True)
            return None

    @synchronized
    def register_actuator(
        self,
        *,
        actuator_id: int,
        name: str,
        actuator_type: ActuatorType,
        protocol: Protocol,
        unit_id: int,
        model: str = "Generic",
        config: dict[str, Any] | None = None,
    ) -> bool:
        """
        Register actuator in runtime (memory-first).

        This creates the actuator hardware adapter and makes it
        available for control. Actuator metadata is cached for fast access.
        """
        try:
            # Validate inputs
            if actuator_id <= 0:
                raise ValueError(f"Invalid actuator_id: {actuator_id}")
            if unit_id <= 0:
                raise ValueError(f"Invalid unit_id: {unit_id}")

            raw_config = config or {}

            # Normalize enums
            if not isinstance(actuator_type, ActuatorType):
                actuator_type = app_to_infra_actuator_type(actuator_type)
            if not isinstance(protocol, Protocol):
                protocol = app_to_infra_protocol(protocol)

            # Canonical config keys expected by ActuatorFactory.
            mapped_config = {
                "gpio_pin": raw_config.get("gpio_pin") or raw_config.get("gpio"),
                "ip_address": raw_config.get("ip_address"),
                "mqtt_topic": raw_config.get("mqtt_topic"),
                "zigbee_id": raw_config.get("zigbee_id")
                or raw_config.get("ieee_address")
                or raw_config.get("zigbee_topic")
                or raw_config.get("zigbee_channel"),
                "invert_logic": raw_config.get("invert_logic", False),
                "power_watts": raw_config.get("power_watts"),
                "metadata": raw_config.get("metadata", {}),
            }
            mapped_config = {k: v for k, v in mapped_config.items() if v is not None}

            # Create actuator config
            actuator_config = ActuatorConfig(
                name=name,
                actuator_type=actuator_type,
                protocol=protocol,
                gpio_pin=mapped_config.get("gpio_pin"),
                mqtt_topic=mapped_config.get("mqtt_topic"),
                ip_address=mapped_config.get("ip_address"),
                zigbee_id=mapped_config.get("zigbee_id"),
                control_mode=ControlMode(raw_config.get("control_mode", "manual")),
                min_value=raw_config.get("min_value", 0.0),
                max_value=raw_config.get("max_value", 100.0),
                invert_logic=mapped_config.get("invert_logic", False),
                pwm_frequency=raw_config.get("pwm_frequency"),
                power_watts=mapped_config.get("power_watts"),
                metadata=mapped_config.get("metadata", {}),
            )

            # Create actuator using factory
            actuator_entity = self.factory.create_actuator(
                actuator_id=actuator_id,
                config=actuator_config,
            )

            # Store in runtime
            self._actuators[actuator_id] = actuator_entity

            # Index by type
            if actuator_type not in self._actuators_by_type:
                self._actuators_by_type[actuator_type] = []
            self._actuators_by_type[actuator_type].append(actuator_entity)

            # Load saved calibration profiles
            self._load_calibration_profiles(actuator_id, actuator_type)

            # Initialize health tracking
            self._operation_counts[actuator_id] = 0
            self._error_counts[actuator_id] = 0
            self._last_health_check[actuator_id] = datetime.now()

            # Emit registration event
            app_actuator_type = infra_to_app_actuator_type(actuator_type)
            app_protocol = infra_to_app_protocol(protocol)
            actuator_type_str = app_actuator_type.value if app_actuator_type else actuator_type.value
            protocol_str = app_protocol.value if app_protocol else protocol.value

            self.event_bus.publish(
                DeviceEvent.ACTUATOR_REGISTERED,
                ActuatorLifecyclePayload(
                    actuator_id=actuator_id,
                    name=name,
                    actuator_type=actuator_type_str,
                    protocol=protocol_str,
                    timestamp=iso_now(),
                ),
            )

            # Track in registered set
            self._registered_actuators.add(actuator_id)

            # Cache actuator metadata
            actuator_metadata = {
                "actuator_id": actuator_id,
                "name": name,
                "actuator_type": actuator_type,
                "protocol": protocol,
                "unit_id": unit_id,
                "model": model,
                "config": raw_config,
            }
            self._actuator_cache.set(f"actuator_{actuator_id}", actuator_metadata)

            logger.info("Registered actuator %s: %s (%s)", actuator_id, name, actuator_type.value)

            # Notify health service
            if self.device_health_service:
                try:
                    self.device_health_service.register_actuator(actuator_id)
                except Exception as health_error:
                    logger.warning("Health registration failed for actuator %s: %s", actuator_id, health_error)

            return True

        except Exception as e:
            logger.exception("Registration failed for actuator %s: %s", actuator_id, e)
            return False

    def register_actuator_config(self, actuator_config: dict[str, Any]) -> bool:
        """
        Register an actuator from a repository config dictionary.

        Expected keys: actuator_id, name, actuator_type, protocol, unit_id, model, config
        """
        return self.register_actuator(
            actuator_id=int(actuator_config["actuator_id"]),
            name=str(actuator_config.get("name") or f"Actuator {actuator_config.get('actuator_id')}"),
            actuator_type=str(actuator_config.get("actuator_type") or ""),
            protocol=str(actuator_config.get("protocol") or ""),
            unit_id=int(actuator_config.get("unit_id") or 0),
            model=str(actuator_config.get("model") or "Generic"),
            config=dict(actuator_config.get("config") or {}),
        )

    @synchronized
    def unregister_actuator(self, actuator_id: int) -> bool:
        """
        Remove actuator from runtime.

        Args:
            actuator_id: Actuator identifier

        Returns:
            True if unregistration successful
        """
        try:
            if actuator_id not in self._actuators:
                return False

            actuator = self._actuators[actuator_id]

            # Turn off before removing (safety)
            with contextlib.suppress(Exception):
                actuator.turn_off()

            # Cleanup adapter resources (unsubscribe MQTT topics, etc.)
            if hasattr(actuator, "adapter") and actuator.adapter is not None:
                try:
                    if hasattr(actuator.adapter, "cleanup"):
                        actuator.adapter.cleanup()
                        logger.debug("Cleaned up adapter for actuator %s", actuator_id)
                except Exception as e:
                    logger.warning("Adapter cleanup failed for actuator %s: %s", actuator_id, e)

            # Remove from storage
            del self._actuators[actuator_id]

            # Remove from type index
            if actuator.actuator_type in self._actuators_by_type:
                with contextlib.suppress(ValueError):
                    self._actuators_by_type[actuator.actuator_type].remove(actuator)

            # Remove from tracking
            self._registered_actuators.discard(actuator_id)

            # Invalidate cache
            self._actuator_cache.invalidate(f"actuator_{actuator_id}")

            # Emit event
            self.event_bus.publish(
                DeviceEvent.ACTUATOR_UNREGISTERED,
                ActuatorLifecyclePayload(
                    actuator_id=actuator_id,
                    timestamp=iso_now(),
                ),
            )

            logger.info("Unregistered actuator %s", actuator_id)

            # Notify health service
            if self.device_health_service:
                try:
                    self.device_health_service.unregister_actuator(actuator_id)
                except Exception as health_error:
                    logger.warning(
                        "Failed to unregister actuator %s from health service: %s", actuator_id, health_error
                    )

            return True

        except Exception as e:
            logger.error("Error unregistering actuator %s: %s", actuator_id, e, exc_info=True)
            return False

    # ==================== Hardware Control Methods ====================

    @synchronized
    def get_actuator_entity(self, actuator_id: int) -> ActuatorEntity | None:
        """Get actuator entity by ID (runtime storage)."""
        return self._actuators.get(actuator_id)

    @synchronized
    def get_all_actuators(self) -> list[ActuatorEntity]:
        """Get all registered actuator entities."""
        return list(self._actuators.values())

    @synchronized
    def get_actuators_by_type(self, actuator_type: ActuatorType) -> list[ActuatorEntity]:
        """Get actuators of specific type."""
        return self._actuators_by_type.get(actuator_type, [])

    @synchronized
    def turn_on(self, actuator_id: int) -> ActuatorReading:
        """
        Turn actuator ON.

        Args:
            actuator_id: ID of actuator

        Returns:
            ActuatorReading with result
        """
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            raise ValueError(f"Actuator {actuator_id} not found")

        # Safety check
        if not self.safety_service.can_turn_on(actuator_id):
            return ActuatorReading(
                actuator_id=actuator_id, state=ActuatorState.ERROR, error_message="Safety interlock active"
            )

        result = actuator.turn_on()
        self.state_tracking_service.record_state_change(actuator_id, result)
        self._track_operation(actuator_id, result)
        self._emit_state_event(actuator_id, result, "on")
        return result

    @synchronized
    def turn_off(self, actuator_id: int) -> ActuatorReading:
        """
        Turn actuator OFF.

        Args:
            actuator_id: ID of actuator

        Returns:
            ActuatorReading with result
        """
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            raise ValueError(f"Actuator {actuator_id} not found")

        result = actuator.turn_off()
        self.state_tracking_service.record_state_change(actuator_id, result)
        self._track_operation(actuator_id, result)
        self._emit_state_event(actuator_id, result, "off")
        return result

    @synchronized
    def toggle(self, actuator_id: int) -> ActuatorReading:
        """Toggle actuator state."""
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            raise ValueError(f"Actuator {actuator_id} not found")

        result = actuator.toggle()
        self.state_tracking_service.record_state_change(actuator_id, result)
        self._track_operation(actuator_id, result)
        self._emit_state_event(actuator_id, result, "toggle")
        return result

    @synchronized
    def set_level(self, actuator_id: int, value: float) -> ActuatorReading:
        """Set actuator level (PWM/dimming), value 0-100."""
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            raise ValueError(f"Actuator {actuator_id} not found")

        result = actuator.set_level(value)
        self.state_tracking_service.record_state_change(actuator_id, result)
        self._track_operation(actuator_id, result)
        self._emit_state_event(actuator_id, result, "set_level", {"value": value})
        return result

    @synchronized
    def pulse(self, actuator_id: int, duration_seconds: float) -> ActuatorReading:
        """Pulse actuator (on for duration then off)."""
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            raise ValueError(f"Actuator {actuator_id} not found")

        result = actuator.pulse(duration_seconds)
        self._emit_state_event(actuator_id, result, "pulse", {"duration_seconds": duration_seconds})
        return result

    @synchronized
    def get_state(self, actuator_id: int) -> ActuatorReading:
        """Get current actuator state."""
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            raise ValueError(f"Actuator {actuator_id} not found")
        return actuator.get_state()

    @synchronized
    def set_schedule(self, actuator_id: int, schedule: DeviceSchedule) -> DeviceSchedule:
        """Create a centralized schedule for an actuator."""
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            raise ValueError(f"Actuator {actuator_id} not found")

        schedule.actuator_id = actuator_id
        if schedule.unit_id <= 0:
            metadata = self.get_actuator(actuator_id) or {}
            schedule.unit_id = int(metadata.get("unit_id") or 0)
        if schedule.unit_id <= 0:
            raise ValueError(
                f"Schedule unit_id is required for actuator {actuator_id}; unable to resolve from actuator metadata"
            )

        created = self.scheduling_service.create_schedule(
            schedule,
            check_conflicts=True,
            source="user",
        )
        if not created:
            raise ValueError(f"Failed to create schedule for actuator {actuator_id}")
        logger.info(
            "Created schedule %s for actuator %s (%s-%s)",
            created.schedule_id,
            actuator_id,
            created.start_time,
            created.end_time,
        )
        return created

    @synchronized
    def clear_schedule(self, actuator_id: int) -> int:
        """Delete all centralized schedules linked to an actuator."""
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            raise ValueError(f"Actuator {actuator_id} not found")

        deleted = 0
        schedules = self.scheduling_service.get_schedules_for_actuator(actuator_id)
        for schedule in schedules:
            if not schedule.schedule_id:
                continue
            if self.scheduling_service.delete_schedule(schedule.schedule_id, source="user"):
                deleted += 1

        logger.info("Cleared %s schedules for actuator %s", deleted, actuator_id)
        return deleted

    @synchronized
    def add_interlock(self, actuator_id: int, interlocked_with: int) -> None:
        """Add safety interlock between actuators."""
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            raise ValueError(f"Actuator {actuator_id} not found")

        actuator.add_interlock(interlocked_with)
        self.safety_service.register_interlock(actuator_id, interlocked_with)
        logger.info("Added interlock: %s <-> %s", actuator_id, interlocked_with)

    @synchronized
    def remove_interlock(self, actuator_id: int, interlocked_with: int) -> None:
        """Remove safety interlock."""
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            raise ValueError(f"Actuator {actuator_id} not found")

        actuator.remove_interlock(interlocked_with)
        self.safety_service.remove_interlock(actuator_id, interlocked_with)
        logger.info("Removed interlock: %s <-> %s", actuator_id, interlocked_with)

    @synchronized
    def get_runtime_stats(self, actuator_id: int) -> dict[str, Any]:
        """Get runtime statistics."""
        return self.state_tracking_service.get_stats(actuator_id)

    @synchronized
    def turn_off_all(self) -> None:
        """Turn off all actuators."""
        for actuator in self._actuators.values():
            try:
                actuator.turn_off()
            except Exception as e:
                logger.error("Failed to turn off actuator %s: %s", actuator.actuator_id, e)
        logger.info("Turned off all actuators")

    @synchronized
    def register_discovery_callback(self, callback: Callable) -> None:
        """Register callback for auto-discovered actuators."""
        self.discovery_callbacks.append(callback)

    @synchronized
    def to_dict(self) -> dict[str, Any]:
        """Convert manager state to dictionary."""
        scheduling_active = False
        try:
            from app.workers.unified_scheduler import get_scheduler

            scheduling_active = get_scheduler().is_running()
        except Exception:
            pass

        return {
            "total_actuators": len(self._actuators),
            "actuators": [a.to_dict() for a in self._actuators.values()],
            "scheduling_active": scheduling_active,
            "energy_monitoring_enabled": self.energy_monitoring is not None,
            "zigbee2mqtt_discovery_enabled": self.zigbee2mqtt_discovery is not None,
            "timestamp": iso_now(),
        }

    def _emit_state_event(
        self, actuator_id: int, result: ActuatorReading, command: str, parameters: dict[str, Any] | None = None
    ) -> None:
        """Emit state change events."""
        try:
            self.event_bus.publish(
                DeviceEvent.DEVICE_COMMAND,
                DeviceCommandPayload(
                    command=command,
                    device_id=str(actuator_id),
                    unit_id=None,
                    parameters=parameters or {},
                    timestamp=result.timestamp.isoformat(),
                ),
            )
            self.event_bus.publish(
                DeviceEvent.ACTUATOR_STATE_CHANGED,
                ActuatorStatePayload(
                    actuator_id=actuator_id,
                    state=result.state.value,
                    value=result.value,
                    timestamp=result.timestamp.isoformat(),
                ),
            )
        except Exception:
            pass

    # ==================== Energy Monitoring ====================

    def _register_default_power_profiles(self) -> None:
        """Register default power profiles for common actuators."""
        if not self.energy_monitoring:
            return
        for profile in DEFAULT_POWER_PROFILES.values():
            self.energy_monitoring.register_power_profile(
                actuator_type=profile.actuator_type,
                rated_power_watts=profile.rated_power_watts,
                standby_power_watts=profile.standby_power_watts,
                efficiency_factor=profile.efficiency_factor,
                power_curve=profile.power_curve,
            )

    def record_power_reading(self, reading: EnergyReading) -> None:
        """Record power consumption reading from a smart switch."""
        if not self.energy_monitoring:
            logger.warning("Energy monitoring not enabled")
            return
        self.energy_monitoring.record_reading(reading)

    def get_power_consumption(self, actuator_id: int) -> float | None:
        """Get current power consumption for an actuator."""
        if not self.energy_monitoring:
            return None

        latest = self.energy_monitoring.get_latest_reading(actuator_id)
        if latest and latest.power is not None:
            return latest.power

        actuator = self._actuators.get(actuator_id)
        if not actuator:
            return None

        return self.energy_monitoring.estimate_power(
            actuator_id=actuator_id,
            actuator_type=actuator.actuator_type.value,
            level=actuator.current_value,
            state=actuator.current_state.value,
        )

    def get_energy_stats(self, actuator_id: int, hours: int | None = None) -> dict[str, Any] | None:
        """Get energy consumption statistics for an actuator."""
        if not self.energy_monitoring:
            return None
        stats = self.energy_monitoring.get_consumption_stats(actuator_id, hours)
        return stats.to_dict() if stats else None

    def get_cost_estimate(self, actuator_id: int, period: str = "daily") -> dict[str, float] | None:
        """Get electricity cost estimate for an actuator."""
        if not self.energy_monitoring:
            return None
        return self.energy_monitoring.get_cost_estimate(actuator_id, period)

    def get_total_power(self) -> float:
        """Get total power consumption across all actuators."""
        if not self.energy_monitoring:
            return 0.0
        return self.energy_monitoring.get_total_power_consumption(list(self._actuators.keys()))

    # ==================== Zigbee2MQTT Discovery ====================

    @synchronized
    def _on_device_discovered(self, device: "DiscoveredDevice") -> None:
        """Handle discovered Zigbee2MQTT device."""
        logger.info(
            f"Discovered Zigbee2MQTT device: {device.friendly_name} "
            f"(type={device.device_type}, model={device.model}, "
            f"power_monitoring={device.supports_power_monitoring})"
        )

        if device.supports_power_monitoring and self.energy_monitoring:
            self.zigbee2mqtt_discovery.register_state_callback(
                device.friendly_name, lambda state: self._on_device_state_update(device.ieee_address, state)
            )

        for callback in self.discovery_callbacks:
            try:
                callback(device)
            except Exception as e:
                logger.error("Error in discovery callback: %s", e)

    @synchronized
    def _on_device_state_update(self, ieee_address: str, state: dict[str, Any]) -> None:
        """Handle device state update (for power monitoring)."""
        if not self.energy_monitoring:
            return

        if any(key in state for key in ["power", "voltage", "current", "energy"]):
            actuator_id = self._find_actuator_by_ieee(ieee_address)
            if actuator_id:
                reading = EnergyReading(
                    actuator_id=actuator_id,
                    voltage=state.get("voltage"),
                    current=state.get("current"),
                    power=state.get("power"),
                    energy=state.get("energy"),
                    power_factor=state.get("power_factor"),
                    frequency=state.get("frequency"),
                    temperature=state.get("device_temperature"),
                )
                self.energy_monitoring.record_reading(reading)
                self._persist_power_reading(actuator_id, reading)

    @synchronized
    def _find_actuator_by_ieee(self, ieee_address: str) -> int | None:
        """Find actuator ID by Zigbee IEEE address."""
        for actuator in self._actuators.values():
            metadata = actuator.config.metadata or {}
            if metadata.get("ieee_address") == ieee_address:
                return actuator.actuator_id
        return None

    @synchronized
    def get_discovered_devices(self) -> list[dict[str, Any]]:
        """Get all discovered Zigbee2MQTT devices."""
        if not self.zigbee2mqtt_discovery:
            return []
        devices = self.zigbee2mqtt_discovery.get_discovered_devices()
        return [device.to_dict() for device in devices]

    @synchronized
    def send_zigbee2mqtt_command(self, friendly_name: str, command: dict[str, Any]) -> bool:
        """
        Send command to Zigbee2MQTT device.

        First tries to find a registered actuator with the given friendly name
        and use its adapter. Falls back to ZigbeeManagementService for
        unregistered devices.

        Args:
            friendly_name: Zigbee2MQTT device name
            command: Command dictionary to send

        Returns:
            True if command sent successfully
        """
        # First, try to find a registered actuator with this name
        for actuator in self._actuators.values():
            if actuator.name == friendly_name:
                return self.send_command(actuator.actuator_id, command)
            # Also check mqtt_topic in metadata
            mqtt_topic = actuator.metadata.get("mqtt_topic", "")
            if friendly_name in mqtt_topic:
                return self.send_command(actuator.actuator_id, command)

        # Fallback to ZigbeeManagementService for unregistered devices
        if not self.zigbee2mqtt_discovery:
            logger.error("Zigbee2MQTT discovery not enabled")
            return False
        return self.zigbee2mqtt_discovery.send_command(friendly_name, command)

    def send_command(self, actuator_id: int, command: dict[str, Any]) -> bool:
        """
        Send a command to an actuator's hardware adapter.

        Only supported for actuators with adapters that have send_command capability
        (e.g., Zigbee2MQTT actuators).

        Args:
            actuator_id: Actuator ID
            command: Command dictionary to send

        Returns:
            True if command sent successfully, False otherwise
        """
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            logger.warning("Actuator %s not found for send_command", actuator_id)
            return False

        adapter = actuator._adapter
        if not adapter:
            logger.warning("Actuator %s has no adapter for send_command", actuator_id)
            return False

        if not hasattr(adapter, "send_command"):
            logger.warning(
                f"Adapter for actuator {actuator_id} ({type(adapter).__name__}) does not support send_command"
            )
            return False

        try:
            return adapter.send_command(command)
        except Exception as e:
            logger.error("Error sending command to actuator %s: %s", actuator_id, e)
            return False

    def identify_actuator(self, actuator_id: int, duration: int = 10) -> bool:
        """
        Trigger identification on an actuator (e.g., flash LED).

        Args:
            actuator_id: Actuator ID
            duration: Identification duration in seconds

        Returns:
            True if identify command sent successfully
        """
        actuator = self._actuators.get(actuator_id)
        if not actuator or not actuator._adapter:
            logger.warning("Actuator %s not found or has no adapter", actuator_id)
            return False

        adapter = actuator._adapter
        if hasattr(adapter, "identify"):
            try:
                return adapter.identify(duration)
            except Exception as e:
                logger.error("Error identifying actuator %s: %s", actuator_id, e)
                return False

        # Fallback: try send_command with identify
        if hasattr(adapter, "send_command"):
            return adapter.send_command({"identify": duration})

        logger.warning("Actuator %s does not support identification", actuator_id)
        return False

    def get_actuator_device_info(self, actuator_id: int) -> dict[str, Any] | None:
        """
        Get device information for an actuator.

        Args:
            actuator_id: Actuator ID

        Returns:
            Device info dictionary or None
        """
        actuator = self._actuators.get(actuator_id)
        if not actuator:
            return None

        adapter = actuator._adapter
        if adapter and hasattr(adapter, "get_device_info"):
            try:
                return adapter.get_device_info()
            except Exception as e:
                logger.error("Error getting device info for actuator %s: %s", actuator_id, e)
                return None

        # Return basic info from entity
        return {
            "actuator_id": actuator_id,
            "name": actuator.config.name,
            "type": actuator.config.actuator_type.value if actuator.config.actuator_type else None,
            "protocol": actuator.config.protocol.value if actuator.config.protocol else None,
            "state": actuator.current_state.value if actuator.current_state else None,
        }

    def rename_actuator_device(self, actuator_id: int, new_name: str) -> bool:
        """
        Rename actuator device on its network (e.g., Zigbee2MQTT).

        This renames the device on the network level. You should also
        update the actuator name in the database separately.

        Args:
            actuator_id: Actuator ID
            new_name: New device name

        Returns:
            True if rename command sent successfully
        """
        actuator = self._actuators.get(actuator_id)
        if not actuator or not actuator._adapter:
            logger.warning("Actuator %s not found or has no adapter", actuator_id)
            return False

        adapter = actuator._adapter
        if hasattr(adapter, "rename"):
            try:
                return adapter.rename(new_name)
            except Exception as e:
                logger.error("Error renaming actuator %s: %s", actuator_id, e)
                return False

        logger.warning("Actuator %s does not support rename", actuator_id)
        return False

    def remove_actuator_from_network(self, actuator_id: int) -> bool:
        """
        Remove actuator device from its network (e.g., Zigbee network).

        This removes the device from the network level. The device will
        need to be re-paired to rejoin the network.

        Args:
            actuator_id: Actuator ID

        Returns:
            True if remove command sent successfully
        """
        actuator = self._actuators.get(actuator_id)
        if not actuator or not actuator._adapter:
            logger.warning("Actuator %s not found or has no adapter", actuator_id)
            return False

        adapter = actuator._adapter
        if hasattr(adapter, "remove_from_network"):
            try:
                return adapter.remove_from_network()
            except Exception as e:
                logger.error("Error removing actuator %s from network: %s", actuator_id, e)
                return False

        logger.warning("Actuator %s does not support network removal", actuator_id)
        return False

    # ==================== Health Tracking ====================

    @synchronized
    def _track_operation(self, actuator_id: int, result: ActuatorReading) -> None:
        """Track operation and update health metrics."""
        self._operation_counts[actuator_id] = self._operation_counts.get(actuator_id, 0) + 1

        if result.state == ActuatorState.ERROR:
            self._error_counts[actuator_id] = self._error_counts.get(actuator_id, 0) + 1
            self._log_anomaly(
                actuator_id=actuator_id,
                anomaly_type="operation_error",
                severity="major",
                details={"error_message": result.error_message, "timestamp": result.timestamp.isoformat()},
            )

        last_check = self._last_health_check.get(actuator_id)
        operations = self._operation_counts.get(actuator_id, 0)

        should_check = operations % 100 == 0
        if not should_check and last_check:
            should_check = (datetime.now() - last_check).total_seconds() > 3600

        if should_check:
            self._save_health_snapshot(actuator_id)
            self._last_health_check[actuator_id] = datetime.now()

    @synchronized
    def _save_health_snapshot(self, actuator_id: int) -> None:
        """Save health snapshot to database."""
        if not self.device_health_service:
            return

        try:
            actuator = self._actuators.get(actuator_id)
            if not actuator:
                return

            operations = self._operation_counts.get(actuator_id, 0)
            errors = self._error_counts.get(actuator_id, 0)

            if operations == 0:
                health_score = 100.0
            else:
                error_rate = errors / operations
                health_score = max(0, 100 - (error_rate * 100))

            if health_score >= 90:
                status = "excellent"
            elif health_score >= 75:
                status = "good"
            elif health_score >= 50:
                status = "fair"
            else:
                status = "poor"

            if hasattr(self.device_health_service, "save_actuator_health"):
                self.device_health_service.save_actuator_health(
                    actuator_id=actuator_id,
                    health_score=health_score,
                    status=status,
                    total_operations=operations,
                    failed_operations=errors,
                    average_response_time=0.0,
                )

            logger.info(
                f"Health snapshot for actuator {actuator_id}: "
                f"score={health_score:.1f}, status={status}, operations={operations}"
            )
        except Exception as e:
            logger.error("Failed to save health snapshot for actuator %s: %s", actuator_id, e)

    def _log_anomaly(self, actuator_id: int, anomaly_type: str, severity: str, details: dict[str, Any]) -> None:
        """Log anomaly to database."""
        if not self.device_health_service:
            return

        try:
            if hasattr(self.device_health_service, "log_actuator_anomaly"):
                self.device_health_service.log_actuator_anomaly(
                    actuator_id=actuator_id, anomaly_type=anomaly_type, severity=severity, details=details
                )
            logger.warning("Anomaly logged for actuator %s: type=%s, severity=%s", actuator_id, anomaly_type, severity)
        except Exception as e:
            logger.error("Failed to log anomaly for actuator %s: %s", actuator_id, e)

    @synchronized
    def _persist_power_reading(self, actuator_id: int, reading: EnergyReading) -> None:
        """Persist power reading to database."""
        if not self.device_health_service:
            return

        try:
            if reading.power is not None and hasattr(self.device_health_service, "save_actuator_power_reading"):
                self.device_health_service.save_actuator_power_reading(
                    actuator_id=actuator_id,
                    power_watts=reading.power,
                    voltage=reading.voltage,
                    current=reading.current,
                    energy_kwh=reading.energy,
                    power_factor=reading.power_factor,
                    frequency=reading.frequency,
                    temperature=reading.temperature,
                    is_estimated=False,
                )
                logger.debug("Power reading persisted for actuator %s: %sW", actuator_id, reading.power)
        except Exception as e:
            logger.error("Failed to persist power reading for actuator %s: %s", actuator_id, e)

    @synchronized
    def _load_calibration_profiles(self, actuator_id: int, actuator_type: ActuatorType) -> None:
        """Load saved calibration profiles for actuator."""
        if not self.device_health_service or not self.energy_monitoring:
            return

        try:
            calibrations = self.device_health_service.get_actuator_calibrations(actuator_id)
            if not calibrations:
                return

            for calibration in calibrations:
                if calibration.get("calibration_type") == "power_profile":
                    data = calibration.get("calibration_data", {})
                    self.energy_monitoring.register_power_profile(
                        actuator_type=actuator_type.value,
                        rated_power_watts=data.get("rated_power_watts", 0),
                        standby_power_watts=data.get("standby_power_watts", 0),
                        efficiency_factor=data.get("efficiency_factor", 1.0),
                        power_curve=data.get("power_curve"),
                    )
                    logger.info(
                        f"Loaded power profile calibration for actuator {actuator_id}: "
                        f"rated={data.get('rated_power_watts')}W"
                    )
                    break
        except Exception as e:
            logger.error("Failed to load calibration profiles for actuator %s: %s", actuator_id, e)

    # ==================== Batch Operations ====================

    def set_multiple_actuators(
        self, actuator_states: dict[int, bool], user_id: int | None = None, reason: str = "batch_operation"
    ) -> dict[int, bool]:
        """
        Set state for multiple actuators in one call.

        Args:
            actuator_states: Dictionary of {actuator_id: desired_state}
            user_id: Optional user who triggered the changes
            reason: Reason for state changes

        Returns:
            Dictionary of {actuator_id: success_bool}

        Example:
            # Turn on fan and pump, turn off light
            results = actuator_service.set_multiple_actuators({
                1: True,   # Fan ON
                2: True,   # Pump ON
                3: False   # Light OFF
            })
        """
        results = {}

        for actuator_id, state in actuator_states.items():
            try:
                success = self.set_actuator_state(actuator_id=actuator_id, state=state, user_id=user_id, reason=reason)
                results[actuator_id] = success
            except Exception as e:
                logger.error("Error in batch operation for actuator %s: %s", actuator_id, e)
                results[actuator_id] = False

        successful = sum(1 for success in results.values() if success)
        logger.info("Batch operation: %s/%s actuators updated successfully", successful, len(actuator_states))

        return results

    # ==================== Queries (Memory-First) ====================

    def get_actuator(self, actuator_id: int) -> dict[str, Any] | None:
        """
        Get actuator metadata (memory-first with DB fallback).

        Args:
            actuator_id: Actuator identifier

        Returns:
            Actuator metadata dictionary or None
        """
        try:
            # Try cache first
            cache_key = f"actuator_{actuator_id}"
            cached = self._actuator_cache.get(cache_key)

            if cached:
                logger.debug("Actuator %s metadata from cache", actuator_id)
                return cached

            # Fallback to database
            actuator = self.repository.find_actuator_config_by_id(actuator_id)

            if actuator:
                # Cache for next time
                self._actuator_cache.set(cache_key, actuator)

                logger.debug("Actuator %s metadata from database (cached)", actuator_id)
                return actuator

            logger.warning("Actuator %s not found", actuator_id)
            return None

        except Exception as e:
            logger.error("Error getting actuator %s: %s", actuator_id, e, exc_info=True)
            return None

    def list_actuators(self, unit_id: int | None = None) -> list[dict[str, Any]]:
        """
        List all actuators, optionally filtered by unit.

        Args:
            unit_id: Optional unit ID to filter actuators

        Returns:
            List of actuator metadata dictionaries
        """
        try:
            return self.repository.list_actuator_configs(unit_id=unit_id)

        except Exception as e:
            logger.error("Error listing actuators: %s", e, exc_info=True)
            return []

    def get_registered_actuator_ids(self) -> list[int]:
        """
        Get list of all registered actuator IDs.

        Returns:
            List of actuator IDs currently registered in runtime
        """
        with self._lock:
            return list(self._registered_actuators)

    # ==================== Health & Diagnostics ====================

    def get_actuator_status(self, actuator_id: int) -> dict[str, Any]:
        """
        Get actuator status and diagnostics.

        Args:
            actuator_id: Actuator identifier

        Returns:
            Status dictionary with registration, state, health, etc.
        """
        try:
            status = {
                "actuator_id": actuator_id,
                "registered": actuator_id in self._registered_actuators,
                "metadata_cached": (self._actuator_cache.get(f"actuator_{actuator_id}") is not None),
            }

            # Get metadata
            metadata = self.get_actuator(actuator_id)
            if metadata:
                status["unit_id"] = metadata.get("unit_id")
                status["actuator_type"] = metadata.get("actuator_type")
                status["protocol"] = metadata.get("protocol")

            # Get current state
            current_state = self.get_actuator_state(actuator_id)
            if current_state is not None:
                status["current_state"] = current_state

            # Get runtime stats (if available)
            runtime_stats = self.get_runtime_stats(actuator_id)
            if runtime_stats:
                status["runtime_stats"] = runtime_stats

            return status

        except Exception as e:
            logger.error("Error getting actuator %s status: %s", actuator_id, e, exc_info=True)
            return {"actuator_id": actuator_id, "error": str(e)}

    # ==================== Internal Helpers ====================

    def _auto_register_actuator(self, actuator_id: int) -> bool:
        """
        Automatically register actuator from database.

        Args:
            actuator_id: Actuator identifier

        Returns:
            True if auto-registration successful
        """
        try:
            # Load from database
            actuator = self.repository.find_actuator_config_by_id(actuator_id)

            if not actuator:
                logger.error("Actuator %s not found in database", actuator_id)
                return False
            # Register in runtime (protect registration to avoid duplicates)
            with self._lock:
                if actuator_id in self._registered_actuators:
                    logger.debug("Actuator %s already registered by another thread", actuator_id)
                    return True
                return self.register_actuator_config(actuator)

        except Exception as e:
            logger.error("Error auto-registering actuator %s: %s", actuator_id, e, exc_info=True)
            return False

    # ==================== Lifecycle ====================

    def shutdown(self) -> None:
        """
        Shutdown actuator management service.

        Turns off all actuators (safety), clears cache, releases resources.
        """
        try:
            logger.info("Shutting down ActuatorManagementService...")

            # Safety: turn off all registered actuators
            with self._lock:
                registered = list(self._registered_actuators)
            for actuator_id in registered:
                try:
                    self.set_actuator_state(actuator_id, False, reason="shutdown_safety")
                except Exception as e:
                    logger.warning("Failed to turn off actuator %s during shutdown: %s", actuator_id, e)

            # Clear cache
            self._actuator_cache.clear()

            # Clear registrations
            self._registered_actuators.clear()

            logger.info("ActuatorManagementService shutdown complete")

        except Exception as e:
            logger.error("Error during ActuatorManagementService shutdown: %s", e, exc_info=True)


__all__ = ["ActuatorManagementService"]
