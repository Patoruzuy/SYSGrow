#!/usr/bin/env python3
"""Test script to verify alert resolution"""
import sys
sys.path.insert(0, '.')

from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from infrastructure.database.repositories.alerts import AlertRepository
from app.services.application.alert_service import AlertService

# Initialize
db = SQLiteDatabaseHandler('database/sysgrow.db')
repo = AlertRepository(db)
svc = AlertService(repo)

# Get active alerts
print("\n=== ACTIVE ALERTS ===")
alerts = svc.get_active_alerts(limit=10)
print(f"Found {len(alerts)} active alerts:")
for a in alerts:
    print(f"  ID {a['alert_id']}: {a['title'][:50]} (resolved={a.get('resolved', False)})")

# Check database directly
print("\n=== DATABASE CHECK (last 10 alerts) ===")
with db.connection() as conn:
    cursor = conn.execute("""
        SELECT alert_id, title, resolved, resolved_at 
        FROM Alert 
        ORDER BY alert_id DESC 
        LIMIT 10
    """)
    for row in cursor.fetchall():
        print(f"  ID {row[0]}: resolved={row[2]}, resolved_at={row[3]}, title={row[1][:50]}")

# Check for duplicates
print("\n=== DUPLICATE CHECK ===")
with db.connection() as conn:
    cursor = conn.execute("""
        SELECT title, COUNT(*) as count 
        FROM Alert 
        WHERE resolved = 0
        GROUP BY title 
        HAVING COUNT(*) > 1
        ORDER BY count DESC
        LIMIT 5
    """)
    duplicates = cursor.fetchall()
    if duplicates:
        print("Found duplicate alerts:")
        for row in duplicates:
            print(f"  '{row[0][:50]}': {row[1]} occurrences")
    else:
        print("No duplicate alerts found")
