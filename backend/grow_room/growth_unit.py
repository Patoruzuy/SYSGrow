# Version: 2024.3
# Description: Manages multiple independent growth units.  
"""
GrowthUnitManager
=================

Manages multiple independent growth units.

Author: Sebastian Gomez
Date: 2024

Classes:
"""
from environment.sensor_polling_service import SensorPollingService
from environment.climate_controller import ClimateController
from devices.sensor_manager import SensorManager
from devices.actuator_controller import ActuatorController
from task_scheduler import TaskScheduler
from grow_room.plant_profile import PlantProfile
from utils.event_bus import EventBus
from ai.ml_model import AIClimateModel
from mqtt.mqtt_fcm_notifier import MQTTNotifier
from devices.camera_manager import CameraManager
import logging
import time
import threading

logging.basicConfig(level=logging.INFO, filename="growth_system.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class GrowthUnit:
    """
    Represents an independent growing environment (tent, greenhouse, grow room).

    Attributes:
        unit_id (int): Unique identifier for the unit.
        name (str): Name of the unit.
        location (str): Indoor or Outdoor.
        database_manager: Handles database operations.
        plants (dict): Dictionary of plants in the growth unit.
        sensors (SensorManager): Manages sensors.
        actuators (ActuatorController): Manages actuators.
        environment (ClimateController): Manages climate control.
        device_observers (dict): Observers for devices.
        task_scheduler (TaskScheduler): Schedules tasks.
        camera_manager (CameraManager): Manages cameras.
        event_bus (EventBus): Manages events.
        active_plant (PlantProfile): The active plant for climate control.
        self.is_db_sync_active (bool): Flag to enable/disable database sync.
        last_sync_time (float): Last sync time to the database.
        ai_model (AIClimateModel): AI model for climate control.
        growth_unit_settings (dict): Settings for the growth unit.
        plant_lock (threading.Lock): Lock for thread-safe access to the plants dictionary.
    """

    def __init__(self, unit_id, unit_name, location, redis_client, database_handler):
        """
        Initializes a single Growth Unit.

        Args:
            unit_id (int): Unique identifier for the unit.
            unit_name (str): Name of the unit.
            location (str): Indoor or Outdoor.
            database_handler: Handles database operations.
        """
        self.unit_id = unit_id
        self.unit_name = unit_name
        self.location = location
        self.redis_client = redis_client
        self.database_handler = database_handler
        self.plants = {}
        self.sensor_manager = SensorManager(self.unit_name, database_handler)
        self.actuator_manager = ActuatorController(self.unit_name, database_handler)
        self.polling_service = SensorPollingService(sensor_manager=self.sensor_manager, redis_client=self.redis_client)
        self.climate_controller = ClimateController(self.actuator_manager, self.polling_service, database_handler)
        self.device_observers = {}
        self.task_scheduler = TaskScheduler()
        self.camera_manager = CameraManager()
        self.event_bus = EventBus()
        self.active_plant = None
        self.is_db_sync_active = False
        self.last_sync_time = time.time()  
        self.ai_model = AIClimateModel()
        self.plant_lock = threading.Lock()

        # Load settings from database
        try:
            settings = database_handler.get_growth_unit(unit_id)
            self.growth_unit_settings = settings if settings else {
                "temperature_threshold": 24.0,
                "humidity_threshold": 50.0,
                "soil_moisture_threshold": 40.0,
                "co2_threshold": 1000.0,
                "voc_threshold": 1000.0,
                "light_intensity_threshold": 1000.0,
                "aqi_threshold": 1000.0,
                "light_start_time": "08:00",
                "light_end_time": "20:00"
            }
        except Exception as e:
            logging.error(f"Error loading growth unit settings for unit {unit_id}: {e}", exc_info=True)
            self.growth_unit_settings =  { # Provide default settings
                "temperature_threshold": 24.0,
                "humidity_threshold": 50.0,
                "soil_moisture_threshold": 40.0,
                "co2_threshold": 1000.0,
                "voc_threshold": 1000.0,
                "light_intensity_threshold": 1000.0,
                "aqi_threshold": 1000.0,
                "light_start_time": "08:00",
                "light_end_time": "20:00"
            }

        # Load plants from the database
        self._load_plants_from_db()
        logging.info(f"Growth Unit {unit_id} ({unit_name}) initialized.")
        self.event_bus.subscribe("plant_added", self.handle_plant_added)
        self.event_bus.subscribe("plant_removed", self.handle_plant_removed)
        self.event_bus.subscribe("plant_stage_update", self.apply_ai_conditions)
        self.event_bus.subscribe("device_linked", self.handle_device_linked)

        self.climate_controller.start() # Start the climate controller

    def save_growth_unit(self):
        """
        Saves the current growth unit settings to the database.
        """
        try:
            self.database_handler.insert_growth_unit(
                self.unit_name,
                self.location,
                self.active_plant.id if self.active_plant else None,
                self.growth_unit_settings["temperature_threshold"], 
                self.growth_unit_settings["humidity_threshold"], 
                self.growth_unit_settings["soil_moisture_threshold"],
                self.growth_unit_settings["co2_threshold"],
                self.growth_unit_settings["voc_threshold"],
                self.growth_unit_settings["light_intensity_threshold"],
                self.growth_unit_settings["aqi_threshold"],
                self.growth_unit_settings["light_start_time"], 
                self.growth_unit_settings["light_end_time"]
                )
            logging.info(f"Growth unit settings saved for unit ID {self.unit_id}")
        except Exception as e:
            logging.error(f"Error saving growth unit settings for unit ID {self.unit_id}: {e}", exc_info=True)

    def _get_growth_stages(self, plant_type):
        """
        Retrieves growth stages from dataset for a given plant species.
        
        Args:
            plant_type (str): Scientific name of the plant.

        Returns:
            dict: Growth stages if found.
        """
        from utils.plant_json_handler import PlantJsonHandler
        try:
            growth_stages = PlantJsonHandler().get_growth_stages(plant_type)
            return growth_stages
        except Exception as e:
            logging.error(f"Error getting growth stages for plant type {plant_type}: {e}", exc_info=True)
            return {}

    def _load_plants_from_db(self):
        """Loads all plant instances from the database into memory."""
        logging.info(f"🔄 Loading plants into Growth Unit {self.unit_id}...")
        try:
            plant_data_list = self.database_manager.get_all_plants_for_unit(self.unit_id)
            plant_sensors = self.database_manager.get_plant_sensors()
            sensor_map = {ps['sensor_id']: ps['plant_id'] for ps in plant_sensors}

            with self.plant_lock: # Use the lock
                for plant_data in plant_data_list:
                    plant_id = plant_data["plant_id"]
                    growth_stages = self._get_growth_stages(plant_data["plant_type"])
                    plant = PlantProfile(plant_id, plant_data["name"], plant_data["current_stage"], growth_stages, self.database_manager)
                    self._create_plant_observer(plant)
                    self.plants[plant.id] = plant
                    logging.info(f"✅ Loaded Plant {plant.name} (ID: {plant_id}) into Growth Unit {self.unit_id}.")
                    if plant_id in sensor_map:
                        plant.link_sensor(sensor_map['sensor_id'])
        except Exception as e:
            logging.error(f"Error loading plants from database for Growth Unit {self.unit_id}: {e}", exc_info=True)

    def add_plant(self, plant_name, plant_type, current_stage, growth_stages):
        """
        Adds a plant to the Growth Unit.

        Args:
            plant_name (str): The plant name.
            plant_type (str): The plant type.
            current_stage (str): The current growth stage of the plant.
            growth_stages (dict): The plant growth stages.
        """
        try:
            plant_id = self.database_manager.add_plant(plant_name, plant_type, current_stage)
            plant = PlantProfile(plant_id, plant_name, plant_type, current_stage, growth_stages, self.database_manager)
            self._create_plant_observer(plant)
            with self.plant_lock: # Use the lock
                self.plants[plant_id] = plant
            logging.info(f"Plant {plant.name} (ID: {plant_id}) added to Growth Unit {self.unit_id}.")
            self.event_bus.publish("plant_added", {"unit_id": self.unit_id, "plant_id": plant_id}) # Publish plant_added event
            return plant_id
        except Exception as e:
            logging.error(f"Error adding plant {plant_name} to Growth Unit {self.unit_id}: {e}", exc_info=True)
            return None

    def remove_plant(self, plant_id):
        """
        Removes a plant from this growth unit.

        Args:
            plant_id (int): The ID of the plant to remove.
        """
        try:
            with self.plant_lock:
                if plant_id in self.plants:
                    del self.plants[plant_id]
                    self.database_manager.remove_plant(plant_id)
                    logging.info(f"Removed Plant {plant_id} from Growth Unit {self.unit_id}.")
                    self.event_bus.publish("plant_removed", {"unit_id": self.unit_id, "plant_id": plant_id}) # Publish plant_removed event
                else:
                    logging.warning(f"Plant {plant_id} not found in this Growth Unit.")
        except Exception as e:
            logging.error(f"Error removing plant {plant_id} from Growth Unit {self.unit_id}: {e}", exc_info=True)

    def get_plant_by_id(self, plant_id):
        """
        Retrieves a plant by its ID.

        Args:
            plant_id (int): The ID of the plant.

        Returns:
            PlantProfile: The plant instance, or None if not found.
        """
        with self.plant_lock:
            return self.plants.get(plant_id)
        
    def get_plant_by_name(self, plant_name):
        """
        Retrieves a plant by its name.

        Args:
            plant_name (str): The name of the plant.

        Returns:
            PlantProfile: The plant instance, or None if not found.
        """
        with self.plant_lock:
            for plant in self.plants.values():
                if plant.plant_name == plant_name:
                    return plant
            return None

    def get_all_plants(self):
        """
        Retrieves all plants currently in the unit.

        Returns:
            list: A list of PlantProfile objects.
        """
        with self.plant_lock:
            return list(self.plants.values())

    def set_active_plant(self, plant_id):
        """
        Sets a plant as the `active_plant` for climate control.

        Args:
            plant_id (int): The plant ID to be set as active.
        """
        try:
            with self.plant_lock:
                if plant_id not in self.plants:
                    raise ValueError(f"Plant {plant_id} not found in Growth Unit {self.unit_id}!")

                self.active_plant = self.plants[plant_id]
            self.save_growth_unit()
            self.apply_ai_conditions()
            logging.info(f"🌿 Active plant set to {self.active_plant.name} in Growth Unit {self.unit_id}.")
            self.event_bus.publish("active_plant_changed", {"unit_id": self.unit_id, "plant_id": plant_id})
        except ValueError as ve:
            logging.error(f"Error setting active plant for Growth Unit {self.unit_id}: {ve}")
        except Exception as e:
            logging.error(f"Error setting active plant for Growth Unit {self.unit_id}: {e}", exc_info=True)

    def set_thresholds(self, temperature_threshold, humidity_threshold, soil_moisture_threshold=None):
        """
        Sets the thresholds for temperature, humidity, and soil moisture, then saves the settings.

        Args:
            temperature_threshold (float): The temperature threshold.
            humidity_threshold (float): The humidity threshold.
            soil_moisture_threshold (float, optional): The soil moisture threshold. Defaults to None.
        """
        try:
            self.growth_unit_settings['temperature_threshold'] = temperature_threshold
            self.growth_unit_settings['humidity_threshold'] = humidity_threshold
            self.growth_unit_settings['soil_moisture_threshold'] = soil_moisture_threshold
            self.save_growth_unit()
            logging.info(f"Thresholds set for Growth Unit {self.unit_id}: temp={temperature_threshold}, humidity={humidity_threshold}, soil={soil_moisture_threshold}")
            self.thresholds_update()
        except Exception as e:
            logging.error(f"Error setting thresholds for Growth Unit {self.unit_id}: {e}", exc_info=True)

    def _create_plant_observer(self, plant):
        """
        Attaches the plant to the timer observer and schedules its growth.

        Args:
            plant (Plant): The plant to be observed and scheduled.
        """
        try:
            observer = self.task_scheduler.PlantTimerObserver(plant)
            self.task_scheduler.attach(observer)
            self.task_scheduler.schedule_plant_growth(time_of_day="00:00")
            logging.info(f"Plant observer created for plant {plant.name} in Growth Unit {self.unit_id}")
        except Exception as e:
            logging.error(f"Error creating plant observer for Growth Unit {self.unit_id}: {e}", exc_info=True)
    
    def create_device_observer(self, actuator):
        """
        Creates the Fan and Light Observer if actuator are available.
        """
        try:
            device = self.actuator_manager.get_actuators().get(actuator)

            if device:
                self.device_observers[actuator] = self.task_scheduler.DeviceStateObserver(actuator, self.actuator_manager)
                self.task_scheduler.attach(self.device_observers[actuator])
                logging.info(f"Observer {actuator} created and attached to the timer.")
            else:
                logging.warning(f"No device found or observer already exists. '{actuator}' Observer not created.")
        except Exception as e:
            logging.error(f"Error creating device observer for Growth Unit {self.unit_id}: {e}", exc_info=True)

    def set_device_schedule(self, device_name, start_time, end_time):
        """
        Schedules the on/off times for any device (Light, Fan, Pump, etc.).

        Args:
            device_name (str): The name of the device to schedule.
            start_time (str): The start time for the schedule in 'HH:MM' format.
            end_time (str): The end time for the schedule in 'HH:MM' format.
        """
        try:
            # Ensure the observer exists for the device
            if device_name not in self.device_observers:
                self.create_device_observer(device_name)

            # Get the observer and schedule the task
            observer = self.device_observers.get(device_name)
            if observer:
                logging.info(f"Scheduling {device_name} from {start_time} to {end_time}.")

                self.task_scheduler.schedule_device(
                    device_name=device_name,
                    start_time=start_time,
                    end_time=end_time
                )

                # Save the growth unit settings after updating the schedule
                self.save_growth_unit()
                logging.info(f"{device_name} scheduled from {start_time} to {end_time}.")
            else:
                logging.warning(f"Cannot schedule {device_name}. No observer available.")
        except Exception as e:
            logging.error(f"Error setting device schedule for Growth Unit {self.unit_id}: {e}", exc_info=True)

    def apply_light_schedule(self):
        """
        Applies the light schedule to the growth unit.
        """
        self.set_device_schedule("Light", self.growth_unit_settings["light_start_time"], self.growth_unit_settings["light_end_time"])

    def start_camera(self):
        """
        A method to start the camera, delegating to the CameraManager.
        """
        self.camera_manager.start_camera()

    def stop_camera(self):
        """
        A method to stop the camera, delegating to the CameraManager.
        """
        self.camera_manager.stop_camera()
    
    def get_hotspot_settings(self):
        """
        Retrieves the current hotspot settings (SSID and password) from the database.

        Returns:
            dict: A dictionary containing the following keys:
                - 'ssid' (str): The SSID of the hotspot.
                - 'password' (str): The password of the hotspot.
        """
        try:
            hotspot_settings = self.database_manager.load_hotspot_settings()
            if hotspot_settings:
                return {
                    'ssid': hotspot_settings.get('ssid', 'default_ssid'),
                    'password': hotspot_settings.get('password', 'default_password')
                }
            else:
                # Return default values if settings are not found in the database
                return {'ssid': 'default_ssid', 'password': 'default_password'}
        except Exception as e:
            logging.error(f"Error getting hotspot settings for Growth Unit {self.unit_id}: {e}", exc_info=True)
            return {'ssid': 'default_ssid', 'password': 'default_password'} 

    def apply_ai_conditions(self):
        """
        Applies AI-based environmental conditions based on the active plant.
        """
        try:
            if not self.active_plant:
                logging.warning(f"No active plant set for Growth Unit {self.unit_id}. Cannot apply AI conditions.")
                return

            predictions = self.ai_model.predict_growth_conditions(self.active_plant.current_stage)

            # Apply AI-predicted settings
            self.growth_unit_settings["temperature_threshold"] = predictions["temperature"]
            self.growth_unit_settings["humidity_threshold"] = predictions["humidity"]
            self.growth_unit_settings["soil_moisture_threshold"] = predictions["soil_moisture"]
            self.save_growth_unit()
            self.thresholds_update()

            logging.info(f"AI Conditions Applied for Growth Unit {self.unit_id}: {predictions}")
        except Exception as e:
            logging.error(f"Error applying AI conditions for Growth Unit {self.unit_id}: {e}", exc_info=True)

    def sync_to_db(self, is_db_sync_active, interval=60):
        """
        Periodically syncs plant data to the database.

        Args:
            is_db_sync_active (bool): Flag to enable/disable database sync.
            interval (int): Sync interval in seconds.
        """
        self.is_db_sync_active = is_db_sync_active
        current_time = time.time()
        if current_time - self.last_sync_time > interval and is_db_sync_active:
            logging.info(f"🔄 Syncing Growth Unit {self.unit_id} plants to database...")
            try:
                with self.plant_lock: # Use the lock
                    for plant in self.plants.values():
                        plant.update_database()
                self.last_sync_time = current_time
                logging.info(f"✅ Database synced for Growth Unit {self.unit_id}.")
            except Exception as e:
                logging.error(f"Error syncing to database for Growth Unit {self.unit_id}: {e}", exc_info=True)

    def link_sensor(self, sensor_id):
        """
        Links a sensor to the unit.

        Args:
            sensor_id (int): Sensor ID.
        """
        try:
            self.sensor_manager.add_sensor(sensor_id)
            logging.info(f"📡 Sensor {sensor_id} linked to Growth Unit {self.unit_id}.")
            self.event_bus.publish("device_linked", {"unit_id": self.unit_id, "device_type": "sensor", "device_id": sensor_id}) # Publish device_linked
        except Exception as e:
            logging.error(f"Error linking sensor {sensor_id} to Growth Unit {self.unit_id}: {e}", exc_info=True)

    def link_actuator(self, actuator_id):
        """
        Links an actuator to the unit.

        Args:
            actuator_id (int): Actuator ID.
        """
        try:
            self.actuator_manager.add_actuator(actuator_id)
            logging.info(f"⚙️ Actuator {actuator_id} linked to Growth Unit {self.unit_id}.")
            self.event_bus.publish("device_linked", {"unit_id": self.unit_id, "device_type": "actuator", "device_id": actuator_id}) # Publish device_linked
        except Exception as e:
            logging.error(f"Error linking actuator {actuator_id} to Growth Unit {self.unit_id}: {e}", exc_info=True)

    def update_wifi_config(self, mqtt_topic, encrypted_payload):
        """
        Updates Wi-Fi credentials on the ESP32-C6 via MQTT.

        Args:
            mqtt_topic (str): mqtt topic for the module to be updated
            encrypted_payload (dict): The encrypted ssid and password
        """
        self.actuator_manager.update_wifi_credentials(mqtt_topic, encrypted_payload)

    def get_status(self):
        """
        Returns the current status of the growth unit.

        Returns:
            dict: Growth Unit details and active plant.
        """
        try:
            with self.plant_lock:
                return {
                    "unit_id": self.unit_id,
                    "name": self.unit_name,
                    "location": self.location,
                    "settings": self.growth_unit_settings,
                    "active_plant": self.active_plant.name if self.active_plant else None,
                    "plants": [plant.to_dict() for plant in self.plants.values()]
                }
        except Exception as e:
            logging.error(f"Error getting status of Growth Unit {self.unit_id}: {e}", exc_info=True)
            return {}
        
    def get_growth_unit_settings(self):
        """
        Returns the growth unit settings.

        Returns:
            dict: The growth unit settings.
        """
        return self.growth_unit_settings   
    
    def log_ai_decision(self):
        """
        Logs AI watering decisions to detect issues.
        """
        try:
            actual_readings = self.database_manager.get_latest_sensor_readings()
            actuator_triggered = self.database_manager.check_actuator_triggered("Water-Pump")

            self.database_manager.insert_ai_log(
                self.unit_id,
                self.growth_unit_settings["temperature_threshold"],
                self.growth_unit_settings["humidity_threshold"],
                self.growth_unit_settings["soil_moisture_threshold"],
                actual_readings["temperature"],
                actual_readings["humidity"],
                actual_readings["soil_moisture"],
                actual_readings["soil_moisture"],
                actuator_triggered
            )

            # Check if there are watering issues
            warning = self.ai_model.detect_watering_issues(self.unit_id)
            logging.warning(warning) if "⚠️" in warning or "🚨" in warning else logging.info(warning)
            return warning
        except Exception as e:
            logging.error(f"Error logging AI decision for Growth Unit {self.unit_id}: {e}", exc_info=True)
            return "Error logging AI decision"
        
    def thresholds_update(self):
        """
        Publishes an event to update the thresholds for the PID controllers.
        """
        try:
            thresholds = {
                "temperature": self.growth_unit_settings["temperature_threshold"],
                "humidity": self.growth_unit_settings["humidity_threshold"],
                "soil_moisture": self.growth_unit_settings["soil_moisture_threshold"],
            }
            self.event_bus.publish("thresholds_update", thresholds)  # Publish the event
            logging.info(f"Thresholds update event published for Growth Unit {self.unit_id}.")
        except Exception as e:
            logging.error(f"Error publishing thresholds update event for Growth Unit {self.unit_id}: {e}", exc_info=True)

    def handle_plant_added(self, data):
        """
        Handles the plant_added event.
        Args:
            data (dict): The event data.
        """
        if data["unit_id"] == self.unit_id:
            logging.info(f"Plant added to Growth Unit {self.unit_id}: Plant ID {data['plant_id']}")

    def handle_plant_removed(self, data):
        """
        Handles the plant_removed event.
        Args:
            data (dict): The event data.
        """
        if data["unit_id"] == self.unit_id:
            logging.info(f"Plant removed from Growth Unit {self.unit_id}: Plant ID {data['plant_id']}")
