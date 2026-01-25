"""
Input Validation Utilities
==========================

Centralized input validation and sanitization for security and data integrity.

Features:
- Input sanitization (XSS prevention)
- Common validators for frequent data types
- Request validation decorator
- Safe SQL parameter handling
"""
import re
import html
import logging
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, Union
from flask import request, jsonify
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


# =============================================================================
# Input Sanitization
# =============================================================================

def sanitize_string(value: Optional[str], max_length: int = 1000) -> Optional[str]:
    """
    Sanitize a string input to prevent XSS and limit length.

    - Escapes HTML entities
    - Strips leading/trailing whitespace
    - Limits length
    - Returns None for empty strings

    Args:
        value: Input string
        max_length: Maximum allowed length

    Returns:
        Sanitized string or None
    """
    if value is None:
        return None

    if not isinstance(value, str):
        value = str(value)

    # Strip whitespace
    value = value.strip()

    # Return None for empty
    if not value:
        return None

    # Escape HTML to prevent XSS
    value = html.escape(value, quote=True)

    # Limit length
    if len(value) > max_length:
        value = value[:max_length]

    return value


def sanitize_dict(
    data: Dict[str, Any],
    string_max_length: int = 1000,
    recursive: bool = True,
) -> Dict[str, Any]:
    """
    Sanitize all string values in a dictionary.

    Args:
        data: Dictionary to sanitize
        string_max_length: Max length for string values
        recursive: Process nested dicts/lists

    Returns:
        Sanitized dictionary
    """
    result = {}

    for key, value in data.items():
        # Sanitize key too
        safe_key = sanitize_string(key, max_length=100) or key

        if isinstance(value, str):
            result[safe_key] = sanitize_string(value, string_max_length)
        elif recursive and isinstance(value, dict):
            result[safe_key] = sanitize_dict(value, string_max_length, recursive)
        elif recursive and isinstance(value, list):
            result[safe_key] = [
                sanitize_dict(item, string_max_length, recursive)
                if isinstance(item, dict)
                else sanitize_string(item, string_max_length)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            result[safe_key] = value

    return result


# =============================================================================
# Common Validators
# =============================================================================

def validate_id(value: Any, name: str = "id") -> int:
    """
    Validate that a value is a positive integer ID.

    Args:
        value: Value to validate
        name: Field name for error messages

    Returns:
        Validated integer

    Raises:
        ValueError: If validation fails
    """
    if value is None:
        raise ValueError(f"{name} is required")

    try:
        id_val = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a valid integer")

    if id_val < 1:
        raise ValueError(f"{name} must be a positive integer")

    return id_val


def validate_pagination(
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    default_limit: int = 50,
    max_limit: int = 500,
) -> tuple:
    """
    Validate and normalize pagination parameters.

    Args:
        limit: Requested limit
        offset: Requested offset
        default_limit: Default if not specified
        max_limit: Maximum allowed limit

    Returns:
        Tuple of (validated_limit, validated_offset)
    """
    # Validate limit
    if limit is None:
        limit = default_limit
    else:
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = default_limit

    limit = max(1, min(limit, max_limit))

    # Validate offset
    if offset is None:
        offset = 0
    else:
        try:
            offset = int(offset)
        except (TypeError, ValueError):
            offset = 0

    offset = max(0, offset)

    return limit, offset


def validate_date_string(value: Optional[str], name: str = "date") -> Optional[str]:
    """
    Validate an ISO date string (YYYY-MM-DD).

    Args:
        value: Date string to validate
        name: Field name for error messages

    Returns:
        Validated date string or None

    Raises:
        ValueError: If format is invalid
    """
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None

    # Validate format
    pattern = r"^\d{4}-\d{2}-\d{2}$"
    if not re.match(pattern, value):
        raise ValueError(f"{name} must be in YYYY-MM-DD format")

    # Validate components
    try:
        from datetime import datetime
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"{name} is not a valid date")

    return value


def validate_datetime_string(value: Optional[str], name: str = "datetime") -> Optional[str]:
    """
    Validate an ISO datetime string.

    Accepts formats:
    - YYYY-MM-DD
    - YYYY-MM-DDTHH:MM:SS
    - YYYY-MM-DDTHH:MM:SSZ
    - YYYY-MM-DD HH:MM:SS

    Args:
        value: Datetime string to validate
        name: Field name for error messages

    Returns:
        Validated datetime string or None

    Raises:
        ValueError: If format is invalid
    """
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None

    from datetime import datetime

    # Try multiple formats
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ]

    for fmt in formats:
        try:
            datetime.strptime(value.replace("Z", ""), fmt.replace("Z", ""))
            return value
        except ValueError:
            continue

    raise ValueError(f"{name} must be a valid ISO datetime format")


def validate_enum_value(
    value: Any,
    allowed_values: List[str],
    name: str = "value",
    case_sensitive: bool = False,
) -> str:
    """
    Validate that a value is one of the allowed values.

    Args:
        value: Value to validate
        allowed_values: List of allowed values
        name: Field name for error messages
        case_sensitive: Whether comparison is case-sensitive

    Returns:
        Validated value

    Raises:
        ValueError: If validation fails
    """
    if value is None:
        raise ValueError(f"{name} is required")

    value = str(value).strip()

    if case_sensitive:
        if value not in allowed_values:
            raise ValueError(f"{name} must be one of: {', '.join(allowed_values)}")
        return value
    else:
        value_lower = value.lower()
        for allowed in allowed_values:
            if allowed.lower() == value_lower:
                return allowed
        raise ValueError(f"{name} must be one of: {', '.join(allowed_values)}")


def validate_number_range(
    value: Any,
    min_val: Optional[float] = None,
    max_val: Optional[float] = None,
    name: str = "value",
    allow_none: bool = False,
) -> Optional[float]:
    """
    Validate that a number is within a specified range.

    Args:
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        name: Field name for error messages
        allow_none: Whether None is allowed

    Returns:
        Validated number

    Raises:
        ValueError: If validation fails
    """
    if value is None:
        if allow_none:
            return None
        raise ValueError(f"{name} is required")

    try:
        num = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a valid number")

    if min_val is not None and num < min_val:
        raise ValueError(f"{name} must be at least {min_val}")

    if max_val is not None and num > max_val:
        raise ValueError(f"{name} must be at most {max_val}")

    return num


# =============================================================================
# Request Validation Decorator
# =============================================================================

def validate_request(
    schema: Optional[Type[BaseModel]] = None,
    sanitize: bool = True,
    required_params: Optional[List[str]] = None,
) -> Callable:
    """
    Decorator for validating and sanitizing request data.

    Usage:
        @app.route('/api/plants', methods=['POST'])
        @validate_request(schema=CreatePlantRequest, sanitize=True)
        def create_plant(validated_data):
            # validated_data is the validated Pydantic model or sanitized dict
            ...

    Args:
        schema: Optional Pydantic schema for validation
        sanitize: Whether to sanitize string inputs
        required_params: List of required query parameters

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Get request data
                if request.method in ('POST', 'PUT', 'PATCH'):
                    data = request.get_json(silent=True) or {}
                else:
                    data = dict(request.args)

                # Sanitize if enabled
                if sanitize and isinstance(data, dict):
                    data = sanitize_dict(data)

                # Check required params
                if required_params:
                    missing = [p for p in required_params if p not in data or data[p] is None]
                    if missing:
                        return jsonify({
                            'ok': False,
                            'data': None,
                            'error': {'message': f"Missing required parameters: {', '.join(missing)}"}
                        }), 400

                # Validate with schema if provided
                if schema:
                    try:
                        validated = schema(**data)
                        kwargs['validated_data'] = validated
                    except ValidationError as e:
                        return jsonify({
                            'ok': False,
                            'data': None,
                            'error': {
                                'message': 'Validation failed',
                                'details': e.errors()
                            }
                        }), 400
                else:
                    kwargs['validated_data'] = data

                return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Request validation error: {e}")
                return jsonify({
                    'ok': False,
                    'data': None,
                    'error': {'message': 'Invalid request'}
                }), 400

        return wrapper
    return decorator


# =============================================================================
# SQL Parameter Safety
# =============================================================================

def safe_like_pattern(value: str) -> str:
    """
    Escape special characters for SQL LIKE patterns.

    Prevents SQL injection in LIKE queries.

    Args:
        value: Search term

    Returns:
        Escaped pattern safe for LIKE
    """
    # Escape SQL LIKE wildcards
    value = value.replace("\\", "\\\\")
    value = value.replace("%", "\\%")
    value = value.replace("_", "\\_")
    return value


def validate_sort_column(
    column: str,
    allowed_columns: List[str],
    default: str = "id",
) -> str:
    """
    Validate that a sort column is in the allowed list.

    Prevents SQL injection in ORDER BY clauses.

    Args:
        column: Requested column name
        allowed_columns: List of allowed column names
        default: Default column if invalid

    Returns:
        Safe column name
    """
    if not column:
        return default

    column = str(column).strip().lower()

    for allowed in allowed_columns:
        if allowed.lower() == column:
            return allowed

    return default


def validate_sort_direction(direction: Optional[str]) -> str:
    """
    Validate sort direction.

    Args:
        direction: Requested direction (asc/desc)

    Returns:
        Safe direction string ('ASC' or 'DESC')
    """
    if not direction:
        return "ASC"

    direction = str(direction).strip().upper()
    return "DESC" if direction == "DESC" else "ASC"
