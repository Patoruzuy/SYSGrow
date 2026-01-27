"""
Train Sample ML Models with Dummy Data
Populates the ML Dashboard with sample trained models for testing

Author: SYSGrow Team
Date: November 2025
"""

import sys
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.ai import ModelRegistry  # Use new service architecture
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, accuracy_score, r2_score
import joblib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def generate_dummy_climate_data(n_samples=1000):
    """Generate dummy data for climate prediction."""
    np.random.seed(42)
    
    # Features: temperature, humidity, soil_moisture, co2, light
    temperature = np.random.normal(22, 3, n_samples)
    humidity = np.random.normal(65, 10, n_samples)
    soil_moisture = np.random.normal(55, 15, n_samples)
    co2 = np.random.normal(450, 100, n_samples)
    light = np.random.uniform(200, 1000, n_samples)
    
    # Target: optimal temperature prediction (simple linear relationship)
    target = temperature + 0.1 * humidity - 0.05 * soil_moisture + np.random.normal(0, 1, n_samples)
    
    df = pd.DataFrame({
        'temperature': temperature,
        'humidity': humidity,
        'soil_moisture': soil_moisture,
        'co2': co2,
        'light': light,
        'target': target
    })
    
    return df


def generate_dummy_disease_data(n_samples=800):
    """Generate dummy data for disease classification."""
    np.random.seed(43)
    
    # Features: leaf_color, leaf_spots, wilting, discoloration
    leaf_color = np.random.uniform(0, 1, n_samples)  # 0=yellow, 1=green
    leaf_spots = np.random.uniform(0, 1, n_samples)  # 0=none, 1=many
    wilting = np.random.uniform(0, 1, n_samples)
    discoloration = np.random.uniform(0, 1, n_samples)
    
    # Target: disease classification (0=healthy, 1=fungal, 2=bacterial, 3=viral)
    # Simple logic: more spots + wilting = disease
    disease_score = leaf_spots * 0.4 + wilting * 0.3 + (1 - leaf_color) * 0.2 + discoloration * 0.1
    target = np.where(disease_score < 0.3, 0,
                     np.where(disease_score < 0.5, 1,
                             np.where(disease_score < 0.7, 2, 3)))
    
    df = pd.DataFrame({
        'leaf_color': leaf_color,
        'leaf_spots': leaf_spots,
        'wilting': wilting,
        'discoloration': discoloration,
        'target': target
    })
    
    return df


def generate_dummy_severity_data(n_samples=600):
    """Generate dummy data for severity prediction."""
    np.random.seed(44)
    
    # Features: disease indicators
    temperature_stress = np.random.uniform(0, 1, n_samples)
    water_stress = np.random.uniform(0, 1, n_samples)
    nutrient_deficiency = np.random.uniform(0, 1, n_samples)
    pest_damage = np.random.uniform(0, 1, n_samples)
    
    # Target: severity score (0-100)
    target = (temperature_stress * 25 + water_stress * 30 + 
             nutrient_deficiency * 25 + pest_damage * 20 + 
             np.random.normal(0, 5, n_samples))
    target = np.clip(target, 0, 100)
    
    df = pd.DataFrame({
        'temperature_stress': temperature_stress,
        'water_stress': water_stress,
        'nutrient_deficiency': nutrient_deficiency,
        'pest_damage': pest_damage,
        'target': target
    })
    
    return df


def train_climate_predictor(registry: ModelRegistry):
    """Train climate predictor model."""
    logger.info("🌡️  Training Climate Predictor Model...")
    
    # Generate data
    df = generate_dummy_climate_data(1000)
    X = df.drop('target', axis=1)
    y = df['target']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    start_time = datetime.now()
    model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
    model.fit(X_train, y_train)
    training_duration = (datetime.now() - start_time).total_seconds()
    
    # Evaluate
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test, y_pred)
    mae = np.mean(np.abs(y_test - y_pred))
    
    logger.info(f"  ✓ RMSE: {rmse:.3f}, R²: {r2:.3f}, MAE: {mae:.3f}")
    
    # Register model
    registry.register_model(
        model=model,
        model_name='climate_predictor',
        version='1.0.0',
        metrics={
            'rmse': float(rmse),
            'r2_score': float(r2),
            'mae': float(mae),
            'mse': float(mse),
            'validation_score': float(r2)
        },
        features_used=list(X.columns),
        hyperparameters={
            'n_estimators': 100,
            'max_depth': 10,
            'random_state': 42
        },
        training_samples=len(X_train),
        training_duration=training_duration,
        notes='Trained with dummy climate data for dashboard testing'
    )
    registry.set_active_version('climate_predictor', '1.0.0')
    
    logger.info("  ✅ Climate Predictor registered and activated")
    return model


def train_disease_classifier(registry: ModelRegistry):
    """Train disease classifier model."""
    logger.info("🦠 Training Disease Classifier Model...")
    
    # Generate data
    df = generate_dummy_disease_data(800)
    X = df.drop('target', axis=1)
    y = df['target']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    start_time = datetime.now()
    model = RandomForestClassifier(n_estimators=80, max_depth=8, random_state=42)
    model.fit(X_train, y_train)
    training_duration = (datetime.now() - start_time).total_seconds()
    
    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    logger.info(f"  ✓ Accuracy: {accuracy:.3f}")
    
    # Register model
    registry.register_model(
        model=model,
        model_name='disease_classifier',
        version='1.0.0',
        metrics={
            'accuracy': float(accuracy),
            'precision': float(accuracy),  # Simplified for testing
            'recall': float(accuracy),
            'f1_score': float(accuracy),
            'validation_score': float(accuracy)
        },
        features_used=list(X.columns),
        hyperparameters={
            'n_estimators': 80,
            'max_depth': 8,
            'random_state': 42
        },
        training_samples=len(X_train),
        training_duration=training_duration,
        notes='Trained with dummy disease data for dashboard testing'
    )
    registry.set_active_version('disease_classifier', '1.0.0')
    
    logger.info("  ✅ Disease Classifier registered and activated")
    return model


def train_severity_predictor(registry: ModelRegistry):
    """Train severity predictor model."""
    logger.info("📊 Training Severity Predictor Model...")
    
    # Generate data
    df = generate_dummy_severity_data(600)
    X = df.drop('target', axis=1)
    y = df['target']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train model
    start_time = datetime.now()
    model = RandomForestRegressor(n_estimators=90, max_depth=12, random_state=42)
    model.fit(X_train, y_train)
    training_duration = (datetime.now() - start_time).total_seconds()
    
    # Evaluate
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    r2 = r2_score(y_test, y_pred)
    mae = np.mean(np.abs(y_test - y_pred))
    
    logger.info(f"  ✓ RMSE: {rmse:.3f}, R²: {r2:.3f}, MAE: {mae:.3f}")
    
    # Register model
    registry.register_model(
        model=model,
        model_name='severity_predictor',
        version='1.0.0',
        metrics={
            'rmse': float(rmse),
            'r2_score': float(r2),
            'mae': float(mae),
            'mse': float(mse),
            'validation_score': float(r2)
        },
        features_used=list(X.columns),
        hyperparameters={
            'n_estimators': 90,
            'max_depth': 12,
            'random_state': 42
        },
        training_samples=len(X_train),
        training_duration=training_duration,
        notes='Trained with dummy severity data for dashboard testing'
    )
    registry.set_active_version('severity_predictor', '1.0.0')
    
    logger.info("  ✅ Severity Predictor registered and activated")
    return model


def main():
    """Train all sample models."""
    logger.info("=" * 60)
    logger.info("🚀 Training Sample ML Models for Dashboard Testing")
    logger.info("=" * 60)
    
    try:
        # Initialize registry
        registry = ModelRegistry(models_dir="models")
        logger.info("✓ Model Registry initialized")
        
        # Train models
        train_climate_predictor(registry)
        train_disease_classifier(registry)
        train_severity_predictor(registry)
        
        # Summary
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ All models trained successfully!")
        logger.info("=" * 60)
        logger.info("")
        logger.info("📊 Model Summary:")
        logger.info("  • climate_predictor v1.0.0 - Active")
        logger.info("  • disease_classifier v1.0.0 - Active")
        logger.info("  • severity_predictor v1.0.0 - Active")
        logger.info("")
        logger.info("🌐 Next Steps:")
        logger.info("  1. Refresh ML Dashboard: http://localhost:5000/ml-dashboard")
        logger.info("  2. Test model comparison feature")
        logger.info("  3. View feature importance charts")
        logger.info("  4. Check training history")
        logger.info("")
        
    except Exception as e:
        logger.error(f"❌ Error training models: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
