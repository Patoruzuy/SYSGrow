from abc import ABC, abstractmethod
from sensors.dht11_sensor import DHT11Sensor
from sensors.co2_sensor import CO2Sensor
from sensors.soil_moisture_sensor import SoilMoistureSensorV2
from sensors.temp_humidity_sensor import BME280Sensor

class Sensor(ABC):
    """
    Abstract base class representing a generic sensor.

    Methods:
        read(): Reads the sensor value(s).
    """
    @abstractmethod
    def read(self):
        """
        Reads the sensor value(s).
        """
        pass

class DHTSensor(Sensor):
    """
    Class to represent a DHT sensor for monitoring temperature and humidity.
    
    Attributes:
        pin (int): The GPIO pin number to which the DHT sensor is connected.
        dht11 (DHT11Sensor): The DHT11 sensor instance.
    """
    def __init__(self, pin):
        """
        Initializes the DHTSensor with a specified GPIO pin.

        Args:
            pin (int): The GPIO pin number to which the DHT sensor is connected.
        """
        self.pin = pin
        self.dht11 = DHT11Sensor(self.pin)

    def read(self):
        """
        Reads the environmental data from the DHT sensor.

        Returns:
            dict: A dictionary containing the temperature and humidity readings.
        """
        data = self.dht11.read()
        if data is None:
            return {'error': 'Failed to get reading. Try again!'}
        return {'temperature': data['temperature'], 'humidity': data['humidity']}

class SoilMoistureSensor(Sensor):
    """
    Class to represent a soil moisture sensor for a plant.
    
    Attributes:
        plant (str): The plant associated with this sensor.
        pin (int): ADC channel where the soil moisture sensor is connected.
    """
    def __init__(self, pin):
        """
        Initializes the SoilMoistureSensor with a plant name.

        Args:
            plant (str): The name of the plant associated with this sensor.
        """
        self.pin = pin
        self.sensor = SoilMoistureSensorV2(self.pin)
        self.sensor.set_sea_level_pressure(1013.25) 

    def read(self):
        """
        Reads the soil moisture level from the sensor.

        Returns:
            dict: A dictionary containing the soil moisture level.
        """
        try:
            moisture_level = self.sensor.read()
            return moisture_level
        except Exception as e:
            print(f"Error reading soil moisture level: {e}")
            return {'error': str(e)}

class CO2Sensor(Sensor):
    """
    Class to represent a CO2 sensor for monitoring CO2 levels.
    
    Attributes:
        pin (int): The GPIO pin number to which the CO2 sensor is connected.
        ip (str): The IP address for wireless control of the CO2 sensor.
        co2_sensor (CO2Sensor): The CO2 sensor instance.
    """
    def __init__(self, pin, ip):
        """
        Initializes the CO2Sensor with a specified IP address.

            pin (int): The GPIO pin number to which the CO2 sensor is connected.
            ip (str): The IP address for wireless control of the CO2 sensor.
        """
        self.pin = pin
        self.ip = ip
        self.co2_sensor = CO2Sensor(self.ip)

    def read(self):
        """
        Reads the CO2 level from the CO2 sensor.

        Returns:
            dict: A dictionary containing the CO2 level.
        """
        data = self.co2_sensor.read()
        if data is None:
            return {'error': 'Failed to get reading. Try again!'}
        return {'CO2': data['CO2']}

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
        read_all_sensors(): Reads data from all sensors.
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
            if config['sensor_type'] == 'BME280':
                sensor = BME280Sensor(i2c_bus=1)
            if config['sensor_type'] == 'DHT':
                sensor = DHTSensor(pin=config['gpio'])
            elif config['sensor_type'] == 'Soil-Moisture':
                sensor = SoilMoistureSensor(pin=config['gpio'])
            elif config['sensor_type'] == 'CO2':
                sensor = CO2Sensor(ip=config['ip_address'])
            else:
                continue
            sensors[config['sensor_type']] = sensor
        return sensors
    
    def get_sensors(self):
        """
        Returns the names of all managed sensors.

        Returns:
            list: A list of sensors names.
        """
        return self.sensors.keys()

    def get_sensor_by_type(self, sensor_type):
        """
        Retrieves a Sensor object by its type.

        Args:
            sensor_type (str): The type or name of the sensor to retrieve.

        Returns:
            Sensor: The Sensor object with the specified type, or None if not found.
        """
        return self.sensors.get(sensor_type)
    
    def get_sensor_by_id(self, sensor_id):
            """
            Retrieves sensor information by its ID.

            Args:
                sensor_id (int): The ID of the sensor.

            Returns:
                Sensor: The sensor object.
            """
            sensor_info = self.database_manager.get_sensor(sensor_id)
            if sensor_info:
                return Sensor(sensor_info['sensor_type'], sensor_info['gpio'], sensor_info['ip_address'])
            return None

    def add_sensor(self, sensor_type, gpio, ip_address):
        """
        Adds a new sensor to the manager.

        Args:
            sensor_type (str): The type or name of the sensor.
            gpio (int, optional): The GPIO pin number for control.
            ip_address (str, optional): The IP address for wireless control.
        """
        if sensor_type == 'BME280':
            sensor = BME280Sensor(i2c_bus=1)
        if sensor_type == 'DHT':
            sensor = DHTSensor(pin=gpio)
        elif sensor_type == 'Soil-Moisture':
            sensor = SoilMoistureSensor(pin=gpio)
        elif sensor_type == 'CO2':
            sensor = CO2Sensor(pin=gpio, ip=ip_address)
        else:
            print(f"Unknown sensor type: {sensor_type}")
            return
        
        self.sensors[sensor_type] = sensor
        self.database_manager.insert_sensor(sensor_type, gpio, ip_address)

    def remove_sensor(self, sensor_type):
        """
        Removes the specified sensor by type.

        Args:
            Sensor_type (str): The type or name of the sensor to remove.
        """
        if sensor_type in self.sensors:
            del self.sensors[sensor_type]
            self.database_manager.remove_sensor(sensor_type)
        else:
            print(f"Cannot remove sensor with sensor name '{sensor_type}' because it is not found.")

    def read_all_sensors(self):
        """
        Reads data from all sensors.

        Returns:
            dict: A dictionary containing the readings from all sensors.
        """
        readings = {}
        for sensor_type, sensor in self.sensors.items():
            reading = sensor.read()
            if reading['temperature'] is None or reading['humidity'] is None:
                print(f"Invalid {sensor_type} readings: {reading}")
                continue
            readings[sensor_type] = reading
            print(f"Sensor manager name: {sensor_type} Reading: {readings}")
        return readings
