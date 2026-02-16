"""
Verify that all API routes use modern decorators
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
api_path = REPO_ROOT / "app" / "blueprints" / "api"
api_files = list(api_path.glob("*.py"))

print("=" * 70)
print("API Route Decorator Verification")
print("=" * 70)

total_files = 0
total_routes = 0
modern_routes = 0
old_routes = 0

for file in sorted(api_files):
    if file.name == "__init__.py":
        continue

    content = file.read_text(encoding="utf-8")

    # Count modern decorators (@api.get, @api.post, etc.)
    modern = len(re.findall(r'@\w+_api\.(get|post|put|delete|patch)\(', content))

    # Count old-style decorators (@api.route(..., methods=[...]))
    old = len(re.findall(r'@\w+_api\.route\(.+methods=\[', content))

    if modern > 0 or old > 0:
        total_files += 1
        total_routes += modern + old
        modern_routes += modern
        old_routes += old

        status = "✓" if old == 0 else "⚠"
        print(f"\n{status} {file.name}")
        print(f"  Modern decorators: {modern}")
        print(f"  Old decorators: {old}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"Total API files: {total_files}")
print(f"Total routes: {total_routes}")

if total_routes > 0:
    modern_pct = modern_routes / total_routes * 100
    old_pct = old_routes / total_routes * 100
else:
    modern_pct = 0.0
    old_pct = 0.0

print(f"Modern decorators: {modern_routes} ({modern_pct:.1f}%)")
print(f"Old decorators: {old_routes} ({old_pct:.1f}%)")

if old_routes == 0:
    print("\n✓ All routes use modern decorators!")
else:
    print(f"\n⚠ {old_routes} routes still use old-style decorators")
