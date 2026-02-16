from __future__ import annotations

from typing import Any

from infrastructure.database.ops.settings import SettingsOperations


class SettingsRepository:
    """Facade providing typed access to settings-related data."""

    def __init__(self, backend: SettingsOperations) -> None:
        self._backend = backend

    # Hotspot -----------------------------------------------------------------
    def get_hotspot(self) -> dict[str, Any] | None:
        return self._backend.load_hotspot_settings()

    def save_hotspot(self, *, ssid: str, encrypted_password: str) -> None:
        self._backend.save_hotspot_settings(ssid, encrypted_password)

    # Camera -------------------------------------------------------------------
    def get_camera(self) -> dict[str, Any] | None:
        return self._backend.load_camera_settings()

    def save_camera(
        self,
        *,
        camera_type: str,
        ip_address: str | None,
        usb_cam_index: int | None,
        last_used: str | None,
        resolution: int | None,
        quality: int | None,
        brightness: int | None,
        contrast: int | None,
        saturation: int | None,
        flip: int | None,
    ) -> None:
        self._backend.save_camera_settings(
            camera_type,
            ip_address,
            usb_cam_index,
            last_used,
            resolution,
            quality,
            brightness,
            contrast,
            saturation,
            flip,
        )

    # Thresholds & schedules ---------------------------------------------------
    def get_environment_thresholds(self) -> dict[str, Any] | None:
        return self._backend.get_environment_thresholds()

    def save_environment_thresholds(
        self,
        *,
        temperature_threshold: float,
        humidity_threshold: float,
        soil_moisture_threshold: float,
    ) -> None:
        self._backend.save_environment_thresholds(temperature_threshold, humidity_threshold, soil_moisture_threshold)

    # ESP32-C3 Device Management -------------------------------------------
    def get_esp32_c6_devices(self) -> list[dict[str, Any]]:
        return self._backend.get_esp32_c6_devices()

    def get_esp32_c6_device(self, device_id: str) -> dict[str, Any] | None:
        return self._backend.get_esp32_c6_device(device_id)

    def save_esp32_c6_device(self, device_id: str, device_data: dict[str, Any]) -> None:
        self._backend.save_esp32_c6_device(device_id, device_data)

    def delete_esp32_c6_device(self, device_id: str) -> bool:
        return self._backend.delete_esp32_c6_device(device_id)
