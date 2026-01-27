"""
Cleanup Migration: Remove Legacy device_schedules Column
=========================================================

This migration removes the deprecated device_schedules JSON column
from the GrowthUnits table after data has been migrated to the
new DeviceSchedules table.

Prerequisites:
    - Phase 2 migration must be complete (migrate_device_schedules.py)
    - All device schedules should be in the DeviceSchedules table

Usage:
    # Validate that all data is migrated (dry run)
    python migrations/cleanup_device_schedules.py --validate
    
    # Remove the column
    python migrations/cleanup_device_schedules.py --execute
    
    # Skip confirmation prompt
    python migrations/cleanup_device_schedules.py --execute --force

Author: Sebastian Gomez
Date: January 2026
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_connection(db_path: str) -> sqlite3.Connection:
    """Get database connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def check_column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Check if a column exists in a table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row["name"] for row in cursor.fetchall()]
    return column in columns


def count_legacy_schedules(conn: sqlite3.Connection) -> dict:
    """
    Count schedules in the legacy device_schedules column.
    
    Returns:
        Dict with total_units, units_with_schedules, schedule_count
    """
    cursor = conn.execute("""
        SELECT unit_id, name, device_schedules
        FROM GrowthUnits
        WHERE device_schedules IS NOT NULL AND device_schedules != '{}'
    """)
    
    units_with_schedules = 0
    total_schedules = 0
    
    for row in cursor.fetchall():
        try:
            schedules = json.loads(row["device_schedules"] or "{}")
            if schedules:
                units_with_schedules += 1
                total_schedules += len(schedules)
        except (json.JSONDecodeError, TypeError):
            pass
    
    total_units = conn.execute("SELECT COUNT(*) FROM GrowthUnits").fetchone()[0]
    
    return {
        "total_units": total_units,
        "units_with_schedules": units_with_schedules,
        "legacy_schedule_count": total_schedules,
    }


def count_new_schedules(conn: sqlite3.Connection) -> int:
    """Count schedules in the new DeviceSchedules table."""
    try:
        result = conn.execute("SELECT COUNT(*) FROM DeviceSchedules").fetchone()
        return result[0] if result else 0
    except sqlite3.OperationalError:
        return 0


def validate_migration(conn: sqlite3.Connection) -> tuple[bool, str]:
    """
    Validate that all legacy schedules have been migrated.
    
    Returns:
        Tuple of (is_valid, message)
    """
    legacy = count_legacy_schedules(conn)
    new_count = count_new_schedules(conn)
    
    if legacy["legacy_schedule_count"] == 0:
        return True, "No legacy schedules found - column can be safely removed"
    
    if new_count >= legacy["legacy_schedule_count"]:
        return True, (
            f"Migration validated: {new_count} schedules in new table, "
            f"{legacy['legacy_schedule_count']} in legacy column"
        )
    
    return False, (
        f"Migration incomplete: {legacy['legacy_schedule_count']} legacy schedules, "
        f"but only {new_count} in new table. Run migrate_device_schedules.py first."
    )


def backup_column_data(conn: sqlite3.Connection, backup_path: Path) -> None:
    """Backup the device_schedules column data before removal."""
    cursor = conn.execute("""
        SELECT unit_id, name, device_schedules, created_at, updated_at
        FROM GrowthUnits
        WHERE device_schedules IS NOT NULL AND device_schedules != '{}'
    """)
    
    backup_data = []
    for row in cursor.fetchall():
        backup_data.append({
            "unit_id": row["unit_id"],
            "name": row["name"],
            "device_schedules": row["device_schedules"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })
    
    if backup_data:
        with open(backup_path, "w") as f:
            json.dump({
                "backup_timestamp": datetime.now().isoformat(),
                "units": backup_data,
            }, f, indent=2)
        logger.info(f"Backed up {len(backup_data)} units to {backup_path}")


def remove_column(conn: sqlite3.Connection) -> bool:
    """
    Remove the device_schedules column from GrowthUnits.
    
    SQLite doesn't support DROP COLUMN directly (before 3.35),
    so we recreate the table without the column.
    """
    logger.info("Removing device_schedules column from GrowthUnits...")
    
    # Get current table schema (without device_schedules)
    cursor = conn.execute("PRAGMA table_info(GrowthUnits)")
    columns = []
    for row in cursor.fetchall():
        if row["name"] != "device_schedules":
            columns.append(row["name"])
    
    if not columns:
        logger.error("Failed to get table schema")
        return False
    
    column_list = ", ".join(columns)
    
    try:
        # SQLite 3.35+ supports ALTER TABLE DROP COLUMN
        conn.execute("ALTER TABLE GrowthUnits DROP COLUMN device_schedules")
        conn.commit()
        logger.info("✅ Column removed using ALTER TABLE DROP COLUMN")
        return True
    except sqlite3.OperationalError as e:
        if "no such column" in str(e).lower():
            logger.info("Column already removed")
            return True
        # Fall back to table recreation for older SQLite versions
        logger.info("Using table recreation method for older SQLite version...")
    
    try:
        conn.execute("BEGIN TRANSACTION")
        
        # Create temporary table
        conn.execute(f"""
            CREATE TABLE GrowthUnits_new AS
            SELECT {column_list}
            FROM GrowthUnits
        """)
        
        # Drop old table
        conn.execute("DROP TABLE GrowthUnits")
        
        # Rename new table
        conn.execute("ALTER TABLE GrowthUnits_new RENAME TO GrowthUnits")
        
        # Recreate indexes
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_growth_units_user_id 
            ON GrowthUnits(user_id)
        """)
        
        conn.commit()
        logger.info("✅ Column removed using table recreation")
        return True
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to remove column: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Remove legacy device_schedules column after migration"
    )
    parser.add_argument(
        "--db-path",
        default="database/sysgrow.db",
        help="Path to SQLite database"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate migration without making changes"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute column removal"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt"
    )
    parser.add_argument(
        "--backup-path",
        default="migrations/backups/device_schedules_backup.json",
        help="Path for backup file"
    )
    
    args = parser.parse_args()
    
    if not args.validate and not args.execute:
        parser.print_help()
        print("\nError: Must specify --validate or --execute")
        sys.exit(1)
    
    # Check database exists
    if not Path(args.db_path).exists():
        logger.error(f"Database not found: {args.db_path}")
        sys.exit(1)
    
    conn = get_connection(args.db_path)
    
    try:
        # Check if column exists
        if not check_column_exists(conn, "GrowthUnits", "device_schedules"):
            logger.info("✅ device_schedules column already removed")
            sys.exit(0)
        
        # Validate migration
        is_valid, message = validate_migration(conn)
        logger.info(f"Validation: {message}")
        
        if args.validate:
            legacy = count_legacy_schedules(conn)
            new_count = count_new_schedules(conn)
            
            print("\n📊 Migration Status:")
            print(f"   Total units: {legacy['total_units']}")
            print(f"   Units with legacy schedules: {legacy['units_with_schedules']}")
            print(f"   Legacy schedule count: {legacy['legacy_schedule_count']}")
            print(f"   New table schedule count: {new_count}")
            print(f"\n   Status: {'✅ Ready for cleanup' if is_valid else '❌ Migration incomplete'}")
            sys.exit(0 if is_valid else 1)
        
        if args.execute:
            if not is_valid and not args.force:
                logger.error("Migration validation failed. Use --force to override.")
                sys.exit(1)
            
            if not args.force:
                response = input("\n⚠️  This will permanently remove the device_schedules column. Continue? [y/N]: ")
                if response.lower() != "y":
                    logger.info("Aborted.")
                    sys.exit(0)
            
            # Create backup
            backup_path = Path(args.backup_path)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_column_data(conn, backup_path)
            
            # Remove column
            if remove_column(conn):
                logger.info("\n✅ Cleanup complete! Legacy device_schedules column removed.")
                logger.info(f"   Backup saved to: {backup_path}")
            else:
                logger.error("Failed to remove column")
                sys.exit(1)
    
    finally:
        conn.close()


if __name__ == "__main__":
    main()
