# ai/train_growth_model.py
import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder

# Load synthetic data
df = pd.read_csv("ai/synthetic_climate_data.csv")

# Convert categorical 'stage' column to numerical labels
label_encoder = LabelEncoder()
df["stage_encoded"] = label_encoder.fit_transform(df["stage"])

# Define features and target variables
X = df[["stage_encoded"]]  # Input: Plant Growth Stage
y = df[["temperature", "humidity", "soil_moisture", "lighting_hours"]]  # Output: Ideal Conditions

# Split into training & testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train AI Model
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Save trained model
joblib.dump(model, "models/growth_model.pkl")
joblib.dump(label_encoder, "models/stage_encoder.pkl")  # Save stage encoder

print("✅ AI Model trained and saved successfully!")
