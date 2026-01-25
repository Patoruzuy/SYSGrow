"""
ClimateController: Manages all environmental factors in the grow tent.

Author: Sebastian Gomez
Date: 2024
"""

import logging
from typing import Any, Dict
from datetime import datetime, timedelta
from utils.event_bus import EventBus
from environment.control_logic import ControlLogic


class ClimateController:
    """
    ClimateController manages environmental factors in the grow tent by:
    - Subscribing to sensor updates from EventBus
    - Emitting commands to actuators based on readings
    - Logging and tracking environmental changes
    """

    def __init__(self, actuator_manager: Any, polling_service: Any, database_handler: Any):
        """
        Initializes the ClimateController.

        Args:
            actuator_manager: Responsible for controlling actuators.
            database_handler: For storing sensor history.
        """
        self.event_bus = EventBus()
        self.actuator_manager = actuator_manager
        self.polling_service = polling_service
        self.control_logic = ControlLogic(self.actuator_manager)
        self.database_handler = database_handler
        self.last_temp_humidity_insert = None
        self.last_soil_moisture_insert = None
        self.insert_interval
        self.insert_interval = timedelta(minutes=30)

        # Subscribe to relevant sensor update events
        self.event_bus.subscribe("temperature_update", self.on_temperature_update)
        self.event_bus.subscribe("humidity_update", self.on_humidity_update)
        self.event_bus.subscribe("soil_moisture_update", self.on_soil_moisture_update)
        self.event_bus.subscribe("co2_update", self.on_co2_update)
        self.event_bus.subscribe("voc_update", self.on_voc_update)

        logging.info("🌿 ClimateController initialized and listening to EventBus.")

    def on_temperature_update(self, data: Dict[str, Any]) -> None:
        temperature = data.get("temperature")
        unit_id = data.get("unit_id")
        if temperature is not None:
            self.control_logic.control_temperature({"unit_id": unit_id, "temperature": temperature})
            self._log_temp_humidity_data(data)

    def on_humidity_update(self, data: Dict[str, Any]) -> None:
        humidity = data.get("humidity")
        unit_id = data.get("unit_id")
        if humidity is not None:
            self.control_logic.control_humidity({"unit_id": unit_id, "humidity": humidity})
            self._log_temp_humidity_data(data)

    def on_soil_moisture_update(self, data: Dict[str, Any]) -> None:
        moisture = data.get("moisture_level") or data.get("soil_moisture")
        unit_id = data.get("unit_id")
        sendor_id = data.get("sensor_id")
        self.event_bus.publish("moisture_level_updated", {"unit_id": unit_id, 'sensor_id': sendor_id, "soil_moisture": moisture})
        if moisture is not None:
            self.control_logic.control_soil_moisture({"unit_id": unit_id, "moisture_level": moisture})
            # Optionally insert moisture history here
            logging.info(f"🌱 Soil moisture reading: {moisture} (Unit: {unit_id})")

    def on_co2_update(self, data: Dict[str, Any]) -> None:
        co2 = data.get("co2")
        unit_id = data.get("unit_id")
        if co2 is not None:
            logging.info(f"🌬️ CO2 reading: {co2} (Unit: {unit_id})")

    def on_voc_update(self, data: Dict[str, Any]) -> None:
        voc = data.get("voc")
        unit_id = data.get("unit_id")
        if voc is not None:
            logging.info(f"🧪 VOC reading: {voc} (Unit: {unit_id})")

    def _log_temp_humidity_data(self, data: Dict[str, Any]) -> None:
        """
        Store temperature and humidity in DB every 30 minutes.
        """
        current_time = datetime.now()
        if (self.last_temp_humidity_insert is None or
                current_time - self.last_temp_humidity_insert >= self.insert_interval):
            temperature = data.get("temperature")
            humidity = data.get("humidity")
            if temperature is not None and humidity is not None:
                self.database_handler.insert_sensor_data(temperature=temperature, humidity=humidity)
                logging.info(f"📝 Logged temperature: {temperature}, humidity: {humidity} at {current_time}")
                self.last_temp_humidity_insert = current_time

    def _log_co2_voc_data(self, data: Dict[str, Any]) -> None:
        """
        Store CO2 and VOC in DB every 30 minutes.
        """
        current_time = datetime.now()
        if (self.last_temp_humidity_insert is None or
                current_time - self.last_temp_humidity_insert >= self.insert_interval):
            co2 = data.get("co2")
            voc = data.get("voc")
            if co2 is not None and voc is not None:
                self.database_handler.insert_sensor_data(co2=co2, voc=voc)
                logging.info(f"📝 Logged CO2: {co2}, VOC: {voc} at {current_time}")
                self.last_temp_humidity_insert = current_time
    
    def _log_soil_moisture_data(self, data: Dict[str, Any]) -> None:
        """
        Store soil moisture in DB every 30 minutes.
        """
        current_time = datetime.now()
        current_moisture = data.get("moisture_level") or data.get("soil_moisture")
        sensor_id = data.get("sensor_id")
        if self.last_soil_moisture_insert is None or (self.last_soil_moisture_insert != 0 and
         abs(current_moisture - self.last_soil_moisture_insert) / self.last_soil_moisture_insert * 100 >= self.insert_soil_interval):
            moisture = data.get("moisture_level") or data.get("soil_moisture")
            if moisture is not None:
                self.database_handler.insert_soil_moisture_history(sensor_id, current_moisture)
                logging.info(f"📝 Logged soil moisture: {moisture} at {current_time}")
                self.last_soil_insert = current_time

    def start(self):
        """
        Starts the polling service for all sensors.
        MQTT automatically handles incoming updates and reload triggers.
        """
        self.polling_service.start_polling()


