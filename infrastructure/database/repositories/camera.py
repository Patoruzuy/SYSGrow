from __future__ import annotations

from typing import Any

from infrastructure.database.ops.camera import CameraOperations


class CameraRepository:
    """Facade for per-unit camera configuration persistence."""

    def __init__(self, backend: CameraOperations) -> None:
        self._backend = backend

    def get_unit_camera_config(self, unit_id: int) -> dict[str, Any] | None:
        return self._backend.get_unit_camera_config(unit_id)

    def save_unit_camera_config(
        self,
        *,
        unit_id: int,
        camera_type: str,
        ip_address: str | None = None,
        port: int | None = None,
        device_index: int | None = None,
        resolution: str | None = None,
        stream_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        quality: int | None = None,
        brightness: int | None = None,
        contrast: int | None = None,
        saturation: int | None = None,
        flip: int | None = None,
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
