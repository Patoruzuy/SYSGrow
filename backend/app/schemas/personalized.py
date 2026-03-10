"""
Personalized Learning Schemas
=============================

Pydantic models for condition profile UI helpers.
"""

from __future__ import annotations

from typing import Union

from pydantic import BaseModel, Field

from app.enums.common import ConditionProfileMode, ConditionProfileTarget, ConditionProfileVisibility

ConditionProfileSectionType = Union[ConditionProfileMode, ConditionProfileVisibility]


class ConditionProfileCard(BaseModel):
    """Compact representation of a condition profile for UI cards."""

    profile_id: str
    name: str | None = None
    image_url: str | None = None
    plant_type: str
    growth_stage: str
    plant_variety: str | None = None
    strain_variety: str | None = None
    pot_size_liters: float | None = None
    mode: ConditionProfileMode | None = None
    visibility: ConditionProfileVisibility | None = None
    rating_avg: float = Field(default=0.0, description="Average rating (0-5)")
    rating_count: int = Field(default=0, description="Number of ratings")
    last_rating: int | None = None
    shared_token: str | None = None
    source_profile_id: str | None = None
    source_profile_name: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class ConditionProfileSection(BaseModel):
    """Grouped card collection for profile selection wizard."""

    section_type: ConditionProfileSectionType
    label: str
    description: str | None = None
    profiles: list[ConditionProfileCard] = Field(default_factory=list)


class ConditionProfileLinkSummary(BaseModel):
    """Summary of current profile link for a target."""

    target_type: ConditionProfileTarget
    target_id: int
    profile_id: str
    mode: ConditionProfileMode


class ConditionProfileSelectorResponse(BaseModel):
    """Response payload for the profile-selection wizard."""

    sections: list[ConditionProfileSection]
    linked_profile: ConditionProfileLinkSummary | None = None
    plant_type: str | None = None
    growth_stage: str | None = None
