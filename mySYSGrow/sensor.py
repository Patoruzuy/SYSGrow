"""
Sensor and SoilMoistureSensor classes for observing and notifying changes in the tent environment and plant soil moisture.

Author: Sebastian Gomez
Date: May 2024
"""

class Sensor:
    """
    Class to represent a sensor for monitoring the tent environment.
    
    Attributes:
        observers (list): List of observer objects that get notified of sensor changes.
    """
    
    def __init__(self):
        """
        Initializes the Sensor with an empty list of observers.
        """
        self.observers = []

    def attach(self, observer):
        """
        Attaches an observer to the sensor.

        Args:
            observer (object): The observer to be attached.
        """
        self.observers.append(observer)

    def detach(self, observer):
        """
        Detaches an observer from the sensor.

        Args:
            observer (object): The observer to be detached.
        """
        self.observers.remove(observer)

    def notify(self, temperature, humidity):
        """
        Notifies all attached observers with the current temperature and humidity.

        Args:
            temperature (float): The current temperature.
            humidity (float): The current humidity.
        """
        for observer in self.observers:
            observer.update(temperature, humidity)

    def read_environment(self):
        """
        Simulates reading the environmental data and notifies observers.
        """
        import random
        temperature = random.uniform(15, 35)  # Example temperature range
        humidity = random.uniform(30, 70)     # Example humidity range
        self.notify(temperature, humidity)

class SoilMoistureSensor:
    """
    Class to represent a soil moisture sensor for a plant.
    
    Attributes:
        plant (Plant): The plant associated with this sensor.
        observers (list): List of observer objects that get notified of soil moisture changes.
    """
    
    def __init__(self, plant):
        """
        Initializes the SoilMoistureSensor with a plant and an empty list of observers.

        Args:
            plant (Plant): The plant associated with this sensor.
        """
        self.plant = plant
        self.observers = []

    def attach(self, observer):
        """
        Attaches an observer to the soil moisture sensor.

        Args:
            observer (object): The observer to be attached.
        """
        self.observers.append(observer)

    def detach(self, observer):
        """
        Detaches an observer from the soil moisture sensor.

        Args:
            observer (object): The observer to be detached.
        """
        self.observers.remove(observer)

    def notify(self, moisture_level):
        """
        Notifies all attached observers with the current soil moisture level.

        Args:
            moisture_level (float): The current soil moisture level.
        """
        for observer in self.observers:
            observer.update_soil_moisture(self.plant, moisture_level)
    
    def read_moisture_level(self):
        """
        Simulates reading the soil moisture level and notifies observers.
        """
        import random
        moisture_level = random.uniform(0, 100)
        self.notify(moisture_level)

