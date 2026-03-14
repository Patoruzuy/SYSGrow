"""
Migration 053: Add irrigation reliability tables and execution claim columns.

Adds telemetry, eligibility tracing, manual irrigation logging, and plant
dry-down model tables. Also extends PendingIrrigationRequest with execution
claim metadata for concurrency-safe processing.
"""
import logging
import sqlite3
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 53
MIGRATION_NAME = "irrigation_reliability_tables"


def _table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _existing_columns(cursor: sqlite3.Cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _add_columns_if_missing(
    cursor: sqlite3.Cursor,
    table_name: str,
    columns: Iterable[tuple[str, str]],
) -> None:
    existing = _existing_columns(cursor, table_name)
    for col_name, col_type in columns:
        if col_name not in existing:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
            logger.info("Added column %s to %s", col_name, table_name)


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Apply irrigation reliability schema additions."""
    try:
        db = db_handler.get_db()
        cursor = db.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS IrrigationExecutionLog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                user_id INTEGER,
                unit_id INTEGER NOT NULL,
                plant_id INTEGER,
                sensor_id TEXT,
                trigger_reason TEXT NOT NULL,
                trigger_moisture REAL,
                threshold_at_trigger REAL,
                triggered_at_utc TEXT NOT NULL,
                planned_duration_s INTEGER,
                actual_duration_s INTEGER,
                pump_actuator_id TEXT,
                valve_actuator_id TEXT,
                assumed_flow_ml_s REAL,
                estimated_volume_ml REAL,
                execution_status TEXT NOT NULL,
                execution_error TEXT,
                executed_at_utc TEXT NOT NULL,
                post_moisture REAL,
                post_moisture_delay_s INTEGER,
                post_measured_at_utc TEXT,
                delta_moisture REAL,
                recommendation TEXT,
                created_at_utc TEXT NOT NULL,
                FOREIGN KEY (request_id) REFERENCES PendingIrrigationRequest(request_id),
                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
                FOREIGN KEY (user_id) REFERENCES Users(id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS IrrigationEligibilityTrace (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id INTEGER,
                unit_id INTEGER NOT NULL,
                sensor_id TEXT,
                moisture REAL,
                threshold REAL,
                decision TEXT NOT NULL,
                skip_reason TEXT,
                evaluated_at_utc TEXT NOT NULL,
                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ManualIrrigationLog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                unit_id INTEGER NOT NULL,
                plant_id INTEGER NOT NULL,
                watered_at_utc TEXT NOT NULL,
                amount_ml REAL,
                notes TEXT,
                pre_moisture REAL,
                pre_moisture_at_utc TEXT,
                post_moisture REAL,
                post_moisture_at_utc TEXT,
                settle_delay_min INTEGER DEFAULT 15,
                delta_moisture REAL,
                created_at_utc TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES Users(id),
                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS PlantIrrigationModel (
                plant_id INTEGER PRIMARY KEY,
                drydown_rate_per_hour REAL,
                sample_count INTEGER DEFAULT 0,
                confidence REAL,
                updated_at_utc TEXT NOT NULL,
                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS IrrigationLock (
                unit_id INTEGER PRIMARY KEY,
                locked_until_utc TEXT NOT NULL,
                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
            )
            """
        )

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_irrigation_execution_unit_time ON IrrigationExecutionLog(unit_id, executed_at_utc)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_irrigation_execution_plant_time ON IrrigationExecutionLog(plant_id, executed_at_utc)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_irrigation_execution_request ON IrrigationExecutionLog(request_id)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_irrigation_eligibility_unit_time ON IrrigationEligibilityTrace(unit_id, evaluated_at_utc)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_irrigation_eligibility_plant_time ON IrrigationEligibilityTrace(plant_id, evaluated_at_utc)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_manual_irrigation_plant_time ON ManualIrrigationLog(plant_id, watered_at_utc)"
        )

        if _table_exists(cursor, "PendingIrrigationRequest"):
            _add_columns_if_missing(
                cursor,
                "PendingIrrigationRequest",
                [
                    ("claimed_at_utc", "TEXT"),
                    ("attempt_count", "INTEGER DEFAULT 0"),
                    ("last_attempt_at_utc", "TEXT"),
                    ("execution_status", "TEXT"),
                ],
            )

        db.commit()
        logger.info("Migration %s (%s) completed successfully", MIGRATION_ID, MIGRATION_NAME)
        return True
    except sqlite3.Error as exc:
        logger.error("Migration %s failed: %s", MIGRATION_ID, exc)
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """Rollback is not supported for these schema additions."""
    logger.warning(
        "Rollback for migration %s not supported; manual intervention required.",
        MIGRATION_ID,
    )
    return False
