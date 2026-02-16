from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.utils.time import iso_now
from infrastructure.database.repositories.settings import SettingsRepository

if TYPE_CHECKING:
    from app.services.application.growth_service import GrowthService
    from app.services.hardware import SensorManagementService

import logging

logger = logging.getLogger(__name__)


@dataclass
class SettingsService:
    """
    High-level API for managing application-wide settings.

    Bidirectional Dependencies:
        - growth_service: Set by ContainerBuilder for unit management operations
        - sensor_service: Set by ContainerBuilder for sensor configuration

    Note: Environment thresholds are now managed per-unit by ThresholdService.
    Use ThresholdService.get_environment_thresholds(unit_id=...) for unit thresholds.
    """

    repository: SettingsRepository
    growth_service: "GrowthService" | None = None
    sensor_service: "SensorManagementService" | None = None

    # --- Hotspot -----------------------------------------------------------------
    def get_hotspot_settings(self) -> dict[str, Any] | None:
        record = self.repository.get_hotspot()
        if not record:
            return None
        return {
            "ssid": record.get("ssid"),
            "encrypted_password": record.get("encrypted_password"),
            "password_present": bool(record.get("encrypted_password")),
        }

    def update_hotspot_settings(self, *, ssid: str, encrypted_password: str | None = None) -> dict[str, Any]:
        current = self.repository.get_hotspot() or {}
        password = encrypted_password if encrypted_password is not None else current.get("encrypted_password")
        if password is None:
            raise ValueError("Hotspot password is required for initial configuration.")

        self.repository.save_hotspot(ssid=ssid, encrypted_password=password)
        return {
            "ssid": ssid,
            "password_present": True,
        }

    # --- Camera ------------------------------------------------------------------
    def get_camera_settings(self) -> dict[str, Any] | None:
        return self.repository.get_camera()

    def update_camera_settings(
        self,
        *,
        camera_type: str,
        ip_address: str | None = None,
        usb_cam_index: int | None = None,
        resolution: int | None = None,
        quality: int | None = None,
        brightness: int | None = None,
        contrast: int | None = None,
        saturation: int | None = None,
        flip: int | None = None,
        last_used: str | None = None,
    ) -> dict[str, Any]:
        current = self.repository.get_camera() or {}
        payload = {
            "camera_type": camera_type,
            "ip_address": ip_address if ip_address is not None else current.get("ip_address"),
            "usb_cam_index": usb_cam_index if usb_cam_index is not None else current.get("usb_cam_index"),
            "resolution": resolution if resolution is not None else current.get("resolution"),
            "quality": quality if quality is not None else current.get("quality"),
            "brightness": brightness if brightness is not None else current.get("brightness"),
            "contrast": contrast if contrast is not None else current.get("contrast"),
            "saturation": saturation if saturation is not None else current.get("saturation"),
            "flip": flip if flip is not None else current.get("flip", 0),
            "last_used": last_used or current.get("last_used") or iso_now(timespec="seconds"),
        }

        self.repository.save_camera(
            camera_type=payload["camera_type"],
            ip_address=payload["ip_address"],
            usb_cam_index=payload["usb_cam_index"],
            last_used=payload["last_used"],
            resolution=payload["resolution"],
            quality=payload["quality"],
            brightness=payload["brightness"],
            contrast=payload["contrast"],
            saturation=payload["saturation"],
            flip=payload["flip"],
        )
        return self.get_camera_settings() or payload
