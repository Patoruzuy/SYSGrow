# flask_app/views/units.py
from flask import Blueprint, render_template, jsonify
import redis
import json

units_bp = Blueprint("units", __name__)

# Redis client (adjust if using Flask extensions)
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

@units_bp.route("/units")
def show_modules_in_units():
    """
    Display all units and their registered modules.
    """
    units_data = {}  # { unit_id: [ {module_data}, ... ] }

    # Get all keys with the format: unit:<unit_id>:modules:<device_id>
    keys = r.keys("unit:*:modules:*")

    for key in keys:
        try:
            parts = key.split(":")
            unit_id = parts[1]
            device_id = parts[3]

            module_info_json = r.get(key)
            module_info = json.loads(module_info_json)

            if unit_id not in units_data:
                units_data[unit_id] = []

            module_info["device_id"] = device_id  # Add device_id to display
            units_data[unit_id].append(module_info)
        except Exception as e:
            print(f"Error parsing key {key}: {e}")
            continue

    return render_template("units.html", units=units_data)


@units_bp.route("/api/units")
def get_modules_in_units_json():
    """
    JSON endpoint: return units/modules for frontend or API use.
    """
    data = {}
    keys = r.keys("unit:*:modules:*")
    for key in keys:
        parts = key.split(":")
        unit_id = parts[1]
        module = json.loads(r.get(key))
        if unit_id not in data:
            data[unit_id] = []
        data[unit_id].append(module)

    return jsonify(data)
