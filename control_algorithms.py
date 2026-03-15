from abc import ABC, abstractmethod

class Controller(ABC):
    @abstractmethod
    def compute(self, current_value):
        """
        Abstract method to compute the control output based on the current value.

        Args:
            current_value (float): The current value to be controlled.

        Returns:
            float: The control output.
        """
        pass

class PIDController(Controller):
    """
    A PID controller class for calculating the control signal to minimize the error.

    Attributes:
        kp (float): Proportional gain.
        ki (float): Integral gain.
        kd (float): Derivative gain.
        setpoint (float): Desired setpoint value.
        integral (float): Integral term accumulator.
        previous_error (float): Previous error value for derivative calculation.
    """

    def __init__(self, kp, ki, kd, setpoint):
        """
        Initializes the PIDController with specified gains and setpoint.

        Args:
            kp (float): Proportional gain.
            ki (float): Integral gain.
            kd (float): Derivative gain.
            setpoint (float): Desired setpoint value.
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        self.integral = 0
        self.previous_error = 0

    def compute(self, current_value):
        """
        Computes the PID control output based on the current value.

        Args:
            current_value (float): The current value to be controlled.

        Returns:
            float: The computed control output.
        """
        # Calculate the error
        error = self.setpoint - current_value
        
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
    def __init__(self, model, setpoint):
        self.model = model
        self.setpoint = setpoint

    def compute(self, current_value):
        # Needs to implement ML-based control logic 
        input_features = [current_value, self.setpoint]
        output = self.model.predict(input_features)
        return output
