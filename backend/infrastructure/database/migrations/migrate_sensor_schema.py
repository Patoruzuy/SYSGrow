#!/usr/bin/env python3
"""
Sensor Schema Migration Runner

Executes the sensor schema migration from denormalized to normalized structure.
This script safely applies the migration with verification and rollback support.

Usage:
    python migrate_sensor_schema.py [--db-path PATH] [--verify-only] [--rollback]

Options:
    --db-path PATH    : Path to SQLite database file (default: smart_agriculture.db)
    --verify-only     : Only verify migration, don't apply changes
    --rollback        : Rollback to old schema (restore from _OLD tables)
"""

import sqlite3
import argparse
import sys
from pathlib import Path
from datetime import datetime


class SensorMigrationRunner:
    """Handles database migration execution and verification."""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")
        
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
    
    def __del__(self):
        if hasattr(self, 'conn'):
            self.conn.close()
    
    def verify_old_schema(self) -> bool:
        """Verify old schema exists before migration."""
        print("🔍 Verifying old schema...")
        
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Sensor'"
        )
        
        if not cursor.fetchone():
            print("❌ Old Sensor table not found!")
            return False
        
        # Check if already migrated
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Sensor_OLD'"
        )
        
        if cursor.fetchone():
            print("⚠️  Migration already applied (Sensor_OLD exists)")
            return False
        
        # Count records
        cursor = self.conn.execute("SELECT COUNT(*) FROM Sensor")
        sensor_count = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM SensorReading")
        reading_count = cursor.fetchone()[0]
        
        print(f"✅ Found {sensor_count} sensors, {reading_count} readings")
        return True
    
    def create_backup(self) -> Path:
        """Create database backup before migration."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.db_path.parent / f"{self.db_path.stem}_backup_{timestamp}.db"
        
        print(f"💾 Creating backup: {backup_path}")
        
        # SQLite backup
        backup_conn = sqlite3.connect(str(backup_path))
        self.conn.backup(backup_conn)
        backup_conn.close()
        
        print(f"✅ Backup created: {backup_path}")
        return backup_path
    
    def apply_migration(self, migration_file: Path) -> bool:
        """Apply migration SQL script."""
        print(f"🚀 Applying migration from: {migration_file}")
        
        if not migration_file.exists():
            print(f"❌ Migration file not found: {migration_file}")
            return False
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            migration_sql = f.read()
        
        try:
            # Execute migration script
            self.conn.executescript(migration_sql)
            self.conn.commit()
            print("✅ Migration applied successfully")
            return True
            
        except sqlite3.Error as e:
            print(f"❌ Migration failed: {e}")
            self.conn.rollback()
            return False
    
    def verify_new_schema(self) -> bool:
        """Verify new schema was created correctly."""
        print("🔍 Verifying new schema...")
        
        expected_tables = [
            'Sensor', 'SensorConfig', 'SensorCalibration',
            'SensorHealthHistory', 'SensorAnomaly', 'SensorReading'
        ]
        
        for table in expected_tables:
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            if not cursor.fetchone():
                print(f"❌ Missing table: {table}")
                return False
        
        print(f"✅ All {len(expected_tables)} tables created")
        
        # Verify data migration
        cursor = self.conn.execute("SELECT COUNT(*) FROM Sensor_OLD")
        old_count = cursor.fetchone()[0]
        
        cursor = self.conn.execute("SELECT COUNT(*) FROM Sensor")
        new_count = cursor.fetchone()[0]
        
        print(f"📊 Data migration: {old_count} → {new_count} sensors")
        
        if new_count != old_count:
            print(f"⚠️  Row count mismatch! Expected {old_count}, got {new_count}")
            return False
        
        # Verify indexes
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = cursor.fetchall()
        print(f"✅ Created {len(indexes)} indexes")
        
        return True
    
    def rollback_migration(self) -> bool:
        """Rollback to old schema by restoring from _OLD tables."""
        print("🔄 Rolling back migration...")
        
        # Check if _OLD tables exist
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='Sensor_OLD'"
        )
        
        if not cursor.fetchone():
            print("❌ Cannot rollback: Sensor_OLD table not found")
            return False
        
        try:
            # Drop new tables
            self.conn.execute("DROP TABLE IF EXISTS SensorAnomaly")
            self.conn.execute("DROP TABLE IF EXISTS SensorHealthHistory")
            self.conn.execute("DROP TABLE IF EXISTS SensorCalibration")
            self.conn.execute("DROP TABLE IF EXISTS SensorConfig")
            self.conn.execute("DROP TABLE IF EXISTS SensorReading")
            self.conn.execute("DROP TABLE IF EXISTS Sensor")
            
            # Restore old tables
            self.conn.execute("ALTER TABLE Sensor_OLD RENAME TO Sensor")
            self.conn.execute("ALTER TABLE SensorReading_OLD RENAME TO SensorReading")
            
            self.conn.commit()
            print("✅ Rollback completed successfully")
            return True
            
        except sqlite3.Error as e:
            print(f"❌ Rollback failed: {e}")
            self.conn.rollback()
            return False
    
    def display_sample_data(self):
        """Display sample migrated data."""
        print("\n📋 Sample migrated data:")
        
        cursor = self.conn.execute("""
            SELECT 
                s.id,
                s.name,
                s.sensor_type,
                s.protocol,
                s.model,
                sc.config_data
            FROM Sensor s
            LEFT JOIN SensorConfig sc ON s.id = sc.sensor_id
            LIMIT 5
        """)
        
        for row in cursor:
            print(f"\n  Sensor ID: {row['id']}")
            print(f"  Name: {row['name']}")
            print(f"  Type: {row['sensor_type']}")
            print(f"  Protocol: {row['protocol']}")
            print(f"  Model: {row['model']}")
            print(f"  Config: {row['config_data']}")


def main():
    parser = argparse.ArgumentParser(description='Run sensor schema migration')
    parser.add_argument(
        '--db-path',
        default='smart_agriculture.db',
        help='Path to SQLite database file'
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Only verify migration, don\'t apply'
    )
    parser.add_argument(
        '--rollback',
        action='store_true',
        help='Rollback to old schema'
    )
    
    args = parser.parse_args()
    
    # Get migration file path
    script_dir = Path(__file__).parent
    migration_file = script_dir / 'migrate_to_new_sensor_schema.sql'
    
    try:
        runner = SensorMigrationRunner(args.db_path)
        
        # Rollback mode
        if args.rollback:
            success = runner.rollback_migration()
            sys.exit(0 if success else 1)
        
        # Verify old schema
        if not runner.verify_old_schema():
            print("❌ Pre-migration verification failed")
            sys.exit(1)
        
        # Verify-only mode
        if args.verify_only:
            print("✅ Pre-migration verification passed")
            sys.exit(0)
        
        # Create backup
        backup_path = runner.create_backup()
        
        # Apply migration
        if not runner.apply_migration(migration_file):
            print(f"\n❌ Migration failed! Restore from backup: {backup_path}")
            sys.exit(1)
        
        # Verify new schema
        if not runner.verify_new_schema():
            print(f"\n⚠️  Post-migration verification failed!")
            print(f"   Backup available at: {backup_path}")
            sys.exit(1)
        
        # Display sample data
        runner.display_sample_data()
        
        print("\n✅ Migration completed successfully!")
        print(f"   Backup saved at: {backup_path}")
        print("   Old tables preserved as: Sensor_OLD, SensorReading_OLD")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
