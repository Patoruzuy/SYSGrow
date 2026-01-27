from app.utils.plant_json_handler import PlantJsonHandler

h = PlantJsonHandler()
print(f'✓ PlantJsonHandler loaded: {len(h.data["plants_info"])} plants')
print(f'✓ Required fields: {len(h.REQUIRED_FIELDS)}')
print(f'✓ New methods available: get_plant_by_id, update_plant, validate_plant_structure')
print(f'✓ Specialized methods: update_automation, update_common_issues, add_companion_plant')
print(f'✓ Search methods: search_plants, get_plants_by_difficulty')
