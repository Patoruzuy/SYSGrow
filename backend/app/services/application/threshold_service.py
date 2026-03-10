"""
Threshold Service
=================
Manages plant-specific environmental thresholds using Domain-Driven Design.

Returns immutable EnvironmentalThresholds domain objects for type safety and validation.
Integrates with AI predictions for optimal environmental conditions.

This service is the single source of truth for all threshold-related operations:
- Unit thresholds (persisted to Units table)
- Plant override thresholds (per-plant customization)
- AI-proposed threshold updates
- Threshold filtering and validation
- Event handling for threshold persistence
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable

from app.constants import NIGHT_THRESHOLD_ADJUSTMENTS, THRESHOLD_UPDATE_TOLERANCE
from app.domain.environmental_thresholds import EnvironmentalThresholds
from app.enums.common import ConditionProfileMode, ConditionProfileTarget
from app.enums.events import RuntimeEvent
from app.schemas.events import ThresholdsPersistPayload
from app.utils.cache import TTLCache
from app.utils.plant_json_handler import PlantJsonHandler

if TYPE_CHECKING:
    from app.enums.common import ConditionProfileMode
    from app.services.ai.climate_optimizer import ClimateOptimizer
    from app.services.ai.personalized_learning import PersonalizedLearningService
    from app.services.application.notifications_service import NotificationsService
    from app.utils.event_bus import EventBus
    from infrastructure.database.repositories.growth import GrowthRepository

logger = logging.getLogger(__name__)

THRESHOLD_KEYS = (
    "temperature_threshold",
    "humidity_threshold",
    "co2_threshold",
    "voc_threshold",
    "lux_threshold",
    "air_quality_threshold",
)

PLANT_OVERRIDE_FIELDS = {
    "temperature_threshold": "temperature_threshold_override",
    "humidity_threshold": "humidity_threshold_override",
    "co2_threshold": "co2_threshold_override",
    "voc_threshold": "voc_threshold_override",
    "lux_threshold": "lux_threshold_override",
    "air_quality_threshold": "air_quality_threshold_override",
}


class ThresholdService:
    """
    Manages plant-specific environmental thresholds using domain objects.

    All methods return EnvironmentalThresholds domain objects for:
    - Type safety (IDE autocomplete, type checking)
    - Validation (ranges checked automatically)
    - Immutability (frozen dataclass)
    - Clean API (to_dict(), with_X(), merge())

    This service also handles:
    - Threshold event handling (THRESHOLDS_PERSIST, THRESHOLDS_PROPOSED)
    - Threshold change filtering with tolerance
    - User confirmation of AI-proposed thresholds
    """

    def __init__(
        self,
        plant_handler: PlantJsonHandler | None = None,
        climate_optimizer: "ClimateOptimizer" | None = None,
        growth_repo: "GrowthRepository" | None = None,
        notifications_service: "NotificationsService" | None = None,
        event_bus: "EventBus" | None = None,
        personalized_learning: "PersonalizedLearningService" | None = None,
    ):
        """
        Initialize threshold service.

        Args:
            plant_handler: Optional PlantJsonHandler instance (creates new if None)
            climate_optimizer: Optional ClimateOptimizer service for AI predictions
            growth_repo: Optional GrowthRepository for persistence
            notifications_service: Optional NotificationsService for threshold proposals
            event_bus: Optional EventBus for subscribing to threshold events
        """
        self.plant_handler = plant_handler or PlantJsonHandler()
        self.climate_optimizer = climate_optimizer
        self.growth_repo = growth_repo
        self.notifications_service = notifications_service
        self.event_bus = event_bus
        self.personalized_learning = personalized_learning
        self._threshold_cache = TTLCache(enabled=True, ttl_seconds=300, maxsize=256)
        self._unit_threshold_cache = TTLCache(enabled=True, ttl_seconds=300, maxsize=128)
        self._plant_override_cache = TTLCache(enabled=True, ttl_seconds=300, maxsize=256)

        # Generic fallback thresholds as domain object
        self.generic_thresholds = EnvironmentalThresholds(
            temperature=24.0, humidity=55.0, soil_moisture=50.0, co2=1000.0, voc=1000.0, lux=1000.0, air_quality=100.0
        )

        # Optional callback to invalidate unit cache (set by GrowthService)
        self._invalidate_unit_cache_callback: Callable[[int], None] | None = None

        logger.info("ThresholdService initialized")

    # ==================== Event Handling ====================

    def subscribe_to_events(self) -> None:
        """Subscribe to runtime events for threshold persistence."""
        if self.event_bus:
            self.event_bus.subscribe(RuntimeEvent.THRESHOLDS_PERSIST, self._handle_thresholds_persist)
            logger.debug("ThresholdService subscribed to RuntimeEvent.THRESHOLDS_PERSIST")

    def set_cache_invalidation_callback(self, callback: Callable[[int], None]) -> None:
        """
        Set callback to invalidate unit cache after threshold persistence.

        Args:
            callback: Function accepting unit_id to invalidate cache
        """
        self._invalidate_unit_cache_callback = callback

    def set_personalized_learning(self, service: "PersonalizedLearningService" | None) -> None:
        """Wire PersonalizedLearningService after initialization."""
        self.personalized_learning = service

    def get_condition_profile(
        self,
        *,
        user_id: int | None,
        plant_type: str,
        growth_stage: str | None,
        profile_id: str | None = None,
        preferred_mode: "ConditionProfileMode" | None = None,
        plant_variety: str | None = None,
        strain_variety: str | None = None,
        pot_size_liters: float | None = None,
    ) -> dict[str, Any] | None:
        if not user_id:
            return None
        if not profile_id and (not plant_type or not growth_stage):
            return None
        if not self.personalized_learning:
            return None
        profile = self.personalized_learning.get_condition_profile(
            user_id=user_id,
            plant_type=plant_type,
            growth_stage=growth_stage,
            profile_id=profile_id,
            preferred_mode=preferred_mode,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )
        return profile.to_dict() if profile else None

    def _handle_thresholds_persist(self, payload: ThresholdsPersistPayload) -> None:
        """
        Handle RuntimeEvent.THRESHOLDS_PERSIST from UnitRuntime.

        Persists thresholds to database when emitted by UnitRuntime.
        """
        try:
            if isinstance(payload, dict):
                unit_id = payload.get("unit_id")
                thresholds = payload.get("thresholds", {})
            else:
                unit_id = payload.unit_id
                thresholds = payload.thresholds

            if unit_id is None or not thresholds:
                return

            # Persist thresholds to database
            repo_fields: dict[str, float] = {}
            for key in THRESHOLD_KEYS:
                if key in thresholds:
                    repo_fields[key] = thresholds[key]

            if repo_fields:
                persisted = self.update_unit_thresholds(unit_id, repo_fields)
                if persisted:
                    # Notify GrowthService to invalidate its cache
                    if self._invalidate_unit_cache_callback:
                        self._invalidate_unit_cache_callback(unit_id)
                    logger.debug(
                        "Persisted thresholds for unit %s: %s",
                        unit_id,
                        list(repo_fields.keys()),
                    )

        except Exception as e:
            logger.error("Error handling THRESHOLDS_PERSIST event: %s", e, exc_info=True)

    # ==================== Threshold Filtering ====================

    def filter_threshold_changes(
        self,
        current_thresholds: dict[str, Any],
        proposed_thresholds: dict[str, Any],
    ) -> tuple[dict[str, float], dict[str, float]]:
        """
        Filter threshold changes based on tolerance.

        Only returns changes that exceed the tolerance defined in THRESHOLD_UPDATE_TOLERANCE.
        This prevents minor fluctuations from triggering threshold updates.

        Args:
            current_thresholds: Current threshold values
            proposed_thresholds: Proposed new threshold values

        Returns:
            Tuple of (filtered_current, filtered_proposed) dictionaries
        """
        filtered_current: dict[str, float] = {}
        filtered_proposed: dict[str, float] = {}

        for key in THRESHOLD_KEYS:
            if key not in proposed_thresholds:
                continue
            try:
                proposed_value = float(proposed_thresholds[key])
            except (TypeError, ValueError):
                continue

            current_value = current_thresholds.get(key)
            if current_value is None:
                filtered_proposed[key] = proposed_value
                continue

            try:
                current_value_float = float(current_value)
            except (TypeError, ValueError):
                filtered_proposed[key] = proposed_value
                continue

            tolerance = THRESHOLD_UPDATE_TOLERANCE.get(key, 0.0)
            if abs(proposed_value - current_value_float) >= tolerance:
                filtered_current[key] = current_value_float
                filtered_proposed[key] = proposed_value

        return filtered_current, filtered_proposed

    def _filter_threshold_payload(self, thresholds: dict[str, Any]) -> dict[str, float]:
        """Filter and coerce threshold payloads to allowed keys."""
        if "lux_threshold" not in thresholds:
            if "lux_threshold" in thresholds:
                thresholds = dict(thresholds)
                thresholds["lux_threshold"] = thresholds.get("lux_threshold")
            elif "light_threshold" in thresholds:
                thresholds = dict(thresholds)
                thresholds["lux_threshold"] = thresholds.get("light_threshold")
            elif "lux" in thresholds:
                thresholds = dict(thresholds)
                thresholds["lux_threshold"] = thresholds.get("lux")
        payload: dict[str, float] = {}
        for key in THRESHOLD_KEYS:
            if key not in thresholds:
                continue
            value = thresholds.get(key)
            if value is None:
                continue
            try:
                payload[key] = float(value)
            except (TypeError, ValueError):
                logger.debug("Skipping invalid threshold %s=%s", key, value)
        return payload

    def _coerce_threshold(
        self,
        data: dict[str, Any],
        keys: tuple[str, ...],
        *,
        default: float,
        min_value: float,
        max_value: float,
    ) -> float:
        value = None
        for key in keys:
            if key in data and data[key] is not None:
                try:
                    value = float(data[key])
                    break
                except (TypeError, ValueError):
                    value = None
                    break
        if value is None:
            value = default
        if value < min_value:
            return min_value
        if value > max_value:
            return max_value
        return value

    def _sanitize_unit_thresholds(self, data: dict[str, Any]) -> dict[str, float]:
        """Clamp persisted thresholds to valid ranges for safe domain construction."""
        return {
            "temperature_threshold": self._coerce_threshold(
                data,
                ("temperature_threshold", "temperature"),
                default=24.0,
                min_value=-50.0,
                max_value=100.0,
            ),
            "humidity_threshold": self._coerce_threshold(
                data,
                ("humidity_threshold", "humidity"),
                default=50.0,
                min_value=0.0,
                max_value=100.0,
            ),
            "co2_threshold": self._coerce_threshold(
                data,
                ("co2_threshold", "co2"),
                default=1000.0,
                min_value=0.0,
                max_value=5000.0,
            ),
            "voc_threshold": self._coerce_threshold(
                data,
                ("voc_threshold", "voc"),
                default=1000.0,
                min_value=0.0,
                max_value=10000.0,
            ),
            "lux_threshold": self._coerce_threshold(
                data,
                ("lux_threshold", "light_threshold", "lux"),
                default=1000.0,
                min_value=0.0,
                max_value=100000.0,
            ),
            "air_quality_threshold": self._coerce_threshold(
                data,
                ("air_quality_threshold", "air_quality", "aqi_threshold", "aqi"),
                default=100.0,
                min_value=0.0,
                max_value=500.0,
            ),
        }

    def get_unit_thresholds(self, unit_id: int) -> EnvironmentalThresholds | None:
        """Fetch unit thresholds from persistence."""
        if not self.growth_repo:
            return None
        cached = self._unit_threshold_cache.get(unit_id)
        if isinstance(cached, EnvironmentalThresholds):
            return cached
        try:
            row = self.growth_repo.get_unit(unit_id)
            if not row:
                return None
            data = row if isinstance(row, dict) else {k: row[k] for k in row.keys()}  # noqa: SIM118
            try:
                thresholds = EnvironmentalThresholds.from_dict(data)
            except ValueError as exc:
                sanitized = self._sanitize_unit_thresholds(data)
                thresholds = EnvironmentalThresholds.from_dict(sanitized)
                self._unit_threshold_cache.set(unit_id, thresholds)
                try:
                    self.growth_repo.update_unit(unit_id, **sanitized)
                except Exception:
                    logger.debug(
                        "Failed to persist sanitized thresholds for unit %s",
                        unit_id,
                        exc_info=True,
                    )
                logger.warning(
                    "Clamped invalid thresholds for unit %s: %s",
                    unit_id,
                    exc,
                )
                return thresholds
            self._unit_threshold_cache.set(unit_id, thresholds)
            return thresholds
        except Exception as exc:
            logger.error("Error fetching unit thresholds for %s: %s", unit_id, exc, exc_info=True)
            return None

    def get_unit_thresholds_dict(self, unit_id: int) -> dict[str, float]:
        """Return unit thresholds in settings dict format."""
        thresholds = self.get_unit_thresholds(unit_id)
        if not thresholds:
            return {}
        data = thresholds.to_settings_dict()
        data.pop("soil_moisture_threshold", None)
        return data

    def update_unit_thresholds(self, unit_id: int, thresholds: dict[str, Any]) -> bool:
        """Persist unit thresholds (single source of truth for DB writes)."""
        if not self.growth_repo:
            logger.warning("GrowthRepository not available; cannot persist thresholds for unit %s", unit_id)
            return False
        payload = self._filter_threshold_payload(thresholds)
        if not payload:
            return False
        try:
            self.growth_repo.update_unit(unit_id, **payload)
            cached = self._unit_threshold_cache.get(unit_id)
            if cached:
                self._unit_threshold_cache.set(unit_id, cached.merge(payload))
            else:
                self._unit_threshold_cache.invalidate(unit_id)
            if self.personalized_learning:
                try:
                    unit = self.growth_repo.get_unit(unit_id)
                    user_id = unit.get("user_id") if unit else None
                    if user_id:
                        link = self.personalized_learning.get_condition_profile_link(
                            user_id=int(user_id),
                            target_type=ConditionProfileTarget.UNIT,
                            target_id=int(unit_id),
                        )
                        if link and link.mode == ConditionProfileMode.ACTIVE:
                            profile = self.personalized_learning.get_condition_profile_by_id(
                                user_id=int(user_id),
                                profile_id=link.profile_id,
                            )
                            if profile:
                                self.personalized_learning.upsert_condition_profile(
                                    user_id=int(user_id),
                                    profile_id=link.profile_id,
                                    plant_type=profile.plant_type,
                                    growth_stage=profile.growth_stage,
                                    environment_thresholds=payload,
                                    plant_variety=profile.plant_variety,
                                    strain_variety=profile.strain_variety,
                                    pot_size_liters=profile.pot_size_liters,
                                )
                except Exception:
                    logger.debug("Failed to update linked condition profile for unit %s", unit_id, exc_info=True)
            return True
        except Exception as exc:
            logger.error("Failed to persist thresholds for unit %s: %s", unit_id, exc, exc_info=True)
            return False

    def get_plant_overrides(self, plant_id: int) -> dict[str, float]:
        """Fetch per-plant override thresholds from persistence."""
        if not self.growth_repo:
            return {}
        cached = self._plant_override_cache.get(plant_id)
        if isinstance(cached, dict):
            return dict(cached)
        try:
            row = self.growth_repo.get_plant(plant_id)
            if not row:
                return {}
            data = row if isinstance(row, dict) else {k: row[k] for k in row.keys()}  # noqa: SIM118
            overrides: dict[str, float] = {}
            for key, field in PLANT_OVERRIDE_FIELDS.items():
                value = data.get(field)
                if value is None:
                    continue
                try:
                    overrides[key] = float(value)
                except (TypeError, ValueError):
                    logger.debug("Skipping invalid override %s=%s", field, value)
            self._plant_override_cache.set(plant_id, dict(overrides))
            return overrides
        except Exception as exc:
            logger.error("Error fetching overrides for plant %s: %s", plant_id, exc, exc_info=True)
            return {}

    def update_plant_overrides(self, plant_id: int, thresholds: dict[str, Any]) -> bool:
        """Persist per-plant threshold overrides."""
        if not self.growth_repo:
            logger.warning("GrowthRepository not available; cannot persist overrides for plant %s", plant_id)
            return False
        payload = self._filter_threshold_payload(thresholds)
        if not payload:
            return False
        overrides = {PLANT_OVERRIDE_FIELDS[key]: value for key, value in payload.items()}
        try:
            self.growth_repo.update_plant(plant_id, **overrides)
            self._plant_override_cache.set(plant_id, dict(payload))
            return True
        except Exception as exc:
            logger.error("Failed to persist overrides for plant %s: %s", plant_id, exc, exc_info=True)
            return False

    def get_environment_thresholds(self, unit_id: int | None = None) -> dict[str, Any] | None:
        """
        Fetch environment thresholds for a unit.

        Note: Global settings are deprecated; unit thresholds live in GrowthUnits.
        """
        if unit_id is None:
            return None
        data = self.get_unit_thresholds_dict(unit_id)
        return data or None

    def update_environment_thresholds(
        self,
        *,
        unit_id: int,
        thresholds: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Persist environment thresholds for a unit.

        Soil moisture is managed per-plant and excluded here.
        """
        if unit_id is None:
            return None
        if not self.update_unit_thresholds(unit_id, thresholds):
            return None
        return self.get_unit_thresholds_dict(unit_id)

    def get_thresholds(
        self,
        plant_type: str,
        growth_stage: str | None = None,
        *,
        user_id: int | None = None,
        profile_id: str | None = None,
        preferred_mode: "ConditionProfileMode" | None = None,
        plant_variety: str | None = None,
        strain_variety: str | None = None,
        pot_size_liters: float | None = None,
    ) -> EnvironmentalThresholds:
        """
        Get environmental thresholds as immutable domain object.

        Args:
            plant_type: Common name of the plant (e.g., 'Tomatoes', 'Lettuce')
            growth_stage: Growth stage name (e.g., 'Vegetative', 'Flowering')
                         If None, returns averaged thresholds across all stages

        Returns:
            EnvironmentalThresholds domain object with validated thresholds
        """
        cache_key = f"thresholds_{plant_type}_{growth_stage or 'all'}_{user_id}_{profile_id}_{preferred_mode}_{plant_variety}_{strain_variety}_{pot_size_liters}"

        # Check cache first
        cached = self._threshold_cache.get(cache_key)
        if cached is not None and isinstance(cached, EnvironmentalThresholds):
            return cached

        try:
            profile = self.get_condition_profile(
                user_id=user_id,
                plant_type=plant_type,
                growth_stage=growth_stage or "",
                profile_id=profile_id,
                preferred_mode=preferred_mode,
                plant_variety=plant_variety,
                strain_variety=strain_variety,
                pot_size_liters=pot_size_liters,
            )

            # Search for plant by common name
            plants = self.plant_handler.search_plants(common_name=plant_type)
            thresholds = self.generic_thresholds
            if plants:
                plant = plants[0]
                # Extract optimal values from plant data
                thresholds = self._extract_optimal_thresholds(plant, growth_stage)

            # Apply profile overrides if available
            if profile:
                merged = thresholds.to_settings_dict()
                merged.update(profile.get("environment_thresholds", {}))
                if profile.get("soil_moisture_threshold") is not None:
                    merged["soil_moisture_threshold"] = profile["soil_moisture_threshold"]
                thresholds = EnvironmentalThresholds.from_dict(merged)

            # Cache and return
            self._threshold_cache.set(cache_key, thresholds)
            return thresholds

        except Exception as e:
            logger.error("Error loading thresholds for %s: %s", plant_type, e)
            return self.generic_thresholds

    def get_thresholds_for_period(
        self,
        plant_type: str,
        growth_stage: str | None = None,
        *,
        is_daytime: bool = True,
        user_id: int | None = None,
        profile_id: str | None = None,
        preferred_mode: "ConditionProfileMode" | None = None,
        plant_variety: str | None = None,
        strain_variety: str | None = None,
        pot_size_liters: float | None = None,
    ) -> EnvironmentalThresholds:
        """
        Get environmental thresholds adjusted for the current photoperiod.

        During the day the base thresholds are returned as-is.
        At night, default adjustments from ``NIGHT_THRESHOLD_ADJUSTMENTS``
        are applied (temperature drops, humidity rises, lux goes to 0)
        unless the user's condition profile already provides explicit
        ``night_environment_thresholds``.

        Args:
            plant_type: Common name of the plant (e.g. 'Tomatoes')
            growth_stage: Current growth stage (e.g. 'Vegetative')
            is_daytime: ``True`` for light-on period, ``False`` for dark period
            user_id / profile_id / preferred_mode / plant_variety /
            strain_variety / pot_size_liters: Forwarded to ``get_thresholds``.

        Returns:
            EnvironmentalThresholds adjusted for the requested period.
        """
        base = self.get_thresholds(
            plant_type,
            growth_stage,
            user_id=user_id,
            profile_id=profile_id,
            preferred_mode=preferred_mode,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )

        if is_daytime:
            return base

        # --- Night adjustment -------------------------------------------------
        # 1) Check if the user's condition profile has explicit night thresholds.
        profile = self.get_condition_profile(
            user_id=user_id,
            plant_type=plant_type,
            growth_stage=growth_stage or "",
            profile_id=profile_id,
            preferred_mode=preferred_mode,
            plant_variety=plant_variety,
            strain_variety=strain_variety,
            pot_size_liters=pot_size_liters,
        )

        if profile and profile.get("night_environment_thresholds"):
            night_env = profile["night_environment_thresholds"]
            merged = base.to_settings_dict()
            merged.update(night_env)
            try:
                return EnvironmentalThresholds.from_dict(merged)
            except ValueError:
                logger.warning(
                    "Invalid night thresholds in profile for %s/%s; using default adjustments",
                    plant_type,
                    growth_stage,
                )

        # 2) Apply default night adjustments from constants.
        night_temp = base.temperature + NIGHT_THRESHOLD_ADJUSTMENTS.get("temperature", -3.0)
        night_humidity = min(
            100.0,
            base.humidity + NIGHT_THRESHOLD_ADJUSTMENTS.get("humidity", 5.0),
        )
        night_lux = NIGHT_THRESHOLD_ADJUSTMENTS.get("lux", 0.0)

        return EnvironmentalThresholds(
            temperature=night_temp,
            humidity=night_humidity,
            soil_moisture=base.soil_moisture,
            co2=base.co2,
            voc=base.voc,
            lux=night_lux,
            air_quality=base.air_quality,
        )

    def _extract_optimal_thresholds(self, plant: dict, growth_stage: str | None = None) -> EnvironmentalThresholds:
        """
        Extract optimal threshold values from plant data.

        Returns the midpoint of optimal ranges as target values.
        """
        growth_stages = plant.get("growth_stages", [])

        if not growth_stages:
            return self.generic_thresholds

        # Filter to specific stage if provided
        if growth_stage:
            target_stage = None
            for stage in growth_stages:
                if stage.get("stage", "").lower() == growth_stage.lower():
                    target_stage = stage
                    break
            stages_to_use = [target_stage] if target_stage else growth_stages
        else:
            stages_to_use = growth_stages

        # Collect threshold values across stages
        temp_values = []
        humidity_values = []
        moisture_values = []

        for stage in stages_to_use:
            conditions = stage.get("conditions", {})
            sensor_targets = stage.get("sensor_targets", {})

            # Temperature from conditions
            temp_range = conditions.get("temperature_C", {})
            if temp_range.get("min") and temp_range.get("max"):
                temp_values.append((temp_range["min"] + temp_range["max"]) / 2)

            # Humidity from conditions
            humidity_range = conditions.get("humidity_percent", {})
            if humidity_range.get("min") and humidity_range.get("max"):
                humidity_values.append((humidity_range["min"] + humidity_range["max"]) / 2)

            # Soil moisture from sensor_targets
            if "soil_moisture" in sensor_targets:
                moisture_values.append(sensor_targets["soil_moisture"])

        # Get CO2 from plant-level sensor requirements
        sensor_reqs = plant.get("sensor_requirements", {})
        co2_reqs = sensor_reqs.get("co2_requirements", {})
        co2_value = 1000.0
        if co2_reqs.get("min") and co2_reqs.get("max"):
            co2_value = (co2_reqs["min"] + co2_reqs["max"]) / 2

        # Calculate averages
        temperature = sum(temp_values) / len(temp_values) if temp_values else 24.0
        humidity = sum(humidity_values) / len(humidity_values) if humidity_values else 55.0
        soil_moisture = sum(moisture_values) / len(moisture_values) if moisture_values else 50.0

        # Create domain value object with optimal target values
        return EnvironmentalThresholds(
            temperature=temperature,
            humidity=humidity,
            soil_moisture=soil_moisture,
            co2=co2_value,
            voc=1000.0,  # Default values for sensors not in plant data
            lux=10000.0,  # Will be enhanced in future
            air_quality=100.0,
        )

    def get_plant_growth_stages(self, plant_type: str) -> list[str]:
        """
        Get list of growth stage names for a plant type.

        Args:
            plant_type: Common name of the plant

        Returns:
            List of growth stage names
        """
        try:
            plants = self.plant_handler.search_plants(common_name=plant_type)

            if not plants:
                return []

            plant = plants[0]
            growth_stages = plant.get("growth_stages", [])

            return [stage.get("stage") for stage in growth_stages if stage.get("stage")]

        except Exception as e:
            logger.error("Error getting growth stages for %s: %s", plant_type, e)
            return []

    def get_threshold_ranges(
        self,
        plant_type: str,
        growth_stage: str | None = None,
        *,
        user_id: int | None = None,
        profile_id: str | None = None,
        preferred_mode: "ConditionProfileMode" | None = None,
        plant_variety: str | None = None,
        strain_variety: str | None = None,
        pot_size_liters: float | None = None,
    ) -> dict[str, dict[str, float]]:
        """
        Get min/max/optimal ranges for hardware control and UI.

        Returns a dict in the shape:
            {
              "temperature": {"min": 18.0, "max": 28.0, "optimal": 24.0},
              "humidity": {"min": 50.0, "max": 80.0, "optimal": 65.0},
              ...
            }

        Notes:
        - "optimal" is the midpoint of min/max when ranges exist, otherwise the
          value from `get_thresholds()`.
        """
        cache_key = f"ranges_{plant_type}_{growth_stage or 'all'}_{user_id}_{profile_id}_{preferred_mode}_{plant_variety}_{strain_variety}_{pot_size_liters}"
        cached = self._threshold_cache.get(cache_key)
        if isinstance(cached, dict):
            return cached

        try:
            plants = self.plant_handler.search_plants(common_name=plant_type)
            if not plants:
                logger.warning("Plant type '%s' not found, using generic ranges", plant_type)
                generic = self.generic_thresholds
                ranges = {
                    "temperature": {
                        "min": generic.temperature,
                        "max": generic.temperature,
                        "optimal": generic.temperature,
                    },
                    "humidity": {"min": generic.humidity, "max": generic.humidity, "optimal": generic.humidity},
                    "soil_moisture": {
                        "min": generic.soil_moisture,
                        "max": generic.soil_moisture,
                        "optimal": generic.soil_moisture,
                    },
                    "co2": {"min": generic.co2, "max": generic.co2, "optimal": generic.co2},
                }
                self._threshold_cache.set(cache_key, ranges)
                return ranges

            plant = plants[0]
            growth_stages = plant.get("growth_stages", []) or []

            # Stage selection (falls back to all stages if not found)
            stages_to_use = growth_stages
            if growth_stage:
                matched = [
                    stage for stage in growth_stages if str(stage.get("stage", "")).lower() == str(growth_stage).lower()
                ]
                stages_to_use = matched or growth_stages

            # Temperature / humidity from stage conditions
            temp_mins: list[float] = []
            temp_maxs: list[float] = []
            hum_mins: list[float] = []
            hum_maxs: list[float] = []

            for stage in stages_to_use:
                conditions = stage.get("conditions", {}) or {}
                temp_range = conditions.get("temperature_C", {}) or {}
                hum_range = conditions.get("humidity_percent", {}) or {}

                if temp_range.get("min") is not None and temp_range.get("max") is not None:
                    temp_mins.append(float(temp_range["min"]))
                    temp_maxs.append(float(temp_range["max"]))

                if hum_range.get("min") is not None and hum_range.get("max") is not None:
                    hum_mins.append(float(hum_range["min"]))
                    hum_maxs.append(float(hum_range["max"]))

            thresholds = self.get_thresholds(
                plant_type,
                growth_stage,
                user_id=user_id,
                profile_id=profile_id,
                preferred_mode=preferred_mode,
                plant_variety=plant_variety,
                strain_variety=strain_variety,
                pot_size_liters=pot_size_liters,
            )

            temperature_min = min(temp_mins) if temp_mins else thresholds.temperature
            temperature_max = max(temp_maxs) if temp_maxs else thresholds.temperature
            humidity_min = min(hum_mins) if hum_mins else thresholds.humidity
            humidity_max = max(hum_maxs) if hum_maxs else thresholds.humidity

            # Soil moisture / CO2 from plant-level sensor requirements when present
            sensor_reqs = plant.get("sensor_requirements", {}) or {}
            moisture_range = sensor_reqs.get("soil_moisture_range", {}) or {}
            co2_range = sensor_reqs.get("co2_requirements", {}) or {}

            soil_moisture_min = (
                float(moisture_range.get("min")) if moisture_range.get("min") is not None else thresholds.soil_moisture
            )
            soil_moisture_max = (
                float(moisture_range.get("max")) if moisture_range.get("max") is not None else thresholds.soil_moisture
            )
            co2_min = float(co2_range.get("min")) if co2_range.get("min") is not None else thresholds.co2
            co2_max = float(co2_range.get("max")) if co2_range.get("max") is not None else thresholds.co2

            ranges = {
                "temperature": {
                    "min": temperature_min,
                    "max": temperature_max,
                    "optimal": (temperature_min + temperature_max) / 2 if temp_mins else thresholds.temperature,
                },
                "humidity": {
                    "min": humidity_min,
                    "max": humidity_max,
                    "optimal": (humidity_min + humidity_max) / 2 if hum_mins else thresholds.humidity,
                },
                "soil_moisture": {
                    "min": soil_moisture_min,
                    "max": soil_moisture_max,
                    "optimal": (soil_moisture_min + soil_moisture_max) / 2
                    if moisture_range.get("min") is not None and moisture_range.get("max") is not None
                    else thresholds.soil_moisture,
                },
                "co2": {
                    "min": co2_min,
                    "max": co2_max,
                    "optimal": (co2_min + co2_max) / 2
                    if co2_range.get("min") is not None and co2_range.get("max") is not None
                    else thresholds.co2,
                },
            }

            profile = self.get_condition_profile(
                user_id=user_id,
                plant_type=plant_type,
                growth_stage=growth_stage or "",
                plant_variety=plant_variety,
                strain_variety=strain_variety,
                pot_size_liters=pot_size_liters,
            )
            if profile:
                env = profile.get("environment_thresholds", {})
                mapping = {
                    "temperature_threshold": "temperature",
                    "humidity_threshold": "humidity",
                    "co2_threshold": "co2",
                    "voc_threshold": "voc",
                    "lux_threshold": "lux",
                    "air_quality_threshold": "air_quality",
                }
                for key, metric in mapping.items():
                    if key in env and metric in ranges:
                        ranges[metric]["optimal"] = float(env[key])
                if profile.get("soil_moisture_threshold") is not None:
                    ranges["soil_moisture"]["optimal"] = float(profile["soil_moisture_threshold"])

            self._threshold_cache.set(cache_key, ranges)
            return ranges

        except Exception as e:
            logger.error("Error getting threshold ranges for %s: %s", plant_type, e, exc_info=True)
            generic = self.generic_thresholds
            return {
                "temperature": {"min": generic.temperature, "max": generic.temperature, "optimal": generic.temperature},
                "humidity": {"min": generic.humidity, "max": generic.humidity, "optimal": generic.humidity},
                "soil_moisture": {
                    "min": generic.soil_moisture,
                    "max": generic.soil_moisture,
                    "optimal": generic.soil_moisture,
                },
                "co2": {"min": generic.co2, "max": generic.co2, "optimal": generic.co2},
            }

    def clear_cache(self):
        """Clear the threshold cache"""
        self._threshold_cache.clear()
        logger.info("Threshold cache cleared")

    # ==================== AI Integration ====================

    def get_optimal_conditions(
        self,
        plant_type: str,
        growth_stage: str,
        use_ai: bool = True,
        *,
        user_id: int | None = None,
        profile_id: str | None = None,
        preferred_mode: "ConditionProfileMode" | None = None,
        plant_variety: str | None = None,
        strain_variety: str | None = None,
        pot_size_liters: float | None = None,
    ) -> EnvironmentalThresholds:
        """
        Get optimal environmental conditions with optional AI enhancement.

        Combines plant-specific thresholds with AI predictions for best results.

        Args:
            plant_type: Common name of the plant (e.g., 'Tomatoes')
            growth_stage: Current growth stage (e.g., 'Vegetative')
            use_ai: Whether to incorporate AI predictions (default: True)

        Returns:
            EnvironmentalThresholds domain object with optimal values
        """
        try:
            # Get base thresholds as domain object
            thresholds = self.get_thresholds(
                plant_type,
                growth_stage,
                user_id=user_id,
                profile_id=profile_id,
                preferred_mode=preferred_mode,
                plant_variety=plant_variety,
                strain_variety=strain_variety,
                pot_size_liters=pot_size_liters,
            )

            # If AI disabled, return as-is
            if not use_ai or not self.climate_optimizer:
                return thresholds

            # Enhance with AI predictions
            try:
                ai_conditions = self.climate_optimizer.predict_conditions(growth_stage)
                if not ai_conditions:
                    return thresholds

                ai_predictions = ai_conditions.to_dict()

                # Blend AI predictions with plant-specific thresholds (70% AI, 30% plant)
                temperature = thresholds.temperature
                humidity = thresholds.humidity
                soil_moisture = thresholds.soil_moisture

                if "temperature" in ai_predictions:
                    temperature = (0.7 * ai_predictions["temperature"]) + (0.3 * temperature)

                if "humidity" in ai_predictions:
                    humidity = (0.7 * ai_predictions["humidity"]) + (0.3 * humidity)

                if "soil_moisture" in ai_predictions:
                    soil_moisture = (0.7 * ai_predictions["soil_moisture"]) + (0.3 * soil_moisture)

                logger.info("Blended AI predictions with plant-specific thresholds for %s", plant_type)

                # Return new domain object with AI-enhanced values
                return EnvironmentalThresholds(
                    temperature=temperature,
                    humidity=humidity,
                    soil_moisture=soil_moisture,
                    co2=thresholds.co2,
                    voc=thresholds.voc,
                    lux=thresholds.lux,
                    air_quality=thresholds.air_quality,
                )

            except Exception as e:
                logger.warning("AI prediction failed, using plant-specific only: %s", e)
                return thresholds

        except Exception as e:
            logger.error("Error getting optimal conditions: %s", e)
            return self.generic_thresholds

    def is_within_optimal_range(
        self, plant_type: str, growth_stage: str, current_conditions: dict[str, float]
    ) -> dict[str, bool]:
        """
        Check if current conditions are within reasonable ranges.

        Args:
            plant_type: Common name of the plant
            growth_stage: Current growth stage
            current_conditions: Current sensor readings

        Returns:
            Dictionary indicating if each factor is acceptable:
            {'temperature': True, 'humidity': False, ...}
        """
        try:
            thresholds = self.get_thresholds(plant_type, growth_stage)

            results = {}
            # Use ±10% tolerance from optimal values
            if "temperature" in current_conditions:
                tolerance = thresholds.temperature * 0.1
                results["temperature"] = abs(current_conditions["temperature"] - thresholds.temperature) <= tolerance

            if "humidity" in current_conditions:
                tolerance = thresholds.humidity * 0.1
                results["humidity"] = abs(current_conditions["humidity"] - thresholds.humidity) <= tolerance

            if "soil_moisture" in current_conditions:
                tolerance = thresholds.soil_moisture * 0.1
                results["soil_moisture"] = (
                    abs(current_conditions["soil_moisture"] - thresholds.soil_moisture) <= tolerance
                )

            if "co2" in current_conditions:
                tolerance = thresholds.co2 * 0.15
                results["co2"] = abs(current_conditions["co2"] - thresholds.co2) <= tolerance

            return results

        except Exception as e:
            logger.error("Error checking optimal range: %s", e)
            return {}

    def get_adjustment_recommendations(
        self, plant_type: str, growth_stage: str, current_conditions: dict[str, float]
    ) -> dict[str, dict[str, Any]]:
        """
        Get specific recommendations for adjusting environmental conditions.

        Args:
            plant_type: Common name of the plant
            growth_stage: Current growth stage
            current_conditions: Current sensor readings

        Returns:
            Dictionary with recommendations for each factor:
            {
                'temperature': {
                    'current': 30.0,
                    'optimal': 24.0,
                    'action': 'decrease',
                    'amount': 6.0,
                    'priority': 'high'
                }
            }
        """
        try:
            thresholds = self.get_optimal_conditions(plant_type, growth_stage, use_ai=True)

            recommendations = {}

            for factor, current_value in current_conditions.items():
                optimal_value = getattr(thresholds, factor, None)
                if optimal_value is None:
                    continue

                difference = current_value - optimal_value
                tolerance = optimal_value * 0.1  # 10% tolerance

                # Determine if adjustment needed
                if abs(difference) <= tolerance:
                    action = "maintain"
                    priority = "low"
                elif difference < 0:
                    action = "increase"
                    priority = "high" if abs(difference) > (optimal_value * 0.2) else "medium"
                else:
                    action = "decrease"
                    priority = "high" if abs(difference) > (optimal_value * 0.2) else "medium"

                recommendations[factor] = {
                    "current": current_value,
                    "optimal": optimal_value,
                    "action": action,
                    "amount": abs(difference),
                    "priority": priority,
                    "plant_specific": True,
                }

            return recommendations

        except Exception as e:
            logger.error("Error getting adjustment recommendations: %s", e)
            return {}
