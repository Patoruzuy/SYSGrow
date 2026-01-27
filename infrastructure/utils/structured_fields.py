from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def parse_json_object(raw: Any) -> Optional[Any]:
    """
    Parse a JSON-serializable object from a string or pass through dict/list.

    Returns None for empty strings or invalid JSON.
    """
    if raw is None:
        return None
    if isinstance(raw, str):
        raw_str = raw.strip()
        if not raw_str:
            return None
        try:
            return json.loads(raw_str)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON string for structured field: %s", raw_str)
            return None
    if isinstance(raw, (dict, list)):
        return raw
    return None


def normalize_dimensions(raw: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize dimensions to a dict with width/height/depth keys.
    """
    parsed = parse_json_object(raw)
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        return None

    return dict(parsed)


def normalize_device_schedules(raw: Any) -> Optional[Dict[str, Any]]:
    """Normalize device schedules into a dictionary."""
    parsed = parse_json_object(raw)
    if parsed is None:
        return None
    if not isinstance(parsed, dict):
        return None
    return dict(parsed)


def dump_json_field(value: Any) -> Optional[str]:
    """Safely serialize structured fields to JSON strings for storage."""
    if value is None:
        return None
    try:
        return json.dumps(value)
    except TypeError:
        logger.warning("Unable to serialize structured field to JSON: %s", value)
        return None
