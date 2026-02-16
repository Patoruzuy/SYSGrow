"""
AI Training Data Operations
============================
Database operations for collecting ML training data.

Provides methods to:
- Collect health score training data from harvests
- Collect health status training data from observations
- Generate synthetic baseline samples for negative examples
"""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)


class AITrainingOperations:
    """Database operations for AI/ML training data collection."""

    @staticmethod
    def _timestamp_query_param(dt: datetime) -> str:
        """Return ISO8601 timestamp suitable for lexical range filtering."""
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        return dt.isoformat()

    def get_health_score_training_data(
        self,
        unit_id: int | None = None,
        plant_type: str | None = None,
        days_limit: int = 365,
        min_quality: int = 1,
    ) -> list[dict[str, Any]]:
        """
        Collect training data from harvests with quality ratings.

        Returns samples with:
        - Environmental snapshot at harvest time
        - 7-day averages before harvest
        - Quality rating as target (1-5 → 20-100)

        Args:
            unit_id: Optional filter by unit
            plant_type: Optional filter by plant type
            days_limit: How far back to look (default 365 days)
            min_quality: Minimum quality rating to include (default 1)

        Returns:
            List of training sample dictionaries
        """
        try:
            db = self.get_db()
            params: list[Any] = []
            filters: list[str] = ["phs.quality_rating >= ?"]
            params.append(min_quality)

            # Time filter
            cutoff = datetime.now(UTC) - timedelta(days=days_limit)
            filters.append("phs.harvested_date >= ?")
            params.append(self._timestamp_query_param(cutoff))

            if unit_id is not None:
                filters.append("phs.unit_id = ?")
                params.append(unit_id)

            if plant_type:
                filters.append("p.plant_type = ?")
                params.append(plant_type)

            where_clause = " AND ".join(filters)

            query = f"""
                SELECT
                    phs.harvest_id,
                    phs.plant_id,
                    phs.unit_id,
                    phs.planted_date,
                    phs.harvested_date,
                    phs.total_days,
                    phs.quality_rating,
                    phs.harvest_weight_grams,
                    phs.avg_temperature,
                    phs.avg_humidity,
                    phs.avg_co2,
                    p.plant_type,
                    p.current_stage AS final_stage
                FROM PlantHarvestSummary phs
                LEFT JOIN Plants p ON phs.plant_id = p.plant_id
                WHERE {where_clause}
                ORDER BY phs.harvested_date DESC
            """

            rows = db.execute(query, params).fetchall()
            samples = []

            for row in rows:
                harvest = dict(row)
                harvest_date = harvest.get("harvested_date")
                plant_id = harvest.get("plant_id")
                h_unit_id = harvest.get("unit_id")

                # Get environmental snapshot from 7 days before harvest
                env_data = self._get_environmental_snapshot(db, h_unit_id, harvest_date, days_before=7)

                # Get plant metrics from before harvest
                plant_data = self._get_plant_metrics_snapshot(db, plant_id, harvest_date, days_before=7)

                # Build training sample
                sample = {
                    "harvest_id": harvest.get("harvest_id"),
                    "plant_id": plant_id,
                    "unit_id": h_unit_id,
                    "plant_type": harvest.get("plant_type"),
                    "quality_rating": harvest.get("quality_rating"),
                    "target_score": (harvest.get("quality_rating") or 3) * 20,
                    "observation_date": harvest_date,
                    "plant_metrics": plant_data,
                    "env_metrics": env_data,
                    "plant_profile": {
                        "growth_stage": harvest.get("final_stage", "harvest"),
                        "plant_age_days": harvest.get("total_days", 60),
                        "days_in_stage": 0,  # At harvest
                    },
                    "thresholds": self._get_plant_thresholds(db, plant_id),
                }
                samples.append(sample)

            logger.info(
                f"Collected {len(samples)} health score training samples (unit_id={unit_id}, plant_type={plant_type})"
            )
            return samples

        except sqlite3.Error as exc:
            logger.error(f"Error collecting health score training data: {exc}")
            return []

    def get_health_status_training_data(
        self,
        unit_id: int | None = None,
        days_limit: int = 365,
        confirmed_only: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Collect training data from user health observations.

        Returns samples with:
        - Environmental conditions at observation time
        - User-assigned health status as target

        Args:
            unit_id: Optional filter by unit
            days_limit: How far back to look
            confirmed_only: Only include confirmed observations (default True)

        Returns:
            List of training sample dictionaries
        """
        try:
            db = self.get_db()
            params: list[Any] = []
            filters: list[str] = [
                "pj.entry_type = 'observation'",
                "pj.observation_type = 'health'",
                "pj.health_status IS NOT NULL",
            ]

            # Time filter
            cutoff = datetime.now(UTC) - timedelta(days=days_limit)
            filters.append("pj.created_at >= ?")
            params.append(self._timestamp_query_param(cutoff))

            if unit_id is not None:
                filters.append("pj.unit_id = ?")
                params.append(unit_id)

            if confirmed_only:
                # Only include observations with severity level set
                filters.append("pj.severity_level IS NOT NULL")

            where_clause = " AND ".join(filters)

            query = f"""
                SELECT
                    pj.entry_id,
                    pj.plant_id,
                    pj.unit_id,
                    pj.health_status,
                    pj.severity_level,
                    pj.symptoms,
                    pj.disease_type,
                    pj.plant_type,
                    pj.growth_stage,
                    pj.environmental_factors,
                    pj.created_at AS observation_date,
                    p.plant_type AS plant_species
                FROM plant_journal pj
                LEFT JOIN Plants p ON pj.plant_id = p.plant_id
                WHERE {where_clause}
                ORDER BY pj.created_at DESC
            """

            rows = db.execute(query, params).fetchall()
            samples = []

            for row in rows:
                obs = dict(row)
                obs_date = obs.get("observation_date")
                plant_id = obs.get("plant_id")
                obs_unit_id = obs.get("unit_id")

                # Parse stored environmental factors if available
                env_factors = {}
                if obs.get("environmental_factors"):
                    try:
                        env_factors = json.loads(obs["environmental_factors"])
                    except (TypeError, ValueError):
                        pass

                # Get environmental snapshot at observation time
                if not env_factors:
                    env_factors = self._get_environmental_snapshot(db, obs_unit_id, obs_date, days_before=1)

                # Get plant metrics at observation time
                plant_data = self._get_plant_metrics_snapshot(db, plant_id, obs_date, days_before=1)

                # Map health status to standardized labels
                health_status = self._normalize_health_status(obs.get("health_status"))

                sample = {
                    "entry_id": obs.get("entry_id"),
                    "plant_id": plant_id,
                    "unit_id": obs_unit_id,
                    "plant_type": obs.get("plant_species") or obs.get("plant_type"),
                    "health_status": health_status,
                    "severity_level": obs.get("severity_level", 3),
                    "observation_date": obs_date,
                    "plant_metrics": plant_data,
                    "env_metrics": env_factors,
                    "plant_profile": {
                        "growth_stage": obs.get("growth_stage", "vegetative"),
                        "plant_age_days": 30,  # Default, could calculate from plant
                        "days_in_stage": 14,
                    },
                    "thresholds": self._get_plant_thresholds(db, plant_id),
                }
                samples.append(sample)

            logger.info(f"Collected {len(samples)} health status training samples (unit_id={unit_id})")
            return samples

        except sqlite3.Error as exc:
            logger.error(f"Error collecting health status training data: {exc}")
            return []

    def generate_health_baseline_samples(
        self,
        unit_id: int,
        num_samples: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Generate synthetic 'healthy' samples from periods without issues.

        Uses times with no health observations as negative examples.
        Looks at sensor readings during periods of no reported problems.

        Args:
            unit_id: Unit ID to generate samples for
            num_samples: Number of samples to generate

        Returns:
            List of synthetic healthy training samples
        """
        try:
            db = self.get_db()

            # Get dates when health issues were reported
            issue_dates = db.execute(
                """
                SELECT DATE(created_at) as issue_date
                FROM plant_journal
                WHERE unit_id = ?
                  AND entry_type = 'observation'
                  AND observation_type = 'health'
                  AND health_status NOT IN ('healthy', 'good', 'excellent')
                GROUP BY DATE(created_at)
                """,
                (unit_id,),
            ).fetchall()
            issue_date_set = {row["issue_date"] for row in issue_dates}

            # Get sensor readings from healthy periods
            query = """
                SELECT
                    DATE(sr.timestamp) as reading_date,
                    sr.timestamp,
                    sr.reading_data,
                    s.sensor_id,
                    s.unit_id
                FROM SensorReading sr
                JOIN Sensor s ON sr.sensor_id = s.sensor_id
                WHERE s.unit_id = ?
                  AND sr.timestamp >= datetime('now', '-180 days')
                ORDER BY RANDOM()
                LIMIT ?
            """

            # Get more readings than needed, then filter
            rows = db.execute(query, (unit_id, num_samples * 3)).fetchall()

            samples = []
            for row in rows:
                reading = dict(row)
                reading_date = reading.get("reading_date")

                # Skip if this date had health issues
                if reading_date in issue_date_set:
                    continue

                # Parse reading data
                reading_data = {}
                if reading.get("reading_data"):
                    try:
                        reading_data = json.loads(reading["reading_data"])
                    except (TypeError, ValueError):
                        continue

                # Build sample with "healthy" label
                env_metrics = {
                    "temperature": reading_data.get("temperature", 22.0),
                    "humidity": reading_data.get("humidity", 60.0),
                    "vpd": reading_data.get("vpd", 1.0),
                }

                plant_metrics = {
                    "soil_moisture": reading_data.get("soil_moisture", 60.0),
                    "ph": reading_data.get("ph", 6.5),
                    "ec": reading_data.get("ec", 1.5),
                }

                sample = {
                    "plant_id": None,  # Synthetic sample
                    "unit_id": unit_id,
                    "plant_type": None,
                    "health_status": "healthy",
                    "severity_level": 1,
                    "observation_date": reading.get("timestamp"),
                    "plant_metrics": plant_metrics,
                    "env_metrics": env_metrics,
                    "plant_profile": {
                        "growth_stage": "vegetative",
                        "plant_age_days": 30,
                        "days_in_stage": 14,
                    },
                    "thresholds": None,
                    "is_synthetic": True,
                }
                samples.append(sample)

                if len(samples) >= num_samples:
                    break

            logger.info(f"Generated {len(samples)} synthetic healthy samples for unit {unit_id}")
            return samples

        except sqlite3.Error as exc:
            logger.error(f"Error generating baseline samples: {exc}")
            return []

    def _get_environmental_snapshot(
        self,
        db,
        unit_id: int | None,
        reference_date: str | None,
        days_before: int = 7,
    ) -> dict[str, float]:
        """Get averaged environmental readings before a reference date."""
        if not unit_id or not reference_date:
            return {
                "temperature": 22.0,
                "humidity": 60.0,
                "vpd": 1.0,
            }

        try:
            # Parse reference date
            if isinstance(reference_date, str):
                ref_dt = datetime.fromisoformat(reference_date.replace("Z", "+00:00"))
            else:
                ref_dt = reference_date

            start_dt = ref_dt - timedelta(days=days_before)

            query = """
                SELECT sr.reading_data
                FROM SensorReading sr
                JOIN Sensor s ON sr.sensor_id = s.sensor_id
                WHERE s.unit_id = ?
                  AND sr.timestamp >= ?
                  AND sr.timestamp <= ?
                ORDER BY sr.timestamp DESC
                LIMIT 100
            """

            rows = db.execute(
                query,
                (unit_id, self._timestamp_query_param(start_dt), reference_date),
            ).fetchall()

            temps = []
            humidities = []
            vpds = []

            for row in rows:
                data = row["reading_data"]
                if data:
                    try:
                        parsed = json.loads(data)
                        if parsed.get("temperature") is not None:
                            temps.append(float(parsed["temperature"]))
                        if parsed.get("humidity") is not None:
                            humidities.append(float(parsed["humidity"]))
                        if parsed.get("vpd") is not None:
                            vpds.append(float(parsed["vpd"]))
                    except (TypeError, ValueError, json.JSONDecodeError):
                        continue

            return {
                "temperature": sum(temps) / len(temps) if temps else 22.0,
                "humidity": sum(humidities) / len(humidities) if humidities else 60.0,
                "vpd": sum(vpds) / len(vpds) if vpds else 1.0,
            }

        except Exception as exc:
            logger.warning(f"Error getting environmental snapshot: {exc}")
            return {"temperature": 22.0, "humidity": 60.0, "vpd": 1.0}

    def _get_plant_metrics_snapshot(
        self,
        db,
        plant_id: int | None,
        reference_date: str | None,
        days_before: int = 7,
    ) -> dict[str, float]:
        """Get averaged plant sensor readings before a reference date."""
        if not plant_id or not reference_date:
            return {
                "soil_moisture": 60.0,
                "ph": 6.5,
                "ec": 1.5,
            }

        try:
            if isinstance(reference_date, str):
                ref_dt = datetime.fromisoformat(reference_date.replace("Z", "+00:00"))
            else:
                ref_dt = reference_date

            start_dt = ref_dt - timedelta(days=days_before)

            query = """
                SELECT soil_moisture, ph, ec
                FROM PlantReadings
                WHERE plant_id = ?
                  AND timestamp >= ?
                  AND timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 50
            """

            rows = db.execute(
                query,
                (plant_id, self._timestamp_query_param(start_dt), reference_date),
            ).fetchall()

            moistures = []
            phs = []
            ecs = []

            for row in rows:
                if row["soil_moisture"] is not None:
                    moistures.append(float(row["soil_moisture"]))
                if row["ph"] is not None:
                    phs.append(float(row["ph"]))
                if row["ec"] is not None:
                    ecs.append(float(row["ec"]))

            return {
                "soil_moisture": sum(moistures) / len(moistures) if moistures else 60.0,
                "ph": sum(phs) / len(phs) if phs else 6.5,
                "ec": sum(ecs) / len(ecs) if ecs else 1.5,
            }

        except Exception as exc:
            logger.warning(f"Error getting plant metrics snapshot: {exc}")
            return {"soil_moisture": 60.0, "ph": 6.5, "ec": 1.5}

    def _get_plant_thresholds(
        self,
        db,
        plant_id: int | None,
    ) -> dict[str, Any] | None:
        """Get optimal thresholds for a plant from its profile."""
        if not plant_id:
            return None

        try:
            row = db.execute(
                """
                SELECT plant_type, current_stage
                FROM Plants
                WHERE plant_id = ?
                """,
                (plant_id,),
            ).fetchone()

            if not row:
                return None

            # Return basic thresholds - could be enhanced to look up plant profiles
            return {
                "soil_moisture": {"min": 40.0, "max": 80.0, "optimal": 60.0},
                "temperature": {"min": 18.0, "max": 28.0, "optimal": 24.0},
                "humidity": {"min": 50.0, "max": 70.0, "optimal": 60.0},
                "vpd": {"min": 0.8, "max": 1.2, "optimal": 1.0},
                "ph": {"min": 5.5, "max": 7.0, "optimal": 6.5},
                "ec": {"min": 1.0, "max": 2.5, "optimal": 1.5},
            }

        except Exception as exc:
            logger.warning(f"Error getting plant thresholds: {exc}")
            return None

    def _normalize_health_status(self, status: str | None) -> str:
        """Normalize health status to standard labels."""
        if not status:
            return "healthy"

        status_lower = status.lower()

        # Map to standard labels: healthy, stressed, critical
        healthy_terms = ["healthy", "good", "excellent", "normal", "ok"]
        stressed_terms = ["stressed", "warning", "moderate", "fair", "nutrient_deficiency"]
        critical_terms = ["critical", "severe", "diseased", "dying", "dead"]

        if any(term in status_lower for term in healthy_terms):
            return "healthy"
        elif any(term in status_lower for term in critical_terms):
            return "critical"
        elif any(term in status_lower for term in stressed_terms):
            return "stressed"
        else:
            # Default based on keywords
            return "stressed"

    def count_available_training_samples(
        self,
        unit_id: int | None = None,
    ) -> dict[str, int]:
        """
        Count available training samples for health models.

        Returns counts of:
        - harvest_samples: Harvests with quality ratings
        - observation_samples: Health observations
        - total_samples: Combined count

        Useful for checking ML readiness.
        """
        try:
            db = self.get_db()

            # Count harvests with quality ratings
            harvest_query = """
                SELECT COUNT(*) as count
                FROM PlantHarvestSummary
                WHERE quality_rating IS NOT NULL
            """
            params: list[Any] = []
            if unit_id is not None:
                harvest_query += " AND unit_id = ?"
                params.append(unit_id)

            harvest_count = db.execute(harvest_query, params).fetchone()["count"]

            # Count health observations
            obs_query = """
                SELECT COUNT(*) as count
                FROM plant_journal
                WHERE entry_type = 'observation'
                  AND observation_type = 'health'
                  AND health_status IS NOT NULL
            """
            obs_params: list[Any] = []
            if unit_id is not None:
                obs_query += " AND unit_id = ?"
                obs_params.append(unit_id)

            obs_count = db.execute(obs_query, obs_params).fetchone()["count"]

            return {
                "harvest_samples": harvest_count,
                "observation_samples": obs_count,
                "total_samples": harvest_count + obs_count,
                "ml_ready": (harvest_count + obs_count) >= 50,
            }

        except sqlite3.Error as exc:
            logger.error(f"Error counting training samples: {exc}")
            return {
                "harvest_samples": 0,
                "observation_samples": 0,
                "total_samples": 0,
                "ml_ready": False,
            }

    # Placeholder for static analyzers
    def get_db(self):  # pragma: no cover
        raise NotImplementedError
