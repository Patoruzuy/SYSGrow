"""
Camera Control Operations
==========================

Endpoints for controlling camera hardware attached to growth units.
Includes start, stop, capture, feed, settings, and status operations.
"""

from __future__ import annotations

import logging

from flask import Response, request

from app.blueprints.api._common import (
    fail as _fail,
    get_camera_service as _camera_manager,
    get_growth_service as _service,
    success as _success,
)
from app.utils.time import iso_now

from . import growth_api

logger = logging.getLogger("growth_api.camera")


def _clean_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_int(
    value: object,
    *,
    field: str,
    errors: dict[str, str],
    default: int | None = None,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int | None:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        errors[field] = "must be an integer"
        return None

    if minimum is not None and parsed < minimum:
        errors[field] = f"must be >= {minimum}"
        return None
    if maximum is not None and parsed > maximum:
        errors[field] = f"must be <= {maximum}"
        return None
    return parsed


# ============================================================================
# CAMERA CONTROL
# ============================================================================


@growth_api.post("/units/<int:unit_id>/camera/start")
def start_camera(unit_id: int):
    """Start camera for a growth unit."""
    logger.info("Starting camera for growth unit %s", unit_id)
    try:
        if not _service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)

        camera_service = _camera_manager()
        if not camera_service:
            return _fail("Camera service not available", 503)

        camera_service.start_camera(unit_id)
        return _success(
            {
                "unit_id": unit_id,
                "camera_status": "started",
                "message": "Camera started successfully",
            }
        )

    except (ValueError, RuntimeError) as exc:
        logger.warning("Camera start failed for unit %s: %s", unit_id, exc)
        return safe_error(exc, 400)
    except Exception as exc:
        logger.exception("Error starting camera for unit %s: %s", unit_id, exc)
        return _fail(f"Failed to start camera: {exc!s}", 500)


@growth_api.post("/units/<int:unit_id>/camera/stop")
def stop_camera(unit_id: int):
    """Stop camera for a growth unit."""
    logger.info("Stopping camera for growth unit %s", unit_id)
    try:
        if not _service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)

        camera_service = _camera_manager()
        if not camera_service:
            return _fail("Camera service not available", 503)

        if camera_service.stop_camera(unit_id):
            return _success(
                {
                    "unit_id": unit_id,
                    "camera_status": "stopped",
                    "message": "Camera stopped successfully",
                }
            )
        return _fail("No camera running for this unit", 400)

    except Exception as exc:
        logger.exception("Error stopping camera for unit %s: %s", unit_id, exc)
        return _fail(f"Failed to stop camera: {exc!s}", 500)


@growth_api.post("/units/<int:unit_id>/camera/capture")
def capture_photo(unit_id: int):
    """Capture a photo with the growth unit camera."""
    logger.info("Capturing photo for growth unit %s", unit_id)
    try:
        if not _service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)

        camera_service = _camera_manager()
        if not camera_service:
            return _fail("Camera service not available", 503)

        frame = camera_service.get_camera_frame(unit_id)
        if frame:
            return _success(
                {
                    "unit_id": unit_id,
                    "message": "Photo captured successfully",
                    "timestamp": iso_now(),
                    "frame_size": len(frame),
                }
            )

        return _fail("Camera not started or no frame available. Please start camera first", 400)

    except Exception as exc:
        logger.exception("Error capturing photo for unit %s: %s", unit_id, exc)
        return _fail(f"Failed to capture photo: {exc!s}", 500)


@growth_api.get("/units/<int:unit_id>/camera/status")
def get_camera_status(unit_id: int):
    """Get camera status for a growth unit."""
    logger.info("Getting camera status for growth unit %s", unit_id)
    try:
        unit = _service().get_unit(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        camera_service = _camera_manager()
        if not camera_service:
            return _fail("Camera service not available", 503)

        camera_settings = camera_service.load_camera_settings(unit_id)
        is_running = camera_service.is_camera_running(unit_id)
        camera_enabled = camera_settings is not None

        return _success(
            {
                "unit_id": unit_id,
                "camera_enabled": camera_enabled,
                "camera_active": is_running,
                "camera_running": is_running,  # Backward compatibility
                "camera_type": camera_settings.get("camera_type") if camera_settings else None,
                "ip_address": (
                    camera_settings.get("ip_address")
                    if camera_settings and camera_settings.get("camera_type") == "esp32"
                    else None
                ),
                "settings": camera_settings or {},
            }
        )

    except Exception as exc:
        logger.exception("Error getting camera status for unit %s: %s", unit_id, exc)
        return _fail(f"Failed to get camera status: {exc!s}", 500)


@growth_api.put("/units/<int:unit_id>/camera/settings")
def update_camera_settings(unit_id: int):
    """Update camera settings for a growth unit."""
    logger.info("Updating camera settings for growth unit %s", unit_id)
    try:
        if not _service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)

        camera_service = _camera_manager()
        if not camera_service:
            return _fail("Camera service not available", 503)

        data = request.get_json(silent=True) or {}
        if not data:
            return _fail("No data provided", 400)

        camera_type = _clean_str(data.get("camera_type"))
        if not camera_type:
            return _fail("camera_type is required", 400)

        valid_types = ["esp32", "usb", "rtsp", "mjpeg", "http"]
        if camera_type not in valid_types:
            return _fail(f"Invalid camera_type. Must be one of: {', '.join(valid_types)}", 400)

        errors: dict[str, str] = {}

        # Normalize common fields
        ip_address = _clean_str(data.get("ip_address"))
        stream_url = _clean_str(data.get("stream_url"))
        username = _clean_str(data.get("username"))
        password = data.get("password")

        port: int | None = None
        device_index: int | None = None

        if camera_type == "esp32":
            if not ip_address:
                errors["ip_address"] = "ip_address is required for esp32 cameras"
            port = _coerce_int(
                data.get("port"),
                field="port",
                errors=errors,
                default=81,
                minimum=1,
                maximum=65535,
            )

            device_index = None
            stream_url = None
            username = None
            password = None
        elif camera_type == "usb":
            device_index = _coerce_int(
                data.get("device_index"),
                field="device_index",
                errors=errors,
                default=0,
                minimum=0,
            )
            ip_address = None
            port = None
            stream_url = None
            username = None
            password = None
        else:
            if not stream_url:
                errors["stream_url"] = f"stream_url is required for {camera_type} cameras"
            ip_address = None
            port = None
            device_index = None

        # Optional image settings (validated only when provided)
        resolution_raw = _clean_str(data.get("resolution"))
        resolution_value: int | str | None = None
        if resolution_raw is not None:
            if camera_type == "esp32":
                resolution_value = _coerce_int(
                    resolution_raw,
                    field="resolution",
                    errors=errors,
                    minimum=0,
                    maximum=13,
                )
            else:
                resolution_value = resolution_raw

        quality = _coerce_int(
            data.get("quality"),
            field="quality",
            errors=errors,
            minimum=0,
            maximum=63,
        )
        brightness = _coerce_int(
            data.get("brightness"),
            field="brightness",
            errors=errors,
            minimum=-2,
            maximum=2,
        )
        contrast = _coerce_int(
            data.get("contrast"),
            field="contrast",
            errors=errors,
            minimum=-2,
            maximum=2,
        )
        saturation = _coerce_int(
            data.get("saturation"),
            field="saturation",
            errors=errors,
            minimum=-2,
            maximum=2,
        )
        flip = _coerce_int(
            data.get("flip"),
            field="flip",
            errors=errors,
            minimum=0,
            maximum=3,
        )

        if errors:
            return _fail("Invalid camera settings", 400, details={"fields": errors})

        success = camera_service.save_camera_settings(
            unit_id=unit_id,
            camera_type=camera_type,
            ip_address=ip_address,
            port=port,
            device_index=device_index,
            resolution=str(resolution_value) if resolution_value is not None else None,
            stream_url=stream_url,
            username=username,
            password=password,
            quality=quality,
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            flip=flip,
        )

        if not success:
            return _fail("Failed to save camera settings", 500)

        restart_error = None
        if camera_service.is_camera_running(unit_id):
            try:
                camera_service.stop_camera(unit_id)
                camera_service.start_camera(unit_id)
            except Exception as exc:
                restart_error = str(exc)

        payload = {
            "unit_id": unit_id,
            "message": "Camera settings updated successfully",
            "camera_type": camera_type,
        }
        if restart_error:
            payload["restart_error"] = restart_error
        return _success(payload)

    except Exception as exc:
        logger.exception("Error updating camera settings for unit %s: %s", unit_id, exc)
        return _fail(f"Failed to update camera settings: {exc!s}", 500)


@growth_api.get("/units/<int:unit_id>/camera/feed")
def camera_feed(unit_id: int):
    """Stream camera feed for a growth unit (MJPEG stream)."""
    try:
        if not _service().get_unit(unit_id):
            logger.error("Growth unit %s not found", unit_id)
            return _fail(f"Growth unit {unit_id} not found", 404)

        camera_service = _camera_manager()
        if not camera_service:
            logger.error("Camera service not available")
            return _fail("Camera service not available", 503)

        camera = camera_service.get_camera_for_unit(unit_id)
        if not camera or not camera._running:
            logger.error("Camera not running for unit %s", unit_id)
            return _fail("Camera not started. Please start camera first", 400)

        def generate():
            """Generate MJPEG frames."""
            try:
                while camera._running:
                    frame = camera.get_frame()
                    if frame:
                        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
                    else:
                        import time

                        time.sleep(0.1)
            except Exception as exc:
                logger.error("Error in camera feed generator: %s", exc)

        return Response(
            generate(),
            mimetype="multipart/x-mixed-replace; boundary=frame",
        )

    except Exception as exc:
        logger.exception("Error streaming camera feed for unit %s: %s", unit_id, exc)
        return _fail(f"Failed to stream camera feed: {exc!s}", 500)
