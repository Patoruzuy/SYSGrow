# ai/plant_growth_model.py
import joblib
import numpy as np

class PlantGrowthPredictor:
    """Predicts ideal environmental conditions for plant growth using AI."""

    def __init__(self):
        """Loads pre-trained AI model."""
        self.model = joblib.load("models/growth_model.pkl")
        self.stage_encoder = joblib.load("models/stage_encoder.pkl")

    def predict_growth_conditions(self, stage_name):
        """Predicts optimal conditions based on plant stage."""
        encoded_stage = self.stage_encoder.transform([stage_name])[0]
        input_data = np.array([[encoded_stage]])
        prediction = self.model.predict(input_data)[0]

        return {
            "temperature": round(prediction[0], 2),
            "humidity": round(prediction[1], 2),
            "soil_moisture": round(prediction[2], 2),
            "lighting_hours": round(prediction[3], 2)
        }
