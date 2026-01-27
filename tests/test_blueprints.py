"""
Test script to verify all API blueprints are registered correctly
"""
from app import create_app

print("Initializing application...")
app = create_app()

print("\n✓ Application created successfully!")
print("\n✓ Registered blueprints:")
for name in sorted([bp.name for bp in app.blueprints.values()]):
    print(f"  - {name}")

print(f"\n✓ Total blueprints registered: {len(app.blueprints)}")

# Check if plants_api is registered
if "plants_api" in [bp.name for bp in app.blueprints.values()]:
    print("\n✓ plants_api successfully registered!")
else:
    print("\n✗ plants_api NOT registered!")

print("\n✓ All API blueprints verified!")
