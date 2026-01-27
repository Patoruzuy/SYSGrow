from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from infrastructure.database.repositories.settings import SettingsRepository
from app.utils.time import iso_now

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
    growth_service: Optional['GrowthService'] = None
    sensor_service: Optional['SensorManagementService'] = None

    # --- Hotspot -----------------------------------------------------------------
    def get_hotspot_settings(self) -> Optional[Dict[str, Any]]:
        record = self.repository.get_hotspot()
        if not record:
            return None
        return {
            "ssid": record.get("ssid"),
            "encrypted_password": record.get("encrypted_password"),
            "password_present": bool(record.get("encrypted_password")),
        }

    def update_hotspot_settings(self, *, ssid: str, encrypted_password: Optional[str] = None) -> Dict[str, Any]:
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
    def get_camera_settings(self) -> Optional[Dict[str, Any]]:
        return self.repository.get_camera()

    def update_camera_settings(
        self,
        *,
        camera_type: str,
        ip_address: Optional[str] = None,
        usb_cam_index: Optional[int] = None,
        resolution: Optional[int] = None,
        quality: Optional[int] = None,
        brightness: Optional[int] = None,
        contrast: Optional[int] = None,
        saturation: Optional[int] = None,
        flip: Optional[int] = None,
        last_used: Optional[str] = None,
    ) -> Dict[str, Any]:
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
