# ai/generate_synthetic_data.py
import pandas as pd
import numpy as np

# Define plant growth stages
stages = ["Germination", "Seedling", "Vegetative", "Flowering", "Fruit Development", "Harvest"]

# Generate synthetic data
np.random.seed(42)
num_samples = 5000

data = {
    "temperature": np.random.uniform(18, 30, num_samples),  # Between 18°C and 30°C
    "humidity": np.random.uniform(40, 70, num_samples),  # Between 40% and 70%
    "soil_moisture": np.random.uniform(20, 60, num_samples),  # Between 20% and 60%
    "lighting_hours": np.random.uniform(10, 18, num_samples),  # Between 10 and 18 hours
    "stage": np.random.choice(stages, num_samples)  # Random stage
}

df = pd.DataFrame(data)
df.to_csv("ai/synthetic_climate_data.csv", index=False)

print("✅ Synthetic data generated successfully!")
