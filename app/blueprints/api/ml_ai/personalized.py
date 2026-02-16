"""
Personalized Learning API
=========================
Endpoints for managing user-specific AI learning and recommendations.
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

from flask import Blueprint, request

from app.blueprints.api._common import (
    fail as _fail,
    get_container as _container,
    get_user_id as _get_user_id,
    success as _success,
)

if TYPE_CHECKING:
    from app.services.ai.personalized_learning import PlantStageConditionProfile
from app.enums.common import (
    ConditionProfileMode,
    ConditionProfileTarget,
    ConditionProfileVisibility,
)
from app.schemas.personalized import (
    ConditionProfileCard,
    ConditionProfileLinkSummary,
    ConditionProfileSection,
    ConditionProfileSelectorResponse,
)

logger = logging.getLogger(__name__)

personalized_bp = Blueprint("ml_personalized", __name__, url_prefix="/api/ml/personalized")


def _get_personalized_service():
    """Get personalized learning service from container."""
    container = _container()
    if not container:
        return None
    return getattr(container, "personalized_learning", None)


def _parse_enum(enum_cls, value, field: str):
    if value is None:
        return None
    try:
        return enum_cls(value)
    except ValueError:
        raise ValueError(f"Invalid {field}")


def _coerce_mode(value) -> ConditionProfileMode | None:
    if value is None:
        return None
    try:
        return ConditionProfileMode(value)
    except ValueError:
        return None


def _coerce_visibility(value) -> ConditionProfileVisibility | None:
    if value is None:
        return None
    try:
        return ConditionProfileVisibility(value)
    except ValueError:
        return None


def _build_profile_card(
    profile_data,
    *,
    fallback_visibility: ConditionProfileVisibility | None = None,
) -> ConditionProfileCard:
    if hasattr(profile_data, "to_dict"):
        payload = profile_data.to_dict()
    else:
        payload = dict(profile_data or {})

    mode = _coerce_mode(payload.get("mode"))
    visibility = _coerce_visibility(payload.get("visibility"))
    if visibility is None and fallback_visibility is not None:
        visibility = fallback_visibility

    try:
        rating_avg = float(payload.get("rating_avg", 0.0) or 0.0)
    except (TypeError, ValueError):
        rating_avg = 0.0
    try:
        rating_count = int(payload.get("rating_count", 0) or 0)
    except (TypeError, ValueError):
        rating_count = 0

    return ConditionProfileCard(
        profile_id=str(payload.get("profile_id", "")),
        name=payload.get("name"),
        image_url=payload.get("image_url"),
        plant_type=str(payload.get("plant_type", "")),
        growth_stage=str(payload.get("growth_stage", "")),
        plant_variety=payload.get("plant_variety"),
        strain_variety=payload.get("strain_variety"),
        pot_size_liters=payload.get("pot_size_liters"),
        mode=mode,
        visibility=visibility,
        rating_avg=rating_avg,
        rating_count=rating_count,
        last_rating=payload.get("last_rating"),
        shared_token=payload.get("shared_token"),
        source_profile_id=payload.get("source_profile_id"),
        source_profile_name=payload.get("source_profile_name"),
        tags=list(payload.get("tags") or []),
        created_at=payload.get("created_at"),
        updated_at=payload.get("updated_at"),
    )


# ==============================================================================
# ENVIRONMENT PROFILES
# ==============================================================================


@personalized_bp.get("/profiles/<int:unit_id>")
def get_profile(unit_id: int):
    """
    Get environment profile for a unit.

    Returns:
        {
            "profile": {
                "user_id": int,
                "unit_id": int,
                "location_characteristics": {...},
                "equipment_profile": {...},
                "historical_patterns": {...},
                "success_factors": [...],
                "challenge_areas": [...]
            }
        }
    """
    try:
        service = _get_personalized_service()

        if not service:
            return _fail("Personalized learning service is not enabled", 503)

        profile = service.get_profile(unit_id)

        if not profile:
            return _fail(f"Profile for unit {unit_id} not found", 404)

        return _success({"profile": profile.to_dict()})

    except Exception as e:
        logger.error(f"Error getting profile for unit {unit_id}: {e}", exc_info=True)
        return safe_error(e, 500)


@personalized_bp.post("/profiles")
def create_profile():
    """
    Create a new environment profile.

    Request body:
        {
            "user_id": int,
            "unit_id": int,
            "location_info": {...} (optional),
            "equipment_info": {...} (optional)
        }

    Returns:
        {
            "profile": {...}
        }
    """
    try:
        service = _get_personalized_service()

        if not service:
            return _fail("Personalized learning service is not enabled", 503)

        data = request.get_json() or {}

        user_id = data.get("user_id")
        unit_id = data.get("unit_id")

        if user_id is None or unit_id is None:
            return _fail("user_id and unit_id are required", 400)

        profile = service.create_environment_profile(
            user_id=user_id,
            unit_id=unit_id,
            location_info=data.get("location_info"),
            equipment_info=data.get("equipment_info"),
        )

        return _success({"profile": profile.to_dict()}, 201)

    except Exception as e:
        logger.error(f"Error creating profile: {e}", exc_info=True)
        return safe_error(e, 500)


@personalized_bp.put("/profiles/<int:unit_id>")
def update_profile(unit_id: int):
    """
    Update an existing environment profile.

    Request body:
        {
            "location_characteristics": {...} (optional),
            "equipment_profile": {...} (optional),
            "success_factors": [...] (optional),
            "challenge_areas": [...] (optional)
        }

    Returns:
        {
            "updated": true,
            "profile": {...}
        }
    """
    try:
        service = _get_personalized_service()

        if not service:
            return _fail("Personalized learning service is not enabled", 503)

        data = request.get_json() or {}

        service.update_profile(unit_id, data)

        # Get updated profile
        profile = service.get_profile(unit_id)

        if not profile:
            return _fail(f"Profile for unit {unit_id} not found", 404)

        return _success({"updated": True, "profile": profile.to_dict()})

    except Exception as e:
        logger.error(f"Error updating profile for unit {unit_id}: {e}", exc_info=True)
        return safe_error(e, 500)


# ==============================================================================
# CONDITION PROFILES (Per-plant stage thresholds)
# ==============================================================================


@personalized_bp.get("/condition-profiles")
def get_condition_profile():
    """
    Get a per-user plant-stage condition profile.

    Query params:
        - user_id (required)
        - profile_id (optional)
        - plant_type (required if profile_id not provided)
        - growth_stage (required if profile_id not provided)
        - plant_variety (optional)
        - strain_variety (optional)
        - pot_size_liters (optional)
        - mode (optional): active or template
    """
    try:
        service = _get_personalized_service()
        if not service:
            return _fail("Personalized learning service is not enabled", 503)

        user_id = request.args.get("user_id", type=int)
        plant_type = request.args.get("plant_type")
        growth_stage = request.args.get("growth_stage")
        profile_id = request.args.get("profile_id")
        plant_variety = request.args.get("plant_variety")
        strain_variety = request.args.get("strain_variety")
        pot_size_liters = request.args.get("pot_size_liters", type=float)
        mode = request.args.get("mode")

        preferred_mode = _parse_enum(ConditionProfileMode, mode, "mode") if mode else None

        if user_id is None:
            return _fail("user_id is required", 400)
        if not profile_id and (not plant_type or not growth_stage):
            return _fail("plant_type and growth_stage are required when profile_id is not provided", 400)

        profile = service.get_condition_profile(
            user_id=user_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            profile_id=profile_id,
            preferred_mode=preferred_mode,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )
        if not profile:
            return _fail("Condition profile not found", 404)
        return _success({"profile": profile.to_dict()})
    except ValueError as e:
        return safe_error(e, 400)
    except Exception as e:
        logger.error("Error fetching condition profile: %s", e, exc_info=True)
        return safe_error(e, 500)


@personalized_bp.get("/condition-profiles/user/<int:user_id>")
def list_condition_profiles(user_id: int):
    """List all condition profiles for a user."""
    try:
        service = _get_personalized_service()
        if not service:
            return _fail("Personalized learning service is not enabled", 503)
        plant_type = request.args.get("plant_type")
        growth_stage = request.args.get("growth_stage")
        mode = request.args.get("mode")
        visibility = request.args.get("visibility")
        mode_enum = _parse_enum(ConditionProfileMode, mode, "mode") if mode else None
        visibility_enum = _parse_enum(ConditionProfileVisibility, visibility, "visibility") if visibility else None

        profiles = service.list_condition_profiles(user_id)
        if plant_type:
            profiles = [p for p in profiles if p.plant_type == plant_type]
        if growth_stage:
            profiles = [p for p in profiles if p.growth_stage == growth_stage]
        if mode_enum:
            profiles = [p for p in profiles if p.mode == mode_enum]
        if visibility_enum:
            profiles = [p for p in profiles if p.visibility == visibility_enum]
        return _success({"profiles": [profile.to_dict() for profile in profiles]})
    except ValueError as e:
        return safe_error(e, 400)
    except Exception as e:
        logger.error("Error listing condition profiles: %s", e, exc_info=True)
        return safe_error(e, 500)


@personalized_bp.get("/condition-profiles/selector")
def get_condition_profile_selector():
    """
    UI helper for the profile-selection wizard.

    Query params:
        - user_id (optional, defaults to session)
        - plant_type (optional)
        - growth_stage (optional)
        - target_type (optional): unit or plant
        - target_id (optional): id for target_type
    """
    try:
        service = _get_personalized_service()
        if not service:
            return _fail("Personalized learning service is not enabled", 503)

        user_id = request.args.get("user_id", type=int) or _get_user_id()
        plant_type = request.args.get("plant_type")
        growth_stage = request.args.get("growth_stage")
        target_type = request.args.get("target_type")
        target_id = request.args.get("target_id", type=int)

        target_type_enum = _parse_enum(ConditionProfileTarget, target_type, "target_type") if target_type else None

        profiles = service.list_condition_profiles(user_id)
        if plant_type:
            profiles = [p for p in profiles if str(p.plant_type).strip().lower() == plant_type.strip().lower()]
        if growth_stage:
            profiles = [p for p in profiles if str(p.growth_stage).strip().lower() == growth_stage.strip().lower()]

        def _has_env_thresholds(profile: "PlantStageConditionProfile") -> bool:
            if not profile.environment_thresholds:
                return False
            return any(value is not None for value in profile.environment_thresholds.values())

        def _has_soil_threshold(profile: "PlantStageConditionProfile") -> bool:
            return profile.soil_moisture_threshold is not None

        if target_type_enum == ConditionProfileTarget.UNIT:
            profiles = [p for p in profiles if _has_env_thresholds(p)]
        elif target_type_enum == ConditionProfileTarget.PLANT:
            profiles = [p for p in profiles if _has_soil_threshold(p)]

        templates = [p for p in profiles if p.mode == ConditionProfileMode.TEMPLATE]
        active = [p for p in profiles if p.mode == ConditionProfileMode.ACTIVE]

        shared_profiles = service.list_shared_profiles()
        if plant_type:
            shared_profiles = [
                p for p in shared_profiles if str(p.get("plant_type", "")).strip().lower() == plant_type.strip().lower()
            ]
        if growth_stage:
            shared_profiles = [
                p
                for p in shared_profiles
                if str(p.get("growth_stage", "")).strip().lower() == growth_stage.strip().lower()
            ]

        if target_type_enum == ConditionProfileTarget.UNIT:
            shared_profiles = [
                p
                for p in shared_profiles
                if p.get("environment_thresholds")
                and any(v is not None for v in p.get("environment_thresholds", {}).values())
            ]
        elif target_type_enum == ConditionProfileTarget.PLANT:
            shared_profiles = [p for p in shared_profiles if p.get("soil_moisture_threshold") is not None]

        sections = [
            ConditionProfileSection(
                section_type=ConditionProfileMode.TEMPLATE,
                label="Templates",
                description="Starter profiles you can clone and tune.",
                profiles=[_build_profile_card(p) for p in templates],
            ),
            ConditionProfileSection(
                section_type=ConditionProfileMode.ACTIVE,
                label="Active Profiles",
                description="Profiles currently tuned to your grows.",
                profiles=[_build_profile_card(p) for p in active],
            ),
            ConditionProfileSection(
                section_type=ConditionProfileVisibility.PUBLIC,
                label="Shared",
                description="Community profiles you can import.",
                profiles=[
                    _build_profile_card(p, fallback_visibility=ConditionProfileVisibility.PUBLIC)
                    for p in shared_profiles
                ],
            ),
        ]

        linked_profile = None
        if target_type_enum and target_id is not None:
            link = service.get_condition_profile_link(
                user_id=user_id,
                target_type=target_type_enum,
                target_id=target_id,
            )
            if link:
                linked_profile = ConditionProfileLinkSummary(
                    target_type=link.target_type,
                    target_id=link.target_id,
                    profile_id=link.profile_id,
                    mode=link.mode,
                )

        payload = ConditionProfileSelectorResponse(
            sections=sections,
            linked_profile=linked_profile,
            plant_type=plant_type,
            growth_stage=growth_stage,
        )
        return _success({"selector": payload.model_dump()})
    except ValueError as e:
        return safe_error(e, 400)
    except Exception as e:
        logger.error("Error building condition profile selector: %s", e, exc_info=True)
        return safe_error(e, 500)


@personalized_bp.post("/condition-profiles")
def upsert_condition_profile():
    """
    Create or update a per-user plant-stage condition profile.

    Request body:
        - user_id (required)
        - plant_type (required)
        - growth_stage (required)
        - environment_thresholds (optional dict)
        - soil_moisture_threshold (optional)
        - rating (optional int)
        - profile_id (optional)
        - name (optional)
        - image_url (optional)
        - mode (optional): active or template
        - visibility (optional): private, link, public
        - allow_template_update (optional bool)
        - plant_variety, strain_variety, pot_size_liters (optional)
    """
    try:
        service = _get_personalized_service()
        if not service:
            return _fail("Personalized learning service is not enabled", 503)

        data = request.get_json() or {}
        user_id = data.get("user_id")
        plant_type = data.get("plant_type")
        growth_stage = data.get("growth_stage")
        profile_id = data.get("profile_id")
        name = data.get("name")
        image_url = data.get("image_url")
        mode = data.get("mode")
        visibility = data.get("visibility")
        allow_template_update = bool(data.get("allow_template_update", False))
        if user_id is None or not plant_type or not growth_stage:
            return _fail("user_id, plant_type, and growth_stage are required", 400)

        mode_enum = _parse_enum(ConditionProfileMode, mode, "mode") if mode else None
        visibility_enum = _parse_enum(ConditionProfileVisibility, visibility, "visibility") if visibility else None

        profile = service.upsert_condition_profile(
            user_id=int(user_id),
            plant_type=plant_type,
            growth_stage=growth_stage,
            environment_thresholds=data.get("environment_thresholds") or data.get("thresholds"),
            soil_moisture_threshold=data.get("soil_moisture_threshold"),
            profile_id=profile_id,
            name=name,
            image_url=image_url,
            mode=mode_enum,
            visibility=visibility_enum,
            allow_template_update=allow_template_update,
            plant_variety=data.get("plant_variety"),
            strain_variety=data.get("strain_variety"),
            pot_size_liters=data.get("pot_size_liters"),
            rating=data.get("rating"),
        )

        return _success({"profile": profile.to_dict()}, 201)
    except ValueError as e:
        return safe_error(e, 400)
    except Exception as e:
        logger.error("Error upserting condition profile: %s", e, exc_info=True)
        return safe_error(e, 500)


@personalized_bp.post("/condition-profiles/clone")
def clone_condition_profile():
    """
    Clone an existing condition profile.

    Body:
        - user_id (required)
        - source_profile_id (required)
        - name (optional)
        - mode (optional): active or template
    """
    try:
        service = _get_personalized_service()
        if not service:
            return _fail("Personalized learning service is not enabled", 503)

        data = request.get_json() or {}
        user_id = data.get("user_id")
        source_profile_id = data.get("source_profile_id")
        name = data.get("name")
        mode = data.get("mode")
        if user_id is None or not source_profile_id:
            return _fail("user_id and source_profile_id are required", 400)
        mode_enum = _parse_enum(ConditionProfileMode, mode, "mode") if mode else ConditionProfileMode.ACTIVE

        profile = service.clone_condition_profile(
            user_id=int(user_id),
            source_profile_id=source_profile_id,
            name=name,
            mode=mode_enum,
        )
        if not profile:
            return _fail("Source profile not found", 404)
        return _success({"profile": profile.to_dict()}, 201)
    except ValueError as e:
        return safe_error(e, 400)
    except Exception as e:
        logger.error("Error cloning condition profile: %s", e, exc_info=True)
        return safe_error(e, 500)


@personalized_bp.post("/condition-profiles/share")
def share_condition_profile():
    """
    Share a condition profile (link or public).

    Body:
        - user_id (required)
        - profile_id (required)
        - visibility (optional): link or public
    """
    try:
        service = _get_personalized_service()
        if not service:
            return _fail("Personalized learning service is not enabled", 503)

        data = request.get_json() or {}
        user_id = data.get("user_id")
        profile_id = data.get("profile_id")
        visibility = data.get("visibility")
        if user_id is None or not profile_id:
            return _fail("user_id and profile_id are required", 400)
        visibility_enum = (
            _parse_enum(ConditionProfileVisibility, visibility, "visibility")
            if visibility
            else ConditionProfileVisibility.LINK
        )

        result = service.share_condition_profile(
            user_id=int(user_id),
            profile_id=profile_id,
            visibility=visibility_enum,
        )
        if not result:
            return _fail("Profile not found", 404)
        return _success(result)
    except ValueError as e:
        return safe_error(e, 400)
    except Exception as e:
        logger.error("Error sharing condition profile: %s", e, exc_info=True)
        return safe_error(e, 500)


@personalized_bp.get("/condition-profiles/shared/<string:token>")
def get_shared_condition_profile(token: str):
    """Fetch a shared condition profile by token."""
    try:
        service = _get_personalized_service()
        if not service:
            return _fail("Personalized learning service is not enabled", 503)
        profile = service.get_shared_profile(token)
        if not profile:
            return _fail("Shared profile not found", 404)
        return _success({"profile": profile})
    except ValueError as e:
        return safe_error(e, 400)
    except Exception as e:
        logger.error("Error fetching shared profile: %s", e, exc_info=True)
        return safe_error(e, 500)


@personalized_bp.get("/condition-profiles/shared")
def list_shared_condition_profiles():
    """List public shared condition profiles."""
    try:
        service = _get_personalized_service()
        if not service:
            return _fail("Personalized learning service is not enabled", 503)
        profiles = service.list_shared_profiles()
        return _success({"profiles": profiles})
    except ValueError as e:
        return safe_error(e, 400)
    except Exception as e:
        logger.error("Error listing shared profiles: %s", e, exc_info=True)
        return safe_error(e, 500)


@personalized_bp.post("/condition-profiles/import")
def import_shared_condition_profile():
    """
    Import a shared condition profile.

    Body:
        - user_id (required)
        - token (required)
        - name (optional)
        - mode (optional)
    """
    try:
        service = _get_personalized_service()
        if not service:
            return _fail("Personalized learning service is not enabled", 503)
        data = request.get_json() or {}
        user_id = data.get("user_id")
        token = data.get("token")
        name = data.get("name")
        mode = data.get("mode")
        if user_id is None or not token:
            return _fail("user_id and token are required", 400)
        mode_enum = _parse_enum(ConditionProfileMode, mode, "mode") if mode else ConditionProfileMode.ACTIVE
        result = service.import_shared_profile(
            user_id=int(user_id),
            token=token,
            name=name,
            mode=mode_enum,
        )
        if not result:
            return _fail("Shared profile not found", 404)
        profile, already_imported = result
        status = 200 if already_imported else 201
        return _success({"profile": profile.to_dict(), "already_imported": already_imported}, status)
    except ValueError as e:
        return safe_error(e, 400)
    except Exception as e:
        logger.error("Error importing shared profile: %s", e, exc_info=True)
        return safe_error(e, 500)


# ==============================================================================
# SUCCESS TRACKING
# ==============================================================================


@personalized_bp.post("/successes")
def record_success():
    """
    Record a growing success (completed grow cycle).

    Request body:
        {
            "user_id": int,
            "unit_id": int,
            "plant_type": str,
            "plant_variety": str (optional),
            "start_date": str (ISO 8601),
            "harvest_date": str (ISO 8601),
            "total_yield": float (grams, optional),
            "quality_rating": int (1-5),
            "growth_conditions": {...} (optional),
            "lessons_learned": [...] (optional),
            "would_repeat": bool
        }

    Returns:
        {
            "recorded": true,
            "success": {...}
        }
    """
    try:
        from app.services.ai.personalized_learning import GrowingSuccess

        service = _get_personalized_service()

        if not service:
            return _fail("Personalized learning service is not enabled", 503)

        data = request.get_json() or {}

        # Validate required fields
        required = ["user_id", "unit_id", "plant_type", "start_date", "harvest_date", "quality_rating", "would_repeat"]
        missing = [f for f in required if f not in data]
        if missing:
            return _fail(f"Missing required fields: {', '.join(missing)}", 400)

        success = GrowingSuccess(
            user_id=data["user_id"],
            unit_id=data["unit_id"],
            plant_type=data["plant_type"],
            plant_variety=data.get("plant_variety"),
            start_date=datetime.fromisoformat(data["start_date"]),
            harvest_date=datetime.fromisoformat(data["harvest_date"]),
            total_yield=data.get("total_yield"),
            quality_rating=data["quality_rating"],
            growth_conditions=data.get("growth_conditions", {}),
            lessons_learned=data.get("lessons_learned", []),
            would_repeat=data["would_repeat"],
        )

        service.record_success(success)

        return _success({"recorded": True, "success": success.to_dict()}, 201)

    except ValueError as e:
        return _fail(f"Invalid date format: {e}", 400)
    except Exception as e:
        logger.error(f"Error recording success: {e}", exc_info=True)
        return safe_error(e, 500)


# ==============================================================================
# RECOMMENDATIONS
# ==============================================================================


@personalized_bp.get("/recommendations/<int:unit_id>")
def get_recommendations(unit_id: int):
    """
    Get personalized recommendations for a unit.

    Query params:
    - plant_type: Plant type for recommendations
    - growth_stage: Current growth stage

    Returns:
        {
            "unit_id": int,
            "recommendations": {
                "climate": {...},
                "watering": {...},
                "lighting": {...},
                "adjustments": [...],
                "confidence": float
            }
        }
    """
    try:
        container = _container()
        service = getattr(container, "personalized_learning", None)

        if not service:
            return _success(
                {"unit_id": unit_id, "recommendations": None, "message": "Personalized learning service is not enabled"}
            )

        plant_type = request.args.get("plant_type", "tomato")
        growth_stage = request.args.get("growth_stage", "vegetative")

        # Get current conditions from latest sensor data
        latest_data = None
        analytics_service = getattr(container, "analytics_service", None)
        if analytics_service:
            try:
                latest_data = analytics_service.get_latest_sensor_reading(unit_id=unit_id)
            except Exception as exc:
                logger.warning("Failed to load latest sensor data for unit %s: %s", unit_id, exc)

        from app.domain.sensors.fields import SensorField

        # Use standardized keys
        lux_value = latest_data.get(SensorField.LUX.value) if isinstance(latest_data, dict) else None

        current_conditions = {
            "temperature": latest_data.get(SensorField.TEMPERATURE.value, 25.0)
            if isinstance(latest_data, dict)
            else 25.0,
            "humidity": latest_data.get(SensorField.HUMIDITY.value, 60.0) if isinstance(latest_data, dict) else 60.0,
            "soil_moisture": latest_data.get(SensorField.SOIL_MOISTURE.value, 50.0)
            if isinstance(latest_data, dict)
            else 50.0,
            "lux": lux_value if lux_value is not None else 500.0,
        }

        recommendations = service.get_personalized_recommendations(
            unit_id=unit_id, plant_type=plant_type, growth_stage=growth_stage, current_conditions=current_conditions
        )

        return _success(
            {
                "unit_id": unit_id,
                "plant_type": plant_type,
                "growth_stage": growth_stage,
                "recommendations": recommendations,
            }
        )

    except Exception as e:
        logger.error(f"Error getting recommendations for unit {unit_id}: {e}", exc_info=True)
        return safe_error(e, 500)


@personalized_bp.get("/similar-growers/<int:unit_id>")
def get_similar_growers(unit_id: int):
    """
    Find growers with similar environments and successes.

    Query params:
    - plant_type: Plant type to compare (optional)
    - limit: Max results (default 5)

    Returns:
        {
            "unit_id": int,
            "similar_growers": [
                {
                    "unit_id": int,
                    "similarity_score": float,
                    "shared_success_factors": [...],
                    "key_conditions": {...}
                }
            ]
        }
    """
    try:
        service = _get_personalized_service()

        if not service:
            return _success(
                {"unit_id": unit_id, "similar_growers": [], "message": "Personalized learning service is not enabled"}
            )

        plant_type = request.args.get("plant_type")
        limit = request.args.get("limit", 5, type=int)

        similar = service.get_similar_growers(unit_id=unit_id, plant_type=plant_type, limit=limit)

        return _success({"unit_id": unit_id, "similar_growers": similar, "count": len(similar)})

    except Exception as e:
        logger.error(f"Error finding similar growers for unit {unit_id}: {e}", exc_info=True)
        return safe_error(e, 500)
