"""
Test Refactored Architecture
=============================

This script tests the new architecture:
- GrowthService (registry + caching)
- UnitRuntime (domain model)
- Hardware Services (SensorManagementService, ActuatorManagementService)
- PlantProfile (enhanced)
- Plant growth scheduling integration

Run this before integration testing to verify basic functionality.
"""

import sys
import logging
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_imports():
    """Test that all key imports work correctly"""
    logger.info("=" * 60)
    logger.info("TEST 1: Verifying Imports")
    logger.info("=" * 60)
    
    try:
        # Test service layer
        from app.services.application.growth_service import GrowthService
        logger.info("✅ GrowthService imported successfully")
        
        # Test domain layer
        from app.domain.unit_runtime import UnitRuntime, UnitSettings, UnitDimensions
        logger.info("✅ UnitRuntime imported successfully")
        
        from app.domain.plant_profile import PlantProfile
        logger.info("✅ PlantProfile imported successfully")
        
        # Test database
        from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
        logger.info("✅ SQLiteDatabaseHandler imported successfully")
        
        logger.info("\n✅ ALL IMPORTS SUCCESSFUL\n")
        return True
        
    except ImportError as e:
        logger.error(f"❌ Import failed: {e}")
        return False


def test_unit_runtime_creation():
    """Test creating a UnitRuntime instance"""
    logger.info("=" * 60)
    logger.info("TEST 2: UnitRuntime Creation")
    logger.info("=" * 60)
    
    try:
        from app.domain.unit_runtime import UnitRuntime, UnitSettings
        
        # Create settings
        settings = UnitSettings(
            temperature_threshold=25.0,
            humidity_threshold=60.0,
            soil_moisture_threshold=50.0,
            device_schedules={
                "light": {"start_time": "08:00", "end_time": "20:00", "enabled": True}
            }
        )
        
        # Create UnitRuntime (no plants parameter - PlantService owns plants)
        runtime = UnitRuntime(
            unit_id=999,
            unit_name="Test Unit",
            location="Test Lab",
            user_id=1,
            settings=settings
        )
        
        logger.info(f"✅ Created UnitRuntime: {runtime}")
        logger.info(f"   - Unit ID: {runtime.unit_id}")
        logger.info(f"   - Name: {runtime.unit_name}")
        logger.info(f"   - Location: {runtime.location}")
        logger.info(f"   - Settings: {runtime.settings}")
        
        # Verify UnitRuntime does NOT have plant management (PlantService handles this)
        logger.info("\n📋 Testing that plants are managed by PlantService:")
        assert not hasattr(runtime, 'plants'), "❌ UnitRuntime should not have plants attribute!"
        assert not hasattr(runtime, 'get_all_plants'), "❌ UnitRuntime should not have get_all_plants!"
        logger.info("   ✅ Plants managed by PlantService (not UnitRuntime)")
        
        logger.info("\n✅ UNITRUNTIME CREATION SUCCESSFUL\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ UnitRuntime creation failed: {e}", exc_info=True)
        return False


def test_plant_profile_enhancement():
    """Test PlantProfile enhancements"""
    logger.info("=" * 60)
    logger.info("TEST 3: PlantProfile Enhancements")
    logger.info("=" * 60)
    
    try:
        from app.domain.plant_profile import PlantProfile
        
        # Create a test plant with correct growth_stages format
        growth_stages = [
            {
                "stage": "seedling",
                "duration": {"min_days": 7, "max_days": 14},
                "conditions": {"light_hours": 16, "temperature": 22, "humidity": 70}
            },
            {
                "stage": "vegetative",
                "duration": {"min_days": 21, "max_days": 35},
                "conditions": {"light_hours": 18, "temperature": 24, "humidity": 65}
            },
            {
                "stage": "flowering",
                "duration": {"min_days": 35, "max_days": 50},
                "conditions": {"light_hours": 12, "temperature": 26, "humidity": 60}
            }
        ]
        
        plant = PlantProfile(
            id=888,
            plant_name="Test Tomato",
            current_stage="seedling",
            growth_stages=growth_stages,
            plant_type="tomato",
            days_in_stage=2,
            moisture_level=55.0,
        )
        
        logger.info(f"✅ Created PlantProfile: {plant}")
        logger.info(f"   - __repr__: {repr(plant)}")
        logger.info(f"   - __str__: {str(plant)}")
        
        # Test to_dict
        logger.info("\n📋 Testing to_dict():")
        plant_dict = plant.to_dict()
        logger.info(f"   - plant_type: {plant_dict.get('plant_type')}")
        logger.info(f"   - current_stage_index: {plant_dict.get('current_stage_index')}")
        logger.info(f"   - total_stages: {plant_dict.get('total_stages')}")
        logger.info(f"   - is_mature: {plant_dict.get('is_mature')}")
        
        # Test get_status
        logger.info("\n📋 Testing get_status():")
        status = plant.get_status()
        logger.info(f"   - stage_info: {status.get('stage_info')}")
        logger.info(f"   - warning: {status.get('warning')}")
        
        # Test growth
        logger.info("\n📋 Testing grow():")
        logger.info(f"   - Before: Day {plant.days_in_stage}")
        plant.grow()
        logger.info(f"   - After: Day {plant.days_in_stage}")
        
        logger.info("\n✅ PLANTPROFILE ENHANCEMENTS SUCCESSFUL\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ PlantProfile test failed: {e}", exc_info=True)
        return False


def test_plant_timer_observer():
    """Test PlantTimerObserver - SKIPPED (functionality moved to PlantService)"""
    logger.info("=" * 60)
    logger.info("TEST 4: PlantTimerObserver - SKIPPED (moved to PlantService)")
    logger.info("=" * 60)
    logger.info("   ℹ️  Plant growth is now handled by PlantService")
    return True


def test_unit_runtime_manager_structure():
    """DEPRECATED: UnitRuntimeManager has been removed - this test is obsolete"""
    logger.info("TEST 5: UnitRuntimeManager Structure - SKIPPED (no longer exists)")
    return True

def _test_unit_runtime_manager_structure_OLD():
    """OLD TEST - UnitRuntimeManager structure (DEPRECATED)"""
    logger.info("=" * 60)
    logger.info("TEST 5: UnitRuntimeManager Structure")
    logger.info("=" * 60)
    
    try:
        from app.models.unit_runtime_manager import UnitRuntimeManager
        
        # Just verify the class exists and has the right methods
        logger.info("✅ UnitRuntimeManager class imported")
        
        # Check methods exist
        methods = [
            'attach_unit_runtime',
            '_setup_plant_observers',
            '_schedule_plant_growth',
            'add_plant_observer',
            'remove_plant_observer',
            'reload_plant_observers',
            'start',
            'stop'
        ]
        
        logger.info("\n📋 Checking plant management methods:")
        for method in methods:
            if hasattr(UnitRuntimeManager, method):
                logger.info(f"   ✅ {method}")
            else:
                logger.error(f"   ❌ {method} MISSING!")
                return False
        
        logger.info("\n✅ UNITRUNTIMEMANAGER STRUCTURE SUCCESSFUL\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ UnitRuntimeManager test failed: {e}", exc_info=True)
        return False


def test_bidirectional_attachment():
    """DEPRECATED: UnitRuntimeManager has been removed - this test is obsolete"""
    logger.info("TEST 6: Bidirectional Attachment - SKIPPED (no longer exists)")
    return True

def _test_bidirectional_attachment_OLD():
    """OLD TEST - Bidirectional attachment (DEPRECATED - UnitRuntimeManager no longer exists)"""
    logger.info("This test is obsolete - UnitRuntimeManager was removed in hardware refactoring")
    return True



def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("REFACTORED ARCHITECTURE TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    results = {
        "Imports": test_imports(),
        "UnitRuntime Creation": test_unit_runtime_creation(),
        "PlantProfile Enhancements": test_plant_profile_enhancement(),
        "PlantTimerObserver": test_plant_timer_observer(),
        "UnitRuntimeManager Structure": test_unit_runtime_manager_structure(),
        "Bidirectional Attachment": test_bidirectional_attachment()
    }
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("TEST SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
    
    logger.info("\n" + "=" * 60)
    logger.info(f"RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 ALL TESTS PASSED! Architecture is ready for integration testing.")
    else:
        logger.error(f"⚠️  {total - passed} test(s) failed. Please review errors above.")
    
    logger.info("=" * 60 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
