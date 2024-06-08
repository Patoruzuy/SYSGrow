"""
Sensor and SoilMoistureSensor classes for observing and notifying changes in the tent environment and plant soil moisture.

Author: Sebastian Gomez
Date: May 2024
"""
from sensors.dht11_sensor import DHT11Sensor

class SensorManager:
    """
    Manages multiple Sensor objects, loading their configurations from a database.

    Attributes:
        database_manager (DatabaseManager): An instance of the database manager.
        sensors (dict): A dictionary of Sensor objects keyed by their functionalities.

    Methods:
        get_sensor_by_functionality(functionality): Retrieves a sensor by its functionality.
        add_sensor(name, gpio, ip_address, type, functionality): Adds a new sensor.
        remove_sensor(functionality): Removes a specified sensor by functionality.
        read_all_sensors(): Reads data from all sensors and notifies their observers.
    """

    def __init__(self, database_manager):
        """
        Initializes a SensorManager object.

        Args:
            database_manager (DatabaseManager): An instance of the database manager.
        """
        self.database_manager = database_manager
        self.sensors = self._load_sensors_from_db()

    def _load_sensors_from_db(self):
        """
        Loads sensor configurations from the database and creates Sensor objects.

        Returns:
            dict: A dictionary of Sensor objects keyed by their functionalities.
        """
        sensors = {}
        sensor_configs = self.database_manager.get_sensor_configs()
        for config in sensor_configs:
            if config['type'] == 'dht':
                sensor = DHTSensor(pin=config['gpio'])
            elif config['type'] == 'soil_moisture':
                sensor = SoilMoistureSensor(plant=config['name'])  # Assuming 'name' is the plant name
            else:
                continue
            sensors[config['functionality']] = sensor
        return sensors

    def get_sensor_by_functionality(self, functionality):
        """
        Retrieves a Sensor object by its functionality.

        Args:
            functionality (str): The functionality of the sensor to retrieve.

        Returns:
            Sensor: The Sensor object with the specified functionality, or None if not found.
        """
        return self.sensors.get(functionality)

    def add_sensor(self, name, gpio, ip_address, type, functionality):
        """
        Adds a new sensor to the manager.

        Args:
            name (str): The name of the sensor.
            gpio (int, optional): The GPIO pin number for control.
            ip_address (str, optional): The IP address for wireless control.
            type (str): The type of sensor.
            functionality (str): Description of the sensor's functionality.
        """
        if type == 'dht':
            sensor = DHTSensor(pin=gpio)
        elif type == 'soil_moisture':
            sensor = SoilMoistureSensor(plant=name)
        else:
            print(f"Unknown sensor type: {type}")
            return
        
        self.sensors[functionality] = sensor
        self.database_manager.insert_sensor(name, gpio, ip_address, type, functionality)

    def remove_sensor(self, functionality):
        """
        Removes the specified sensor by functionality.

        Args:
            functionality (str): The functionality of the sensor to remove.
        """
        if functionality in self.sensors:
            del self.sensors[functionality]
            self.database_manager.remove_sensor(functionality)
        else:
            print(f"Cannot remove sensor with functionality '{functionality}' because it is not found.")

    def read_all_sensors(self):
        """
        Reads data from all sensors and notifies their observers.
        """
        for sensor in self.sensors.values():
            if isinstance(sensor, DHTSensor):
                sensor.read_environment()
            elif isinstance(sensor, SoilMoistureSensor):
                sensor.read_moisture_level()

class DHTSensor():
    """
    Class to represent a sensor for monitoring the tent environment.
    
    Attributes:
        observers (list): List of observer objects that get notified of sensor changes.
    """
    
    def __init__(self, pin):
        """
        Initializes the Sensor with an empty list of observers.
        """
        self.pin = pin
        self.dht11 = DHT11Sensor(self.pin)
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
    
    def get_temperature():
        """Return the temperature
        """
        data = self.dht11.read()
        if data is None:
            return {'error': 'Failed to get reading. Try again!'}
        return data['temperature']
    
    def get_humidity():
        """Return the temperature
        """
        data = self.dht11.read()
        if data is None:
            return {'error': 'Failed to get reading. Try again!'}
        return data['humidity']

    def read_environment(self):
        """
        Simulates reading the environmental data and notifies observers.
        """
        data = self.dht11.read()
        if data is None:
            return {'error': 'Failed to get reading. Try again!'}
        self.notify(data['temperature'], data['humidity'])
        return data
        

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
        try:
            # Simulate reading the moisture level
            import random
            moisture_level = random.uniform(0, 100)
            self.notify(moisture_level)
            return moisture_level
        except Exception as e:
            print(f"Error reading soil moisture level: {e}")
            return None

