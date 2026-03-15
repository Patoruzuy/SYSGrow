"""Legacy harvest test skipped after v2 migration."""
import pytest

pytest.skip("Legacy harvest endpoints deprecated", allow_module_level=True)

def test_harvest_endpoint():
    print("\n" + "="*60)
    print("HARVEST ENDPOINT TEST")
    print("="*60 + "\n")
    
    # Initialize database
    db_handler = SQLiteDatabaseHandler("database/sysgrow.db")
    db_handler.create_tables()
    
    # Initialize repositories
    analytics_repo = AnalyticsRepository(db_handler)
    growth_repo = GrowthRepository(db_handler)
    
    # Initialize service
    harvest_service = PlantHarvestService(analytics_repo)
    
    print("✅ Service initialized successfully\n")
    
    # Test 1: Get all units
    print("📊 Test 1: List all growth units")
    units = growth_repo.list_units()
    print(f"   Found {len(units)} units")
    for unit in units[:3]:
        print(f"   - Unit {unit.get('unit_id')}: {unit.get('name')}")
    
    # Test 2: Get plants in first unit
    if units:
        unit_id = units[0].get('unit_id')
        print(f"\n📊 Test 2: List plants in Unit {unit_id}")
        plants = growth_repo.list_plants_for_unit(unit_id)
        print(f"   Found {len(plants)} plants")
        for plant in plants[:3]:
            print(f"   - Plant {plant.get('plant_id')}: {plant.get('name')} ({plant.get('current_stage')})")
        
        # Test 3: Try to generate a harvest report
        if plants:
            plant_id = plants[0].get('plant_id')
            print(f"\n📊 Test 3: Generate harvest report for Plant {plant_id}")
            try:
                report = harvest_service.generate_harvest_report(
                    plant_id=plant_id,
                    harvest_weight_grams=150.0,
                    quality_rating=4,
                    notes="Test harvest from command line"
                )
                print(f"   ✅ Report generated successfully!")
                print(f"   - Harvest ID: {report.get('harvest_id')}")
                print(f"   - Weight: {report.get('yield', {}).get('weight_grams')}g")
                print(f"   - Energy: {report.get('energy_consumption', {}).get('total_kwh')}kWh")
                print(f"   - Efficiency: {report.get('efficiency_metrics', {}).get('grams_per_kwh')}g/kWh")
                print(f"   - Rating: {report.get('efficiency_metrics', {}).get('energy_efficiency_rating')}")
            except Exception as e:
                print(f"   ❌ Error: {e}")
                import traceback
                traceback.print_exc()
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        test_harvest_endpoint()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
