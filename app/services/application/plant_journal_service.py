"""
Plant Journal Service
=====================
Business logic for managing plant journals.

Consolidates:
- Health observations
- Nutrient applications
- Treatment records
- General notes and photos

Provides data for AI analysis of nutrient-health correlations.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.ai.plant_health_monitor import PlantHealthMonitor
    from app.services.application.manual_irrigation_service import ManualIrrigationService
    from infrastructure.database.repositories.plant_journal import PlantJournalRepository

logger = logging.getLogger(__name__)


class PlantJournalService:
    """
    Service for managing plant journal entries.

    Bidirectional Dependencies:
        - health_monitor: Set by ContainerBuilder for AI-based health correlations
    """

    def __init__(
        self,
        journal_repo: "PlantJournalRepository",
        health_monitor: "PlantHealthMonitor" | None = None,
        manual_irrigation_service: "ManualIrrigationService" | None = None,
    ):
        """
        Initialize service.

        Args:
            journal_repo: Plant journal repository
            health_monitor: Optional plant health monitor for correlations
        """
        self.repo = journal_repo
        self.health_monitor = health_monitor
        self.manual_irrigation_service = manual_irrigation_service

    def set_manual_irrigation_service(self, service: "ManualIrrigationService" | None) -> None:
        """Wire manual irrigation service after construction."""
        self.manual_irrigation_service = service

    # ========================================================================
    # Observations
    # ========================================================================

    def record_observation(
        self,
        plant_id: int,
        observation_type: str,
        notes: str,
        health_status: str | None = None,
        severity_level: int | None = None,
        symptoms: list[str] | None = None,
        image_path: str | None = None,
        user_id: int | None = None,
    ) -> int | None:
        """
        Record a plant observation.

        Args:
            plant_id: Plant ID
            observation_type: Type (health, growth, pest, disease, general)
            notes: Observation notes
            health_status: Health status if health-related
            severity_level: Severity (1-5)
            symptoms: List of symptoms
            image_path: Path to observation image
            user_id: User who made observation

        Returns:
            entry_id if successful
        """
        try:
            # Convert symptoms list to JSON
            symptoms_json = json.dumps(symptoms) if symptoms else None

            entry_id = self.repo.create_observation(
                plant_id=plant_id,
                observation_type=observation_type,
                health_status=health_status,
                severity_level=severity_level,
                symptoms=symptoms_json,
                notes=notes,
                image_path=image_path,
                user_id=user_id,
            )

            if entry_id:
                logger.info("Recorded observation for plant %s: %s", plant_id, entry_id)

            return entry_id

        except Exception as e:
            logger.error("Failed to record observation: %s", e)
            return None

    def record_watering(
        self,
        plant_id: int,
        unit_id: int | None = None,
        *,
        amount_ml: float | None = None,
        amount: float | None = None,
        unit: str = "ml",
        method: str = "manual",
        source: str = "user",
        ph_level: float | None = None,
        ec_level: float | None = None,
        duration_seconds: int | None = None,
        notes: str = "",
        user_id: int | None = None,
        watered_at_utc: str | None = None,
    ) -> int | None:
        """
        Record a watering event (unified method).

        Supports both simple watering (amount + unit) and advanced watering
        (method, source, pH, EC, duration). Optionally forwards to
        ManualIrrigationService for irrigation logging.

        Args:
            plant_id: Plant ID
            unit_id: Unit ID for context
            amount_ml: Amount of water in milliliters (preferred)
            amount: Amount in arbitrary units (fallback)
            unit: Unit of measurement for amount ('ml', 'l', etc.)
            method: Watering method (manual, automatic, drip)
            source: Event source (user, sensor_triggered, schedule)
            ph_level: pH level of water (optional)
            ec_level: EC level of water (optional)
            duration_seconds: Duration of watering in seconds
            notes: Additional notes
            user_id: User who performed watering
            watered_at_utc: ISO timestamp of watering event

        Returns:
            entry_id if successful
        """
        try:
            entry_id = self.repo.create_watering_entry(
                plant_id=plant_id,
                amount_ml=amount_ml,
                amount=amount,
                unit=unit,
                method=method,
                source=source,
                ph_level=ph_level,
                ec_level=ec_level,
                notes=notes,
                user_id=user_id,
                unit_id=unit_id,
                observation_date=watered_at_utc,
            )

            if entry_id:
                logger.info("Recorded watering for plant %s: entry %s", plant_id, entry_id)

            # Forward to irrigation service if available
            if entry_id and self.manual_irrigation_service and unit_id is not None and user_id is not None:
                resolved_ml = None
                if amount_ml is not None:
                    resolved_ml = float(amount_ml)
                elif amount is not None:
                    normalized_unit = (unit or "").strip().lower()
                    if normalized_unit in ("l", "liter", "liters"):
                        resolved_ml = float(amount) * 1000.0
                    else:
                        resolved_ml = float(amount)

                self.manual_irrigation_service.log_watering_event(
                    user_id=int(user_id),
                    unit_id=int(unit_id),
                    plant_id=int(plant_id),
                    watered_at_utc=watered_at_utc,
                    amount_ml=resolved_ml,
                    notes=notes,
                )

            return entry_id
        except Exception as e:
            logger.error("Failed to record watering: %s", e)
            return None

    def record_health_observation(
        self,
        plant_id: int,
        health_status: str,
        symptoms: list[str],
        severity_level: int,
        unit_id: int | None = None,
        disease_type: str | None = None,
        affected_parts: list[str] | None = None,
        environmental_factors: dict[str, Any] | None = None,
        treatment_applied: str | None = None,
        plant_type: str | None = None,
        growth_stage: str | None = None,
        notes: str = "",
        image_path: str | None = None,
        user_id: int | None = None,
        observation_date: str | None = None,
    ) -> int | None:
        """
        Record a health-specific observation.

        This is a convenience method for health observations that also
        triggers health monitoring analysis if available.

        Args:
            plant_id: Plant ID
            health_status: Health status
            symptoms: List of symptoms
            severity_level: Severity (1-5)
            unit_id: Unit ID for context
            disease_type: Type of disease if applicable
            affected_parts: List of affected plant parts
            environmental_factors: Environmental conditions dict
            treatment_applied: Treatment that was applied
            plant_type: Plant species/type
            growth_stage: Growth stage during observation
            notes: Additional notes
            image_path: Path to observation image
            user_id: User who made observation
            observation_date: Custom observation date (ISO format)

        Returns:
            entry_id if successful
        """
        # Convert lists/dicts to JSON
        symptoms_json = json.dumps(symptoms) if symptoms else None
        affected_parts_json = json.dumps(affected_parts) if affected_parts else None
        env_factors_json = json.dumps(environmental_factors) if environmental_factors else None

        return self.repo.create_observation(
            plant_id=plant_id,
            observation_type="health",
            unit_id=unit_id,
            health_status=health_status,
            severity_level=severity_level,
            symptoms=symptoms_json,
            disease_type=disease_type,
            affected_parts=affected_parts_json,
            environmental_factors=env_factors_json,
            treatment_applied=treatment_applied,
            plant_type=plant_type,
            growth_stage=growth_stage,
            notes=notes,
            image_path=image_path,
            user_id=user_id,
            observation_date=observation_date,
        )

    def record_health_observation_validated(
        self,
        *,
        unit_id: int,
        health_status: str,
        symptoms: list[str],
        severity_level: int,
        plant_id: int | None = None,
        disease_type: str | None = None,
        affected_parts: list[str] | None = None,
        environmental_factors: dict[str, Any] | None = None,
        treatment_applied: str | None = None,
        plant_type: str | None = None,
        growth_stage: str | None = None,
        notes: str = "",
        image_path: str | None = None,
        user_id: int | None = None,
        observation_date: str | None = None,
    ) -> int | None:
        """Validate and normalize a health observation before persistence."""
        from app.domain.plant_journal_entity import PlantHealthObservationEntity

        observation = PlantHealthObservationEntity(
            unit_id=unit_id,
            plant_id=plant_id,
            health_status=health_status,
            symptoms=symptoms,
            disease_type=disease_type,
            severity_level=severity_level,
            affected_parts=affected_parts or [],
            environmental_factors=environmental_factors or {},
            treatment_applied=treatment_applied,
            notes=notes,
            plant_type=plant_type,
            growth_stage=growth_stage,
            image_path=image_path,
            user_id=user_id,
            observation_date=observation_date,
        )
        return self.record_health_observation(**observation.to_service_kwargs())

    # ========================================================================
    # Nutrients
    # ========================================================================

    def record_nutrient_application(
        self,
        plant_id: int,
        nutrient_type: str,
        nutrient_name: str,
        amount: float,
        unit: str = "ml",
        notes: str = "",
        user_id: int | None = None,
    ) -> int | None:
        """
        Record a nutrient application.

        Args:
            plant_id: Plant ID
            nutrient_type: Type (nitrogen, phosphorus, potassium, calcium, etc.)
            nutrient_name: Product name
            amount: Amount applied
            unit: Unit (ml, g, tsp, etc.)
            notes: Additional notes
            user_id: User who applied nutrient

        Returns:
            entry_id if successful
        """
        try:
            entry_id = self.repo.create_nutrient_entry(
                plant_id=plant_id,
                nutrient_type=nutrient_type,
                nutrient_name=nutrient_name,
                amount=amount,
                unit=unit,
                notes=notes,
                user_id=user_id,
            )

            if entry_id:
                logger.info("Recorded nutrient for plant %s: %s (%s%s)", plant_id, nutrient_type, amount, unit)

            return entry_id

        except Exception as e:
            logger.error("Failed to record nutrient: %s", e)
            return None

    def record_bulk_nutrient_application(
        self,
        plant_ids: list[int],
        nutrient_type: str,
        nutrient_name: str,
        amount: float,
        unit: str = "ml",
        notes: str = "",
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """
        Record nutrient application for multiple plants.

        Args:
            plant_ids: List of plant IDs
            nutrient_type: Type of nutrient
            nutrient_name: Product name
            amount: Amount per plant
            unit: Unit of measurement
            notes: Additional notes
            user_id: User who applied nutrient

        Returns:
            Dictionary with success count and created entry IDs
        """
        try:
            created_ids = []

            for plant_id in plant_ids:
                entry_id = self.record_nutrient_application(
                    plant_id=plant_id,
                    nutrient_type=nutrient_type,
                    nutrient_name=nutrient_name,
                    amount=amount,
                    unit=unit,
                    notes=notes,
                    user_id=user_id,
                )
                if entry_id:
                    created_ids.append(entry_id)

            return {"success": True, "entries_created": len(created_ids), "entry_ids": created_ids}

        except Exception as e:
            logger.error("Failed bulk nutrient application: %s", e)
            return {"success": False, "entries_created": 0, "error": str(e)}

    # ========================================================================
    # Treatments
    # ========================================================================

    def record_treatment(
        self, plant_id: int, treatment_type: str, treatment_name: str, notes: str = "", user_id: int | None = None
    ) -> int | None:
        """
        Record a treatment application.

        Args:
            plant_id: Plant ID
            treatment_type: Type (fungicide, pesticide, pruning, etc.)
            treatment_name: Product/action name
            notes: Additional notes
            user_id: User who applied treatment

        Returns:
            entry_id if successful
        """
        try:
            entry_id = self.repo.create_treatment_entry(
                plant_id=plant_id,
                treatment_type=treatment_type,
                treatment_name=treatment_name,
                notes=notes,
                user_id=user_id,
            )

            if entry_id:
                logger.info("Recorded treatment for plant %s: %s", plant_id, treatment_type)

            return entry_id

        except Exception as e:
            logger.error("Failed to record treatment: %s", e)
            return None

    # ========================================================================
    # Notes
    # ========================================================================

    def add_note(
        self, plant_id: int, notes: str, image_path: str | None = None, user_id: int | None = None
    ) -> int | None:
        """
        Add a general note to plant journal.

        Args:
            plant_id: Plant ID
            notes: Note text
            image_path: Optional image
            user_id: User who created note

        Returns:
            entry_id if successful
        """
        try:
            entry_id = self.repo.create_note(plant_id=plant_id, notes=notes, image_path=image_path, user_id=user_id)

            if entry_id:
                logger.info("Added note for plant %s", plant_id)

            return entry_id

        except Exception as e:
            logger.error("Failed to add note: %s", e)
            return None

    # ========================================================================
    # Retrieval
    # ========================================================================

    def get_journal(
        self,
        plant_id: int | None = None,
        unit_id: int | None = None,
        entry_type: str | None = None,
        limit: int = 100,
        days: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get journal entries with filters.

        Args:
            plant_id: Filter by plant ID
            unit_id: Filter by unit ID
            entry_type: Filter by type (observation, nutrient, treatment, note)
            limit: Max entries
            days: Only last N days

        Returns:
            List of journal entries
        """
        entries = self.repo.get_entries(
            plant_id=plant_id, unit_id=unit_id, entry_type=entry_type, limit=limit, days=days
        )

        # Parse JSON fields
        for entry in entries:
            if entry.get("symptoms"):
                with contextlib.suppress(ValueError, TypeError):
                    entry["symptoms"] = json.loads(entry["symptoms"])

        return entries

    def get_nutrient_history(
        self, plant_id: int, nutrient_type: str | None = None, days: int = 90
    ) -> list[dict[str, Any]]:
        """
        Get nutrient application history.

        Args:
            plant_id: Plant ID
            nutrient_type: Filter by type
            days: Look back period

        Returns:
            List of nutrient applications
        """
        return self.repo.get_nutrient_history(plant_id=plant_id, nutrient_type=nutrient_type, days=days)

    def get_health_timeline(self, plant_id: int, days: int = 30) -> list[dict[str, Any]]:
        """
        Get health observation timeline.

        Args:
            plant_id: Plant ID
            days: Look back period

        Returns:
            List of health observations
        """
        observations = self.repo.get_health_observations(plant_id=plant_id, days=days)

        # Parse symptoms
        for obs in observations:
            if obs.get("symptoms"):
                try:
                    obs["symptoms"] = json.loads(obs["symptoms"])
                except (ValueError, TypeError):
                    obs["symptoms"] = []

        return observations

    # ========================================================================
    # AI Analysis
    # ========================================================================

    def analyze_nutrient_health_correlation(self, plant_id: int, days: int = 60) -> dict[str, Any]:
        """
        Analyze correlation between nutrients and health outcomes.

        This method provides data for AI to learn which nutrients
        improve or worsen plant health.

        Args:
            plant_id: Plant ID
            days: Analysis period

        Returns:
            Correlation analysis data
        """
        try:
            # Get raw correlation data
            correlation = self.repo.correlate_nutrients_with_health(plant_id=plant_id, days=days)

            # Enhance with analysis
            timeline = correlation.get("timeline", [])

            # Find patterns: nutrients followed by health changes
            patterns = []
            for i in range(len(timeline) - 1):
                if timeline[i]["type"] == "nutrient":
                    # Look for health observation within 7 days
                    nutrient_entry = timeline[i]["data"]

                    for j in range(i + 1, min(i + 10, len(timeline))):
                        if timeline[j]["type"] == "health":
                            health_entry = timeline[j]["data"]
                            patterns.append(
                                {
                                    "nutrient_type": nutrient_entry.get("nutrient_type"),
                                    "nutrient_name": nutrient_entry.get("nutrient_name"),
                                    "amount": nutrient_entry.get("amount"),
                                    "health_status": health_entry.get("health_status"),
                                    "severity": health_entry.get("severity_level"),
                                    "days_after": self._calculate_days_between(
                                        nutrient_entry.get("created_at"), health_entry.get("created_at")
                                    ),
                                }
                            )
                            break

            correlation["patterns"] = patterns
            correlation["pattern_count"] = len(patterns)

            return correlation

        except Exception as e:
            logger.error("Failed to analyze correlation: %s", e)
            return {}

    def get_nutrient_recommendations(self, plant_id: int) -> dict[str, Any]:
        """
        Get nutrient recommendations based on history and health.

        Args:
            plant_id: Plant ID

        Returns:
            Recommendations dictionary
        """
        try:
            # Get recent nutrient history
            recent_nutrients = self.get_nutrient_history(plant_id, days=30)

            # Get recent health status
            recent_health = self.get_health_timeline(plant_id, days=7)

            # Calculate time since last application by type
            last_applications = {}
            for entry in recent_nutrients:
                nutrient_type = entry.get("nutrient_type")
                if nutrient_type not in last_applications:
                    last_applications[nutrient_type] = entry.get("created_at")

            # Basic recommendations (can be enhanced with ML later)
            recommendations = {
                "last_applications": last_applications,
                "recent_health_status": recent_health[0].get("health_status") if recent_health else "unknown",
                "suggestions": [],
            }

            # Simple rule-based suggestions
            if recent_health and recent_health[0].get("health_status") == "nutrient_deficiency":
                symptoms = recent_health[0].get("symptoms", [])
                if "yellowing_leaves" in symptoms:
                    recommendations["suggestions"].append(
                        {
                            "type": "nitrogen",
                            "reason": "Yellowing leaves may indicate nitrogen deficiency",
                            "priority": "high",
                        }
                    )

            return recommendations

        except Exception as e:
            logger.error("Failed to get recommendations: %s", e)
            return {}

    # ========================================================================
    # Utilities
    # ========================================================================

    def _calculate_days_between(self, date1: str, date2: str) -> int:
        """Calculate days between two ISO date strings."""
        try:
            d1 = datetime.fromisoformat(date1.replace("Z", "+00:00"))
            d2 = datetime.fromisoformat(date2.replace("Z", "+00:00"))
            return abs((d2 - d1).days)
        except Exception:
            return 0

    def update_entry(self, entry_id: int, updates: dict[str, Any]) -> bool:
        """
        Update a journal entry.

        Args:
            entry_id: Entry ID
            updates: Fields to update

        Returns:
            True if successful
        """
        return self.repo.update_entry(entry_id, updates)

    def delete_entry(self, entry_id: int) -> bool:
        """
        Delete a journal entry.

        Args:
            entry_id: Entry ID

        Returns:
            True if successful
        """
        return self.repo.delete_entry(entry_id)

    # ========================================================================
    # Extended Entry Types (Phase 7)
    # ========================================================================

    def record_pruning(
        self,
        plant_id: int,
        pruning_type: str,
        parts_removed: list[str] | None = None,
        notes: str = "",
        image_path: str | None = None,
        user_id: int | None = None,
    ) -> int | None:
        """
        Record a pruning/training event.

        Args:
            plant_id: Plant ID
            pruning_type: Type of pruning (topping, lollipopping, defoliation, lst, scrog)
            parts_removed: List of parts removed
            notes: Additional notes
            image_path: Path to image
            user_id: User who performed pruning

        Returns:
            entry_id if successful
        """
        try:
            entry_id = self.repo.create_pruning_entry(
                plant_id=plant_id,
                pruning_type=pruning_type,
                parts_removed=parts_removed,
                notes=notes,
                image_path=image_path,
                user_id=user_id,
            )

            if entry_id:
                logger.info("Recorded pruning for plant %s: %s", plant_id, pruning_type)

            return entry_id

        except Exception as e:
            logger.error("Failed to record pruning: %s", e)
            return None

    def record_stage_change(
        self,
        plant_id: int,
        from_stage: str,
        to_stage: str,
        trigger: str = "manual",
        notes: str = "",
        user_id: int | None = None,
    ) -> int | None:
        """
        Record a growth stage transition.

        Args:
            plant_id: Plant ID
            from_stage: Previous growth stage
            to_stage: New growth stage
            trigger: What triggered the change (manual, automatic, time_based)
            notes: Additional notes
            user_id: User who recorded the change

        Returns:
            entry_id if successful
        """
        try:
            entry_id = self.repo.create_stage_change_entry(
                plant_id=plant_id,
                from_stage=from_stage,
                to_stage=to_stage,
                trigger=trigger,
                notes=notes,
                user_id=user_id,
            )

            if entry_id:
                logger.info("Recorded stage change for plant %s: %s -> %s", plant_id, from_stage, to_stage)

            return entry_id

        except Exception as e:
            logger.error("Failed to record stage change: %s", e)
            return None

    def record_harvest(
        self,
        plant_id: int,
        harvest_type: str,
        weight_grams: float | None = None,
        quality_rating: int | None = None,
        notes: str = "",
        image_path: str | None = None,
        user_id: int | None = None,
    ) -> int | None:
        """
        Record a harvest event.

        Args:
            plant_id: Plant ID
            harvest_type: Type of harvest (partial, full)
            weight_grams: Harvest weight in grams
            quality_rating: Quality rating (1-5)
            notes: Additional notes
            image_path: Path to image
            user_id: User who performed harvest

        Returns:
            entry_id if successful
        """
        try:
            entry_id = self.repo.create_harvest_entry(
                plant_id=plant_id,
                harvest_type=harvest_type,
                weight_grams=weight_grams,
                quality_rating=quality_rating,
                notes=notes,
                image_path=image_path,
                user_id=user_id,
            )

            if entry_id:
                logger.info(
                    f"Recorded harvest for plant {plant_id}: {harvest_type}, {weight_grams}g, quality={quality_rating}"
                )

            return entry_id

        except Exception as e:
            logger.error("Failed to record harvest: %s", e)
            return None

    def record_environmental_adjustment(
        self,
        plant_id: int,
        adjustment_type: str,
        old_value: str,
        new_value: str,
        reason: str = "",
        user_id: int | None = None,
    ) -> int | None:
        """
        Record an environmental control adjustment.

        Args:
            plant_id: Plant ID
            adjustment_type: Type of adjustment (fan_speed, light_intensity, etc.)
            old_value: Previous setting value
            new_value: New setting value
            reason: Reason for the adjustment
            user_id: User who made the adjustment

        Returns:
            entry_id if successful
        """
        try:
            entry_id = self.repo.create_environmental_adjustment_entry(
                plant_id=plant_id,
                adjustment_type=adjustment_type,
                old_value=old_value,
                new_value=new_value,
                reason=reason,
                user_id=user_id,
            )

            if entry_id:
                logger.info(
                    f"Recorded environmental adjustment for plant {plant_id}: "
                    f"{adjustment_type} {old_value} -> {new_value}"
                )

            return entry_id

        except Exception as e:
            logger.error("Failed to record environmental adjustment: %s", e)
            return None

    def record_transplant(
        self,
        plant_id: int,
        from_container: str,
        to_container: str,
        new_medium: str | None = None,
        notes: str = "",
        user_id: int | None = None,
    ) -> int | None:
        """
        Record a transplanting event.

        Args:
            plant_id: Plant ID
            from_container: Original container/pot
            to_container: New container/pot
            new_medium: New growing medium (optional)
            notes: Additional notes
            user_id: User who performed transplant

        Returns:
            entry_id if successful
        """
        try:
            entry_id = self.repo.create_transplant_entry(
                plant_id=plant_id,
                from_container=from_container,
                to_container=to_container,
                new_medium=new_medium,
                notes=notes,
                user_id=user_id,
            )

            if entry_id:
                logger.info("Recorded transplant for plant %s: %s -> %s", plant_id, from_container, to_container)

            return entry_id

        except Exception as e:
            logger.error("Failed to record transplant: %s", e)
            return None

    # ========================================================================
    # Auto-Journaling Event Handlers
    # ========================================================================

    def handle_stage_update_event(self, payload) -> None:
        """
        Auto-record a journal entry when a plant stage changes.

        Subscribes to PlantEvent.PLANT_STAGE_UPDATE.
        """
        try:
            plant_id = getattr(payload, "plant_id", None) or (
                payload.get("plant_id") if isinstance(payload, dict) else None
            )
            new_stage = getattr(payload, "new_stage", None) or (
                payload.get("new_stage") if isinstance(payload, dict) else None
            )
            days_in_stage = getattr(payload, "days_in_stage", 0) or (
                payload.get("days_in_stage", 0) if isinstance(payload, dict) else 0
            )

            if not plant_id or not new_stage:
                return

            self.record_stage_change(
                plant_id=plant_id,
                from_stage="",
                to_stage=new_stage,
                trigger="automatic",
                notes=f"Auto-recorded stage update to '{new_stage}' (day {days_in_stage})",
            )
            logger.debug("Auto-journaled stage update for plant %s → %s", plant_id, new_stage)

        except Exception as e:
            logger.error("Auto-journal stage update failed: %s", e, exc_info=True)

    def handle_plant_added_event(self, payload) -> None:
        """
        Auto-record a journal entry when a plant is added.

        Subscribes to PlantEvent.PLANT_ADDED.
        """
        try:
            plant_id = getattr(payload, "plant_id", None) or (
                payload.get("plant_id") if isinstance(payload, dict) else None
            )
            unit_id = getattr(payload, "unit_id", None) or (
                payload.get("unit_id") if isinstance(payload, dict) else None
            )

            if not plant_id:
                return

            self.repo.create_note(
                plant_id=plant_id,
                notes=f"Plant added to unit {unit_id or 'unknown'}",
            )
            logger.debug("Auto-journaled plant added: %s", plant_id)

        except Exception as e:
            logger.error("Auto-journal plant added failed: %s", e, exc_info=True)

    def handle_plant_removed_event(self, payload) -> None:
        """
        Auto-record a journal entry when a plant is removed.

        Subscribes to PlantEvent.PLANT_REMOVED.
        """
        try:
            plant_id = getattr(payload, "plant_id", None) or (
                payload.get("plant_id") if isinstance(payload, dict) else None
            )
            unit_id = getattr(payload, "unit_id", None) or (
                payload.get("unit_id") if isinstance(payload, dict) else None
            )

            if not plant_id:
                return

            self.repo.create_note(
                plant_id=plant_id,
                notes=f"Plant removed from unit {unit_id or 'unknown'}",
            )
            logger.debug("Auto-journaled plant removed: %s", plant_id)

        except Exception as e:
            logger.error("Auto-journal plant removed failed: %s", e, exc_info=True)

    def handle_active_plant_changed_event(self, payload) -> None:
        """
        Auto-record a journal entry when a plant becomes active.

        Subscribes to PlantEvent.ACTIVE_PLANT_CHANGED.
        """
        try:
            plant_id = getattr(payload, "plant_id", None) or (
                payload.get("plant_id") if isinstance(payload, dict) else None
            )
            unit_id = getattr(payload, "unit_id", None) or (
                payload.get("unit_id") if isinstance(payload, dict) else None
            )

            if not plant_id:
                return

            self.repo.create_note(
                plant_id=plant_id,
                notes=f"Plant set as active in unit {unit_id or 'unknown'}",
            )
            logger.debug("Auto-journaled active plant changed: %s", plant_id)

        except Exception as e:
            logger.error("Auto-journal active plant changed failed: %s", e, exc_info=True)
