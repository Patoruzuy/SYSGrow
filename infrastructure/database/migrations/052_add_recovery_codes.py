#!/usr/bin/env python3
"""
Migration 052: Add RecoveryCodes table for offline password recovery

This enables users to reset passwords without internet/email by using
pre-generated one-time recovery codes.

Usage:
    python infrastructure/database/migrations/052_add_recovery_codes.py database/sysgrow.db
"""

import sqlite3
import sys
from pathlib import Path


def migrate(db_path: str) -> bool:
    """
    Add RecoveryCodes table for offline password recovery.

    Args:
        db_path: Path to SQLite database

    Returns:
        True if successful
    """
    print(f"Running migration 052 on {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='RecoveryCodes'
        """)
        if cursor.fetchone():
            print("RecoveryCodes table already exists, skipping")
            return True

        # Create the RecoveryCodes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS RecoveryCodes (
                code_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                used_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
            )
        """)

        # Create index for efficient lookups by user
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_recovery_codes_user ON RecoveryCodes(user_id)
        """)

        conn.commit()
        print("Created RecoveryCodes table and index")
        return True

    except sqlite3.Error as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python 052_add_recovery_codes.py <database_path>")
        sys.exit(1)

    db_path = sys.argv[1]
    if not Path(db_path).exists():
        print(f"Database not found: {db_path}")
        sys.exit(1)

    success = migrate(db_path)
    sys.exit(0 if success else 1)
