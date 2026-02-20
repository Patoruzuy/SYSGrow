"""
Plant Harvest Service

Generates comprehensive harvest reports including energy consumption,
health history, and lifecycle analytics.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.repositories.analytics import AnalyticsRepository
    from infrastructure.database.repositories.devices import DeviceRepository
    from infrastructure.database.repositories.plants import PlantRepository

logger = logging.getLogger(__name__)


class PlantHarvestService:
    """
    Service for generating comprehensive plant harvest reports.

    Tracks full plant lifecycle from planting to harvest including:
    - Energy consumption by growth stage
    - Device usage breakdown
    - Light exposure hours
    - Health incidents
    - Environmental conditions
    - Yield and efficiency metrics
    """

    def __init__(
        self,
        analytics_repo: "AnalyticsRepository",
        plant_repo: "PlantRepository" | None = None,
        device_repo: "DeviceRepository" | None = None,
    ):
        """
        Initialize harvest service.

        Args:
            analytics_repo: AnalyticsRepository for database access
            plant_repo: PlantRepository for plant cleanup operations
            device_repo: DeviceRepository for pre-aggregated sensor summaries
        """
        self.analytics_repo = analytics_repo
        self._plant_repo = plant_repo
        self._device_repo = device_repo

    def generate_harvest_report(
        self, plant_id: int, harvest_weight_grams: float = 0.0, quality_rating: int = 3, notes: str = ""
    ) -> dict:
        """
        Generate comprehensive harvest report for a plant.

        Args:
            plant_id: Plant ID
            harvest_weight_grams: Harvest weight in grams
            quality_rating: Quality rating (1-5 scale)
            notes: Optional harvest notes

        Returns:
            Complete harvest report dictionary
        """
        try:
            # Get plant info
            plant_info = self.analytics_repo.get_plant_info(plant_id)
            if not plant_info:
                raise ValueError(f"Plant {plant_id} not found")

            # Convert Row to dict for easier access
            plant_dict = dict(plant_info) if hasattr(plant_info, "keys") else plant_info

            # Calculate lifecycle dates
            planted_date = plant_dict.get("planted_date") or plant_dict.get("created_at")
            if not planted_date:
                # Fallback to current date minus days_in_stage if no date available
                planted_date = (datetime.now() - timedelta(days=plant_dict.get("days_in_stage", 0))).isoformat()

            harvested_date = datetime.now()

            # Parse planted_date if it's a string
            if isinstance(planted_date, str):
                try:
                    planted_dt = datetime.fromisoformat(planted_date)
                except ValueError:
                    # Try parsing as datetime string
                    planted_dt = datetime.strptime(planted_date, "%Y-%m-%d %H:%M:%S")
            else:
                planted_dt = planted_date

            total_days = (harvested_date - planted_dt).days

            # Get energy summary
            energy_summary = self._get_energy_summary(plant_id, planted_dt, harvested_date)

            # Get health history
            health_summary = self._get_health_summary(plant_id)

            # Get environmental averages
            env_averages = self._get_environmental_averages(plant_id)

            # Get light exposure
            light_summary = self._get_light_summary(plant_id)

            # Calculate efficiency metrics
            efficiency = self._calculate_efficiency(
                energy_summary["total_kwh"], energy_summary["total_cost"], harvest_weight_grams
            )

            # Build comprehensive report
            report = {
                "harvest_id": None,  # Will be set after DB insert
                "plant_id": plant_id,
                "plant_name": plant_dict.get("name", "Unknown"),
                "unit_id": plant_dict.get("unit_id"),
                "lifecycle": {
                    "planted_date": planted_date if isinstance(planted_date, str) else planted_date.isoformat(),
                    "harvested_date": harvested_date.isoformat(),
                    "total_days": total_days,
                    "stages": self._get_stage_durations(plant_dict),
                },
                "energy_consumption": energy_summary,
                "light_exposure": light_summary,
                "environmental_conditions": env_averages,
                "health_summary": health_summary,
                "yield": {"weight_grams": harvest_weight_grams, "quality_rating": quality_rating, "notes": notes},
                "efficiency_metrics": efficiency,
                "recommendations": self._generate_recommendations(
                    energy_summary, health_summary, env_averages, total_days
                ),
            }

            # Save to database
            summary_data = self._prepare_db_summary(report)
            harvest_id = self.analytics_repo.save_harvest_summary(plant_id, summary_data)
            report["harvest_id"] = harvest_id

            logger.info("Generated harvest report for plant %s (harvest_id: %s)", plant_id, harvest_id)
            return report

        except Exception as e:  # TODO(narrow): complex orchestration — revisit
            logger.error("Failed to generate harvest report for plant %s: %s", plant_id, e)
            raise

    def _get_energy_summary(self, plant_id: int, planted_date: datetime, harvested_date: datetime) -> dict:
        """Get energy consumption summary"""
        try:
            return self.analytics_repo.get_plant_energy_summary(plant_id)
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Failed to get energy summary: %s", e)
            return {
                "total_kwh": 0.0,
                "total_cost": 0.0,
                "avg_daily_power_watts": 0.0,
                "by_stage": {},
                "cost_by_stage": {},
                "by_device": {},
            }

    def _get_health_summary(self, plant_id: int) -> dict:
        """Get health incident summary"""
        try:
            # This would query PlantHealthLogs table
            # Simplified for now
            return {
                "total_incidents": 0,
                "incidents": [],
                "disease_free_days": 0,
                "pest_free_days": 0,
                "avg_health_score": 95,
            }
        except (KeyError, TypeError, ValueError, AttributeError) as e:
            logger.warning("Failed to get health summary: %s", e)
            return {
                "total_incidents": 0,
                "incidents": [],
                "disease_free_days": 0,
                "pest_free_days": 0,
                "avg_health_score": 0,
            }

    def _get_environmental_averages(self, plant_id: int) -> dict:
        """Get environmental condition averages.

        Prefers pre-aggregated data from ``SensorReadingSummary`` (written by
        the ``maintenance.aggregate_sensor_data`` scheduled task) which
        survives raw-reading pruning.  Falls back to live analytics queries
        when summary data is unavailable.
        """
        # --- Try SensorReadingSummary first -----------------------------------
        summary_stats = self._fetch_summary_env_stats(plant_id)
        if summary_stats:
            return summary_stats

        # --- Fallback: live queries on raw readings ---------------------------
        try:
            avg_temp = self.analytics_repo.get_average_temperature(plant_id)
            avg_humidity = self.analytics_repo.get_average_humidity(plant_id)

            return {
                "temperature": {
                    "avg": round(avg_temp, 1),
                    "min": 0.0,
                    "max": 0.0,
                    "optimal_range": "22-26°C",
                    "within_range_percent": 90,
                },
                "humidity": {
                    "avg": round(avg_humidity, 1),
                    "min": 0.0,
                    "max": 0.0,
                    "optimal_range": "60-70%",
                    "within_range_percent": 85,
                },
                "co2": {"avg": 0, "optimal": "400-1000 ppm"},
            }
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.warning("Failed to get environmental averages: %s", e)
            return {
                "temperature": {"avg": 0, "min": 0, "max": 0},
                "humidity": {"avg": 0, "min": 0, "max": 0},
                "co2": {"avg": 0},
            }

    def _fetch_summary_env_stats(self, plant_id: int) -> dict | None:
        """Try to build environmental averages from SensorReadingSummary.

        Returns a fully-populated dict matching the ``_get_environmental_averages``
        schema, or ``None`` if summary data is unavailable.
        """
        if not self._device_repo:
            return None
        try:
            plant_info = self.analytics_repo.get_plant_info(plant_id)
            if not plant_info:
                return None
            plant_dict = dict(plant_info) if hasattr(plant_info, "keys") else plant_info
            unit_id = plant_dict.get("unit_id")
            if not unit_id:
                return None

            planted_date = plant_dict.get("planted_date") or plant_dict.get("created_at", "")
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = planted_date[:10] if planted_date else end_date

            stats = self._device_repo.get_sensor_summary_stats_for_harvest(
                unit_id=unit_id, start_date=start_date, end_date=end_date
            )
            if not stats:
                return None

            def _stat(sensor_type: str) -> dict:
                s = stats.get(sensor_type, {})
                return {
                    "avg": round(s["avg"], 1) if s.get("avg") is not None else 0.0,
                    "min": round(s["min"], 1) if s.get("min") is not None else 0.0,
                    "max": round(s["max"], 1) if s.get("max") is not None else 0.0,
                }

            result: dict = {}
            if "temperature" in stats or "temperature_sensor" in stats:
                t = _stat("temperature") if "temperature" in stats else _stat("temperature_sensor")
                t["optimal_range"] = "22-26°C"
                result["temperature"] = t
            else:
                result["temperature"] = {"avg": 0, "min": 0, "max": 0, "optimal_range": "22-26°C"}

            if "humidity" in stats or "humidity_sensor" in stats:
                h = _stat("humidity") if "humidity" in stats else _stat("humidity_sensor")
                h["optimal_range"] = "60-70%"
                result["humidity"] = h
            else:
                result["humidity"] = {"avg": 0, "min": 0, "max": 0, "optimal_range": "60-70%"}

            co2 = stats.get("co2", stats.get("co2_sensor", {}))
            if co2:
                result["co2"] = {
                    "avg": round(co2["avg"], 1) if co2.get("avg") is not None else 0,
                    "optimal": "400-1000 ppm",
                }
            else:
                result["co2"] = {"avg": 0, "optimal": "400-1000 ppm"}

            # Only return if we found at least one sensor type with data
            has_data = any(result[k].get("avg", 0) != 0 for k in ("temperature", "humidity"))
            return result if has_data else None

        except (KeyError, TypeError, ValueError, AttributeError, OSError) as exc:
            logger.debug("SensorReadingSummary lookup failed for plant %s: %s", plant_id, exc)
            return None

    def _get_light_summary(self, plant_id: int) -> dict:
        """Get light exposure summary"""
        try:
            total_hours = self.analytics_repo.get_total_light_hours(plant_id)

            return {
                "total_hours": round(total_hours, 1),
                "by_stage": {},  # Would calculate per stage
                "total_dli": 0,  # Daily Light Integral
            }
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.warning("Failed to get light summary: %s", e)
            return {"total_hours": 0.0, "by_stage": {}, "total_dli": 0}

    def _get_stage_durations(self, plant_info: dict) -> dict:
        """Get duration in each growth stage"""
        # This would parse the plant's growth stage history
        # Simplified for now
        return {
            "seedling": {"days": 7, "dates": "N/A"},
            "vegetative": {"days": 21, "dates": "N/A"},
            "flowering": {"days": 18, "dates": "N/A"},
        }

    def _calculate_efficiency(self, total_kwh: float, total_cost: float, harvest_weight_grams: float) -> dict:
        """Calculate efficiency metrics"""
        if harvest_weight_grams > 0 and total_kwh > 0:
            grams_per_kwh = harvest_weight_grams / total_kwh
            cost_per_gram = total_cost / harvest_weight_grams
            cost_per_pound = cost_per_gram * 453.592  # grams in a pound

            return {
                "grams_per_kwh": round(grams_per_kwh, 2),
                "cost_per_gram": round(cost_per_gram, 3),
                "cost_per_pound": round(cost_per_pound, 2),
                "energy_efficiency_rating": self._get_efficiency_rating(grams_per_kwh),
            }

        return {"grams_per_kwh": 0.0, "cost_per_gram": 0.0, "cost_per_pound": 0.0, "energy_efficiency_rating": "N/A"}

    def _get_efficiency_rating(self, grams_per_kwh: float) -> str:
        """Rate energy efficiency"""
        if grams_per_kwh >= 5.0:
            return "Excellent"
        elif grams_per_kwh >= 3.0:
            return "Good"
        elif grams_per_kwh >= 1.5:
            return "Average"
        else:
            return "Poor"

    def _generate_recommendations(
        self, energy_summary: dict, health_summary: dict, env_averages: dict, total_days: int
    ) -> dict:
        """Generate recommendations for next grow"""
        recommendations = {"next_grow": [], "cost_optimization": []}

        # Health-based recommendations
        if health_summary["avg_health_score"] >= 90:
            recommendations["next_grow"].append("Excellent health score! Maintain current practices.")
        elif health_summary["avg_health_score"] < 70:
            recommendations["next_grow"].append("Consider improving environmental controls to boost plant health.")

        # Energy optimization
        total_kwh = energy_summary.get("total_kwh", 0)
        if total_kwh > 0:
            recommendations["cost_optimization"].append(
                f"Total energy used: {total_kwh} kWh. Consider LED efficiency upgrades."
            )

        # Duration recommendations
        if total_days > 60:
            recommendations["next_grow"].append("Long growing cycle. Consider faster-growing varieties.")

        return recommendations

    def _prepare_db_summary(self, report: dict) -> dict:
        """Prepare summary data for database storage"""

        # Helper to parse cost values (handles both string "$X.XX" and float X.XX)
        def parse_cost(value):
            if isinstance(value, str):
                return float(value.replace("$", "").replace(",", ""))
            return float(value) if value else 0.0

        return {
            "unit_id": report.get("unit_id"),
            "planted_date": report["lifecycle"]["planted_date"],
            "harvested_date": report["lifecycle"]["harvested_date"],
            "total_days": report["lifecycle"]["total_days"],
            "seedling_days": report["lifecycle"]["stages"]["seedling"]["days"],
            "vegetative_days": report["lifecycle"]["stages"]["vegetative"]["days"],
            "flowering_days": report["lifecycle"]["stages"]["flowering"]["days"],
            "total_energy_kwh": report["energy_consumption"]["total_kwh"],
            "energy_by_stage": json.dumps(report["energy_consumption"]["by_stage"]),
            "total_cost": parse_cost(report["energy_consumption"]["total_cost"]),
            "cost_by_stage": json.dumps(report["energy_consumption"].get("cost_by_stage", {})),
            "device_usage": json.dumps(report["energy_consumption"]["by_device"]),
            "avg_daily_power_watts": report["energy_consumption"].get("avg_daily_power_watts", 0.0),
            "total_light_hours": report["light_exposure"]["total_hours"],
            "light_hours_by_stage": json.dumps(report["light_exposure"]["by_stage"]),
            "avg_ppfd": 0.0,
            "health_incidents": json.dumps(report["health_summary"]["incidents"]),
            "disease_days": 0,
            "pest_days": 0,
            "avg_health_score": report["health_summary"]["avg_health_score"],
            "avg_temperature": report["environmental_conditions"]["temperature"]["avg"],
            "avg_humidity": report["environmental_conditions"]["humidity"]["avg"],
            "avg_co2": report["environmental_conditions"]["co2"]["avg"],
            "harvest_weight_grams": report["yield"]["weight_grams"],
            "quality_rating": report["yield"]["quality_rating"],
            "notes": report["yield"]["notes"],
            "grams_per_kwh": report["efficiency_metrics"]["grams_per_kwh"],
            "cost_per_gram": parse_cost(report["efficiency_metrics"]["cost_per_gram"]),
        }

    def get_harvest_reports(self, unit_id: int | None = None) -> list[dict]:
        """
        Get all harvest reports, optionally filtered by unit.

        Args:
            unit_id: Optional unit ID filter

        Returns:
            List of harvest summaries
        """
        try:
            return self.analytics_repo.get_all_harvest_reports(unit_id)
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Failed to get harvest reports: %s", e)
            return []

    def compare_harvests(self, unit_id: int, limit: int = 10) -> list[dict]:
        """
        Get harvest efficiency trends for comparison.

        Args:
            unit_id: Unit ID
            limit: Number of harvests to compare

        Returns:
            List of harvest efficiency metrics
        """
        try:
            return self.analytics_repo.get_harvest_efficiency_trends(unit_id, limit)
        except (KeyError, TypeError, ValueError, OSError) as e:
            logger.error("Failed to compare harvests: %s", e)
            return []

    def cleanup_after_harvest(self, plant_id: int, delete_plant_data: bool = True) -> dict[str, int]:
        """
        Clean up plant-specific data after harvest.

        IMPORTANT: This only deletes PLANT-SPECIFIC data. Shared data is preserved:
        - Energy readings are KEPT (needed for other plants' reports)
        - Sensor readings are KEPT (shared across unit)
        - Environmental data is KEPT (shared across unit)
        - Device history is KEPT (affects multiple plants)

        Only deleted if delete_plant_data=True:
        - Plant record (from Plants table)
        - Plant health logs (PlantHealth, PlantHealthLogs)
        - Plant-sensor associations (PlantSensors)
        - Plant-unit associations (GrowthUnitPlants)
        - AI decisions specific to this plant

        Args:
            plant_id: Plant ID to clean up
            delete_plant_data: If True, delete plant-specific records

        Returns:
            Dictionary with counts of deleted records by type
        """
        deleted_counts = {
            "plant_health_logs": 0,
            "plant_sensors": 0,
            "plant_unit_associations": 0,
            "ai_decision_logs": 0,
            "plant_record": 0,
        }

        if not delete_plant_data:
            logger.info("Skipping plant data deletion for plant %s (delete_plant_data=False)", plant_id)
            return deleted_counts

        try:
            if self._plant_repo is not None:
                result = self._plant_repo.cleanup_plant_data(plant_id)
                # Map repository keys back to the legacy dict shape
                deleted_counts["plant_health_logs"] = result.get("plant_health_logs", 0)
                deleted_counts["plant_sensors"] = result.get("plant_sensors", 0)
                deleted_counts["plant_unit_associations"] = result.get("plant_unit_associations", 0)
                deleted_counts["plant_record"] = result.get("plant_record", 0)
            else:
                logger.warning(
                    "PlantRepository not available — falling back to raw SQL for plant %s cleanup",
                    plant_id,
                )
                deleted_counts = self._cleanup_plant_data_raw_sql(plant_id)
            return deleted_counts
        except Exception as e:  # TODO(narrow): delegates to raw SQL — sqlite3 errors possible
            logger.error("Failed to cleanup plant %s: %s", plant_id, e)
            raise

    def _cleanup_plant_data_raw_sql(self, plant_id: int) -> dict[str, int]:
        """Legacy fallback: cleanup via raw SQL when no PlantRepository is available."""
        deleted_counts: dict[str, int] = {
            "plant_health_logs": 0,
            "plant_sensors": 0,
            "plant_unit_associations": 0,
            "ai_decision_logs": 0,
            "plant_record": 0,
        }
        try:
            with self.analytics_repo._backend.connection() as conn:
                # 1. Delete plant health logs (plant-specific)
                deleted_counts["plant_health_logs"] = 0
                for table_name in ("PlantHealthLogs", "PlantHealth"):
                    try:
                        cursor = conn.execute(
                            f"DELETE FROM {table_name} WHERE plant_id = ?",  # nosec B608 — table_name is a compile-time constant
                            (plant_id,),
                        )
                        deleted_counts["plant_health_logs"] += cursor.rowcount
                    except Exception as exc:  # TODO(narrow): catches sqlite3.OperationalError via string check
                        if "no such table" in str(exc).lower():
                            continue
                        raise

                # 2. Delete plant-sensor associations (plant-specific)
                cursor = conn.execute("DELETE FROM PlantSensors WHERE plant_id = ?", (plant_id,))
                deleted_counts["plant_sensors"] = cursor.rowcount

                # 3. Delete plant-unit associations (plant-specific)
                cursor = conn.execute("DELETE FROM GrowthUnitPlants WHERE plant_id = ?", (plant_id,))
                deleted_counts["plant_unit_associations"] = cursor.rowcount

                # 4. Delete AI decision logs for this plant (optional - may want to keep for learning)
                # Uncomment if you want to delete AI decisions:
                # cursor = conn.execute(
                #     "DELETE FROM AI_DecisionLogs WHERE plant_id = ?",
                #     (plant_id,)
                # )
                # deleted_counts['ai_decision_logs'] = cursor.rowcount

                # 5. Clear active_plant_id from GrowthUnits (don't delete the unit!)
                conn.execute(
                    """
                    UPDATE GrowthUnits
                    SET active_plant_id = NULL
                    WHERE active_plant_id = ?
                    """,
                    (plant_id,),
                )

                # 6. Delete the plant record itself (LAST!)
                cursor = conn.execute("DELETE FROM Plants WHERE plant_id = ?", (plant_id,))
                deleted_counts["plant_record"] = cursor.rowcount

            logger.info(
                f"Cleaned up plant {plant_id}: "
                f"Health logs: {deleted_counts['plant_health_logs']}, "
                f"Sensor associations: {deleted_counts['plant_sensors']}, "
                f"Unit associations: {deleted_counts['plant_unit_associations']}, "
                f"Plant record: {deleted_counts['plant_record']}"
            )

            return deleted_counts

        except Exception as e:  # TODO(narrow): raw SQL fallback — sqlite3 errors possible
            logger.error("Failed to cleanup plant %s (raw SQL fallback): %s", plant_id, e)
            raise

    def harvest_and_cleanup(
        self,
        plant_id: int,
        harvest_weight_grams: float = 0.0,
        quality_rating: int = 3,
        notes: str = "",
        delete_plant_data: bool = True,
    ) -> dict:
        """
        Generate harvest report AND optionally clean up plant data.

        This is a convenience method that:
        1. Generates the comprehensive harvest report
        2. Saves it to PlantHarvestSummary table
        3. Optionally deletes plant-specific data (preserves shared data)

        Args:
            plant_id: Plant ID
            harvest_weight_grams: Harvest weight in grams
            quality_rating: Quality rating (1-5 scale)
            notes: Optional harvest notes
            delete_plant_data: If True, delete plant-specific records after harvest

        Returns:
            Dictionary with harvest report and cleanup results
        """
        try:
            # Generate harvest report first
            report = self.generate_harvest_report(
                plant_id=plant_id, harvest_weight_grams=harvest_weight_grams, quality_rating=quality_rating, notes=notes
            )

            # Clean up plant data if requested
            cleanup_results = None
            if delete_plant_data:
                cleanup_results = self.cleanup_after_harvest(plant_id=plant_id, delete_plant_data=True)

            return {
                "harvest_report": report,
                "cleanup_results": cleanup_results,
                "plant_data_deleted": delete_plant_data,
            }

        except Exception as e:  # TODO(narrow): complex orchestration — revisit
            logger.error("Failed to harvest and cleanup plant %s: %s", plant_id, e)
            raise
