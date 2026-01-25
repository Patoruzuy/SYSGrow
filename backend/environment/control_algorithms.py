from abc import ABC, abstractmethod
import logging
import numpy as np

"""
ControlLogic: AI + PID climate control for plant growth.

Author: Sebastian Gomez
Date: 2024
"""

logging.basicConfig(level=logging.INFO, filename="devices_system.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class Controller(ABC):
    """
    Abstract base class for all controllers.
    """
    @abstractmethod
    def compute(self, current_value, setpoint):
        """
        Computes the control output.

        Args:
            current_value (float): The current sensor value.
            setpoint (float): The target setpoint.

        Returns:
            float: The control output.
        """
        pass

class PIDController(Controller):
    """
    A PID controller class.
    """
    def __init__(self, kp, ki, kd, setpoint):
        """
        Initializes the PIDController.
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.integral = 0
        self.previous_error = 0

    def compute(self, current_value, setpoint):
        """
        Computes the PID control output.

        Args:
            current_value (float): The current sensor value.
            setpoint (float): The target setpoint.

        Returns:
            float: The control output.
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

class MLController(Controller):
    """
    A controller that uses a machine learning model.
    """
    def __init__(self, model, setpoint):
        """
        Initializes the MLController.

        Args:
            model: A trained machine learning model.
            setpoint (float): The target setpoint.
        """
        self.model = model
        self.setpoint = setpoint

    def compute(self, current_value, setpoint):
        """
        Computes the control output using the ML model.

        Args:
            current_value (float): The current sensor value.
            setpoint (float): The target setpoint.

        Returns:
            float: The computed control output.
        """
        input_data = np.array([[current_value, setpoint]])
        output = self.model.predict(input_data)[0]
        return output
