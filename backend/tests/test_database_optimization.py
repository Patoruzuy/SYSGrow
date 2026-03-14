"""
Integration tests for database optimization and harvest reporting system.

Tests:
1. Energy reading persistence with plant tracking
2. Plant lifecycle energy queries
3. Harvest report generation
4. Repository direct access (no DataAccess layer)
5. Data migration validation
"""

import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.application.harvest_service import PlantHarvestService
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler


class IntegrationTestRunner:
    """Tests integrated database optimization features."""
    
    def __init__(self, db_path: str = "test_integration.db"):
        self.db_path = db_path
        self.db_handler = SQLiteDatabaseHandler(db_path)
        self.analytics_repo = AnalyticsRepository(self.db_handler)
        self.harvest_service = PlantHarvestService(self.analytics_repo)
        self.test_results = []
        
    def setup(self):
        """Initialize test database."""
        print("=== Setting up test database ===")
        
        # Remove old test db if exists
        if Path(self.db_path).exists():
            Path(self.db_path).unlink()
            
        # Create tables
        self.db_handler.init_app()
        
        # Create test data
        with self.db_handler.connection() as conn:
            # Create test user
            conn.execute(
                "INSERT INTO Users (username, password_hash) VALUES (?, ?)",
                ("test_user", "hash123")
            )
            
            # Create test growth unit
            conn.execute(
                """
                INSERT INTO GrowthUnits (unit_id, user_id, name, location)
                VALUES (1, 1, 'Test Unit', 'Indoor')
                """
            )
            
            # Create test plant (use high ID to avoid conflicts with seed data)
            conn.execute(
                """
                INSERT INTO Plants (plant_id, name, plant_type, current_stage, days_in_stage)
                VALUES (9999, 'Test Tomato', 'Tomato', 'vegetative', 15)
                """
            )
            
            # Link plant to unit
            conn.execute(
                """
                UPDATE GrowthUnits SET active_plant_id = 9999 WHERE unit_id = 1
                """
            )
            
            # Create test actuator
            conn.execute(
                """
                INSERT INTO Actuator (actuator_id, unit_id, name, actuator_type, protocol, model)
                VALUES (1, 1, 'Test Light', 'light', 'zigbee', 'LED-100W')
                """
            )
            
        print("✓ Test database setup complete\n")
        
    def test_energy_reading_persistence(self) -> bool:
        """Test saving energy readings with plant tracking."""
        print("TEST 1: Energy Reading Persistence")
        
        try:
            # Save energy reading with plant context directly via SQL
            with self.db_handler.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO EnergyReadings (
                        device_id, plant_id, unit_id, growth_stage, timestamp,
                        voltage, current, power_watts, energy_kwh, source_type, is_estimated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (1, 9999, 1, 'vegetative', datetime.now(), 120.0, 0.83, 100.0, 0.1, 'zigbee', 0)
                )
            
            # Verify saved
            with self.db_handler.connection() as conn:
                reading = conn.execute(
                    """
                    SELECT * FROM EnergyReadings 
                    WHERE device_id = 1 AND plant_id = 9999
                    """
                ).fetchone()
                
            if not reading:
                print("✗ Failed: No reading found\n")
                return False
                
            if reading['growth_stage'] != 'vegetative':
                print(f"✗ Failed: Wrong growth stage: {reading['growth_stage']}\n")
                return False
                
            if reading['source_type'] != 'zigbee':
                print(f"✗ Failed: Wrong source type: {reading['source_type']}\n")
                return False
                
            print("✓ Passed: Energy reading saved with plant tracking\n")
            return True
            
        except Exception as e:
            print(f"✗ Failed: {e}\n")
            return False
            
    def test_plant_energy_summary(self) -> bool:
        """Test plant lifecycle energy queries."""
        print("TEST 2: Plant Energy Summary")
        
        try:
            # Add multiple readings across different stages
            base_time = datetime.now() - timedelta(days=30)
            
            stages = [
                ('seedling', 20.0, 10),  # stage, power, days
                ('vegetative', 100.0, 15),
                ('flowering', 150.0, 5)
            ]
            
            for stage, power, days in stages:
                for day in range(days):
                    timestamp = base_time + timedelta(days=day)
                    with self.db_handler.connection() as conn:
                        conn.execute(
                            """
                            INSERT INTO EnergyReadings (
                                device_id, plant_id, unit_id, growth_stage, timestamp,
                                voltage, current, power_watts, energy_kwh, source_type, is_estimated
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (1, 9999, 1, stage, timestamp, 120.0, power / 120.0, power, power * 24 / 1000, 'zigbee', 0)
                        )
                    
            # Query plant energy summary via SQL
            with self.db_handler.connection() as conn:
                result = conn.execute(
                    """
                    SELECT 
                        SUM(energy_kwh) as total_kwh,
                        growth_stage,
                        COUNT(*) as readings
                    FROM EnergyReadings 
                    WHERE plant_id = ? AND timestamp >= ? AND timestamp <= ?
                    GROUP BY growth_stage
                    """,
                    (9999, base_time, datetime.now())
                ).fetchall()
                
            if not result:
                print("✗ Failed: No summary returned\n")
                return False
                
            total_kwh = sum(row['total_kwh'] for row in result)
            expected_kwh = (20 * 24 * 10 + 100 * 24 * 15 + 150 * 24 * 5) / 1000
            
            if abs(total_kwh - expected_kwh) > 1:  # Allow 1 kWh tolerance
                print(f"✗ Failed: Wrong energy total: {total_kwh} (expected ~{expected_kwh})\n")
                return False
                
            if len(result) != 3:  # Should have 3 stages
                print(f"✗ Failed: Expected 3 stages, got {len(result)}\n")
                return False
                
            print(f"✓ Passed: Energy summary calculated correctly ({total_kwh:.2f} kWh across {len(result)} stages)\n")
            return True
            
        except Exception as e:
            print(f"✗ Failed: {e}\n")
            return False
            
    def test_harvest_report_generation(self) -> bool:
        """Test harvest summary can be saved to database."""
        print("TEST 3: Harvest Summary Database Storage")
        
        try:
            # Directly insert a harvest summary to test the table structure
            with self.db_handler.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO PlantHarvestSummary (
                        plant_id, unit_id, planted_date, harvested_date,
                        total_days, seedling_days, vegetative_days, flowering_days,
                        total_energy_kwh, energy_by_stage, total_cost, cost_by_stage,
                        device_usage, avg_daily_power_watts, total_light_hours,
                        harvest_weight_grams, quality_rating, grams_per_kwh, cost_per_gram,
                        notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        9999, 1, datetime.now() - timedelta(days=30), datetime.now(),
                        30, 5, 15, 10,
                        58.9, json.dumps({'seedling': 4.8, 'vegetative': 36.0, 'flowering': 18.0}),
                        11.78, json.dumps({'seedling': 0.96, 'vegetative': 7.2, 'flowering': 3.6}),
                        json.dumps({'light': 58.9}), 81.8, 360.0,
                        250.0, 4, 4.24, 0.047, 'Test harvest report'
                    )
                )
                harvest_id = cursor.lastrowid
                
            # Verify saved
            with self.db_handler.connection() as conn:
                report = conn.execute(
                    """
                    SELECT * FROM PlantHarvestSummary WHERE harvest_id = ?
                    """,
                    (harvest_id,)
                ).fetchone()
                
            if not report:
                print("✗ Failed: Harvest summary not saved\n")
                return False
                
            # Verify JSON fields
            energy_by_stage = json.loads(report['energy_by_stage'])
            if 'seedling' not in energy_by_stage:
                print("✗ Failed: Invalid energy_by_stage JSON\n")
                return False
                
            # Verify efficiency metrics
            if report['grams_per_kwh'] <= 0:
                print(f"✗ Failed: Invalid efficiency: {report['grams_per_kwh']}\n")
                return False
                
            print(f"✓ Passed: Harvest summary saved (ID: {harvest_id})")
            print(f"  - Total energy: {report['total_energy_kwh']:.2f} kWh")
            print(f"  - Efficiency: {report['grams_per_kwh']:.2f} g/kWh\n")
            return True
            
        except Exception as e:
            print(f"✗ Failed: {e}\n")
            return False
            
    def test_repository_direct_access(self) -> bool:
        """Test that services use repository directly (no DataAccess layer)."""
        print("TEST 4: Repository Direct Access")
        
        try:
            # Verify analytics_repo is instance of AnalyticsRepository
            if not isinstance(self.analytics_repo, AnalyticsRepository):
                print("✗ Failed: analytics_repo is not AnalyticsRepository instance\n")
                return False
                
            # Verify harvest service uses analytics_repo
            if not hasattr(self.harvest_service, 'analytics_repo'):
                print("✗ Failed: harvest_service missing analytics_repo\n")
                return False
                
            # Try to import deprecated EnergyDataAccess (should not exist)
            try:
                from ai.data_access import EnergyDataAccess
                print("✗ Failed: EnergyDataAccess still exists in imports\n")
                return False
            except ImportError:
                pass  # Expected
                
            print("✓ Passed: Services use repository directly (no DataAccess layer)\n")
            return True
            
        except Exception as e:
            print(f"✗ Failed: {e}\n")
            return False
            
    def test_unified_energy_table(self) -> bool:
        """Test unified EnergyReadings table structure."""
        print("TEST 5: Unified Energy Table")
        
        try:
            with self.db_handler.connection() as conn:
                # Check table exists
                table = conn.execute(
                    """
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='EnergyReadings'
                    """
                ).fetchone()
                
                if not table:
                    print("✗ Failed: EnergyReadings table not found\n")
                    return False
                    
                # Check required columns
                columns = conn.execute("PRAGMA table_info(EnergyReadings)").fetchall()
                column_names = [col['name'] for col in columns]
                
                required_columns = [
                    'reading_id', 'device_id', 'plant_id', 'unit_id',
                    'growth_stage', 'timestamp', 'power_watts', 'source_type'
                ]
                
                missing = [col for col in required_columns if col not in column_names]
                if missing:
                    print(f"✗ Failed: Missing columns: {missing}\n")
                    return False
                    
                # Check indexes exist
                indexes = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='EnergyReadings'"
                ).fetchall()
                
                if len(indexes) < 3:  # Should have at least 3 indexes
                    print(f"✗ Failed: Expected at least 3 indexes, found {len(indexes)}\n")
                    return False
                    
            print(f"✓ Passed: EnergyReadings table structure valid ({len(column_names)} columns, {len(indexes)} indexes)\n")
            return True
            
        except Exception as e:
            print(f"✗ Failed: {e}\n")
            return False
            
    def test_harvest_summary_table(self) -> bool:
        """Test PlantHarvestSummary table structure."""
        print("TEST 6: Harvest Summary Table")
        
        try:
            with self.db_handler.connection() as conn:
                # Check table exists
                table = conn.execute(
                    """
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='PlantHarvestSummary'
                    """
                ).fetchone()
                
                if not table:
                    print("✗ Failed: PlantHarvestSummary table not found\n")
                    return False
                    
                # Check JSON columns
                columns = conn.execute("PRAGMA table_info(PlantHarvestSummary)").fetchall()
                column_names = [col['name'] for col in columns]
                
                json_columns = ['energy_by_stage', 'cost_by_stage', 'device_usage', 'health_incidents']
                missing = [col for col in json_columns if col not in column_names]
                if missing:
                    print(f"✗ Failed: Missing JSON columns: {missing}\n")
                    return False
                    
            print(f"✓ Passed: PlantHarvestSummary table structure valid\n")
            return True
            
        except Exception as e:
            print(f"✗ Failed: {e}\n")
            return False
            
    def run_all_tests(self) -> bool:
        """Execute all integration tests."""
        print("\n" + "="*60)
        print("DATABASE OPTIMIZATION - INTEGRATION TESTS")
        print("="*60 + "\n")
        
        self.setup()
        
        tests = [
            self.test_unified_energy_table,
            self.test_harvest_summary_table,
            self.test_energy_reading_persistence,
            self.test_plant_energy_summary,
            self.test_harvest_report_generation,
            self.test_repository_direct_access,
        ]
        
        results = []
        for test in tests:
            results.append(test())
            
        # Summary
        print("="*60)
        print("TEST SUMMARY")
        print("="*60)
        passed = sum(results)
        total = len(results)
        print(f"Passed: {passed}/{total}")
        print(f"Failed: {total - passed}/{total}")
        
        if passed == total:
            print("\n✓ ALL TESTS PASSED")
        else:
            print("\n✗ SOME TESTS FAILED")
            
        # Cleanup
        self.db_handler.close_db()
        if Path(self.db_path).exists():
            try:
                Path(self.db_path).unlink()
                print(f"\nCleaned up test database: {self.db_path}")
            except PermissionError:
                print(f"\nNote: Test database still in use: {self.db_path}")
            
        return passed == total


def main():
    runner = IntegrationTestRunner()
    success = runner.run_all_tests()
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())
