""" AI-powered climate control model for plant growth.

    Returns:
        dict: predicted temperature, humidity, soil moisture, and lighting hours.
"""

import joblib
import numpy as np

class AIClimateModel:
    """
    AI-powered climate control model for plant growth.
    """

    def __init__(self, database_handler):
        """Initializes AI model and connects to the database."""
        self.database_handler = database_handler
        self.model = joblib.load("models/climate_model.pkl") 
        self.stage_encoder = joblib.load("models/stage_encoder.pkl")

    def predict_growth_conditions(self, plant_stage):
        """
        Predicts ideal environmental conditions based on plant growth stage.

        Args:
            plant_stage (str): The current growth stage of the plant.

        Returns:
            dict: Predicted temperature, humidity, soil moisture, and lighting hours.
        """
        encoded_stage = self.stage_encoder.transform([plant_stage])[0]
        input_data = np.array([[encoded_stage]])
        prediction = self.model.predict(input_data)[0]

        return {
            "temperature": round(prediction[0], 2),
            "humidity": round(prediction[1], 2),
            "soil_moisture": round(prediction[2], 2),
        }

    def detect_watering_issues(self, unit_id):
        """
        Detects watering problems by comparing AI predictions with real soil moisture data.

        Args:
            unit_id (int): The ID of the growth unit.

        Returns:
            str: A warning if watering issues are detected.
        """
        # ✅ Get AI-predicted soil moisture
        latest_log = self.database_handler.get_latest_ai_log(unit_id)
        if not latest_log:
            return "⚠️ No AI logs found for this unit."

        ai_soil_moisture = latest_log["ai_soil_moisture"]
        actual_soil_moisture = latest_log["actual_soil_moisture"]
        actuator_triggered = latest_log["actuator_triggered"]

        # ✅ Check if watering was needed but not activated
        if actual_soil_moisture < ai_soil_moisture - 5 and not actuator_triggered:
            return f"🚨 Underwatering Detected: Soil moisture ({actual_soil_moisture}%) is lower than AI's prediction ({ai_soil_moisture}%), but the water pump did not activate."

        # ✅ Check if soil moisture remains too high (overwatering)
        if actual_soil_moisture > ai_soil_moisture + 5 and actuator_triggered:
            return f"⚠️ Overwatering Warning: Soil moisture ({actual_soil_moisture}%) is higher than AI's prediction ({ai_soil_moisture}%), and the water pump was recently used."

        return "✅ No watering issues detected."

    def analyze_climate_control(self, unit_id):
        """
        Compares AI predictions with real sensor data to find climate control errors.

        Args:
            unit_id (int): The growth unit ID.

        Returns:
            dict: AI vs. actual climate differences.
        """
        latest_log = self.database_handler.get_latest_ai_log(unit_id)
        if not latest_log:
            return {"status": "⚠️ No AI logs found for this unit."}

        return {
            "temperature_diff": latest_log["actual_temperature"] - latest_log["ai_temperature"],
            "humidity_diff": latest_log["actual_humidity"] - latest_log["ai_humidity"],
            "soil_moisture_diff": latest_log["actual_soil_moisture"] - latest_log["ai_soil_moisture"]
        }

