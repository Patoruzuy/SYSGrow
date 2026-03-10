"""
Database Pagination Utilities
==============================
Helper functions for consistent pagination across repositories.

Enforces Raspberry Pi-friendly pagination:
- Default limit: 100 (balances memory and usability)
- Maximum limit: 500 (prevents Pi memory issues)
- Minimum limit: 1
- Minimum offset: 0

Author: SYSGrow Team
Date: December 2025
"""

from dataclasses import dataclass
from typing import Any

# Pagination Constants (Pi-friendly defaults)
DEFAULT_LIMIT = 100
MAX_LIMIT = 500
MIN_LIMIT = 1
MIN_OFFSET = 0


@dataclass
class PaginationParams:
    """Validated pagination parameters."""

    limit: int
    offset: int

    @classmethod
    def from_request(
        cls,
        limit: int | None = None,
        offset: int | None = None,
    ) -> "PaginationParams":
        """
        Create validated pagination parameters from request inputs.

        Args:
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0, min: 0)

        Returns:
            PaginationParams with validated values

        Raises:
            ValueError: If limit or offset are out of valid ranges
        """
        # Validate and set limit
        if limit is None:
            validated_limit = DEFAULT_LIMIT
        else:
            if limit < MIN_LIMIT:
                raise ValueError(f"Limit must be at least {MIN_LIMIT}")
            if limit > MAX_LIMIT:
                raise ValueError(f"Limit cannot exceed {MAX_LIMIT} (Pi memory constraint)")
            validated_limit = limit

        # Validate and set offset
        if offset is None:
            validated_offset = MIN_OFFSET
        else:
            if offset < MIN_OFFSET:
                raise ValueError(f"Offset must be at least {MIN_OFFSET}")
            validated_offset = offset

        return cls(limit=validated_limit, offset=validated_offset)

    def to_sql_clause(self) -> str:
        """
        Generate SQL LIMIT/OFFSET clause.

        Returns:
            SQL clause string (e.g., "LIMIT 100 OFFSET 0")
        """
        return f"LIMIT {self.limit} OFFSET {self.offset}"


@dataclass
class PaginatedResponse:
    """Standard paginated response structure."""

    items: list[Any]
    total: int
    limit: int
    offset: int

    @property
    def has_next(self) -> bool:
        """Check if there are more results after current page."""
        return (self.offset + self.limit) < self.total

    @property
    def has_prev(self) -> bool:
        """Check if there are results before current page."""
        return self.offset > 0

    @property
    def page_count(self) -> int:
        """Calculate total number of pages."""
        if self.limit == 0:
            return 0
        return (self.total + self.limit - 1) // self.limit  # Ceiling division

    @property
    def current_page(self) -> int:
        """Calculate current page number (1-indexed)."""
        if self.limit == 0:
            return 0
        return (self.offset // self.limit) + 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON responses."""
        return {
            "items": self.items,
            "pagination": {
                "total": self.total,
                "limit": self.limit,
                "offset": self.offset,
                "has_next": self.has_next,
                "has_prev": self.has_prev,
                "page_count": self.page_count,
                "current_page": self.current_page,
            },
        }


def validate_pagination(
    limit: int | None = None,
    offset: int | None = None,
) -> tuple[int, int]:
    """
    Validate pagination parameters (convenience function).

    Args:
        limit: Number of results per page
        offset: Number of results to skip

    Returns:
        Tuple of (validated_limit, validated_offset)

    Raises:
        ValueError: If parameters are invalid
    """
    params = PaginationParams.from_request(limit=limit, offset=offset)
    return params.limit, params.offset


def apply_pagination_to_query(
    query: str,
    limit: int | None = None,
    offset: int | None = None,
) -> tuple[str, int, int]:
    """
    Add LIMIT/OFFSET clause to SQL query.

    Args:
        query: Base SQL query (should not already have LIMIT/OFFSET)
        limit: Number of results per page
        offset: Number of results to skip

    Returns:
        Tuple of (query_with_pagination, validated_limit, validated_offset)

    Raises:
        ValueError: If parameters are invalid

    Example:
        >>> query = "SELECT * FROM Sensors WHERE unit_id = ?"
        >>> paginated_query, limit, offset = apply_pagination_to_query(query, 50, 100)
        >>> print(paginated_query)
        SELECT * FROM Sensors WHERE unit_id = ? LIMIT 50 OFFSET 100
    """
    params = PaginationParams.from_request(limit=limit, offset=offset)
    paginated_query = f"{query.rstrip(';')} {params.to_sql_clause()}"
    return paginated_query, params.limit, params.offset
