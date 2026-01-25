#!/usr/bin/env python3
"""Legacy device schedule tests skipped after v2 migration."""
import pytest

pytest.skip("Legacy device schedule v1 tests removed after v2 migration", allow_module_level=True)

def test_save_device_schedule():
    """Test saving individual device schedules"""
    print("\n=== Test: Save Device Schedule ===")
    
    db = SQLiteDatabaseHandler("test_schedules.db")
    db.create_tables()
    
    # Create a test growth unit directly using database
    conn = db.get_db()
    cursor = conn.execute(
        """
        INSERT INTO GrowthUnits (user_id, name, location, device_schedules)
        VALUES (1, 'Test Unit', 'Indoor', NULL)
        """
    )
    unit_id = cursor.lastrowid
    conn.commit()
    
    print(f"✓ Created test unit: {unit_id}")
    
    # Save light schedule
    success = db.save_device_schedule(
        unit_id=unit_id,
        device_type="light",
        start_time="06:00",
        end_time="22:00",
        enabled=True
    )
    print(f"✓ Save light schedule: {'Success' if success else 'Failed'}")
    
    # Save fan schedule
    success = db.save_device_schedule(
        unit_id=unit_id,
        device_type="fan",
        start_time="08:00",
        end_time="20:00",
        enabled=True
    )
    print(f"✓ Save fan schedule: {'Success' if success else 'Failed'}")
    
    # Save pump schedule
    success = db.save_device_schedule(
        unit_id=unit_id,
        device_type="pump",
        start_time="09:00",
        end_time="18:00",
        enabled=False
    )
    print(f"✓ Save pump schedule (disabled): {'Success' if success else 'Failed'}")
    
    return db, unit_id

def test_get_device_schedule(db, unit_id):
    """Test retrieving specific device schedule"""
    print("\n=== Test: Get Device Schedule ===")
    
    # Get light schedule
    light_schedule = db.get_device_schedule(unit_id, "light")
    if light_schedule:
        print(f"✓ Light schedule: {light_schedule['start_time']} - {light_schedule['end_time']}, Enabled: {light_schedule['enabled']}")
    else:
        print("✗ Light schedule not found")
    
    # Get fan schedule
    fan_schedule = db.get_device_schedule(unit_id, "fan")
    if fan_schedule:
        print(f"✓ Fan schedule: {fan_schedule['start_time']} - {fan_schedule['end_time']}, Enabled: {fan_schedule['enabled']}")
    else:
        print("✗ Fan schedule not found")
    
    # Get non-existent schedule
    heater_schedule = db.get_device_schedule(unit_id, "heater")
    if heater_schedule is None:
        print("✓ Non-existent schedule returns None correctly")
    
    return light_schedule is not None and fan_schedule is not None

def test_get_all_device_schedules(db, unit_id):
    """Test retrieving all device schedules"""
    print("\n=== Test: Get All Device Schedules ===")
    
    all_schedules = db.get_all_device_schedules(unit_id)
    
    print(f"✓ Found {len(all_schedules)} device schedules:")
    for device_type, schedule in all_schedules.items():
        print(f"  - {device_type}: {schedule['start_time']} - {schedule['end_time']} (Enabled: {schedule['enabled']})")
    
    return len(all_schedules) >= 2

def test_update_device_schedule_status(db, unit_id):
    """Test enabling/disabling a device schedule"""
    print("\n=== Test: Update Device Schedule Status ===")
    
    # Disable light schedule
    success = db.update_device_schedule_status(unit_id, "light", enabled=False)
    print(f"✓ Disable light schedule: {'Success' if success else 'Failed'}")
    
    # Verify it's disabled
    light_schedule = db.get_device_schedule(unit_id, "light")
    if light_schedule and not light_schedule['enabled']:
        print(f"✓ Light schedule is now disabled")
    else:
        print("✗ Failed to disable light schedule")
    
    # Re-enable it
    success = db.update_device_schedule_status(unit_id, "light", enabled=True)
    print(f"✓ Re-enable light schedule: {'Success' if success else 'Failed'}")
    
    return success

def test_delete_device_schedule(db, unit_id):
    """Test deleting a device schedule"""
    print("\n=== Test: Delete Device Schedule ===")
    
    # Delete pump schedule
    success = db.delete_device_schedule(unit_id, "pump")
    print(f"✓ Delete pump schedule: {'Success' if success else 'Failed'}")
    
    # Verify it's gone
    pump_schedule = db.get_device_schedule(unit_id, "pump")
    if pump_schedule is None:
        print("✓ Pump schedule successfully deleted")
    else:
        print("✗ Pump schedule still exists")
    
    # Check remaining schedules
    all_schedules = db.get_all_device_schedules(unit_id)
    print(f"✓ Remaining schedules: {list(all_schedules.keys())}")
    
    return success and pump_schedule is None

def test_update_existing_schedule(db, unit_id):
    """Test updating an existing schedule's times"""
    print("\n=== Test: Update Existing Schedule ===")
    
    # Update light schedule times
    success = db.save_device_schedule(
        unit_id=unit_id,
        device_type="light",
        start_time="07:00",
        end_time="23:00",
        enabled=True
    )
    print(f"✓ Update light schedule times: {'Success' if success else 'Failed'}")
    
    # Verify new times
    light_schedule = db.get_device_schedule(unit_id, "light")
    if light_schedule:
        if light_schedule['start_time'] == "07:00" and light_schedule['end_time'] == "23:00":
            print(f"✓ Light schedule updated: {light_schedule['start_time']} - {light_schedule['end_time']}")
        else:
            print(f"✗ Times not updated: {light_schedule}")
    
    return success

def test_backward_compatibility(db):
    """Test that old methods still work (deprecated but functional)"""
    print("\n=== Test: Backward Compatibility (Deprecated Methods) ===")
    
    # Test old save_light_schedule
    db.save_light_schedule("06:00", "20:00")
    print("✓ save_light_schedule() still works (deprecated)")
    
    # Test old get_light_schedule
    old_schedule = db.get_light_schedule()
    if old_schedule:
        print(f"✓ get_light_schedule() returns: {old_schedule}")
    
    # Test old save_fan_schedule
    db.save_fan_schedule("08:00", "18:00")
    print("✓ save_fan_schedule() still works (deprecated)")
    
    # Test old get_fan_schedule
    old_fan_schedule = db.get_fan_schedule()
    if old_fan_schedule:
        print(f"✓ get_fan_schedule() returns: {old_fan_schedule}")
    
    print("\n⚠️  Note: These methods are DEPRECATED. Use device_schedules methods instead.")
    
    return True

def cleanup(db=None):
    """Clean up test database"""
    print("\n=== Cleanup ===")
    import os
    
    # Close database connection first
    if db:
        db.close_db()
    
    # Wait a moment for Windows to release the file
    import time
    time.sleep(0.5)
    
    try:
        if os.path.exists("test_schedules.db"):
            os.remove("test_schedules.db")
            print("✓ Test database removed")
    except PermissionError:
        print("⚠️  Could not remove test database (file in use)")
    except FileNotFoundError:
        pass

def main():
    """Run all tests"""
    print("=" * 70)
    print("Testing New Device Schedule Methods")
    print("=" * 70)
    
    db = None
    try:
        # Run tests
        db, unit_id = test_save_device_schedule()
        test1 = test_get_device_schedule(db, unit_id)
        test2 = test_get_all_device_schedules(db, unit_id)
        test3 = test_update_device_schedule_status(db, unit_id)
        test4 = test_delete_device_schedule(db, unit_id)
        test5 = test_update_existing_schedule(db, unit_id)
        test6 = test_backward_compatibility(db)
        
        # Summary
        results = [test1, test2, test3, test4, test5, test6]
        print("\n" + "=" * 70)
        print(f"Tests passed: {sum(results)}/{len(results)}")
        print("=" * 70)
        
        if all(results):
            print("✓ All tests passed!")
            print("\n📋 New Methods Available:")
            print("  - save_device_schedule(unit_id, device_type, start_time, end_time, enabled)")
            print("  - get_device_schedule(unit_id, device_type)")
            print("  - get_all_device_schedules(unit_id)")
            print("  - update_device_schedule_status(unit_id, device_type, enabled)")
            print("  - delete_device_schedule(unit_id, device_type)")
        else:
            print("✗ Some tests failed")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup(db)

if __name__ == "__main__":
    main()
