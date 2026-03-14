from __future__ import annotations

from typing import Any
from flask import Response, jsonify
from app.utils.time import iso_now


def success_response(
    data: dict | list | None = None,
    status: int = 200,
    *,
    message: str | None = None,
) -> Response:
    payload: dict[str, Any] = {"ok": True, "data": data, "error": None}
    if message is not None:
        payload["message"] = message
    response = jsonify(payload)
    response.status_code = status
    return response


def error_response(
    message: str,
    status: int = 500,
    *,
    details: dict | None = None,
) -> Response:
    payload: dict[str, Any] = {"message": message, "timestamp": iso_now()}
    if details:
        payload.update(details)
    response_body: dict[str, Any] = {
        "ok": False,
        "data": None,
        "error": payload,
        "message": message,
    }
    if details:
        response_body["details"] = details
    response = jsonify(response_body)
    response.status_code = status
    return response
