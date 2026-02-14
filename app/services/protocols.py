"""
Service protocols (structural typing interfaces).

Protocols let consumer services declare the *minimal* surface they depend on
without importing the concrete class, breaking circular imports and making
tests trivially mockable.

Usage
-----
In a consumer service::

    from __future__ import annotations
    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from app.services.protocols import PlantStateReader

    class GrowthService:
        def __init__(self, plant_service: "PlantStateReader", ...): ...

At runtime the concrete ``PlantViewService`` already satisfies the protocol
via structural subtyping — no explicit inheritance needed.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any

from typing import Protocol, runtime_checkable

from app.domain.plant import PlantProfile


@runtime_checkable
class PlantStateReader(Protocol):
    """Read-only view over the plant catalogue.

    Any object that implements these methods can be used wherever a
    ``PlantStateReader`` is expected.  ``PlantViewService`` satisfies this
    protocol implicitly.
    """

    def get_plant(
        self, plant_id: int, unit_id: Optional[int] = None
    ) -> Optional[PlantProfile]:
        """Return a single plant profile, or ``None`` if not found."""
        ...

    def get_active_plant(self, unit_id: int) -> Optional[PlantProfile]:
        """Return the currently active plant for a unit."""
        ...

    def list_plants(self, unit_id: int) -> List[PlantProfile]:
        """Return all plants belonging to a unit."""
        ...

    def get_plant_as_dict(
        self, plant_id: int, unit_id: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Return a plant profile serialized as a plain dict."""
        ...

    def list_plants_as_dicts(self, unit_id: int) -> List[Dict[str, Any]]:
        """Return all plants belonging to a unit as plain dicts."""
        ...
