"""Database operations for personalized learning profiles."""

from __future__ import annotations

import logging
import sqlite3
from typing import Any

from app.utils.time import iso_now

logger = logging.getLogger(__name__)


class PersonalizedLearningOperations:
    """Database operations for plant condition profiles."""

    def upsert_condition_profile(
        self,
        *,
        profile_key: str,
        user_id: int,
        plant_type: str,
        growth_stage: str,
        cultivar: str,
        strain: str,
        pot_size_liters: float,
        temperature_target: float | None,
        humidity_target: float | None,
        co2_target: float | None,
        voc_target: float | None,
        lux_target: float | None,
        air_quality_target: float | None,
        soil_moisture_target: float | None,
        confidence: float | None,
        source: str | None,
        created_at_utc: str | None = None,
        updated_at_utc: str | None = None,
    ) -> bool:
        """Insert or update a plant condition profile."""
        stamp = updated_at_utc or iso_now()
        created_at = created_at_utc or stamp
        try:
            db = self.get_db()
            db.execute(
                """
                INSERT INTO PlantConditionProfile (
                    profile_key,
                    user_id,
                    plant_type,
                    growth_stage,
                    cultivar,
                    strain,
                    pot_size_liters,
                    temperature_target,
                    humidity_target,
                    co2_target,
                    voc_target,
                    lux_target,
                    air_quality_target,
                    soil_moisture_target,
                    confidence,
                    source,
                    created_at_utc,
                    updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(profile_key) DO UPDATE SET
                    plant_type = excluded.plant_type,
                    growth_stage = excluded.growth_stage,
                    cultivar = excluded.cultivar,
                    strain = excluded.strain,
                    pot_size_liters = excluded.pot_size_liters,
                    temperature_target = excluded.temperature_target,
                    humidity_target = excluded.humidity_target,
                    co2_target = excluded.co2_target,
                    voc_target = excluded.voc_target,
                    lux_target = excluded.lux_target,
                    air_quality_target = excluded.air_quality_target,
                    soil_moisture_target = excluded.soil_moisture_target,
                    confidence = COALESCE(excluded.confidence, PlantConditionProfile.confidence),
                    source = excluded.source,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    profile_key,
                    user_id,
                    plant_type,
                    growth_stage,
                    cultivar,
                    strain,
                    pot_size_liters,
                    temperature_target,
                    humidity_target,
                    co2_target,
                    voc_target,
                    lux_target,
                    air_quality_target,
                    soil_moisture_target,
                    confidence,
                    source,
                    created_at,
                    stamp,
                ),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to upsert condition profile: %s", exc)
            return False

    def get_condition_profile_by_key(self, profile_key: str) -> dict[str, Any] | None:
        """Fetch a plant condition profile by key."""
        try:
            db = self.get_db()
            row = db.execute(
                "SELECT * FROM PlantConditionProfile WHERE profile_key = ?",
                (profile_key,),
            ).fetchone()
            return dict(row) if row else None
        except sqlite3.Error as exc:
            logger.error("Failed to fetch condition profile: %s", exc)
            return None

    def list_condition_profiles(
        self,
        *,
        user_id: int,
        plant_type: str | None = None,
        growth_stage: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """List condition profiles for a user with optional filters."""
        try:
            db = self.get_db()
            query = "SELECT * FROM PlantConditionProfile WHERE user_id = ?"
            params: list[Any] = [user_id]
            if plant_type:
                query += " AND plant_type = ?"
                params.append(plant_type)
            if growth_stage:
                query += " AND growth_stage = ?"
                params.append(growth_stage)
            query += " ORDER BY updated_at_utc DESC LIMIT ?"
            params.append(limit)
            rows = db.execute(query, params).fetchall()
            return [dict(row) for row in rows]
        except sqlite3.Error as exc:
            logger.error("Failed to list condition profiles: %s", exc)
            return []

    def update_condition_profile_rating(
        self,
        *,
        profile_key: str,
        rating_sum: float,
        rating_count: int,
        confidence: float | None,
        updated_at_utc: str | None = None,
    ) -> bool:
        """Update rating aggregates for a profile."""
        stamp = updated_at_utc or iso_now()
        try:
            db = self.get_db()
            db.execute(
                """
                UPDATE PlantConditionProfile
                SET rating_sum = ?,
                    rating_count = ?,
                    confidence = COALESCE(?, confidence),
                    updated_at_utc = ?
                WHERE profile_key = ?
                """,
                (rating_sum, rating_count, confidence, stamp, profile_key),
            )
            db.commit()
            return True
        except sqlite3.Error as exc:
            logger.error("Failed to update condition profile rating: %s", exc)
            return False
