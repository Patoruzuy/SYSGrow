from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.utils.time import iso_now

logger = logging.getLogger(__name__)


class PlantConditionProfileRepository:
    """Repository for plant condition profile persistence."""

    def __init__(self, backend) -> None:
        self._db = backend

    @staticmethod
    def _normalize_text(value: Optional[str]) -> str:
        if not value:
            return ""
        return str(value).strip().lower()

    def build_profile_key(
        self,
        *,
        user_id: int,
        plant_type: str,
        growth_stage: str,
        cultivar: Optional[str] = None,
        strain: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> str:
        pot_value = float(pot_size_liters or 0.0)
        return "|".join([
            str(user_id),
            self._normalize_text(plant_type),
            self._normalize_text(growth_stage),
            self._normalize_text(cultivar),
            self._normalize_text(strain),
            f"{pot_value:.2f}",
        ])

    def get_profile(
        self,
        *,
        user_id: int,
        plant_type: str,
        growth_stage: str,
        cultivar: Optional[str] = None,
        strain: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        key = self.build_profile_key(
            user_id=user_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            cultivar=cultivar,
            strain=strain,
            pot_size_liters=pot_size_liters,
        )
        return self._db.get_condition_profile_by_key(key)

    def list_profiles(
        self,
        *,
        user_id: int,
        plant_type: Optional[str] = None,
        growth_stage: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        return self._db.list_condition_profiles(
            user_id=user_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            limit=limit,
        )

    def upsert_profile(
        self,
        *,
        user_id: int,
        plant_type: str,
        growth_stage: str,
        cultivar: Optional[str] = None,
        strain: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
        temperature_target: Optional[float] = None,
        humidity_target: Optional[float] = None,
        co2_target: Optional[float] = None,
        voc_target: Optional[float] = None,
        lux_target: Optional[float] = None,
        air_quality_target: Optional[float] = None,
        soil_moisture_target: Optional[float] = None,
        confidence: Optional[float] = None,
        source: Optional[str] = None,
    ) -> bool:
        key = self.build_profile_key(
            user_id=user_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            cultivar=cultivar,
            strain=strain,
            pot_size_liters=pot_size_liters,
        )
        stamp = iso_now()
        return self._db.upsert_condition_profile(
            profile_key=key,
            user_id=user_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            cultivar=cultivar or "",
            strain=strain or "",
            pot_size_liters=float(pot_size_liters or 0.0),
            temperature_target=temperature_target,
            humidity_target=humidity_target,
            co2_target=co2_target,
            voc_target=voc_target,
            lux_target=lux_target,
            air_quality_target=air_quality_target,
            soil_moisture_target=soil_moisture_target,
            confidence=confidence,
            source=source,
            created_at_utc=stamp,
            updated_at_utc=stamp,
        )

    def add_rating(
        self,
        *,
        user_id: int,
        plant_type: str,
        growth_stage: str,
        rating: float,
        cultivar: Optional[str] = None,
        strain: Optional[str] = None,
        pot_size_liters: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        profile = self.get_profile(
            user_id=user_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            cultivar=cultivar,
            strain=strain,
            pot_size_liters=pot_size_liters,
        )
        if not profile:
            return None

        current_sum = float(profile.get("rating_sum") or 0.0)
        current_count = int(profile.get("rating_count") or 0)
        new_sum = current_sum + float(rating)
        new_count = current_count + 1
        confidence = min(1.0, new_count / 10.0)

        key = profile.get("profile_key")
        if not key:
            key = self.build_profile_key(
                user_id=user_id,
                plant_type=plant_type,
                growth_stage=growth_stage,
                cultivar=cultivar,
                strain=strain,
                pot_size_liters=pot_size_liters,
            )

        updated = self._db.update_condition_profile_rating(
            profile_key=key,
            rating_sum=new_sum,
            rating_count=new_count,
            confidence=confidence,
            updated_at_utc=iso_now(),
        )
        if not updated:
            return None

        profile["rating_sum"] = new_sum
        profile["rating_count"] = new_count
        profile["confidence"] = confidence
        profile["updated_at_utc"] = iso_now()
        return profile
