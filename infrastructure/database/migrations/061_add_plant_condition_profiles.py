"""
Migration 061: Add PlantConditionProfile table.

Stores per-user, per-plant-stage learned condition profiles for reuse.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MIGRATION_VERSION = 61


def migrate(db_handler) -> bool:
    try:
        with db_handler.connection() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS PlantConditionProfile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_key TEXT NOT NULL UNIQUE,
                    user_id INTEGER NOT NULL,
                    plant_type TEXT NOT NULL,
                    growth_stage TEXT NOT NULL,
                    cultivar TEXT NOT NULL DEFAULT '',
                    strain TEXT NOT NULL DEFAULT '',
                    pot_size_liters REAL NOT NULL DEFAULT 0.0,
                    temperature_target REAL,
                    humidity_target REAL,
                    co2_target REAL,
                    voc_target REAL,
                    lux_target REAL,
                    air_quality_target REAL,
                    soil_moisture_target REAL,
                    rating_sum REAL NOT NULL DEFAULT 0.0,
                    rating_count INTEGER NOT NULL DEFAULT 0,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    source TEXT,
                    created_at_utc TEXT NOT NULL,
                    updated_at_utc TEXT NOT NULL
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_plant_condition_profile_user ON PlantConditionProfile(user_id)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS idx_plant_condition_profile_type_stage ON PlantConditionProfile(plant_type, growth_stage)"
            )
        logger.info("✓ Migration %s completed: PlantConditionProfile table ready", MIGRATION_VERSION)
        return True
    except Exception as exc:
        logger.error("Migration %s failed: %s", MIGRATION_VERSION, exc)
        return False
