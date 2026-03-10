"""
Database Utilities
==================

Shared utilities for database operations across repositories and services.

Author: SYSGrow Team
Date: January 2026
"""

from typing import Any


def row_to_dict(row) -> dict[str, Any]:
    """
    Convert database row to dictionary.

    Handles multiple row types:
    - None: Returns empty dict
    - dict: Returns as-is
    - Row object: Converts keys to dict

    Args:
        row: Database row (sqlite3.Row, dict, or None)

    Returns:
        Dictionary representation of the row

    Examples:
        >>> row = db.execute("SELECT * FROM Users WHERE id = ?", (1,)).fetchone()
        >>> user_dict = row_to_dict(row)
        >>> print(user_dict["name"])
    """
    if row is None:
        return {}
    if isinstance(row, dict):
        return row
    # Handle sqlite3.Row or similar objects with keys() method
    return {k: row[k] for k in row}
