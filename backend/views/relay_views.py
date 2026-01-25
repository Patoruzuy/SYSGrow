# === Flask View Integration (relay_views.py) ===

from flask import Blueprint, render_template, jsonify
from utils.relay_monitor import RelayMonitor

relay_bp = Blueprint("relay", __name__)
relay_monitor = RelayMonitor()

@relay_bp.route("/relays")
def show_all_relay_status():
    """
    Renders a dashboard page with all relay states grouped by Unit.
    """
    status_by_unit = relay_monitor.get_all_unit_status()
    return render_template("relay_status.html", relays=status_by_unit)


@relay_bp.route("/api/relays")
def get_relay_status_api():
    """
    API endpoint to return relay status JSON for UI polling.
    """
    status_by_unit = relay_monitor.get_all_unit_status()
    return jsonify(status_by_unit)
