from __future__ import annotations

from typing import Any, Dict, Optional

from infrastructure.database.ops.camera import CameraOperations


class CameraRepository:
    """Facade for per-unit camera configuration persistence."""

    def __init__(self, backend: CameraOperations) -> None:
        self._backend = backend

    def get_unit_camera_config(self, unit_id: int) -> Optional[Dict[str, Any]]:
        return self._backend.get_unit_camera_config(unit_id)

    def save_unit_camera_config(
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
        return self._backend.save_unit_camera_config(
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

    def is_unit_camera_enabled(self, unit_id: int) -> bool:
        return self._backend.is_unit_camera_enabled(unit_id)

