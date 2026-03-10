"""Socket.IO ML event handlers.

ML monitoring/control events are exposed under the allowed /system namespace.

Namespace: /system
Events:
- ml_subscribe
- ml_unsubscribe
- request_drift_update
- request_training_status

Broadcast Events:
- training_started
- training_progress
- training_complete
- training_cancelled
- training_failed
- drift_detected
- retraining_scheduled
- model_activated
"""

import logging

from flask import current_app, request
from flask_socketio import emit, join_room, leave_room

from app.extensions import socketio
from app.utils.emitters import SOCKETIO_NAMESPACE_SYSTEM

logger = logging.getLogger(__name__)

# Track active ML subscribers
ml_subscribers = set()


def _container():
    """Get ServiceContainer from Flask app config."""
    return current_app.config.get("CONTAINER")


# =====================================
# /system (ml) NAMESPACE HANDLERS
# =====================================


@socketio.on("connect", namespace=SOCKETIO_NAMESPACE_SYSTEM)
def handle_ml_connect():
    """Handle ML namespace connection"""
    try:
        logger.info("Client %s connected to /system (ml) namespace", request.sid)
        # Send immediate acknowledgment
        emit("ml_connected", {"status": "connected", "sid": request.sid})
    except Exception as e:
        logger.error("Error in ML connect handler: %s", e, exc_info=True)
        return False  # Reject connection on error


@socketio.on("disconnect", namespace=SOCKETIO_NAMESPACE_SYSTEM)
def handle_ml_disconnect():
    """Handle ML namespace disconnection"""
    try:
        client_id = request.sid
        ml_subscribers.discard(client_id)
        logger.info("Client %s disconnected from /system (ml) namespace", client_id)
    except Exception as e:
        logger.error("Error in ML disconnect handler: %s", e, exc_info=True)


@socketio.on("ml_subscribe", namespace=SOCKETIO_NAMESPACE_SYSTEM)
def handle_ml_subscribe():
    """Subscribe to ML infrastructure updates"""
    try:
        client_id = request.sid
        ml_subscribers.add(client_id)
        join_room("ml_updates")

        logger.info("Client %s subscribed to ML updates", client_id)

        # Send initial state
        emit("ml_status", {"connected": True, "subscribers": len(ml_subscribers), "timestamp": None})
    except Exception as e:
        logger.error("Error in ml_subscribe handler: %s", e, exc_info=True)
        emit("error", {"message": str(e)})


@socketio.on("ml_unsubscribe", namespace=SOCKETIO_NAMESPACE_SYSTEM)
def handle_ml_unsubscribe():
    """Unsubscribe from ML infrastructure updates"""
    client_id = request.sid
    ml_subscribers.discard(client_id)
    leave_room("ml_updates")

    logger.info("Client %s unsubscribed from ML updates", client_id)


@socketio.on("request_drift_update", namespace=SOCKETIO_NAMESPACE_SYSTEM)
def handle_drift_request(data):
    """Client requests drift metrics for a specific model"""
    model_name = data.get("model_name")

    if not model_name:
        emit("error", {"message": "model_name is required"})
        return

    try:
        container = _container()
        if not container or not getattr(container, "drift_detector", None):
            emit("error", {"message": "ML services not available"})
            return

        drift_metrics = container.drift_detector.check_drift(model_name)
        drift_status = drift_metrics.to_dict() if hasattr(drift_metrics, "to_dict") else drift_metrics

        emit(
            "drift_update",
            {
                "model_name": model_name,
                "drift_detected": drift_status.get("drift_detected", False),
                "metrics": drift_status,
                "timestamp": None,
            },
        )

    except Exception as e:
        logger.error("Error fetching drift metrics: %s", e)
        emit("error", {"message": str(e)})


@socketio.on("request_training_status", namespace=SOCKETIO_NAMESPACE_SYSTEM)
def handle_training_status_request(data):
    """Client requests current training status"""
    try:
        container = _container()
        registry = getattr(container, "model_registry", None) if container else None
        if not registry:
            emit("error", {"message": "Model registry not available"})
            return

        models = registry.list_models()

        emit("training_status", {"models": models, "timestamp": None})

    except Exception as e:
        logger.error("Error fetching training status: %s", e)
        emit("error", {"message": str(e)})


# =====================================
# BROADCAST FUNCTIONS (called from ML services)
# =====================================


def broadcast_training_started(model_name, version):
    """Broadcast training start event to all subscribers"""
    try:
        socketio.emit(
            "training_started",
            {"model_name": model_name, "version": version, "timestamp": None},
            namespace=SOCKETIO_NAMESPACE_SYSTEM,
            room="ml_updates",
        )

        logger.info("Broadcasted training start: %s v%s", model_name, version)
    except Exception as e:
        logger.error("Error broadcasting training start: %s", e)


def broadcast_training_progress(
    model_name,
    version,
    progress,
    metrics=None,
    stage=None,
    message=None,
    elapsed_seconds=None,
    eta_seconds=None,
):
    """Broadcast training progress updates."""
    try:
        payload = {
            "model_name": model_name,
            "version": version,
            "progress": progress,  # 0-100
            "metrics": metrics or {},
            "timestamp": None,
        }
        if stage is not None:
            payload["stage"] = stage
        if message is not None:
            payload["message"] = message
        if elapsed_seconds is not None:
            payload["elapsed_seconds"] = elapsed_seconds
        if eta_seconds is not None:
            payload["eta_seconds"] = eta_seconds

        socketio.emit("training_progress", payload, namespace=SOCKETIO_NAMESPACE_SYSTEM, room="ml_updates")

    except Exception as e:
        logger.error("Error broadcasting training progress: %s", e)


def broadcast_training_complete(model_name, version, metrics):
    """Broadcast training completion event"""
    try:
        socketio.emit(
            "training_complete",
            {"model_name": model_name, "version": version, "metrics": metrics, "timestamp": None},
            namespace=SOCKETIO_NAMESPACE_SYSTEM,
            room="ml_updates",
        )

        logger.info("Broadcasted training complete: %s v%s", model_name, version)
    except Exception as e:
        logger.error("Error broadcasting training complete: %s", e)


def broadcast_training_cancelled(model_name, version, message=None):
    """Broadcast training cancellation event."""
    try:
        socketio.emit(
            "training_cancelled",
            {
                "model_name": model_name,
                "version": version,
                "message": message or "Cancelled",
                "timestamp": None,
            },
            namespace=SOCKETIO_NAMESPACE_SYSTEM,
            room="ml_updates",
        )

        logger.info("Broadcasted training cancelled: %s v%s", model_name, version)
    except Exception as e:
        logger.error("Error broadcasting training cancelled: %s", e)


def broadcast_training_failed(model_name, version, error):
    """Broadcast training failure event"""
    try:
        socketio.emit(
            "training_failed",
            {"model_name": model_name, "version": version, "error": str(error), "timestamp": None},
            namespace=SOCKETIO_NAMESPACE_SYSTEM,
            room="ml_updates",
        )

        logger.error("Broadcasted training failure: %s v%s - %s", model_name, version, error)
    except Exception as e:
        logger.error("Error broadcasting training failure: %s", e)


def broadcast_drift_detected(model_name, drift_metrics):
    """Broadcast drift detection event"""
    try:
        socketio.emit(
            "drift_detected",
            {
                "model_name": model_name,
                "metrics": drift_metrics,
                "severity": "warning" if drift_metrics.get("drift_detected") else "info",
                "timestamp": None,
            },
            namespace=SOCKETIO_NAMESPACE_SYSTEM,
            room="ml_updates",
        )

        logger.warning("Broadcasted drift detected: %s", model_name)
    except Exception as e:
        logger.error("Error broadcasting drift detection: %s", e)


def broadcast_retraining_scheduled(model_name, scheduled_time):
    """Broadcast retraining schedule event"""
    try:
        socketio.emit(
            "retraining_scheduled",
            {"model_name": model_name, "scheduled_time": scheduled_time, "timestamp": None},
            namespace=SOCKETIO_NAMESPACE_SYSTEM,
            room="ml_updates",
        )

        logger.info("Broadcasted retraining scheduled: %s at %s", model_name, scheduled_time)
    except Exception as e:
        logger.error("Error broadcasting retraining schedule: %s", e)


def broadcast_model_activated(model_name, version):
    """Broadcast model activation event"""
    try:
        socketio.emit(
            "model_activated",
            {"model_name": model_name, "version": version, "timestamp": None},
            namespace=SOCKETIO_NAMESPACE_SYSTEM,
            room="ml_updates",
        )

        logger.info("Broadcasted model activated: %s v%s", model_name, version)
    except Exception as e:
        logger.error("Error broadcasting model activation: %s", e)
