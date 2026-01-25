from __future__ import annotations

from flask import Blueprint, jsonify

status_bp = Blueprint("status", __name__)


@status_bp.get("/")
def status():
    return jsonify({"status": "ok"}), 200

