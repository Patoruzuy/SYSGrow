"""
Base Repository Protocol
========================

Defines the minimal contract that all SYSGrow repositories implement.
Uses ``typing.Protocol`` (structural subtyping) so existing repository
classes satisfy the contract **without any inheritance change** — they
only need to expose the required attribute.

Establish a shared repository interface so the
persistence layer can be swapped (e.g. SQLite → PostgreSQL) without
touching service code.

Usage in service type hints::

    from infrastructure.database.repositories.base import BaseRepository


    class MyService:
        def __init__(self, repo: BaseRepository) -> None: ...

For domain-specific contracts, combine with tighter Protocols::

    class PlantRepo(BaseRepository, Protocol):
        def get_plant(self, plant_id: int) -> dict | None: ...
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BaseRepository(Protocol):
    """Minimal contract shared by every SYSGrow repository.

    Every repository must expose a ``_backend`` **or** ``_db`` attribute
    (the underlying database handle).  This Protocol checks for neither
    attribute name specifically — it only asserts structural compatibility
    at the type-checking level.

    Concrete repositories should satisfy this protocol automatically via
    structural subtyping (duck typing).  No code changes are needed in
    existing repositories unless they want explicit ``BaseRepository``
    type annotations.
    """

    # We intentionally keep this empty of method signatures because the
    # 17 repositories share **no** common CRUD naming (create vs insert,
    # get vs fetch, list vs get_all, etc.).  Forcing artificial method
    # names would break the codebase.  Instead, this Protocol serves as:
    #
    # 1. A type marker for dependency injection
    # 2. A documentation anchor for the repository layer contract
    # 3. A future extension point — add shared methods here as naming
    #    conventions converge across repositories
    #
    # Domain-specific protocols (like ScheduleRepository in
    # app/domain/schedules/repository.py) remain the correct place for
    # detailed CRUD contracts per aggregate.


@runtime_checkable
class ReadRepository(Protocol):
    """Repository that supports reading a single record by ID."""

    def get(self, record_id: int) -> dict[str, Any] | None:
        """Retrieve a record by its primary key.

        Returns ``None`` when the record does not exist.
        """
        ...


@runtime_checkable
class WriteRepository(Protocol):
    """Repository that supports creating a record."""

    def create(self, **kwargs: Any) -> int | None:
        """Persist a new record and return its generated ID.

        Returns ``None`` on failure.
        """
        ...


@runtime_checkable
class CrudRepository(ReadRepository, WriteRepository, Protocol):
    """Convenience union of Read + Write protocols.

    Repositories that implement both ``get(record_id)`` and
    ``create(**kwargs)`` satisfy this protocol automatically.
    """


__all__ = [
    "BaseRepository",
    "CrudRepository",
    "ReadRepository",
    "WriteRepository",
]
