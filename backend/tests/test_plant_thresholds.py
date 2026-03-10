#!/usr/bin/env python3
"""
Test Plant-Specific Threshold System
Tests the ThresholdService with domain objects
"""

import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from app.services.application.threshold_service import ThresholdService


def test_get_generic_thresholds():
    """Test getting generic fallback thresholds"""
    print("\n=== Test 1: Generic Thresholds (Fallback) ===")
    service = ThresholdService()

    # Non-existent plant should return generic thresholds
    thresholds = service.get_thresholds("NonExistentPlant")

    print("✓ Generic thresholds loaded (EnvironmentalThresholds domain object)")
    print(f"  Temperature: {thresholds.temperature}°C")
    print(f"  Humidity: {thresholds.humidity}%")
    print(f"  Soil moisture: {thresholds.soil_moisture}%")
    print(f"  CO2: {thresholds.co2} ppm")

    return True


def test_get_plant_specific_thresholds():
    """Test getting plant-specific thresholds (averaged across stages)"""
    print("\n=== Test 2: Plant-Specific Thresholds (Tomatoes) ===")
    service = ThresholdService()

    thresholds = service.get_thresholds("Tomatoes")

    print("✓ Tomato-specific thresholds loaded")
    print(f"  Temperature: {thresholds.temperature}°C")
    print(f"  Humidity: {thresholds.humidity}%")
    print(f"  Soil moisture: {thresholds.soil_moisture}%")
    print(f"  CO2: {thresholds.co2} ppm")

    return True


def test_get_stage_specific_thresholds():
    """Test getting growth stage-specific thresholds"""
    print("\n=== Test 3: Stage-Specific Thresholds (Tomatoes - Vegetative) ===")
    service = ThresholdService()

    thresholds = service.get_thresholds("Tomatoes", "Vegetative")

    print("✓ Vegetative stage thresholds loaded")
    print(f"  Temperature: {thresholds.temperature}°C")
    print(f"  Humidity: {thresholds.humidity}%")
    print(f"  Soil moisture: {thresholds.soil_moisture}%")

    return True


def test_domain_object_methods():
    """Test EnvironmentalThresholds domain object methods"""
    print("\n=== Test 4: Domain Object Methods ===")
    service = ThresholdService()

    thresholds = service.get_thresholds("Lettuce")

    print("✓ Domain object methods:")
    print(f"  to_dict(): {thresholds.to_dict()}")
    print(f"  Immutable: {thresholds.__dataclass_fields__}")

    # Test with_X methods
    modified = thresholds.with_temperature(25.0)
    print(f"  with_temperature(25.0): {modified.temperature}°C (original: {thresholds.temperature}°C)")

    return True


def test_growth_stages():
    """Test getting list of growth stages"""
    print("\n=== Test 5: Growth Stages ===")
    service = ThresholdService()

    stages = service.get_plant_growth_stages("Tomatoes")
    print(f"✓ Tomato growth stages: {stages}")

    return True


def test_ai_integration():
    """Test get_optimal_conditions (AI-enhanced)"""
    print("\n=== Test 6: AI Integration (get_optimal_conditions) ===")
    service = ThresholdService()  # No AI model = returns plant-specific only

    optimal = service.get_optimal_conditions("Tomatoes", "Flowering", use_ai=False)

    print("✓ Optimal conditions (without AI):")
    print(f"  Temperature: {optimal.temperature}°C")
    print(f"  Humidity: {optimal.humidity}%")
    print(f"  Soil moisture: {optimal.soil_moisture}%")

    return True


def test_validation_methods():
    """Test is_within_optimal_range method"""
    print("\n=== Test 7: Validation Methods ===")
    service = ThresholdService()

    current_conditions = {"temperature": 24.5, "humidity": 60.0, "soil_moisture": 55.0, "co2": 1000.0}

    results = service.is_within_optimal_range("Tomatoes", "Vegetative", current_conditions)

    print("✓ is_within_optimal_range():")
    for factor, is_ok in results.items():
        status = "✓" if is_ok else "✗"
        print(f"  {status} {factor}: {current_conditions[factor]}")

    return True


def test_adjustment_recommendations():
    """Test get_adjustment_recommendations method"""
    print("\n=== Test 8: Adjustment Recommendations ===")
    service = ThresholdService()

    current_conditions = {
        "temperature": 30.0,  # Too hot
        "humidity": 40.0,  # Too low
        "soil_moisture": 55.0,  # OK
    }

    recommendations = service.get_adjustment_recommendations("Lettuce", "Vegetative", current_conditions)

    print("✓ get_adjustment_recommendations():")
    for factor, rec in recommendations.items():
        print(f"  {factor}: {rec['action']} by {rec['amount']:.1f} (priority: {rec['priority']})")

    return True


def test_caching():
    """Test threshold caching"""
    print("\n=== Test 9: Caching Mechanism ===")
    service = ThresholdService()

    # First call - loads from data
    thresholds1 = service.get_thresholds("Tomatoes", "Flowering")
    print("✓ First call: loaded from data")

    # Second call - should use cache
    thresholds2 = service.get_thresholds("Tomatoes", "Flowering")
    print("✓ Second call: loaded from cache")

    # Verify same object
    assert thresholds1.temperature == thresholds2.temperature
    print(f"  Cache working: {thresholds1.temperature == thresholds2.temperature}")

    # Clear cache
    service.clear_cache()
    print("✓ Cache cleared")

    return True


def test_all():
    """Run all tests"""
    print("=" * 70)
    print("PLANT THRESHOLD SYSTEM - DOMAIN-DRIVEN DESIGN TESTS")
    print("=" * 70)

    tests = [
        test_get_generic_thresholds,
        test_get_plant_specific_thresholds,
        test_get_stage_specific_thresholds,
        test_domain_object_methods,
        test_growth_stages,
        test_ai_integration,
        test_validation_methods,
        test_adjustment_recommendations,
        test_caching,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"\n✗ Test failed: {test.__name__}")
            print(f"  Error: {e}")
            failed += 1

    print("\n" + "=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    success = test_all()
    sys.exit(0 if success else 1)
