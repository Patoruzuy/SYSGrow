import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

with (REPO_ROOT / 'plants_info.json').open('r', encoding='utf-8') as f:
    data = json.load(f)

plants = data['plants_info']
print(f'Total plants: {len(plants)}\n')

required_fields = ['sensor_requirements', 'yield_data', 'nutritional_info', 'automation', 'common_issues', 'companion_plants', 'harvest_guide']

incomplete = []
for p in plants:
    missing = []
    for field in required_fields:
        if field not in p:
            missing.append(field)
        elif isinstance(p[field], dict) and not p[field]:
            missing.append(f"{field} (empty)")
        elif isinstance(p[field], list) and not p[field]:
            missing.append(f"{field} (empty)")

    if missing:
        incomplete.append({
            'id': p['id'],
            'name': p['common_name'],
            'missing': missing
        })

if incomplete:
    print('Plants with incomplete data:\n')
    for p in incomplete:
        print(f"ID {p['id']:2d}: {p['name']:30s} - Missing: {', '.join(p['missing'])}")
else:
    print('All plants have complete data!')
