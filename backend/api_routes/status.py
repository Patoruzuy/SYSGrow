# Flask route to expose sensor uptime status
from flask import Blueprint, jsonify
from datetime import datetime

status_bp = Blueprint("status", __name__)

# This should be injected or imported from your polling service instance
polling_service = None  # Replace with actual SensorPollingService instance

@status_bp.route("/status", methods=["GET"])
def get_status():
    """
    Returns the last seen timestamps of all active MQTT sensors
    along with time since last heartbeat.
    """
    if not polling_service or not hasattr(polling_service, "mqtt_last_seen"):
        return jsonify({"error": "Polling service not initialized"}), 503

    now = datetime.now()
    sensor_status = {}
    for sensor_id, last_seen in polling_service.mqtt_last_seen.items():
        seconds_ago = (now - last_seen).total_seconds()
        sensor_status[sensor_id] = {
            "last_seen": last_seen.isoformat(),
            "seconds_since_last": int(seconds_ago),
            "status": "online" if seconds_ago < 120 else "stale"
        }

    return jsonify({"sensors": sensor_status})
