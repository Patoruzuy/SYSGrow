"""
Test Service Container and Architecture Integration
===================================================

Quick test to verify ServiceContainer initializes correctly with
the refactored architecture.
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


def test_service_container():
    """Test that ServiceContainer initializes correctly"""
    logger.info("=" * 60)
    logger.info("TEST: ServiceContainer Initialization")
    logger.info("=" * 60)
    
    try:
        from app.config import AppConfig
        from app.services.container import ServiceContainer
        import tempfile
        import os
        
        # Create temp directory for database
        temp_dir = tempfile.mkdtemp()
        db_path = os.path.join(temp_dir, "test.db")
        
        # Create config with temp database
        config = AppConfig(database_path=db_path)
        logger.info("✅ AppConfig created")
        
        # Build container
        container = ServiceContainer.build(config)
        logger.info("✅ ServiceContainer built")
        
        # Verify services
        assert container.growth_service is not None, "GrowthService not initialized"
        logger.info("✅ GrowthService initialized")
        
        # Note: ClimateService was removed in Phase 6 (Dec 8, 2025)
        # Hardware operations are now handled by GrowthService → Hardware Services (singletons)
        
        assert container.database is not None, "Database not initialized"
        logger.info("✅ Database initialized")
        
        # Check GrowthService has correct attributes (uses repository, not direct database_handler)
        assert hasattr(container.growth_service, 'repository'), "Missing repository"
        assert hasattr(container.growth_service, 'mqtt_client'), "Missing mqtt_client"
        logger.info("✅ GrowthService has correct attributes")
        
        # Check registry
        assert hasattr(container.growth_service, '_unit_runtimes'), "Missing _unit_runtimes"
        assert hasattr(container.growth_service, '_unit_cache'), "Missing _unit_cache"
        logger.info("✅ GrowthService has registry and cache")
        
        logger.info("\n✅ ALL CHECKS PASSED!\n")
        
        # Cleanup
        container.shutdown()
        logger.info("✅ Container shut down cleanly")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        return False


def test_ui_helpers():
    """Test that UI helpers can be imported"""
    logger.info("=" * 60)
    logger.info("TEST: UI Helpers Import")
    logger.info("=" * 60)
    
    try:
        from app.blueprints.ui.helpers import determine_landing_page, get_unit_card_data
        logger.info("✅ UI helpers imported successfully")
        
        # Check function signatures
        import inspect
        
        sig = inspect.signature(determine_landing_page)
        assert 'growth_service' in sig.parameters, "Missing growth_service parameter"
        assert 'user_id' in sig.parameters, "Missing user_id parameter"
        logger.info("✅ determine_landing_page signature correct")
        
        sig = inspect.signature(get_unit_card_data)
        assert 'growth_service' in sig.parameters, "Missing growth_service parameter"
        assert 'growth_repo' in sig.parameters, "Missing growth_repo parameter"
        assert 'unit_id' in sig.parameters, "Missing unit_id parameter"
        logger.info("✅ get_unit_card_data signature correct")
        
        logger.info("\n✅ ALL HELPER TESTS PASSED!\n")
        return True
        
    except Exception as e:
        logger.error(f"❌ Helper test failed: {e}", exc_info=True)
        return False


def main():
    """Run all tests"""
    logger.info("\n" + "=" * 60)
    logger.info("SERVICE INTEGRATION TEST SUITE")
    logger.info("=" * 60 + "\n")
    
    results = {
        "ServiceContainer": test_service_container(),
        "UI Helpers": test_ui_helpers()
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
        logger.info("🎉 ALL TESTS PASSED! Service integration is working correctly.")
    else:
        logger.error(f"⚠️  {total - passed} test(s) failed. Please review errors above.")
    
    logger.info("=" * 60 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
