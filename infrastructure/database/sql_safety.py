"""
SQL Safety Utilities
====================

Helpers that prevent SQL-injection via dict-key → column-name interpolation.

The ``safe_columns()`` function filters a mapping so that only keys
matching an explicit allowlist reach a ``SET …`` or ``INSERT … VALUES``
SQL fragment.  Any unknown key is silently dropped and logged.

Usage::

    from infrastructure.database.sql_safety import safe_columns

    ALLOWED = {"name", "email", "active"}
    cols = safe_columns(user_data, ALLOWED, context="update_user")
    set_clause = ", ".join(f"{k} = ?" for k in cols)
    values = [cols[k] for k in cols]
    db.execute(f"UPDATE Users SET {set_clause} WHERE id = ?", [*values, uid])
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Column names must be simple identifiers: letters, digits, underscores.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def safe_columns(
    data: dict[str, Any],
    allowed: frozenset[str] | set[str],
    *,
    context: str = "",
    drop_none: bool = False,
) -> dict[str, Any]:
    """Return *data* filtered to keys present in *allowed*.

    Parameters
    ----------
    data:
        Incoming dict (e.g. from request JSON or service layer).
    allowed:
        Set of column names that may be interpolated into SQL.
    context:
        Optional label for log messages (e.g. ``"upsert_notification_settings"``).
    drop_none:
        If ``True``, also drop keys whose value is ``None``.

    Returns
    -------
    dict[str, Any]
        Filtered copy — safe for SQL column-name interpolation.
    """
    filtered: dict[str, Any] = {}
    rejected: list[str] = []

    for key, value in data.items():
        if key not in allowed:
            rejected.append(key)
            continue
        if drop_none and value is None:
            continue
        # Defence-in-depth: even allowlisted keys must look like identifiers
        if not _IDENT_RE.match(key):
            rejected.append(key)
            continue
        filtered[key] = value

    if rejected:
        logger.warning(
            "safe_columns(%s): dropped non-allowed keys: %s",
            context or "?",
            rejected,
        )

    return filtered


def build_set_clause(cols: dict[str, Any]) -> tuple[str, list[Any]]:
    """Build a ``SET col1 = ?, col2 = ?`` fragment from *cols*.

    Returns ``(sql_fragment, values_list)``.

    >>> build_set_clause({"name": "Alice", "active": True})
    ('name = ?, active = ?', ['Alice', True])
    """
    clause = ", ".join(f"{k} = ?" for k in cols)
    return clause, list(cols.values())


def build_insert_parts(cols: dict[str, Any]) -> tuple[str, str, list[Any]]:
    """Build column-list, placeholder-list, and values for INSERT.

    Returns ``(columns_sql, placeholders_sql, values_list)``.

    >>> build_insert_parts({"user_id": 1, "email": "a@b"})
    ('user_id, email', '?, ?', [1, 'a@b'])
    """
    keys = list(cols.keys())
    columns_sql = ", ".join(keys)
    placeholders_sql = ", ".join("?" for _ in keys)
    return columns_sql, placeholders_sql, list(cols.values())
