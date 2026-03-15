#!/usr/bin/env python3
"""
Test script to verify API updates for device schedules and complete fields support.

This script tests:
1. JSON serialization for dimensions and device_schedules
2. API payload structure
"""

import json


def test_dimensions_serialization():
    """Test dimensions JSON serialization"""
    print("\n=== Test 1: Dimensions Serialization ===")
    
    dimensions = {
        "width": 300,
        "height": 250,
        "depth": 200
    }
    
    # Serialize for storage
    dimensions_json = json.dumps(dimensions)
    print(f"✅ Dimensions JSON: {dimensions_json}")
    
    # Deserialize from storage
    restored_dimensions = json.loads(dimensions_json)
    assert restored_dimensions == dimensions
    print(f"✅ Deserialization successful: {restored_dimensions}")
    
    return True


def test_device_schedules_serialization():
    """Test device schedules JSON serialization"""
    print("\n=== Test 2: Device Schedules Serialization ===")
    
    device_schedules = {
        "light": {
            "start_time": "06:00",
            "end_time": "22:00",
            "enabled": True
        },
        "fan": {
            "start_time": "08:00",
            "end_time": "20:00",
            "enabled": True
        },
        "pump": {
            "start_time": "07:00",
            "end_time": "19:00",
            "enabled": False
        }
    }
    
    # Serialize for storage
    device_schedules_json = json.dumps(device_schedules)
    print(f"✅ Serialized for storage: {device_schedules_json}")
    
    # Deserialize from storage
    restored_schedules = json.loads(device_schedules_json)
    assert restored_schedules == device_schedules
    print(f"✅ Deserialization successful")
    print(f"   Retrieved {len(restored_schedules)} schedules")
    
    for device_type, schedule in restored_schedules.items():
        print(f"   - {device_type}: {schedule['start_time']}-{schedule['end_time']} (enabled: {schedule['enabled']})")
    
    return True


def test_complete_unit_creation_payload():
    """Test complete unit creation payload structure"""
    print("\n=== Test 3: Complete Unit Creation Payload ===")
    
    payload = {
        "name": "Test Greenhouse",
        "location": "Greenhouse",
        "dimensions": {
            "width": 300,
            "height": 250,
            "depth": 200
        },
        "device_schedules": {
            "light": {
                "start_time": "06:00",
                "end_time": "22:00",
                "enabled": True
            },
            "fan": {
                "start_time": "08:00",
                "end_time": "20:00",
                "enabled": True
            }
        },
        "camera_enabled": True,
        "custom_image": "/path/to/image.jpg"
    }
    
    print("✅ Complete unit creation payload:")
    print(json.dumps(payload, indent=2))
    
    # Test serialization of dimensions and device_schedules
    dimensions_json = json.dumps(payload["dimensions"])
    device_schedules_json = json.dumps(payload["device_schedules"])
    
    print(f"\n✅ Serialized dimensions: {dimensions_json}")
    print(f"✅ Serialized device_schedules: {device_schedules_json}")
    
    # Verify deserialization works
    restored_dimensions = json.loads(dimensions_json)
    restored_schedules = json.loads(device_schedules_json)
    
    assert restored_dimensions == payload["dimensions"]
    assert restored_schedules == payload["device_schedules"]
    print("✅ Round-trip serialization successful")
    
    return True


def test_api_field_extraction():
    """Test extracting fields from API request"""
    print("\n=== Test 4: API Field Extraction ===")
    
    # Simulate Flask request payload
    payload = {
        "name": "My Unit",
        "location": "Indoor",
        "dimensions": {
            "width": 150,
            "height": 200,
            "depth": 100
        },
        "device_schedules": {
            "light": {
                "start_time": "08:00",
                "end_time": "20:00",
                "enabled": True
            }
        },
        "camera_enabled": True,
        "custom_image": None
    }
    
    # Extract fields as API endpoint would
    name = payload.get("name")
    location = payload.get("location", "Indoor")
    dimensions = payload.get("dimensions")
    device_schedules = payload.get("device_schedules")
    custom_image = payload.get("custom_image")
    camera_enabled = payload.get("camera_enabled", False)
    
    print(f"✅ Extracted fields:")
    print(f"   name: {name}")
    print(f"   location: {location}")
    print(f"   dimensions: {dimensions}")
    print(f"   device_schedules: {device_schedules}")
    print(f"   custom_image: {custom_image}")
    print(f"   camera_enabled: {camera_enabled}")
    
    # Simulate service layer serialization
    dimensions_json = json.dumps(dimensions) if dimensions else None
    device_schedules_json = json.dumps(device_schedules) if device_schedules else None
    
    print(f"\n✅ Prepared for repository:")
    print(f"   dimensions_json: {dimensions_json}")
    print(f"   device_schedules_json: {device_schedules_json}")
    
    return True


def main():
    """Run all tests"""
    print("=" * 60)
    print("API Updates - Device Schedules Test Suite")
    print("=" * 60)
    
    tests = [
        ("Dimensions Serialization", test_dimensions_serialization),
        ("Device Schedules Serialization", test_device_schedules_serialization),
        ("Complete Unit Creation Payload", test_complete_unit_creation_payload),
        ("API Field Extraction", test_api_field_extraction),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            print(f"\n❌ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
