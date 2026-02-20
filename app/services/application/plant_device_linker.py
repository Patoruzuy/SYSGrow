"""
Plant Device Linker
===================
Handles sensor and actuator linking/unlinking for plants.

Extracted from PlantViewService to reduce its scope (audit item #8).
PlantViewService delegates to this class for all device-linking operations.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.domain.actuators import ActuatorType
from app.hardware.compat.enums import app_to_infra_actuator_type

if TYPE_CHECKING:
    from app.services.hardware import SensorManagementService

logger = logging.getLogger(__name__)


class PlantDeviceLinker:
    """
    Manages the linking of sensors and actuators to plants.

    Responsibilities:
    - Sensor linking/unlinking with type validation
    - Actuator linking/unlinking with type + unit validation
    - Available sensors/actuators discovery with friendly names
    - Friendly name generation for UI display
    """

    def __init__(
        self,
        plant_repo: Any,
        sensor_service: "SensorManagementService",
        devices_repo: Any = None,
        audit_logger: Any = None,
    ):
        self.plant_repo = plant_repo
        self.sensor_service = sensor_service
        self.devices_repo = devices_repo
        self.audit_logger = audit_logger

    # ==================== Sensor Linking ====================

    def link_plant_sensor(self, plant_id: int, sensor_id: int, plant_profile: Any = None) -> bool:
        """
        Link a sensor to a plant with validation.

        Args:
            plant_id: Plant identifier
            sensor_id: Sensor identifier
            plant_profile: Optional PlantProfile to update in-memory state

        Returns:
            True if successful
        """
        try:
            sensor = self.sensor_service.get_sensor(sensor_id)
            if not sensor:
                logger.error("Sensor %s not found", sensor_id)
                return False

            sensor_type = str(sensor.get("sensor_type") or "").strip().lower()
            allowed_types = {"soil_moisture", "plant_sensor"}
            if sensor_type not in allowed_types:
                logger.error(
                    f"Sensor type '{sensor_type}' cannot be linked to plants. Allowed: {sorted(allowed_types)}"
                )
                return False

            self.plant_repo.link_sensor_to_plant(plant_id, sensor_id)

            if plant_profile:
                plant_profile.link_sensor(sensor_id)
                logger.info("Linked sensor %s to plant %s in memory", sensor_id, plant_id)

            if self.audit_logger:
                self.audit_logger.log_event(
                    actor="system",
                    action="link",
                    resource=f"plant:{plant_id}",
                    outcome="success",
                    sensor_id=sensor_id,
                )

            logger.info("Linked sensor %s (%s) to plant %s", sensor_id, sensor_type, plant_id)
            return True

        except Exception as e:
            logger.error("Error linking sensor %s to plant %s: %s", sensor_id, plant_id, e, exc_info=True)
            return False

    def unlink_plant_sensor(self, plant_id: int, sensor_id: int, plant_profile: Any = None) -> bool:
        """
        Unlink a sensor from a plant.

        Args:
            plant_id: Plant identifier
            sensor_id: Sensor identifier
            plant_profile: Optional PlantProfile to update in-memory state

        Returns:
            True if successful
        """
        try:
            self.plant_repo.unlink_sensor_from_plant(plant_id, sensor_id)

            if plant_profile and plant_profile.get_sensor_id() == sensor_id:
                plant_profile.link_sensor(None)
                logger.info("Unlinked sensor %s from plant %s in memory", sensor_id, plant_id)

            if self.audit_logger:
                self.audit_logger.log_event(
                    actor="system",
                    action="unlink",
                    resource=f"plant:{plant_id}",
                    outcome="success",
                    sensor_id=sensor_id,
                )

            logger.info("Unlinked sensor %s from plant %s", sensor_id, plant_id)
            return True

        except Exception as e:
            logger.error("Error unlinking sensor %s from plant %s: %s", sensor_id, plant_id, e, exc_info=True)
            return False

    def unlink_all_sensors_from_plant(self, plant_id: int) -> bool:
        """
        Unlink all sensors from a plant.
        Best-effort cleanup operation, typically called before plant deletion.

        Args:
            plant_id: Plant identifier

        Returns:
            True if successful, False otherwise
        """
        try:
            self.plant_repo.unlink_all_sensors_from_plant(plant_id)
            logger.info("Unlinked all sensors from plant %s", plant_id)
            return True
        except Exception as e:
            logger.debug("Failed to unlink all sensors from plant %s: %s", plant_id, e, exc_info=True)
            return False

    def get_plant_sensor_ids(self, plant_id: int) -> list[int]:
        """
        Get sensor IDs linked to a plant.

        Args:
            plant_id: Plant identifier

        Returns:
            List of sensor IDs
        """
        try:
            return self.plant_repo.get_sensors_for_plant(plant_id)
        except Exception as e:
            logger.error("Error getting sensors for plant %s: %s", plant_id, e, exc_info=True)
            return []

    def get_plant_sensors(self, plant_id: int) -> list[dict[str, Any]]:
        """
        Get full sensor details for all sensors linked to a plant.

        Args:
            plant_id: Plant identifier

        Returns:
            List of sensor dictionaries with friendly names
        """
        try:
            sensor_ids = self.get_plant_sensor_ids(plant_id)
            if not sensor_ids:
                return []

            # Batch fetch — single query instead of N+1
            if self.devices_repo and hasattr(self.devices_repo, "get_sensors_by_ids"):
                batch = self.devices_repo.get_sensors_by_ids(sensor_ids)
                sensors = []
                for sid in sensor_ids:
                    sensor = batch.get(sid)
                    if sensor:
                        sensor["friendly_name"] = self._generate_friendly_name(sensor)
                        sensors.append(sensor)
                return sensors

            # Fallback: individual reads
            sensors = []
            for sensor_id in sensor_ids:
                sensor = self.sensor_service.get_sensor(sensor_id)
                if sensor:
                    sensor["friendly_name"] = self._generate_friendly_name(sensor)
                    sensors.append(sensor)
            return sensors

        except Exception as e:
            logger.error("Error getting sensor details for plant %s: %s", plant_id, e, exc_info=True)
            return []

    # ==================== Actuator Linking ====================

    @staticmethod
    def _normalize_actuator_type(value: Any) -> ActuatorType:
        """Normalize actuator type values to infrastructure ActuatorType."""
        actuator_type = app_to_infra_actuator_type(value)
        if actuator_type != ActuatorType.UNKNOWN:
            return actuator_type
        text = str(value or "").strip().lower().replace("-", "_")
        if text in {"water_pump", "waterpump"}:
            return ActuatorType.PUMP
        return ActuatorType.UNKNOWN

    def link_plant_actuator(
        self,
        plant_id: int,
        actuator_id: int,
        get_plant_fn: Any = None,
    ) -> bool:
        """
        Link an actuator to a plant (e.g., dedicated irrigation pump).

        Args:
            plant_id: Plant identifier
            actuator_id: Actuator identifier
            get_plant_fn: Callable to resolve plant by ID (injected by PlantViewService)

        Returns:
            True if successful
        """
        try:
            plant = get_plant_fn(plant_id) if get_plant_fn else None
            if not plant:
                logger.error("Plant %s not found", plant_id)
                return False

            actuator = None
            if self.devices_repo:
                actuator = self.devices_repo.get_actuator_config_by_id(actuator_id)

            if not actuator:
                logger.error("Actuator %s not found", actuator_id)
                return False

            plant_unit_id = plant.unit_id
            actuator_unit_id = actuator.get("unit_id")
            if plant_unit_id and actuator_unit_id and int(plant_unit_id) != int(actuator_unit_id):
                logger.error("Actuator %s does not belong to unit %s", actuator_id, plant_unit_id)
                return False

            actuator_type = self._normalize_actuator_type(actuator.get("actuator_type"))
            if actuator_type not in {ActuatorType.PUMP, ActuatorType.VALVE}:
                logger.error(
                    "Actuator %s is not a pump or valve (type=%s)",
                    actuator_id,
                    actuator.get("actuator_type") or "unknown",
                )
                return False

            self.plant_repo.link_actuator_to_plant(plant_id, actuator_id)
            logger.info("Linked actuator %s to plant %s", actuator_id, plant_id)
            return True
        except Exception as e:
            logger.error("Error linking actuator %s to plant %s: %s", actuator_id, plant_id, e, exc_info=True)
            return False

    def unlink_plant_actuator(self, plant_id: int, actuator_id: int) -> bool:
        """Unlink an actuator from a plant."""
        try:
            self.plant_repo.unlink_actuator_from_plant(plant_id, actuator_id)
            logger.info("Unlinked actuator %s from plant %s", actuator_id, plant_id)
            return True
        except Exception as e:
            logger.error("Error unlinking actuator %s from plant %s: %s", actuator_id, plant_id, e, exc_info=True)
            return False

    def get_plant_actuator_ids(self, plant_id: int) -> list[int]:
        """Get actuator IDs linked to a plant."""
        try:
            return self.plant_repo.get_actuators_for_plant(plant_id)
        except Exception as e:
            logger.error("Error getting actuators for plant %s: %s", plant_id, e, exc_info=True)
            return []

    def get_plant_actuators(self, plant_id: int) -> list[dict[str, Any]]:
        """Get actuator details linked to a plant."""
        try:
            actuator_ids = self.get_plant_actuator_ids(plant_id)
            if not actuator_ids or not self.devices_repo:
                return []

            # Batch fetch — single query instead of N+1
            if hasattr(self.devices_repo, "get_actuators_by_ids"):
                batch = self.devices_repo.get_actuators_by_ids(actuator_ids)
                return [batch[aid] for aid in actuator_ids if aid in batch]

            # Fallback: individual reads
            actuators: list[dict[str, Any]] = []
            for actuator_id in actuator_ids:
                actuator = self.devices_repo.get_actuator_config_by_id(actuator_id)
                if actuator:
                    actuators.append(actuator)
            return actuators
        except Exception as e:
            logger.error("Error getting actuator details for plant %s: %s", plant_id, e, exc_info=True)
            return []

    def get_available_actuators_for_plant(
        self,
        unit_id: int,
        actuator_type: str = "pump",
    ) -> list[dict[str, Any]]:
        """List available actuators for linking to plants."""
        try:
            if not self.devices_repo:
                return []
            actuators = self.devices_repo.list_actuator_configs(unit_id=unit_id)
            normalized_type = self._normalize_actuator_type(actuator_type)
            if normalized_type == ActuatorType.UNKNOWN:
                return actuators

            filtered: list[dict[str, Any]] = []
            for actuator in actuators:
                candidate_type = self._normalize_actuator_type(actuator.get("actuator_type"))
                if candidate_type == normalized_type:
                    filtered.append(actuator)
            return filtered
        except Exception as e:
            logger.error("Error getting available actuators for unit %s: %s", unit_id, e, exc_info=True)
            return []

    # ==================== Available Sensors Discovery ====================

    def get_available_sensors_for_plant(
        self,
        unit_id: int,
        sensor_type: str = "soil_moisture",
    ) -> list[dict[str, Any]]:
        """
        Get all sensors available for plant linking with friendly names.

        Args:
            unit_id: Unit identifier
            sensor_type: Type of sensor to filter (default: SOIL_MOISTURE)

        Returns:
            List of sensors with friendly names and availability status
        """
        try:
            sensors = self.sensor_service.list_sensors(unit_id=unit_id)

            available = []
            for sensor in sensors:
                if str(sensor.get("sensor_type") or "").strip().lower() == str(sensor_type).strip().lower():
                    friendly_name = self._generate_friendly_name(sensor)
                    is_linked = self._is_sensor_linked(sensor.get("sensor_id"))

                    available.append(
                        {
                            "sensor_id": sensor["sensor_id"],
                            "name": friendly_name,
                            "sensor_type": sensor.get("sensor_type"),
                            "protocol": sensor.get("protocol", "GPIO"),
                            "model": sensor.get("model", "Unknown"),
                            "is_linked": is_linked,
                            "enabled": sensor.get("is_active", True),
                        }
                    )

            logger.debug("Found %s available %s sensors for unit %s", len(available), sensor_type, unit_id)
            return available

        except Exception as e:
            logger.error("Error getting available sensors for unit %s: %s", unit_id, e, exc_info=True)
            return []

    # ==================== Actuator Resolution (for plant context) ====================

    def resolve_plant_actuator(self, plant_id: int) -> tuple:
        """
        Resolve actuator (pump) assignment for a plant.

        Returns:
            Tuple of (actuator_id, plant_pump_assigned)
        """
        try:
            actuator_ids = self.plant_repo.get_actuators_for_plant(plant_id)
        except Exception as exc:
            logger.debug("Failed to resolve actuators for plant %s: %s", plant_id, exc, exc_info=True)
            return None, False

        if not actuator_ids:
            return None, False

        actuator_id = None
        if self.devices_repo:
            for candidate in actuator_ids:
                actuator = self.devices_repo.get_actuator_config_by_id(candidate)
                if not actuator:
                    continue
                actuator_type = self._normalize_actuator_type(actuator.get("actuator_type"))
                if actuator_type == ActuatorType.PUMP:
                    actuator_id = candidate
                    break

        if actuator_id is None:
            return None, False

        return actuator_id, True

    def resolve_unit_pump_actuator(self, unit_id: int) -> int | None:
        """Resolve a unit-level pump actuator if no plant-specific pump is set."""
        if not self.devices_repo:
            return None
        try:
            actuators = self.devices_repo.list_actuator_configs(unit_id=unit_id)
        except Exception as exc:
            logger.debug("Failed to list actuators for unit %s: %s", unit_id, exc, exc_info=True)
            return None

        for actuator in actuators or []:
            actuator_type = self._normalize_actuator_type(actuator.get("actuator_type"))
            if actuator_type == ActuatorType.PUMP:
                actuator_id = actuator.get("actuator_id")
                if actuator_id is not None:
                    return int(actuator_id)
        return None

    def get_plant_valve_actuator_id(self, plant_id: int) -> int | None:
        """Resolve a valve actuator linked to a plant, if any."""
        try:
            actuator_ids = self.plant_repo.get_actuators_for_plant(plant_id)
        except Exception as exc:
            logger.debug("Failed to resolve actuators for plant %s: %s", plant_id, exc, exc_info=True)
            return None

        if not actuator_ids or not self.devices_repo:
            return None

        for candidate in actuator_ids:
            actuator = self.devices_repo.get_actuator_config_by_id(candidate)
            if not actuator:
                continue
            actuator_type = self._normalize_actuator_type(actuator.get("actuator_type"))
            if actuator_type == ActuatorType.VALVE:
                return candidate
        return None

    # ==================== Private Helpers ====================

    @staticmethod
    def _generate_friendly_name(sensor: dict[str, Any]) -> str:
        """
        Generate a user-friendly sensor name.

        Examples:
        - "Soil Moisture (GPIO Pin 17)"
        - "Soil Moisture (MQTT: growtent/sensor/soil_0)"
        - "Soil Moisture (ESP32-C6: grow-sensor-01)"
        """
        try:
            sensor_type = sensor.get("sensor_type", "UNKNOWN")
            base_name = sensor_type.replace("_", " ").title()

            protocol = str(sensor.get("protocol", "GPIO") or "GPIO")
            config_data = sensor.get("config", {}) or {}

            if protocol.upper() == "GPIO":
                gpio = config_data.get("gpio_pin")
                if gpio is None:
                    gpio = config_data.get("gpio")
                if gpio is not None:
                    return f"{base_name} (GPIO Pin {gpio})"
                else:
                    return f"{base_name} (GPIO)"

            elif protocol.lower() in ("mqtt", "zigbee2mqtt", "zigbee"):
                mqtt_topic = config_data.get("mqtt_topic", "unknown")
                device_id = config_data.get("esp32_device_id") or config_data.get("device_id")

                if device_id:
                    return f"{base_name} (ESP32-C6: {device_id})"
                else:
                    topic_parts = mqtt_topic.split("/")
                    short_topic = "/".join(topic_parts[-2:]) if len(topic_parts) > 2 else mqtt_topic
                    return f"{base_name} (MQTT: {short_topic})"

            elif protocol == "WIRELESS":
                address = config_data.get("address", "unknown")
                return f"{base_name} (Wireless: {address})"

            else:
                sensor_id = sensor.get("sensor_id")
                return f"{base_name} (ID: {sensor_id})"

        except Exception as e:
            logger.warning("Error generating friendly name: %s", e)
            return f"Sensor #{sensor.get('sensor_id', 'unknown')}"

    @staticmethod
    def _is_sensor_linked(sensor_id: int) -> bool:
        """
        Check if a sensor is already linked to any plant.

        Note: Currently returns False (allows sensor sharing).
        TODO: Implement actual database check if exclusive linking is needed.
        """
        try:
            return False
        except Exception as e:
            logger.warning("Error checking if sensor %s is linked: %s", sensor_id, e)
            return False
