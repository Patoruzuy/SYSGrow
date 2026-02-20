"""
Camera Settings Management
===========================

Endpoints for managing camera configuration including type, IP address,
USB settings, and image quality parameters.
"""

from __future__ import annotations

from flask import Response

from app.blueprints.api._common import (
    fail as _fail,
    get_json as _json,
    get_settings_service as _service,
    success as _success,
)
from app.utils.http import safe_route

from . import settings_api


@settings_api.get("/camera")
@safe_route("Failed to get camera settings")
def get_camera_settings() -> Response:
    """
    Get current camera configuration.

    Returns:
        - camera_type: Type of camera (ip, usb, pi)
        - ip_address: IP address for network cameras
        - usb_cam_index: USB camera device index
        - resolution: Image resolution
        - quality: JPEG quality (0-100)
        - brightness: Brightness adjustment
        - contrast: Contrast adjustment
        - saturation: Color saturation
        - flip: Image flip settings
        - last_used: Last used timestamp
    """
    data = _service().get_camera_settings()
    if not data:
        return _fail("Camera settings not configured.", 404)
    return _success(data, 200)


@settings_api.put("/camera")
@safe_route("Failed to update camera settings")
def update_camera_settings() -> Response:
    """
    Update camera configuration.

    Request Body:
        - camera_type (required): Camera type (ip, usb, pi)
        - ip_address (optional): IP address for network cameras
        - usb_cam_index (optional): USB device index
        - resolution (optional): Image resolution (e.g., "1920x1080")
        - quality (optional): JPEG quality 0-100
        - brightness (optional): Brightness adjustment
        - contrast (optional): Contrast adjustment
        - saturation (optional): Color saturation
        - flip (optional): Image flip settings
        - last_used (optional): Last used timestamp
    """
    payload = _json()
    camera_type = payload.get("camera_type")
    if not camera_type:
        return _fail("camera_type is required.", 400)
    data = _service().update_camera_settings(
        camera_type=camera_type,
        ip_address=payload.get("ip_address"),
        usb_cam_index=payload.get("usb_cam_index"),
        resolution=payload.get("resolution"),
        quality=payload.get("quality"),
        brightness=payload.get("brightness"),
        contrast=payload.get("contrast"),
        saturation=payload.get("saturation"),
        flip=payload.get("flip"),
        last_used=payload.get("last_used"),
    )
    return _success(data, 200)
