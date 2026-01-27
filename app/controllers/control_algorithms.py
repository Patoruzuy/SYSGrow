"""
Control Algorithms: PID and ML controllers for climate control.

This module provides control algorithm implementations:
- PIDController: Classic proportional-integral-derivative control
- MLController: Machine learning based control (for future use)

Author: Sebastian Gomez
Date: 2024
"""
import os
from abc import ABC, abstractmethod
import logging
from logging.handlers import RotatingFileHandler

# Module-level logger with rotation (prevents unbounded log file growth)
logger = logging.getLogger(__name__)
if not logger.handlers:
    os.makedirs("logs", exist_ok=True)
    _handler = RotatingFileHandler(
        "logs/devices.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=3,
        encoding="utf-8"
    )
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Don't duplicate to root logger


class Controller(ABC):
    """
    Abstract base class for all controllers.
    """
    @abstractmethod
    def compute(self, current_value: float, setpoint: float) -> float:
        """
        Computes the control output.

        Args:
            current_value: The current sensor value.
            setpoint: The target setpoint.

        Returns:
            The control output.
        """
        pass


class PIDController(Controller):
    """
    A PID controller class.
    
    Used for environmental control:
    - Temperature (heater/cooler)
    - Humidity (humidifier/dehumidifier)
    - CO2 (injector)
    - Light (dimmer)
    
    Note: Soil moisture/irrigation is user-controlled, not PID-controlled.
    """
    def __init__(self, kp: float, ki: float, kd: float, setpoint: float):
        """
        Initializes the PIDController.
        
        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
            setpoint: Target setpoint
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.integral = 0.0
        self.previous_error = 0.0

    def compute(self, current_value: float, setpoint: float) -> float:
        """
        Computes the PID control output.

        Args:
            current_value: The current sensor value.
            setpoint: The target setpoint.

        Returns:
            The control output.
        """
        # Calculate the error
        error = setpoint - current_value
        
        # Accumulate the integral term
        self.integral += error
        
        # Calculate the derivative term
        derivative = error - self.previous_error
        
        # Compute the PID output
        output = self.kp * error + self.ki * self.integral + self.kd * derivative
        
        # Update the previous error for the next derivative calculation
        self.previous_error = error
        
        return output

    def reset(self) -> None:
        """Reset the controller state."""
        self.integral = 0.0
        self.previous_error = 0.0


class MLController(Controller):
    """
    A controller that uses a machine learning model.
    """
    def __init__(self, model, setpoint: float):
        """
        Initializes the MLController.

        Args:
            model: A trained machine learning model.
            setpoint: The target setpoint.
        """
        self.model = model
        self.setpoint = setpoint

    def compute(self, current_value: float, setpoint: float) -> float:
        """
        Computes the control output using the ML model.

        Args:
            current_value: The current sensor value.
            setpoint: The target setpoint.

        Returns:
            The computed control output.
        """
        import numpy as np  # Lazy load
        input_data = np.array([[current_value, setpoint]])
        output = self.model.predict(input_data)[0]
        return output
