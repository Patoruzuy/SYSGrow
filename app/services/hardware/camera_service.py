"""
Camera Service for per-unit camera management.

This service manages multiple camera instances across growth units,
similar to how SensorManagementService manages sensors.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

from app.hardware.devices.camera_manager import CameraHandler, ESP32CameraController
from infrastructure.database.repositories.camera import CameraRepository

logger = logging.getLogger(__name__)


def _coerce_int(value: object) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _map_esp32_resolution(value: object) -> Optional[int]:
    """
    Map a stored resolution value to the ESP32 framesize integer (0-13).

    Historical data may contain strings like "640x480" instead of framesize codes.
    """
    if value is None or value == "":
        return None

    if isinstance(value, int):
        return value

    text = str(value).strip().lower()
    parsed = _coerce_int(text)
    if parsed is not None:
        return parsed

    mapping = {
        "96x96": 0,
        "160x120": 1,
        "176x144": 2,
        "240x176": 3,
        "240x240": 4,
        "320x240": 5,
        "400x296": 6,
        "480x320": 7,
        "640x480": 8,
        "800x600": 9,
        "1024x768": 10,
        "1280x720": 11,
        "1280x1024": 12,
        "1600x1200": 13,
    }
    return mapping.get(text)


class CameraService:
    """
    Singleton service for managing per-unit cameras.

    Responsibilities:
    - Maintain registry of camera instances per unit
    - Load and apply camera configurations from database
    - Start/stop cameras for specific units
    - Provide camera access for frame capture

    Similar to SensorManagementService pattern but for cameras.
    """

    def __init__(self, repository: CameraRepository):
        self.repository = repository
        self._cameras: Dict[int, CameraHandler] = {}
        self._camera_lock = threading.Lock()
        self._settings_controllers: Dict[int, ESP32CameraController] = {}
        logger.info("CameraService initialized")

    def get_camera_for_unit(self, unit_id: int) -> Optional[CameraHandler]:
        with self._camera_lock:
            return self._cameras.get(unit_id)

    def is_camera_running(self, unit_id: int) -> bool:
        camera = self.get_camera_for_unit(unit_id)
        return bool(camera and getattr(camera, "_running", False))

    def load_camera_settings(self, unit_id: int) -> Optional[Dict[str, Any]]:
        """
        Load camera settings for a specific unit from database.

        Returns a dictionary of camera settings or None if not found.
        """
        row = self.repository.get_unit_camera_config(unit_id)
        if row:
            device_index = row.get("device_index")
            safe_device_index = device_index if device_index is not None else 0

            return {
                "camera_type": row.get("camera_type"),
                "ip_address": row.get("ip_address"),
                "port": row.get("port") if row.get("port") is not None else 81,
                "device_index": safe_device_index,
                "usb_cam_index": safe_device_index,  # Backward compatibility
                "resolution": row.get("resolution"),
                "stream_url": row.get("stream_url"),
                "username": row.get("username"),
                "password": row.get("password"),
                "quality": row.get("quality"),
                "brightness": row.get("brightness"),
                "contrast": row.get("contrast"),
                "saturation": row.get("saturation"),
                "flip": row.get("flip"),
            }

        if self.repository.is_unit_camera_enabled(unit_id):
            logger.info(
                "Unit %s has camera enabled but no config; using defaults",
                unit_id,
            )
            return {
                "camera_type": "esp32",
                "ip_address": "192.168.1.100",
                "port": 81,
                "device_index": 0,
                "usb_cam_index": 0,
                "resolution": None,
                "stream_url": None,
                "username": None,
                "password": None,
                "quality": None,
                "brightness": None,
                "contrast": None,
                "saturation": None,
                "flip": None,
            }

        return None

    def save_camera_settings(
        self,
        *,
        unit_id: int,
        camera_type: str,
        ip_address: Optional[str] = None,
        port: Optional[int] = None,
        device_index: Optional[int] = None,
        resolution: Optional[str] = None,
        stream_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        quality: Optional[int] = None,
        brightness: Optional[int] = None,
        contrast: Optional[int] = None,
        saturation: Optional[int] = None,
        flip: Optional[int] = None,
    ) -> bool:
        """
        Save camera settings for a specific unit.

        For updates, optional image fields use COALESCE to avoid overwriting existing
        values when the client omits them.
        """
        success = self.repository.save_unit_camera_config(
            unit_id=unit_id,
            camera_type=camera_type,
            ip_address=ip_address,
            port=port,
            device_index=device_index,
            resolution=resolution,
            stream_url=stream_url,
            username=username,
            password=password,
            quality=quality,
            brightness=brightness,
            contrast=contrast,
            saturation=saturation,
            flip=flip,
        )
        if success:
            logger.info("Saved camera settings for unit %s: %s", unit_id, camera_type)
        return success

    def start_camera(self, unit_id: int) -> bool:
        """
        Start camera for a specific growth unit.

        Raises:
            RuntimeError / ValueError for invalid or missing configuration.
        """
        if self.is_camera_running(unit_id):
            logger.info("Camera for unit %s is already running", unit_id)
            return True

        settings = self.load_camera_settings(unit_id)
        if not settings:
            raise RuntimeError(f"No camera settings found for unit {unit_id}")

        camera_type = settings.get("camera_type")
        if not camera_type:
            raise RuntimeError(f"Missing camera_type for unit {unit_id}")

        with self._camera_lock:
            existing_camera = self._cameras.pop(unit_id, None)
            if existing_camera:
                existing_camera.stop()

            self._settings_controllers.pop(unit_id, None)

            if camera_type == "esp32":
                ip_address = settings.get("ip_address")
                if not ip_address:
                    raise ValueError("ip_address is required for ESP32 camera type")

                stream_port = settings.get("port") or 81
                camera = CameraHandler(
                    camera_type="esp32",
                    ip_address=ip_address,
                    port=stream_port,
                )

                controller = ESP32CameraController(
                    ip_address=ip_address,
                    port=80,  # Control port (stream is usually on 81)
                )
                self._settings_controllers[unit_id] = controller

                try:
                    controller.apply_settings(
                        {
                            "resolution": _map_esp32_resolution(settings.get("resolution")),
                            "quality": _coerce_int(settings.get("quality")),
                            "brightness": _coerce_int(settings.get("brightness")),
                            "contrast": _coerce_int(settings.get("contrast")),
                            "saturation": _coerce_int(settings.get("saturation")),
                            "flip": _coerce_int(settings.get("flip")),
                        }
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to apply ESP32 camera settings for unit %s: %s",
                        unit_id,
                        exc,
                    )

            elif camera_type == "usb":
                device_index = settings.get("device_index")
                if device_index is None:
                    device_index = settings.get("usb_cam_index", 0)
                if device_index is None:
                    device_index = 0

                camera = CameraHandler(
                    camera_type="usb",
                    usb_cam_index=int(device_index),
                )

            elif camera_type in {"rtsp", "mjpeg", "http"}:
                stream_url = settings.get("stream_url")
                if not stream_url:
                    raise ValueError(f"stream_url is required for {camera_type} camera type")

                camera = CameraHandler(
                    camera_type=camera_type,
                    stream_url=stream_url,
                    username=settings.get("username"),
                    password=settings.get("password"),
                )

            else:
                raise RuntimeError(f"Unknown camera type: {camera_type}")

            camera.initialize()
            self._cameras[unit_id] = camera

        logger.info("Started %s camera for unit %s", camera_type, unit_id)
        return True

    def stop_camera(self, unit_id: int) -> bool:
        """Stop camera for a specific unit."""
        try:
            with self._camera_lock:
                camera = self._cameras.pop(unit_id, None)
                if not camera:
                    logger.warning("No camera running for unit %s", unit_id)
                    return False

                camera.stop()
                self._settings_controllers.pop(unit_id, None)
                logger.info("Stopped camera for unit %s", unit_id)
                return True

        except Exception as exc:
            logger.error(
                "Error stopping camera for unit %s: %s",
                unit_id,
                exc,
                exc_info=True,
            )
            return False

    def get_camera_frame(self, unit_id: int) -> Optional[bytes]:
        """Get current JPEG frame bytes for a unit camera."""
        camera = self.get_camera_for_unit(unit_id)
        if not camera:
            return None

        try:
            return camera.get_frame()
        except Exception as exc:
            logger.error("Error getting frame from unit %s camera: %s", unit_id, exc)
            return None

    def get_camera_settings_controller(self, unit_id: int) -> Optional[ESP32CameraController]:
        """Get the ESP32 camera settings controller for a unit (if any)."""
        return self._settings_controllers.get(unit_id)

    def stop_all_cameras(self) -> None:
        """Stop all cameras (cleanup on shutdown)."""
        with self._camera_lock:
            for unit_id, camera in list(self._cameras.items()):
                try:
                    camera.stop()
                    logger.info("Stopped camera for unit %s", unit_id)
                except Exception as exc:
                    logger.error("Error stopping camera for unit %s: %s", unit_id, exc)

            self._cameras.clear()
            self._settings_controllers.clear()
