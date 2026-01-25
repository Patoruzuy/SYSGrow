# ai/train_growth_model.py
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import sqlite3

# ✅ Load historical data from the database
def load_data_from_db(db_path="database/grow_tent.db"):
    """Fetches sensor readings, AI decisions, and actuator logs for training."""
    
    conn = sqlite3.connect(db_path)
    query = """
        SELECT 
            sr.temperature, sr.humidity, sr.soil_moisture, 
            sr.co2_ppm, sr.voc_ppb, sr.aqi, sr.pressure, 
            ai.ai_temperature, ai.ai_humidity, ai.ai_soil_moisture, 
            ah.action AS heater, 
            ah.action AS humidifier, 
            ah.action AS water_pump
        FROM SensorReading sr
        LEFT JOIN AI_DecisionLogs ai ON sr.sensor_id = ai.unit_id
        LEFT JOIN ActuatorHistory ah ON sr.sensor_id = ah.unit_id
    """
    
    df = pd.read_sql_query(query, conn)
    conn.close()

    # Convert actuator ON/OFF actions to binary (1=ON, 0=OFF)
    df["heater"] = df["heater"].apply(lambda x: 1 if x == "ON" else 0)
    df["humidifier"] = df["humidifier"].apply(lambda x: 1 if x == "ON" else 0)
    df["water_pump"] = df["water_pump"].apply(lambda x: 1 if x == "ON" else 0)

    return df

# ✅ Load Data
data = load_data_from_db()

# ✅ Features: Expanded to include CO₂, VOC, AQI, Pressure
X = data[["temperature", "humidity", "soil_moisture", "co2_ppm", "voc_ppb", "aqi", "pressure"]]

# ✅ Target Variables: Expanded to include all actuators
y = data[["heater", "humidifier", "water_pump"]]

# ✅ Split into training & test sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# ✅ Train AI Model
model = RandomForestClassifier(n_estimators=150)
model.fit(X_train, y_train)

# ✅ Save trained model
joblib.dump(model, "models/climate_model.pkl")

print("✅ AI Model trained & saved successfully!")
