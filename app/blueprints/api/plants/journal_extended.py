"""
Plant Journal Extended Endpoints
=================================

Extended journal operations:
- Type-specific entry creation (watering, pruning, transplant, env-adjustment)
- Entry update and deletion
- Journal summary and analytics
- Paginated journal retrieval
- Stage extension
- Unified plant detail endpoint

These endpoints complement journal.py with full CRUD and analytics.
"""

from __future__ import annotations

import logging
from contextlib import suppress
from datetime import date

from flask import Response, request

from app.blueprints.api._common import (
    fail as _fail,
    get_container,
    get_plant_journal_service as _journal_service,
    get_plant_service as _plant_service,
    get_user_id,
    success as _success,
)
from app.schemas.plants import (
    EnvironmentalAdjustmentRequest,
    PruningEntryRequest,
    StageExtensionRequest,
    TransplantEntryRequest,
    UpdateJournalEntryRequest,
    WateringEntryRequest,
)
from app.utils.http import safe_error, safe_route

from . import plants_api

logger = logging.getLogger("plants_api.journal_extended")


# ============================================================================
# TYPE-SPECIFIC JOURNAL ENTRIES
# ============================================================================


@plants_api.post("/plants/<int:plant_id>/journal/watering")
@safe_route("Failed to record watering")
def add_watering_entry(plant_id: int) -> Response:
    """Record a watering event for a plant."""
    payload = request.get_json(silent=True) or {}
    schema = WateringEntryRequest(**payload)

    plant_service = _plant_service()
    plant = plant_service.get_plant(plant_id)
    if not plant:
        return _fail(f"Plant {plant_id} not found", 404)

    unit_id = plant.get("unit_id") if isinstance(plant, dict) else getattr(plant, "unit_id", None)
    user_id = get_user_id()

    entry_id = _journal_service().record_watering(
        plant_id=plant_id,
        unit_id=unit_id,
        amount_ml=schema.amount_ml,
        method=schema.method.value,
        source=schema.source.value,
        ph_level=schema.ph_level,
        ec_level=schema.ec_level,
        notes=schema.notes,
        user_id=user_id,
    )

    if not entry_id:
        return _fail("Failed to record watering", 500)

    return _success({"entry_id": entry_id, "message": "Watering recorded"}, 201)


@plants_api.post("/plants/<int:plant_id>/journal/pruning")
@safe_route("Failed to record pruning")
def add_pruning_entry(plant_id: int) -> Response:
    """Record a pruning event for a plant."""
    payload = request.get_json(silent=True) or {}
    schema = PruningEntryRequest(**payload)

    plant_service = _plant_service()
    plant = plant_service.get_plant(plant_id)
    if not plant:
        return _fail(f"Plant {plant_id} not found", 404)

    user_id = get_user_id()

    entry_id = _journal_service().record_pruning(
        plant_id=plant_id,
        pruning_type=schema.pruning_type,
        parts_removed=schema.parts_pruned,
        notes=schema.notes,
        user_id=user_id,
    )

    if not entry_id:
        return _fail("Failed to record pruning", 500)

    return _success({"entry_id": entry_id, "message": "Pruning recorded"}, 201)


@plants_api.post("/plants/<int:plant_id>/journal/transplant")
@safe_route("Failed to record transplant")
def add_transplant_entry(plant_id: int) -> Response:
    """Record a transplant event for a plant."""
    payload = request.get_json(silent=True) or {}
    schema = TransplantEntryRequest(**payload)

    plant_service = _plant_service()
    plant = plant_service.get_plant(plant_id)
    if not plant:
        return _fail(f"Plant {plant_id} not found", 404)

    user_id = get_user_id()

    entry_id = _journal_service().record_transplant(
        plant_id=plant_id,
        from_container=schema.from_container,
        to_container=schema.to_container,
        new_medium=schema.new_soil_mix,
        notes=schema.notes,
        user_id=user_id,
    )

    if not entry_id:
        return _fail("Failed to record transplant", 500)

    return _success({"entry_id": entry_id, "message": "Transplant recorded"}, 201)


@plants_api.post("/plants/<int:plant_id>/journal/environmental-adjustment")
@safe_route("Failed to record environmental adjustment")
def add_environmental_adjustment_entry(plant_id: int) -> Response:
    """Record an environmental adjustment for a plant."""
    payload = request.get_json(silent=True) or {}
    schema = EnvironmentalAdjustmentRequest(**payload)

    plant_service = _plant_service()
    plant = plant_service.get_plant(plant_id)
    if not plant:
        return _fail(f"Plant {plant_id} not found", 404)

    user_id = get_user_id()

    entry_id = _journal_service().record_environmental_adjustment(
        plant_id=plant_id,
        adjustment_type=schema.parameter,
        old_value=schema.old_value,
        new_value=schema.new_value,
        reason=schema.reason or schema.notes,
        user_id=user_id,
    )

    if not entry_id:
        return _fail("Failed to record environmental adjustment", 500)

    return _success({"entry_id": entry_id, "message": "Environmental adjustment recorded"}, 201)


# ============================================================================
# ENTRY UPDATE / DELETE
# ============================================================================


@plants_api.put("/plants/<int:plant_id>/journal/<int:entry_id>")
@safe_route("Failed to update journal entry")
def update_journal_entry(plant_id: int, entry_id: int) -> Response:
    """Update an existing journal entry."""
    payload = request.get_json(silent=True) or {}
    schema = UpdateJournalEntryRequest(**payload)

    journal = _journal_service()

    # Verify entry belongs to this plant
    entry = journal.repo.get_entry_by_id(entry_id)
    if not entry:
        return _fail("Entry not found", 404)
    if entry.get("plant_id") != plant_id:
        return _fail("Entry does not belong to this plant", 403)

    updates = {k: v for k, v in schema.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return _fail("No updates provided", 400)

    success = journal.update_entry(entry_id, updates)
    if not success:
        return _fail("Failed to update entry", 500)

    return _success({"entry_id": entry_id, "message": "Entry updated"})


@plants_api.delete("/plants/<int:plant_id>/journal/<int:entry_id>")
@safe_route("Failed to delete journal entry")
def delete_journal_entry(plant_id: int, entry_id: int) -> Response:
    """Delete a journal entry."""
    journal = _journal_service()

    # Verify entry belongs to this plant
    entry = journal.repo.get_entry_by_id(entry_id)
    if not entry:
        return _fail("Entry not found", 404)
    if entry.get("plant_id") != plant_id:
        return _fail("Entry does not belong to this plant", 403)

    success = journal.delete_entry(entry_id)
    if not success:
        return _fail("Failed to delete entry", 500)

    return _success({"entry_id": entry_id, "message": "Entry deleted"})


# ============================================================================
# JOURNAL RETRIEVAL & ANALYTICS
# ============================================================================


@plants_api.get("/plants/<int:plant_id>/journal/entries")
@safe_route("Failed to get journal entries")
def get_journal_paginated(plant_id: int) -> Response:
    """
    Get paginated journal entries for a plant.

    Query params:
        page: Page number (default 1)
        per_page: Items per page (default 20, max 100)
        type: Filter by entry_type (optional)
    """
    page = request.args.get("page", 1, type=int)
    per_page = min(request.args.get("per_page", 20, type=int), 100)
    entry_type = request.args.get("type")

    result = _journal_service().repo.get_entries_paginated(
        plant_id=plant_id,
        page=page,
        per_page=per_page,
        entry_type=entry_type,
    )

    return _success(result)


@plants_api.get("/plants/<int:plant_id>/journal/summary")
@safe_route("Failed to get journal summary")
def get_journal_summary(plant_id: int) -> Response:
    """Get aggregated journal summary for a plant."""
    summary = _journal_service().repo.get_journal_summary(plant_id)

    # Include stage timeline
    summary["stage_changes"] = _journal_service().repo.get_stage_timeline(plant_id)

    return _success(summary)


@plants_api.get("/plants/<int:plant_id>/journal/watering-history")
@safe_route("Failed to get watering history")
def get_watering_history(plant_id: int) -> Response:
    """Get watering history for a plant."""
    days = request.args.get("days", 90, type=int)
    entries = _journal_service().repo.get_watering_history(plant_id, days=days)
    frequency = _journal_service().repo.get_watering_frequency(plant_id, days=days)

    return _success(
        {
            "plant_id": plant_id,
            "entries": entries,
            "frequency": frequency,
            "count": len(entries),
        }
    )


@plants_api.get("/plants/<int:plant_id>/journal/stage-timeline")
@safe_route("Failed to get stage timeline")
def get_stage_timeline(plant_id: int) -> Response:
    """Get stage change timeline for a plant."""
    timeline = _journal_service().repo.get_stage_timeline(plant_id)

    return _success(
        {
            "plant_id": plant_id,
            "timeline": timeline,
            "count": len(timeline),
        }
    )


# ============================================================================
# STAGE EXTENSION
# ============================================================================


@plants_api.post("/plants/<int:plant_id>/stage/extend")
@safe_route("Failed to extend plant stage")
def extend_plant_stage(plant_id: int) -> Response:
    """
    Extend the current growth stage by days or until a date (max 5 days).

    Body:
        extend_days: int (1-5) OR
        extend_until: ISO date string (max 5 days ahead)
        reason: str (optional)
    """
    try:
        payload = request.get_json(silent=True) or {}
        schema = StageExtensionRequest(**payload)

        if schema.extend_days is None and schema.extend_until is None:
            return _fail("Provide either extend_days or extend_until", 400)

        plant_service = _plant_service()
        plant = plant_service.get_plant(plant_id)
        if not plant:
            return _fail(f"Plant {plant_id} not found", 404)

        # Resolve days
        extend_days = schema.extend_days
        if schema.extend_until is not None:
            today = date.today()
            delta = (schema.extend_until - today).days
            if delta < 1:
                return _fail("extend_until must be in the future", 400)
            if delta > 5:
                return _fail("Cannot extend more than 5 days", 400)
            extend_days = delta

        if extend_days is None or extend_days < 1 or extend_days > 5:
            return _fail("Extension must be between 1 and 5 days", 400)

        # Get stage manager via plant_service
        stage_manager = plant_service._stage_manager

        result = stage_manager.extend_stage(
            plant_id=plant_id,
            plant=plant,
            extend_days=extend_days,
            reason=schema.reason,
        )

        if not result:
            return _fail("Failed to extend stage", 500)

        return _success(result)

    except ValueError as e:
        return safe_error(e, 400)


# ============================================================================
# UNIFIED PLANT DETAIL ENDPOINT
# ============================================================================


@plants_api.get("/plants/<int:plant_id>/detail")
@safe_route("Failed to get plant detail")
def get_plant_detail_unified(plant_id: int) -> Response:
    """
    Unified plant detail endpoint.

    Returns plant info, journal summary, linked devices, latest health,
    and ML predictions in a single response.
    """
    plant_service = _plant_service()
    plant = plant_service.get_plant(plant_id)
    if not plant:
        return _fail(f"Plant {plant_id} not found", 404)

    plant_dict = plant.to_dict() if hasattr(plant, "to_dict") else (plant if isinstance(plant, dict) else {})
    unit_id = plant_dict.get("unit_id")

    # Journal summary
    journal = _journal_service()
    journal_summary = journal.repo.get_journal_summary(plant_id)
    journal_summary["stage_changes"] = journal.repo.get_stage_timeline(plant_id)

    # Recent journal entries (first page)
    recent_entries = journal.repo.get_entries_paginated(plant_id, page=1, per_page=5)

    # Watering frequency
    watering_freq = journal.repo.get_watering_frequency(plant_id, days=30)

    # Linked devices
    linked_sensors = []
    linked_actuators = []
    with suppress(Exception):
        linked_sensors = plant_service.get_linked_sensors(plant_id) or []
    with suppress(Exception):
        linked_actuators = plant_service.get_linked_actuators(plant_id) or []

    # Active plant info
    is_active = False
    try:
        active = plant_service.get_active_plant(unit_id)
        if active and (
            getattr(active, "plant_id", None) == plant_id
            or (isinstance(active, dict) and active.get("plant_id") == plant_id)
        ):
            is_active = True
    except Exception:
        pass

    # Stage change impact (if active)
    stage_info = {
        "current_stage": plant_dict.get("current_stage"),
        "days_in_stage": plant_dict.get("days_in_stage", 0),
        "is_active_plant": is_active,
    }

    # ML predictions (best effort)
    predictions = {}
    try:
        container = get_container()
        if hasattr(container, "personalized_learning") and container.personalized_learning:
            predictions = container.personalized_learning.get_personalized_recommendations(
                unit_id=unit_id,
                plant_type=plant_dict.get("plant_type", ""),
                growth_stage=plant_dict.get("current_stage", ""),
                current_conditions={},
            )
    except Exception:
        pass

    return _success(
        {
            "plant": plant_dict,
            "journal_summary": journal_summary,
            "recent_entries": recent_entries.get("items", []),
            "watering_frequency": watering_freq,
            "linked_sensors": linked_sensors if isinstance(linked_sensors, list) else [],
            "linked_actuators": linked_actuators if isinstance(linked_actuators, list) else [],
            "stage_info": stage_info,
            "predictions": predictions,
        }
    )
