"""
UI Blueprint Helpers
====================

Helper functions for UI routes that format data for display.
These functions work with GrowthService to provide UI-specific data transformations.

Author: SYSGrow Team
Date: November 2025
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.services.application.plant_service import PlantViewService

if TYPE_CHECKING:
    from app.services.application.growth_service import GrowthService

logger = logging.getLogger(__name__)


def determine_landing_page(growth_service: "GrowthService", user_id: int) -> dict[str, Any]:
    """
    Smart routing: Determine where user should land after login.

    Args:
        growth_service: GrowthService instance
        user_id: The user identifier

    Returns:
        Dictionary with routing information:
        {
            "route": "dashboard" | "unit_selector",
            "unit_id": <id> if single unit,
            "units": [...] if multiple units
        }
    """
    try:
        units = growth_service.list_units(user_id=user_id)

        if len(units) == 0:
            # No units - create default and go to dashboard
            unit_id = growth_service.create_unit(name="My First Growth Unit", location="Indoor", user_id=user_id)
            logger.info("Created default unit %s for new user %s", unit_id, user_id)
            return {"route": "dashboard", "unit_id": unit_id, "is_new_user": True}

        elif len(units) == 1:
            # Single unit - go straight to dashboard
            return {"route": "dashboard", "unit_id": units[0]["unit_id"], "is_new_user": False}

        else:
            # Multiple units - show selector
            return {"route": "unit_selector", "units": units, "is_new_user": False}

    except Exception as e:
        logger.error("Error determining landing page for user %s: %s", user_id, e, exc_info=True)
        return {"route": "dashboard", "error": True}


def get_unit_card_data(
    growth_service: "GrowthService", plant_service: "PlantViewService", unit_id: int
) -> dict[str, Any]:
    """
    Get data formatted for unit selection card display.

    Args:
        growth_service: GrowthService instance
        plant_service: PlantService instance
        unit_id: Unit identifier

    Returns:
        Dictionary formatted for UI display
    """
    try:
        unit = growth_service.get_unit(unit_id)
        if not unit:
            return {}

        plants = plant_service.list_plants_as_dicts(unit_id)

        # Get statistics via service (no direct repo access)
        hw_stats = growth_service.get_unit_stats(unit_id)
        stats = {
            "plant_count": len(plants),
            "sensor_count": hw_stats.get("sensor_count", 0),
            "actuator_count": hw_stats.get("actuator_count", 0),
            "camera_active": hw_stats.get("camera_active", False),
            "last_activity": hw_stats.get("last_activity"),
            "uptime_hours": hw_stats.get("uptime_hours", 0),
        }

        # Format plant data with moisture indicators
        plant_cards = []
        for plant in plants[:6]:  # Limit to 6 for display
            moisture_level = plant.get("moisture_level", 0)
            plant_cards.append(
                {
                    "id": plant.get("plant_id") or plant.get("id"),
                    "name": plant.get("plant_name") or plant.get("name"),
                    "icon": _get_plant_icon(plant.get("plant_type", "")),
                    "moisture_level": moisture_level,
                    "moisture_status": _get_moisture_status(moisture_level),
                    "stage": plant.get("current_stage", "Unknown"),
                }
            )

        return {
            "unit_id": unit.get("unit_id") or unit.get("id"),
            "name": unit.get("name", "Default Growth Unit"),
            "location": unit.get("location", "Indoor"),
            "custom_image": unit.get("custom_image", "/static/images/my-unit.png"),
            "dimensions": unit.get("dimensions"),
            "plant_count": stats.get("plant_count", 0),
            "sensor_count": stats.get("sensor_count", 0),
            "actuator_count": stats.get("actuator_count", 0),
            "plants": plant_cards,
            "camera_available": stats.get("camera_active", False),
            "last_activity": stats.get("last_activity"),
            "uptime_hours": stats.get("uptime_hours", 0),
        }

    except Exception as e:
        logger.error("Error getting card data for unit %s: %s", unit_id, e, exc_info=True)
        return {}


def _get_plant_icon(plant_type: str) -> str:
    """Get emoji icon for plant type"""
    icon_map = {
        "tomato": "🍅",
        "lettuce": "🥬",
        "basil": "🌿",
        "pepper": "🌶️",
        "strawberry": "🍓",
        "cannabis": "🌱",
        "herb": "🌿",
    }
    return icon_map.get(plant_type.lower(), "🌱")


def _get_moisture_status(moisture_level: float) -> dict[str, str]:
    """
    Determine moisture status with color coding.

    Returns:
        {
            "status": "too_wet" | "wet" | "normal" | "dry" | "too_dry",
            "color": "#hex_color",
            "label": "Display text"
        }
    """
    if moisture_level >= 80:
        return {"status": "too_wet", "color": "#0066cc", "label": "Too Wet"}
    elif moisture_level >= 60:
        return {"status": "wet", "color": "#00aaff", "label": "Wet"}
    elif moisture_level >= 30:
        return {"status": "normal", "color": "#28a745", "label": "Good"}
    elif moisture_level >= 15:
        return {"status": "dry", "color": "#ffc107", "label": "Dry"}
    else:
        return {"status": "too_dry", "color": "#dc3545", "label": "Too Dry"}
