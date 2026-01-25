"""
Automated Retraining API
========================
Endpoints for managing automated model retraining.
"""

import logging
from flask import Blueprint, request
from pydantic import ValidationError
from app.services.ai import RetrainingTrigger
from app.schemas import RetrainingJobRequest

from app.blueprints.api._common import (
    get_container as _container,
    success as _success,
    fail as _fail,
)

logger = logging.getLogger(__name__)

retraining_bp = Blueprint("ml_retraining", __name__, url_prefix="/api/ml/retraining")


def _get_retraining_service():
    """Get retraining service from container, with fallback for disabled service."""
    container = _container()
    if not container:
        return None
    return getattr(container, 'automated_retraining', None)


@retraining_bp.route("/jobs", methods=["GET"])
def get_jobs():
    """Get all retraining jobs."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _success({
                "jobs": [],
                "message": "Automated retraining service is not enabled"
            })

        jobs = retraining_service.get_jobs()

        return _success({
            "jobs": [job.to_dict() for job in jobs] if jobs else []
        })

    except Exception as e:
        logger.error(f"Error getting retraining jobs: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/jobs", methods=["POST"])
def create_job():
    """Create a new retraining job."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _fail("Automated retraining service is not enabled", 503)

        raw = request.get_json() or {}
        try:
            body = RetrainingJobRequest(**raw)
        except ValidationError as ve:
            return _fail("Invalid request", 400, details={"errors": ve.errors()})

        # Extract optional parameters from validated body
        kwargs = {}
        if body.min_samples is not None:
            kwargs["min_samples"] = body.min_samples
        if body.drift_threshold is not None:
            kwargs["drift_threshold"] = body.drift_threshold
        if body.performance_threshold is not None:
            kwargs["performance_threshold"] = body.performance_threshold
        if body.schedule_time is not None:
            kwargs["schedule_time"] = body.schedule_time
        if body.schedule_day is not None:
            kwargs["schedule_day"] = body.schedule_day
        kwargs["enabled"] = body.enabled

        job = retraining_service.add_job(
            model_type=body.model_type,
            schedule_type=body.schedule_type.value,
            **kwargs
        )

        return _success({"job": job.to_dict()}, 201)

    except Exception as e:
        logger.error(f"Error creating retraining job: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/jobs/<job_id>", methods=["DELETE"])
def delete_job(job_id: str):
    """Delete a retraining job."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _fail("Automated retraining service is not enabled", 503)

        success = retraining_service.remove_job(job_id)

        if success:
            return _success({"message": f"Job {job_id} deleted"})
        else:
            return _fail(f"Job {job_id} not found", 404)

    except Exception as e:
        logger.error(f"Error deleting retraining job: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/jobs/<job_id>/enable", methods=["POST"])
def enable_job(job_id: str):
    """Enable a retraining job."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _fail("Automated retraining service is not enabled", 503)

        success = retraining_service.enable_job(job_id, True)

        if success:
            return _success({"message": f"Job {job_id} enabled"})
        else:
            return _fail(f"Job {job_id} not found", 404)

    except Exception as e:
        logger.error(f"Error enabling job: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/jobs/<job_id>/disable", methods=["POST"])
def disable_job(job_id: str):
    """Disable a retraining job."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _fail("Automated retraining service is not enabled", 503)

        success = retraining_service.enable_job(job_id, False)

        if success:
            return _success({"message": f"Job {job_id} disabled"})
        else:
            return _fail(f"Job {job_id} not found", 404)

    except Exception as e:
        logger.error(f"Error disabling job: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/jobs/<job_id>/run", methods=["POST"])
def run_job_now(job_id: str):
    """
    Immediately execute a scheduled retraining job.

    This triggers the job to run now, regardless of its schedule.
    """
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _fail("Automated retraining service is not enabled", 503)

        # Get the job first to check if it exists
        jobs = retraining_service.get_jobs()
        job = next((j for j in jobs if str(j.job_id) == str(job_id)), None)

        if not job:
            return _fail(f"Job {job_id} not found", 404)

        # Trigger retraining for this job's model type
        if hasattr(retraining_service, 'run_job_immediately'):
            event = retraining_service.run_job_immediately(job_id)
        else:
            # Fallback: use trigger_retraining with the job's model type
            event = retraining_service.trigger_retraining(
                model_type=job.model_type,
                trigger=RetrainingTrigger.MANUAL
            )

        if event:
            return _success({
                "message": f"Job {job_id} execution started",
                "event": event.to_dict() if hasattr(event, 'to_dict') else {}
            }, 202)
        else:
            return _fail("Failed to start job execution", 500)

    except Exception as e:
        logger.error(f"Error running job {job_id}: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/jobs/<job_id>/pause", methods=["POST"])
def pause_job(job_id: str):
    """Pause a running retraining job."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _fail("Automated retraining service is not enabled", 503)

        if hasattr(retraining_service, 'pause_job'):
            success = retraining_service.pause_job(job_id)
        else:
            # Fallback: disable the job
            success = retraining_service.enable_job(job_id, False)

        if success:
            return _success({"message": f"Job {job_id} paused"})
        else:
            return _fail(f"Job {job_id} not found or cannot be paused", 404)

    except Exception as e:
        logger.error(f"Error pausing job {job_id}: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/jobs/<job_id>/resume", methods=["POST"])
def resume_job(job_id: str):
    """Resume a paused retraining job."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _fail("Automated retraining service is not enabled", 503)

        if hasattr(retraining_service, 'resume_job'):
            success = retraining_service.resume_job(job_id)
        else:
            # Fallback: enable the job
            success = retraining_service.enable_job(job_id, True)

        if success:
            return _success({"message": f"Job {job_id} resumed"})
        else:
            return _fail(f"Job {job_id} not found or cannot be resumed", 404)

    except Exception as e:
        logger.error(f"Error resuming job {job_id}: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/trigger", methods=["POST"])
def trigger_retraining():
    """Manually trigger model retraining."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _fail("Automated retraining service is not enabled", 503)

        data = request.get_json()
        if not data:
            return _fail("No data provided", 400)

        model_type = data.get("model_type") or data.get("model_name")
        if not model_type:
            return _fail("model_type or model_name is required", 400)

        event = retraining_service.trigger_retraining(
            model_type=model_type,
            trigger=RetrainingTrigger.MANUAL
        )

        if event:
            return _success({
                "event": event.to_dict() if hasattr(event, 'to_dict') else {},
                "version": event.new_version if hasattr(event, 'new_version') else None
            }, 202)
        else:
            return _fail("Failed to trigger retraining", 500)

    except Exception as e:
        logger.error(f"Error triggering retraining: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/events", methods=["GET"])
def get_events():
    """Get retraining event history."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _success({
                "events": [],
                "message": "Automated retraining service is not enabled"
            })

        model_type = request.args.get("model_type")
        limit = request.args.get("limit", default=100, type=int)

        events = retraining_service.get_events(
            model_type=model_type,
            limit=limit
        )

        return _success({
            "events": [event.to_dict() for event in events] if events else []
        })

    except Exception as e:
        logger.error(f"Error getting retraining events: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/scheduler/start", methods=["POST"])
def start_scheduler():
    """Start the automated retraining scheduler."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _fail("Automated retraining service is not enabled", 503)

        retraining_service.start_scheduler()

        return _success({"message": "Scheduler started"})

    except Exception as e:
        logger.error(f"Error starting scheduler: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/scheduler/stop", methods=["POST"])
def stop_scheduler():
    """Stop the automated retraining scheduler."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _fail("Automated retraining service is not enabled", 503)

        retraining_service.stop_scheduler()

        return _success({"message": "Scheduler stopped"})

    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}", exc_info=True)
        return _fail(str(e), 500)


@retraining_bp.route("/status", methods=["GET"])
def get_status():
    """Get retraining service status."""
    try:
        retraining_service = _get_retraining_service()

        if not retraining_service:
            return _success({
                "status": {
                    "scheduler_running": False,
                    "total_jobs": 0,
                    "enabled_jobs": 0,
                    "total_events": 0,
                    "recent_failures": 0,
                    "message": "Automated retraining service is not enabled"
                }
            })

        status = retraining_service.get_status()

        return _success({"status": status})

    except Exception as e:
        logger.error(f"Error getting retraining status: {e}", exc_info=True)
        return _fail(str(e), 500)
