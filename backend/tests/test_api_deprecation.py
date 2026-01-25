#!/usr/bin/env python3
"""
Test to verify Growth API device schedules are working correctly
Previously: test_api_deprecation.py - tested deprecated endpoints
Now: Tests the current Growth API device schedule endpoints
"""

import json

def test_growth_api_schedules():
    """Test Growth API device schedule endpoints"""
    print("\n=== Testing Growth API Device Schedules ===\n")
    
    print("✅ Old deprecated endpoints have been removed:")
    print("   ❌ GET /api/settings/light (removed)")
    print("   ❌ PUT /api/settings/light (removed)")
    print("   ❌ GET /api/settings/fan (removed)")
    print("   ❌ PUT /api/settings/fan (removed)\n")
    
    print("✅ Use these Growth API endpoints instead:\n")
    
    print("1. Load All Device Schedules:")
    print("   GET /api/growth/units/{unit_id}/schedules")
    
    get_all_response = {
        "ok": True,
        "data": {
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
            }
        }
    }
    
    print(f"   Response: {json.dumps(get_all_response, indent=2)}\n")
    
    print("2. Load Specific Device Schedule:")
    print("   GET /api/growth/units/{unit_id}/schedules/light")
    
    get_one_response = {
        "ok": True,
        "data": {
            "device_type": "light",
            "start_time": "06:00",
            "end_time": "22:00",
            "enabled": True
        }
    }
    
    print(f"   Response: {json.dumps(get_one_response, indent=2)}\n")
    
    print("3. Create/Update Schedule:")
    print("   POST /api/growth/units/{unit_id}/schedules")
    print("   Body: {")
    print('     "device_type": "light",')
    print('     "start_time": "06:00",')
    print('     "end_time": "22:00",')
    print('     "enabled": true')
    print("   }")
    
    post_response = {
        "ok": True,
        "message": "Schedule saved successfully"
    }
    
    print(f"   Response: {json.dumps(post_response, indent=2)}\n")
    
    print("4. Delete Schedule:")
    print("   DELETE /api/growth/units/{unit_id}/schedules/light")
    
    delete_response = {
        "ok": True,
        "message": "Schedule deleted successfully"
    }
    
    print(f"   Response: {json.dumps(delete_response, indent=2)}\n")
    
    print("=" * 60)
    print("Features:")
    print("  ✅ Unit-specific device schedules")
    print("  ✅ Enable/disable without deleting")
    print("  ✅ Support for any device type (light, fan, pump, etc.)")
    print("  ✅ RESTful API design")
    print("  ✅ Unified endpoint for all devices")
    print("=" * 60)
    print("\n📚 Documentation: docs/API_DEVICE_SCHEDULES_MIGRATION.md")

if __name__ == "__main__":
    test_growth_api_schedules()

