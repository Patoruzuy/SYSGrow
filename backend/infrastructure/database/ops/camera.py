from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CameraOperations:
    """Camera (per-unit) database operations."""

    def get_unit_camera_config(self, unit_id: int) -> Optional[Dict[str, Any]]:
        """Return per-unit camera config row or None."""
        try:
            db = self.get_db()
            row = db.execute(
                """
                SELECT camera_type, ip_address, port, device_index, resolution,
                       stream_url, username, password,
                       quality, brightness, contrast, saturation, flip
                FROM camera_configs
                WHERE unit_id = ?
                LIMIT 1
                """,
                (unit_id,),
            ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error(
                "Error loading camera config for unit %s: %s",
                unit_id,
                exc,
                exc_info=True,
            )
            return None

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
        """
        Insert or update per-unit camera config.

        For updates, optional image fields use COALESCE to avoid overwriting existing
        values when the client omits them.
        """
        try:
            db = self.get_db()
            existing = db.execute(
                "SELECT camera_id FROM camera_configs WHERE unit_id = ?",
                (unit_id,),
            ).fetchone()

            if existing:
                db.execute(
                    """
                    UPDATE camera_configs
                    SET camera_type = ?,
                        ip_address = ?,
                        port = ?,
                        device_index = ?,
                        resolution = COALESCE(?, resolution),
                        stream_url = ?,
                        username = ?,
                        password = ?,
                        quality = COALESCE(?, quality),
                        brightness = COALESCE(?, brightness),
                        contrast = COALESCE(?, contrast),
                        saturation = COALESCE(?, saturation),
                        flip = COALESCE(?, flip)
                    WHERE unit_id = ?
                    """,
                    (
                        camera_type,
                        ip_address,
                        port,
                        device_index,
                        resolution,
                        stream_url,
                        username,
                        password,
                        quality,
                        brightness,
                        contrast,
                        saturation,
                        flip,
                        unit_id,
                    ),
                )
            else:
                insert_resolution = resolution if resolution is not None else "640x480"
                insert_quality = quality if quality is not None else 10
                insert_brightness = brightness if brightness is not None else 0
                insert_contrast = contrast if contrast is not None else 0
                insert_saturation = saturation if saturation is not None else 0
                insert_flip = flip if flip is not None else 0

                db.execute(
                    """
                    INSERT INTO camera_configs
                    (unit_id, camera_type, ip_address, port, device_index, resolution,
                     stream_url, username, password,
                     quality, brightness, contrast, saturation, flip)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        unit_id,
                        camera_type,
                        ip_address,
                        port,
                        device_index,
                        insert_resolution,
                        stream_url,
                        username,
                        password,
                        insert_quality,
                        insert_brightness,
                        insert_contrast,
                        insert_saturation,
                        insert_flip,
                    ),
                )

            db.commit()
            return True

        except sqlite3.Error as exc:
            logger.error(
                "Error saving camera config for unit %s: %s",
                unit_id,
                exc,
                exc_info=True,
            )
            return False

    def is_unit_camera_enabled(self, unit_id: int) -> bool:
        """Return GrowthUnits.camera_enabled flag (legacy fallback)."""
        try:
            db = self.get_db()
            row = db.execute(
                "SELECT camera_enabled FROM GrowthUnits WHERE unit_id = ?",
                (unit_id,),
            ).fetchone()
            return bool(row and row["camera_enabled"])
        except sqlite3.Error as exc:
            logger.error(
                "Error checking camera_enabled flag for unit %s: %s",
                unit_id,
                exc,
                exc_info=True,
            )
            return False

