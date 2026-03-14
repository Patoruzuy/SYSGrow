"""
Training Data API
=================
Endpoints for managing ML training data collection and quality.
"""

import logging
from flask import Blueprint, request

from app.blueprints.api._common import (
    get_container as _container,
    success as _success,
    fail as _fail,
)

logger = logging.getLogger(__name__)

training_data_bp = Blueprint("ml_training_data", __name__, url_prefix="/api/ml/training-data")


def _get_training_data_collector():
    """Get training data collector from container."""
    container = _container()
    if not container:
        return None
    return getattr(container, 'training_data_collector', None)


# ==============================================================================
# DATA COLLECTION
# ==============================================================================

@training_data_bp.get("/summary")
def get_summary():
    """
    Get summary of available training data.
    
    Returns:
        {
            "datasets": {
                "disease": {...},
                "climate": {...},
                "growth": {...}
            },
            "total_examples": int,
            "quality_summary": {...}
        }
    """
    try:
        collector = _get_training_data_collector()
        
        if not collector:
            return _success({
                "datasets": {},
                "total_examples": 0,
                "message": "Training data collector is not enabled"
            })
        
        summary = collector.get_training_data_summary()
        
        return _success(summary)
        
    except Exception as e:
        logger.error(f"Error getting training data summary: {e}", exc_info=True)
        return _fail(str(e), 500)


@training_data_bp.post("/collect/disease")
def collect_disease_data():
    """
    Trigger disease training data collection.
    
    Request body:
        {
            "days_back": int (optional, default 30),
            "min_examples_per_class": int (optional, default 50)
        }
    
    Returns:
        {
            "collected": true,
            "examples_count": int,
            "class_distribution": {...}
        }
    """
    try:
        collector = _get_training_data_collector()
        
        if not collector:
            return _fail("Training data collector is not enabled", 503)
        
        data = request.get_json() or {}
        days_back = data.get('days_back', 30)
        min_examples = data.get('min_examples_per_class', 50)
        
        result = collector.collect_disease_training_data(
            days_back=days_back,
            min_examples_per_class=min_examples
        )
        
        examples_count = len(result) if result is not None else 0
        
        return _success({
            "collected": True,
            "examples_count": examples_count,
            "days_analyzed": days_back
        })
        
    except Exception as e:
        logger.error(f"Error collecting disease training data: {e}", exc_info=True)
        return _fail(str(e), 500)


@training_data_bp.post("/collect/climate")
def collect_climate_data():
    """
    Trigger climate optimization training data collection.
    
    Request body:
        {
            "days_back": int (optional, default 30)
        }
    
    Returns:
        {
            "collected": true,
            "examples_count": int
        }
    """
    try:
        collector = _get_training_data_collector()
        
        if not collector:
            return _fail("Training data collector is not enabled", 503)
        
        data = request.get_json() or {}
        days_back = data.get('days_back', 30)
        
        result = collector.collect_climate_training_data(days_back=days_back)
        
        examples_count = len(result) if result is not None else 0
        
        return _success({
            "collected": True,
            "examples_count": examples_count,
            "days_analyzed": days_back
        })
        
    except Exception as e:
        logger.error(f"Error collecting climate training data: {e}", exc_info=True)
        return _fail(str(e), 500)


@training_data_bp.post("/collect/growth")
def collect_growth_data():
    """
    Trigger growth outcome training data collection.
    
    Request body:
        {
            "min_examples": int (optional, default 100)
        }
    
    Returns:
        {
            "collected": true,
            "examples_count": int
        }
    """
    try:
        collector = _get_training_data_collector()
        
        if not collector:
            return _fail("Training data collector is not enabled", 503)
        
        data = request.get_json() or {}
        min_examples = data.get('min_examples', 100)
        
        result = collector.collect_growth_outcome_data(min_examples=min_examples)
        
        examples_count = len(result) if result is not None else 0
        
        return _success({
            "collected": True,
            "examples_count": examples_count
        })
        
    except Exception as e:
        logger.error(f"Error collecting growth training data: {e}", exc_info=True)
        return _fail(str(e), 500)


# ==============================================================================
# DATA VALIDATION
# ==============================================================================

@training_data_bp.post("/validate")
def validate_data():
    """
    Validate training data quality.
    
    Request body:
        {
            "dataset_type": str ("disease", "climate", "growth")
        }
    
    Returns:
        {
            "valid": bool,
            "quality_score": float,
            "issues": [...],
            "recommendations": [...]
        }
    """
    try:
        collector = _get_training_data_collector()
        
        if not collector:
            return _fail("Training data collector is not enabled", 503)
        
        data = request.get_json() or {}
        dataset_type = data.get('dataset_type')
        
        if not dataset_type:
            return _fail("dataset_type is required", 400)
        
        if dataset_type not in ['disease', 'climate', 'growth']:
            return _fail("dataset_type must be one of: disease, climate, growth", 400)
        
        validation_result = collector.validate_training_data(dataset_type)
        
        return _success(validation_result)
        
    except Exception as e:
        logger.error(f"Error validating training data: {e}", exc_info=True)
        return _fail(str(e), 500)


@training_data_bp.get("/quality/<dataset_type>")
def get_quality_metrics(dataset_type: str):
    """
    Get quality metrics for a specific dataset.
    
    Returns:
        {
            "dataset_type": str,
            "total_examples": int,
            "verified_examples": int,
            "average_quality_score": float,
            "class_balance": {...},
            "temporal_coverage": {...}
        }
    """
    try:
        collector = _get_training_data_collector()
        
        if not collector:
            return _success({
                "dataset_type": dataset_type,
                "message": "Training data collector is not enabled"
            })
        
        if dataset_type not in ['disease', 'climate', 'growth']:
            return _fail("dataset_type must be one of: disease, climate, growth", 400)
        
        # Get file summary for the dataset
        filename_map = {
            'disease': 'disease_training_data.csv',
            'climate': 'climate_training_data.csv',
            'growth': 'growth_training_data.csv'
        }
        
        summary = collector._get_file_summary(filename_map[dataset_type])
        
        return _success({
            "dataset_type": dataset_type,
            **summary
        })
        
    except Exception as e:
        logger.error(f"Error getting quality metrics for {dataset_type}: {e}", exc_info=True)
        return _fail(str(e), 500)
