"""
Growth Units CRUD Operations
============================

Endpoints for creating, reading, updating, and deleting growth units.
Also includes plant management endpoints that operate on units.
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Response, request
from pydantic import ValidationError

from app.blueprints.api._common import (
    fail as _fail,
    get_container as _container,
    get_growth_service as _service,
    get_scheduling_service as _scheduling_service,
    get_user_id,
    success as _success,
)
from app.enums.common import ConditionProfileMode, ConditionProfileTarget
from app.schemas.growth import (
    CreateGrowthUnitRequest,
    CreateUnitPayload,
    GrowthUnitResponse,
    ScheduleCreateSchema,
    UpdateGrowthUnitRequest,
    UpdateUnitPayload,
)
from app.security.auth import api_login_required
from app.utils.http import safe_error, safe_route
from infrastructure.utils.structured_fields import normalize_device_schedules, normalize_dimensions

from . import growth_api

logger = logging.getLogger("growth_api.units")


def _unit_to_response(unit: dict[str, Any]) -> GrowthUnitResponse:
    thresholds = {
        "temperature": unit.get("temperature_threshold"),
        "humidity": unit.get("humidity_threshold"),
        "co2": unit.get("co2_threshold"),
        "voc": unit.get("voc_threshold"),
        "lux": unit.get("lux_threshold"),
        "aqi": unit.get("aqi_threshold"),
    }

    return GrowthUnitResponse(
        id=unit.get("unit_id"),
        name=unit.get("name"),
        location=str(unit.get("location") or "Unknown"),
        description=unit.get("description"),
        area_size=unit.get("area_size"),
        active=bool(unit.get("active", True)),
        user_id=unit.get("user_id", 1),
        timezone=unit.get("timezone"),
        thresholds=thresholds,
        plant_count=int(unit.get("plant_count", 0)),
        device_count=int(unit.get("device_count", 0)),
        camera_enabled=bool(unit.get("camera_enabled", False)),
        camera_active=bool(unit.get("camera_active", False)),
        created_at=unit.get("created_at"),
        updated_at=unit.get("updated_at"),
    )


def _apply_condition_profile_to_unit(
    *,
    unit_id: int,
    user_id: int,
    profile_id: str | None,
    mode: ConditionProfileMode | None,
    name: str | None,
) -> dict[str, Any] | None:
    if not profile_id:
        return None
    container = _container()
    if not container:
        return None
    profile_service = getattr(container, "personalized_learning", None)
    threshold_service = getattr(container, "threshold_service", None)
    if not profile_service or not threshold_service:
        return None

    profile = profile_service.get_condition_profile_by_id(user_id=user_id, profile_id=profile_id)
    if not profile:
        raise ValueError("Condition profile not found")

    desired_mode = mode
    if desired_mode and not isinstance(desired_mode, ConditionProfileMode):
        desired_mode = ConditionProfileMode(str(desired_mode))
    desired_mode = desired_mode or profile.mode
    if profile.mode == ConditionProfileMode.TEMPLATE and desired_mode == ConditionProfileMode.ACTIVE:
        cloned = profile_service.clone_condition_profile(
            user_id=user_id,
            source_profile_id=profile.profile_id,
            name=name,
            mode=ConditionProfileMode.ACTIVE,
        )
        if cloned:
            profile = cloned
            desired_mode = ConditionProfileMode.ACTIVE

    env_thresholds = profile.environment_thresholds or {}
    if env_thresholds:
        try:
            growth_service = _service()
            growth_service.update_unit_thresholds(unit_id, env_thresholds)
        except RuntimeError as exc:
            logger.info(
                "Growth service threshold update unavailable for unit %s; using ThresholdService fallback: %s",
                unit_id,
                exc,
            )
            threshold_service.update_unit_thresholds(unit_id, env_thresholds)

    profile_service.link_condition_profile(
        user_id=user_id,
        target_type=ConditionProfileTarget.UNIT,
        target_id=int(unit_id),
        profile_id=profile.profile_id,
        mode=desired_mode or ConditionProfileMode.ACTIVE,
    )

    return profile.to_dict()


def _create_unit_device_schedules(
    *,
    unit_id: int,
    user_id: int,
    device_schedules: dict[str, Any] | None,
) -> None:
    if not device_schedules:
        return
    try:
        sched_service = _scheduling_service()
    except RuntimeError as exc:
        logger.warning("Scheduling service unavailable for unit %s: %s", unit_id, exc)
        return

    for device_type, schedule_input in device_schedules.items():
        if schedule_input is None:
            continue
        schedule_data = schedule_input.model_dump() if hasattr(schedule_input, "model_dump") else dict(schedule_input)
        start_time = schedule_data.get("start_time")
        end_time = schedule_data.get("end_time")
        if not start_time or not end_time:
            logger.warning(
                "Skipping schedule for unit %s device %s: missing start_time/end_time",
                unit_id,
                device_type,
            )
            continue
        normalized_device_type = str(device_type).lower()
        schedule_type = "photoperiod" if normalized_device_type == "light" else "simple"
        try:
            payload = ScheduleCreateSchema(
                name=f"{str(device_type).title()} Schedule",
                device_type=normalized_device_type,
                schedule_type=schedule_type,
                start_time=start_time,
                end_time=end_time,
                enabled=bool(schedule_data.get("enabled", True)),
            )
        except ValidationError as exc:
            logger.warning("Skipping schedule for unit %s device %s: invalid payload (%s)", unit_id, device_type, exc)
            continue

        schedule = sched_service.build_schedule_from_payload(unit_id=unit_id, payload=payload)
        created = sched_service.create_schedule(
            schedule,
            check_conflicts=True,
            source="unit_create",
            user_id=user_id,
        )
        if not created:
            logger.warning("Failed to create schedule for unit %s device %s", unit_id, device_type)


# ============================================================================
# GROWTH UNIT CRUD OPERATIONS
# ============================================================================


@growth_api.get("/v2/units")
@safe_route("Failed to list growth units")
def list_units() -> Response:
    """
    Endpoint for listing growth units.

    Returns a list of GrowthUnitResponse models for the current user (when
    available) or all units when no user is in session.
    """
    logger.info("Listing growth units via endpoint")
    try:
        user_id = get_user_id()
        units = _service().list_units(user_id=user_id)

        # Enrich units with camera status
        camera_service = getattr(_container(), "camera_service", None)
        if camera_service:
            for unit in units:
                unit_id = unit.get("unit_id")
                if unit_id:
                    camera_settings = camera_service.load_camera_settings(unit_id)
                    unit["camera_enabled"] = camera_settings is not None
                    unit["camera_active"] = camera_service.is_camera_running(unit_id)

        typed_units: list[GrowthUnitResponse] = []
        for unit in units:
            typed_units.append(_unit_to_response(unit))

        # Pydantic models are JSON-serializable; wrap in standard envelope.
        return _success([u.model_dump() for u in typed_units])
    except RuntimeError as exc:
        logger.warning("Growth service unavailable while listing units: %s", exc)
        return safe_error(exc, 503, context="growth.units.list")


@growth_api.post("/v2/units")
@api_login_required
@safe_route("Failed to create growth unit")
def create_unit() -> Response:
    """
    Endpoint for creating a growth unit.

    Accepts CreateGrowthUnitRequest or CreateUnitPayload payloads.
    """
    try:
        raw = request.get_json() or {}
        location = raw.get("location") or "Indoor"
        payload_data = dict(raw)
        payload_data["location"] = location

        try:
            if "device_schedules" in payload_data:
                try:
                    typed = CreateUnitPayload(**payload_data)
                except ValidationError:
                    typed = CreateGrowthUnitRequest(**payload_data)
            else:
                try:
                    typed = CreateGrowthUnitRequest(**payload_data)
                except ValidationError:
                    typed = CreateUnitPayload(**payload_data)
        except ValidationError as ve:
            return _fail("Invalid growth unit payload", 400, details={"errors": ve.errors()})

        user_id = get_user_id()
        dimensions = None
        device_schedules = None

        if getattr(typed, "dimensions", None):
            dimensions = typed.dimensions.model_dump()
        if getattr(typed, "device_schedules", None):
            device_schedules = typed.device_schedules

        unit_id = _service().create_unit(
            name=typed.name,
            location=location,
            user_id=user_id,
            timezone=getattr(typed, "timezone", None),
            dimensions=dimensions,
            custom_image=getattr(typed, "custom_image", None),
            camera_enabled=getattr(typed, "camera_enabled", False),
        )

        if not unit_id:
            return _fail("Failed to create growth unit", 500)

        if device_schedules:
            _create_unit_device_schedules(
                unit_id=unit_id,
                user_id=user_id,
                device_schedules=device_schedules,
            )

        condition_profile = None
        try:
            condition_profile = _apply_condition_profile_to_unit(
                unit_id=unit_id,
                user_id=user_id,
                profile_id=getattr(typed, "condition_profile_id", None),
                mode=getattr(typed, "condition_profile_mode", None),
                name=getattr(typed, "condition_profile_name", None),
            )
        except ValueError as exc:
            return safe_error(exc, 400)

        created = _service().get_unit(unit_id)
        if not created:
            payload = {"unit_id": unit_id}
            if condition_profile:
                payload["condition_profile"] = condition_profile
            return _success(payload, status=201)

        payload = _unit_to_response(created).model_dump()
        if condition_profile:
            payload["condition_profile"] = condition_profile
        return _success(payload, status=201)
    except RuntimeError as exc:
        logger.warning("Growth service unavailable while creating unit: %s", exc)
        return safe_error(exc, 503, context="growth.units.create")


@growth_api.get("/units/<int:unit_id>")
@safe_route("Failed to get growth unit")
def get_unit(unit_id: int) -> Response:
    """Get a specific growth unit by ID"""
    logger.info("Getting growth unit %s", unit_id)
    try:
        unit = _service().get_unit(unit_id)

        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        return _success(unit)

    except RuntimeError as exc:
        logger.warning("Growth service unavailable while getting unit %s: %s", unit_id, exc)
        return safe_error(exc, 503, context="growth.units.get")


@growth_api.patch("/units/<int:unit_id>")
@api_login_required
@safe_route("Failed to update growth unit")
def update_unit(unit_id: int) -> Response:
    """Update an existing growth unit"""
    logger.info("Updating growth unit %s", unit_id)
    try:
        raw = request.get_json() or {}
        if not raw:
            return _fail("No update fields provided", 400)

        try:
            payload = UpdateUnitPayload(**raw)
        except ValidationError as ve:
            return _fail("Invalid update payload", 400, details={"errors": ve.errors()})

        current = _service().get_unit(unit_id)
        if not current:
            return _fail(f"Growth unit {unit_id} not found", 404)

        unit_kwargs = {
            "name": payload.name,
            "location": payload.location,
            "timezone": payload.timezone,
            "dimensions": payload.dimensions.model_dump() if payload.dimensions else None,
            "device_schedules": (
                {k: v.model_dump() for k, v in (payload.device_schedules or {}).items()}
                if payload.device_schedules
                else None
            ),
            "custom_image": payload.custom_image,
            "camera_enabled": payload.camera_enabled
            if payload.camera_enabled is not None
            else current.get("camera_enabled", False),
        }

        unit = _service().update_unit(unit_id, **unit_kwargs)

        if not unit:
            return _fail(f"Growth unit {unit_id} not found or update failed", 404)

        return _success({"message": "Growth unit updated successfully", "unit": unit})

    except ValueError as e:
        logger.warning("Validation error updating unit: %s", e)
        return safe_error(e, 400)
    except RuntimeError as exc:
        logger.warning("Growth service unavailable while updating unit %s: %s", unit_id, exc)
        return safe_error(exc, 503, context="growth.units.update")


@growth_api.delete("/units/<int:unit_id>")
@api_login_required
@safe_route("Failed to delete growth unit")
def delete_unit(unit_id: int) -> Response:
    """Delete a growth unit"""
    logger.info("Deleting growth unit %s", unit_id)
    try:
        if not _service().get_unit(unit_id):
            return _fail(f"Growth unit {unit_id} not found", 404)

        _service().delete_unit(unit_id)

        return _success({"message": "Growth unit removed successfully"})

    except RuntimeError as exc:
        logger.warning("Growth service unavailable while deleting unit %s: %s", unit_id, exc)
        return safe_error(exc, 503, context="growth.units.delete")


@growth_api.patch("/v2/units/<int:unit_id>")
@api_login_required
@safe_route("Failed to update growth unit")
def update_unit_v2(unit_id: int) -> Response:
    """Typed v2 endpoint for updating a growth unit."""
    logger.info("Updating growth unit %s via v2 endpoint", unit_id)
    try:
        raw = request.get_json() or {}
        try:
            payload = UpdateGrowthUnitRequest(**raw)
        except ValidationError as ve:
            return _fail("Invalid growth unit payload", 400, details={"errors": ve.errors()})

        current = _service().get_unit(unit_id)
        if not current:
            return _fail(f"Growth unit {unit_id} not found", 404)

        dimensions = normalize_dimensions(current.get("dimensions"))
        device_schedules = normalize_device_schedules(current.get("device_schedules"))

        # Determine light_mode: use payload value if provided, else keep current
        light_mode = current.get("light_mode") or current.get("settings", {}).get("light_mode", "schedule")
        if payload.light_mode is not None:
            light_mode = payload.light_mode.value

        unit = _service().update_unit(
            unit_id,
            name=payload.name or current.get("name"),
            location=str(payload.location.value if payload.location else current.get("location") or "Indoor"),
            dimensions=dimensions,
            device_schedules=device_schedules,
            custom_image=current.get("custom_image"),
            camera_enabled=current.get("camera_enabled", False),
            light_mode=light_mode,
            timezone=payload.timezone,
        )

        if payload.thresholds:
            raw_thresholds = payload.thresholds.model_dump(exclude_none=True)
            _service().update_unit_thresholds(
                unit_id,
                {
                    "temperature_threshold": raw_thresholds.get("max_temp", current.get("temperature_threshold")),
                    "humidity_threshold": raw_thresholds.get("max_humidity", current.get("humidity_threshold")),
                },
            )

        latest = _service().get_unit(unit_id) or unit
        return _success(_unit_to_response(latest or current).model_dump())
    except RuntimeError as exc:
        logger.warning("Growth service unavailable while updating unit v2 %s: %s", unit_id, exc)
        return safe_error(exc, 503, context="growth.units.update_v2")


@growth_api.delete("/v2/units/<int:unit_id>")
@api_login_required
@safe_route("Failed to delete growth unit")
def delete_unit_v2(unit_id: int) -> Response:
    """Typed v2 endpoint for deleting a growth unit."""
    logger.info("Deleting growth unit %s via v2 endpoint", unit_id)
    try:
        unit = _service().get_unit(unit_id)
        if not unit:
            return _fail(f"Growth unit {unit_id} not found", 404)

        _service().delete_unit(unit_id)
        return _success({"unit_id": unit_id, "message": "Growth unit deleted"})
    except RuntimeError as exc:
        logger.warning("Growth service unavailable while deleting unit v2 %s: %s", unit_id, exc)
        return safe_error(exc, 503, context="growth.units.delete_v2")
