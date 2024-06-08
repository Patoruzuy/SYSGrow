class SoilMoistureSensorV2:
    def __init__(self, adc_channel):
        """
        Initializes the SoilMoistureSensor.
        
        Args:
            adc_channel (int): ADC channel where the soil moisture sensor is connected.
        """
        self.adc_channel = adc_channel
        from Adafruit_ADS1x15 import ADS1x15
        self.adc = ADS1x15()

    def read(self):
        """
        Reads the soil moisture level from the sensor.
        
        Returns:
            dict: A dictionary containing 'soil_moisture'.
        """
        try:
            # Read soil moisture value from ADC
            moisture_level = self.adc.read_adc(self.adc_channel, gain=1)
            return {'soil_moisture': moisture_level}
        except Exception as e:
            print(f"Error reading soil moisture level: {e}")
            return None
