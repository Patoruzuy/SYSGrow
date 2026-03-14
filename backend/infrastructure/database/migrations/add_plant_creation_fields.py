"""
Database Migration: Add Plant Creation Fields
==============================================
Adds container, variety, and planning fields to Plants table.

These are fields the user knows at planting time:
- Container: pot_size_liters, pot_material, growing_medium, medium_ph
- Variety: strain_variety
- Planning: expected_yield_grams, light_distance_cm
"""
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def apply_migration(db_path: str) -> None:
    """Apply migration to add creation-time plant fields."""
    conn = sqlite3.connect(db_path)
    
    try:
        # Get existing columns
        cursor = conn.execute("PRAGMA table_info(Plants)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        logger.info(f"Found {len(existing_columns)} existing columns in Plants table")
        
        # Define new columns
        new_columns = [
            ("pot_size_liters", "REAL DEFAULT 0.0"),
            ("pot_material", "TEXT DEFAULT 'plastic'"),
            ("growing_medium", "TEXT DEFAULT 'soil'"),
            ("medium_ph", "REAL DEFAULT 7.0"),
            ("strain_variety", "TEXT"),
            ("expected_yield_grams", "REAL DEFAULT 0.0"),
            ("light_distance_cm", "REAL DEFAULT 0.0"),
        ]
        
        # Add columns that don't exist
        added_count = 0
        for column_name, column_def in new_columns:
            if column_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE Plants ADD COLUMN {column_name} {column_def}"
                    conn.execute(sql)
                    logger.info(f"Added column: {column_name}")
                    added_count += 1
                except sqlite3.Error as e:
                    logger.error(f"Failed to add column {column_name}: {e}")
            else:
                logger.debug(f"Column {column_name} already exists, skipping")
        
        conn.commit()
        logger.info(f"Migration completed. Added {added_count} new columns.")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Default database path
    db_path = Path(__file__).parent.parent.parent.parent / "database" / "sysgrow.db"
    
    print(f"Applying migration to: {db_path}")
    apply_migration(str(db_path))
    print("✓ Migration complete!")
