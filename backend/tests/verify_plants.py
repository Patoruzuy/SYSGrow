import json

with open('plants_info.json', 'r') as f:
    data = json.load(f)

print(f'Total plants: {len(data["plants_info"])}')

for plant_id in [10, 11, 12, 13, 14, 15]:
    p = [p for p in data['plants_info'] if p['id'] == plant_id][0]
    print(f"\nPlant {plant_id} ({p['common_name']}):")
    has_automation = 'automation' in p
    has_common_issues = 'common_issues' in p
    has_companion = 'companion_plants' in p
    has_harvest = 'harvest_guide' in p
    print(f"  - automation: {'✓' if has_automation else '✗'}")
    print(f"  - common_issues: {'✓' if has_common_issues else '✗'}")
    print(f"  - companion_plants: {'✓' if has_companion else '✗'}")
    print(f"  - harvest_guide: {'✓' if has_harvest else '✗'}")
