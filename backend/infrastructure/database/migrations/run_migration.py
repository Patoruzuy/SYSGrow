#!/usr/bin/env python3
"""
Database Migration Script
=========================

Adds multi-user support to GrowthUnits table.

Usage:
    python run_migration.py [path_to_database]
    
Example:
    python run_migration.py sysgrow.db
"""

import sqlite3
import sys
import shutil
from datetime import datetime
from pathlib import Path


def backup_database(db_path: str) -> str:
    """Create a backup of the database."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{db_path}.backup_{timestamp}"
    
    print(f"Creating backup: {backup_path}")
    shutil.copy2(db_path, backup_path)
    print(f"✅ Backup created successfully")
    
    return backup_path


def run_migration(db_path: str) -> bool:
    """Run the migration script."""
    migration_sql = Path(__file__).parent / "add_multi_user_support.sql"
    
    if not migration_sql.exists():
        print(f"❌ Migration script not found: {migration_sql}")
        return False
    
    print(f"Running migration from: {migration_sql}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Read and execute migration
        with open(migration_sql, 'r') as f:
            migration_script = f.read()
        
        conn.executescript(migration_script)
        conn.commit()
        
        # Verify migration
        cursor = conn.execute("PRAGMA table_info(GrowthUnits)")
        columns = [row[1] for row in cursor.fetchall()]
        
        required_columns = ['user_id', 'dimensions', 'custom_image', 'created_at', 'updated_at', 'camera_active']
        missing_columns = [col for col in required_columns if col not in columns]
        
        if missing_columns:
            print(f"⚠️  Warning: Missing columns: {missing_columns}")
            return False
        
        # Show results
        cursor = conn.execute("SELECT COUNT(*) as count FROM GrowthUnits")
        total_units = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) as count FROM GrowthUnits WHERE user_id IS NOT NULL")
        units_with_user = cursor.fetchone()[0]
        
        conn.close()
        
        print(f"\n✅ Migration completed successfully!")
        print(f"   - Total units: {total_units}")
        print(f"   - Units with user_id: {units_with_user}")
        print(f"   - New columns added: {', '.join(required_columns)}")
        
        return True
        
    except sqlite3.Error as e:
        print(f"❌ Migration failed: {e}")
        return False


def verify_migration(db_path: str):
    """Verify the migration was successful."""
    print("\n" + "="*60)
    print("VERIFICATION RESULTS")
    print("="*60)
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Check table structure
        print("\n📊 GrowthUnits Table Structure:")
        cursor = conn.execute("PRAGMA table_info(GrowthUnits)")
        for row in cursor.fetchall():
            print(f"   - {row[1]}: {row[2]}")
        
        # Check indexes
        print("\n🔍 Indexes:")
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='GrowthUnits'"
        )
        for row in cursor.fetchall():
            print(f"   - {row[0]}")
        
        # Sample data
        print("\n📝 Sample Unit Data:")
        cursor = conn.execute("SELECT * FROM GrowthUnits LIMIT 1")
        unit = cursor.fetchone()
        if unit:
            for key in unit.keys():
                print(f"   - {key}: {unit[key]}")
        else:
            print("   (No units in database)")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Verification failed: {e}")


def main():
    """Main migration entry point."""
    print("="*60)
    print("SYSGrow Database Migration")
    print("Adding Multi-User Support to GrowthUnits")
    print("="*60)
    
    # Get database path
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    else:
        db_path = "sysgrow.db"
    
    db_path = Path(db_path)
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        print(f"\nUsage: python {sys.argv[0]} [path_to_database]")
        sys.exit(1)
    
    print(f"\n📁 Database: {db_path}")
    print(f"   Size: {db_path.stat().st_size / 1024:.2f} KB")
    
    # Confirm migration
    response = input("\n⚠️  This will modify the database. Continue? [y/N]: ")
    if response.lower() not in ['y', 'yes']:
        print("Migration cancelled.")
        sys.exit(0)
    
    # Create backup
    backup_path = backup_database(str(db_path))
    
    # Run migration
    success = run_migration(str(db_path))
    
    if success:
        verify_migration(str(db_path))
        print(f"\n✅ Migration successful!")
        print(f"   Backup saved at: {backup_path}")
    else:
        print(f"\n❌ Migration failed!")
        print(f"   You can restore from backup: {backup_path}")
        sys.exit(1)


if __name__ == "__main__":
    main()
