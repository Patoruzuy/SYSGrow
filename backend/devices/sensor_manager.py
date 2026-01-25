from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from sensors.co2_sensor import ENS160_AHT21Sensor
from sensors.soil_moisture_sensor import SoilMoistureSensorV2
from sensors.mq2_sensor import MQ2Sensor
from sensors.light_sensor import TSL2591Driver
from utils.event_bus import EventBus
import redis


class Sensor(ABC):
    """
    Abstract base class representing a generic sensor.

    Methods:
        read(): Reads the sensor value(s).
    """
    @abstractmethod
    def read(self) -> dict:
        """
        Reads the sensor value(s).
        """
        pass

class ENS160_AHT21Sensor(Sensor):
    """
    Class to represent an ENS160 + AHT21 sensor for monitoring air quality, temperature, and humidity.

    Attributes:
        i2c_bus (int): The I2C bus number where the sensor is connected.
        sensor (ENS160AHT21Sensor): The sensor instance.
    """
    def __init__(self, unit_id, i2c_bus, sensor_id, communication, redis_key, redis_client):
        """
        Initializes the ENS160 + AHT21 sensor with a specified I2C bus.

        Args:
            i2c_bus (int): The I2C bus number to which the sensor is connected.
        """
        self.unit_id = unit_id
        self.id = sensor_id  # ID assigned by the database
        self.comm = communication
        self.redis_key = redis_key
        self.redis_client = redis_client
        self.name = "ENS160_AHT21Sensor_GPIO"
        self.i2c_bus = i2c_bus
        if self.comm != 'wireless':
            self.sensor = ENS160_AHT21Sensor(self.i2c_bus)

    def read(self):
        """
        Reads the air quality, temperature, and humidity from the ENS160 + AHT21 sensor.

        Returns:
            dict: A dictionary containing air quality, temperature, and humidity.
        """
        if self.comm == 'wireless':
            return self.read_redis()
        try:
            data = self.sensor.read()
            return {
                'unit_id': self.unit_id,
                'sensor_id': self.id,
                'sensor_type': 'environment_sensor',
                'sensor_name': self.name,
                'co2': data['co2'],
                'voc': data['voc'],
                'temperature': data['temperature'],
                'humidity': data['humidity']
            }
        except Exception as e:
            print(f"Error reading ENS160 + AHT21 sensor: {e}")
            return {
                'unit_id': self.unit_id,
                'sensor_id': self.id,
                'sensor_type': 'temp_humidity_sensor',
                'sensor_name': self.name,
                'error': str(e)
            }
        
    def read_redis(self):
        """
        Reads redis for the air quality, temperature, and humidity from the ENS160 + AHT21 sensor.
        """
        try:
            data = self.redis_client.get(self.redis_key)
            if not data:
                return {'error': 'No data available in Redis'}
            decoded = data.decode('utf-8')
            import json
            payload = json.loads(decoded)
            self.name = "ENS160_AHT21_Wireless"
            return {
                'unit_id': self.unit_id,
                'sensor_id': self.id,
                'sensor_type': 'environment_sensor',
                **payload
            }
        except Exception as e:
            return {'unit_id': self.unit_id, 'sensor_id': self.id, 'error': str(e)}

class TSL2591Sensor(Sensor):
    """
    Class to represent a TSL2591 Lux sensor for measuring light intensity.

    Attributes:
        i2c_bus (int): The I2C bus number where the sensor is connected.
        sensor (TSL2591): The TSL2591 sensor instance.
    """
    def __init__(self, unit_id, i2c_bus, sensor_id, redis_key, communication, redis_client):
        """
        Initializes the TSL2591 sensor with a specified I2C bus.

        Args:
            unit_id (str): The ID of the unit.
            i2c_bus (int): The I2C bus number to which the sensor is connected.
        """
        self.unit_id = unit_id
        self.id = sensor_id  # ID assigned by the database
        self.name = "TSL2591Sensor_GPIO"
        self.comm = communication
        self.redis_key = redis_key
        self.redis_client = redis_client
        self.i2c_bus = i2c_bus
        if self.comm != 'wireless':
            self.sensor = TSL2591Driver(self.i2c_bus)

    def read(self):
        """
        Reads the light intensity from the TSL2591 sensor.

        Returns:
            dict: A dictionary containing the lux value.
        """
        if self.comm == 'wireless':
            return self.read_redis()
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
                'unit_id': self.unit_id,
                'sensor_id': self.id,
                'sensor_type': 'lux_sensor',
                'sensor_name': self.name,
                'error': str(e)
            }
    
    def read_redis(self):
        """
        Reads the light intensity from the TSL2591 sensor.

        Returns:
            dict: A dictionary containing the lux value.
        """
        try:
            data = self.redis_client.get(self.redis_key)
            if not data:
                return {'error': 'No data available in Redis'}
            lux = float(data.decode('utf-8'))
            self.name = "TSL2591_Wireless"
            return {
                'unit_id': self.unit_id,
                'sensor_id': self.id,
                'sensor_type': 'lux_sensor',
                'lux': lux
            }
        except Exception as e:
            return {'unit_id': self.unit_id, 'sensor_id': self.id, 'error': str(e)}

class SoilMoistureSensor(Sensor):
    """
    Class to represent a soil moisture sensor for a plant.
    
    Attributes:
        pin (int): ADC channel where the soil moisture sensor is connected.
        sensor (SoilMoistureSensorV2): The soil moisture sensor instance.
        count (int): Class variable to track the number of instances.
    """
    count = 0  # Class variable to keep track of the number of SoilMoistureSensor instances

    def __init__(self, unit_id, pin, sensor_id, communication, redis_key, redis_client):
        """
        Initializes the SoilMoistureSensor with a specified ADC channel.

        Args:
            unit_id (str): The ID of the unit.
            pin (int): The ADC channel where the soil moisture sensor is connected.
        """
        self.unit_id = unit_id
        self.id = sensor_id  # ID assigned by the database
        self.name = "SoilMoistureSensor_GPIO"
        self.pin = pin
        self.comm = communication
        self.redis_key = redis_key
        self.redis_client = redis_client
        if self.comm != 'wireless':
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
        if self.comm == 'wireless':
            return self.read_redis()
        try:
            moisture_level = self.sensor.read()
            moisture_level = moisture_level.get('soil_moisture')
            return {
                'unit_id': self.unit_id,
                'sensor_id': self.id,
                'sensor_type': 'soil_moisture_sensor',
                'sensor_name': self.name,
                'moisture_level': moisture_level
            }
        except Exception as e:
            print(f"Error reading soil moisture level: {e}")
            return {
                'unit_id': self.unit_id,
                'sensor_id': self.id,
                'sensor_type': 'soil_sensor',
                'sensor_name': self.name,
                'error': str(e)
            }
        
    def read_redis(self):
        try:
            data = self.redis_client.get(self.redis_key)
            if not data:
                return {'error': 'No data available in Redis'}
            moisture = float(data.decode('utf-8'))
            self.name = "SoilMoistureSensor_Wireless"
            return {
                'unit_id': self.unit_id,
                'sensor_id': self.id,
                'sensor_type': 'soil_moisture_sensor',
                'moisture_level': moisture
            }
        except Exception as e:
            return {'unit_id': self.unit_id, 'sensor_id': self.id, 'error': str(e)}
        
class MQ2Sensor(Sensor):

    def __init__(self, pin, is_digital, sensor_id, communication, redis_key, redis_client):
        """
        Initializes the SmokeSensor with a specified GPIO pin.

        Args:
            pin (int): The GPIO pin number to which the MQ2 sensor is connected.
            is_digital (bool): True if the sensor reads digital signal, False otherwise (Analog output) 
        """
        self.id = sensor_id  # ID assigned by the database
        self.pin = pin
        self.comm = communication
        self.redis_key = redis_key
        self.redis_client = redis_client
        self.is_digital = is_digital
        if self.comm != 'wireless':
            self.mq2_sensor = MQ2Sensor(self.pin, is_digital)

        
    def read(self):
        """
        Reads the smoke level from the smoke sensor.

        Returns:
            dict: A dictionary containing the smoke level (Analogic) or a boolean value (Digital).
        """
        try:
            if self.is_digital:
                data = self.mq2_sensor.read()
            else:
                data = self.mq2_sensor.read_analog()
            if data:
                return {'error': 'Failed to get reading. Try again!'}
            return {'Smoke': data['Smoke']}
        except Exception as e:
            return {'unit_id': self.unit_id, 'sensor_id': self.id, 'error': str(e)}
    
    def read_redis(self):
        """
        Reads redis for the smoke level from the smoke sensor.
        """
        try:
            data = self.redis_client.get(self.redis_key)
            if not data:
                return {'error': 'No data available in Redis'}
            value = float(data.decode('utf-8'))
            self.name = "MQ2Sensor_Wireless"
            return {
                'unit_id': self.unit_id,
                'sensor_id': self.id,
                'sensor_type': 'smoke_sensor',
                'smoke': value
            }
        except Exception as e:
            return {'unit_id': self.unit_id, 'sensor_id': self.id, 'error': str(e)}

class SensorFactory:
    """
    Factory class for creating sensor instances.    
    """
    @staticmethod
    def create_sensor(sensor_type: str, unit_id: int, sensor_id: int, redis_client: Optional[redis.Redis] = None, **kwargs):
        """
        Creates a sensor instance based on the sensor type.

        Args:
            sensor_type (str): The type of sensor to create.
            unit_id (int): The ID of the unit.
            sensor_id (int): The ID of the sensor.
            **kwargs: Additional keyword arguments for sensor creation.

        Returns:
            Sensor: The sensor instance.
        """
        if sensor_type == 'Soil-Moisture':
            sensor = SoilMoistureSensor(unit_id, sensor_id, **kwargs)
            sensor_name = kwargs.get('name')
            if sensor_name:
                sensor.set_name(sensor_name)
            return sensor
        elif sensor_type == 'ENS160AHT21':
            return ENS160_AHT21Sensor(unit_id, sensor_id, **kwargs)
        elif sensor_type == 'TSL2591':
            return TSL2591Sensor(unit_id, sensor_id, **kwargs)
        elif sensor_type == 'MQ2':
            return MQ2Sensor(unit_id, sensor_id, is_digital=False, **kwargs)
        else:
            raise ValueError(f"Unknown sensor type: {sensor_type}")
        
class SensorManager:
    """
    Manages sensors in a unit, including GPIO/I2C and wireless types.

    Attributes:
        unit_id (str): Identifier of the current unit.
        database_handler (DatabaseHandler): Handles DB operations.
        event_bus (EventBus): Event publisher for system-wide updates.
        sensors (dict): All sensors indexed by sensor_id.
        gpio_sensors (dict): Sensors using GPIO/I2C protocols.
        wireless_sensors (dict): Metadata for sensors using wireless communication.
    """

    def __init__(self, unit_id: int, database_handler, redis_client: Optional[redis.Redis] = None):
        """
        Initializes the SensorManager and loads sensors from the database.

        Args:
            unit_id (int): The unit identifier.
            database_handler: Database interface for loading and saving sensor configurations.
            redis_client (Optional[redis.Redis]): Redis client for caching sensor data.
        """
        self.unit_id = unit_id
        self.database_handler = database_handler
        self.event_bus = EventBus()
        self.redis_client = redis_client
        self.sensors: Dict[int, Sensor] = {}
        self.gpio_sensors: Dict[int, Sensor] = {}
        self.wireless_sensors: Dict[int, dict] = {}
        self.reload_all_sensors()

        self.event_bus.subscribe("reload_sensors", self.reload_all_sensors)
        self.event_bus.subscribe("add_sensor", self.add_sensor)
        self.event_bus.subscribe("remove_sensor", self.remove_sensor)
        
    def update_sensor_registry(self, config: dict, sensor_id: int, comm: str, sensor: Optional[Sensor]) -> None:
        """
        Updates the sensor registry based on the communication type.

        Args:
            config (dict): Sensor configuration metadata.
            sensor_id (int): Sensor ID.
            comm (str): Communication type (GPIO or wireless).
            sensor (Optional[Sensor]): Sensor instance.
        """
        if sensor:
            self.sensors[sensor_id] = sensor
            if comm.lower () in ('gpio', 'i2c'):
                self.gpio_sensors[sensor_id] = sensor
            else:
                self.wireless_sensors[sensor_id] = config
        self.event_bus.publish("sensor_update", sensor)

    def reload_all_sensors(self) -> None:
        """
        Reloads all sensors from the database and categorizes them.
        """
        sensor_configs = self.database_handler.get_sensor_configs()
        self.sensors.clear()
        self.gpio_sensors.clear()
        self.wireless_sensors.clear()

        for config in sensor_configs:
            sensor_id = config['sensor_id']
            sensor_type = config['sensor_type']
            gpio = config.get('gpio')
            comm = config.get('communication', 'GPIO')

            sensor: Optional[Sensor] = None
            sensor = SensorFactory.create_sensor(sensor_type=sensor_type, unit_id=self.unit_id,
                                                    sensor_id=sensor_id, redis_client=self.redis_client, **config)

            self.update_sensor_registry(config, sensor_id, comm, sensor)
    
    def add_sensor(self, unit_id: int, sensor_name: str, sensor_type: str,
                   communication: str, gpio: Optional[int] = None, i2c: Optional[str] = None, ip_address: Optional[str] = None) -> None:
        """
        Adds a new sensor to the system.

        Args:
            unit_id (int): Unit ID where the sensor belongs.
            sensor_name (str): Human-readable name.
            sensor_type (str): Type of sensor (e.g., temperature, soil_moisture).
            sensor_model (str): Hardware model.
            gpio (int): GPIO pin used.
            ip_address (Optional[str]): IP address for wireless sensors.
        """
        sensor_id = self.database_manager.insert_sensor(sensor_name, sensor_type, communication, gpio, i2c, ip_address)
        config = {
            'sensor_id': sensor_id,
            'gpio': gpio,
            'i2c': i2c,
            'ip_address': ip_address,
            'name': sensor_name,
            'unit_id': unit_id,
            'communication': 'GPIO' if not ip_address else 'wireless'
        }

        sensor: Optional[Sensor] = None
        sensor = SensorFactory.create_sensor(sensor_type=sensor_type, unit_id=self.unit_id,
                                                sensor_id=sensor_id, redis_client=self.redis_client, **config)

        self.update_sensor_registry(config, sensor_id, communication, sensor)

    def remove_sensor(self, sensor_id: int) -> None:
        """
        Removes a sensor from all tracking and deletes it from the database.

        Args:
            sensor_id (int): ID of the sensor to remove.
        """
        self.sensors.pop(sensor_id, None)
        self.gpio_sensors.pop(sensor_id, None)
        self.wireless_sensors.pop(sensor_id, None)
        self.database_handler.remove_sensor(sensor_id)

    def get_sensor_by_id(self, sensor_id: int) -> Optional[Sensor]:
        """
        Retrieves a sensor by its ID.

        Args:
            sensor_id (int): Unique sensor identifier.

        Returns:
            Optional[Sensor]: The sensor instance if found.
        """
        return self.sensors.get(sensor_id)

    def get_sensors(self) -> List[int]:
        """
        Returns list of all known sensor IDs.

        Returns:
            List[int]: List of sensor IDs.
        """
        return list(self.sensors.keys())
    
    def read_all_sensors(self) -> Dict[int, dict]:
        """
        Reads all sensor values regardless of communication type.

        Returns:
            Dict[int, dict]: Dictionary of readings indexed by sensor_id.
        """
        return {sid: sensor.read() for sid, sensor in self.sensors.items()}

    def read_all_gpio_sensors(self) -> Dict[int, dict]:
        """
        Reads values from all GPIO/I2C sensors.

        Returns:
            Dict[int, dict]: Readings from GPIO sensors.
        """
        return {sid: sensor.read() for sid, sensor in self.gpio_sensors.items()}

    def get_wireless_sensor_configs(self) -> List[dict]:
        """
        Gets configuration metadata for wireless sensors.

        Returns:
            List[dict]: List of wireless sensor metadata.
        """
        return list(self.wireless_sensors.values())


