"""
Database Migration: Consolidate PlantHealth to PlantHealthLogs
===============================================================
Migrates data from the deprecated PlantHealth table to PlantHealthLogs
and removes the old table.

Run this script once to complete the database consolidation.
"""

import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def check_table_exists(cursor, table_name: str) -> bool:
    """Check if a table exists in the database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None

def count_records(cursor, table_name: str) -> int:
    """Count records in a table."""
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        return cursor.fetchone()[0]
    except sqlite3.Error:
        return 0

def migrate_plant_health_data(db_path: str, dry_run: bool = True):
    """
    Migrate data from PlantHealth to PlantHealthLogs.
    
    Args:
        db_path: Path to the SQLite database
        dry_run: If True, only show what would be done without making changes
    """
    print(f"\n{'='*70}")
    print(f"PlantHealth → PlantHealthLogs Migration")
    print(f"{'='*70}")
    print(f"Database: {db_path}")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE MIGRATION'}")
    print(f"{'='*70}\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if PlantHealth table exists
        if not check_table_exists(cursor, 'PlantHealth'):
            print("✓ PlantHealth table does not exist - nothing to migrate")
            return True
        
        # Check if PlantHealthLogs table exists
        if not check_table_exists(cursor, 'PlantHealthLogs'):
            print("✗ PlantHealthLogs table does not exist - cannot migrate!")
            print("  Run the application first to create the schema.")
            return False
        
        # Count records in both tables
        old_count = count_records(cursor, 'PlantHealth')
        new_count_before = count_records(cursor, 'PlantHealthLogs')
        
        print(f"📊 Current Status:")
        print(f"   PlantHealth (old):        {old_count} records")
        print(f"   PlantHealthLogs (new):    {new_count_before} records")
        print()
        
        if old_count == 0:
            print("✓ No data to migrate from PlantHealth")
            if not dry_run:
                print("\n📋 Removing empty PlantHealth table...")
                cursor.execute("DROP TABLE IF EXISTS PlantHealth")
                conn.commit()
                print("✓ PlantHealth table removed")
            else:
                print("   (Would remove PlantHealth table in live mode)")
            return True
        
        # Show sample data from old table
        print(f"📋 Sample data from PlantHealth:")
        cursor.execute("SELECT * FROM PlantHealth LIMIT 3")
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]
        
        for row in rows:
            print(f"   {dict(zip(columns, row))}")
        print()
        
        # Migrate data
        print(f"🔄 Migrating {old_count} records...")
        
        if not dry_run:
            cursor.execute("""
                INSERT INTO PlantHealthLogs (
                    plant_id,
                    observation_date,
                    health_status,
                    notes,
                    severity_level
                )
                SELECT 
                    plant_id,
                    timestamp,
                    CASE 
                        WHEN disease_detected IS NOT NULL AND disease_detected != '' 
                        THEN 'diseased'
                        ELSE 'healthy'
                    END as health_status,
                    'Migrated from PlantHealth: ' ||
                    'leaf_color=' || COALESCE(leaf_color, 'unknown') || ', ' ||
                    'growth_rate=' || COALESCE(CAST(growth_rate AS TEXT), 'unknown') || ', ' ||
                    COALESCE('disease=' || disease_detected, 'no disease') as notes,
                    CASE 
                        WHEN disease_detected IS NOT NULL AND disease_detected != ''
                        THEN 3  -- Moderate severity for detected diseases
                        ELSE 1  -- Healthy
                    END as severity_level
                FROM PlantHealth
            """)
            
            migrated = cursor.rowcount
            conn.commit()
            
            # Verify migration
            new_count_after = count_records(cursor, 'PlantHealthLogs')
            
            print(f"✓ Migrated {migrated} records")
            print(f"✓ PlantHealthLogs now has {new_count_after} records")
            
            # Drop old table
            print("\n🗑️  Removing PlantHealth table...")
            cursor.execute("DROP TABLE PlantHealth")
            conn.commit()
            print("✓ PlantHealth table removed")
            
        else:
            print("   → Would migrate records to PlantHealthLogs")
            print("   → Would drop PlantHealth table")
            print("\n💡 Run with --live flag to apply changes")
        
        return True
        
    except sqlite3.Error as e:
        print(f"\n✗ Database error: {e}")
        if not dry_run:
            conn.rollback()
        return False
    
    finally:
        conn.close()

def main():
    """Main migration script."""
    # Parse arguments
    dry_run = '--live' not in sys.argv
    db_path = 'database/sysgrow.db'
    
    # Check if custom db path provided
    for i, arg in enumerate(sys.argv[1:]):
        if arg == '--db' and i + 2 < len(sys.argv):
            db_path = sys.argv[i + 2]
    
    # Verify database exists
    if not Path(db_path).exists():
        print(f"✗ Database not found: {db_path}")
        print("  Make sure the path is correct")
        return 1
    
    # Run migration
    success = migrate_plant_health_data(db_path, dry_run=dry_run)
    
    if success:
        print(f"\n{'='*70}")
        print("✅ Migration completed successfully!")
        print(f"{'='*70}\n")
        
        if dry_run:
            print("This was a DRY RUN - no changes were made.")
            print("To apply changes, run: python migrate_health_tables.py --live")
        else:
            print("Database consolidation is complete.")
            print("The PlantHealth table has been removed.")
            print("All health data is now in PlantHealthLogs.")
        
        return 0
    else:
        print(f"\n{'='*70}")
        print("❌ Migration failed!")
        print(f"{'='*70}\n")
        return 1

if __name__ == '__main__':
    sys.exit(main())
