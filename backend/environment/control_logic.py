"""
ControlLogic: AI + PID climate control for plant growth.

Author: Sebastian Gomez
Date: 2024
"""

from environment.control_algorithms import PIDController, MLController
from utils.event_bus import EventBus
import logging
import csv
import datetime
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
import joblib

class ControlLogic:
    """
    Uses AI and PID controllers to manage temperature, humidity, and soil moisture.
    """
    def __init__(self, actuator_manager, database_manager, use_ml_control=False, log_file="plant_growth_data.csv"):
        """
        Initializes the control logic.

        Args:
            actuator_manager: Manages actuators.
            database_manager: Manages the database.
            use_ml_control (bool): Flag to use MLController.
            log_file (str): File to log the data
        """
        self.actuator_manager = actuator_manager
        self.event_bus = EventBus()
        self.use_ml_control = use_ml_control
        self.log_file = log_file
        self.available_actuators = ['Light', 'Fan', 'Heater', 'Cooler', 'Humidifier', 'Dehumidifier', 'CO2Injector'] # from user input

        # PID or ML Controllers for Temperature, Humidity, and Soil Moisture
        if use_ml_control:
            # self.temp_model = joblib.load("models/temp_model.pkl")
            # self.humidity_model = joblib.load("models/humidity_model.pkl")
            # self.soil_moisture_model = joblib.load("models/soil_moisture_model.pkl")
            self.temp_controller = MLController(model=LinearRegression(), setpoint=24.0) # replace LinearRegression()
            self.humidity_controller = MLController(model=LinearRegression(), setpoint=50.0)
            self.soil_moisture_controller = MLController(model=LinearRegression(), setpoint=30.0)
        else:
            self.temp_controller = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=24.0)
            self.humidity_controller = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=50.0)
            self.soil_moisture_controller = PIDController(kp=1.0, ki=0.1, kd=0.05, setpoint=30.0)

        # Create log file header
        self.log_header = [
            "timestamp", "temperature", "humidity", "soil_moisture", "co2", "light", "growth_stage",
            "heater_state",  "cooler_state","humidifier_state", "dehumidifier_state", "water_pump_state", "fan_state", "co2_injector_state", "light_state",
            "growth_rate", "health_metrics"
        ]
        with open(self.log_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.log_header)

    def _log_data(self, data):
        """
        Logs sensor, actuator, and plant growth data to a CSV file.
        """
        timestamp = datetime.datetime.now().isoformat()
        log_data = [timestamp] + [data.get(key, "") for key in self.log_header[1:]]
        with open(self.log_file, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(log_data)

    def control_temperature(self, data):
        """Controls temperature using AI and PID models."""
        temperature = float(data["temperature"])

        control_signal = self.temp_controller.compute(temperature, self.temp_controller.setpoint)

        if control_signal > 0 and "Heater" in self.available_actuators:
            self.actuator_manager.activate_actuator("Heater")
            heater_state = "on"
            cooler_state = "off"
        elif control_signal < 0 and "Cooler" in self.available_actuators:
            self.actuator_manager.activate_actuator("Cooler")
            heater_state = "off"
            cooler_state = "on"
        else:
            if "Heater" in self.available_actuators:
                self.actuator_manager.deactivate_actuator("Heater")
            if "Cooler" in self.available_actuators:
                self.actuator_manager.deactivate_actuator("Cooler")
            heater_state = "off"
            cooler_state = "off"

        log_data = {
            "temperature": temperature,
            "heater_state": heater_state,
            "cooler_state": cooler_state,
            "growth_stage": self.growth_stage,
        }
        self._log_data(log_data)
        logging.info(f"🔥 Temperature Control: {temperature}°C, Heater State: {heater_state}, Cooler State: {cooler_state}")

    def control_humidity(self, data):
        """Controls humidity based on AI model and PID adjustments."""
        humidity = float(data["humidity"])
        control_signal = self.humidity_controller.compute(humidity, self.humidity_controller.setpoint)
        if control_signal > 0 and "Humidifier" in self.available_actuators:
            self.actuator_manager.activate_actuator("Humidifier")
            humidifier_state = "on"
            dehumidifier_state = "off"
        elif control_signal < 0 and "Dehumidifier" in self.available_actuators:
            self.actuator_manager.activate_actuator("Dehumidifier")
            humidifier_state = "off"
            dehumidifier_state = "on"
        else:
            if "Humidifier" in self.available_actuators:
                self.actuator_manager.deactivate_actuator("Humidifier")
            if "Dehumidifier" in self.available_actuators:
                 self.actuator_manager.deactivate_actuator("Dehumidifier")
            humidifier_state = "off"
            dehumidifier_state = "off"

        log_data = {
            "humidity": humidity,
            "humidifier_state": humidifier_state,
            "dehumidifier_state": dehumidifier_state,
            "growth_stage": self.growth_stage,
        }
        self._log_data(log_data)
        logging.info(f"💧 Humidity Control: {humidity}%, Humidifier State: {humidifier_state}, Dehumidifier State: {dehumidifier_state}")

    def control_soil_moisture(self, data):
        """Controls soil moisture."""
        soil_moisture = float(data["soil_moisture"])
        control_signal = self.soil_moisture_controller.compute(soil_moisture, self.soil_moisture_controller.setpoint)
        if control_signal > 0 and "Water-Pump" in self.available_actuators:
            self.actuator_manager.activate_actuator("Water-Pump")
            water_pump_state = "on"
        else:
            if "Water-Pump" in self.available_actuators:
                self.actuator_manager.deactivate_actuator("Water-Pump")
            water_pump_state = "off"

        log_data = {
            "soil_moisture": soil_moisture,
            "water_pump_state": water_pump_state,
            "growth_stage": self.growth_stage,
        }
        self._log_data(log_data)
        logging.info(f"🌱 Soil Moisture Control: {soil_moisture}%, Water Pump State: {water_pump_state}")

    def update_thresholds(self, data):
        """Updates the setpoints for the PID controllers."""
        self.temp_controller.setpoint = data.get("temperature", self.temp_controller.setpoint)
        self.humidity_controller.setpoint = data.get("humidity", self.humidity_controller.setpoint)
        self.soil_moisture_controller.setpoint = data.get("soil_moisture", self.soil_moisture_controller.setpoint)