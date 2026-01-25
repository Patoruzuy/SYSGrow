# ai/train_growth_model.py
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

# Load historical sensor data
data = pd.read_csv("historical_climate_data.csv")

# Features: Temperature, Humidity, Soil Moisture
X = data[["temperature", "humidity", "soil_moisture"]]
y = data[["heater", "humidifier", "water_pump"]]  # Binary target labels (1=ON, 0=OFF)

# Split into training and test sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train model
model = RandomForestClassifier(n_estimators=100)
model.fit(X_train, y_train)

# Save trained model
joblib.dump(model, "models/climate_model.pkl")

print("✅ AI Model trained & saved successfully!")
