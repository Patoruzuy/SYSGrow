# utils/event_logger.py
import logging

from app.enums.events import ActivityEvent, DeviceEvent, PlantEvent, RuntimeEvent, SensorEvent
from app.utils.event_bus import EventBus


class EventLogger:
    """Listens for events and logs them."""

    def __init__(self):
        self.event_bus = EventBus()

        # Configure logging
        logging.basicConfig(
            filename="grow_tent.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )

        # Subscribe to relevant events (prefer enums; keep legacy dynamic where needed)
        self.event_bus.subscribe(SensorEvent.TEMPERATURE_UPDATE, self.log_temperature)
        self.event_bus.subscribe(SensorEvent.HUMIDITY_UPDATE, self.log_humidity)
        self.event_bus.subscribe(SensorEvent.SOIL_MOISTURE_UPDATE, self.log_soil_moisture)
        self.event_bus.subscribe("activate_actuator", self.log_actuator_activation)
        self.event_bus.subscribe("deactivate_actuator", self.log_actuator_deactivation)
        # Legacy alias and canonical topic
        self.event_bus.subscribe("update_plant_stage", self.log_plant_stage)
        self.event_bus.subscribe(PlantEvent.PLANT_STAGE_UPDATE, self.log_plant_stage)
        self.event_bus.subscribe(PlantEvent.GROWTH_WARNING, self.log_growth_warning)
        # Additional subscribers to cover gaps
        self.event_bus.subscribe(DeviceEvent.RELAY_STATE_CHANGED, self.log_relay_state)
        self.event_bus.subscribe(DeviceEvent.DEVICE_COMMAND, self.log_device_command)
        self.event_bus.subscribe(DeviceEvent.CONNECTIVITY_CHANGED, self.log_connectivity)
        self.event_bus.subscribe(PlantEvent.ACTIVE_PLANT_CHANGED, self.log_active_plant_changed)
        self.event_bus.subscribe(RuntimeEvent.SENSOR_RELOAD, self.log_sensor_reload)

        # Subscribe to activity events (new)
        self.event_bus.subscribe(ActivityEvent.PLANT_ADDED, self.log_activity_event)
        self.event_bus.subscribe(ActivityEvent.PLANT_REMOVED, self.log_activity_event)
        self.event_bus.subscribe(ActivityEvent.UNIT_CREATED, self.log_activity_event)
        self.event_bus.subscribe(ActivityEvent.DEVICE_CONNECTED, self.log_activity_event)
        self.event_bus.subscribe(ActivityEvent.HARVEST_RECORDED, self.log_activity_event)
        self.event_bus.subscribe(ActivityEvent.SYSTEM_STARTUP, self.log_activity_event)
        self.event_bus.subscribe(ActivityEvent.SYSTEM_SHUTDOWN, self.log_activity_event)

    def log_temperature(self, data):
        logging.info(f"🌡️ Temperature updated: {data['temperature']}°C")

    def log_humidity(self, data):
        logging.info(f"💧 Humidity updated: {data['humidity']}%")

    def log_soil_moisture(self, data):
        try:
            moisture = data.get("soil_moisture") if isinstance(data, dict) else None
            if moisture is None and isinstance(data, dict):
                moisture = data.get("moisture_level")
            plant_or_sensor = None
            if isinstance(data, dict):
                plant_or_sensor = data.get("plant_id") or data.get("sensor_id")
            logging.info(f"🌱 Soil moisture for Plant/Sensor {plant_or_sensor}: {moisture}%")
        except Exception:
            logging.info("🌱 Soil moisture update received")

    def log_actuator_activation(self, data):
        logging.info(f"⚡ Actuator activated: {data['actuator']}")

    def log_actuator_deactivation(self, data):
        logging.info(f"🛑 Actuator deactivated: {data['actuator']}")

    def log_plant_stage(self, data):
        logging.info(f"🌿 Plant {data['plant_id']} advanced to {data['new_stage']} stage")

    def log_growth_warning(self, data):
        try:
            plant_id = data.get("plant_id")
            stage = data.get("stage")
            message = data.get("message")
            logging.warning(f"⚠️ Growth warning for plant {plant_id} at stage {stage}: {message}")
        except Exception:
            logging.warning(f"⚠️ Growth warning event: {data}")

    def log_relay_state(self, data):
        try:
            device = data.get("device")
            state = data.get("state")
            logging.info(f"🔁 Relay '{device}' state → {state}")
        except Exception:
            logging.info("🔁 Relay state changed (payload unavailable)")

    def log_device_command(self, data):
        try:
            logging.info(f"📣 Device command: {data}")
        except Exception:
            logging.info("📣 Device command issued")

    def log_active_plant_changed(self, data):
        try:
            logging.info(f"🌱 Active plant changed: {data}")
        except Exception:
            logging.info("🌱 Active plant changed")

    def log_sensor_reload(self, data):
        try:
            logging.info(f"🔄 Sensor reload requested: {data}")
        except Exception:
            logging.info("🔄 Sensor reload requested")

    def log_connectivity(self, data):
        try:
            ctype = data.get("connection_type")
            status = data.get("status") or ("connected" if data.get("connected") else "disconnected")
            endpoint = data.get("endpoint") or data.get("broker")
            logging.info(f"📡 Connectivity ({ctype}) → {status} [{endpoint}]")
        except Exception:
            logging.info("📡 Connectivity event")

    def log_activity_event(self, data):
        """Log activity events from ActivityLogger."""
        try:
            activity_type = data.get("activity_type", "").replace("_", " ").title()
            description = data.get("description", "")
            severity = data.get("severity", "info")

            emoji_map = {
                "plant_added": "🌱",
                "plant_removed": "🗑️",
                "unit_created": "🏠",
                "device_connected": "🔌",
                "harvest_recorded": "🌾",
                "system_startup": "🚀",
                "system_shutdown": "🛑",
            }

            emoji = emoji_map.get(data.get("activity_type"), "📝")
            log_msg = f"{emoji} {activity_type}: {description}"

            if severity == "error":
                logging.error(log_msg)
            elif severity == "warning":
                logging.warning(log_msg)
            else:
                logging.info(log_msg)
        except Exception:
            logging.info(f"📝 Activity event: {data}")


# Initialize logger
EventLogger()
