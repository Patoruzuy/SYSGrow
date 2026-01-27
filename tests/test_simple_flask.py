#!/usr/bin/env python3
"""
Simple test to verify the Flask app works
"""

from app import create_app

try:
    app = create_app()
    print("✅ App created successfully")
    
    # Test device blueprint registration
    blueprints = [bp.name for bp in app.blueprints.values()]
    print(f"📋 Registered blueprints: {blueprints}")
    
    if 'devices_api' in blueprints:
        print("✅ Devices API blueprint registered")
    else:
        print("❌ Devices API blueprint NOT registered")
    
    # Test a simple route
    with app.test_client() as client:
        response = client.get('/api/devices/config/sensor_types')
        print(f"📡 Test route status: {response.status_code}")
        if response.status_code == 200:
            print("✅ Test route working")
            print(f"   Response: {response.get_json()}")
        else:
            print(f"❌ Test route failed: {response.get_data(as_text=True)}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()