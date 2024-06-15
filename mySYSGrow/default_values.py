import os

class Config:
    DATABASE = os.getenv('DATABASE_PATH', 'database/grow_tent.db')
    

class DefaultValues():
    TEMPERATURE_THRESHOLD = 25  # Example threshold value
    HUMIDITY_THRESHOLD = 50  # Example threshold value
    SOIL_MOISTURE_THRESHOLD = 30  # Example threshold value
    HYSTERESIS = 2  # Example hysteresis value
    DHT11_PIN = 4  # Example GPIO pin for DHT11 sensor

    ADC_CHANNEL_MAP = {
    'P0': ADS.P0,
    'P1': ADS.P1,
    'P2': ADS.P2,
    'P3': ADS.P3
    }   

    # Mapping of GPIO pins to their names
    GPIO_PINS = {
        2: 'GPIO2',
        3: 'GPIO3',
        4: 'GPIO4',
        17: 'GPIO17',
        27: 'GPIO27',
        22: 'GPIO22',
        10: 'GPIO10',
        9: 'GPIO9',
        11: 'GPIO11',
        0: 'GPIO0',
        5: 'GPIO5',
        6: 'GPIO6',
        13: 'GPIO13',
        19: 'GPIO19',
        26: 'GPIO26',
        14: 'GPIO14',
        15: 'GPIO15',
        18: 'GPIO18',
        23: 'GPIO23',
        24: 'GPIO24',
        25: 'GPIO25',
        8: 'GPIO8',
        7: 'GPIO7',
        1: 'GPIO1',
        12: 'GPIO12',
        16: 'GPIO16',
        20: 'GPIO20',
        21: 'GPIO21'
    }

    # Track used GPIO pins
    used_pins = set()

    def get_available_gpio_pins():
        return {pin: name for pin, name in GPIO_PINS.items() if pin not in used_pins}
