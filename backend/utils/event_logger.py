# utils/event_logger.py
import logging
from utils.event_bus import EventBus

class EventLogger:
    """Listens for events and logs them."""

    def __init__(self):
        self.event_bus = EventBus()

        # Configure logging
        logging.basicConfig(
            filename="grow_tent.log",
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )

        # Subscribe to relevant events
        self.event_bus.subscribe("temperature_update", self.log_temperature)
        self.event_bus.subscribe("humidity_update", self.log_humidity)
        self.event_bus.subscribe("soil_moisture_update", self.log_soil_moisture)
        self.event_bus.subscribe("activate_actuator", self.log_actuator_activation)
        self.event_bus.subscribe("deactivate_actuator", self.log_actuator_deactivation)
        self.event_bus.subscribe("update_plant_stage", self.log_plant_stage)

    def log_temperature(self, data):
        logging.info(f"🌡️ Temperature updated: {data['temperature']}°C")

    def log_humidity(self, data):
        logging.info(f"💧 Humidity updated: {data['humidity']}%")

    def log_soil_moisture(self, data):
        logging.info(f"🌱 Soil moisture for Plant {data['plant_id']}: {data['moisture_level']}%")

    def log_actuator_activation(self, data):
        logging.info(f"⚡ Actuator activated: {data['actuator']}")

    def log_actuator_deactivation(self, data):
        logging.info(f"🛑 Actuator deactivated: {data['actuator']}")

    def log_plant_stage(self, data):
        logging.info(f"🌿 Plant {data['plant_id']} advanced to {data['new_stage']} stage")

# Initialize logger
EventLogger()
