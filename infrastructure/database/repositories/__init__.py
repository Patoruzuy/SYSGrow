"""Repository facades exposing typed accessors over low-level mixins.

Base protocols are available for type-checking and dependency injection::

    from infrastructure.database.repositories.base import BaseRepository
"""

from infrastructure.database.repositories.base import (
    BaseRepository,
    CrudRepository,
    ReadRepository,
    WriteRepository,
)

__all__ = [
    "BaseRepository",
    "CrudRepository",
    "ReadRepository",
    "WriteRepository",
]
