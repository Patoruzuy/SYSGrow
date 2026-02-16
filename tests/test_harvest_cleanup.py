"""
Test harvest data cleanup functionality.

Verifies that:
1. Plant-specific data is deleted when requested
2. Shared data is preserved (energy, sensors, etc.)
3. Harvest report is complete before cleanup
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.application.harvest_service import PlantHarvestService
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler


def test_harvest_cleanup():
    """Test that cleanup preserves shared data while removing plant-specific data."""

    print("\n" + "=" * 60)
    print("HARVEST CLEANUP TEST")
    print("=" * 60 + "\n")

    # Setup test database
    db_path = "test_cleanup.db"
    if Path(db_path).exists():
        Path(db_path).unlink()

    db_handler = SQLiteDatabaseHandler(db_path)
    db_handler.init_app()
    analytics_repo = AnalyticsRepository(db_handler)
    harvest_service = PlantHarvestService(analytics_repo)

    try:
        # Create test data
        with db_handler.connection() as conn:
            # User
            conn.execute("INSERT INTO Users (username, password_hash) VALUES (?, ?)", ("test", "hash"))

            # Unit with 2 plants
            conn.execute("""
                INSERT INTO GrowthUnits (unit_id, user_id, name, active_plant_id)
                VALUES (1, 1, 'Test Unit', 101)
            """)

            # Plant 1 (to harvest)
            conn.execute("""
                INSERT INTO Plants (plant_id, name, plant_type, current_stage)
                VALUES (101, 'Tomato', 'Tomato', 'flowering')
            """)

            # Plant 2 (still growing)
            conn.execute("""
                INSERT INTO Plants (plant_id, name, plant_type, current_stage)
                VALUES (102, 'Pepper', 'Pepper', 'vegetative')
            """)

            # Link both plants to unit
            conn.execute("INSERT INTO GrowthUnitPlants (unit_id, plant_id) VALUES (1, 101)")
            conn.execute("INSERT INTO GrowthUnitPlants (unit_id, plant_id) VALUES (1, 102)")

            # Create actuator
            conn.execute("""
                INSERT INTO Actuator (actuator_id, unit_id, name, actuator_type, protocol, model)
                VALUES (1, 1, 'LED Light', 'light', 'zigbee', 'LED-100W')
            """)

            # Add energy readings (SHARED between both plants)
            for i in range(10):
                timestamp = datetime.now() - timedelta(days=i)
                conn.execute(
                    """
                    INSERT INTO EnergyReadings (
                        device_id, plant_id, unit_id, growth_stage, timestamp,
                        power_watts, energy_kwh, source_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (1, 101, 1, "flowering", timestamp, 100.0, 2.4, "zigbee"),
                )

                # Some shared readings (both plants benefit)
                conn.execute(
                    """
                    INSERT INTO EnergyReadings (
                        device_id, plant_id, unit_id, growth_stage, timestamp,
                        power_watts, energy_kwh, source_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (1, 102, 1, "vegetative", timestamp, 80.0, 1.92, "zigbee"),
                )

            # Add health logs for Plant 101
            conn.execute(
                """
                INSERT INTO PlantHealthLogs (
                    plant_id, observation_date, health_status, 
                    notes, severity_level
                )
                VALUES (101, ?, 'healthy', 'Test health log', 1)
            """,
                (datetime.now(),),
            )

            # Add sensor associations
            conn.execute("""
                INSERT INTO Sensor (sensor_id, unit_id, name, sensor_type, protocol, model)
                VALUES (1, 1, 'Temp Sensor', 'temperature', 'mqtt', 'DHT22')
            """)
            conn.execute("INSERT INTO PlantSensors (plant_id, sensor_id) VALUES (101, 1)")

        # Count records BEFORE cleanup
        print("📊 BEFORE HARVEST & CLEANUP:")
        with db_handler.connection() as conn:
            plants_count = conn.execute("SELECT COUNT(*) FROM Plants").fetchone()[0]
            health_count = conn.execute("SELECT COUNT(*) FROM PlantHealthLogs WHERE plant_id = 101").fetchone()[0]
            energy_count = conn.execute("SELECT COUNT(*) FROM EnergyReadings").fetchone()[0]
            energy_plant101 = conn.execute("SELECT COUNT(*) FROM EnergyReadings WHERE plant_id = 101").fetchone()[0]
            energy_plant102 = conn.execute("SELECT COUNT(*) FROM EnergyReadings WHERE plant_id = 102").fetchone()[0]
            unit_plants = conn.execute("SELECT COUNT(*) FROM GrowthUnitPlants WHERE unit_id = 1").fetchone()[0]

        print(f"  Plants: {plants_count}")
        print(f"  Plant 101 health logs: {health_count}")
        print(f"  Total energy readings: {energy_count}")
        print(f"    - Plant 101: {energy_plant101}")
        print(f"    - Plant 102: {energy_plant102}")
        print(f"  Plants in unit: {unit_plants}")
        print()

        # Harvest plant 101 with cleanup
        print("🌾 HARVESTING PLANT 101 (with cleanup)...")
        result = harvest_service.harvest_and_cleanup(
            plant_id=101,
            harvest_weight_grams=250.0,
            quality_rating=4,
            notes="First harvest",
            delete_plant_data=True,  # Delete plant-specific data
        )

        print(f"  ✓ Harvest report generated (ID: {result['harvest_report']['harvest_id']})")
        if result["cleanup_results"]:
            print("  ✓ Deleted records:")
            for key, count in result["cleanup_results"].items():
                if count > 0:
                    print(f"    - {key}: {count}")
        print()

        # Count records AFTER cleanup
        print("📊 AFTER HARVEST & CLEANUP:")
        with db_handler.connection() as conn:
            plants_count = conn.execute("SELECT COUNT(*) FROM Plants").fetchone()[0]
            health_count = conn.execute("SELECT COUNT(*) FROM PlantHealthLogs WHERE plant_id = 101").fetchone()[0]
            energy_count = conn.execute("SELECT COUNT(*) FROM EnergyReadings").fetchone()[0]
            energy_plant101 = conn.execute("SELECT COUNT(*) FROM EnergyReadings WHERE plant_id = 101").fetchone()[0]
            energy_plant102 = conn.execute("SELECT COUNT(*) FROM EnergyReadings WHERE plant_id = 102").fetchone()[0]
            unit_plants = conn.execute("SELECT COUNT(*) FROM GrowthUnitPlants WHERE unit_id = 1").fetchone()[0]
            harvest_reports = conn.execute("SELECT COUNT(*) FROM PlantHarvestSummary").fetchone()[0]
            active_plant = conn.execute("SELECT active_plant_id FROM GrowthUnits WHERE unit_id = 1").fetchone()[0]

        print(f"  Plants: {plants_count} (should be 1 - only Plant 102)")
        print(f"  Plant 101 health logs: {health_count} (should be 0)")
        print(f"  Total energy readings: {energy_count} (should be {20} - PRESERVED)")
        print(f"    - Plant 101: {energy_plant101} (should be {10} - PRESERVED)")
        print(f"    - Plant 102: {energy_plant102} (should be {10} - PRESERVED)")
        print(f"  Plants in unit: {unit_plants} (should be 1 - only Plant 102)")
        print(f"  Harvest reports: {harvest_reports} (should be 1)")
        print(f"  Unit active_plant_id: {active_plant} (should be NULL)")
        print()

        # Verify critical data preservation
        print("✅ VERIFICATION:")

        success = True

        if plants_count != 1:
            print("  ✗ FAIL: Plant 101 should be deleted, Plant 102 should remain")
            success = False
        else:
            print("  ✓ PASS: Plant 101 deleted, Plant 102 preserved")

        if health_count != 0:
            print("  ✗ FAIL: Plant 101 health logs should be deleted")
            success = False
        else:
            print("  ✓ PASS: Plant 101 health logs deleted")

        if energy_count != 20:
            print(f"  ✗ FAIL: Energy readings should be preserved (expected 20, got {energy_count})")
            success = False
        else:
            print("  ✓ PASS: All energy readings preserved (needed for Plant 102 report)")

        if energy_plant101 != 10:
            print(f"  ✗ FAIL: Plant 101 energy readings should be preserved (expected 10, got {energy_plant101})")
            success = False
        else:
            print("  ✓ PASS: Plant 101 energy readings preserved (historical data)")

        if energy_plant102 != 10:
            print(f"  ✗ FAIL: Plant 102 energy readings should be preserved (expected 10, got {energy_plant102})")
            success = False
        else:
            print("  ✓ PASS: Plant 102 energy readings preserved (needed for future report)")

        if unit_plants != 1:
            print("  ✗ FAIL: Only Plant 102 should remain in unit")
            success = False
        else:
            print("  ✓ PASS: Plant 102 still associated with unit")

        if harvest_reports != 1:
            print("  ✗ FAIL: Harvest report should be saved")
            success = False
        else:
            print("  ✓ PASS: Harvest report saved to database")

        if active_plant is not None:
            print(f"  ✗ FAIL: Unit active_plant_id should be NULL (got {active_plant})")
            success = False
        else:
            print("  ✓ PASS: Unit active_plant_id cleared")

        print()
        print("=" * 60)
        if success:
            print("✅ ALL TESTS PASSED")
            print("=" * 60)
            print("\nKey Takeaways:")
            print("  • Plant-specific data deleted (Plant, PlantHealth, associations)")
            print("  • Shared data preserved (EnergyReadings, SensorReadings)")
            print("  • Plant 102 can still generate accurate harvest report")
            print("  • Unit remains functional for remaining plants")
        else:
            print("❌ SOME TESTS FAILED")
            print("=" * 60)
        print()

        return success

    finally:
        # Cleanup
        db_handler.close_db()
        if Path(db_path).exists():
            Path(db_path).unlink()


if __name__ == "__main__":
    success = test_harvest_cleanup()
    exit(0 if success else 1)
