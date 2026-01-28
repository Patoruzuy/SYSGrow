"""
GrowthService
=============

Application-layer service that orchestrates unit runtimes, plant lifecycle operations,
and hardware integration for the SYSGrow platform.

Design goals (audit-oriented):
- Clear separation of concerns:
    * UnitRuntime is a pure domain model (no DB calls).
    * PlantViewService is the single source of truth for in-memory plant state.
    * GrowthService coordinates repositories/services, publishes events, and logs audits.
- Deterministic eventing: a single shared EventBus is used across GrowthService,
  PlantViewService, and UnitRuntime instances to avoid split-brain behavior.
- Memory-first behaviour with persistence:
    * Read paths prefer in-memory caches and unit runtime registry.
    * Write paths mutate in-memory state first (where applicable), then persist to DB,
      and always attempt to emit audit/activity logs.
- Defensive coding:
    * All external service calls are guarded; failures are logged with context.
    * Public methods aim to be safe under partial dependency injection during tests.

This module is intended to be reviewed under SOC2-style change controls:
- Public methods are documented and avoid side effects not explicitly stated.
- AuditLogger events are emitted for sensitive actions where available.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING
import logging
import threading

from app.enums import NotificationSeverity, NotificationType
from app.enums.events import PlantEvent, RuntimeEvent
from app.schemas.events import (
    PlantLifecyclePayload,
    ThresholdsProposedPayload,
    ActivePlantSetPayload,
)
from app.utils.event_bus import EventBus
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.repositories.units import UnitRepository
from infrastructure.logging.audit import AuditLogger
from app.domain.unit_runtime import UnitRuntime
from app.domain.plant_profile import PlantProfile
from app.domain.unit_runtime_factory import UnitRuntimeFactory
from app.utils.cache import TTLCache, CacheRegistry
from app.utils.plant_json_handler import PlantJsonHandler
from app.hardware.sensors.processors.base_processor import IDataProcessor

from app.services.hardware.sensor_polling_service import SensorPollingService
from app.controllers import ClimateController, ControlLogic, PlantSensorController
from infrastructure.utils.structured_fields import (
    dump_json_field,
    normalize_dimensions,
)

if TYPE_CHECKING:
    from app.services.application.threshold_service import ThresholdService
    from app.services.application.activity_logger import ActivityLogger
    from app.services.application.notifications_service import NotificationsService
    from app.services.application.irrigation_workflow_service import IrrigationWorkflowService
    from app.services.hardware import SensorManagementService, ActuatorManagementService

logger = logging.getLogger(__name__)


class GrowthServiceError(RuntimeError):
    """Base exception for GrowthService failures."""

class NotFoundError(GrowthServiceError):
    """Resource not found."""

class ValidationError(GrowthServiceError):
    """Invalid input from caller."""


def _row_to_dict(row) -> dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    return {k: row[k] for k in row.keys()}


# Import threshold constants from ThresholdService (single source of truth)
from app.services.application.threshold_service import THRESHOLD_KEYS, PLANT_OVERRIDE_FIELDS


class GrowthService:
    """
    Application-level registry and orchestrator for growth units.

    Responsibilities:
    - Maintain registry of {unit_id: UnitRuntime} instances
    - Manage unit lifecycle (create, start, stop, delete)
    - Provide caching layer before repository calls
    - Coordinate between domain (UnitRuntime) and infrastructure (UnitRuntimeManager)

    This is the central service that the Flask app interacts with.

    Bidirectional Dependencies:
        - plant_service: PlantViewService, set by ContainerBuilder after construction for cross-service delegation
        - device_health_service: Set by ContainerBuilder for health monitoring
    """

    def __init__(
        self,
        unit_repo: UnitRepository,
        analytics_repo: AnalyticsRepository,
        audit_logger: AuditLogger,
        devices_repo: DeviceRepository,
        activity_logger: Optional['ActivityLogger'] = None,
        notifications_service: Optional['NotificationsService'] = None,
        irrigation_workflow_service: Optional['IrrigationWorkflowService'] = None,
        event_bus: Optional[EventBus] = None,
        mqtt_client: Optional[Any] = None,
        zigbee_service: Optional[Any] = None,
        threshold_service: Optional['ThresholdService'] = None,
        device_health_service: Optional[Any] = None,
        sensor_management_service: Optional['SensorManagementService'] = None,
        actuator_management_service: Optional['ActuatorManagementService'] = None,
        plant_service: Optional[Any] = None,
        sensor_processor: Optional[IDataProcessor] = None,
        ai_health_repo: Optional[Any] = None,
        cache_enabled: bool = True,
        cache_ttl_seconds: int = 30,
        cache_maxsize: int = 128,
    ):
        """
        Initialize the growth service.

        Args:
            unit_repo: Database repository for unit operations
            analytics_repo: Database repository for analytics
            devices_repo: Database repository for devices (needed for hardware managers - LEGACY)
            audit_logger: Audit logging service
            activity_logger: Optional activity logger for user-visible actions
            notifications_service: Optional NotificationsService for action workflows
            irrigation_workflow_service: Optional IrrigationWorkflowService for approval workflows
            event_bus: Shared EventBus for inter-service events
            mqtt_client: Optional MQTT client for wireless sensors
            zigbee_service: Optional shared ZigbeeManagementService
            threshold_service: Optional service for unified threshold management
            device_health_service: Optional singleton DeviceHealthService from container
            sensor_management_service: Optional singleton SensorManagementService (NEW)
            actuator_management_service: Optional singleton ActuatorManagementService (NEW)
            plant_service: Optional PlantViewService for cross-service delegation (circular dependency)
            sensor_processor: Optional sensor processor pipeline (CompositeProcessor) for priority filtering
            ai_health_repo: Optional AIHealthDataRepository for control log storage
        """
        self.unit_repo = unit_repo
        self.analytics_repo = analytics_repo
        self.devices_repo = devices_repo
        self.audit_logger = audit_logger
        self.activity_logger = activity_logger
        self.notifications_service = notifications_service
        self.irrigation_workflow_service = irrigation_workflow_service
        self.event_bus = event_bus or EventBus()
        self.mqtt_client = mqtt_client
        self.zigbee_service = zigbee_service
        self.threshold_service = threshold_service
        self.device_health_service = device_health_service
        self.sensor_processor = sensor_processor
        self.ai_health_repo = ai_health_repo

        # Hardware management services (singleton, memory-first)
        self.sensor_service = sensor_management_service
        self.actuator_service = actuator_management_service

        # Circular dependency - will be set by ContainerBuilder
        self._plant_service = plant_service

        # Factory for creating UnitRuntime instances
        # PlantService is passed to delegate PlantProfile creation
        self.factory = UnitRuntimeFactory(
            plant_handler=PlantJsonHandler(),
            threshold_service=threshold_service,
            plant_service=plant_service,
        )

        self._unit_cache = TTLCache(
            enabled=cache_enabled,
            ttl_seconds=cache_ttl_seconds,
            maxsize=cache_maxsize,
        )
        # Register cache for monitoring
        try:
            CacheRegistry.get_instance().register("growth_service.units", self._unit_cache)
        except ValueError:
            # Cache already registered (e.g., during testing)
            pass

        # Registry of active unit runtimes
        self._unit_runtimes: Dict[int, UnitRuntime] = {}
        self._runtime_lock = threading.Lock()
        
        # Per-unit infrastructure
        # unit_id -> SensorPollingService
        self._polling_services: Dict[int, SensorPollingService] = {}
        # unit_id -> ClimateController
        self._climate_controllers: Dict[int, ClimateController] = {}
        # unit_id -> PlantSensorController (plant sensors + irrigation workflow)
        self._plant_sensor_controllers: Dict[int, PlantSensorController] = {}
        

        logger.info(
            f"GrowthService initialized "
            f"(hardware_services={'enabled' if sensor_management_service else 'disabled'})"
        )

        # Subscribe to runtime events for persistence
        self._subscribe_to_runtime_events()
        self._subscribe_to_plant_events()
        
        # Wire up ThresholdService event handling and cache invalidation
        self._setup_threshold_service_integration()

    def _subscribe_to_runtime_events(self) -> None:
        """Subscribe to RuntimeEvent.* events for persistence."""
        if self.event_bus:
            # Note: THRESHOLDS_PERSIST is handled by ThresholdService directly
            self.event_bus.subscribe(RuntimeEvent.THRESHOLDS_PROPOSED, self._handle_thresholds_proposed)
            self.event_bus.subscribe(RuntimeEvent.ACTIVE_PLANT_SET, self._handle_active_plant_set)
            logger.debug(
                "GrowthService subscribed to RuntimeEvent.THRESHOLDS_PROPOSED and ACTIVE_PLANT_SET"
            )

    def _subscribe_to_plant_events(self) -> None:
        """Subscribe to PlantEvent.* events for schedule automation."""
        if self.event_bus:
            self.event_bus.subscribe(PlantEvent.ACTIVE_PLANT_CHANGED, self._handle_active_plant_changed)
            logger.debug("GrowthService subscribed to PlantEvent.ACTIVE_PLANT_CHANGED")

    def _setup_threshold_service_integration(self) -> None:
        """Wire up ThresholdService event handling and cache invalidation."""
        if self.threshold_service:
            # ThresholdService handles THRESHOLDS_PERSIST event
            self.threshold_service.subscribe_to_events()
            # Allow ThresholdService to invalidate our cache after persistence
            self.threshold_service.set_cache_invalidation_callback(self._invalidate_unit_cache)

    def _handle_thresholds_proposed(self, payload: ThresholdsProposedPayload) -> None:
        """Handle RuntimeEvent.THRESHOLDS_PROPOSED from UnitRuntime."""
        try:
            if not self.notifications_service:
                logger.debug("Notifications service unavailable; skipping threshold proposals")
                return

            if isinstance(payload, dict):
                unit_id = payload.get("unit_id")
                user_id = payload.get("user_id")
                plant_id = payload.get("plant_id")
                plant_type = payload.get("plant_type")
                growth_stage = payload.get("growth_stage")
                current_thresholds = payload.get("current_thresholds", {}) or {}
                proposed_thresholds = payload.get("proposed_thresholds", {}) or {}
            else:
                unit_id = payload.unit_id
                user_id = payload.user_id
                plant_id = payload.plant_id
                plant_type = payload.plant_type
                growth_stage = payload.growth_stage
                current_thresholds = payload.current_thresholds or {}
                proposed_thresholds = payload.proposed_thresholds or {}

            if unit_id is None or not proposed_thresholds:
                return

            if not current_thresholds:
                runtime = self.get_unit_runtime(unit_id)

            # Best-effort unlink of sensors before deleting plant records.
            # This avoids FK violations and keeps linkage tables tidy.
            try:
                if self._plant_service:
                    self._plant_service.unlink_all_sensors_from_plant(plant_id)
            except Exception as exc:
                logger.debug(
                    "Failed to unlink sensors from plant %s prior to removal: %s",
                    plant_id,
                    exc,
                    exc_info=True,
                )

            if runtime:
                current_thresholds = runtime.settings.to_dict()

            # Use ThresholdService for filtering (single source of truth)
            if self.threshold_service:
                filtered_current, filtered_proposed = self.threshold_service.filter_threshold_changes(
                    current_thresholds,
                    proposed_thresholds,
                )
            else:
                # Fallback if ThresholdService not available
                filtered_current, filtered_proposed = current_thresholds, proposed_thresholds

            if not filtered_proposed:
                return

            if user_id is None:
                unit_row = self.unit_repo.get_unit(unit_id)
                unit_data = _row_to_dict(unit_row) if unit_row else {}
                user_id = unit_data.get("user_id")

            if not user_id:
                logger.debug("No user_id for unit %s; skipping threshold proposal", unit_id)
                return

            plant_label = plant_type or "plant"
            stage_label = growth_stage or "current stage"
            title = "AI Threshold Update Proposal"
            message = (
                f"AI suggests updated thresholds for {plant_label} "
                f"({stage_label}). Review and accept to apply."
            )

            action_data = {
                "unit_id": unit_id,
                "plant_id": plant_id,
                "plant_type": plant_type,
                "growth_stage": growth_stage,
                "current_thresholds": filtered_current,
                "proposed_thresholds": filtered_proposed,
            }

            self.notifications_service.send_notification(
                user_id=user_id,
                notification_type=NotificationType.SYSTEM_ALERT,
                title=title,
                message=message,
                severity=NotificationSeverity.INFO,
                source_type="unit",
                source_id=unit_id,
                unit_id=unit_id,
                requires_action=True,
                action_type="threshold_update",
                action_data=action_data,
            )

        except Exception as e:
            logger.error(f"Error handling THRESHOLDS_PROPOSED event: {e}", exc_info=True)

    def _handle_active_plant_set(self, payload: ActivePlantSetPayload) -> None:
        """Handle RuntimeEvent.ACTIVE_PLANT_SET from UnitRuntime."""
        try:
            if isinstance(payload, dict):
                unit_id = payload.get("unit_id")
                plant_id = payload.get("plant_id")
            else:
                unit_id = payload.unit_id
                plant_id = payload.plant_id

            if unit_id is None or plant_id is None:
                return

            # Persist active plant to database via PlantViewService
            try:
                if self._plant_service:
                    self._plant_service.set_active_plant(unit_id, plant_id)
            except Exception as exc:
                logger.debug("Failed to persist active plant %s: %s", plant_id, exc, exc_info=True)

            # Emit ACTIVE_PLANT_CHANGED event for subscribers
            runtime = self.get_unit_runtime(unit_id)
            if runtime:
                # Use PlantService (single source of truth)
                plant = None
                if self._plant_service:
                    plant = self._plant_service.get_plant(plant_id, unit_id)
                if plant:
                    self._apply_active_plant_overrides(runtime, plant)
                    runtime.apply_ai_conditions()
                    self.event_bus.publish(
                        PlantEvent.ACTIVE_PLANT_CHANGED,
                        PlantLifecyclePayload(unit_id=unit_id, plant_id=plant_id),
                    )

                    # Log activity
                    if self.activity_logger:
                        from app.services.application.activity_logger import ActivityLogger
                        self.activity_logger.log_activity(
                            activity_type=ActivityLogger.PLANT_UPDATED,
                            description=f"Set active plant to '{plant.plant_name}' in unit {unit_id}",
                            severity=ActivityLogger.INFO,
                            entity_type="plant",
                            entity_id=plant_id,
                            metadata={"plant_type": plant.plant_type or "Unknown", "unit_id": unit_id},
                        )
                    logger.debug(f"Activated plant {plant_id} in unit {unit_id}")

        except Exception as e:
            logger.error(f"Error handling ACTIVE_PLANT_SET event: {e}", exc_info=True)

    def _handle_active_plant_changed(self, payload: PlantLifecyclePayload) -> None:
        """Auto-apply plant stage schedules when active plant changes."""
        try:
            if isinstance(payload, dict):
                unit_id = payload.get("unit_id")
                plant_id = payload.get("plant_id")
            else:
                unit_id = payload.unit_id
                plant_id = payload.plant_id

            if unit_id is None or plant_id is None:
                return

            self._auto_apply_plant_stage_schedules(
                unit_id=unit_id,
                plant_id=plant_id,
                require_empty=False,
                reason="active_plant_changed",
            )
        except Exception as e:
            logger.error("Error handling ACTIVE_PLANT_CHANGED event: %s", e, exc_info=True)

    def _apply_active_plant_overrides(self, runtime: UnitRuntime, plant: PlantProfile) -> None:
        """Apply per-plant overrides when a plant becomes active."""
        if self.threshold_service:
            overrides = self.threshold_service.get_plant_overrides(plant.plant_id)
        else:
            overrides = plant.get_threshold_overrides()
        if not overrides:
            return

        current_thresholds = runtime.settings.to_dict()
        changes: Dict[str, float] = {}
        for key, value in overrides.items():
            if key not in THRESHOLD_KEYS:
                continue
            if current_thresholds.get(key) != value:
                changes[key] = value

        if changes:
            self.update_unit_thresholds(runtime.unit_id, changes)

    def _get_scheduling_service(self):
        manager = getattr(self.actuator_service, "actuator_manager", None)
        return getattr(manager, "scheduling_service", None)

    def _resolve_unit_actuator_ids(
        self,
        unit_id: int,
    ) -> tuple[Optional[int], Optional[int]]:
        if not self.devices_repo:
            return None, None
        try:
            actuators = self.devices_repo.list_actuator_configs(unit_id=unit_id)
        except Exception as exc:
            logger.debug(
                "Failed to list actuators for unit %s: %s",
                unit_id,
                exc,
                exc_info=True,
            )
            return None, None

        light_actuator = next(
            (a for a in actuators if str(a.get("actuator_type", "")).lower() == "light"),
            None,
        )
        fan_actuator = next(
            (a for a in actuators if str(a.get("actuator_type", "")).lower() == "fan"),
            None,
        )
        light_actuator_id = light_actuator.get("actuator_id") if light_actuator else None
        fan_actuator_id = fan_actuator.get("actuator_id") if fan_actuator else None
        return light_actuator_id, fan_actuator_id

    def _build_plant_schedule_payload(
        self,
        plant: PlantProfile,
    ) -> tuple[str, str, Dict[str, Any]]:
        if not self._plant_service:
            raise ValueError("PlantService not available")

        plant_type = plant.plant_type or plant.plant_name or "default"
        current_stage = plant.current_stage or "Vegetative"
        automation = self._plant_service.get_plant_automation_settings(plant_type) or {}
        lighting_schedule = automation.get("lighting_schedule") or {}
        stage_key = (current_stage or "").strip().lower() or "default"
        stage_lighting = lighting_schedule.get(stage_key) or {}

        hours = stage_lighting.get("hours")
        if hours is None:
            hours = stage_lighting.get("hours_per_day")
        intensity = stage_lighting.get("intensity")

        if hours is None or intensity is None:
            raise ValueError(
                f"Lighting data missing for plant '{plant_type}' stage '{current_stage}'."
            )

        automation = dict(automation)
        lighting_schedule = dict(lighting_schedule)
        lighting_schedule[stage_key] = {"hours": hours, "intensity": intensity}
        automation["lighting_schedule"] = lighting_schedule
        return plant_type, current_stage, {"automation": automation}

    def _auto_apply_plant_stage_schedules(
        self,
        *,
        unit_id: int,
        plant_id: Optional[int] = None,
        require_empty: bool = False,
        reason: str = "auto",
    ) -> int:
        scheduling_service = self._get_scheduling_service()
        if not scheduling_service:
            logger.debug(
                "SchedulingService not available; skipping auto schedules for unit %s",
                unit_id,
            )
            return 0
        if not self._plant_service:
            logger.debug(
                "PlantService not available; skipping auto schedules for unit %s",
                unit_id,
            )
            return 0

        schedules = scheduling_service.get_schedules_for_unit(unit_id)
        if require_empty and schedules:
            logger.debug(
                "Schedules already exist for unit %s; skipping auto generation (%s)",
                unit_id,
                reason,
            )
            return 0

        if not require_empty:
            has_custom = any(not s.metadata.get("auto_generated") for s in schedules)
            if has_custom:
                logger.debug(
                    "Custom schedules exist for unit %s; skipping auto generation (%s)",
                    unit_id,
                    reason,
                )
                return 0

        plant = None
        if plant_id:
            plant = self._plant_service.get_plant(plant_id, unit_id=unit_id)
        if not plant:
            plant = self._plant_service.get_active_plant(unit_id)
        if not plant:
            plants = self._plant_service.list_plants(unit_id)
            plant = plants[0] if plants else None

        if not plant:
            logger.debug("No plant found for unit %s; skipping auto schedules", unit_id)
            return 0

        try:
            plant_type, current_stage, plant_info = self._build_plant_schedule_payload(plant)
        except ValueError as exc:
            logger.warning(
                "Skipping auto schedules for unit %s: %s",
                unit_id,
                exc,
            )
            return 0

        light_actuator_id, fan_actuator_id = self._resolve_unit_actuator_ids(unit_id)

        try:
            created_count = scheduling_service.apply_plant_stage_schedules(
                unit_id=unit_id,
                plant_info=plant_info,
                current_stage=current_stage,
                light_actuator_id=light_actuator_id,
                fan_actuator_id=fan_actuator_id,
                replace_existing=True,
            )
        except ValueError as exc:
            logger.warning(
                "Auto schedule generation failed for unit %s: %s",
                unit_id,
                exc,
            )
            return 0

        if created_count:
            logger.info(
                "Auto-generated %d schedules for unit %s (%s, %s)",
                created_count,
                unit_id,
                plant_type,
                current_stage,
            )
        return created_count

    def _update_plant_threshold_overrides(
        self,
        plant_id: int,
        thresholds: Dict[str, float],
        unit_id: Optional[int] = None,
    ) -> bool:
        """Persist threshold overrides to plant and update runtime cache."""
        if not thresholds:
            return False

        if not self.threshold_service:
            logger.warning(
                "ThresholdService not available; skipping override persistence for plant %s",
                plant_id,
            )
            return False

        persisted = self.threshold_service.update_plant_overrides(plant_id, thresholds)
        if not persisted:
            return False

        # Resolve unit_id if not provided, using PlantViewService
        if unit_id is None and self._plant_service:
            plant_data = self._plant_service.get_plant_as_dict(plant_id)
            if plant_data:
                unit_id = plant_data.get("unit_id")

        if unit_id:
            self._invalidate_unit_cache(unit_id)
            runtime = self.get_unit_runtime(unit_id)
            if runtime:
                # Use PlantService (single source of truth)
                plant = None
                if self._plant_service:
                    plant = self._plant_service.get_plant(plant_id, unit_id)
                if plant:
                    plant.set_threshold_overrides(thresholds)

        return persisted

    def handle_threshold_update_action(
        self,
        action_response: str,
        action_data: Dict[str, Any],
        message: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Apply threshold updates after user confirmation."""
        response = (action_response or "").strip().lower()
        accepted = response in {"confirm", "approved", "approve", "accept", "accepted", "yes"}
        if not accepted:
            return True

        unit_id = action_data.get("unit_id") or (message or {}).get("unit_id")
        plant_id = action_data.get("plant_id")
        proposed = action_data.get("proposed_thresholds") or {}

        try:
            unit_id = int(unit_id)
        except (TypeError, ValueError):
            unit_id = None

        if plant_id is not None:
            try:
                plant_id = int(plant_id)
            except (TypeError, ValueError):
                plant_id = None

        if unit_id is None or not proposed:
            logger.debug("Threshold update action missing unit_id or proposed thresholds")
            return False

        threshold_updates: Dict[str, float] = {}
        for key in THRESHOLD_KEYS:
            if key not in proposed:
                continue
            try:
                threshold_updates[key] = float(proposed[key])
            except (TypeError, ValueError):
                continue

        if not threshold_updates:
            return False

        overrides_ok = True
        if plant_id:
            overrides_ok = self._update_plant_threshold_overrides(
                plant_id,
                threshold_updates,
                unit_id=unit_id,
            )

        apply_to_unit = True
        runtime = self.get_unit_runtime(unit_id)
        if runtime and plant_id:
            # Get active plant from PlantService (single source of truth)
            active = self._plant_service.get_active_plant(unit_id) if self._plant_service else None
            if active and active.plant_id != plant_id:
                apply_to_unit = False

        applied = True
        if apply_to_unit:
            applied = self.update_unit_thresholds(unit_id, threshold_updates)

        return overrides_ok and applied

    def _invalidate_unit_cache(self, unit_id: int) -> None:
        """Invalidate cached unit payloads after writes."""
        try:
            self._unit_cache.invalidate(unit_id)
        except Exception:
            logger.debug("Cache invalidation failed for unit %s", unit_id, exc_info=True)

    def _require_runtime(self, unit_id: int) -> UnitRuntime:
        """
        Resolve a UnitRuntime for a unit_id.

        Contract:
        - Returns a runtime if the unit exists (creating/loading it if needed).
        - Raises NotFoundError if the unit does not exist.
        """
        runtime = self.get_unit_runtime(unit_id)
        if runtime is None:
            raise NotFoundError(f"Growth unit {unit_id} not found")
        return runtime

    def _resolve_soil_moisture_context(
        self,
        *,
        unit_id: int,
        sensor_id: Optional[int],
    ) -> Dict[str, Any]:
        """
        Resolve plant-specific context for a soil moisture sensor (thin wrapper).
        
        Delegates to PlantViewService which owns plant context resolution.
        Exists for backward compatibility with ClimateController.
        
        Args:
            unit_id: Unit identifier
            sensor_id: Sensor identifier
            
        Returns:
            Plant context dictionary
        """
        if sensor_id is None:
            return {}
        
        if not self._plant_service:
            logger.warning("PlantViewService not available; cannot resolve plant context")
            return {}
        
        try:
            return self._plant_service.get_plant_context_for_sensor(
                unit_id=unit_id,
                sensor_id=sensor_id,
            )
        except Exception as exc:
            logger.debug(f"Failed to resolve plant context for sensor {sensor_id}: {exc}", exc_info=True)
            return {}
    
    # ==================== Unit Registry Management ====================
    
    def start_unit_runtime(self, unit_id: int) -> bool:
        """
        Start hardware operations for a unit.
        
        This method now directly manages infrastructure without UnitRuntimeManager wrapper.
        Responsibilities:
        - Initialize sensor polling
        - Initialize climate control  
        - Load and register devices with hardware services
        - Setup plant growth scheduling
        
        Args:
            unit_id: Unit identifier
            
        Returns:
            True if successful
        """
        runtime = self.get_unit_runtime(unit_id)
        if not runtime:
            logger.error(f"Cannot start unit {unit_id}: not found")
            return False
        
        try:
            # Direct infrastructure initialization (no UnitRuntimeManager)
            if self.sensor_service and self.actuator_service:
                logger.info(
                    f"Starting runtime for unit {unit_id} ({runtime.unit_name}) "
                    f"using singleton hardware services"
                )
                
                # 1. Load devices from database
                if self.devices_repo:
                    sensors = self.devices_repo.list_sensor_configs(unit_id=unit_id)
                    actuators = self.devices_repo.list_actuator_configs(unit_id=unit_id)
                    
                    # 2. Register devices with singleton hardware services
                    for sensor in sensors:
                        try:
                            self.sensor_service.register_sensor_config(sensor)
                            logger.debug(f"   Registered sensor {sensor.get('sensor_id')} for unit {unit_id}")
                        except Exception as e:
                            logger.warning(f"Failed to register sensor {sensor.get('sensor_id')}: {e}")
                    
                    for actuator in actuators:
                        try:
                            self.actuator_service.register_actuator_config(actuator)
                            logger.debug(f"   Registered actuator {actuator.get('actuator_id')} for unit {unit_id}")
                        except Exception as e:
                            logger.warning(f"Failed to register actuator {actuator.get('actuator_id')}: {e}")
                    
                    # 3. Sensor polling is managed by SensorManagementService
                    # It auto-starts when GPIO/WiFi sensors are registered
                    polling_service = self.sensor_service.polling_service
                    self._polling_services[unit_id] = polling_service
                    logger.debug(f"   Sensor polling service referenced for unit {unit_id}")
                    
                    # 4. Initialize climate control (per-unit)
                    # Note: Primary sensor filtering is done by CompositeProcessor before events
                    # reach ClimateController, so no priority_processor is needed here.
                    control_logic = ControlLogic(
                        self.actuator_service,
                        analytics_repo=self.analytics_repo,
                        event_bus=self.event_bus,
                    )
                    climate_controller = ClimateController(
                        unit_id=unit_id,
                        control_logic=control_logic,
                        polling_service=polling_service,
                        analytics_repo=self.analytics_repo,
                    )
                    plant_sensor_controller = PlantSensorController(
                        unit_id=unit_id,
                        analytics_repo=self.analytics_repo,
                        irrigation_workflow_service=self.irrigation_workflow_service,
                        plant_context_resolver=self._resolve_soil_moisture_context,
                        threshold_service=self.threshold_service,
                        event_bus=self.event_bus,
                    )
                    thresholds = None
                    if self.threshold_service:
                        thresholds = self.threshold_service.get_unit_thresholds(unit_id)
                    if thresholds:
                        control_logic.update_thresholds(
                            {
                                "temperature": thresholds.temperature,
                                "humidity": thresholds.humidity,
                                "co2": thresholds.co2,
                                "voc": thresholds.voc,
                                "lux": thresholds.lux,
                                "air_quality": thresholds.air_quality
                            }
                        )
                    else:
                        control_logic.update_thresholds(
                            {
                                "temperature": runtime.settings.temperature_threshold,
                                "humidity": runtime.settings.humidity_threshold,
                                "co2": runtime.settings.co2_threshold,
                                "voc": runtime.settings.voc_threshold,
                                "lux": runtime.settings.lux_threshold,
                                "air_quality": runtime.settings.air_quality_threshold
                            }
                        )
                    climate_controller.start()
                    self._climate_controllers[unit_id] = climate_controller
                    self._plant_sensor_controllers[unit_id] = plant_sensor_controller
                    logger.debug(f"   Climate controller started for unit {unit_id}")
                    
                    # 5. Load schedules into memory (memory-first pattern)
                    # Schedules are owned by SchedulingService via ActuatorManager
                    scheduling_service = getattr(
                        getattr(self.actuator_service, 'actuator_manager', None),
                        'scheduling_service',
                        None
                    )
                    if scheduling_service:
                        schedule_count = scheduling_service.load_schedules_for_unit(unit_id)
                        logger.debug(f"   Loaded {schedule_count} schedules for unit {unit_id}")
                    
                    # 6. Mark hardware as running on runtime
                    # Note: Plant growth scheduling is handled globally by UnifiedScheduler
                    # (see app/workers/scheduled_tasks.py -> plant_grow_task)
                    runtime.set_hardware_running(True)

                    logger.info("Unit %s runtime fully operational (new architecture)", unit_id)
                    return True
            
            logger.error(
                "Hardware services not available for unit %s; cannot start runtime",
                unit_id,
            )
            return False
            
        except Exception as e:
            logger.error(f"Error starting runtime for unit {unit_id}: {e}", exc_info=True)
            return False
    
    def stop_unit_runtime(self, unit_id: int) -> bool:
        """
        Stop hardware operations for a unit.

        Cleans up all per-unit infrastructure:
        - Stop sensor polling
        - Stop climate control
        - Unregister devices from hardware services (optional)

        Note: Plant growth scheduling is handled globally by UnifiedScheduler

        Args:
            unit_id: Unit identifier

        Returns:
            True if successful
        """
        with self._runtime_lock:
            runtime = self._unit_runtimes.get(unit_id)

        if not runtime:
            logger.warning(f"Unit {unit_id} not in runtime registry")
            return False

        try:
            # Clean up per-unit infrastructure
            # 1. Stop sensor polling
            if unit_id in self._polling_services:
                self._polling_services[unit_id].stop_polling()
                del self._polling_services[unit_id]
                logger.debug(f"   Stopped sensor polling for unit {unit_id}")

            # 2. Stop climate control (no explicit stop needed - event-driven)
            if unit_id in self._climate_controllers:
                del self._climate_controllers[unit_id]
                logger.debug(f"   Stopped climate controller for unit {unit_id}")
            if unit_id in self._plant_sensor_controllers:
                del self._plant_sensor_controllers[unit_id]
                logger.debug(f"   Stopped plant sensor controller for unit {unit_id}")

            # 3. Clear schedules from memory (memory-first cleanup)
            scheduling_service = getattr(
                getattr(self.actuator_service, 'actuator_manager', None),
                'scheduling_service',
                None
            )
            if scheduling_service:
                scheduling_service.clear_unit_schedules(unit_id)
                logger.debug(f"   Cleared schedules from memory for unit {unit_id}")

            # 4. Mark hardware as not running on runtime
            runtime.set_hardware_running(False)

            # Remove from registry
            with self._runtime_lock:
                del self._unit_runtimes[unit_id]

            logger.info(f"Stopped and removed unit {unit_id} from registry")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping runtime for unit {unit_id}: {e}", exc_info=True)
            return False

    def is_unit_hardware_running(self, unit_id: int) -> bool:
        polling_service = self._polling_services.get(unit_id)
        return polling_service is not None

    def get_climate_controller(self, unit_id: int):
        """Return the ClimateController instance for a unit, if running."""
        return self._climate_controllers.get(unit_id)
        
    def get_unit_runtimes(self) -> Dict[int, UnitRuntime]:
        """
        Get all active unit runtimes.

        Returns:
            Dictionary of {unit_id: UnitRuntime}
        """
        with self._runtime_lock:
            return dict(self._unit_runtimes)

    def get_unit_runtime(self, unit_id: int) -> Optional[UnitRuntime]:
        """
        Fetch or create the UnitRuntime instance for a unit.

        Attempts the in-memory registry first, then loads from the database and
        constructs a runtime if necessary. Plants are loaded via PlantService.
        """
        with self._runtime_lock:
            if unit_id in self._unit_runtimes:
                return self._unit_runtimes[unit_id]

        try:
            row = self.unit_repo.get_unit(unit_id)
            if not row:
                return None
            unit_data = _row_to_dict(row)
            
            # Factory creates runtime WITHOUT plants
            runtime = self.factory.create_runtime(unit_data)
            
            # PlantService loads plants into its own collection
            if self._plant_service:
                active_plant_id = unit_data.get('active_plant_id')
                plant_count = self._plant_service.load_plants_for_unit(unit_id, active_plant_id)
                logger.debug(
                    f"PlantService loaded {plant_count} plants for unit {unit_id}"
                )
            
            with self._runtime_lock:
                self._unit_runtimes[unit_id] = runtime
            return runtime
        except Exception as exc:
            logger.error("Error loading runtime for unit %s: %s", unit_id, exc, exc_info=True)
            return None
    
    def update_unit_thresholds(self, unit_id: int, thresholds: Dict[str, float]) -> bool:
        """
        Update environmental thresholds for a unit.
        
        Args:
            unit_id: Unit identifier
            thresholds: Dictionary of threshold values
            
        Returns:
            True if successful
        """
        if "lux_threshold" not in thresholds:
            if "lux_threshold" in thresholds:
                thresholds = dict(thresholds)
                thresholds["lux_threshold"] = thresholds.get("lux_threshold")
            elif "light_threshold" in thresholds:
                thresholds = dict(thresholds)
                thresholds["lux_threshold"] = thresholds.get("light_threshold")
            elif "lux" in thresholds:
                thresholds = dict(thresholds)
                thresholds["lux_threshold"] = thresholds.get("lux")

        runtime = self.get_unit_runtime(unit_id)
        if runtime and hasattr(runtime, "update_settings"):
            runtime.update_settings(**thresholds)

        repo_fields: Dict[str, float] = {}
        for key in THRESHOLD_KEYS:
            if key in thresholds:
                repo_fields[key] = thresholds[key]

        if not repo_fields:
            logger.warning("No thresholds provided to update for unit %s", unit_id)
            return bool(runtime)

        if not self.threshold_service:
            logger.warning(
                "ThresholdService not available; skipping persistence for unit %s",
                unit_id,
            )
            return bool(runtime)

        persisted = self.threshold_service.update_unit_thresholds(unit_id, repo_fields)
        if persisted:
            self._invalidate_unit_cache(unit_id)
        return persisted or bool(runtime)

    def set_active_plant(self, unit_id: int, plant_id: int) -> bool:
        """
        Set active plant for a unit (thin wrapper).
        
        Delegates to PlantViewService which owns plant lifecycle operations.
        Exists for backward compatibility and to handle runtime updates.
        
        Args:
            unit_id: Unit identifier
            plant_id: Plant identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self._plant_service:
            logger.error("PlantViewService not available; cannot set active plant")
            return False

        try:
            # Delegate to PlantViewService (handles DB, memory, events)
            success = self._plant_service.set_active_plant(unit_id, plant_id)
            
            if success:
                # Apply plant overrides and trigger AI conditions on runtime
                runtime = self.get_unit_runtime(unit_id)
                if runtime:
                    plant = self._plant_service.get_plant(plant_id, unit_id)
                    if plant:
                        self._apply_active_plant_overrides(runtime, plant)
                        runtime.apply_ai_conditions()
            
            return success
            
        except Exception as exc:
            logger.error(f"Failed to set active plant via PlantViewService: {exc}", exc_info=True)
            return False

    def add_plant_to_unit(
        self,
        unit_id: int,
        plant_name: str,
        plant_type: str,
        current_stage: str,
        days_in_stage: int = 0,
        growth_stages: Optional[Any] = None,
        moisture_level: float = 0.0,
        # Creation-time fields
        pot_size_liters: float = 0.0,
        pot_material: str = "plastic",
        growing_medium: str = "soil",
        medium_ph: float = 7.0,
        strain_variety: Optional[str] = None,
        expected_yield_grams: float = 0.0,
        light_distance_cm: float = 0.0,
    ) -> Optional[int]:
        """
        Create plant in unit (thin wrapper).
        
        Delegates to PlantViewService which owns plant lifecycle operations.
        Exists for backward compatibility with code that calls GrowthService directly.
        
        Args:
            unit_id: Unit identifier
            plant_name: Plant name
            plant_type: Plant type/species
            current_stage: Initial growth stage
            days_in_stage: Days in current stage
            growth_stages: Optional growth stages (unused - loaded from plant_json_handler)
            moisture_level: Initial moisture level
            pot_size_liters: Container size in liters
            pot_material: Container material
            growing_medium: Growing medium type
            medium_ph: pH level
            strain_variety: Specific cultivar/strain
            expected_yield_grams: Target harvest amount
            light_distance_cm: Light distance
            
        Returns:
            Plant ID if successful, None otherwise
        """
        if not self._plant_service:
            logger.error("PlantViewService not available; cannot create plant")
            return None

        try:
            result = self._plant_service.create_plant(
                unit_id=unit_id,
                plant_name=plant_name,
                plant_type=plant_type,
                current_stage=current_stage,
                days_in_stage=days_in_stage,
                moisture_level=moisture_level,
                pot_size_liters=pot_size_liters,
                pot_material=pot_material,
                growing_medium=growing_medium,
                medium_ph=medium_ph,
                strain_variety=strain_variety,
                expected_yield_grams=expected_yield_grams,
                light_distance_cm=light_distance_cm,
            )
            
            if result:
                # Invalidate cache for API responses
                self._invalidate_unit_cache(unit_id)
                return result.get('plant_id')
            return None
            
        except Exception as exc:
            logger.error(f"Failed to create plant via PlantViewService: {exc}", exc_info=True)
            return None

    def remove_plant_from_unit(self, unit_id: int, plant_id: int) -> bool:
        """
        Remove plant from unit (thin wrapper).
        
        Delegates to PlantViewService which owns plant lifecycle operations.
        Exists for backward compatibility with code that calls GrowthService directly.
        
        Args:
            unit_id: Unit identifier
            plant_id: Plant identifier
            
        Returns:
            True if successful, False otherwise
        """
        if not self._plant_service:
            logger.error("PlantViewService not available; cannot remove plant")
            return False

        try:
            success = self._plant_service.remove_plant(unit_id, plant_id)
            
            if success:
                # Invalidate cache for API responses
                self._invalidate_unit_cache(unit_id)
            
            return success
            
        except Exception as exc:
            logger.error(f"Failed to remove plant via PlantViewService: {exc}", exc_info=True)
            return False

    # ==================== Unit CRUD Operations ====================
    
    def list_units(self, user_id: Optional[int] = None) -> List[dict[str, Any]]:
        """
        List all units, optionally filtered by user.
        
        Args:
            user_id: Optional user filter
            
        Returns:
            List of unit dictionaries
        """
        try:
            units_by_id: dict[int, dict[str, Any]] = {}

            # First: populate from in-memory runtime registry
            with self._runtime_lock:
                for unit_id, runtime in self._unit_runtimes.items():
                    # Apply user filter if specified
                    if user_id is not None and runtime.user_id != user_id:
                        continue
                    try:
                        data = runtime.to_dict()
                        units_by_id[unit_id] = data
                    except Exception as exc:
                        logger.debug("Unable to serialize runtime for unit %s: %s", unit_id, exc)
            # Second: only fetch from database if no units found in memory
            if not units_by_id:
                rows = (
                    self.unit_repo.get_user_units(user_id)
                    if user_id
                    else self.unit_repo.list_units()
                )

                for row in rows or []:
                    unit_dict = _row_to_dict(row)
                    unit_id = unit_dict.get("unit_id")
                    if unit_id is not None:
                        units_by_id[unit_id] = unit_dict
                        self._unit_cache.set(unit_id, unit_dict)
                        # Optionally create runtime for units not yet loaded
                        try:
                            runtime = self.factory.create_runtime(unit_dict)
                            with self._runtime_lock:
                                self._unit_runtimes[unit_id] = runtime
                            logger.info("Loaded unit %s into runtime registry during list_units", unit_id)
                        except Exception as exc:
                            logger.debug("Failed to create runtime for unit %s: %s", unit_id, exc)

            return list(units_by_id.values())
        except Exception as e:
            logger.error("Error listing units: %s", e, exc_info=True)
            return []

    def get_unit(self, unit_id: int) -> Optional[dict[str, Any]]:
        """
        Get unit details from cache or database.
        
        Args:
            unit_id: Unit identifier
            
        Returns:
            Unit dictionary or None
        """
        try:
            runtime = self._unit_runtimes.get(unit_id)
            if runtime:
                logger.debug("Fetched unit %s from runtime cache", unit_id)
                return runtime.to_dict()

            unit_data = self._unit_cache.get(unit_id)
            if unit_data is None:
                row = self.unit_repo.get_unit(unit_id)
                logger.debug("Fetched unit %s from database: %s", unit_id, row)
                unit_data = _row_to_dict(row)
                if unit_data is not None:
                    self._unit_cache.set(unit_id, unit_data)

            if not unit_data:
                return None

            try:
                runtime = self.factory.create_runtime(unit_data)
                with self._runtime_lock:
                    self._unit_runtimes[unit_id] = runtime
                logger.info("Loaded unit %s into registry", unit_id)
            except Exception as e:
                logger.error("Error creating runtime for unit %s: %s", unit_id, e, exc_info=True)

            return unit_data
        except Exception as e:
            logger.error(f"Error fetching unit {unit_id} from runtime cache: {e}", exc_info=True)

    def create_unit(
        self,
        *,
        name: str,
        location: str = "Indoor",
        user_id: Optional[int] = None,
        timezone: Optional[str] = None,
        dimensions: Optional[Dict[str, float]] = None,
        custom_image: Optional[str] = None,
        camera_enabled: bool = False
        ) -> Optional[int]:
        """
        Create a new growth unit.
        
        Args:
            name: Unit name
            location: Indoor/Outdoor/Greenhouse/Hydroponics
            user_id: Owner of the unit
            dimensions: Optional physical dimensions (e.g., {"width": 100, "height": 200, "depth": 50})
            custom_image: Optional custom image path
            camera_enabled: Enable camera for this unit
            
        Returns:
            Unit ID if successful, None otherwise
        """
        logger.info("Creating growth unit '%s' in location '%s'", name, location)
        try:
            normalized_dimensions = normalize_dimensions(dimensions) if dimensions else dimensions

            dimensions_json = dump_json_field(normalized_dimensions)
            
            # Default user_id to 1 if not provided
            if user_id is None:
                user_id = 1
            
            logger.debug("Calling repo.create_unit with user_id=%s", user_id)
            unit_id = self.unit_repo.create_unit(
                name=name, 
                location=location,
                user_id=user_id,
                timezone=timezone,
                dimensions=dimensions_json,
                custom_image=custom_image,
                camera_enabled=camera_enabled
            )
            logger.debug("repo.create_unit returned unit_id=%s", unit_id)
            
            if unit_id is None:
                logger.error("repo.create_unit returned None; raising RuntimeError")
                raise RuntimeError("Failed to create growth unit.")
            
            logger.debug("Creating unit runtime for unit_id=%s", unit_id)
            
            # Create unit runtime and start hardware
            unit_data = {
                "unit_id": unit_id,
                "name": name,
                "location": location,
                "user_id": user_id,
                "timezone": timezone,
                "custom_image": custom_image,
                "dimensions": normalized_dimensions,
                "camera_enabled": camera_enabled,
            }
            
            runtime = self.factory.create_runtime(unit_data)

            logger.debug("Runtime created for unit_id=%s; adding to _unit_runtimes", unit_id)
            with self._runtime_lock:
                self._unit_runtimes[unit_id] = runtime

            self._invalidate_unit_cache(unit_id)
            
            # Start hardware runtime
            logger.info(f"Starting hardware runtime for new unit {unit_id} ({name})")
            self.start_unit_runtime(unit_id)

            self._auto_apply_plant_stage_schedules(
                unit_id=unit_id,
                require_empty=True,
                reason="unit_creation",
            )
            
            self.audit_logger.log_event(
                actor="system",
                action="create",
                resource=f"growth_unit:{unit_id}",
                outcome="success",
                name=name,
                location=location,
            )
            
            logger.info("Growth unit created successfully with unit_id=%s", unit_id)
            return unit_id
            
        except Exception as e:
            logger.error(f"Error creating unit: {e}", exc_info=True)
            return None

    def update_unit(
        self,
        unit_id: int,
        *,
        name: Optional[str] = None,
        location: Optional[str] = None,
        dimensions: Optional[Dict[str, float]] = None,
        custom_image: Optional[str] = None,
        camera_enabled: bool = False,
        timezone: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Update unit information.
        
        Args:
            unit_id: Unit identifier
            name: New name
            location: New location
            dimensions: Physical dimensions
            custom_image: Custom image path
            camera_enabled: Enable camera for this unit
            
        Returns:
            Updated unit dictionary
        """
        normalized_dimensions = normalize_dimensions(dimensions) if dimensions is not None else None

        unit_data = {
            "unit_id": unit_id,
            "name": name,
            "location": location,
            "timezone": timezone,
            "custom_image": custom_image,
            "dimensions": dump_json_field(normalized_dimensions),
            "camera_enabled": camera_enabled
            }

        if unit_data is not None:
            self.unit_repo.update_unit(unit_id, **unit_data)
            
            # Update runtime if exists
            with self._runtime_lock:
                if unit_id in self._unit_runtimes:
                    runtime = self._unit_runtimes[unit_id]
                    if name:
                        runtime.unit_name = name
                    if location:
                        runtime.location = location
                    if normalized_dimensions is not None:
                        runtime.settings.dimensions = normalized_dimensions
                    if custom_image:
                        runtime.custom_image = custom_image
                    if timezone is not None:
                        runtime.settings.timezone = timezone
                    runtime.settings.camera_enabled = camera_enabled

            self._invalidate_unit_cache(unit_id)
            
            self.audit_logger.log_event(
                actor="system",
                action="update",
                resource=f"growth_unit:{unit_id}",
                outcome="success",
                **unit_data,
            )
        
        return self.get_unit(unit_id)

    def delete_unit(self, unit_id: int) -> None:
        """
        Delete a growth unit.
        
        Args:
            unit_id: Unit identifier
        """
        # Stop hardware runtime first
        logger.info(f"Stopping hardware runtime for unit {unit_id}")
        try:
            self.stop_unit_runtime(unit_id)
            self._invalidate_unit_cache(unit_id)

            # Delete from database
            self.unit_repo.delete_unit(unit_id)

            # Remove from registry if exists
            self._remove_unit_runtime(unit_id)

            self.audit_logger.log_event(
                actor="system",
                action="delete",
                resource=f"growth_unit:{unit_id}",
                outcome="success",
            )
        except Exception as e:
            logger.error(f"Error deleting unit {unit_id}: {e}", exc_info=True)

    # ==================== Unit Settings & Thresholds ====================
    def get_thresholds(self, unit_id: int) -> dict[str, Any]:
        """
        Get environmental thresholds and settings for a unit.
        
        Delegates threshold retrieval to ThresholdService (single source of truth),
        then adds non-threshold settings like dimensions, camera_enabled.
        
        Note: device_schedules and light_mode are no longer returned here.
        Use SchedulingService.get_schedules_for_unit() for schedule data.
        
        Args:
            unit_id: Unit identifier
            
        Returns:
            Dictionary of threshold values plus dimensions, camera_enabled
        """
        # Get thresholds from ThresholdService (single source of truth)
        thresholds: Dict[str, Any] = {}
        if self.threshold_service:
            thresholds = self.threshold_service.get_unit_thresholds_dict(unit_id)

        # Add non-threshold settings from runtime or unit data
        if unit_id in self._unit_runtimes:
            runtime = self._unit_runtimes[unit_id]
            settings = runtime.settings
            # Fallback to runtime settings if ThresholdService unavailable
            if not thresholds:
                thresholds = {
                    "temperature_threshold": settings.temperature_threshold,
                    "humidity_threshold": settings.humidity_threshold,
                    "co2_threshold": settings.co2_threshold,
                    "voc_threshold": settings.voc_threshold,
                    "lux_threshold": settings.lux_threshold,
                    "air_quality_threshold": settings.air_quality_threshold,
                }
            thresholds.update({
                "dimensions": settings.dimensions,
                "camera_enabled": settings.camera_enabled,
            })
            return thresholds

        # Fallback to unit data from DB
        unit = self.get_unit(unit_id)
        if not unit:
            return thresholds

        if not thresholds:
            thresholds = {
                "temperature_threshold": unit.get("temperature_threshold"),
                "humidity_threshold": unit.get("humidity_threshold"),
                "co2_threshold": unit.get("co2_threshold"),
                "voc_threshold": unit.get("voc_threshold"),
                "lux_threshold": unit.get("lux_threshold"),
                "air_quality_threshold": unit.get("air_quality_threshold", unit.get("aqi_threshold")),
            }

        thresholds.update({
            "dimensions": unit.get("dimensions"),
            "camera_enabled": unit.get("camera_enabled"),
        })
        return thresholds

    def set_thresholds(
        self,
        unit_id: int,
        *,
        temperature_threshold: Optional[float] = None,
        humidity_threshold: Optional[float] = None,
    ) -> Optional[dict[str, Any]]:
        """
        Set environmental thresholds for a unit.
        
        Delegates to ThresholdService for persistence, adds audit logging.
        
        Args:
            unit_id: Unit identifier
            temperature_threshold: Temperature threshold
            humidity_threshold: Humidity threshold
        Returns:
            Updated unit dictionary
        """
        updates = {}
        if temperature_threshold is not None:
            updates["temperature_threshold"] = temperature_threshold
        if humidity_threshold is not None:
            updates["humidity_threshold"] = humidity_threshold
        
        if updates:
            # Delegate to ThresholdService (single source of truth)
            if self.threshold_service:
                self.threshold_service.update_unit_thresholds(unit_id, updates)
            else:
                self.update_unit_thresholds(unit_id, updates)
        
        self.audit_logger.log_event(
            actor="system",
            action="update",
            resource=f"growth_unit:{unit_id}",
            outcome="success",
            temperature_threshold=temperature_threshold,
            humidity_threshold=humidity_threshold,
        )
        
        return self.get_unit(unit_id)

    def update_unit_settings(self, unit_id: int, settings: Any) -> bool:
        """
        Persist unit settings (thresholds, schedules, dimensions) and refresh runtime cache.

        Args:
            unit_id: Unit identifier.
            settings: UnitSettings instance or dict-like payload.
        """
        try:
            settings_dict = settings.to_dict() if hasattr(settings, "to_dict") else dict(settings)
        except Exception:
            settings_dict = {}

        if not settings_dict:
            logger.warning("update_unit_settings called with empty settings for unit %s", unit_id)
            return False

        threshold_payload = {
            key: settings_dict[key]
            for key in THRESHOLD_KEYS
            if key in settings_dict
        }
        if threshold_payload and self.threshold_service:
            current = self.threshold_service.get_unit_thresholds_dict(unit_id)
            changes: Dict[str, float] = {}
            for key, value in threshold_payload.items():
                if key not in current or current.get(key) != value:
                    changes[key] = value
            if changes:
                self.update_unit_thresholds(unit_id, changes)

        repo_payload = dict(settings_dict)
        if isinstance(repo_payload.get("device_schedules"), (dict, list)):
            repo_payload["device_schedules"] = dump_json_field(repo_payload["device_schedules"])
        if isinstance(repo_payload.get("dimensions"), (dict, list)):
            repo_payload["dimensions"] = dump_json_field(repo_payload["dimensions"])
        if self.threshold_service:
            for key in THRESHOLD_KEYS:
                repo_payload.pop(key, None)

        ok = self.unit_repo.update_unit_settings(unit_id, repo_payload)
        if ok:
            self._invalidate_unit_cache(unit_id)
            with self._runtime_lock:
                runtime = self._unit_runtimes.get(unit_id)
                if runtime and hasattr(runtime, "settings"):
                    # Keep runtime in sync with persisted settings (write-through).
                    if hasattr(settings, "device_schedules"):
                        runtime.settings.device_schedules = getattr(settings, "device_schedules")
                    elif "device_schedules" in settings_dict:
                        runtime.settings.device_schedules = settings_dict.get("device_schedules")

                    if hasattr(settings, "dimensions"):
                        runtime.settings.dimensions = getattr(settings, "dimensions")
                    elif "dimensions" in settings_dict:
                        runtime.settings.dimensions = settings_dict.get("dimensions")

                    if hasattr(settings, "camera_enabled"):
                        runtime.settings.camera_enabled = bool(getattr(settings, "camera_enabled"))
                    elif "camera_enabled" in settings_dict:
                        runtime.settings.camera_enabled = bool(settings_dict.get("camera_enabled"))

                    if hasattr(settings, "timezone"):
                        runtime.settings.timezone = getattr(settings, "timezone")
                    elif "timezone" in settings_dict:
                        runtime.settings.timezone = settings_dict.get("timezone")

                    if not self.threshold_service:
                        threshold_updates: Dict[str, float] = {}
                        for key in (
                            "temperature_threshold",
                            "humidity_threshold",
                            "co2_threshold",
                            "voc_threshold",
                            "lux_threshold",
                            "air_quality_threshold",
                        ):
                            if key in settings_dict:
                                threshold_updates[key] = settings_dict[key]
                        if threshold_updates and hasattr(runtime, "update_settings"):
                            runtime.update_settings(**threshold_updates)

        return ok

    # ==================== Private Helper Methods ====================

    def _remove_unit_runtime(self, unit_id: int) -> None:
        """
        Remove a UnitRuntime from the registry.
        
        Args:
            unit_id: Unit identifier
        """
        with self._runtime_lock:
            if unit_id in self._unit_runtimes:
                del self._unit_runtimes[unit_id]
                logger.info(f"Removed unit {unit_id} from runtime registry")
    
    def shutdown(self) -> None:
        """
        Shutdown all unit runtimes gracefully.
        
        Call this when the application is shutting down.
        """
        logger.info("Shutting down all unit runtimes...")
        
        with self._runtime_lock:
            unit_ids = list(self._unit_runtimes.keys())
        
        for unit_id in unit_ids:
            try:
                self.stop_unit_runtime(unit_id)
            except Exception as e:
                logger.error(f"Error stopping unit {unit_id} during shutdown: {e}")
        
        logger.info("All unit runtimes stopped")
