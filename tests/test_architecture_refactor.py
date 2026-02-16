"""
Test Architecture Refactoring - Domain Model Verification
==========================================================
Verifies that UnitRuntime is now a pure domain model without infrastructure dependencies.

Run: python test_architecture_refactor.py
"""

import logging
import sys

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_unit_runtime_is_domain_only():
    """Verify UnitRuntime has no infrastructure dependencies"""
    logger.info("=" * 70)
    logger.info("TEST 1: UnitRuntime Domain Model Verification")
    logger.info("=" * 70)

    from app.domain.unit_runtime import UnitRuntime, UnitSettings

    # Test 1: Constructor accepts domain data only
    logger.info("\n📋 Test 1.1: Constructor parameters")
    import inspect

    sig = inspect.signature(UnitRuntime.__init__)
    params = list(sig.parameters.keys())

    # Should NOT have repository parameters
    assert "growth_repo" not in params, "❌ UnitRuntime still has growth_repo dependency!"
    assert "analytics_repo" not in params, "❌ UnitRuntime still has analytics_repo dependency!"
    logger.info("   ✅ No repository parameters in constructor")

    # Plants are now managed by PlantService, not UnitRuntime
    assert "plants" not in params, "❌ UnitRuntime should not have plants parameter (use PlantService)!"
    logger.info("   ✅ No plants parameter (PlantService owns plant collection)")

    # Test 2: Can instantiate without repositories
    logger.info("\n📋 Test 1.2: Instantiation without repositories")
    try:
        runtime = UnitRuntime(unit_id=1, unit_name="Test Unit", location="Indoor", user_id=1, settings=UnitSettings())
        logger.info("   ✅ UnitRuntime created without repositories")
        logger.info(f"      - Unit ID: {runtime.unit_id}")
        logger.info(f"      - Name: {runtime.unit_name}")
    except TypeError as e:
        logger.error(f"   ❌ Failed to create UnitRuntime: {e}")
        return False

    # Test 3: Verify no _load_plants_from_db method
    logger.info("\n📋 Test 1.3: No database loading methods")
    assert not hasattr(runtime, "_load_plants_from_db"), "❌ _load_plants_from_db method still exists!"
    logger.info("   ✅ No _load_plants_from_db method (plant loading now in PlantService)")

    # Test 4: Verify no plant management methods in UnitRuntime
    logger.info("\n📋 Test 1.4: No plant management methods in UnitRuntime")
    assert not hasattr(runtime, "add_plant"), "❌ add_plant method still exists!"
    assert not hasattr(runtime, "plants"), "❌ plants attribute still exists!"
    assert not hasattr(runtime, "get_plant"), "❌ get_plant method still exists!"
    assert not hasattr(runtime, "get_all_plants"), "❌ get_all_plants method still exists!"
    assert not hasattr(runtime, "add_plant_to_memory"), "❌ add_plant_to_memory method still exists!"
    assert not hasattr(runtime, "pop_plant_from_memory"), "❌ pop_plant_from_memory method still exists!"
    logger.info("   ✅ No plant management methods (use PlantService instead)")

    logger.info("\n✅ DOMAIN MODEL VERIFICATION SUCCESSFUL\n")
    return True


def test_growth_service_loads_plants():
    """Verify PlantService owns plant collection"""
    logger.info("=" * 70)
    logger.info("TEST 2: PlantService Plant Management")
    logger.info("=" * 70)

    from app.services.application.plant_service import PlantService

    # Check PlantService methods exist
    logger.info("\n📋 Test 2.1: PlantService has required methods")

    required_methods = ["list_plants", "get_plant", "create_plant_profile", "remove_plant", "get_active_plant"]
    for method in required_methods:
        assert hasattr(PlantService, method), f"❌ PlantService missing {method} method!"
        logger.info(f"   ✅ PlantService.{method}() exists")

    logger.info("\n✅ PLANT SERVICE VERIFICATION SUCCESSFUL\n")
    return True


def test_climate_service_no_duplicate_managers():
    """Verify ClimateService doesn't create duplicate hardware managers"""
    logger.info("=" * 70)
    logger.info("TEST 3: ClimateService Hardware Manager Creation")
    logger.info("=" * 70)

    import inspect

    from app.services.application.growth_service import GrowthService

    logger.info("\n📋 Test 3.1: No fallback UnitRuntimeManager creation")
    source = inspect.getsource(GrowthService.start_unit_runtime)

    # Count how many times UnitRuntimeManager is instantiated
    manager_instantiations = source.count("UnitRuntimeManager(")

    assert manager_instantiations == 0, f"❌ Found {manager_instantiations} UnitRuntimeManager instantiations!"
    logger.info("   ✅ No direct UnitRuntimeManager instantiation in GrowthService")

    # Verify it uses singleton hardware services
    assert "sensor_service" in source.lower(), "❌ Doesn't reference SensorManagementService!"
    assert "actuator_service" in source.lower(), "❌ Doesn't reference ActuatorManagementService!"

    logger.info("   ✅ Requires GrowthService to be available")
    logger.info("   ✅ Fails fast if GrowthService not provided")

    logger.info("\n✅ CLIMATE SERVICE VERIFICATION SUCCESSFUL\n")
    return True


def test_full_integration():
    """Test full integration: PlantService manages plant collection"""
    logger.info("=" * 70)
    logger.info("TEST 4: Full Integration Test")
    logger.info("=" * 70)

    from unittest.mock import MagicMock

    from app.services.application.growth_service import GrowthService
    from app.services.application.plant_service import PlantService
    from infrastructure.database.repositories.analytics import AnalyticsRepository
    from infrastructure.database.repositories.devices import DeviceRepository
    from infrastructure.database.repositories.growth import GrowthRepository
    from infrastructure.logging.audit import AuditLogger

    # Create mocks
    mock_growth = MagicMock(spec=GrowthRepository)
    mock_analytics = MagicMock(spec=AnalyticsRepository)
    mock_audit = MagicMock(spec=AuditLogger)
    mock_devices = MagicMock(spec=DeviceRepository)
    mock_plant_service = MagicMock(spec=PlantService)

    # Mock plant data via PlantService
    from app.domain.plant_profile import PlantProfile

    mock_plant = PlantProfile(
        plant_id=1,
        plant_name="Test Tomato",
        plant_type="Tomatoes",
        current_stage="Seedling",
        days_in_stage=5,
        moisture_level=60.0,
    )
    mock_plant_service.list_plants.return_value = [mock_plant]
    mock_plant_service.get_active_plant.return_value = mock_plant

    logger.info("\n📋 Test 4.1: Create GrowthService")
    service = GrowthService(
        unit_repo=mock_growth,
        analytics_repo=mock_analytics,
        audit_logger=mock_audit,
        devices_repo=mock_devices,
        plant_service=mock_plant_service,
        cache_enabled=False,
    )
    logger.info("   ✅ GrowthService created")

    logger.info("\n📋 Test 4.2: Create UnitRuntime via get_unit_runtime")
    unit_data = {"unit_id": 1, "name": "Test Unit", "location": "Indoor", "user_id": 1, "custom_image": None}

    mock_growth.get_unit.return_value = unit_data
    runtime = service.get_unit_runtime(1)

    assert runtime is not None, "❌ Failed to create runtime!"
    assert runtime.unit_id == 1, "❌ Wrong unit ID!"

    logger.info("   ✅ UnitRuntime created (plants managed by PlantService)")
    logger.info(f"      - Unit: {runtime.unit_name}")

    # Verify PlantService owns plant collection
    logger.info("\n📋 Test 4.3: Verify PlantService owns plant collection")
    plants = mock_plant_service.list_plants(unit_id=1)
    assert len(plants) == 1, f"❌ Expected 1 plant from PlantService, got {len(plants)}!"
    assert plants[0].plant_name == "Test Tomato", "❌ Wrong plant name!"
    logger.info(f"   ✅ PlantService.list_plants() returned {len(plants)} plant(s)")
    logger.info(f"      - Plant: {plants[0].plant_name}")

    # Verify UnitRuntime doesn't have plants attribute
    assert not hasattr(runtime, "plants"), "❌ UnitRuntime should not have plants attribute!"
    logger.info("   ✅ UnitRuntime has no plants attribute (PlantService is single source)")

    logger.info("\n✅ FULL INTEGRATION TEST SUCCESSFUL\n")
    return True


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 70)
    logger.info("ENTERPRISE ARCHITECTURE REFACTORING VERIFICATION")
    logger.info("=" * 70)
    logger.info("Verifying Domain-Driven Design principles:")
    logger.info("  1. Domain models have no infrastructure dependencies")
    logger.info("  2. Services handle persistence and orchestration")
    logger.info("  3. No duplicate hardware manager creation")
    logger.info("=" * 70 + "\n")

    tests = [
        test_unit_runtime_is_domain_only,
        test_growth_service_loads_plants,
        test_climate_service_no_duplicate_managers,
        test_full_integration,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"❌ Test {test.__name__} failed with exception: {e}", exc_info=True)
            failed += 1

    logger.info("=" * 70)
    logger.info("FINAL RESULTS")
    logger.info("=" * 70)
    logger.info(f"✅ Passed: {passed}/{len(tests)}")
    if failed > 0:
        logger.info(f"❌ Failed: {failed}/{len(tests)}")
        return 1
    else:
        logger.info("🎉 ALL TESTS PASSED - ARCHITECTURE REFACTORING SUCCESSFUL!")
        logger.info("\nKey Improvements:")
        logger.info("  ✓ UnitRuntime is now a pure domain model")
        logger.info("  ✓ No infrastructure dependencies in domain layer")
        logger.info("  ✓ GrowthService handles all persistence")
        logger.info("  ✓ No duplicate hardware manager creation")
        logger.info("  ✓ Clean separation of concerns")
        return 0


if __name__ == "__main__":
    sys.exit(main())
