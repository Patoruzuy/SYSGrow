"""
Personalized Learning Schemas
=============================

Pydantic models for condition profile UI helpers.
"""
from __future__ import annotations

from typing import List, Optional, Union

from pydantic import BaseModel, Field

from app.enums.common import ConditionProfileMode, ConditionProfileVisibility, ConditionProfileTarget


ConditionProfileSectionType = Union[ConditionProfileMode, ConditionProfileVisibility]


class ConditionProfileCard(BaseModel):
    """Compact representation of a condition profile for UI cards."""

    profile_id: str
    name: Optional[str] = None
    image_url: Optional[str] = None
    plant_type: str
    growth_stage: str
    plant_variety: Optional[str] = None
    strain_variety: Optional[str] = None
    pot_size_liters: Optional[float] = None
    mode: Optional[ConditionProfileMode] = None
    visibility: Optional[ConditionProfileVisibility] = None
    rating_avg: float = Field(default=0.0, description="Average rating (0-5)")
    rating_count: int = Field(default=0, description="Number of ratings")
    last_rating: Optional[int] = None
    shared_token: Optional[str] = None
    source_profile_id: Optional[str] = None
    source_profile_name: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ConditionProfileSection(BaseModel):
    """Grouped card collection for profile selection wizard."""

    section_type: ConditionProfileSectionType
    label: str
    description: Optional[str] = None
    profiles: List[ConditionProfileCard] = Field(default_factory=list)


class ConditionProfileLinkSummary(BaseModel):
    """Summary of current profile link for a target."""

    target_type: ConditionProfileTarget
    target_id: int
    profile_id: str
    mode: ConditionProfileMode


class ConditionProfileSelectorResponse(BaseModel):
    """Response payload for the profile-selection wizard."""

    sections: List[ConditionProfileSection]
    linked_profile: Optional[ConditionProfileLinkSummary] = None
    plant_type: Optional[str] = None
    growth_stage: Optional[str] = None
