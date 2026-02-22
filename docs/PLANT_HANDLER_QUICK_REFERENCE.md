# PlantJsonHandler Quick Reference

## Basic Usage

```python
from app.utils.plant_json_handler import PlantJsonHandler

# Initialize handler
handler = PlantJsonHandler()  # Uses default plants_info.json
```

## Read Operations

### Get All Plants
```python
all_plants = handler.get_plants_info()
# Returns: List of all 15 plants with complete data
```

### Get Plant by ID
```python
tomatoes = handler.get_plant_by_id(2)
# Returns: Complete plant dictionary or None
```

### Get Growth Stages
```python
stages = handler.get_growth_stages("Tomatoes")
# Returns: List of growth stages for the plant
```

### Check if Plant Exists
```python
exists = handler.plant_exists("Lettuce")
# Returns: True/False
```

### List All Plant Names
```python
names = handler.list_plants()
# Returns: ['Leafy Greens', 'Tomatoes', 'Peppers', ...]
```

## Write Operations

### Add New Plant
```python
new_plant = {
    "common_name": "New Plant",
    "species": "Species name",
    "variety": "Variety",
    # ... all required fields
}
success = handler.add_plant(new_plant)
# Auto-assigns ID, checks for duplicates, saves to disk
```

### Update Entire Plant
```python
success = handler.update_plant(5, {
    "variety": "English Cucumber",
    "tips": ["Water consistently", "Provide support"]
}, validate=True)
# Updates multiple fields, optional validation
```

### Delete Plant
```python
success = handler.delete_plant(10)
# Removes plant and saves to disk
```

## Validation

### Validate Plant Structure
```python
plant = handler.get_plant_by_id(3)
is_valid = handler.validate_plant_structure(plant, strict=True)
# strict=True: Requires all fields (returns False if missing)
# strict=False: Logs warnings only (returns True)
```

## Specialized Field Updates

### Update Automation Settings
```python
handler.update_automation(5, {
    "watering_schedule": {
        "frequency_hours": 24,
        "amount_ml_per_plant": 500,
        "soil_moisture_trigger": 60
    },
    "lighting_schedule": {
        "daily_hours": 14,
        "intensity_lux": 25000,
        "schedule": "06:00-20:00"
    }
})
```

### Update Common Issues
```python
handler.update_common_issues(3, [
    {
        "problem": "Aphids",
        "symptoms": ["Sticky leaves", "Distorted growth"],
        "causes": ["Poor air circulation"],
        "solutions": ["Neem oil spray", "Beneficial insects"],
        "prevention": "Regular inspection"
    }
])
```

### Add Companion Plants
```python
handler.add_companion_plant(7, {
    "beneficial": [
        {"plant": "Tomatoes", "reason": "Pest deterrent"}
    ],
    "plants_to_avoid": ["Dill"]
})
```

### Update Harvest Guide
```python
handler.update_harvest_guide(14, {
    "harvest_indicators": {
        "visual": "Leaves fully formed",
        "size": "6-8 inches tall"
    },
    "best_time_of_day": "Morning",
    "storage": {
        "temperature": "1-4°C",
        "humidity": "95-100%",
        "duration": "7-10 days"
    },
    "processing": ["Wash immediately", "Remove damaged leaves"]
})
```

## Search & Filter

### Search by Criteria
```python
# Find all Cannabis plants
cannabis = handler.search_plants(species="Cannabis sativa")

# Find specific variety
cherry = handler.search_plants(variety="Cherry")

# Multiple criteria
results = handler.search_plants(species="Tomatoes", variety="Cherry")
```

### Filter by Difficulty
```python
easy_plants = handler.get_plants_by_difficulty("Easy")
medium_plants = handler.get_plants_by_difficulty("Medium")
advanced_plants = handler.get_plants_by_difficulty("Advanced")
```

### Get Plants with Automation
```python
automated = handler.get_plants_requiring_automation()
# Returns all plants that have automation configurations
```

## Export

### Export Plant Summary
```python
summary = handler.export_plant_summary(9)
# Returns simplified data for API responses:
# {
#     "id": 9,
#     "common_name": "Autoflowering Cannabis",
#     "species": "Cannabis ruderalis",
#     "difficulty_level": "intermediate",
#     "automation_enabled": True,
#     "companion_plants": ["Basil", "Marigolds", ...]
# }
```

## Common Patterns

### Update Multiple Plants
```python
# Update all cannabis plants
cannabis_plants = handler.search_plants(species="Cannabis sativa")
for plant in cannabis_plants:
    handler.update_plant(plant['id'], {
        "tips": ["Monitor pH closely", "Use LED grow lights"]
    })
```

### Validate All Plants
```python
all_plants = handler.get_plants_info()
for plant in all_plants:
    if not handler.validate_plant_structure(plant):
        print(f"Warning: {plant['common_name']} has missing fields")
```

### Export All Plant Summaries
```python
all_plants = handler.get_plants_info()
summaries = [
    handler.export_plant_summary(plant['id'])
    for plant in all_plants
]
```

## Error Handling

```python
# All methods handle errors gracefully
plant = handler.get_plant_by_id(999)  # Returns None
if plant is None:
    print("Plant not found")

# Update returns False on failure
success = handler.update_plant(999, {"variety": "New"})
if not success:
    print("Update failed - plant not found")
```

## Required Fields

All plants must have these 17 fields:

1. `id` - Unique identifier
2. `species` - Scientific name
3. `common_name` - Common name
4. `variety` - Plant variety
5. `pH_range` - Soil pH requirements
6. `water_requirements` - Watering needs
7. `sensor_requirements` - Sensor thresholds
8. `yield_data` - Expected yields
9. `nutritional_info` - Nutrient requirements
10. `automation` - **Automation schedules and thresholds**
11. `growth_stages` - Development stages
12. `common_issues` - **Pest/disease problems and solutions**
13. `companion_plants` - **Beneficial and incompatible plants**
14. `harvest_guide` - **Harvest timing and storage**
15. `tips` - Growing tips
16. `disease_prevention` - Disease prevention strategies
17. `fertilizer_recommendations` - Fertilization guidelines

## Complete Example

```python
from app.utils.plant_json_handler import PlantJsonHandler

# Initialize
handler = PlantJsonHandler()

# Get a plant
plant = handler.get_plant_by_id(5)  # Cucumbers
print(f"Plant: {plant['common_name']}")

# Update automation
handler.update_automation(5, {
    "watering_schedule": {
        "frequency_hours": 24,
        "amount_ml_per_plant": 400
    }
})

# Add a common issue
current_issues = plant.get('common_issues', [])
current_issues.append({
    "problem": "Powdery Mildew",
    "symptoms": ["White powder on leaves"],
    "causes": ["High humidity", "Poor air circulation"],
    "solutions": ["Increase air flow", "Apply fungicide"],
    "prevention": "Space plants properly"
})
handler.update_common_issues(5, current_issues)

# Validate
if handler.validate_plant_structure(plant):
    print("✓ Plant data is complete")

# Export summary for API
summary = handler.export_plant_summary(5)
print(f"API Summary: {summary}")
```

## Tips

- **Always validate** after major updates: `validate_plant_structure(plant)`
- **Use specialized methods** for nested structures (automation, issues, etc.)
- **Search before adding** new plants to avoid duplicates
- **Export summaries** for API responses to reduce payload size
- **All methods auto-save** to disk when modifying data
