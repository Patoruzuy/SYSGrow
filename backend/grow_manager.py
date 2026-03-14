"""
Description: This script defines the GrowthEnvironment class for managing agricultural setups (greenhouses, vertical farms, etc.),
including environmental monitoring and control mechanisms.

Author: Sebastian Gomez
Date: 26/05/2024
"""

from task_scheduler import *
import logging
from growth_environment import GrowthEnvironment
from plant_profile import *
from sensor_manager import SensorManager
from flask import current_app
from actuator_controller import *
from control_algorithms import PIDController
from config_defaults import SystemConfigDefaults
from camera_manager import CameraManager

class GrowthEnvironment:
    """
    Manages the growth of plants in a tent, including monitoring environmental conditions and controlling devices.

    Attributes:
        database_manager (DatabaseManager): The database manager for storing data.
        tent (Tent): The grow tent.
        timer (Timer): The timer for scheduling tasks.
        fan (Fan): The fan for temperature control.
        water_spray (WaterSpray): The water spray for humidity control.
        sensor (Sensor): The sensor for reading environmental data.
        temperature_threshold (float): The temperature threshold for triggering the fan.
        humidity_threshold (float): The humidity threshold for triggering the water spray.
        soil_moisture_threshold (float): The soil moisture threshold for triggering the water spray.
        hysteresis (integer): hysteresis helps to prevent rapid on/off cycling of a system component.
        load_setting (DatabaseManager): The database manager for saving and loading settings.
    """
    def __init__(self, database_manager):
        """Initializes the GrowthManager with default settings and attaches the sensor."""
        self.database_manager = database_manager
        self.tent = GrowthEnvironment(database_manager)
        self.task_scheduler = TaskScheduler()
        self.light_observer = None
        self.fan_observer = None
        self.plant_observer = {}
        self.actuator_controller = ActuatorController(database_manager)
        self.sensor_manager = SensorManager(database_manager)
        self.camera_manager = CameraManager(database_manager)
        self.temperature_threshold = 24
        self.humidity_threshold = 40
        self.soil_moisture_threshold = 50
        self.temp_pid = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=self.temperature_threshold)
        self.humidity_pid = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=self.humidity_threshold)
        self.soil_moisture_pid = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=self.soil_moisture_threshold)
        self.co2_pid = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=22.0)
        #self.controller = MLController(model=your_model, setpoint=22.0)
        self.light_start_time = "08:00"
        self.light_end_time = "20:00"
        self.fan_start_time = "08:00"
        self.fan_end_time = "20:00"
        self.last_temp_humidity_insert = None  # Initialize to store the last insert time
        self.insert_interval = timedelta(minutes=30)  # Define the interval (30 minutes)
        self.insert_soil_interval = 5 # Define the interval in %
        self.plants_info = SystemConfigDefaults.plants_info
        self.active_plant = None
        self.is_active_plant = False
        self.load_settings()

    def load_settings(self):
        """
        Loads the settings from the database and applies them to the environment.
        """
        # Tries to load settings when it is safe within app context.
        with current_app.app_context():
            settings = self.database_manager.load_settings()

        if settings:
            print("setting:", settings)
            # Apply the settings
            self.light_start_time = settings['light_start_time']
            self.light_end_time = settings['light_end_time']
            self.fan_start_time = settings['fan_start_time']
            self.fan_end_time = settings['fan_end_time']
            self.temperature_threshold = settings['temperature_threshold']
            self.humidity_threshold = settings['humidity_threshold']
            self.soil_moisture_threshold = settings['soil_moisture_threshold']
            self.active_plant = self.tent.get_plant_by_id(settings['active_plant_id'])
            if isinstance(self.active_plant, (PlantProfile)):
                self.is_active_plant = True
            self.set_light_schedule(self.light_start_time, self.light_end_time)
            self.set_thresholds(self.temperature_threshold, self.humidity_threshold, self.soil_moisture_threshold)
        else:
            print("Cannot load the settings, setted the threshold values by default")

    def save_settings(self):
        """
        Saves the current settings to the database.
        """
        self.database_manager.save_settings(
            self.light_start_time, 
            self.light_end_time, 
            self.fan_start_time,
            self.fan_end_time,
            self.temperature_threshold, 
            self.humidity_threshold, 
            self.soil_moisture_threshold,
            self.active_plant.id
            )
    
    def get_stage_info(self, stage_name):
        """
        Returns the environmental settings for the given stage.

        Args:
            stage_name (str): The name of the stage.

        Returns:
            dict: A dictionary with temperature, humidity, and lighting info.
        """
        for plant in self.plants_info:
            if plant['name'].lower() == self.active_plant.name.lower():
                for stage in plant['growth_stages']:
                    if 'stage' in stage and stage['stage'].lower() == stage_name.lower():
                        return stage
        raise ValueError(f"Stage '{stage_name}' not found for the plant '{self.active_plant.name}'")

    def adjust_environment(self, plant):
        """
        Adjusts the environment based on the plant's current stage.

        Args:
            plant (Plant): The plant to adjust enviroment
        """
        stage_name = plant.get_stage_name()
        if stage_name.endswith('Stage'):
            # Remove the 'Stage' suffix
            stage_info = self.get_stage_info(stage_name[:-5])
        if stage_info:
            self.auto_light_schedule(stage_info['lighting'])
            self.temperature_threshold = self.get_adverge_number(stage_info['temperature'])
            self.set_humidity_threshold = self.get_adverge_number(stage_info['humidity'])
            self.set_thresholds(self.temperature_threshold, self.humidity_threshold)

    def get_adverge_number(self, number):
        if '-' in number:
            two_number = number.split('-')
            num1 = int(two_number[0])
            num2 = int(two_number[1])
        return (num1 + num2) / 2  

    def get_plant_by_sensor_id(self, sensor_id):
        """
        Retrieves the plant associated with a specific sensor ID.

        Args:
            sensor_id (int): The ID of the sensor.

        Returns:
            Plant: The plant associated with the sensor, or None if not found.
        """
        plant_sensors = self.database_manager.get_plant_sensors()
        for ps in plant_sensors:
            if ps['sensor_id'] == sensor_id:
                plant_id = ps['plant_id']
                return next((plant for plant in self.tent.get_all_plants() if plant.id == plant_id), None)
        return None
    
    def add_plant(self, plant_name, stage_durations, current_stage, days_in_current_stage):
        """
        Adds a plant to the tent, sets up monitoring, and saves it to the database.

        Args:
            plant_name (str): The name of plant to add.
            stage_durations (dic (str|int)): 
            current_stage (str): The stage of plant is in.
            days_in_current_stage (int): Number of days the plant has been in the current stage.
        """
        # Add plant to tent and schedule its growth
        plant = self.tent.add_plant(plant_name, stage_durations, current_stage, days_in_current_stage, adjust_environment_callback=self.adjust_environment)
        self.create_plant_observer(plant)

    def set_active_plant(self, plant):
        """
        Sets the active plant and adjusts environmental controls.

        Args:
            plant (Plant): The plant to set as active.
        """
        self.is_active_plant = True
        self.active_plant = plant
        self.database_manager.set_active_plant(self.active_plant.id)
        self.adjust_environment(self.active_plant)

    def create_plant_observer(self, plant):
        """
        Attaches the plant to the timer observer and schedules its growth.

        Args:
            plant (Plant): The plant to be observed and scheduled.
        """
        observer = PlantTimerObserver(plant)
        self.task_scheduler.attach(observer)
        self.plant_observer[plant.name] = observer  # Store observer by plant name
        self.task_scheduler.schedule_plant_growth(time_of_day="00:00")

    def remove_plant(self, plant):
        """
        Removes a plant from the tent and stops monitoring it.

        Args:
            plant (Plant): The plant to remove.
        """
        
        observer = self.plant_observer.pop(plant.name, None)
        if observer:
            self.task_scheduler.detach(observer)
        self.tent.remove_plant(plant)

    def link_sensor_to_plant(self, plant_id, sensor_id):
        """
        Link a soil moisture sensor to a plant.

        Args:
            plant_id (int): The ID of the plant.
            sensor_id (int): The ID of the sensor.
        """
            # Ensure plant_id and sensor_id are integers
        plant_id = int(plant_id)
        sensor_id = int(sensor_id)

        print("Linking sensor to plant", f"Plant ID: {plant_id}, Sensor ID: {sensor_id}")

        # Retrieve the plant and sensor directly from the Tent and SensorManager
        plant = self.tent.get_plant_by_id(plant_id)
        sensor = self.sensor_manager.get_sensor_by_id(sensor_id)
        print("Linking sensor to plant", f"Plant: {plant}, Sensor: {sensor}")
        # Ensure both plant and sensor exist
        if plant and sensor:
            # Log the linking operation
            print(f"Linking sensor '{sensor.name}' to plant '{plant.name}'.")

            # Link the sensor to the plant in the database
            self.database_manager.link_sensor_to_plant(plant_id, sensor_id)
            
            # Set the sensor_id in the plant object
            plant.set_sensor_id(sensor_id)
            plant.set_sensor_name(sensor.name)

            print(f"Sensor '{sensor.name}' has been successfully linked to plant '{plant.name}'.")
        else:
            print("Plant or sensor not found.")

    def set_thresholds(self, temperature_threshold, humidity_threshold, soil_moisture_threshold=None):
        """
        Sets the thresholds for temperature, humidity, and soil moisture, then saves the settings.

        Args:
            temperature_threshold (float): The temperature threshold.
            humidity_threshold (float): The humidity threshold.
            soil_moisture_threshold (float): The soil moisture threshold.
        """
        self.temperature_threshold = temperature_threshold
        self.humidity_threshold = humidity_threshold
        self.soil_moisture_threshold = soil_moisture_threshold
        self.save_settings()

    def create_observer(self, actuator):
        """
        Creates the Fan and Light Observer if actuator are available.
        """
        device = self.actuator_controller.get_actuators().get(actuator)
        print("create actuator, device: ", device)

        if device:
            self.device_observer = DeviceStateObserver(actuator, self.actuator_controller)
            self.task_scheduler.attach(self.device_observer)
            print(f"Observer {actuator} created and attached to the timer.")
        else:
            print(f"No device found or observer already exists. '{actuator}' Observer not created.")

    def set_device_schedule(self, device_name, start_time, end_time):
        """
        Schedules the on/off times for any device (Light, Fan, Pump, etc.).

        Args:
            device_name (str): The name of the device to schedule.
            start_time (str): The start time for the schedule in 'HH:MM' format.
            end_time (str): The end time for the schedule in 'HH:MM' format.
        """
        # Ensure the observer exists for the device
        if device_name not in self.device_observers:
            self.create_observer(device_name)

        # Get the observer and schedule the task
        observer = self.device_observers.get(device_name)
        if observer:
            print(f"Scheduling {device_name} from {start_time} to {end_time}.")

            self.task_scheduler.schedule_device(
                start_time=start_time,
                end_time=end_time
            )

            # Save the settings after updating the schedule
            self.save_settings()
            print(f"{device_name} scheduled from {start_time} to {end_time}.")
        else:
            print(f"Cannot schedule {device_name}. No observer available.")

    def auto_light_schedule(self, lighting_info):
        """
        Schedules the light on/off times based on the lighting info provided.

        Args:
            lighting_info (str): The lighting schedule in hours.
        """
        self.is_active_plant = True
        min_hours, max_hours = map(int, lighting_info.split('-'))
        default_start_time = datetime.strptime("07:00", "%H:%M")
        start_time = default_start_time.strftime("%H:%M")
        end_time = (default_start_time + timedelta(hours=min_hours)).strftime("%H:%M")
        self.set_light_schedule(start_time, end_time)

    def get_fan_schedule(self):
        return self.database_manager.get_fan_schedule()

    def get_light_schedule(self):
        return self.database_manager.get_light_schedule()
    
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
            dict: A dictionary containing 'ssid' and 'password' keys.
        """
        # Example: Fetching from the database
        hotspot_settings = self.database_manager.load_hotspot_settings()
        if hotspot_settings:
            return {
                'ssid': hotspot_settings.get('ssid', 'default_ssid'),
                'password': hotspot_settings.get('password', 'default_password')
            }
        else:
            # Return default values if settings are not found in the database
            return {'ssid': 'default_ssid', 'password': 'default_password'}

    def monitor_environment(self):
        """
        Monitors the environment and updates devices accordingly.

        Returns:
            dict: The current environmental data.
        """
        sensor_readings = self.sensor_manager.read_all_sensors()
        if not sensor_readings:
            print("No sensor readings available.")
            return {}

        for sensor_id, readings in sensor_readings.items():
            sensor_type = readings.get('sensor_type')
            
            if sensor_type == 'temp_humidity_sensor':
                temperature = readings.get('temperature')
                humidity = readings.get('humidity')
                self.handle_temp_humidity(sensor_id, temperature, humidity)
            
            elif sensor_type.startswith('soil_sensor'):
                moisture_level = readings.get('reading')
                plant = self.get_plant_by_sensor_id(sensor_id)  # Get the plant associated with this sensor_id
                self.handle_soil_moisture(sensor_id, plant, moisture_level)
                print(f"Monitor: Soil moisture reading from sensor ID: {sensor_id} - plant: {plant}, moisture level: {moisture_level}")
        return sensor_readings
    
    def handle_soil_moisture(self, sensor_id, plant, moisture_level):
        """
        Handles soil moisture reading and decides whether to store the data in the database based on the percentage change.

        Args:
            sensor_id (int): The sensor ID reading the soil moisture.
            plant (Plant): The plant object associated with the sensor.
            moisture_level (dict): The moisture level reading.
        """
        # Extract the numerical soil moisture value
        current_moisture = moisture_level.get('soil_moisture')

        if current_moisture is not None:
            # Get the last recorded soil moisture for this specific plant
            last_moisture = plant.moisture_level

            # Check if it's the first reading or if the percentage change exceeds the threshold
            if last_moisture is None or (last_moisture != 0 and abs(current_moisture - last_moisture) / last_moisture * 100 >= self.insert_soil_interval):
                # Insert the new soil moisture level into the database
                self.database_manager.insert_soil_moisture_history(plant.id, current_moisture)
                print(f"Inserted soil moisture for plant '{plant.name}' with sensor ID {sensor_id}, moisture level: {current_moisture}")
            
            # Update the plant's current soil moisture level via the tent
            self.tent.update_plant_soil_moisture(plant, current_moisture)
            print(f"Updated soil moisture for plant '{plant.name}' in the tent, moisture level: {current_moisture}")

        else:
            print(f"Invalid moisture level received for plant '{plant.name}' with sensor ID {sensor_id}.")

    def handle_temp_humidity(self, sensor_id, temperature, humidity):
        """
        Handles temperature and humidity readings, ensuring data is saved every 30 minutes.

        Args:
            sensor_id (int): The sensor ID reading the temperature and humidity.
            temperature (float): The temperature reading.
            humidity (float): The humidity reading.
        """
        current_time = datetime.now()
        if (self.last_temp_humidity_insert is None or
                current_time - self.last_temp_humidity_insert >= self.insert_interval):
            # Insert readings into the database
            self.database_manager.insert_sensor_data(temperature=temperature, humidity=humidity)
            print(f"Inserted temperature and humidity at {current_time} for sensor ID: {sensor_id}")

            # Update the last insertion time
            self.last_temp_humidity_insert = current_time

        # Continue to control temperature and humidity regardless of the database insertion
        self.control_temperature(temperature)
        self.control_humidity(humidity)

    def control_temperature(self, current_temperature):
        if current_temperature is None:
            print("Invalid temperature reading.")
            return
        control_signal = self.temp_pid.compute(float(current_temperature))
        print("current temp: ", current_temperature, "control_signal: ", control_signal)
    
        if control_signal > 0:
            self.actuator_controller.activate_actuator("Heater")
            self.actuator_controller.deactivate_actuator("Cooler")
        else:
            self.actuator_controller.deactivate_actuator("Heater")
            self.actuator_controller.activate_actuator("Cooler")
    
    def control_humidity(self, current_humidity):
        if current_humidity is None:
            print("Invalid humidity reading.")
            return
        control_signal = self.humidity_pid.compute(float(current_humidity))
        print("current humidity: ", current_humidity, "control_signal: ", control_signal)

        if control_signal > 0:
            self.actuator_controller.activate_actuator('Humidifier')
            self.actuator_controller.deactivate_actuator("Dehumidifier")
        else:
            self.actuator_controller.deactivate_actuator("Humidifier")
            self.actuator_controller.activate_actuator("Dehumidifier")

        print(f"Humidity: {current_humidity}%, Control Signal: {control_signal}")

    def control_soil_moisture(self, current_moisture):
        if current_moisture is None:
            print("Invalid soil moisture reading.")
            return
        control_signal = self.soil_moisture_pid.compute(float(current_moisture))

        if control_signal > 0:
            self.actuator_controller.activate_actuator('Water-Pump')
        else:
            self.actuator_controller.deactivate_actuator('Water-Pump')

        print(f"Soil Moisture: {current_moisture}%, Control Signal: {control_signal}")

        print(f"Soil Moisture: {current_moisture}%, Control Signal: {control_signal}")

    # def control_smoke(self, readings):
    #     current_smoke = readings
    #     if current_smoke < 50:
    #         logging.info(f"Smoke Level Normal: {current_smoke}")  # Normal smoke level
    #     elif current_smoke < 100:
    #         logging.warning(f"Smoke Level High: {current_smoke}")  # High smoke level detected
    #         self.actuator_controller.activate_actuator('Smoke-Alarm') # Activate smoke alarm  
        # elif current_smoke < 150:
        #     logging.error(f"Smoke Level Critical: {current_smoke}")  # Critical smoke level detected  
        #     self.actuator_controller.activate_actuator('Smoke-Alarm') # Activate smoke alarm
        #     self.actuator_controller.activate_actuator('Sprinkler') # Activate sprinkler system   
        # else:
        #     logging.critical(f"Smoke Level Emergency: {current_smoke}")  # Emergency smoke level detected
        #     self.actuator_controller.activate_actuator('Smoke-Alarm') # Activate smoke alarm  
        #     self.actuator_controller.activate_actuator('Sprinkler') # Activate sprinkler system

