#!/usr/bin/env python3
"""Cleanup script to resolve duplicate alerts"""
import sys
sys.path.insert(0, '.')

from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from app.utils.time import iso_now

db = SQLiteDatabaseHandler('database/sysgrow.db')

print("\n=== CLEANING UP DUPLICATE ALERTS ===")

with db.connection() as conn:
    # Find all duplicate alert titles with counts
    cursor = conn.execute("""
        SELECT title, COUNT(*) as count, MIN(alert_id) as keep_id
        FROM Alert 
        WHERE resolved = 0
        GROUP BY title 
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    """)
    duplicates = cursor.fetchall()
    
    total_to_resolve = 0
    
    for row in duplicates:
        title, count, keep_id = row[0], row[1], row[2]
        num_to_resolve = count - 1  # Keep one, resolve the rest
        
        print(f"\nTitle: '{title[:60]}'")
        print(f"  Total: {count} alerts")
        print(f"  Keeping: alert_id={keep_id}")
        print(f"  Resolving: {num_to_resolve} duplicates")
        
        # Resolve all except the one we're keeping
        conn.execute("""
            UPDATE Alert 
            SET resolved = 1, resolved_at = ?
            WHERE title = ? 
            AND alert_id != ?
            AND resolved = 0
        """, (iso_now(), title, keep_id))
        
        total_to_resolve += num_to_resolve
    
    conn.commit()
    
    print(f"\n✅ Resolved {total_to_resolve} duplicate alerts")
    
    # Show final count
    cursor = conn.execute("SELECT COUNT(*) FROM Alert WHERE resolved = 0")
    remaining = cursor.fetchone()[0]
    print(f"✅ Remaining active alerts: {remaining}")
