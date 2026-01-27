"""
Migration 029: Add disease occurrence tracking tables.

Creates tables for tracking disease occurrences and prediction feedback
to enable ML training for disease prediction models.

Author: SYSGrow Team
Date: January 2026
"""
import logging
import sqlite3
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)

MIGRATION_ID = 30
MIGRATION_NAME = "disease_tracking"


def migrate(db_handler: "SQLiteDatabaseHandler") -> bool:
    """
    Create disease tracking tables for ML training.
    
    New tables:
    - DiseaseOccurrence: Records confirmed disease occurrences
    - DiseasePredictionFeedback: Tracks prediction accuracy for model improvement
    """
    try:
        db = db_handler.get_db()
        cursor = db.cursor()
        
        # ========== DiseaseOccurrence table ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS DiseaseOccurrence (
                occurrence_id INTEGER PRIMARY KEY AUTOINCREMENT,
                unit_id INTEGER NOT NULL,
                plant_id INTEGER,
                disease_type TEXT NOT NULL,  -- fungal, bacterial, pest, nutrient_deficiency, environmental_stress
                severity TEXT NOT NULL DEFAULT 'mild',  -- mild, moderate, severe
                detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                
                -- Environmental snapshot at time of detection
                temperature_at_detection REAL,
                humidity_at_detection REAL,
                soil_moisture_at_detection REAL,
                vpd_at_detection REAL,
                
                -- 72-hour averages before detection (for pattern recognition)
                avg_temperature_72h REAL,
                avg_humidity_72h REAL,
                avg_soil_moisture_72h REAL,
                humidity_variance_72h REAL,  -- High variance = poor air circulation
                
                -- User confirmation and treatment
                confirmed_by_user BOOLEAN DEFAULT FALSE,
                symptoms TEXT,  -- JSON list of observed symptoms
                affected_parts TEXT,  -- leaves, stems, roots, fruit, etc.
                treatment_applied TEXT,
                treatment_date TIMESTAMP,
                resolved_at TIMESTAMP,
                resolution_notes TEXT,
                
                -- Context
                plant_type TEXT,
                growth_stage TEXT,
                days_in_stage INTEGER,
                
                -- Metadata
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
                FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
            )
        """)
        logger.info("✓ Created DiseaseOccurrence table")
        
        # ========== DiseasePredictionFeedback table ==========
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS DiseasePredictionFeedback (
                feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id TEXT UNIQUE NOT NULL,  -- UUID from prediction
                unit_id INTEGER NOT NULL,
                
                -- What was predicted
                predicted_disease_type TEXT NOT NULL,
                predicted_risk_level TEXT NOT NULL,  -- low, moderate, high, critical
                predicted_risk_score REAL NOT NULL,
                prediction_timestamp TIMESTAMP NOT NULL,
                
                -- Contributing factors at prediction time (JSON)
                contributing_factors TEXT,
                
                -- What actually happened
                actual_disease_occurred BOOLEAN,
                actual_disease_type TEXT,
                actual_severity TEXT,
                days_to_occurrence INTEGER,  -- If disease occurred, how many days after prediction
                
                -- Feedback timing
                feedback_timestamp TIMESTAMP,
                feedback_source TEXT DEFAULT 'user',  -- user, auto_detected, follow_up
                
                -- For calculating prediction quality
                was_true_positive BOOLEAN,  -- Predicted high risk AND disease occurred
                was_false_positive BOOLEAN,  -- Predicted high risk BUT no disease
                was_true_negative BOOLEAN,  -- Predicted low risk AND no disease
                was_false_negative BOOLEAN,  -- Predicted low risk BUT disease occurred
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
            )
        """)
        logger.info("✓ Created DiseasePredictionFeedback table")
        
        # ========== Indexes ==========
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_disease_occurrence_unit ON DiseaseOccurrence(unit_id)",
            "CREATE INDEX IF NOT EXISTS idx_disease_occurrence_type ON DiseaseOccurrence(disease_type)",
            "CREATE INDEX IF NOT EXISTS idx_disease_occurrence_detected ON DiseaseOccurrence(detected_at DESC)",
            "CREATE INDEX IF NOT EXISTS idx_disease_occurrence_plant_type ON DiseaseOccurrence(plant_type)",
            "CREATE INDEX IF NOT EXISTS idx_disease_prediction_unit ON DiseasePredictionFeedback(unit_id)",
            "CREATE INDEX IF NOT EXISTS idx_disease_prediction_timestamp ON DiseasePredictionFeedback(prediction_timestamp DESC)",
            "CREATE INDEX IF NOT EXISTS idx_disease_prediction_type ON DiseasePredictionFeedback(predicted_disease_type)",
        ]
        
        for idx_sql in indexes:
            cursor.execute(idx_sql)
        logger.info("✓ Created disease tracking indexes")
        
        db.commit()
        logger.info(f"✅ Migration {MIGRATION_ID} ({MIGRATION_NAME}) completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Migration {MIGRATION_ID} failed: {e}", exc_info=True)
        return False


def rollback(db_handler: "SQLiteDatabaseHandler") -> bool:
    """
    Rollback migration by dropping created tables.
    """
    try:
        db = db_handler.get_db()
        cursor = db.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS DiseasePredictionFeedback")
        cursor.execute("DROP TABLE IF EXISTS DiseaseOccurrence")
        
        db.commit()
        logger.info(f"✅ Migration {MIGRATION_ID} rolled back successfully")
        return True
        
    except Exception as e:
        logger.error(f"Rollback of migration {MIGRATION_ID} failed: {e}", exc_info=True)
        return False
