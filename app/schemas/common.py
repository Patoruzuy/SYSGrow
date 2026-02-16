"""
Common Schemas
==============

Shared Pydantic models for API responses and common data structures.
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Standard success response format"""

    ok: bool = Field(default=True, description="Request success status")
    data: T = Field(..., description="Response data")
    error: str | None = Field(default=None, description="Error message (null on success)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ok": True,
                "data": {"id": 1, "name": "Example"},
                "error": None,
            }
        }
    )


class ErrorResponse(BaseModel):
    """Standard error response format"""

    ok: bool = Field(default=False, description="Request success status")
    data: Any | None = Field(default=None, description="Data (null on error)")
    error: str = Field(..., description="Error message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ok": False,
                "data": None,
                "error": "Invalid request parameters",
            }
        }
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response format"""

    ok: bool = Field(default=True, description="Request success status")
    data: list[T] = Field(..., description="Array of items")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    error: str | None = Field(default=None, description="Error message")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ok": True,
                "data": [{"id": 1}, {"id": 2}],
                "total": 100,
                "page": 1,
                "page_size": 10,
                "total_pages": 10,
                "error": None,
            }
        }
    )
