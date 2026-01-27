"""
Migration script to migrate device_schedules JSON from GrowthUnits to DeviceSchedules table.

This script:
1. Reads all device_schedules JSON from GrowthUnits table
2. Converts each schedule to the new Schedule entity format
3. Inserts into the DeviceSchedules table
4. Validates data integrity after migration

Usage:
    python -m migrations.migrate_device_schedules --dry-run  # Preview changes
    python -m migrations.migrate_device_schedules            # Execute migration

Author: Sebastian Gomez
Date: January 2026
"""

import argparse
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScheduleMigration:
    """Migrates legacy device_schedules JSON to DeviceSchedules table."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        
    def __enter__(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
            
    def validate_schema(self) -> bool:
        """Verify that all required tables exist."""
        cursor = self.conn.cursor()
        
        required_tables = ['GrowthUnits', 'DeviceSchedules']
        
        for table in required_tables:
            result = cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            if not result:
                logger.error(f"Required table '{table}' does not exist")
                return False
                
        logger.info("✓ All required tables exist")
        return True
        
    def get_migration_stats(self) -> Dict[str, Any]:
        """Get current record counts and preview data."""
        cursor = self.conn.cursor()
        
        # Count units with schedules
        units_with_schedules = cursor.execute("""
            SELECT COUNT(*) FROM GrowthUnits 
            WHERE device_schedules IS NOT NULL 
            AND device_schedules != ''
            AND device_schedules != '{}'
        """).fetchone()[0]
        
        # Count existing DeviceSchedules records
        existing_schedules = cursor.execute(
            "SELECT COUNT(*) FROM DeviceSchedules"
        ).fetchone()[0]
        
        # Get all units with legacy schedules
        legacy_data = cursor.execute("""
            SELECT unit_id, name, device_schedules 
            FROM GrowthUnits 
            WHERE device_schedules IS NOT NULL 
            AND device_schedules != ''
            AND device_schedules != '{}'
        """).fetchall()
        
        # Count total individual schedules to migrate
        total_schedules = 0
        schedule_breakdown = {}
        for row in legacy_data:
            try:
                schedules = json.loads(row['device_schedules']) if row['device_schedules'] else {}
                for device_type in schedules:
                    total_schedules += 1
                    schedule_breakdown[device_type] = schedule_breakdown.get(device_type, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass
        
        return {
            'units_with_schedules': units_with_schedules,
            'total_legacy_schedules': total_schedules,
            'existing_new_schedules': existing_schedules,
            'schedule_breakdown': schedule_breakdown,
        }

    def get_legacy_schedules(self) -> List[Tuple[int, str, Dict[str, Any]]]:
        """
        Retrieve all legacy device_schedules from GrowthUnits.
        
        Returns:
            List of tuples: (unit_id, unit_name, schedules_dict)
        """
        cursor = self.conn.cursor()
        
        rows = cursor.execute("""
            SELECT unit_id, name, device_schedules 
            FROM GrowthUnits 
            WHERE device_schedules IS NOT NULL 
            AND device_schedules != ''
            AND device_schedules != '{}'
        """).fetchall()
        
        results = []
        for row in rows:
            try:
                schedules = json.loads(row['device_schedules']) if row['device_schedules'] else {}
                if schedules:
                    results.append((row['unit_id'], row['name'], schedules))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse schedules for unit {row['unit_id']}: {e}")
                
        return results

    def check_already_migrated(self, unit_id: int, device_type: str) -> bool:
        """Check if a schedule already exists in DeviceSchedules table."""
        cursor = self.conn.cursor()
        result = cursor.execute("""
            SELECT schedule_id FROM DeviceSchedules 
            WHERE unit_id = ? AND device_type = ?
            LIMIT 1
        """, (unit_id, device_type)).fetchone()
        return result is not None

    def convert_legacy_schedule(
        self,
        unit_id: int,
        device_type: str,
        schedule_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Convert legacy schedule format to new DeviceSchedules format.
        
        Legacy format:
            {"start_time": "08:00", "end_time": "20:00", "enabled": true}
            
        New format includes:
            - name, schedule_type, days_of_week, state_when_active, priority, etc.
        """
        now = datetime.now().isoformat()
        
        # Determine schedule type based on device
        schedule_type = 'photoperiod' if device_type == 'light' else 'simple'
        
        # Create photoperiod config for light schedules
        photoperiod_config = None
        if device_type == 'light':
            photoperiod_config = json.dumps({
                'source': 'schedule',
                'sensor_threshold': 100.0,
                'prefer_sensor': False,
                'sun_times': None,
                'min_light_hours': None,
                'max_light_hours': None,
            })
        
        return {
            'unit_id': unit_id,
            'name': f"{device_type.title()} Schedule",
            'device_type': device_type,
            'actuator_id': None,  # Legacy schedules don't have actuator links
            'schedule_type': schedule_type,
            'start_time': schedule_data.get('start_time', '08:00'),
            'end_time': schedule_data.get('end_time', '20:00'),
            'days_of_week': json.dumps([0, 1, 2, 3, 4, 5, 6]),  # All days by default
            'enabled': 1 if schedule_data.get('enabled', True) else 0,
            'state_when_active': 'on',
            'value': None,
            'photoperiod_config': photoperiod_config,
            'priority': 0,
            'metadata': json.dumps({'migrated_from': 'device_schedules', 'migration_date': now}),
            'created_at': now,
            'updated_at': now,
        }

    def migrate_schedules(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Migrate all legacy schedules to DeviceSchedules table.
        
        Args:
            dry_run: If True, don't actually insert data
            
        Returns:
            Migration results summary
        """
        cursor = self.conn.cursor()
        
        legacy_schedules = self.get_legacy_schedules()
        
        results = {
            'units_processed': 0,
            'schedules_migrated': 0,
            'schedules_skipped': 0,
            'errors': [],
        }
        
        for unit_id, unit_name, schedules in legacy_schedules:
            results['units_processed'] += 1
            logger.info(f"Processing unit {unit_id} ({unit_name}): {len(schedules)} schedules")
            
            for device_type, schedule_data in schedules.items():
                # Skip if already migrated
                if self.check_already_migrated(unit_id, device_type):
                    logger.debug(f"  Skipping {device_type} (already exists)")
                    results['schedules_skipped'] += 1
                    continue
                
                try:
                    new_schedule = self.convert_legacy_schedule(
                        unit_id, device_type, schedule_data
                    )
                    
                    if dry_run:
                        logger.info(f"  [DRY RUN] Would migrate {device_type}: "
                                  f"{schedule_data.get('start_time')} - {schedule_data.get('end_time')}")
                    else:
                        cursor.execute("""
                            INSERT INTO DeviceSchedules (
                                unit_id, name, device_type, actuator_id, schedule_type,
                                start_time, end_time, days_of_week, enabled, state_when_active,
                                value, photoperiod_config, priority, metadata, created_at, updated_at
                            ) VALUES (
                                :unit_id, :name, :device_type, :actuator_id, :schedule_type,
                                :start_time, :end_time, :days_of_week, :enabled, :state_when_active,
                                :value, :photoperiod_config, :priority, :metadata, :created_at, :updated_at
                            )
                        """, new_schedule)
                        logger.info(f"  ✓ Migrated {device_type}: "
                                  f"{schedule_data.get('start_time')} - {schedule_data.get('end_time')}")
                    
                    results['schedules_migrated'] += 1
                    
                except Exception as e:
                    error_msg = f"Failed to migrate {device_type} for unit {unit_id}: {e}"
                    logger.error(f"  ✗ {error_msg}")
                    results['errors'].append(error_msg)
        
        if not dry_run:
            self.conn.commit()
            logger.info("✓ Migration committed to database")
        
        return results

    def validate_migration(self) -> Dict[str, Any]:
        """Validate that migration was successful."""
        cursor = self.conn.cursor()
        
        # Get legacy schedules
        legacy = self.get_legacy_schedules()
        legacy_count = sum(len(schedules) for _, _, schedules in legacy)
        
        # Get migrated schedules
        migrated_count = cursor.execute(
            "SELECT COUNT(*) FROM DeviceSchedules WHERE metadata LIKE '%migrated_from%'"
        ).fetchone()[0]
        
        # Check for any units with legacy data but no migrated schedules
        missing = []
        for unit_id, unit_name, schedules in legacy:
            for device_type in schedules:
                exists = cursor.execute("""
                    SELECT 1 FROM DeviceSchedules 
                    WHERE unit_id = ? AND device_type = ?
                """, (unit_id, device_type)).fetchone()
                if not exists:
                    missing.append(f"Unit {unit_id} ({unit_name}): {device_type}")
        
        return {
            'legacy_schedule_count': legacy_count,
            'migrated_schedule_count': migrated_count,
            'missing_schedules': missing,
            'validation_passed': len(missing) == 0,
        }

    def rollback_migration(self) -> int:
        """
        Remove all migrated schedules (identified by metadata).
        
        Returns:
            Number of records deleted
        """
        cursor = self.conn.cursor()
        
        cursor.execute(
            "DELETE FROM DeviceSchedules WHERE metadata LIKE '%migrated_from%'"
        )
        deleted = cursor.rowcount
        
        self.conn.commit()
        logger.info(f"Rolled back {deleted} migrated schedules")
        
        return deleted


def find_database() -> str:
    """Find the database file path."""
    # Check common locations
    possible_paths = [
        Path("database/sysgrow.db"),
        Path("database/sysgrow_dev.db"),
        Path("instance/sysgrow.db"),
        Path("../instance/sysgrow.db"),
        Path("instance/database.db"),
        Path("database.db"),
    ]
    
    for path in possible_paths:
        if path.exists():
            return str(path.resolve())
    
    raise FileNotFoundError(
        "Could not find database file. Please specify with --db-path"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Migrate device_schedules JSON to DeviceSchedules table"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview migration without making changes'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        help='Path to SQLite database file'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback migration (delete migrated records)'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate migration status'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show migration statistics only'
    )
    
    args = parser.parse_args()
    
    # Find database
    try:
        db_path = args.db_path or find_database()
    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    
    logger.info(f"Using database: {db_path}")
    
    with ScheduleMigration(db_path) as migration:
        # Validate schema
        if not migration.validate_schema():
            logger.error("Schema validation failed. Please ensure DeviceSchedules table exists.")
            return 1
        
        # Show stats
        stats = migration.get_migration_stats()
        logger.info("=" * 60)
        logger.info("Migration Statistics:")
        logger.info(f"  Units with legacy schedules: {stats['units_with_schedules']}")
        logger.info(f"  Total legacy schedules to migrate: {stats['total_legacy_schedules']}")
        logger.info(f"  Existing schedules in new table: {stats['existing_new_schedules']}")
        logger.info(f"  Schedule breakdown by device type:")
        for device_type, count in stats['schedule_breakdown'].items():
            logger.info(f"    - {device_type}: {count}")
        logger.info("=" * 60)
        
        if args.stats:
            return 0
        
        if args.validate:
            validation = migration.validate_migration()
            logger.info("Validation Results:")
            logger.info(f"  Legacy schedules: {validation['legacy_schedule_count']}")
            logger.info(f"  Migrated schedules: {validation['migrated_schedule_count']}")
            if validation['missing_schedules']:
                logger.warning(f"  Missing schedules:")
                for missing in validation['missing_schedules']:
                    logger.warning(f"    - {missing}")
            logger.info(f"  Validation passed: {validation['validation_passed']}")
            return 0 if validation['validation_passed'] else 1
        
        if args.rollback:
            confirm = input("Are you sure you want to rollback the migration? [y/N]: ")
            if confirm.lower() == 'y':
                deleted = migration.rollback_migration()
                logger.info(f"Rollback complete. Deleted {deleted} records.")
            else:
                logger.info("Rollback cancelled.")
            return 0
        
        # Run migration
        if args.dry_run:
            logger.info("DRY RUN MODE - No changes will be made")
        
        results = migration.migrate_schedules(dry_run=args.dry_run)
        
        logger.info("=" * 60)
        logger.info("Migration Results:")
        logger.info(f"  Units processed: {results['units_processed']}")
        logger.info(f"  Schedules migrated: {results['schedules_migrated']}")
        logger.info(f"  Schedules skipped (already exist): {results['schedules_skipped']}")
        if results['errors']:
            logger.error(f"  Errors: {len(results['errors'])}")
            for error in results['errors']:
                logger.error(f"    - {error}")
        logger.info("=" * 60)
        
        if not args.dry_run and results['schedules_migrated'] > 0:
            # Validate after migration
            validation = migration.validate_migration()
            if validation['validation_passed']:
                logger.info("✓ Migration validation passed!")
            else:
                logger.warning("⚠ Migration validation found issues")
                for missing in validation['missing_schedules']:
                    logger.warning(f"  - {missing}")
        
        return 0 if not results['errors'] else 1


if __name__ == '__main__':
    exit(main())
