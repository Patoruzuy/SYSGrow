"""
Migration script to consolidate energy data from legacy tables into unified EnergyReadings table.

This script:
1. Migrates data from ActuatorPowerReading to EnergyReadings
2. Migrates data from EnergyConsumption (ZigBee monitors) to EnergyReadings
3. Preserves all historical data for harvest reports
4. Maps devices to plants where possible based on timestamps and unit assignments
5. Validates data integrity after migration

Usage:
    python -m migration.migrate_energy_data --dry-run  # Preview changes
    python -m migration.migrate_energy_data            # Execute migration
"""

import argparse
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EnergyDataMigration:
    """Migrates legacy energy tables to unified EnergyReadings table."""
    
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
        
        required_tables = [
            'EnergyReadings',
            'ActuatorPowerReading',
            'EnergyConsumption',
            'Actuator',
            'GrowthUnits',
            'Plants'
        ]
        
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
        
    def get_migration_stats(self) -> dict:
        """Get current record counts from all tables."""
        cursor = self.conn.cursor()
        
        stats = {
            'actuator_power_readings': cursor.execute(
                "SELECT COUNT(*) FROM ActuatorPowerReading"
            ).fetchone()[0],
            'energy_consumption': cursor.execute(
                "SELECT COUNT(*) FROM EnergyConsumption"
            ).fetchone()[0],
            'existing_energy_readings': cursor.execute(
                "SELECT COUNT(*) FROM EnergyReadings"
            ).fetchone()[0],
        }
        
        return stats
        
    def migrate_actuator_power_readings(self, dry_run: bool = False) -> int:
        """Migrate ActuatorPowerReading to EnergyReadings."""
        cursor = self.conn.cursor()
        
        # Get all actuator power readings with device and unit info
        query = """
        SELECT 
            apr.reading_id,
            apr.actuator_id as device_id,
            a.unit_id,
            apr.timestamp,
            apr.voltage,
            apr.current,
            apr.power_watts,
            apr.energy_kwh,
            apr.power_factor,
            apr.frequency,
            apr.temperature,
            apr.is_estimated,
            a.protocol as source_type,
            gu.active_plant_id as plant_id
        FROM ActuatorPowerReading apr
        INNER JOIN Actuator a ON apr.actuator_id = a.actuator_id
        LEFT JOIN GrowthUnits gu ON a.unit_id = gu.unit_id
        WHERE NOT EXISTS (
            SELECT 1 FROM EnergyReadings er 
            WHERE er.device_id = apr.actuator_id 
            AND er.timestamp = apr.timestamp
            AND er.source_type = 'actuator'
        )
        ORDER BY apr.timestamp
        """
        
        readings = cursor.execute(query).fetchall()
        
        if not readings:
            logger.info("No ActuatorPowerReading records to migrate")
            return 0
            
        if dry_run:
            logger.info(f"[DRY RUN] Would migrate {len(readings)} actuator power readings")
            return len(readings)
            
        # Insert into EnergyReadings
        insert_query = """
        INSERT INTO EnergyReadings (
            device_id, plant_id, unit_id, growth_stage, timestamp,
            voltage, current, power_watts, energy_kwh, power_factor,
            frequency, temperature, source_type, is_estimated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'actuator', ?)
        """
        
        migrated = 0
        for reading in readings:
            try:
                # Try to determine growth stage based on plant info if available
                growth_stage = None
                if reading['plant_id']:
                    plant = cursor.execute(
                        "SELECT current_stage FROM Plants WHERE plant_id = ?",
                        (reading['plant_id'],)
                    ).fetchone()
                    if plant:
                        growth_stage = plant['current_stage']
                
                cursor.execute(insert_query, (
                    reading['device_id'],
                    reading['plant_id'],
                    reading['unit_id'],
                    growth_stage,
                    reading['timestamp'],
                    reading['voltage'],
                    reading['current'],
                    reading['power_watts'],
                    reading['energy_kwh'],
                    reading['power_factor'],
                    reading['frequency'],
                    reading['temperature'],
                    reading['is_estimated']
                ))
                migrated += 1
            except sqlite3.Error as e:
                logger.error(f"Error migrating actuator reading {reading['reading_id']}: {e}")
                
        self.conn.commit()
        logger.info(f"✓ Migrated {migrated} actuator power readings")
        return migrated
        
    def migrate_zigbee_energy_consumption(self, dry_run: bool = False) -> int:
        """Migrate EnergyConsumption (ZigBee monitors) to EnergyReadings."""
        cursor = self.conn.cursor()
        
        # Get all energy consumption readings with monitor and unit info
        query = """
        SELECT 
            ec.consumption_id,
            zem.monitor_id as device_id,
            zem.unit_id,
            ec.timestamp,
            ec.voltage,
            ec.current,
            ec.power_watts,
            ec.energy_kwh,
            ec.power_factor,
            ec.frequency,
            ec.temperature,
            gu.active_plant_id as plant_id
        FROM EnergyConsumption ec
        INNER JOIN ZigBeeEnergyMonitors zem ON ec.monitor_id = zem.monitor_id
        LEFT JOIN GrowthUnits gu ON zem.unit_id = gu.unit_id
        WHERE NOT EXISTS (
            SELECT 1 FROM EnergyReadings er 
            WHERE er.device_id = ec.monitor_id 
            AND er.timestamp = ec.timestamp
            AND er.source_type = 'zigbee'
        )
        ORDER BY ec.timestamp
        """
        
        readings = cursor.execute(query).fetchall()
        
        if not readings:
            logger.info("No EnergyConsumption records to migrate")
            return 0
            
        if dry_run:
            logger.info(f"[DRY RUN] Would migrate {len(readings)} ZigBee energy readings")
            return len(readings)
            
        # Insert into EnergyReadings
        insert_query = """
        INSERT INTO EnergyReadings (
            device_id, plant_id, unit_id, growth_stage, timestamp,
            voltage, current, power_watts, energy_kwh, power_factor,
            frequency, temperature, source_type, is_estimated
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'zigbee', 0)
        """
        
        migrated = 0
        for reading in readings:
            try:
                # Try to determine growth stage based on plant info if available
                growth_stage = None
                if reading['plant_id']:
                    plant = cursor.execute(
                        "SELECT current_stage FROM Plants WHERE plant_id = ?",
                        (reading['plant_id'],)
                    ).fetchone()
                    if plant:
                        growth_stage = plant['current_stage']
                
                cursor.execute(insert_query, (
                    reading['device_id'],
                    reading['plant_id'],
                    reading['unit_id'],
                    growth_stage,
                    reading['timestamp'],
                    reading['voltage'],
                    reading['current'],
                    reading['power_watts'],
                    reading['energy_kwh'],
                    reading['power_factor'],
                    reading['frequency'],
                    reading['temperature']
                ))
                migrated += 1
            except sqlite3.Error as e:
                logger.error(f"Error migrating consumption reading {reading['consumption_id']}: {e}")
                
        self.conn.commit()
        logger.info(f"✓ Migrated {migrated} ZigBee energy readings")
        return migrated
        
    def validate_migration(self) -> bool:
        """Verify migration completed successfully."""
        cursor = self.conn.cursor()
        
        # Check record counts
        original_actuator = cursor.execute(
            "SELECT COUNT(*) FROM ActuatorPowerReading"
        ).fetchone()[0]
        
        original_consumption = cursor.execute(
            "SELECT COUNT(*) FROM EnergyConsumption"
        ).fetchone()[0]
        
        migrated_actuator = cursor.execute(
            "SELECT COUNT(*) FROM EnergyReadings WHERE source_type = 'actuator'"
        ).fetchone()[0]
        
        migrated_zigbee = cursor.execute(
            "SELECT COUNT(*) FROM EnergyReadings WHERE source_type = 'zigbee'"
        ).fetchone()[0]
        
        logger.info("\n=== Migration Validation ===")
        logger.info(f"ActuatorPowerReading: {original_actuator} original → {migrated_actuator} migrated")
        logger.info(f"EnergyConsumption: {original_consumption} original → {migrated_zigbee} migrated")
        
        # Check for orphaned records (readings without valid device references)
        orphaned = cursor.execute("""
            SELECT COUNT(*) FROM EnergyReadings 
            WHERE unit_id NOT IN (SELECT unit_id FROM GrowthUnits)
        """).fetchone()[0]
        
        if orphaned > 0:
            logger.warning(f"⚠ Found {orphaned} readings with invalid unit_id references")
        else:
            logger.info("✓ No orphaned records found")
            
        # Verify plant associations
        with_plants = cursor.execute(
            "SELECT COUNT(*) FROM EnergyReadings WHERE plant_id IS NOT NULL"
        ).fetchone()[0]
        
        logger.info(f"✓ {with_plants} readings associated with plants")
        
        # Check for duplicate timestamps per device
        duplicates = cursor.execute("""
            SELECT device_id, timestamp, COUNT(*) as count
            FROM EnergyReadings
            GROUP BY device_id, timestamp, source_type
            HAVING count > 1
        """).fetchall()
        
        if duplicates:
            logger.warning(f"⚠ Found {len(duplicates)} duplicate timestamp entries")
            return False
        else:
            logger.info("✓ No duplicate entries found")
            
        return True
        
    def run(self, dry_run: bool = False) -> bool:
        """Execute full migration."""
        logger.info("=== Energy Data Migration ===")
        logger.info(f"Database: {self.db_path}")
        logger.info(f"Mode: {'DRY RUN' if dry_run else 'EXECUTE'}")
        logger.info("")
        
        # Validate schema
        if not self.validate_schema():
            return False
            
        # Get initial stats
        stats = self.get_migration_stats()
        logger.info("\n=== Pre-Migration Stats ===")
        logger.info(f"ActuatorPowerReading: {stats['actuator_power_readings']} records")
        logger.info(f"EnergyConsumption: {stats['energy_consumption']} records")
        logger.info(f"EnergyReadings (existing): {stats['existing_energy_readings']} records")
        logger.info("")
        
        # Run migrations
        logger.info("=== Starting Migration ===")
        actuator_count = self.migrate_actuator_power_readings(dry_run)
        zigbee_count = self.migrate_zigbee_energy_consumption(dry_run)
        
        total_migrated = actuator_count + zigbee_count
        logger.info(f"\n=== Migration Summary ===")
        logger.info(f"Total records migrated: {total_migrated}")
        
        if not dry_run and total_migrated > 0:
            # Validate migration
            logger.info("")
            if self.validate_migration():
                logger.info("\n✓ Migration completed successfully!")
                return True
            else:
                logger.error("\n✗ Migration validation failed")
                return False
        elif dry_run:
            logger.info("\n[DRY RUN] No changes made to database")
            return True
        else:
            logger.info("\n✓ No records needed migration")
            return True


def main():
    parser = argparse.ArgumentParser(description='Migrate energy data to unified EnergyReadings table')
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without modifying database')
    parser.add_argument('--db-path', type=str, default='smart_agriculture.db', help='Path to SQLite database')
    args = parser.parse_args()
    
    # Find database path
    db_path = Path(args.db_path)
    if not db_path.exists():
        # Try relative to script location
        script_dir = Path(__file__).parent.parent
        db_path = script_dir / args.db_path
        
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return 1
        
    try:
        with EnergyDataMigration(str(db_path)) as migration:
            success = migration.run(dry_run=args.dry_run)
            return 0 if success else 1
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    exit(main())
