#!/usr/bin/env python3
"""
Quick test to verify plants data loading in the route
"""

import sys
import os
from pathlib import Path

# Add the backend directory to Python path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

def test_plants_route():
    """Test the plants guide route data loading"""
    from pathlib import Path
    from app.defaults import SystemConfigDefaults
    import json
    
    print("🧪 Testing Plants Guide Data Loading")
    print("=" * 40)
    
    # Test SystemConfigDefaults
    config_plants = SystemConfigDefaults.PLANTS_INFO
    print(f"📋 Plants from SystemConfigDefaults: {len(config_plants)}")
    
    if config_plants:
        print(f"   First plant: {config_plants[0].get('name', 'Unknown')}")
        has_growth_stages = any(plant.get('growth_stages') for plant in config_plants)
        print(f"   Has detailed growth stages: {has_growth_stages}")
    
    # Test JSON loading
    try:
        backend_dir = Path(__file__).resolve().parent.parent
        plants_file = backend_dir / 'plants_info.json'
        print(f"\n📁 Looking for plants file at: {plants_file}")
        print(f"   File exists: {plants_file.exists()}")
        
        if plants_file.exists():
            with open(plants_file, 'r') as f:
                data = json.load(f)
                json_plants_data = data.get('plants_info', [])
                print(f"📊 Plants from JSON file: {len(json_plants_data)}")
                
                if json_plants_data:
                    first_plant = json_plants_data[0]
                    print(f"   First plant: {first_plant.get('common_name', 'Unknown')}")
                    print(f"   Species: {first_plant.get('species', 'Unknown')}")
                    print(f"   pH range: {first_plant.get('pH_range', 'Unknown')}")
                    
                    growth_stages = first_plant.get('growth_stages', [])
                    print(f"   Growth stages: {len(growth_stages)}")
                    
                    if growth_stages:
                        print(f"   First stage: {growth_stages[0].get('stage', 'Unknown')}")
    except Exception as e:
        print(f"❌ Error loading JSON: {e}")
    
    print(f"\n✅ Test completed!")

if __name__ == "__main__":
    test_plants_route()