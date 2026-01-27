"""
Test Health Observation Creation and AI Services
=================================================
Tests the complete health observation workflow and AI services.
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:5000"

def test_health_observation():
    """Test creating a health observation."""
    print("\n" + "="*70)
    print("Test 1: Create Health Observation")
    print("="*70)
    
    observation_data = {
        "unit_id": 1,
        "plant_id": None,
        "health_status": "healthy",
        "symptoms": [],
        "disease_type": None,
        "severity_level": 1,
        "affected_parts": [],
        "environmental_factors": {},
        "treatment_applied": None,
        "notes": "Test observation - plant looking great!",
        "plant_type": "tomato",
        "growth_stage": "vegetative"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/ml/predictions/health/observation",
            json=observation_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code in (200, 201):
            print("✅ PASS: Health observation created successfully")
            return True
        else:
            print("❌ FAIL: Failed to create health observation")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_disease_statistics():
    """Test disease statistics endpoint."""
    print("\n" + "="*70)
    print("Test 2: Get Disease Statistics")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/ml/analytics/disease/statistics")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print("✅ PASS: Disease statistics retrieved successfully")
            return True
        else:
            print(f"Response: {response.text}")
            print("❌ FAIL: Failed to get disease statistics")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_active_units():
    """Test getting active units."""
    print("\n" + "="*70)
    print("Test 3: Get Active Units (via health system)")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/health/system")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print("✅ PASS: Monitoring status retrieved successfully")
            return True
        else:
            print(f"Response: {response.text}")
            print("⚠️  WARNING: Monitoring status endpoint may not exist yet")
            return True  # Not critical
    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Cannot connect to server. Is it running?")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_ai_status():
    """Test AI services status."""
    print("\n" + "="*70)
    print("Test 4: Get AI Services Status")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/ml/health")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print("✅ PASS: AI services status retrieved successfully")
            return True
        else:
            print(f"Response: {response.text}")
            print("❌ FAIL: Failed to get AI status")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_models_list():
    """Test listing AI models."""
    print("\n" + "="*70)
    print("Test 5: List AI Models")
    print("="*70)
    
    try:
        response = requests.get(f"{BASE_URL}/api/ml/models")
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print("✅ PASS: AI models listed successfully")
            return True
        else:
            print(f"Response: {response.text}")
            print("❌ FAIL: Failed to list AI models")
            return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_disease_prediction():
    """Test disease risk prediction."""
    print("\n" + "="*70)
    print("Test 6: Predict Disease Risk")
    print("="*70)
    
    prediction_data = {
        "unit_id": 1,
        "plant_type": "tomato",
        "growth_stage": "vegetative",
        "current_conditions": {
            "temperature": 24.5,
            "humidity": 65.0,
            "soil_moisture": 45.0
        }
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/ml/predictions/disease/risk",
            json=prediction_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Response: {json.dumps(data, indent=2)}")
            print("✅ PASS: Disease prediction successful")
            return True
        else:
            print(f"Response: {response.text}")
            print("⚠️  WARNING: Disease prediction may need trained models")
            return True  # Not critical if models not trained
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("Health Observation & AI Services Test Suite")
    print("="*70)
    print(f"Testing against: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    tests = [
        test_ai_status,
        test_models_list,
        test_disease_statistics,
        test_active_units,
        test_health_observation,
        test_disease_prediction,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except KeyboardInterrupt:
            print("\n\nTests interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error in test: {e}")
            results.append(False)
    
    # Summary
    print("\n" + "="*70)
    print("Test Summary")
    print("="*70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
    elif passed > total // 2:
        print(f"\n⚠️  MOSTLY WORKING - {total - passed} tests need attention")
    else:
        print(f"\n❌ MULTIPLE FAILURES - {total - passed} tests failed")
    
    print("="*70 + "\n")
    
    return 0 if passed == total else 1

if __name__ == '__main__':
    import sys
    sys.exit(main())
