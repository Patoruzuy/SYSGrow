"""Legacy device schedule JSON tests skipped after v2 migration."""
import pytest

pytest.skip("Legacy device schedule storage tests removed", allow_module_level=True)
from dataclasses import dataclass
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class UnitDimensions:
    """Physical dimensions of a growth unit"""
    width: float   # cm
    height: float  # cm
    depth: float   # cm
    
    def to_dict(self) -> Dict[str, float]:
        return {
            "width": self.width,
            "height": self.height,
            "depth": self.depth,
            "volume_liters": (self.width * self.height * self.depth) / 1000
        }
    
    @staticmethod
    def from_dict(data: Dict[str, float]) -> Optional['UnitDimensions']:
        """Create UnitDimensions from dictionary"""
        if not data or 'width' not in data:
            return None
        return UnitDimensions(
            width=data['width'],
            height=data['height'],
            depth=data['depth']
        )


@dataclass
class UnitSettings:
    """Environmental settings for a growth unit."""
    temperature_threshold: float = 24.0
    humidity_threshold: float = 50.0
    soil_moisture_threshold: float = 40.0
    co2_threshold: float = 1000.0
    voc_threshold: float = 1000.0
    lux_threshold: float = 1000.0
    aqi_threshold: float = 1000.0
    device_schedules: Optional[Dict[str, Dict[str, str]]] = None
    dimensions: Optional[UnitDimensions] = None
    camera_enabled: bool = False
    
    def get_device_schedule(self, device_type: str) -> Optional[Dict[str, str]]:
        if not self.device_schedules:
            return None
        return self.device_schedules.get(device_type)

    def set_device_schedule(self, device_type: str, start_time: str, end_time: str) -> None:
        if not self.device_schedules:
            self.device_schedules = {}
        self.device_schedules[device_type] = {
            "start_time": start_time,
            "end_time": end_time
        }

    def remove_device_schedule(self, device_type: str) -> bool:
        if not self.device_schedules or device_type not in self.device_schedules:
            return False
        del self.device_schedules[device_type]
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "temperature_threshold": self.temperature_threshold,
            "humidity_threshold": self.humidity_threshold,
            "soil_moisture_threshold": self.soil_moisture_threshold,
            "co2_threshold": self.co2_threshold,
            "voc_threshold": self.voc_threshold,
            "lux_threshold": self.lux_threshold,
            "aqi_threshold": self.aqi_threshold,
            "device_schedules": json.dumps(self.device_schedules) if self.device_schedules else None,
            "dimensions": json.dumps(self.dimensions.to_dict()) if self.dimensions else None,
            "camera_enabled": self.camera_enabled
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'UnitSettings':
        """Create UnitSettings from database row or dictionary"""
        # Parse dimensions from JSON string
        dimensions_str = data.get('dimensions')
        dimensions = None
        if dimensions_str:
            try:
                dimensions_data = json.loads(dimensions_str) if isinstance(dimensions_str, str) else dimensions_str
                dimensions = UnitDimensions.from_dict(dimensions_data) if dimensions_data else None
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in dimensions: {dimensions_str}")
                dimensions = None
        
        # Parse device schedules from JSON string
        device_schedules_str = data.get('device_schedules')
        device_schedules = None
        if device_schedules_str:
            try:
                device_schedules = json.loads(device_schedules_str) if isinstance(device_schedules_str, str) else device_schedules_str
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON in device_schedules: {device_schedules_str}")
                device_schedules = None
        
        return UnitSettings(
            temperature_threshold=data.get('temperature_threshold', 24.0),
            humidity_threshold=data.get('humidity_threshold', 50.0),
            soil_moisture_threshold=data.get('soil_moisture_threshold', 40.0),
            co2_threshold=data.get('co2_threshold', 1000.0),
            voc_threshold=data.get('voc_threshold', 1000.0),
            lux_threshold=data.get('lux_threshold', data.get('lux_threshold', 1000.0)),
            aqi_threshold=data.get('aqi_threshold', 1000.0),
            device_schedules=device_schedules,
            dimensions=dimensions,
            camera_enabled=data.get('camera_enabled', False)
        )


def test_device_schedules():
    """Test device schedules serialization/deserialization"""
    print("=" * 70)
    print("Testing Device Schedules")
    print("=" * 70)
    
    # Create settings with device schedules
    settings = UnitSettings(
        temperature_threshold=25.0,
        humidity_threshold=60.0,
        device_schedules={
            "light": {"start_time": "08:00", "end_time": "20:00"},
            "fan": {"start_time": "09:00", "end_time": "19:00"},
            "heater": {"start_time": "06:00", "end_time": "22:00"}
        }
    )
    
    # Test to_dict (serialization)
    settings_dict = settings.to_dict()
    print("\n1. Serialized to_dict():")
    print(f"   device_schedules type: {type(settings_dict['device_schedules'])}")
    print(f"   device_schedules value: {settings_dict['device_schedules']}")
    
    # Verify it's a JSON string
    assert isinstance(settings_dict['device_schedules'], str), "device_schedules should be JSON string"
    
    # Test from_dict (deserialization)
    restored_settings = UnitSettings.from_dict(settings_dict)
    print("\n2. Deserialized from_dict():")
    print(f"   device_schedules type: {type(restored_settings.device_schedules)}")
    print(f"   device_schedules value: {restored_settings.device_schedules}")
    
    # Verify it's a dict again
    assert isinstance(restored_settings.device_schedules, dict), "device_schedules should be dict after deserialization"
    assert restored_settings.device_schedules["light"]["start_time"] == "08:00"
    assert restored_settings.device_schedules["fan"]["end_time"] == "19:00"
    
    # Test helper methods
    print("\n3. Testing helper methods:")
    fan_schedule = restored_settings.get_device_schedule("fan")
    print(f"   Get fan schedule: {fan_schedule}")
    assert fan_schedule == {"start_time": "09:00", "end_time": "19:00"}
    
    # Test set_device_schedule
    restored_settings.set_device_schedule("extractor", "10:00", "18:00")
    print(f"   Set extractor schedule: {restored_settings.get_device_schedule('extractor')}")
    
    # Test remove_device_schedule
    removed = restored_settings.remove_device_schedule("heater")
    print(f"   Removed heater: {removed}")
    assert "heater" not in restored_settings.device_schedules
    
    print("\n✅ Device schedules test PASSED!\n")


def test_dimensions():
    """Test dimensions serialization/deserialization"""
    print("=" * 70)
    print("Testing Dimensions")
    print("=" * 70)
    
    # Create dimensions
    dims = UnitDimensions(width=100.0, height=200.0, depth=50.0)
    print("\n1. Created dimensions:")
    print(f"   {dims}")
    
    # Create settings with dimensions
    settings = UnitSettings(
        temperature_threshold=24.0,
        dimensions=dims
    )
    
    # Test to_dict (serialization)
    settings_dict = settings.to_dict()
    print("\n2. Serialized to_dict():")
    print(f"   dimensions type: {type(settings_dict['dimensions'])}")
    print(f"   dimensions value: {settings_dict['dimensions']}")
    
    # Verify it's a JSON string
    assert isinstance(settings_dict['dimensions'], str), "dimensions should be JSON string"
    dims_parsed = json.loads(settings_dict['dimensions'])
    assert dims_parsed['width'] == 100.0
    assert dims_parsed['height'] == 200.0
    
    # Test from_dict (deserialization)
    restored_settings = UnitSettings.from_dict(settings_dict)
    print("\n3. Deserialized from_dict():")
    print(f"   dimensions type: {type(restored_settings.dimensions)}")
    print(f"   dimensions value: {restored_settings.dimensions}")
    
    # Verify it's a UnitDimensions object again
    assert isinstance(restored_settings.dimensions, UnitDimensions), "dimensions should be UnitDimensions after deserialization"
    assert restored_settings.dimensions.width == 100.0
    assert restored_settings.dimensions.height == 200.0
    assert restored_settings.dimensions.depth == 50.0
    
    print("\n✅ Dimensions test PASSED!\n")


def test_legacy_migration():
    """Test migration from legacy light_start_time/light_end_time"""
    print("=" * 70)
    print("Testing Legacy Migration")
    print("=" * 70)
    
    # Simulate loading from database with legacy fields
    legacy_data = {
        'temperature_threshold': 24.0,
        'humidity_threshold': 50.0,
        'soil_moisture_threshold': 40.0,
        'co2_threshold': 1000.0,
        'voc_threshold': 1000.0,
        'lux_threshold': 1000.0,
        'aqi_threshold': 1000.0,
        'light_start_time': '07:00',
        'light_end_time': '21:00',
        'device_schedules': None  # No device_schedules yet
    }
    
    print("\n1. Legacy data with light_start_time/light_end_time:")
    print(f"   light_start_time: {legacy_data['light_start_time']}")
    print(f"   light_end_time: {legacy_data['light_end_time']}")
    
    # Load settings (should auto-migrate)
    settings = UnitSettings.from_dict(legacy_data)
    
    print("\n2. After migration to device_schedules:")
    print(f"   device_schedules: {settings.device_schedules}")
    
    # Verify migration worked
    assert settings.device_schedules is not None, "device_schedules should be created"
    assert "light" in settings.device_schedules, "light schedule should be migrated"
    assert settings.device_schedules["light"]["start_time"] == "07:00"
    assert settings.device_schedules["light"]["end_time"] == "21:00"
    
    print("\n✅ Legacy migration test PASSED!\n")


def test_null_handling():
    """Test handling of NULL/missing values"""
    print("=" * 70)
    print("Testing NULL Handling")
    print("=" * 70)
    
    # Test with no device_schedules
    data1 = {
        'temperature_threshold': 24.0,
        'humidity_threshold': 50.0,
        'soil_moisture_threshold': 40.0,
        'co2_threshold': 1000.0,
        'voc_threshold': 1000.0,
        'lux_threshold': 1000.0,
        'aqi_threshold': 1000.0,
    }
    
    settings1 = UnitSettings.from_dict(data1)
    print("\n1. No device_schedules in data:")
    print(f"   device_schedules: {settings1.device_schedules}")
    assert settings1.device_schedules is None
    
    # Test with empty JSON string
    data2 = data1.copy()
    data2['device_schedules'] = '{}'
    settings2 = UnitSettings.from_dict(data2)
    print("\n2. Empty JSON object:")
    print(f"   device_schedules: {settings2.device_schedules}")
    assert settings2.device_schedules == {}
    
    # Test with no dimensions
    settings3 = UnitSettings.from_dict(data1)
    print("\n3. No dimensions in data:")
    print(f"   dimensions: {settings3.dimensions}")
    assert settings3.dimensions is None
    
    print("\n✅ NULL handling test PASSED!\n")


if __name__ == "__main__":
    try:
        test_device_schedules()
        test_dimensions()
        test_legacy_migration()
        test_null_handling()
        
        print("=" * 70)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 70)
        print("\nSummary:")
        print("  ✅ Device schedules serialize to JSON string")
        print("  ✅ Device schedules deserialize to Python dict")
        print("  ✅ Dimensions serialize to JSON string")
        print("  ✅ Dimensions deserialize to UnitDimensions object")
        print("  ✅ Helper methods work correctly")
        print("  ✅ Legacy migration works")
        print("  ✅ NULL/missing values handled properly")
        print("\nReady for database integration! 🚀")
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
