# ai/ml_model.py
import joblib
import numpy as np

class AIClimateModel:
    """Predicts optimal climate conditions for plant growth using a trained ML model."""

    def __init__(self, model_path="models/climate_model.pkl"):
        """Loads a pre-trained AI model for climate control."""
        self.model = joblib.load(model_path)

    def predict_optimal_conditions(self, temperature, humidity, soil_moisture):
        """Predicts ideal actuator settings based on sensor inputs."""
        input_data = np.array([[temperature, humidity, soil_moisture]])
        output = self.model.predict(input_data)[0]
        
        return {
            "heater": output[0],    # 1 = ON, 0 = OFF
            "humidifier": output[1],
            "water_pump": output[2]
        }
