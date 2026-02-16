import os

try:
    import adafruit_ads1x15.ads1115 as ADS

    HAS_ADS1115 = True
except ImportError:
    # Mock ADS constants for non-hardware environments
    class MockADS:
        P0, P1, P2, P3 = "P0", "P1", "P2", "P3"

    ADS = MockADS()
    HAS_ADS1115 = False

try:
    import smbus

    HAS_SMBUS = True
except ImportError:
    HAS_SMBUS = False


class Config:
    DATABASE = os.getenv("DATABASE_PATH", "database/sysgrow.db")


class SystemConfigDefaults:
    TEMPERATURE_THRESHOLD = 25  # Example threshold value
    HUMIDITY_THRESHOLD = 50  # Example threshold value
    SOIL_MOISTURE_THRESHOLD = 30  # Example threshold value
    HYSTERESIS = 2  # Example hysteresis value
    DHT11_PIN = 4  # Example GPIO pin for DHT11 sensor

    ADC_CHANNEL_MAP = {"P0": ADS.P0, "P1": ADS.P1, "P2": ADS.P2, "P3": ADS.P3}

    # Mapping of GPIO pins to their names
    GPIO_PINS = {
        2: "GPIO2",
        3: "GPIO3",
        4: "GPIO4",
        17: "GPIO17",
        27: "GPIO27",
        22: "GPIO22",
        10: "GPIO10",
        9: "GPIO9",
        11: "GPIO11",
        0: "GPIO0",
        5: "GPIO5",
        6: "GPIO6",
        13: "GPIO13",
        19: "GPIO19",
        26: "GPIO26",
        14: "GPIO14",
        15: "GPIO15",
        18: "GPIO18",
        23: "GPIO23",
        24: "GPIO24",
        25: "GPIO25",
        8: "GPIO8",
        7: "GPIO7",
        1: "GPIO1",
        12: "GPIO12",
        16: "GPIO16",
        20: "GPIO20",
        21: "GPIO21",
    }

    PLANTS_INFO = [
        {
            "name": "Leafy Greens",
            "growth_stages": [
                {
                    "stage": "Germination",
                    "time": "3-7",
                    "temperature": "18-24",
                    "humidity": "50-70",
                    "lighting": "14-16",
                },
                {
                    "stage": "Seedling",
                    "time": "14-21",
                    "temperature": "18-24",
                    "humidity": "50-70",
                    "lighting": "14-16",
                },
                {
                    "stage": "Vegetative",
                    "time": "28-42",
                    "temperature": "18-24",
                    "humidity": "50-70",
                    "lighting": "14-16",
                },
                {"stage": "Harvest", "time": "42-56", "temperature": "18-24", "humidity": "50-70", "lighting": "14-16"},
            ],
            "tips": "Avoid high temperatures to prevent bolting. Maintain consistent moisture.",
        },
        {
            "name": "Tomatoes",
            "growth_stages": [
                {
                    "stage": "Germination",
                    "time": "5-10",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-18",
                },
                {
                    "stage": "Seedling",
                    "time": "21-28",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-18",
                },
                {
                    "stage": "Vegetative",
                    "time": "28-42",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-18",
                },
                {
                    "stage": "Flowering",
                    "time": "7-14",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-18",
                },
                {
                    "stage": "Fruit Development",
                    "time": "42-56",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-18",
                },
                {"stage": "Harvest", "time": "60-85", "temperature": "22-28", "humidity": "40-60", "lighting": "16-18"},
            ],
            "tips": "Support plants with stakes or cages. Ensure good airflow to prevent fungal diseases.",
        },
        {
            "name": "Peppers",
            "growth_stages": [
                {
                    "stage": "Germination",
                    "time": "7-14",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-18",
                },
                {
                    "stage": "Seedling",
                    "time": "21-28",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-18",
                },
                {
                    "stage": "Vegetative",
                    "time": "28-42",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-18",
                },
                {
                    "stage": "Flowering",
                    "time": "14-21",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-18",
                },
                {
                    "stage": "Fruit Development",
                    "time": "56-70",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-18",
                },
                {"stage": "Harvest", "time": "70-90", "temperature": "22-28", "humidity": "40-60", "lighting": "16-18"},
            ],
            "tips": "Peppers benefit from slightly dry conditions between watering.",
        },
        {
            "name": "Herbs",
            "growth_stages": [
                {
                    "stage": "Germination",
                    "time": "5-14",
                    "temperature": "18-24",
                    "humidity": "50-70",
                    "lighting": "14-16",
                },
                {
                    "stage": "Seedling",
                    "time": "14-21",
                    "temperature": "18-24",
                    "humidity": "50-70",
                    "lighting": "14-16",
                },
                {
                    "stage": "Vegetative",
                    "time": "28-56",
                    "temperature": "18-24",
                    "humidity": "50-70",
                    "lighting": "14-16",
                },
                {"stage": "Harvest", "time": "28-56", "temperature": "18-24", "humidity": "50-70", "lighting": "14-16"},
            ],
            "tips": "Regularly trim to promote bushier growth and prevent flowering.",
        },
        {
            "name": "Cucumbers",
            "growth_stages": [
                {
                    "stage": "Germination",
                    "time": "3-7",
                    "temperature": "24-29",
                    "humidity": "40-70",
                    "lighting": "16-18",
                },
                {
                    "stage": "Seedling",
                    "time": "14-21",
                    "temperature": "24-29",
                    "humidity": "40-70",
                    "lighting": "16-18",
                },
                {
                    "stage": "Vegetative",
                    "time": "28-42",
                    "temperature": "24-29",
                    "humidity": "40-70",
                    "lighting": "16-18",
                },
                {
                    "stage": "Flowering",
                    "time": "7-14",
                    "temperature": "24-29",
                    "humidity": "40-70",
                    "lighting": "16-18",
                },
                {
                    "stage": "Fruit Development",
                    "time": "28-42",
                    "temperature": "24-29",
                    "humidity": "40-70",
                    "lighting": "16-18",
                },
                {"stage": "Harvest", "time": "50-70", "temperature": "24-29", "humidity": "40-70", "lighting": "16-18"},
            ],
            "tips": "Provide trellising for vertical growth. Maintain consistent watering.",
        },
        {
            "name": "Strawberries",
            "growth_stages": [
                {
                    "stage": "Germination",
                    "time": "7-14",
                    "temperature": "18-24",
                    "humidity": "40-60",
                    "lighting": "12-16",
                },
                {
                    "stage": "Vegetative",
                    "time": "28-42",
                    "temperature": "18-24",
                    "humidity": "40-60",
                    "lighting": "12-16",
                },
                {
                    "stage": "Flowering",
                    "time": "14-21",
                    "temperature": "18-24",
                    "humidity": "40-60",
                    "lighting": "12-16",
                },
                {
                    "stage": "Fruit Development",
                    "time": "28-42",
                    "temperature": "18-24",
                    "humidity": "40-60",
                    "lighting": "12-16",
                },
                {"stage": "Harvest", "time": "70-90", "temperature": "18-24", "humidity": "40-60", "lighting": "12-16"},
            ],
            "tips": "Keep the soil slightly acidic (pH 5.5-6.5). Avoid wetting the foliage to prevent fungal diseases.",
        },
        {
            "name": "Carrots",
            "growth_stages": [
                {
                    "stage": "Germination",
                    "time": "7-14",
                    "temperature": "18-24",
                    "humidity": "40-60",
                    "lighting": "12-16",
                },
                {
                    "stage": "Seedling",
                    "time": "21-28",
                    "temperature": "18-24",
                    "humidity": "40-60",
                    "lighting": "12-16",
                },
                {
                    "stage": "Vegetative",
                    "time": "42-56",
                    "temperature": "18-24",
                    "humidity": "40-60",
                    "lighting": "12-16",
                },
                {"stage": "Harvest", "time": "70-80", "temperature": "18-24", "humidity": "40-60", "lighting": "12-16"},
            ],
            "tips": "Thin seedlings to prevent overcrowding. Ensure deep, loose soil for root growth.",
        },
        {
            "name": "Cannabis",
            "growth_stages": [
                {
                    "stage": "Germination",
                    "time": "3-7",
                    "temperature": "22-28",
                    "humidity": "70-90",
                    "lighting": "18-24",
                },
                {
                    "stage": "Seedling",
                    "time": "10-14",
                    "temperature": "20-25",
                    "humidity": "65-70",
                    "lighting": "18-24",
                },
                {
                    "stage": "Vegetative",
                    "time": "21-42",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "16-22",
                },
                {
                    "stage": "Flowering",
                    "time": "42-63",
                    "temperature": "20-26",
                    "humidity": "40-50",
                    "lighting": "12-12",
                },
                {"stage": "Harvest", "time": "7-14", "temperature": "18-24", "humidity": "30-40", "lighting": "12-12"},
            ],
            "tips": "Ensure good ventilation and prevent overwatering. Use appropriate nutrient levels for each stage.",
        },
        {
            "name": "Autoflowering Cannabis",
            "growth_stages": [
                {
                    "stage": "Germination",
                    "time": "3-7",
                    "temperature": "22-26",
                    "humidity": "70-90",
                    "lighting": "18-24",
                },
                {"stage": "Seedling", "time": "7-10", "temperature": "20-25", "humidity": "60-70", "lighting": "18-24"},
                {
                    "stage": "Vegetative",
                    "time": "14-21",
                    "temperature": "22-28",
                    "humidity": "40-60",
                    "lighting": "18-24",
                },
                {
                    "stage": "Flowering",
                    "time": "28-42",
                    "temperature": "20-26",
                    "humidity": "40-50",
                    "lighting": "18-24",
                },
                {"stage": "Harvest", "time": "7-10", "temperature": "18-24", "humidity": "30-40", "lighting": "18-24"},
            ],
            "tips": "Autoflowering strains are generally easier to grow, require less maintenance, and have a shorter lifecycle.",
        },
    ]

    SENSOR_TEMPLATES = [
        # 📟 PIN-Based Sensors (select mode first → then type)
        {
            "name": "BME280 (I2C)",
            "mode": "PIN",
            "type": "environment",
            "communication": "I2C",
            "parameters": ["temperature", "humidity", "pressure"],
            "address": "0x76",
        },
        {
            "name": "DHT11 (GPIO)",
            "mode": "PIN",
            "type": "environment",
            "communication": "GPIO",
            "parameters": ["temperature", "humidity"],
            "gpio": 4,
        },
        {
            "name": "ENS160 + AHT21 (I2C)",
            "mode": "PIN",
            "type": "environment",
            "communication": "I2C",
            "parameters": ["eco2", "tvoc", "temperature", "humidity"],
            "address": "0x53",
        },
        {
            "name": "TSL2591 (I2C)",
            "mode": "PIN",
            "type": "light",
            "communication": "I2C",
            "parameters": ["lux", "full_spectrum", "infrared", "visible"],
            "address": "0x29",
        },
        {
            "name": "MQ2 (Digital GPIO)",
            "mode": "PIN",
            "type": "gas",
            "communication": "GPIO",
            "parameters": ["smoke"],
            "gpio": 17,
        },
        {
            "name": "Soil Moisture Sensor (ADC)",
            "mode": "PIN",
            "type": "plant",
            "communication": "ADC",
            "parameters": ["soil_moisture"],
            "channel": "P0",
        },
        # 📡 Wireless Sensors (select mode first → then type)
        {
            "name": "Wireless Soil Node (MQTT)",
            "mode": "WIRELESS",
            "type": "plant",
            "communication": "MQTT",
            "parameters": ["soil_moisture"],
            "mqtt_topic": "growtent/<unit_id>/sensor/soil_moisture",
            "update_interval": "10min",
        },
        {
            "name": "Wireless Env Node (Redis)",
            "mode": "WIRELESS",
            "type": "environment",
            "communication": "Redis",
            "parameters": {
                "temperature": "Temperature",
                "humidity": "Humidity",
                "eco2": "CO2",
                "voc": "Total Volatile Organic Compound",
                "aqi": "Air Quality Index",
            },
            "redis_keys": ["unit:<unit_id>:sensor:temperature"],
            "update_interval": "1min",
        },
        {
            "name": "Light",
            "mode": "WIRELESS",
            "type": "environment",
            "communication": "MQTT",
            "parameters": ["lux"],
            "mqtt_topic": "growtent/<unit_id>/sensor/lux",
            "update_interval": "2min",
        },
    ]

    # Track used GPIO pins
    used_pins = set()

    @classmethod
    def get_available_gpio_pins(cls):
        """Returns available GPIO pins (not in use)"""
        return {pin: name for pin, name in cls.GPIO_PINS.items() if pin not in cls.used_pins}

    @classmethod
    def get_all_gpio_pins(cls):
        """Returns all GPIO pins"""
        return cls.GPIO_PINS

    @classmethod
    def get_adc_channels(cls):
        """Returns available ADS1115 channels"""
        return {
            "P0": "ADS1115 Channel 0 (A0)",
            "P1": "ADS1115 Channel 1 (A1)",
            "P2": "ADS1115 Channel 2 (A2)",
            "P3": "ADS1115 Channel 3 (A3)",
        }

    @classmethod
    def is_hardware_available(cls):
        """Check if we're running on hardware with actual GPIO/I2C support"""
        return HAS_ADS1115 and HAS_SMBUS

    @classmethod
    def reserve_pin(cls, pin):
        """Mark a GPIO pin as used"""
        cls.used_pins.add(pin)

    @classmethod
    def release_pin(cls, pin):
        """Mark a GPIO pin as available"""
        cls.used_pins.discard(pin)

    @classmethod
    def scan_i2c_devices(cls):
        """Scan for I2C devices on the bus"""
        if not HAS_SMBUS:
            # smbus not available (non-Pi environment)
            return []

        try:
            bus = smbus.SMBus(1)  # I2C bus 1 on Raspberry Pi
            devices = []
            for addr in range(0x03, 0x77):
                try:
                    bus.write_quick(addr)
                    devices.append(hex(addr))
                except Exception:
                    continue
            return devices
        except Exception:
            return []
