"""
Description: This script defines the GrowthManager class for managing plant growth in a grow tent, including environmental monitoring and control mechanisms.

Author: Sebastian Gomez
Date: 26/05/2024
"""

from timer import *
from grow_tent import Tent
from grow_plant import *
from db_manager import DatabaseManager
from sensor import Sensor, SoilMoistureSensor
from flask import current_app
from relay.relay import Relay

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
        self.sensor = Sensor(pin=4)
        self.sensor.attach(self)
        self.temperature_threshold = 24
        self.humidity_threshold = 40
        self.soil_moisture_threshold = 50
        self.light_start_time = "08:00"
        self.light_end_time = "20:00"
        self.light_gpio = None
        self.fan_gpio = None
        self.water_spray_gpio = None
        self.hysteresis = 2
        self.add_plant("Cannabies", "Sedding")
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
            self.temperature_threshold = settings['temperature_threshold']
            self.humidity_threshold = settings['humidity_threshold']
            self.soil_moisture_threshold = settings['soil_moisture_threshold']
            self.light_gpio = settings['light_gpio']
            self.fan_gpio = settings['fan_gpio']
            self.water_spray_gpio = settings['water_spray_gpio']
            self.set_light_schedule(self.light_start_time, self.light_end_time)
            self.set_thresholds(self.temperature_threshold, self.humidity_threshold, self.soil_moisture_threshold)

            self.light_relay = Light(pin=self.light_gpio)
            self.fan = Fan(pin=self.fan_gpio)
            self.water_spray = WaterSpray(pin=self.water_spray_gpio)
        else:
            print("Cannot load the settings, setted the threshold values by default")

    def save_settings(self):
        """
        Saves the current settings to the database.
        """
        self.database_manager.save_settings(
            self.light_start_time, 
            self.light_end_time, 
            self.temperature_threshold, 
            self.humidity_threshold, 
            self.soil_moisture_threshold,
            self.light_gpio,
            self.fan_gpio,
            self.water_spray_gpio
            )

    def add_plant(self, plant_type, state):
        """
        Adds a plant to the tent and sets up monitoring for it.

        Args:
            plant_type (str): The type of plant to add.
        """
        plant = PlantFactory.create_plant(plant_type)
        self.tent.add_plant(plant)
        self.timer.attach(PlantTimerObserver(plant))
        self.database_manager.insert_plant(plant.name, state, moisture_level=None)
        plant.soil_moisture_sensor.attach(self)

    def remove_plant(self, plant):
        """
        Removes a plant from the tent and stops monitoring it.

        Args:
            plant (Plant): The plant to remove.
        """
        self.tent.remove_plant(plant)
        self.timer.detach(PlantTimerObserver(plant))
        self.soil_moisture_sensor.detach(self)

    def set_temperature_threshold(self, temperature):
        """
        Sets the temperature threshold for the fan.

        Args:
            temperature (float): The new temperature threshold.
        """
        self.temperature_threshold = temperature

    def set_humidity_threshold(self, humidity):
        """
        Sets the humidity threshold for the water spray.

        Args:
            humidity (float): The new humidity threshold.
        """
        self.humidity_threshold = humidity

    def set_soil_moisture_threshold(self, moisture):
        """
        Sets the soil moisture threshold for the water spray.

        Args:
            moisture (float): The new soil moisture threshold.
        """
        self.soil_moisture_threshold = moisture

    def set_hysteresis(self,value):
        """
        Sets the hysteresis value to prevent rapid cycling.

        Args:
            hysteresis (int): The new hysteresis value
        """
        self.hysteresis = value

    def set_stage_durations(self, plant_name, seed_days, veg_days, flowering_days):
        """
        Sets the stage durations for a specific plant identified by its name.

        Args:
            plant_name (str): The name of the plant for which to set the stage durations.
            seed_days (int): The number of days for the seed stage.
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

    def set_light_schedule(self, start_time, end_time):
        """
        Schedules the light to turn on and off at specified times and saves the settings.

        Args:
            start_time (str): The time to turn on the light.
            end_time (str): The time to turn off the light.
        """
        self.light_start_time = start_time
        self.light_end_time = end_time
        self.timer.schedule_light(start_time, end_time)
        self.save_settings()

    def get_light_schedule(self):
        return self.database_manager.get_light_schedule()
    

    def grow_all_plants(self):
        """
        Updates the growth stage of all plants and stores the data in the database.
        """
        self.timer.notify()
        for plant in self.tent.get_plants():
            self.database_manager.update_plant_growth_stage(
                plant.name, plant.state.__class__.__name__
            )
            plant.get_moisture_level()

    def update(self, temperature, humidity):
        """
        Updates the environmental conditions and controls the fan and water spray.

        Args:
            temperature (float): The current temperature.
            humidity (float): The current humidity.
        """
        print(f"Temperature: {temperature}, Humidity: {humidity}")
        self.database_manager.insert_sensor_data(temperature=temperature, humidity=humidity)
        if temperature > self.temperature_threshold + self.hysteresis:
            self.fan.turn_on()
        elif temperature < self.temperature_threshold - self.hysteresis:
            self.fan.turn_off()

        if humidity < self.humidity_threshold - self.hysteresis:
            self.water_spray.turn_on()
        elif humidity > self.humidity_threshold - self.hysteresis:  
            self.water_spray.turn_off()

    def update_soil_moisture(self, plant, moisture_level):
        """
        Updates the soil moisture level and controls the water spray.

        Args:
            plant (Plant): The plant being monitored.
            moisture_level (float): The current soil moisture level.
        """
        print(f"Plant: {plant.name}, Soil Moisture Level: {moisture_level}")
        self.database_manager.insert_sensor_data(plant_name=plant.name, moisture_level=moisture_level)
        if moisture_level < self.soil_moisture_threshold:
            self.water_spray.turn_on()
        else:
            self.water_spray.turn_off()

    
    def monitor_environment(self):
        data = self.sensor.read_environment()
        for plant in self.tent.get_plants():
             name = plant.get_name()
             level = plant.get_moisture_level()
             self.update_soil_moisture(name, level)
        if 'error' in data:
            return data
        self.update(data['temperature'], data['humidity'])
        return data
    
    def turn_on_light(self):
        """Turn on the light by activating the light relay."""
        self.light.turn_on()

    def turn_off_light(self):
        """Turn off the light by deactivating the light relay."""
        self.light.turn_off()

    def turn_on_fan(self):
        """Turn on the fan by activating the fan relay."""
        self.fan.turn_on()

    def turn_off_fan(self):
        """Turn off the fan by deactivating the fan relay."""
        self.fan.turn_off()

    def turn_on_water_spray(self):
        """Turn on the water spray by activating the water spray relay."""
        self.water_spray.turn_on()

    def turn_off_water_spray(self):
        """Turn off the water spray by deactivating the water spray relay."""
        self.water_spray.turn_off()

    
class Light:
    """Represents a light controlled by the schedule."""
    def __ini__(self, pin=None, ip=None):
        self.light = Relay('light', pin, ip)

    def turn_on(self):
        """Turns the light on."""
        self.light.turn_on()
        print("Light is turned on.")

    def turn_off(self):
        """Turns the light off."""
        self.light.turn_off()
        print("Light is turned off.")
   
class Fan:
    """Represents a fan used for temperature control."""
    def __ini__(self, pin=None, ip=None):
        self.fan = Relay('fan', pin, ip)

    def turn_on(self):
        """Turns the fan on."""
        self.fan.turn_on()
        print("Fan is turned on to cool down the tent.")

    def turn_off(self):
        """Turns the fan off."""
        self.fan.turn_off()
        print("Fan is turned off.")


class WaterSpray:
    """Represents a water spray used for humidity control."""
    def __ini__(self, pin=None, ip=None):
        self.waterspray = Relay('fan', pin, ip)
    def turn_on(self):
        """Turns the water spray on."""
        self.waterspray.turn_on()
        print("Water spray is turned on to increase humidity.")

    def turn_off(self):
        """Turns the water spray off."""
        self.waterspray.turn_off()
        print("Water spray is turned off.")