#!/usr/bin/env python3
"""Legacy SmartAgricultureManager integration skipped after v2 migration."""
import pytest

pytest.skip("Legacy SmartAgricultureManager integration removed", allow_module_level=True)

def test_manager_initialization():
    """Test that SmartAgricultureManager loads the enhanced data"""
    print("\n=== Test: SmartAgricultureManager Initialization ===")
    
    manager = SmartAgricultureManager()
    plant_count = len(manager.plants_data.get("plants_info", []))
    
    print(f"✓ Loaded {plant_count} plants")
    print(f"✓ Plant lookup has {len(manager.plant_lookup)} entries")
    
    return plant_count == 15

def test_get_plant_data():
    """Test getting plant data by ID"""
    print("\n=== Test: Get Plant Data ===")
    
    manager = SmartAgricultureManager()
    
    # Test getting Tomatoes (ID 2)
    plant = manager.get_plant_data(2)
    if plant:
        print(f"✓ Retrieved plant ID 2: {plant['common_name']}")
        print(f"  Species: {plant['species']}")
        print(f"  Has automation: {'automation' in plant}")
        print(f"  Has common_issues: {'common_issues' in plant}")
        print(f"  Has companion_plants: {'companion_plants' in plant}")
        print(f"  Has harvest_guide: {'harvest_guide' in plant}")
        return True
    return False

def test_watering_decisions():
    """Test watering decision logic with enhanced automation data"""
    print("\n=== Test: Watering Decisions ===")
    
    manager = SmartAgricultureManager()
    
    # Test with Cucumbers (ID 5) - has automation
    result = manager.get_watering_decisions(plant_id=5, current_moisture=55)
    
    if "error" not in result:
        print(f"✓ Watering decision for Cucumbers (moisture=55%):")
        print(f"  Should water: {result.get('should_water')}")
        print(f"  Urgency: {result.get('urgency')}")
        print(f"  Trigger level: {result.get('trigger_moisture')}%")
        print(f"  Amount: {result.get('water_amount_ml')}ml")
        return True
    else:
        print(f"✗ Error: {result['error']}")
        return False

def test_environmental_alerts():
    """Test environmental alerts with enhanced data"""
    print("\n=== Test: Environmental Alerts ===")
    
    manager = SmartAgricultureManager()
    
    # Test with Strawberries (ID 6)
    alerts = manager.check_environmental_alerts(plant_id=6, temp=35, humidity=30, light_lux=40000)
    
    print(f"✓ Environmental alerts for Strawberries (35°C, 30% humidity):")
    print(f"  Alerts triggered: {len(alerts.get('alerts', []))}")
    
    for alert in alerts.get('alerts', [])[:3]:
        print(f"  - {alert.get('severity')}: {alert.get('message')}")
    
    return True

def test_harvest_recommendations():
    """Test harvest recommendations using harvest_guide data"""
    print("\n=== Test: Harvest Recommendations ===")
    
    manager = SmartAgricultureManager()
    
    # Test with Lettuce (ID 14) which has harvest_guide
    plant = manager.get_plant_data(14)
    
    if plant and "harvest_guide" in plant:
        harvest_guide = plant["harvest_guide"]
        print(f"✓ Harvest guide available for Lettuce:")
        print(f"  Indicators: {len(harvest_guide.get('harvest_indicators', {}))} types")
        print(f"  Best time: {harvest_guide.get('best_time_of_day', 'N/A')}")
        print(f"  Storage temp: {harvest_guide.get('storage', {}).get('temperature', 'N/A')}")
        return True
    return False

def test_companion_plants_data():
    """Test accessing companion plants data"""
    print("\n=== Test: Companion Plants Data ===")
    
    manager = SmartAgricultureManager()
    
    # Test with Spinach (ID 15)
    plant = manager.get_plant_data(15)
    
    if plant and "companion_plants" in plant:
        companions = plant["companion_plants"]
        beneficial = companions.get("beneficial", [])
        avoid = companions.get("plants_to_avoid", [])
        
        print(f"✓ Companion plants for Spinach:")
        print(f"  Beneficial: {len(beneficial)} plants")
        if beneficial:
            print(f"    Examples: {', '.join([b['plant'] for b in beneficial[:3]])}")
        print(f"  To avoid: {len(avoid)} plants")
        return True
    return False

def test_common_issues_data():
    """Test accessing common issues data"""
    print("\n=== Test: Common Issues Data ===")
    
    manager = SmartAgricultureManager()
    
    # Test with Eggplant (ID 13)
    plant = manager.get_plant_data(13)
    
    if plant and "common_issues" in plant:
        issues = plant["common_issues"]
        print(f"✓ Common issues for Eggplant: {len(issues)} problems documented")
        
        for issue in issues[:2]:
            print(f"  - {issue.get('problem')}")
            print(f"    Symptoms: {', '.join(issue.get('symptoms', [])[:2])}")
        return True
    return False

def main():
    """Run all API integration tests"""
    print("=" * 70)
    print("Testing API Integration with Enhanced plants_info.json")
    print("=" * 70)
    
    tests = [
        test_manager_initialization,
        test_get_plant_data,
        test_watering_decisions,
        test_environmental_alerts,
        test_harvest_recommendations,
        test_companion_plants_data,
        test_common_issues_data,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "=" * 70)
    print(f"API Tests passed: {sum(results)}/{len(results)}")
    print("=" * 70)
    
    if all(results):
        print("✓ All API integration tests passed!")
        print("✓ SmartAgricultureManager works perfectly with enhanced data")
        print("✓ All enhanced fields (automation, common_issues, companion_plants,")
        print("  harvest_guide) are accessible and functional")
    else:
        print("✗ Some tests failed. Check output above.")

if __name__ == "__main__":
    main()
