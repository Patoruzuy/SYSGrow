"""
A/B Testing API
===============
Endpoints for managing A/B tests for ML model comparison and deployment.
"""

import logging

from flask import Blueprint, request

from app.blueprints.api._common import (
    fail as _fail,
    get_container as _container,
    success as _success,
)

logger = logging.getLogger(__name__)

ab_testing_bp = Blueprint("ml_ab_testing", __name__, url_prefix="/api/ml/ab-testing")


def _get_ab_testing_service():
    """Get A/B testing service from container."""
    container = _container()
    if not container:
        return None
    return getattr(container, "ab_testing", None)


# ==============================================================================
# A/B TEST MANAGEMENT
# ==============================================================================


@ab_testing_bp.get("/tests")
def list_tests():
    """
    List all A/B tests.

    Query params:
    - status: Filter by status (running, completed, cancelled)
    - model_name: Filter by model name

    Returns:
        {
            "tests": [...],
            "count": int
        }
    """
    try:
        service = _get_ab_testing_service()

        if not service:
            return _success({"tests": [], "count": 0, "message": "A/B testing service is not enabled"})

        status = request.args.get("status")
        model_name = request.args.get("model_name")

        tests = service.list_tests(status=status, model_name=model_name)

        return _success({"tests": tests, "count": len(tests)})

    except Exception as e:
        logger.error(f"Error listing A/B tests: {e}", exc_info=True)
        return safe_error(e, 500)


@ab_testing_bp.post("/tests")
def create_test():
    """
    Create a new A/B test.

    Request body:
        {
            "model_name": str,
            "version_a": str,
            "version_b": str,
            "split_ratio": float (0-1, optional, default 0.5),
            "min_samples": int (optional, default 100)
        }

    Returns:
        {
            "test": {...}
        }
    """
    try:
        service = _get_ab_testing_service()

        if not service:
            return _fail("A/B testing service is not enabled", 503)

        data = request.get_json() or {}

        model_name = data.get("model_name")
        version_a = data.get("version_a")
        version_b = data.get("version_b")

        if not all([model_name, version_a, version_b]):
            return _fail("model_name, version_a, and version_b are required", 400)

        split_ratio = data.get("split_ratio", 0.5)
        min_samples = data.get("min_samples", 100)

        test = service.create_test(
            model_name=model_name,
            version_a=version_a,
            version_b=version_b,
            split_ratio=split_ratio,
            min_samples=min_samples,
        )

        return _success({"test": test.to_dict()}, 201)

    except Exception as e:
        logger.error(f"Error creating A/B test: {e}", exc_info=True)
        return safe_error(e, 500)


@ab_testing_bp.get("/tests/<test_id>")
def get_test(test_id: str):
    """
    Get details of a specific A/B test.

    Returns:
        {
            "test": {...}
        }
    """
    try:
        service = _get_ab_testing_service()

        if not service:
            return _fail("A/B testing service is not enabled", 503)

        test = service.get_test(test_id)

        if not test:
            return _fail(f"Test {test_id} not found", 404)

        return _success({"test": test})

    except Exception as e:
        logger.error(f"Error getting A/B test {test_id}: {e}", exc_info=True)
        return safe_error(e, 500)


@ab_testing_bp.get("/tests/<test_id>/analysis")
def analyze_test(test_id: str):
    """
    Get statistical analysis of an A/B test.

    Returns:
        {
            "test_id": str,
            "version_a_stats": {...},
            "version_b_stats": {...},
            "comparison": {...},
            "statistical_significance": bool,
            "p_value": float,
            "recommended_winner": str | null
        }
    """
    try:
        service = _get_ab_testing_service()

        if not service:
            return _fail("A/B testing service is not enabled", 503)

        analysis = service.analyze_test(test_id)

        if not analysis:
            return _fail(f"Test {test_id} not found", 404)

        return _success(analysis)

    except Exception as e:
        logger.error(f"Error analyzing A/B test {test_id}: {e}", exc_info=True)
        return safe_error(e, 500)


@ab_testing_bp.post("/tests/<test_id>/select-version")
def select_version(test_id: str):
    """
    Select a version for a prediction request (used by inference).

    Uses the test's split ratio to determine which version to use.

    Returns:
        {
            "test_id": str,
            "selected_version": str
        }
    """
    try:
        service = _get_ab_testing_service()

        if not service:
            return _fail("A/B testing service is not enabled", 503)

        version = service.select_version(test_id)

        if not version:
            return _fail(f"Test {test_id} not found or not running", 404)

        return _success({"test_id": test_id, "selected_version": version})

    except Exception as e:
        logger.error(f"Error selecting version for test {test_id}: {e}", exc_info=True)
        return safe_error(e, 500)


@ab_testing_bp.post("/tests/<test_id>/record-result")
def record_result(test_id: str):
    """
    Record a result for an A/B test.

    Request body:
        {
            "version": str,
            "predicted": any,
            "actual": any (optional),
            "error": float (optional)
        }

    Returns:
        {
            "recorded": true,
            "result_count": int
        }
    """
    try:
        service = _get_ab_testing_service()

        if not service:
            return _fail("A/B testing service is not enabled", 503)

        data = request.get_json() or {}

        version = data.get("version")
        predicted = data.get("predicted")

        if version is None or predicted is None:
            return _fail("version and predicted are required", 400)

        result = service.record_result(
            test_id=test_id, version=version, predicted=predicted, actual=data.get("actual"), error=data.get("error")
        )

        if not result:
            return _fail(f"Test {test_id} not found or not running", 404)

        return _success({"recorded": True, "test_id": test_id})

    except Exception as e:
        logger.error(f"Error recording result for test {test_id}: {e}", exc_info=True)
        return safe_error(e, 500)


@ab_testing_bp.post("/tests/<test_id>/complete")
def complete_test(test_id: str):
    """
    Complete an A/B test and optionally deploy the winner.

    Request body:
        {
            "deploy_winner": bool (optional, default false)
        }

    Returns:
        {
            "test_id": str,
            "winner": str,
            "deployed": bool,
            "analysis": {...}
        }
    """
    try:
        service = _get_ab_testing_service()

        if not service:
            return _fail("A/B testing service is not enabled", 503)

        data = request.get_json() or {}
        deploy_winner = data.get("deploy_winner", False)

        result = service.complete_test(test_id, deploy_winner=deploy_winner)

        if not result:
            return _fail(f"Test {test_id} not found", 404)

        return _success(result)

    except Exception as e:
        logger.error(f"Error completing A/B test {test_id}: {e}", exc_info=True)
        return safe_error(e, 500)


@ab_testing_bp.post("/tests/<test_id>/cancel")
def cancel_test(test_id: str):
    """
    Cancel an A/B test.

    Returns:
        {
            "test_id": str,
            "cancelled": true
        }
    """
    try:
        service = _get_ab_testing_service()

        if not service:
            return _fail("A/B testing service is not enabled", 503)

        success = service.cancel_test(test_id)

        if not success:
            return _fail(f"Test {test_id} not found or already completed", 404)

        return _success({"test_id": test_id, "cancelled": True})

    except Exception as e:
        logger.error(f"Error cancelling A/B test {test_id}: {e}", exc_info=True)
        return safe_error(e, 500)
