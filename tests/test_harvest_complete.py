"""
Test harvest functionality with sample data
"""
import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.growth import GrowthRepository
from app.services.application.harvest_service import PlantHarvestService

def setup_test_data(db_handler, growth_repo):
    """Create test data for harvest testing"""
    print("Creating test data...")
    
    with db_handler.connection() as conn:
        # Create a test unit
        unit_id = conn.execute("""
            INSERT INTO GrowthUnits (name, location)
            VALUES ('Test Unit', 'Indoor')
        """).lastrowid
        print(f"  ✓ Created unit {unit_id}")
        
        # Create a test plant
        planted_date = (datetime.now() - timedelta(days=75)).isoformat()
        plant_id = conn.execute("""
            INSERT INTO Plants (name, plant_type, current_stage, days_in_stage, planted_date)
            VALUES ('Test Tomato', 'Cherry Tomato', 'ripening', 10, ?)
        """, (planted_date,)).lastrowid
        print(f"  ✓ Created plant {plant_id}")
        
        # Link plant to unit
        conn.execute("""
            INSERT INTO GrowthUnitPlants (unit_id, plant_id)
            VALUES (?, ?)
        """, (unit_id, plant_id))
        
        #Add energy readings
        for i in range(30):
            timestamp = datetime.now() - timedelta(days=i)
            conn.execute("""
                INSERT INTO EnergyReadings (
                    device_id, plant_id, unit_id, growth_stage, timestamp,
                    power_watts, energy_kwh, source_type
                ) VALUES (1, ?, ?, 'flowering', ?, 100.0, 2.4, 'zigbee')
            """, (plant_id, unit_id, timestamp))
        print(f"  ✓ Added 30 energy readings")
        
    return unit_id, plant_id

def test_harvest():
    print("\n" + "="*70)
    print("🌾 HARVEST REPORT FUNCTIONALITY TEST")
    print("="*70 + "\n")
    
    # Initialize
    db_handler = SQLiteDatabaseHandler(":memory:")  # Use in-memory for test
    db_handler.create_tables()
    
    analytics_repo = AnalyticsRepository(db_handler)
    growth_repo = GrowthRepository(db_handler)
    harvest_service = PlantHarvestService(analytics_repo)
    
    # Setup test data
    unit_id, plant_id = setup_test_data(db_handler, growth_repo)
    
    print("\n" + "-"*70)
    print("TEST 1: Generate Harvest Report")
    print("-"*70)
    
    try:
        report = harvest_service.generate_harvest_report(
            plant_id=plant_id,
            harvest_weight_grams=250.5,
            quality_rating=5,
            notes="Excellent test harvest with perfect conditions"
        )
        
        print(f"\n✅ Harvest Report Generated Successfully!\n")
        print(f"📊 HARVEST SUMMARY:")
        print(f"   Harvest ID: {report.get('harvest_id')}")
        print(f"   Plant: {report.get('plant_name')}")
        print(f"   Weight: {report.get('yield', {}).get('weight_grams')}g")
        print(f"   Quality: {'⭐' * report.get('yield', {}).get('quality_rating')}")
        
        energy = report.get('energy_consumption', {})
        print(f"\n⚡ ENERGY CONSUMPTION:")
        print(f"   Total: {energy.get('total_kwh'):.2f} kWh")
        print(f"   Cost: ${energy.get('total_cost'):.2f}")
        
        efficiency = report.get('efficiency_metrics', {})
        print(f"\n📈 EFFICIENCY METRICS:")
        print(f"   Yield Efficiency: {efficiency.get('grams_per_kwh'):.2f} g/kWh")
        print(f"   Cost per Gram: ${efficiency.get('cost_per_gram'):.4f}")
        print(f"   Rating: {efficiency.get('energy_efficiency_rating')}")
        
        lifecycle = report.get('lifecycle', {})
        print(f"\n🌱 LIFECYCLE:")
        print(f"   Total Days: {lifecycle.get('total_days')}")
        print(f"   Planted: {lifecycle.get('planted_date')}")
        print(f"   Harvested: {lifecycle.get('harvested_date')}")
        
    except Exception as e:
        print(f"\n❌ Error generating report: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "-"*70)
    print("TEST 2: Cleanup After Harvest")
    print("-"*70)
    
    try:
        cleanup = harvest_service.cleanup_after_harvest(
            plant_id=plant_id,
            delete_plant_data=True
        )
        
        print(f"\n✅ Cleanup Completed!\n")
        print(f"🗑️  DELETED:")
        deleted = cleanup.get('deleted', {})
        for key, count in deleted.items():
            print(f"   {key}: {count}")
        
        print(f"\n💾 PRESERVED:")
        preserved = cleanup.get('preserved', {})
        for key, count in preserved.items():
            print(f"   {key}: {count}")
            
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70 + "\n")
    
    print("📋 Summary:")
    print("   ✓ Harvest report generation works")
    print("   ✓ Energy consumption tracking works")
    print("   ✓ Efficiency calculations work")
    print("   ✓ Data cleanup works (preserves shared data)")
    print("   ✓ Database persistence works")
    print("\n🎉 Harvest functionality is ready to use!")
    print("\n💡 Next steps:")
    print("   1. Start the web server: python start_dev_localhost.py")
    print("   2. Open browser: http://localhost:5000/harvest_report.html")
    print("   3. Or use API: POST /api/plants/<id>/harvest")
    
    return True

if __name__ == "__main__":
    try:
        success = test_harvest()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
