"""
Description: This script defines the GrowthManager class for managing plant growth in a grow tent, including environmental monitoring and control mechanisms.

Author: Sebastian Gomez
Date: 26/05/2024
"""

from timer import *
from grow_tent import Tent
from grow_plant import *
from db_manager import DatabaseManager
from sensor_manager import SensorManager
from flask import current_app
from actuator_manager import *
from pib_controller import PIDController

class GrowthManager:
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
        self.tent = Tent()
        self.timer = Timer()
        self.light_observer = None
        self.fan_observer = None
        self.actuator_manager = ActuatorManager(database_manager)
        self.sensor_manager = SensorManager(database_manager)
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
        self.hysteresis = 2
        self.add_plant("Cannabies", "Seedling", "1")
        self.load_settings() 

    def load_settings(self):
        """
        Loads the settings from the database and applies them to the environment.
        """
        # Tries to load settings when it is safe within app context.
        with current_app.app_context():
            settings = self.database_manager.load_settings()

        if settings:
            # Apply the settings
            self.light_start_time = settings['light_start_time']
            self.light_end_time = settings['light_end_time']
            self.fan_start_time = settings['fan_start_time']
            self.fan_end_time = settings['fan_end_time']
            self.temperature_threshold = settings['temperature_threshold']
            self.humidity_threshold = settings['humidity_threshold']
            self.soil_moisture_threshold = settings['soil_moisture_threshold']
            self.set_light_schedule(self.light_start_time, self.light_end_time)
            self.set_thresholds(self.temperature_threshold, self.humidity_threshold, self.soil_moisture_threshold)
            self.sensor_manager._load_sensors_from_db()
            self.actuator_manager._load_actuators_from_db()
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
            self.soil_moisture_threshold
            )

    def get_plant(self, id) -> Plant:
        """
        Retrieves a Plant object by its ID.

        Args:
            id (int): The ID of the plant.

        Returns:
            Plant: The Plant object.
        """
        row = self.database_manager.get_plant(id)
        if row:
            return self.create_plant_from_row(row)
        return None

    def create_plant_from_row(self, row) -> Plant:
        """
        Creates a Plant object from a database row.

        Args:
            row (sqlite3.Row): The database row containing plant data.

        Returns:
            Plant: The created Plant object.
        """
        plant = Plant(row['name'])
        plant.set_stage(row['current_stage'])
        pin = row.get('pin')
        if pin:
            plant.soil_moisture_sensor = SoilMoistureSensor(plant, pin=pin) 
            print(f"No pin available for plant {plant.name}")
        return plant
        
    def get_all_plants(self) -> list:
        """
        Retrieves all Plant objects.

        Returns:
            list: A list of Plant objects.
        """
        rows = self.database_manager.get_all_plants()
        plants = [self.create_plant_from_row(row) for row in rows]
        return plants
    
    def get_plant_by_name(self, name):
        for plant in self.get_all_plants():
            if plant.name == name:
                return plant
        return None
    
    def add_plant(self, plant_type, current_stage, days_in_current_stage):
        """
        Adds a plant to the tent and sets up monitoring for it.

        Args:
            plant_type (str): The type of plant to add.
            current_stage (str): The stage of plant is in.
            details (str): Plant details (optional)
        """
        plant = PlantFactory.create_plant(plant_type)
        self.tent.add_plant(plant)
        self.timer.attach(PlantTimerObserver(plant))
        self.database_manager.insert_plant(plant.name, current_stage, days_in_current_stage, moisture_level=None)

    def remove_plant(self, plant):
        """
        Removes a plant from the tent and stops monitoring it.

        Args:
            plant (Plant): The plant to remove.
        """
        self.tent.remove_plant(plant)
        self.timer.detach(PlantTimerObserver(plant))
        self.soil_moisture_sensor.detach(self)

    def link_sensor_to_plant(self, plant_id, sensor_id):
        """
        Link a soil moisture sensor to a plant.

        Args:
            plant_id (int): The ID of the plant.
            sensor_id (int): The ID of the sensor.
        """
        plant = self.database_manager.get_plant_by_id(plant_id)
        sensor = self.device_manager.get_device_by_id(sensor_id)

        if plant and sensor:
            self.database_manager.link_sensor_to_plant(plant_id, sensor_id)
            print(f"Linked sensor '{sensor.name}' to plant '{plant.name}'.")

    def set_stage_durations(self, plant_name, seed_days, veg_days, flowering_days):
        """
        Sets the stage durations for a specific plant identified by its name.

        Args:
            plant_name (str): The name of the plant for which to set the stage durations.
            seed_days (int): The number of days for the seedling stage.
            veg_days (int): The number of days for the vegetative stage.
            flowering_days (int): The number of days for the flowering stage.
        """
        # Retrieve the plant object by its name from the tent
        plant = self.tent.get_plant_by_name(plant_name)
        if plant:
            plant.set_stage_durations(seed_days, veg_days, flowering_days)

    def set_thresholds(self, temperature_threshold, humidity_threshold, soil_moisture_threshold):
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
        device = self.actuator_manager.get_actuator(actuator)

        if device == 'Light':
            self.light_observer = LightObserver(device)
            self.timer.attach(self.light_observer)
            print("LightObserver created and attached to the timer.")
        elif actuator == 'Fan':
            self.fan_observer = FanObserver(device)
            self.timer.attach(self.fan_observer)
        else:
            print(f"No device found. '{actuator}'Observer not created.")

    def set_light_schedule(self, start_time, end_time):
        """
        Schedules the light on/off times.

        Args:
            start_time (str): The start time for the light schedule in 'HH:MM' format.
            end_time (str): The end time for the light schedule in 'HH:MM' format.
        """
        if not self.light_observer:
            self.create_observer('Light')
        
        if self.light_observer:
            self.light_start_time = start_time
            self.light_end_time = end_time
            self.timer.schedule_light(self.light_start_time, self.light_end_time)
            self.save_settings()
            print(f"Light scheduled from {start_time} to {end_time}.")
        else:
            print("Cannot schedule light. No LightObserver available.")

    def set_fan_schedule(self, start_time, end_time):
        if not self.fan_observer:
            self.create_observer('Fan')
        self.timer.schedule_fan(start_time, end_time)

    def get_light_schedule(self):
        return self.database_manager.get_light_schedule()
    
    def grow_all_plants(self):
        """
        Updates the growth stage of all plants and stores the data in the database.
        """
        self.timer.notify()
        for plant in self.tent.get_all_plants():
            self.database_manager.update_plant_current_stage(
                plant.name, plant.stage.__class__.__name__
            )
            plant.get_moisture_level()

    def update_soil_moisture(self, plant, moisture_level):
        """
        Updates the soil moisture level and controls the water spray.

        Args:
            plant (Plant): The plant being monitored.
            moisture_level (float): The current soil moisture level.
        """
        self.database_manager.insert_soil_moisture_history(plant.id, moisture_level)
        self.database_manager.insert_sensor_data(moisture_level=moisture_level)

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

        for sensor_type, readings in sensor_readings.items():
            if sensor_type == 'DHT':
                temperature = readings.get('temperature')
                humidity = readings.get('humidity')
                self.control_temperature(temperature)
                self.control_humidity(humidity)
                self.database_manager.insert_sensor_data(temperature=temperature, humidity=humidity)
            elif sensor_type == 'Soil-Moisture':
                for plant in self.get_all_plants():
                    moisture_level = readings.get('moisture_level')
                    self.update_soil_moisture(plant, moisture_level)
            elif sensor_type == 'CO2':
                co2_level = readings.get('co2')
                self.database_manager.insert_sensor_data(co2_level=co2_level)
        
        return sensor_readings

    def control_temperature(self, current_temperature):
        if current_temperature is None:
            print("Invalid temperature reading.")
            return
        control_signal = self.temp_pid.compute(current_temperature)
        print("current temp: ", current_temperature, "control_signal: ", control_signal)
    
        if control_signal > 0:
            self.actuator_manager.activate_actuator("Heater")
            self.actuator_manager.deactivate_actuator("Cooler")
        else:
            self.actuator_manager.deactivate_actuator("Heater")
            self.actuator_manager.activate_actuator("Cooler")
    
    def control_humidity(self, current_humidity):
        if current_humidity is None:
            print("Invalid humidity reading.")
            return
        control_signal = self.humidity_pid.compute(current_humidity)
        print("current humidity: ", current_humidity, "control_signal: ", control_signal)

        if control_signal > 0:
            self.actuator_manager.activate_actuator('Humidifier')
            self.actuator_manager.deactivate_actuator("Dehumidifier")
        else:
            self.actuator_manager.deactivate_actuator("Humidifier")
            self.actuator_manager.activate_actuator("Dehumidifier")

        print(f"Humidity: {current_humidity}%, Control Signal: {control_signal}")

    def control_soil_moisture(self, current_moisture):
        if current_moisture is None:
            print("Invalid soil moisture reading.")
            return
        control_signal = self.soil_moisture_pid.compute(current_moisture)

        if control_signal > 0:
            self.actuator_manager.activate_actuator('Water-Pump')
        else:
            self.actuator_manager.deactivate_actuator('Water-Pump')

        print(f"Soil Moisture: {current_moisture}%, Control Signal: {control_signal}")

    # def control_co2(self, readings):
    #     current_co2 = readings
    #     control_signal = self.co2_pid.compute(current_co2)

    #     if control_signal > 0:
    #         self.actuator_manager.activate_actuator('CO2-Injector')
    #     else:
    #         self.actuator_manager.deactivate_actuator('CO2-Injector')

    #     print(f"CO2 Level: {current_co2}ppm, Control Signal: {control_signal}")