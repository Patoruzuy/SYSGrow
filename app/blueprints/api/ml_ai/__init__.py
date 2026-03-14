"""
ML/AI API Module
================
Consolidated AI and ML endpoints organized by domain.

Structure:
- base.py - Base ML endpoints (health, training history)
- predictions.py - Core AI predictions (disease, growth, climate, health)
- models.py - Model management (registry, versions, promotion)
- monitoring.py - Real-time monitoring, drift detection, insights
- analytics.py - ML performance analytics and statistics
- retraining.py - Model retraining workflows
- readiness.py - ML model readiness and activation
- ab_testing.py - A/B testing for model comparison
- continuous.py - Continuous monitoring control
- personalized.py - Personalized learning and profiles
- training_data.py - Training data collection and quality

All endpoints use dependency injection via ServiceContainer.
"""

from .base import base_bp
from .predictions import predictions_bp
from .models import models_bp
from .monitoring import monitoring_bp
from .analytics import analytics_bp
from .retraining import retraining_bp
from .analysis import analysis_bp
from .readiness import readiness_bp
from .ab_testing import ab_testing_bp
from .continuous import continuous_bp
from .personalized import personalized_bp
from .training_data import training_data_bp

__all__ = [
    'base_bp',
    'predictions_bp',
    'models_bp', 
    'monitoring_bp',
    'analytics_bp',
    'retraining_bp',
    'analysis_bp',
    'readiness_bp',
    'ab_testing_bp',
    'continuous_bp',
    'personalized_bp',
    'training_data_bp',
]
