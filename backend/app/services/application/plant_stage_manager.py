"""
Plant Stage Manager
===================
Handles growth-stage transitions, threshold proposals, and condition profiles.

Extracted from PlantViewService to reduce its scope (audit item #8).
PlantViewService delegates stage/threshold operations to this class.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.constants import THRESHOLD_UPDATE_TOLERANCE
from app.enums.common import ConditionProfileMode, ConditionProfileTarget
from app.enums.events import PlantEvent
from app.schemas.events import PlantStageUpdatePayload
from app.services.application.activity_logger import ActivityLogger, log_if_available
from app.services.application.threshold_service import THRESHOLD_KEYS

if TYPE_CHECKING:
    from app.domain.plant_profile import PlantProfile
    from app.services.application.notifications_service import NotificationsService
    from app.services.application.threshold_service import ThresholdService
    from app.utils.event_bus import EventBus

logger = logging.getLogger(__name__)


class PlantStageManager:
    """
    Manages plant growth-stage transitions and environmental-threshold proposals.

    Responsibilities:
    - Stage updates with event emission and threshold proposals
    - Soil moisture threshold overrides (per-plant)
    - Condition profile application (linking / cloning)
    - Historical threshold override resolution
    """

    def __init__(
        self,
        plant_repo: Any,
        event_bus: "EventBus",
        threshold_service: "ThresholdService" | None = None,
        notifications_service: "NotificationsService" | None = None,
        activity_logger: "ActivityLogger" | None = None,
    ):
        self.plant_repo = plant_repo
        self.event_bus = event_bus
        self.threshold_service = threshold_service
        self.notifications_service = notifications_service
        self.activity_logger = activity_logger

    # ==================== Stage Transitions ====================

    def update_plant_stage(
        self,
        plant: "PlantProfile",
        new_stage: str,
        days_in_stage: int = 0,
        *,
        skip_threshold_proposal: bool = False,
    ) -> bool:
        """
        Update plant growth stage.

        When stage changes, proposes new thresholds based on stage-specific
        requirements and sends notification for user confirmation.

        Args:
            plant: PlantProfile object (must be resolved by caller)
            new_stage: New growth stage
            days_in_stage: Days in new stage
            skip_threshold_proposal: Skip sending threshold proposal

        Returns:
            True if successful
        """
        try:
            unit_id = plant.unit_id
            if not unit_id:
                logger.error("Plant %s has no unit_id", plant.plant_id)
                return False

            old_stage = plant.current_stage

            # Update the in-memory PlantProfile directly
            plant.set_stage(new_stage, days_in_stage)
            moisture_level = plant.moisture_level

            self.plant_repo.update_plant_progress(
                plant_id=plant.plant_id,
                current_stage=new_stage,
                moisture_level=moisture_level,
                days_in_stage=days_in_stage,
            )

            plant_name = plant.plant_name or "Unknown"
            plant_type = plant.plant_type or "Unknown"

            log_if_available(
                self.activity_logger,
                ActivityLogger.PLANT_UPDATED,
                f"Updated {plant_type} plant '{plant_name}' to unit {unit_id}",
                severity=ActivityLogger.INFO,
                entity_type="plant",
                entity_id=plant.plant_id,
                metadata={"plant_type": plant_type, "unit_id": unit_id, "stage": new_stage},
            )

            try:
                payload = PlantStageUpdatePayload(
                    plant_id=plant.plant_id, new_stage=new_stage, days_in_stage=days_in_stage
                )
                self.event_bus.publish(PlantEvent.PLANT_STAGE_UPDATE, payload)
            except Exception:
                logger.debug(
                    "Event bus publish failed for plant %s stage update",
                    plant.plant_id,
                    exc_info=True,
                )

            # Propose threshold update if stage changed
            if not skip_threshold_proposal and old_stage and old_stage.lower() != new_stage.lower():
                self._propose_stage_thresholds(plant, old_stage, new_stage)

            logger.info("Updated plant %s to stage '%s'", plant.plant_id, new_stage)
            return True

        except Exception as e:
            logger.error("Error updating plant %s stage: %s", plant.plant_id, e, exc_info=True)
            return False

    # ==================== Threshold Proposals ====================

    def _propose_stage_thresholds(
        self,
        plant: "PlantProfile",
        old_stage: str,
        new_stage: str,
        *,
        seed_overrides: dict[str, float] | None = None,
        force: bool = False,
    ) -> None:
        """
        Propose new thresholds when plant enters a new growth stage.

        Sends notification with Apply/Keep Current/Customize options.
        """
        if not self.threshold_service or not self.notifications_service:
            logger.debug("Threshold proposal skipped - threshold_service or notifications_service not available")
            return

        try:
            plant_type = plant.plant_type or "default"
            user_id = self._get_unit_owner(plant.unit_id)

            new_thresholds = self.threshold_service.get_thresholds(
                plant_type,
                new_stage,
                user_id=user_id,
                profile_id=getattr(plant, "condition_profile_id", None),
                preferred_mode=getattr(plant, "condition_profile_mode", None),
                plant_variety=plant.plant_variety,
                strain_variety=plant.strain_variety,
                pot_size_liters=plant.pot_size_liters,
            )
            proposed_map = new_thresholds.to_settings_dict()
            if seed_overrides:
                for key, value in seed_overrides.items():
                    if key in proposed_map:
                        proposed_map[key] = value

            current_env = self.threshold_service.get_unit_thresholds_dict(plant.unit_id)
            if not current_env:
                logger.debug("No current thresholds for unit %s, using generic", plant.unit_id)
                current_env = self.threshold_service.generic_thresholds.to_settings_dict()

            threshold_comparison: dict[str, dict[str, float]] = {}
            for key in THRESHOLD_KEYS:
                proposed_value = proposed_map.get(key)
                if proposed_value is None:
                    continue
                current_value = current_env.get(key)
                if current_value is None:
                    current_value = proposed_value
                tolerance = THRESHOLD_UPDATE_TOLERANCE.get(key, 0.0)
                if force or abs(proposed_value - current_value) >= tolerance:
                    threshold_comparison[key] = {
                        "current": float(current_value),
                        "proposed": float(proposed_value),
                    }

            soil_proposed = proposed_map.get("soil_moisture_threshold")
            if soil_proposed is not None:
                current_soil = plant.soil_moisture_threshold_override
                if current_soil is None:
                    current_soil = soil_proposed
                tolerance = THRESHOLD_UPDATE_TOLERANCE.get("soil_moisture_threshold", 2.0)
                if force or abs(float(soil_proposed) - float(current_soil)) >= tolerance:
                    threshold_comparison["soil_moisture_threshold"] = {
                        "current": float(current_soil),
                        "proposed": float(soil_proposed),
                    }

            if not threshold_comparison:
                logger.debug(
                    "No significant threshold changes for stage %s -> %s",
                    old_stage,
                    new_stage,
                )
                return

            self._send_threshold_proposal_notification(
                plant=plant,
                old_stage=old_stage,
                new_stage=new_stage,
                comparison=threshold_comparison,
                proposed_thresholds=new_thresholds,
            )

            logger.info(
                "Sent threshold proposal notification for plant %s stage %s -> %s",
                plant.plant_id,
                old_stage,
                new_stage,
            )

        except Exception as e:
            logger.error(
                "Error proposing stage thresholds for plant %s: %s",
                plant.plant_id,
                e,
                exc_info=True,
            )

    def _send_threshold_proposal_notification(
        self,
        plant: "PlantProfile",
        old_stage: str,
        new_stage: str,
        comparison: dict[str, dict[str, float]],
        proposed_thresholds: Any,
    ) -> None:
        """
        Send notification for threshold proposal with action buttons.
        """
        from app.enums import NotificationSeverity, NotificationType

        user_id = self._get_unit_owner(plant.unit_id)
        if not user_id:
            logger.warning("Cannot send threshold proposal - no owner for unit %s", plant.unit_id)
            return

        metric_meta = {
            "temperature_threshold": ("Temperature", "°C", 1),
            "humidity_threshold": ("Humidity", "%", 1),
            "soil_moisture_threshold": ("Soil Moisture", "%", 1),
            "co2_threshold": ("CO₂", "ppm", 0),
            "voc_threshold": ("VOC", "ppb", 0),
            "lux_threshold": ("Light", "lux", 0),
            "air_quality_threshold": ("Air Quality", "AQI", 0),
        }
        changes: list[str] = []
        for param, values in comparison.items():
            diff = values["proposed"] - values["current"]
            if abs(diff) > 0.5:
                direction = "↑" if diff > 0 else "↓"
                name, unit, precision = metric_meta.get(param, (param.replace("_", " ").title(), "", 1))
                fmt = f"{{:.{precision}f}}"
                current_str = fmt.format(values["current"])
                proposed_str = fmt.format(values["proposed"])
                suffix = f" {unit}" if unit else ""
                changes.append(f"{name}: {current_str}{suffix} → {proposed_str}{suffix} {direction}")

        if not changes:
            return

        plant_name = plant.plant_name or "Unknown"
        if old_stage and old_stage.lower() != new_stage.lower():
            header = f"Plant '{plant_name}' moved from {old_stage} to {new_stage}."
        else:
            header = f"Plant '{plant_name}' is in {new_stage} stage."
        message = header + " Recommended threshold changes:\n" + "\n".join(changes)

        actions = ["apply", "keep_current", "customize"]
        if old_stage and old_stage.lower() != new_stage.lower():
            actions.append("delay_stage")

        self.notifications_service.send_notification(
            user_id=user_id,
            notification_type=NotificationType.THRESHOLD_PROPOSAL,
            title=f"🌱 Threshold Update for {plant_name}",
            message=message,
            severity=NotificationSeverity.INFO,
            unit_id=plant.unit_id,
            requires_action=True,
            action_type="threshold_proposal",
            action_data={
                "plant_id": plant.plant_id,
                "unit_id": plant.unit_id,
                "old_stage": old_stage,
                "new_stage": new_stage,
                "proposed_thresholds": comparison,
                "actions": actions,
            },
        )

    # ==================== Soil Moisture Threshold ====================

    def update_soil_moisture_threshold(
        self,
        plant_id: int,
        threshold: float,
        plant: "PlantProfile" | None = None,
        unit_id: int | None = None,
    ) -> bool:
        """
        Update the per-plant soil moisture threshold override.

        Args:
            plant_id: Plant identifier
            threshold: New soil moisture threshold (0-100)
            plant: Optional resolved PlantProfile (for in-memory update + profile sync)
            unit_id: Optional unit identifier

        Returns:
            True if updated, False otherwise
        """
        try:
            value = float(threshold)
        except (TypeError, ValueError):
            logger.error("Invalid soil moisture threshold for plant %s: %s", plant_id, threshold)
            return False

        value = max(0.0, min(100.0, value))

        try:
            self.plant_repo.update_plant(plant_id, soil_moisture_threshold_override=value)
        except Exception as exc:
            logger.error(
                "Failed to persist soil moisture threshold override for plant %s: %s",
                plant_id,
                exc,
                exc_info=True,
            )
            return False

        if plant:
            plant.soil_moisture_threshold_override = value

        # Sync to active condition profile if applicable
        if (
            plant
            and unit_id is not None
            and self.threshold_service
            and plant.condition_profile_id
            and plant.condition_profile_mode == ConditionProfileMode.ACTIVE
        ):
            profile_service = getattr(self.threshold_service, "personalized_learning", None)
            user_id = self._get_unit_owner(unit_id)
            if profile_service and user_id:
                profile_service.upsert_condition_profile(
                    user_id=user_id,
                    profile_id=plant.condition_profile_id,
                    plant_type=plant.plant_type or "unknown",
                    growth_stage=plant.current_stage or "Unknown",
                    soil_moisture_threshold=value,
                    plant_variety=plant.plant_variety,
                    strain_variety=plant.strain_variety,
                    pot_size_liters=plant.pot_size_liters if plant.pot_size_liters > 0 else None,
                )

        logger.info(
            "Updated soil moisture threshold override for plant %s to %.1f",
            plant_id,
            value,
        )
        return True

    # ==================== Condition Profiles ====================

    def apply_condition_profile_to_plant(
        self,
        *,
        plant_id: int,
        profile_id: str,
        plant: "PlantProfile" | None = None,
        unit_id: int | None = None,
        mode: ConditionProfileMode | None = None,
        name: str | None = None,
        user_id: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Apply a condition profile to an existing plant.

        Updates soil moisture threshold and links profile (active/template).

        Args:
            plant_id: Plant identifier
            profile_id: Condition profile ID to apply
            plant: Resolved PlantProfile (caller must provide)
            unit_id: Resolved unit ID (caller must provide)
            mode: Optional override for profile mode
            name: Optional name for cloned profile
            user_id: Optional user ID override

        Returns:
            Dict with result details, or None on failure
        """
        if not plant:
            return None
        if unit_id is None:
            return None

        if user_id is None:
            user_id = self._get_unit_owner(unit_id)
        if user_id is None:
            return None

        if not self.threshold_service:
            raise ValueError("Threshold service not available")
        profile_service = getattr(self.threshold_service, "personalized_learning", None)
        if not profile_service:
            raise ValueError("Condition profile service not available")

        profile = profile_service.get_condition_profile_by_id(
            user_id=user_id,
            profile_id=profile_id,
        )
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

        applied_threshold = None
        if profile.soil_moisture_threshold is not None:
            applied_threshold = float(profile.soil_moisture_threshold)
            if not self.update_soil_moisture_threshold(
                plant_id=plant_id,
                threshold=applied_threshold,
                plant=plant,
                unit_id=unit_id,
            ):
                return None

        profile_service.link_condition_profile(
            user_id=user_id,
            target_type=ConditionProfileTarget.PLANT,
            target_id=int(plant_id),
            profile_id=profile.profile_id,
            mode=desired_mode or ConditionProfileMode.ACTIVE,
        )

        plant.condition_profile_id = profile.profile_id
        plant.condition_profile_mode = desired_mode

        return {
            "plant_id": plant_id,
            "unit_id": unit_id,
            "profile": profile.to_dict(),
            "applied_threshold": applied_threshold,
        }

    # ==================== Historical Overrides ====================

    def resolve_historical_threshold_overrides(
        self,
        *,
        unit_id: int,
        plant_type: str,
        growth_stage: str,
        plant_variety: str | None,
        strain_variety: str | None,
        pot_size_liters: float | None,
    ) -> dict[str, float]:
        """Fetch the latest stored overrides for a matching plant context."""
        user_id = self._get_unit_owner(unit_id)
        if not user_id:
            return {}
        try:
            row = self.plant_repo.get_latest_threshold_overrides(
                user_id=user_id,
                plant_type=plant_type,
                growth_stage=growth_stage,
                plant_variety=plant_variety,
                strain_variety=strain_variety,
                pot_size_liters=pot_size_liters,
            )
        except Exception as exc:
            logger.debug("Failed to load historical threshold overrides: %s", exc)
            return {}
        if not row:
            return {}
        mapping = {
            "temperature_threshold": row.get("temperature_threshold_override"),
            "humidity_threshold": row.get("humidity_threshold_override"),
            "co2_threshold": row.get("co2_threshold_override"),
            "voc_threshold": row.get("voc_threshold_override"),
            "lux_threshold": row.get("lux_threshold_override"),
            "air_quality_threshold": row.get("air_quality_threshold_override"),
            "soil_moisture_threshold": row.get("soil_moisture_threshold_override"),
        }
        overrides: dict[str, float] = {}
        for key, value in mapping.items():
            if value is None:
                continue
            try:
                overrides[key] = float(value)
            except (TypeError, ValueError):
                continue
        return overrides

    # ==================== Helpers ====================

    def _get_unit_owner(self, unit_id: int) -> int | None:
        """
        Get the owner user_id for a unit.

        Uses the unit_repo injected via set_unit_repo().
        """
        if not hasattr(self, "_unit_repo") or self._unit_repo is None:
            return None
        try:
            unit = self._unit_repo.get_unit(unit_id)
            if not unit:
                return None
            if isinstance(unit, dict):
                return unit.get("user_id")
            try:
                return unit["user_id"]
            except (TypeError, KeyError):
                return getattr(unit, "user_id", None)
        except Exception as e:
            logger.error("Error getting unit owner for %s: %s", unit_id, e)
        return None

    def set_unit_repo(self, unit_repo: Any) -> None:
        """
        Set the unit repository (avoids circular dependency at init time).
        """
        self._unit_repo = unit_repo

    # ==================== Journal Service ====================

    @property
    def journal_service(self):
        """Journal service for recording stage-related entries."""
        return getattr(self, "_journal_service", None)

    @journal_service.setter
    def journal_service(self, service) -> None:
        self._journal_service = service

    # ==================== Stage Extension ====================

    def extend_stage(
        self,
        plant_id: int,
        plant: Any,
        extend_days: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Extend the current growth stage by a number of days (max 5).

        Args:
            plant_id: Plant ID
            plant: Plant dict or PlantProfile
            extend_days: Days to extend (1-5)
            reason: Reason for extension

        Returns:
            Dict with extension details

        Raises:
            ValueError: if days out of range or stage unknown
        """
        if extend_days < 1 or extend_days > 5:
            raise ValueError("Extension must be between 1 and 5 days")

        plant_dict = plant if isinstance(plant, dict) else (plant.to_dict() if hasattr(plant, "to_dict") else {})

        current_stage = plant_dict.get("current_stage") or getattr(plant, "current_stage", None)
        days_in_stage = plant_dict.get("days_in_stage", 0) or getattr(plant, "days_in_stage", 0)
        plant_dict.get("unit_id") or getattr(plant, "unit_id", None)

        if not current_stage:
            raise ValueError("Plant has no current stage to extend")

        new_days = (days_in_stage or 0) + extend_days

        # Update the stage with new days_in_stage (effectively same stage, more days)
        try:
            profile = plant if hasattr(plant, "plant_id") else None
            if profile:
                self.update_plant_stage(
                    plant=profile,
                    new_stage=current_stage,
                    days_in_stage=new_days,
                    skip_threshold_proposal=True,
                )
        except Exception as e:
            logger.error("Failed to persist stage extension: %s", e, exc_info=True)

        # Auto-journal the extension
        if self.journal_service:
            try:
                self.journal_service.record_stage_change(
                    plant_id=plant_id,
                    from_stage=current_stage,
                    to_stage=current_stage,
                    trigger="extension",
                    notes=f"Stage extended by {extend_days} day(s). Reason: {reason or 'not specified'}",
                )
            except Exception as e:
                logger.error("Failed to journal stage extension: %s", e, exc_info=True)

        result = {
            "plant_id": plant_id,
            "stage": current_stage,
            "previous_days": days_in_stage,
            "extended_by": extend_days,
            "new_days_in_stage": new_days,
            "reason": reason,
            "message": f"Stage '{current_stage}' extended by {extend_days} day(s)",
        }

        logger.info(
            f"Extended stage '{current_stage}' for plant {plant_id} by {extend_days} days → {new_days} total days"
        )
        return result
