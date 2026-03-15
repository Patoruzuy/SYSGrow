from abc import ABC, abstractmethod
from sensors.co2_sensor import ENS160_AHT21Sensor
from sensors.soil_moisture_sensor import SoilMoistureSensorV2
from sensors.mq2_sensor import MQ2Sensor
from sensors.light_sensor import TSL2591Driver


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

class ENS160AHT21Sensor(Sensor):
    """
    Class to represent an ENS160 + AHT21 sensor for monitoring air quality, temperature, and humidity.

    Attributes:
        i2c_bus (int): The I2C bus number where the sensor is connected.
        sensor (ENS160AHT21Sensor): The sensor instance.
    """
    def __init__(self, i2c_bus, sensor_id):
        """
        Initializes the ENS160 + AHT21 sensor with a specified I2C bus.

        Args:
            i2c_bus (int): The I2C bus number to which the sensor is connected.
        """
        self.id = sensor_id  # ID assigned by the database
        self.name = None
        self.i2c_bus = i2c_bus
        self.sensor = ENS160_AHT21Sensor(self.i2c_bus)

    def read(self):
        """
        Reads the air quality, temperature, and humidity from the ENS160 + AHT21 sensor.

        Returns:
            dict: A dictionary containing air quality, temperature, and humidity.
        """
        try:
            data = self.sensor.read()
            return {
                'sensor_id': self.id,
                'sensor_type': 'temp_humidity_sensor',
                'sensor_name': self.name,
                'co2': data['co2'],
                'voc': data['voc'],
                'temperature': data['temperature'],
                'humidity': data['humidity']
            }
        except Exception as e:
            print(f"Error reading ENS160 + AHT21 sensor: {e}")
            return {
                'sensor_id': self.id,
                'sensor_type': 'temp_humidity_sensor',
                'sensor_name': self.name,
                'error': str(e)
            }

class TSL2591Sensor(Sensor):
    """
    Class to represent a TSL2591 Lux sensor for measuring light intensity.

    Attributes:
        i2c_bus (int): The I2C bus number where the sensor is connected.
        sensor (TSL2591): The TSL2591 sensor instance.
    """
    def __init__(self, i2c_bus, sensor_id):
        """
        Initializes the TSL2591 sensor with a specified I2C bus.

        Args:
            i2c_bus (int): The I2C bus number to which the sensor is connected.
        """
        self.id = sensor_id  # ID assigned by the database
        self.name = None
        self.i2c_bus = i2c_bus
        # Assuming there is a driver class for the TSL2591 sensor
        self.sensor = TSL2591Driver(self.i2c_bus)

    def read(self):
        """
        Reads the light intensity from the TSL2591 sensor.

        Returns:
            dict: A dictionary containing the lux value.
        """
        try:
            lux = self.sensor.read_lux()
            return {
                'sensor_id': self.id,
                'sensor_type': 'lux_sensor',
                'sensor_name': self.name,
                'lux': lux
            }
        except Exception as e:
            print(f"Error reading TSL2591 sensor: {e}")
            return {
                'sensor_id': self.id,
                'sensor_type': 'lux_sensor',
                'sensor_name': self.name,
                'error': str(e)
            }

class SoilMoistureSensor(Sensor):
    """
    Class to represent a soil moisture sensor for a plant.
    
    Attributes:
        pin (int): ADC channel where the soil moisture sensor is connected.
        sensor (SoilMoistureSensorV2): The soil moisture sensor instance.
        count (int): Class variable to track the number of instances.
    """
    count = 0  # Class variable to keep track of the number of SoilMoistureSensor instances

    def __init__(self, pin, sensor_id):
        """
        Initializes the SoilMoistureSensor with a specified ADC channel.

        Args:
            pin (int): The ADC channel where the soil moisture sensor is connected.
        """
        self.id = sensor_id  # ID assigned by the database
        self.name = None
        self.pin = pin
        self.sensor = SoilMoistureSensorV2(self.pin)
        self.instance_count = SoilMoistureSensor.count  # Unique count for this instance

    def set_name(self, name):
        """
        Sets the name for the sensor.

        Args:
            name (str): The name to set for the sensor.
        """
        self.name = name

    def set_count(self):
        """
        Increases the sensor count by 1 and updates the instance count.
        """
        SoilMoistureSensor.count += 1
        self.instance_count = SoilMoistureSensor.count

    def get_count(self) -> int:
        """
        Returns the sensor's unique count.

        Returns:
            int: The instance count for this specific sensor.
        """
        return self.instance_count

    def read(self):
        """
        Reads the soil moisture level from the sensor.

        Returns:
            dict: A dictionary containing the soil moisture level and other relevant information.
        """
        try:
            moisture_level = self.sensor.read()
            moisture_level = moisture_level.get('soil_moisture')
            return {
                'sensor_id': self.id,
                'sensor_type': 'soil_sensor',
                'sensor_name': self.name,
                'reading': moisture_level
            }
        except Exception as e:
            print(f"Error reading soil moisture level: {e}")
            return {
                'sensor_id': self.id,
                'sensor_type': 'soil_sensor',
                'sensor_name': self.name,
                'error': str(e)
            }

class SmokeSensor(Sensor):

    def __init__(self, pin, is_digital, sensor_id):
        """
        Initializes the SmokeSensor with a specified GPIO pin.

        Args:
            pin (int): The GPIO pin number to which the MQ2 sensor is connected.
            is_digital (bool): True if the sensor reads digital signal, False otherwise (Analog output) 
        """
        self.id = sensor_id  # ID assigned by the database
        self.pin = pin
        self.is_digital = is_digital
        self.mq2_sensor = MQ2Sensor(self.pin, is_digital)

        
    def read(self):
        """
        Reads the smoke level from the smoke sensor.

        Returns:
            dict: A dictionary containing the smoke level (Analogic) or a boolean value (Digital).
        """
        if self.is_digital:
            data = self.mq2_sensor.read()
        else:
            data = self.mq2_sensor.read_analog()
        if data:
            return {'error': 'Failed to get reading. Try again!'}
        return {'Smoke': data['Smoke']}


class SensorManager:
    """
    Manages multiple Sensor objects, loading their configurations from a database.

    Attributes:
        database_manager (DatabaseManager): An instance of the database manager.
        sensors (dict): A dictionary of Sensor objects keyed by model.

    Methods:
        get_sensor_by_model(model): Retrieves a sensor by its model.
        add_sensor(name, gpio, ip_address, type, model): Adds a new sensor.
        remove_sensor(model): Removes a specified sensor by model.
        read_all_sensors(): Reads data from all sensors.
    """
    
    def __init__(self, database_handler):
        """
        Initializes a SensorManager object.

        Args:
            database_manager (DatabaseManager): An instance of the database manager.
        """
        self.database_handler = database_handler
        self.sensors = self._load_sensors_from_db()

    def _load_sensors_from_db(self):
        """
        Loads sensor configurations from the database and creates Sensor objects.

        Returns:
            dict: A dictionary of Sensor objects keyed by their unique identifiers.
        """
        sensors = {}
        sensor_configs = self.database_handler.get_sensor_configs()
        for config in sensor_configs:
            sensor_id = config['sensor_id']

            if config['sensor_model'] == 'Soil-Moisture':
                sensor = SoilMoistureSensor(pin=config['gpio'], sensor_id=sensor_id)
                sensor.set_name(config['name'])
            elif config['sensor_model'] == 'ENS160AHT21':
                sensor = ENS160AHT21Sensor(i2c_bus=1, sensor_id=sensor_id)
            elif config['sensor_model'] == 'TSL2591':
                sensor = TSL2591Sensor(i2c_bus=1, sensor_id=sensor_id)
            else:
                print(f"Unknown sensor model: {config['sensor_model']}")
                continue

            if sensor:
                sensors[sensor_id] = sensor
                print(f"Loaded sensor: {sensor_id}, Object: {sensor}")
            else:
                print(f"Failed to create sensor for ID: {sensor_id}")

        return sensors
        
    def get_sensors(self):
        """
        Returns the keys (names) of all managed sensors.

        Returns:
            list: A list of sensor keys (names).
        """
        return list(self.sensors.keys())

    def get_sensor_by_model(self, sensor_model, count=None):
        """
        Retrieves a Sensor object by its model and optional count.

        Args:
            sensor_model (str): The model or type of the sensor to retrieve.
            count (int, optional): The unique count identifier for the sensor.

        Returns:
            Sensor: The Sensor object with the specified model and count, or None if not found.
        """
        key = sensor_model if count is None else f"{sensor_model}{count}"
        return self.sensors.get(key)

    def get_sensor_by_id(self, sensor_id: int):
        """
        Retrieves sensor information by its ID.

        Args:
            sensor_id (int): The ID of the sensor.

        Returns:
            Sensor: The sensor object.
        """
        print(f"Searching for sensor_id: {sensor_id} in sensors: {list(self.sensors.keys())}")
        sensor = self.sensors.get(sensor_id)
        print(f"Found sensor: {sensor}")
        return sensor

    def add_sensor(self, sensor_name, sensor_type, sensor_model, gpio, ip_address=None):
        """
        Adds a new sensor to the manager.

        Args:
            sensor_name (str): The name of the sensor.
            sensor_type (str): The type of the sensor.
            sensor_model (str): The model or name of the sensor.
            gpio (int, optional): The GPIO pin number for control.
            ip_address (str, optional): The IP address for wireless control.
        """
        sensor_id = self.database_manager.insert_sensor(sensor_name, sensor_type, sensor_model, gpio, ip_address)

        if sensor_model == 'Soil-Moisture':
            sensor = SoilMoistureSensor(pin=gpio, sensor_id=sensor_id)
            sensor.set_name(sensor_name)
        elif sensor_model == 'ENS160AHT21':
            sensor = ENS160AHT21Sensor(i2c_bus=1, sensor_id=sensor_id)
        elif sensor_model == 'TSL2591':
            sensor = TSL2591Sensor(i2c_bus=1, sensor_id=sensor_id)
        else:
            print(f"Unknown sensor model: {sensor_model}")
            return

        if sensor:
            print(f"Added sensor '{sensor}' with ID {sensor_id} to the SensorManager.")
            self.sensors[sensor_id] = sensor

    def remove_sensor(self, sensor_id):
        """
        Removes the specified sensor id.

        Args:
            sensor_type (str): The type of the sensor to remove.
        """
        if sensor_id in self.sensors:
            del self.sensors[sensor_id]
            self.database_manager.remove_sensor(sensor_id)
        else:
            print(f"Cannot remove sensor with ID '{sensor_id}' because it is not found.")


    def read_all_sensors(self):
        """
        Reads data from all sensors.

        Returns:
            dict: A dictionary containing the readings from all sensors, including pin numbers.
        """
        readings = {}
        for sensor_id, sensor in self.sensors.items():
            readings[sensor_id] = sensor.read()
        return readings
