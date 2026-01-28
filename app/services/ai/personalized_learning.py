"""
Personalized Learning System
==============================
Adapts AI models to individual user's growing environment and patterns.

Features:
- User-specific model fine-tuning
- Environment fingerprinting (unique characteristics of each setup)
- Success pattern recognition
- Failure pattern learning
- Adaptive recommendations based on user's history
"""

import logging
import json
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, TYPE_CHECKING, Callable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from app.enums.common import (
    ConditionProfileMode,
    ConditionProfileVisibility,
    ConditionProfileTarget,
)

# ML libraries lazy loaded in methods for faster startup
# import numpy as np
# import pandas as pd

if TYPE_CHECKING:
    from app.services.ai.model_registry import ModelRegistry
    from infrastructure.database.repositories.ai import AITrainingDataRepository

logger = logging.getLogger(__name__)

ENV_THRESHOLD_KEYS = (
    "temperature_threshold",
    "humidity_threshold",
    "co2_threshold",
    "voc_threshold",
    "lux_threshold",
    "air_quality_threshold",
)


@dataclass
class EnvironmentProfile:
    """Profile of a user's unique growing environment."""
    
    user_id: int
    unit_id: int
    location_characteristics: Dict[str, Any]
    equipment_profile: Dict[str, Any]
    historical_patterns: Dict[str, Any]
    success_factors: List[str]
    challenge_areas: List[str]
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'unit_id': self.unit_id,
            'location_characteristics': self.location_characteristics,
            'equipment_profile': self.equipment_profile,
            'historical_patterns': self.historical_patterns,
            'success_factors': self.success_factors,
            'challenge_areas': self.challenge_areas,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class GrowingSuccess:
    """Record of a successful grow cycle."""
    
    user_id: int
    unit_id: int
    plant_type: str
    plant_variety: Optional[str]
    start_date: datetime
    harvest_date: datetime
    total_yield: Optional[float]  # grams
    quality_rating: int  # 1-5
    growth_conditions: Dict[str, Any]
    lessons_learned: List[str]
    would_repeat: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'unit_id': self.unit_id,
            'plant_type': self.plant_type,
            'plant_variety': self.plant_variety,
            'start_date': self.start_date.isoformat(),
            'harvest_date': self.harvest_date.isoformat(),
            'days_to_harvest': (self.harvest_date - self.start_date).days,
            'total_yield': self.total_yield,
            'quality_rating': self.quality_rating,
            'growth_conditions': self.growth_conditions,
            'lessons_learned': self.lessons_learned,
            'would_repeat': self.would_repeat,
        }


@dataclass
class ConditionProfileLink:
    """Link between a plant/unit and a condition profile."""

    user_id: int
    target_type: ConditionProfileTarget
    target_id: int
    profile_id: str
    mode: ConditionProfileMode
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "target_type": str(self.target_type),
            "target_id": self.target_id,
            "profile_id": self.profile_id,
            "mode": str(self.mode),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "ConditionProfileLink":
        return ConditionProfileLink(
            user_id=int(data["user_id"]),
            target_type=ConditionProfileTarget(data.get("target_type", ConditionProfileTarget.UNIT)),
            target_id=int(data.get("target_id", 0)),
            profile_id=str(data.get("profile_id", "")),
            mode=ConditionProfileMode(data.get("mode") or ConditionProfileMode.ACTIVE),
            created_at=datetime.fromisoformat(data.get("created_at")) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data.get("updated_at")) if data.get("updated_at") else datetime.now(),
        )

@dataclass
class PlantStageConditionProfile:
    """Per-user plant-stage condition profile for threshold reuse."""

    profile_id: str
    name: Optional[str]
    image_url: Optional[str]
    user_id: int
    plant_type: str
    growth_stage: str
    plant_variety: Optional[str]
    strain_variety: Optional[str]
    pot_size_liters: Optional[float]
    environment_thresholds: Dict[str, float]
    soil_moisture_threshold: Optional[float]
    mode: ConditionProfileMode = ConditionProfileMode.ACTIVE
    visibility: ConditionProfileVisibility = ConditionProfileVisibility.PRIVATE
    shared_token: Optional[str] = None
    shared_at: Optional[datetime] = None
    source_profile_id: Optional[str] = None
    source_profile_name: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    rating_count: int = 0
    rating_avg: float = 0.0
    last_rating: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "image_url": self.image_url,
            "user_id": self.user_id,
            "plant_type": self.plant_type,
            "growth_stage": self.growth_stage,
            "plant_variety": self.plant_variety,
            "strain_variety": self.strain_variety,
            "pot_size_liters": self.pot_size_liters,
            "environment_thresholds": self.environment_thresholds,
            "soil_moisture_threshold": self.soil_moisture_threshold,
            "mode": str(self.mode),
            "visibility": str(self.visibility),
            "shared_token": self.shared_token,
            "shared_at": self.shared_at.isoformat() if self.shared_at else None,
            "source_profile_id": self.source_profile_id,
            "source_profile_name": self.source_profile_name,
            "tags": list(self.tags),
            "rating_count": self.rating_count,
            "rating_avg": self.rating_avg,
            "last_rating": self.last_rating,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PlantStageConditionProfile":
        mode_raw = data.get("mode") or ConditionProfileMode.ACTIVE
        visibility_raw = data.get("visibility") or ConditionProfileVisibility.PRIVATE
        try:
            mode = ConditionProfileMode(mode_raw)
        except ValueError:
            mode = ConditionProfileMode.ACTIVE
        try:
            visibility = ConditionProfileVisibility(visibility_raw)
        except ValueError:
            visibility = ConditionProfileVisibility.PRIVATE
        return PlantStageConditionProfile(
            profile_id=str(data.get("profile_id") or uuid4().hex),
            name=data.get("name"),
            image_url=data.get("image_url"),
            user_id=int(data["user_id"]),
            plant_type=data.get("plant_type", ""),
            growth_stage=data.get("growth_stage", ""),
            plant_variety=data.get("plant_variety"),
            strain_variety=data.get("strain_variety"),
            pot_size_liters=data.get("pot_size_liters"),
            environment_thresholds=data.get("environment_thresholds", {}),
            soil_moisture_threshold=data.get("soil_moisture_threshold"),
            mode=mode,
            visibility=visibility,
            shared_token=data.get("shared_token"),
            shared_at=datetime.fromisoformat(data.get("shared_at"))
            if data.get("shared_at")
            else None,
            source_profile_id=data.get("source_profile_id"),
            source_profile_name=data.get("source_profile_name"),
            tags=list(data.get("tags") or []),
            rating_count=int(data.get("rating_count", 0)),
            rating_avg=float(data.get("rating_avg", 0.0)),
            last_rating=data.get("last_rating"),
            created_at=datetime.fromisoformat(data.get("created_at")) if data.get("created_at") else datetime.now(),
            updated_at=datetime.fromisoformat(data.get("updated_at")) if data.get("updated_at") else datetime.now(),
        )



class PersonalizedLearningService:
    """
    Service for personalizing AI recommendations to individual users.
    
    Learns from each user's unique environment, equipment, and growing history
    to provide increasingly accurate and personalized recommendations.
    """
    
    def __init__(
        self,
        model_registry: "ModelRegistry",
        training_data_repo: "AITrainingDataRepository",
        profiles_dir: Optional[Path] = None
    ):
        """
        Initialize personalized learning service.
        
        Args:
            model_registry: Model registry for accessing base models
            training_data_repo: Repository for training data
            profiles_dir: Directory for storing user profiles
        """
        self.model_registry = model_registry
        self.training_data_repo = training_data_repo
        self.profiles_dir = profiles_dir or Path("data/user_profiles")
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache of loaded profiles
        self._profile_cache: Dict[int, EnvironmentProfile] = {}
        
        # Success/failure tracking
        self.successes_dir = self.profiles_dir / "successes"
        self.successes_dir.mkdir(exist_ok=True)

        self.condition_profiles_dir = self.profiles_dir / "condition_profiles"
        self.condition_profiles_dir.mkdir(exist_ok=True)
        self._condition_profile_cache: Dict[int, List[PlantStageConditionProfile]] = {}
        self.condition_profile_links_dir = self.condition_profiles_dir / "links"
        self.condition_profile_links_dir.mkdir(exist_ok=True)
        self._condition_profile_links_cache: Dict[int, List[ConditionProfileLink]] = {}

        self.shared_profiles_dir = self.condition_profiles_dir / "shared"
        self.shared_profiles_dir.mkdir(exist_ok=True)
        self.shared_profiles_index = self.shared_profiles_dir / "index.json"
        self._profile_update_callbacks: List[Callable[[], None]] = []
        
        logger.info("PersonalizedLearningService initialized")

    def register_profile_update_callback(self, callback: Callable[[], None]) -> None:
        """Register a callback to invoke when condition profiles change."""
        if callback not in self._profile_update_callbacks:
            self._profile_update_callbacks.append(callback)

    def _notify_profile_update(self) -> None:
        for callback in self._profile_update_callbacks:
            try:
                callback()
            except Exception:
                logger.exception("Profile update callback failed")
    
    def create_environment_profile(
        self,
        user_id: int,
        unit_id: int,
        location_info: Optional[Dict[str, Any]] = None,
        equipment_info: Optional[Dict[str, Any]] = None
    ) -> EnvironmentProfile:
        """
        Create initial environment profile for a user's grow unit.
        
        Args:
            user_id: User ID
            unit_id: Unit ID
            location_info: Optional location characteristics (climate zone, etc.)
            equipment_info: Optional equipment specifications
            
        Returns:
            Created EnvironmentProfile
        """
        # Analyze historical data to build profile
        historical_patterns = self._analyze_historical_patterns(unit_id)
        
        # Detect unique environmental characteristics
        location_chars = location_info or self._detect_location_characteristics(unit_id)
        equipment_profile = equipment_info or self._profile_equipment(unit_id)
        
        profile = EnvironmentProfile(
            user_id=user_id,
            unit_id=unit_id,
            location_characteristics=location_chars,
            equipment_profile=equipment_profile,
            historical_patterns=historical_patterns,
            success_factors=[],  # Will be populated as grows complete
            challenge_areas=[],  # Will be populated from issues
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Save profile
        self._save_profile(profile)
        self._profile_cache[unit_id] = profile
        
        logger.info(f"Created environment profile for user {user_id}, unit {unit_id}")
        return profile
    
    def get_profile(self, unit_id: int) -> Optional[EnvironmentProfile]:
        """Get environment profile for a unit."""
        # Check cache
        if unit_id in self._profile_cache:
            return self._profile_cache[unit_id]
        
        # Load from disk
        profile_file = self.profiles_dir / f"unit_{unit_id}_profile.json"
        if profile_file.exists():
            try:
                with open(profile_file, 'r') as f:
                    data = json.load(f)
                    profile = EnvironmentProfile(
                        user_id=data['user_id'],
                        unit_id=data['unit_id'],
                        location_characteristics=data['location_characteristics'],
                        equipment_profile=data['equipment_profile'],
                        historical_patterns=data['historical_patterns'],
                        success_factors=data['success_factors'],
                        challenge_areas=data['challenge_areas'],
                        created_at=datetime.fromisoformat(data['created_at']),
                        updated_at=datetime.fromisoformat(data['updated_at'])
                    )
                    self._profile_cache[unit_id] = profile
                    return profile
            except Exception as e:
                logger.error(f"Error loading profile: {e}")
        
        return None
    
    def update_profile(self, unit_id: int, updates: Dict[str, Any]):
        """Update environment profile with new learnings."""
        profile = self.get_profile(unit_id)
        if not profile:
            logger.warning(f"No profile found for unit {unit_id}")
            return
        
        # Update fields
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        profile.updated_at = datetime.now()
        
        # Save updated profile
        self._save_profile(profile)
        self._profile_cache[unit_id] = profile

    # ------------------------------------------------------------------
    # Condition profiles (per-user plant-stage thresholds)
    # ------------------------------------------------------------------

    def get_condition_profile(
        self,
        *,
        user_id: int,
        plant_type: str,
        growth_stage: str,
        profile_id: Optional[str] = None,
        preferred_mode: Optional[ConditionProfileMode] = None,
        plant_variety: Optional[str] = None,
        strain_variety: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> Optional[PlantStageConditionProfile]:
        profiles = self._load_condition_profiles(user_id)
        if profile_id:
            for profile in profiles:
                if profile.profile_id == profile_id:
                    return profile
            return None
        matches = [
            profile
            for profile in profiles
            if self._profile_matches(
                profile,
                plant_type=plant_type,
                growth_stage=growth_stage,
                plant_variety=plant_variety,
                strain_variety=strain_variety,
                pot_size_liters=pot_size_liters,
            )
        ]
        if not matches:
            return None
        if preferred_mode:
            preferred = [p for p in matches if p.mode == preferred_mode]
            if preferred:
                preferred.sort(key=lambda p: p.updated_at, reverse=True)
                return preferred[0]
        matches.sort(key=lambda p: p.updated_at, reverse=True)
        return matches[0]

    def get_condition_profile_by_id(
        self, user_id: int, profile_id: str
    ) -> Optional[PlantStageConditionProfile]:
        profiles = self._load_condition_profiles(user_id)
        for profile in profiles:
            if profile.profile_id == profile_id:
                return profile
        return None

    def list_condition_profiles(self, user_id: int) -> List[PlantStageConditionProfile]:
        return list(self._load_condition_profiles(user_id))

    def upsert_condition_profile(
        self,
        *,
        user_id: int,
        plant_type: str,
        growth_stage: str,
        environment_thresholds: Optional[Dict[str, Any]] = None,
        soil_moisture_threshold: Optional[float] = None,
        profile_id: Optional[str] = None,
        name: Optional[str] = None,
        image_url: Optional[str] = None,
        mode: Optional[ConditionProfileMode] = None,
        visibility: Optional[ConditionProfileVisibility] = None,
        allow_template_update: bool = False,
        plant_variety: Optional[str] = None,
        strain_variety: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
        rating: Optional[int] = None,
    ) -> PlantStageConditionProfile:
        profiles = self._load_condition_profiles(user_id)
        existing = None
        for profile in profiles:
            if self._profile_matches(
                profile,
                plant_type=plant_type,
                growth_stage=growth_stage,
                plant_variety=plant_variety,
                strain_variety=strain_variety,
                pot_size_liters=pot_size_liters,
                require_exact=True,
                profile_id=profile_id,
            ):
                existing = profile
                break

        env_payload: Dict[str, float] = {}
        for key, value in (environment_thresholds or {}).items():
            if key not in ENV_THRESHOLD_KEYS:
                continue
            try:
                env_payload[key] = float(value)
            except (TypeError, ValueError):
                continue

        now = datetime.now()

        if existing:
            if existing.mode == ConditionProfileMode.TEMPLATE and not allow_template_update:
                return existing
            if env_payload:
                existing.environment_thresholds.update(env_payload)
            if soil_moisture_threshold is not None:
                try:
                    existing.soil_moisture_threshold = float(soil_moisture_threshold)
                except (TypeError, ValueError):
                    pass
            if name:
                existing.name = name
            if image_url is not None:
                existing.image_url = image_url
            if mode:
                existing.mode = mode
            if visibility:
                existing.visibility = visibility
            if rating is not None:
                try:
                    rating_int = int(rating)
                except (TypeError, ValueError):
                    rating_int = None
                if rating_int is not None:
                    new_count = existing.rating_count + 1
                    existing.rating_avg = (
                        (existing.rating_avg * existing.rating_count) + rating_int
                    ) / new_count
                    existing.rating_count = new_count
                    existing.last_rating = rating_int
            existing.updated_at = now
            profile = existing
        else:
            profile = PlantStageConditionProfile(
                profile_id=profile_id or uuid4().hex,
                name=name,
                image_url=image_url,
                user_id=user_id,
                plant_type=plant_type,
                growth_stage=growth_stage,
                plant_variety=plant_variety,
                strain_variety=strain_variety,
                pot_size_liters=pot_size_liters,
                environment_thresholds=env_payload,
                soil_moisture_threshold=float(soil_moisture_threshold)
                if soil_moisture_threshold is not None
                else None,
                mode=mode or ConditionProfileMode.ACTIVE,
                visibility=visibility or ConditionProfileVisibility.PRIVATE,
                rating_count=1 if rating is not None else 0,
                rating_avg=float(rating) if rating is not None else 0.0,
                last_rating=int(rating) if rating is not None else None,
                created_at=now,
                updated_at=now,
            )
            profiles.append(profile)

        self._save_condition_profiles(user_id, profiles)
        self._condition_profile_cache[user_id] = profiles
        self._notify_profile_update()
        return profile

    def clone_condition_profile(
        self,
        *,
        user_id: int,
        source_profile_id: str,
        name: Optional[str] = None,
        mode: ConditionProfileMode = ConditionProfileMode.ACTIVE,
    ) -> Optional[PlantStageConditionProfile]:
        profiles = self._load_condition_profiles(user_id)
        source = None
        for profile in profiles:
            if profile.profile_id == source_profile_id:
                source = profile
                break
        if not source:
            return None

        now = datetime.now()
        cloned = PlantStageConditionProfile(
            profile_id=uuid4().hex,
            name=name or (f"Copy of {source.name}" if source.name else None),
            image_url=source.image_url,
            user_id=user_id,
            plant_type=source.plant_type,
            growth_stage=source.growth_stage,
            plant_variety=source.plant_variety,
            strain_variety=source.strain_variety,
            pot_size_liters=source.pot_size_liters,
            environment_thresholds=dict(source.environment_thresholds),
            soil_moisture_threshold=source.soil_moisture_threshold,
            mode=mode,
            visibility=ConditionProfileVisibility.PRIVATE,
            shared_token=None,
            shared_at=None,
            source_profile_id=source.profile_id,
            source_profile_name=source.name,
            tags=list(source.tags),
            rating_count=0,
            rating_avg=0.0,
            last_rating=None,
            created_at=now,
            updated_at=now,
        )
        profiles.append(cloned)
        self._save_condition_profiles(user_id, profiles)
        self._condition_profile_cache[user_id] = profiles
        self._notify_profile_update()
        return cloned

    def share_condition_profile(
        self,
        *,
        user_id: int,
        profile_id: str,
        visibility: ConditionProfileVisibility = ConditionProfileVisibility.LINK,
    ) -> Optional[Dict[str, Any]]:
        profile = self.get_condition_profile_by_id(user_id, profile_id)
        if not profile:
            return None

        token = profile.shared_token or secrets.token_urlsafe(16)
        profile.shared_token = token
        profile.shared_at = datetime.now()
        profile.visibility = visibility

        self._save_condition_profiles(user_id, self._load_condition_profiles(user_id))
        self._condition_profile_cache.pop(user_id, None)

        snapshot = profile.to_dict()
        self._save_shared_profile_snapshot(token, snapshot)
        if visibility == ConditionProfileVisibility.PUBLIC:
            self._update_shared_index(snapshot)

        return {
            "token": token,
            "profile": snapshot,
        }

    def get_shared_profile(self, token: str) -> Optional[Dict[str, Any]]:
        path = self.shared_profiles_dir / f"{token}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r") as fh:
                return json.load(fh)
        except Exception as exc:
            logger.error("Failed to load shared profile %s: %s", token, exc)
            return None

    def list_shared_profiles(self) -> List[Dict[str, Any]]:
        if not self.shared_profiles_index.exists():
            return []
        try:
            with open(self.shared_profiles_index, "r") as fh:
                return json.load(fh) or []
        except Exception as exc:
            logger.error("Failed to load shared profile index: %s", exc)
            return []

    def import_shared_profile(
        self,
        *,
        user_id: int,
        token: str,
        name: Optional[str] = None,
        mode: ConditionProfileMode = ConditionProfileMode.ACTIVE,
    ) -> Optional[PlantStageConditionProfile]:
        snapshot = self.get_shared_profile(token)
        if not snapshot:
            return None
        source = PlantStageConditionProfile.from_dict(snapshot)
        now = datetime.now()
        imported = PlantStageConditionProfile(
            profile_id=uuid4().hex,
            name=name or source.name,
            image_url=source.image_url,
            user_id=user_id,
            plant_type=source.plant_type,
            growth_stage=source.growth_stage,
            plant_variety=source.plant_variety,
            strain_variety=source.strain_variety,
            pot_size_liters=source.pot_size_liters,
            environment_thresholds=dict(source.environment_thresholds),
            soil_moisture_threshold=source.soil_moisture_threshold,
            mode=mode,
            visibility=ConditionProfileVisibility.PRIVATE,
            shared_token=None,
            shared_at=None,
            source_profile_id=source.profile_id,
            source_profile_name=source.name,
            tags=list(source.tags),
            rating_count=0,
            rating_avg=0.0,
            last_rating=None,
            created_at=now,
            updated_at=now,
        )
        profiles = self._load_condition_profiles(user_id)
        profiles.append(imported)
        self._save_condition_profiles(user_id, profiles)
        self._condition_profile_cache[user_id] = profiles
        self._notify_profile_update()
        return imported

    def link_condition_profile(
        self,
        *,
        user_id: int,
        target_type: ConditionProfileTarget,
        target_id: int,
        profile_id: str,
        mode: ConditionProfileMode,
    ) -> ConditionProfileLink:
        links = self._load_condition_profile_links(user_id)
        existing = None
        for link in links:
            if link.target_type == target_type and link.target_id == target_id:
                existing = link
                break

        now = datetime.now()
        if existing:
            existing.profile_id = profile_id
            existing.mode = mode
            existing.updated_at = now
            link = existing
        else:
            link = ConditionProfileLink(
                user_id=user_id,
                target_type=target_type,
                target_id=target_id,
                profile_id=profile_id,
                mode=mode,
                created_at=now,
                updated_at=now,
            )
            links.append(link)

        self._save_condition_profile_links(user_id, links)
        self._condition_profile_links_cache[user_id] = links
        return link

    def get_condition_profile_link(
        self,
        *,
        user_id: int,
        target_type: ConditionProfileTarget,
        target_id: int,
    ) -> Optional[ConditionProfileLink]:
        links = self._load_condition_profile_links(user_id)
        for link in links:
            if link.target_type == target_type and link.target_id == target_id:
                return link
        return None

    def unlink_condition_profile(
        self,
        *,
        user_id: int,
        target_type: ConditionProfileTarget,
        target_id: int,
    ) -> bool:
        links = self._load_condition_profile_links(user_id)
        remaining = [
            link for link in links
            if not (link.target_type == target_type and link.target_id == target_id)
        ]
        if len(remaining) == len(links):
            return False
        self._save_condition_profile_links(user_id, remaining)
        self._condition_profile_links_cache[user_id] = remaining
        return True
    
    def record_success(self, success: GrowingSuccess):
        """
        Record a successful grow cycle for learning.
        
        Args:
            success: GrowingSuccess record
        """
        try:
            # Save success record
            success_file = self.successes_dir / f"success_{success.unit_id}_{datetime.now().timestamp()}.json"
            with open(success_file, 'w') as f:
                json.dump(success.to_dict(), f, indent=2)
            
            # Update environment profile with success factors
            profile = self.get_profile(success.unit_id)
            if profile:
                # Extract key factors that led to success
                success_factors = self._extract_success_factors(success)
                
                # Add unique factors to profile
                for factor in success_factors:
                    if factor not in profile.success_factors:
                        profile.success_factors.append(factor)
                
                profile.updated_at = datetime.now()
                self._save_profile(profile)
            
            logger.info(f"Recorded successful grow for unit {success.unit_id}")
            
        except Exception as e:
            logger.error(f"Error recording success: {e}", exc_info=True)
    
    def get_personalized_recommendations(
        self,
        unit_id: int,
        plant_type: str,
        growth_stage: str,
        current_conditions: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Get personalized recommendations based on user's profile and history.
        
        Args:
            unit_id: Unit ID
            plant_type: Plant type
            growth_stage: Current growth stage
            current_conditions: Current environmental readings
            
        Returns:
            Personalized recommendations with explanations
        """
        profile = self.get_profile(unit_id)
        
        # Start with base recommendations
        recommendations = {
            'temperature': self._get_base_recommendation('temperature', plant_type, growth_stage),
            'humidity': self._get_base_recommendation('humidity', plant_type, growth_stage),
            'soil_moisture': self._get_base_recommendation('soil_moisture', plant_type, growth_stage),
            'personalization_notes': []
        }
        
        if not profile:
            recommendations['personalization_notes'].append(
                "Using general recommendations. Create profile for personalized advice."
            )
            return recommendations
        
        # Adjust based on environment profile
        adjustments = self._calculate_personalized_adjustments(
            profile, plant_type, growth_stage, current_conditions
        )
        
        for metric, adjustment in adjustments.items():
            if metric in recommendations:
                recommendations[metric] += adjustment
                if adjustment != 0:
                    recommendations['personalization_notes'].append(
                        f"Adjusted {metric} by {adjustment:+.1f} based on your environment"
                    )
        
        # Add success-based insights
        past_successes = self._get_past_successes(unit_id, plant_type)
        if past_successes:
            best_success = max(past_successes, key=lambda x: x.quality_rating)
            recommendations['personalization_notes'].append(
                f"Previously grew {plant_type} with {best_success.quality_rating}/5 rating. "
                f"Consider similar conditions."
            )
        
        # Add challenge-aware notes
        if profile.challenge_areas:
            for challenge in profile.challenge_areas:
                recommendations['personalization_notes'].append(
                    f"⚠️ Watch for {challenge} - this has been challenging in your environment"
                )
        
        return recommendations
    
    def get_similar_growers(
        self,
        unit_id: int,
        plant_type: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find growers with similar environments who succeeded with this plant type.
        
        Args:
            unit_id: User's unit ID
            plant_type: Plant type being grown
            limit: Maximum number of similar growers to return
            
        Returns:
            List of similar grower profiles and their success strategies
        """
        profile = self.get_profile(unit_id)
        if not profile:
            return []
        
        similar_growers = []
        
        # Scan all success records
        for success_file in self.successes_dir.glob("success_*.json"):
            try:
                with open(success_file, 'r') as f:
                    success_data = json.load(f)
                
                # Skip if different plant type
                if success_data['plant_type'] != plant_type:
                    continue
                
                # Skip if same unit (that's us!)
                if success_data['unit_id'] == unit_id:
                    continue
                
                # Calculate similarity score
                similarity = self._calculate_environment_similarity(
                    profile, success_data['growth_conditions']
                )
                
                if similarity > 0.6:  # 60% similarity threshold
                    similar_growers.append({
                        'similarity_score': similarity,
                        'success_data': success_data,
                        'key_conditions': self._extract_key_conditions(success_data)
                    })
            
            except Exception as e:
                logger.error(f"Error reading success file: {e}")
                continue
        
        # Sort by similarity and return top matches
        similar_growers.sort(key=lambda x: x['similarity_score'], reverse=True)
        return similar_growers[:limit]

    def _profile_matches(
        self,
        profile: PlantStageConditionProfile,
        *,
        plant_type: str,
        growth_stage: str,
        profile_id: Optional[str] = None,
        plant_variety: Optional[str],
        strain_variety: Optional[str],
        pot_size_liters: Optional[float],
        require_exact: bool = False,
    ) -> bool:
        if profile_id is not None and profile.profile_id != profile_id:
            return False
        if self._normalize(profile.plant_type) != self._normalize(plant_type):
            return False
        if self._normalize(profile.growth_stage) != self._normalize(growth_stage):
            return False
        if plant_variety and self._normalize(profile.plant_variety) != self._normalize(plant_variety):
            return False
        if strain_variety and self._normalize(profile.strain_variety) != self._normalize(strain_variety):
            return False
        if pot_size_liters is not None:
            if profile.pot_size_liters is None:
                return False if require_exact else True
            if abs(float(profile.pot_size_liters) - float(pot_size_liters)) > 0.1:
                return False
        if require_exact:
            if plant_variety is None and profile.plant_variety:
                return False
            if strain_variety is None and profile.strain_variety:
                return False
            if pot_size_liters is None and profile.pot_size_liters is not None:
                return False
        return True

    @staticmethod
    def _normalize(value: Optional[str]) -> str:
        return str(value or "").strip().lower()

    def _condition_profiles_path(self, user_id: int) -> Path:
        return self.condition_profiles_dir / f"user_{user_id}_condition_profiles.json"

    def _condition_profile_links_path(self, user_id: int) -> Path:
        return self.condition_profile_links_dir / f"user_{user_id}_condition_profile_links.json"

    def _load_condition_profiles(self, user_id: int) -> List[PlantStageConditionProfile]:
        if user_id in self._condition_profile_cache:
            return self._condition_profile_cache[user_id]
        path = self._condition_profiles_path(user_id)
        if not path.exists():
            self._condition_profile_cache[user_id] = []
            return []
        try:
            with open(path, "r") as fh:
                raw = json.load(fh) or []
            profiles = [PlantStageConditionProfile.from_dict(item) for item in raw]
            self._condition_profile_cache[user_id] = profiles
            return profiles
        except Exception as exc:
            logger.error("Failed to load condition profiles: %s", exc)
            return []

    def _save_condition_profiles(
        self, user_id: int, profiles: List[PlantStageConditionProfile]
    ) -> None:
        path = self._condition_profiles_path(user_id)
        payload = [profile.to_dict() for profile in profiles]
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as fh:
                json.dump(payload, fh, indent=2)
            tmp_path.replace(path)
        except Exception as exc:
            logger.error("Failed to save condition profiles: %s", exc)

    def _load_condition_profile_links(self, user_id: int) -> List[ConditionProfileLink]:
        if user_id in self._condition_profile_links_cache:
            return self._condition_profile_links_cache[user_id]
        path = self._condition_profile_links_path(user_id)
        if not path.exists():
            self._condition_profile_links_cache[user_id] = []
            return []
        try:
            with open(path, "r") as fh:
                raw = json.load(fh) or []
            links = [ConditionProfileLink.from_dict(item) for item in raw]
            self._condition_profile_links_cache[user_id] = links
            return links
        except Exception as exc:
            logger.error("Failed to load condition profile links: %s", exc)
            return []

    def _save_condition_profile_links(
        self, user_id: int, links: List[ConditionProfileLink]
    ) -> None:
        path = self._condition_profile_links_path(user_id)
        payload = [link.to_dict() for link in links]
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as fh:
                json.dump(payload, fh, indent=2)
            tmp_path.replace(path)
        except Exception as exc:
            logger.error("Failed to save condition profile links: %s", exc)

    def _save_shared_profile_snapshot(self, token: str, payload: Dict[str, Any]) -> None:
        path = self.shared_profiles_dir / f"{token}.json"
        tmp_path = path.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as fh:
                json.dump(payload, fh, indent=2)
            tmp_path.replace(path)
        except Exception as exc:
            logger.error("Failed to save shared profile snapshot: %s", exc)

    def _update_shared_index(self, payload: Dict[str, Any]) -> None:
        index: List[Dict[str, Any]] = []
        if self.shared_profiles_index.exists():
            try:
                with open(self.shared_profiles_index, "r") as fh:
                    index = json.load(fh) or []
            except Exception:
                index = []
        entry = {
            "profile_id": payload.get("profile_id"),
            "name": payload.get("name"),
            "image_url": payload.get("image_url"),
            "plant_type": payload.get("plant_type"),
            "growth_stage": payload.get("growth_stage"),
            "plant_variety": payload.get("plant_variety"),
            "strain_variety": payload.get("strain_variety"),
            "pot_size_liters": payload.get("pot_size_liters"),
            "mode": payload.get("mode"),
            "visibility": payload.get("visibility"),
            "shared_token": payload.get("shared_token"),
            "shared_at": payload.get("shared_at"),
            "source_profile_id": payload.get("source_profile_id"),
            "source_profile_name": payload.get("source_profile_name"),
            "tags": payload.get("tags"),
            "rating_avg": payload.get("rating_avg"),
            "rating_count": payload.get("rating_count"),
        }
        index = [item for item in index if item.get("profile_id") != entry["profile_id"]]
        index.append(entry)
        tmp_path = self.shared_profiles_index.with_suffix(".tmp")
        try:
            with open(tmp_path, "w") as fh:
                json.dump(index, fh, indent=2)
            tmp_path.replace(self.shared_profiles_index)
        except Exception as exc:
            logger.error("Failed to update shared profile index: %s", exc)
    
    def _analyze_historical_patterns(self, unit_id: int) -> Dict[str, Any]:
        """Analyze historical data to find patterns."""
        import pandas as pd  # Lazy load

        try:
            # Get 90 days of data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)

            df = self.training_data_repo.get_sensor_data_range(
                unit_id,
                start_date.isoformat(),
                end_date.isoformat()
            )

            if df.empty:
                return {}

            patterns = {}

            # Identify daily cycles
            if 'temperature' in df.columns:
                df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
                hourly_avg = df.groupby('hour')['temperature'].mean()
                patterns['daily_temp_cycle'] = {
                    'min_hour': int(hourly_avg.idxmin()),
                    'max_hour': int(hourly_avg.idxmax()),
                    'range': float(hourly_avg.max() - hourly_avg.min())
                }
            
            # Identify stability characteristics
            for col in ['temperature', 'humidity', 'soil_moisture']:
                if col in df.columns:
                    patterns[f'{col}_stability'] = {
                        'mean': float(df[col].mean()),
                        'std': float(df[col].std()),
                        'coefficient_of_variation': float(df[col].std() / df[col].mean())
                    }
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}")
            return {}
    
    def _detect_location_characteristics(self, unit_id: int) -> Dict[str, Any]:
        """Detect unique location characteristics."""
        # This would integrate with external APIs or user input
        # For now, return placeholder
        return {
            'climate_zone': 'temperate',
            'indoor_outdoor': 'indoor',
            'natural_light_available': False,
            'ambient_temp_stable': True
        }
    
    def _profile_equipment(self, unit_id: int) -> Dict[str, Any]:
        """Profile the equipment setup."""
        # Would query device inventory and capabilities
        return {
            'has_automated_watering': True,
            'has_climate_control': True,
            'has_co2_injection': False,
            'lighting_type': 'LED',
            'sensor_accuracy': 'high'
        }
    
    def _save_profile(self, profile: EnvironmentProfile):
        """Save profile to disk."""
        profile_file = self.profiles_dir / f"unit_{profile.unit_id}_profile.json"
        with open(profile_file, 'w') as f:
            json.dump(profile.to_dict(), f, indent=2)
    
    def _extract_success_factors(self, success: GrowingSuccess) -> List[str]:
        """Extract key factors that contributed to success."""
        factors = []
        
        # Analyze conditions
        conditions = success.growth_conditions
        
        # Check for optimal ranges
        if conditions.get('temperature_stability', 0) < 2.0:
            factors.append('stable_temperature')
        
        if conditions.get('consistent_watering', False):
            factors.append('consistent_watering')
        
        if success.quality_rating >= 4:
            factors.append('high_quality_outcome')
        
        # Add user-provided lessons
        factors.extend(success.lessons_learned)
        
        return factors
    
    def _get_past_successes(
        self,
        unit_id: int,
        plant_type: str
    ) -> List[GrowingSuccess]:
        """Get past successful grows for this unit and plant type."""
        successes = []
        
        for success_file in self.successes_dir.glob(f"success_{unit_id}_*.json"):
            try:
                with open(success_file, 'r') as f:
                    data = json.load(f)
                    if data['plant_type'] == plant_type:
                        success = GrowingSuccess(
                            user_id=data['user_id'],
                            unit_id=data['unit_id'],
                            plant_type=data['plant_type'],
                            plant_variety=data.get('plant_variety'),
                            start_date=datetime.fromisoformat(data['start_date']),
                            harvest_date=datetime.fromisoformat(data['harvest_date']),
                            total_yield=data.get('total_yield'),
                            quality_rating=data['quality_rating'],
                            growth_conditions=data['growth_conditions'],
                            lessons_learned=data['lessons_learned'],
                            would_repeat=data['would_repeat']
                        )
                        successes.append(success)
            except Exception as e:
                logger.error(f"Error loading success: {e}")
        
        return successes
    
    def _calculate_personalized_adjustments(
        self,
        profile: EnvironmentProfile,
        plant_type: str,
        growth_stage: str,
        current_conditions: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate adjustments based on user's environment."""
        adjustments = {
            'temperature': 0.0,
            'humidity': 0.0,
            'soil_moisture': 0.0
        }
        
        # Adjust for historical patterns
        if 'temperature_stability' in profile.historical_patterns:
            stability = profile.historical_patterns['temperature_stability']
            if stability['std'] > 3.0:
                # Unstable temps - aim slightly higher to accommodate fluctuations
                adjustments['temperature'] = 1.0
        
        # Adjust for equipment capabilities
        if not profile.equipment_profile.get('has_climate_control'):
            # Without climate control, be more conservative
            adjustments['humidity'] = -5.0
        
        return adjustments
    
    def _get_base_recommendation(
        self,
        metric: str,
        plant_type: str,
        growth_stage: str
    ) -> float:
        """Get base recommendation from general knowledge."""
        # This would query the growth predictor or climate optimizer
        defaults = {
            'temperature': {'Germination': 22, 'Vegetative': 24, 'Flowering': 23},
            'humidity': {'Germination': 75, 'Vegetative': 65, 'Flowering': 60},
            'soil_moisture': {'Germination': 85, 'Vegetative': 75, 'Flowering': 70}
        }
        
        return defaults.get(metric, {}).get(growth_stage, 0)
    
    def _calculate_environment_similarity(
        self,
        profile: EnvironmentProfile,
        conditions: Dict[str, Any]
    ) -> float:
        """Calculate similarity between two environments."""
        # Simple similarity based on key characteristics
        similarity_score = 0.0
        comparison_points = 0
        
        # Compare equipment
        if profile.equipment_profile.get('lighting_type') == conditions.get('lighting_type'):
            similarity_score += 0.3
        comparison_points += 1
        
        # Compare climate control capability
        if profile.equipment_profile.get('has_climate_control') == conditions.get('has_climate_control'):
            similarity_score += 0.2
        comparison_points += 1
        
        # Compare location characteristics
        if profile.location_characteristics.get('climate_zone') == conditions.get('climate_zone'):
            similarity_score += 0.3
        comparison_points += 1
        
        return similarity_score
    
    def _extract_key_conditions(self, success_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key conditions from success data."""
        conditions = success_data.get('growth_conditions', {})
        return {
            'avg_temperature': conditions.get('avg_temperature'),
            'avg_humidity': conditions.get('avg_humidity'),
            'lighting_hours': conditions.get('lighting_hours'),
            'watering_frequency': conditions.get('watering_frequency')
        }
