"""
Training Data API
=================
Endpoints for managing ML training data collection and quality.
"""

from __future__ import annotations

import logging
from contextlib import suppress

from flask import Blueprint, Response, request

from app.blueprints.api._common import (
    fail as _fail,
    get_container as _container,
    success as _success,
)
from app.utils.http import safe_route

logger = logging.getLogger(__name__)

training_data_bp = Blueprint("ml_training_data", __name__)


def _get_training_data_collector():
    """Get training data collector from container."""
    container = _container()
    if not container:
        return None
    return getattr(container, "training_data_collector", None)


# ==============================================================================
# DATA COLLECTION
# ==============================================================================


@training_data_bp.get("/summary")
@safe_route("Failed to get training data summary")
def get_summary() -> Response:
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
    collector = _get_training_data_collector()

    if not collector:
        return _success({"datasets": {}, "total_examples": 0, "message": "Training data collector is not enabled"})

    summary = collector.get_training_data_summary()

    return _success(summary)


@training_data_bp.post("/collect/disease")
@safe_route("Failed to collect disease training data")
def collect_disease_data() -> Response:
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
    collector = _get_training_data_collector()

    if not collector:
        return _fail("Training data collector is not enabled", 503)

    data = request.get_json() or {}
    days_back = data.get("days_back", 30)
    min_examples = data.get("min_examples_per_class", 50)

    result = collector.collect_disease_training_data(days_back=days_back, min_examples_per_class=min_examples)

    examples_count = len(result) if result is not None else 0

    return _success({"collected": True, "examples_count": examples_count, "days_analyzed": days_back})


@training_data_bp.post("/collect/climate")
@safe_route("Failed to collect climate training data")
def collect_climate_data() -> Response:
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
    collector = _get_training_data_collector()

    if not collector:
        return _fail("Training data collector is not enabled", 503)

    data = request.get_json() or {}
    days_back = data.get("days_back", 30)

    result = collector.collect_climate_training_data(days_back=days_back)

    examples_count = len(result) if result is not None else 0

    return _success({"collected": True, "examples_count": examples_count, "days_analyzed": days_back})


@training_data_bp.post("/collect/growth")
@safe_route("Failed to collect growth training data")
def collect_growth_data() -> Response:
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
    collector = _get_training_data_collector()

    if not collector:
        return _fail("Training data collector is not enabled", 503)

    data = request.get_json() or {}
    min_examples = data.get("min_examples", 100)

    result = collector.collect_growth_outcome_data(min_examples=min_examples)

    examples_count = len(result) if result is not None else 0

    return _success({"collected": True, "examples_count": examples_count})


# ==============================================================================
# DATA VALIDATION
# ==============================================================================


@training_data_bp.post("/validate")
@safe_route("Failed to validate training data")
def validate_data() -> Response:
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
    collector = _get_training_data_collector()

    if not collector:
        return _fail("Training data collector is not enabled", 503)

    data = request.get_json() or {}
    dataset_type = data.get("dataset_type")

    if not dataset_type:
        return _fail("dataset_type is required", 400)

    if dataset_type not in ["disease", "climate", "growth"]:
        return _fail("dataset_type must be one of: disease, climate, growth", 400)

    validation_result = collector.validate_training_data(dataset_type)

    return _success(validation_result)


@training_data_bp.get("/quality/<dataset_type>")
@safe_route("Failed to get training data quality metrics")
def get_quality_metrics(dataset_type: str) -> Response:
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
    collector = _get_training_data_collector()

    if not collector:
        return _success({"dataset_type": dataset_type, "message": "Training data collector is not enabled"})

    if dataset_type not in ["disease", "climate", "growth"]:
        return _fail("dataset_type must be one of: disease, climate, growth", 400)

    # Get file summary for the dataset
    filename_map = {
        "disease": "disease_training_data.csv",
        "climate": "climate_training_data.csv",
        "growth": "growth_training_data.csv",
    }

    summary = collector._get_file_summary(filename_map[dataset_type])

    return _success({"dataset_type": dataset_type, **summary})


# ==============================================================================
# PLANT HEALTH MODEL TRAINING
# ==============================================================================


def _get_ml_trainer():
    """Get ML trainer service from container."""
    container = _container()
    if not container:
        return None
    return getattr(container, "ml_trainer", None)


@training_data_bp.post("/plant-health/train")
@safe_route("Failed to train plant health models")
def train_plant_health_models() -> Response:
    """
    Trigger training of plant health ML models.

    Trains both:
    - Health score regressor (predicts 0-100 score)
    - Health status classifier (predicts healthy/stressed/critical)

    Request body (optional):
        {
            "unit_id": int,
            "plant_type": str,
            "days": int (default 365),
            "model_type": "both" | "regressor" | "classifier"
        }

    Returns:
        {
            "success": bool,
            "regressor": {...training metrics...},
            "classifier": {...training metrics...}
        }
    """
    ml_trainer = _get_ml_trainer()

    if not ml_trainer:
        return _fail("ML trainer service is not available", 503)

    data = request.get_json() or {}
    unit_id = data.get("unit_id")
    plant_type = data.get("plant_type")
    days = data.get("days", 365)
    model_type = data.get("model_type", "both")

    results = {"success": False}

    # Train regressor
    if model_type in ("both", "regressor"):
        regressor_result = ml_trainer.train_health_score_model(
            unit_id=unit_id,
            plant_type=plant_type,
            days=days,
            save_model=True,
        )
        results["regressor"] = regressor_result
        if regressor_result.get("success"):
            results["success"] = True

    # Train classifier
    if model_type in ("both", "classifier"):
        classifier_result = ml_trainer.train_health_status_classifier(
            unit_id=unit_id,
            days=days,
            save_model=True,
        )
        results["classifier"] = classifier_result
        if classifier_result.get("success"):
            results["success"] = True

    if results["success"]:
        return _success(results)
    else:
        # Return partial results with error info
        error_msg = "Training failed - insufficient data"
        if "regressor" in results and not results["regressor"].get("success"):
            error_msg = results["regressor"].get("error", error_msg)
        elif "classifier" in results and not results["classifier"].get("success"):
            error_msg = results["classifier"].get("error", error_msg)
        return _fail(error_msg, 400, data=results)


@training_data_bp.get("/plant-health/status")
@safe_route("Failed to get plant health training status")
def get_plant_health_training_status() -> Response:
    """
    Get plant health model training readiness status.

    Returns:
        {
            "ready_for_training": bool,
            "harvest_samples": int,
            "observation_samples": int,
            "min_samples_required": int,
            "regressor_model_exists": bool,
            "classifier_model_exists": bool,
            "recommendations": [str]
        }
    """
    container = _container()
    if not container:
        return _fail("Container not available", 503)

    # Check for training data repository
    training_repo = getattr(container, "training_data_repo", None)
    model_registry = getattr(container, "model_registry", None)

    MIN_SAMPLES = 50
    harvest_samples = 0
    observation_samples = 0
    regressor_exists = False
    classifier_exists = False

    # Count available training data
    if training_repo and hasattr(training_repo, "get_health_score_training_data"):
        try:
            harvest_data = training_repo.get_health_score_training_data(days_limit=365)
            harvest_samples = len(harvest_data) if harvest_data else 0
        except Exception as e:
            logger.warning("Error getting harvest samples: %s", e)

    if training_repo and hasattr(training_repo, "get_health_status_training_data"):
        try:
            obs_data = training_repo.get_health_status_training_data(days_limit=365)
            observation_samples = len(obs_data) if obs_data else 0
        except Exception as e:
            logger.warning("Error getting observation samples: %s", e)

    # Check if models exist
    if model_registry:
        with suppress(Exception):
            regressor_exists = model_registry.model_exists("plant_health_regressor")
        with suppress(Exception):
            classifier_exists = model_registry.model_exists("plant_health_classifier")

    ready_for_training = harvest_samples >= MIN_SAMPLES or observation_samples >= MIN_SAMPLES
    recommendations = []

    if harvest_samples < MIN_SAMPLES:
        recommendations.append(f"Need {MIN_SAMPLES - harvest_samples} more harvest records with quality ratings")
    if observation_samples < MIN_SAMPLES:
        recommendations.append(f"Need {MIN_SAMPLES - observation_samples} more health observations")
    if ready_for_training and not regressor_exists:
        recommendations.append("Ready to train health score regressor")
    if ready_for_training and not classifier_exists:
        recommendations.append("Ready to train health status classifier")

    return _success(
        {
            "ready_for_training": ready_for_training,
            "harvest_samples": harvest_samples,
            "observation_samples": observation_samples,
            "min_samples_required": MIN_SAMPLES,
            "regressor_model_exists": regressor_exists,
            "classifier_model_exists": classifier_exists,
            "recommendations": recommendations,
        }
    )
