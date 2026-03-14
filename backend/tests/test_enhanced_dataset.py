#!/usr/bin/env python3
"""Test the enhanced plants dataset"""

import json

def test_enhanced_dataset():
    with open('plants_info.json', 'r') as f:
        data = json.load(f)
    
    print('📊 Enhanced Plants Dataset Summary:')
    print('=' * 50)
    enhanced_count = 0
    total_plants = len(data['plants_info'])
    
    for plant in data['plants_info']:
        if 'sensor_requirements' in plant:
            enhanced_count += 1
            print(f'✅ ID {plant["id"]}: {plant["common_name"]} - {plant.get("variety", "N/A")}')
            
            # Show yield data
            yield_data = plant.get('yield_data', {})
            if yield_data:
                market_value = yield_data.get('market_value_per_kg', 0)
                difficulty = yield_data.get('difficulty_level', 'unknown')
                print(f'   💰 Value: ${market_value}/kg, Difficulty: {difficulty}')
            
            # Show automation
            automation = plant.get('automation', {})
            if automation:
                watering = automation.get('watering_schedule', {})
                amount = watering.get('amount_ml_per_plant', 0)
                frequency = watering.get('frequency_hours', 24)
                print(f'   💧 Auto watering: {amount}ml every {frequency}hrs')
            
            # Show sensor requirements
            sensor_reqs = plant.get('sensor_requirements', {})
            if sensor_reqs:
                moisture_range = sensor_reqs.get('soil_moisture_range', {})
                temp_range = sensor_reqs.get('soil_temperature_C', {})
                print(f'   🌡️ Moisture: {moisture_range.get("min", 0)}-{moisture_range.get("max", 100)}%, Temp: {temp_range.get("min", 0)}-{temp_range.get("max", 30)}°C')
            
            print()
        else:
            print(f'❌ ID {plant["id"]}: {plant["common_name"]} - Not enhanced yet')
    
    print(f'📈 Enhanced Plants: {enhanced_count}/{total_plants}')
    print(f'🎯 Enhancement Rate: {(enhanced_count/total_plants)*100:.1f}%')
    
    # Show sample API calls
    print('\n🔗 Sample API Calls:')
    print('=' * 30)
    print('GET /api/v1/agriculture/watering-decision?plant_id=2&moisture=65')
    print('GET /api/v1/agriculture/environmental-alerts?plant_id=2&temperature=25&humidity=60')
    print('GET /api/v1/agriculture/yield-projection?plant_id=2&plants_count=10')
    print('GET /api/v1/agriculture/harvest-recommendations?plant_id=2&days_since_planting=75')
    print('GET /api/v1/agriculture/available-plants')

if __name__ == "__main__":
    test_enhanced_dataset()