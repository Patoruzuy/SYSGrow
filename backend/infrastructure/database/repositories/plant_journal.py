"""
Plant Journal Repository
=========================
Data access layer for plant journal entries (observations and nutrients).

Provides unified access to:
- Health observations
- Nutrient applications
- Treatment records
- General notes and photos
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

logger = logging.getLogger(__name__)


class PlantJournalRepository:
    """Repository for plant journal operations."""

    def __init__(self, database_handler):
        """
        Initialize repository.

        Args:
            database_handler: Database handler instance
        """
        self.db = database_handler
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Ensure plant journal tables exist."""
        with self.db.connection() as conn:
            # Main journal table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS plant_journal (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plant_id INTEGER NOT NULL,
                    unit_id INTEGER,        -- Unit ID for context
                    entry_type TEXT NOT NULL,  -- 'observation', 'nutrient', 'treatment', 'note', 'watering'

                    -- Observation fields
                    observation_type TEXT,  -- 'health', 'growth', 'pest', 'disease', 'general'
                    health_status TEXT,     -- 'healthy', 'stressed', 'diseased', etc.
                    severity_level INTEGER, -- 1-5 scale
                    symptoms TEXT,          -- JSON array
                    disease_type TEXT,      -- 'fungal', 'bacterial', 'viral', 'pest', etc.
                    affected_parts TEXT,    -- JSON array of affected plant parts
                    environmental_factors TEXT,  -- JSON dict of environmental conditions
                    plant_type TEXT,        -- Plant species/type
                    growth_stage TEXT,      -- Growth stage during observation

                    -- Nutrient fields
                    nutrient_type TEXT,     -- 'nitrogen', 'phosphorus', 'potassium', 'calcium', 'custom'
                    nutrient_name TEXT,     -- Specific product name
                    amount REAL,            -- Amount applied
                    unit TEXT,              -- 'ml', 'g', 'tsp', etc.

                    -- Treatment fields
                    treatment_type TEXT,    -- 'fungicide', 'pesticide', 'pruning', etc.
                    treatment_name TEXT,    -- Product or action name
                    treatment_applied TEXT, -- Treatment that was applied (for observations)

                    -- Common fields
                    notes TEXT,
                    image_path TEXT,
                    user_id INTEGER,
                    observation_date TIMESTAMP,  -- Custom observation date
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    extra_data TEXT,  -- JSON blob for type-specific fields (Phase 7+)

                    FOREIGN KEY (plant_id) REFERENCES Plant(plant_id) ON DELETE CASCADE
                )
            """)

            # Migrate: add extra_data column if missing (existing databases)
            try:
                conn.execute("ALTER TABLE plant_journal ADD COLUMN extra_data TEXT")
                conn.commit()
                logger.info("Added extra_data column to plant_journal table")
            except Exception:
                pass  # Column already exists

            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_journal_plant
                ON plant_journal(plant_id, created_at DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_journal_type
                ON plant_journal(entry_type, created_at DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_journal_plant_type
                ON plant_journal(plant_id, entry_type)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_journal_health
                ON plant_journal(plant_id, health_status)
            """)

            conn.commit()

    # ========================================================================
    # CREATE Operations
    # ========================================================================

    def create_observation(
        self,
        plant_id: int,
        observation_type: str,
        unit_id: int | None = None,
        health_status: str | None = None,
        severity_level: int | None = None,
        symptoms: str | None = None,
        disease_type: str | None = None,
        affected_parts: str | None = None,
        environmental_factors: str | None = None,
        treatment_applied: str | None = None,
        plant_type: str | None = None,
        growth_stage: str | None = None,
        notes: str = "",
        image_path: str | None = None,
        user_id: int | None = None,
        observation_date: str | None = None,
    ) -> int | None:
        """
        Create a plant observation entry.

        Args:
            plant_id: Plant ID
            observation_type: Type of observation
            unit_id: Unit ID for context
            health_status: Health status if health-related
            severity_level: Severity (1-5)
            symptoms: JSON array of symptoms
            disease_type: Type of disease if applicable
            affected_parts: JSON array of affected plant parts
            environmental_factors: JSON dict of environmental conditions
            treatment_applied: Treatment that was applied
            plant_type: Plant species/type
            growth_stage: Growth stage during observation
            notes: Additional notes
            image_path: Path to observation image
            user_id: User who made observation
            observation_date: Custom observation date (ISO format)

        Returns:
            entry_id if successful, None otherwise
        """
        try:
            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO plant_journal (
                        plant_id, unit_id, entry_type, observation_type, health_status,
                        severity_level, symptoms, disease_type, affected_parts,
                        environmental_factors, treatment_applied, plant_type, growth_stage,
                        notes, image_path, user_id, observation_date
                    )
                    VALUES (?, ?, 'observation', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        plant_id,
                        unit_id,
                        observation_type,
                        health_status,
                        severity_level,
                        symptoms,
                        disease_type,
                        affected_parts,
                        environmental_factors,
                        treatment_applied,
                        plant_type,
                        growth_stage,
                        notes,
                        image_path,
                        user_id,
                        observation_date,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create observation: {e}")
            return None

    def create_nutrient_entry(
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
        Create a nutrient application entry.

        Args:
            plant_id: Plant ID
            nutrient_type: Type of nutrient (N/P/K/etc)
            nutrient_name: Product name
            amount: Amount applied
            unit: Unit of measurement
            notes: Additional notes
            user_id: User who applied nutrient

        Returns:
            entry_id if successful, None otherwise
        """
        try:
            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO plant_journal (
                        plant_id, entry_type, nutrient_type, nutrient_name,
                        amount, unit, notes, user_id
                    )
                    VALUES (?, 'nutrient', ?, ?, ?, ?, ?, ?)
                """,
                    (plant_id, nutrient_type, nutrient_name, amount, unit, notes, user_id),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create nutrient entry: {e}")
            return None

    def create_treatment_entry(
        self, plant_id: int, treatment_type: str, treatment_name: str, notes: str = "", user_id: int | None = None
    ) -> int | None:
        """
        Create a treatment entry.

        Args:
            plant_id: Plant ID
            treatment_type: Type of treatment
            treatment_name: Product/action name
            notes: Additional notes
            user_id: User who applied treatment

        Returns:
            entry_id if successful, None otherwise
        """
        try:
            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO plant_journal (
                        plant_id, entry_type, treatment_type, treatment_name,
                        notes, user_id
                    )
                    VALUES (?, 'treatment', ?, ?, ?, ?)
                """,
                    (plant_id, treatment_type, treatment_name, notes, user_id),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create treatment entry: {e}")
            return None

    def create_note(
        self, plant_id: int, notes: str, image_path: str | None = None, user_id: int | None = None
    ) -> int | None:
        """
        Create a general note entry.

        Args:
            plant_id: Plant ID
            notes: Note text
            image_path: Optional image
            user_id: User who created note

        Returns:
            entry_id if successful, None otherwise
        """
        try:
            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO plant_journal (
                        plant_id, entry_type, notes, image_path, user_id
                    )
                    VALUES (?, 'note', ?, ?, ?)
                """,
                    (plant_id, notes, image_path, user_id),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create note: {e}")
        return None

    # ========================================================================
    # READ Operations
    # ========================================================================

    def get_entries(
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
            unit_id: Filter by unit ID (gets all plants in unit)
            entry_type: Filter by type
            limit: Max entries to return
            days: Only entries from last N days

        Returns:
            List of journal entries
        """
        try:
            # Query without JOIN to avoid FK constraint issues with missing Plant table
            query = """
                SELECT *
                FROM plant_journal
                WHERE 1=1
            """
            params = []

            if plant_id is not None:
                query += " AND plant_id = ?"
                params.append(plant_id)

            if unit_id is not None:
                query += " AND unit_id = ?"
                params.append(unit_id)

            if entry_type:
                query += " AND entry_type = ?"
                params.append(entry_type)

            if days is not None:
                query += " AND created_at >= datetime('now', ?)"
                params.append(f"-{days} days")

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            with self.db.connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get entries: {e}")
            return []

    def get_nutrient_history(
        self, plant_id: int, nutrient_type: str | None = None, days: int = 90
    ) -> list[dict[str, Any]]:
        """
        Get nutrient application history for a plant.

        Args:
            plant_id: Plant ID
            nutrient_type: Filter by nutrient type
            days: Look back period

        Returns:
            List of nutrient entries
        """
        try:
            query = """
                SELECT *
                FROM plant_journal
                WHERE plant_id = ?
                AND entry_type = 'nutrient'
                AND created_at >= datetime('now', ?)
            """
            params = [plant_id, f"-{days} days"]

            if nutrient_type:
                query += " AND nutrient_type = ?"
                params.append(nutrient_type)

            query += " ORDER BY created_at DESC"

            with self.db.connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get nutrient history: {e}")
            return []

    def get_health_observations(
        self, plant_id: int, days: int = 30, health_status: str | None = None
    ) -> list[dict[str, Any]]:
        """
        Get health observations for a plant.

        Args:
            plant_id: Plant ID
            days: Look back period
            health_status: Filter by health status

        Returns:
            List of health observations
        """
        try:
            query = """
                SELECT *
                FROM plant_journal
                WHERE plant_id = ?
                AND entry_type = 'observation'
                AND observation_type = 'health'
                AND created_at >= datetime('now', ?)
            """
            params = [plant_id, f"-{days} days"]

            if health_status:
                query += " AND health_status = ?"
                params.append(health_status)

            query += " ORDER BY created_at DESC"

            with self.db.connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get health observations: {e}")
            return []

    def get_entry_by_id(self, entry_id: int) -> dict[str, Any] | None:
        """
        Get a specific journal entry.

        Args:
            entry_id: Entry ID

        Returns:
            Entry data or None
        """
        try:
            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT j.*, p.name as plant_name, p.unit_id, p.plant_type
                    FROM plant_journal j
                    JOIN Plant p ON j.plant_id = p.plant_id
                    WHERE j.entry_id = ?
                """,
                    (entry_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get entry: {e}")
            return None

    # ========================================================================
    # UPDATE Operations
    # ========================================================================

    def update_entry(self, entry_id: int, updates: dict[str, Any]) -> bool:
        """
        Update a journal entry.

        Args:
            entry_id: Entry ID
            updates: Dictionary of fields to update

        Returns:
            True if successful
        """
        try:
            if not updates:
                return False

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values())
            values.append(entry_id)

            with self.db.connection() as conn:
                conn.execute(
                    f"""
                    UPDATE plant_journal
                    SET {set_clause}
                    WHERE entry_id = ?
                """,
                    values,
                )
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to update entry: {e}")
            return False

    # ========================================================================
    # DELETE Operations
    # ========================================================================

    def delete_entry(self, entry_id: int) -> bool:
        """
        Delete a journal entry.

        Args:
            entry_id: Entry ID

        Returns:
            True if successful
        """
        try:
            with self.db.connection() as conn:
                conn.execute("DELETE FROM plant_journal WHERE entry_id = ?", (entry_id,))
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to delete entry: {e}")
            return False

    # ========================================================================
    # Analytics for AI
    # ========================================================================

    def get_nutrient_timeline(self, plant_id: int, days: int = 90) -> dict[str, list[dict[str, Any]]]:
        """
        Get nutrient application timeline grouped by type.

        Args:
            plant_id: Plant ID
            days: Look back period

        Returns:
            Dictionary mapping nutrient_type to list of applications
        """
        try:
            nutrients = self.get_nutrient_history(plant_id, days=days)

            timeline = {}
            for entry in nutrients:
                nutrient_type = entry.get("nutrient_type", "unknown")
                if nutrient_type not in timeline:
                    timeline[nutrient_type] = []
                timeline[nutrient_type].append(entry)

            return timeline

        except Exception as e:
            logger.error(f"Failed to get nutrient timeline: {e}")
            return {}

    def correlate_nutrients_with_health(self, plant_id: int, days: int = 60) -> dict[str, Any]:
        """
        Correlate nutrient applications with health observations.

        Args:
            plant_id: Plant ID
            days: Look back period

        Returns:
            Dictionary with correlation data for AI analysis
        """
        try:
            nutrients = self.get_nutrient_history(plant_id, days=days)
            health_obs = self.get_health_observations(plant_id, days=days)

            return {
                "plant_id": plant_id,
                "period_days": days,
                "total_nutrient_applications": len(nutrients),
                "total_health_observations": len(health_obs),
                "nutrients_by_type": self._group_by_field(nutrients, "nutrient_type"),
                "health_by_status": self._group_by_field(health_obs, "health_status"),
                "timeline": self._merge_timelines(nutrients, health_obs),
            }

        except Exception as e:
            logger.error(f"Failed to correlate data: {e}")
            return {}

    def _group_by_field(self, entries: list[dict], field: str) -> dict[str, int]:
        """Group entries by a field and count."""
        counts = {}
        for entry in entries:
            value = entry.get(field, "unknown")
            counts[value] = counts.get(value, 0) + 1
        return counts

    def _merge_timelines(self, nutrients: list[dict], health_obs: list[dict]) -> list[dict[str, Any]]:
        """Merge nutrient and health timelines chronologically."""
        combined = []

        for entry in nutrients:
            combined.append({"type": "nutrient", "timestamp": entry.get("created_at"), "data": entry})

        for entry in health_obs:
            combined.append({"type": "health", "timestamp": entry.get("created_at"), "data": entry})

        # Sort by timestamp descending
        combined.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        return combined

    # ========================================================================
    # Extended Retrieval Methods
    # ========================================================================

    def get_watering_history(
        self,
        plant_id: int,
        days: int = 90,
    ) -> list[dict[str, Any]]:
        """
        Get watering history for a plant.

        Args:
            plant_id: Plant ID
            days: Look back period

        Returns:
            List of watering entries with parsed extra_data
        """
        try:
            query = """
                SELECT *
                FROM plant_journal
                WHERE plant_id = ?
                  AND entry_type = 'watering'
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at DESC
            """
            with self.db.connection() as conn:
                cursor = conn.execute(query, [plant_id, f"-{days} days"])
                rows = [dict(row) for row in cursor.fetchall()]

            # Parse extra_data JSON for each row
            import json

            for row in rows:
                if row.get("extra_data"):
                    with contextlib.suppress(json.JSONDecodeError, TypeError):
                        row["extra_data"] = json.loads(row["extra_data"])
            return rows
        except Exception as e:
            logger.error(f"Failed to get watering history: {e}")
            return []

    def get_stage_timeline(self, plant_id: int) -> list[dict[str, Any]]:
        """
        Get the stage change timeline for a plant, ordered chronologically.

        Returns:
            List of stage_change entries (oldest first)
        """
        try:
            query = """
                SELECT entry_id, plant_id, observation_type AS from_stage,
                       growth_stage AS to_stage, treatment_type AS trigger,
                       notes, created_at
                FROM plant_journal
                WHERE plant_id = ?
                  AND entry_type = 'stage_change'
                ORDER BY created_at ASC
            """
            with self.db.connection() as conn:
                cursor = conn.execute(query, [plant_id])
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get stage timeline: {e}")
            return []

    def get_journal_summary(self, plant_id: int) -> dict[str, Any]:
        """
        Get aggregate journal summary for a plant.

        Returns:
            Dict with counts per entry type, last entry dates, etc.
        """
        try:
            with self.db.connection() as conn:
                # Total and per-type counts
                cursor = conn.execute(
                    """
                    SELECT entry_type, COUNT(*) as cnt
                    FROM plant_journal
                    WHERE plant_id = ?
                    GROUP BY entry_type
                """,
                    [plant_id],
                )
                entries_by_type = {}
                total = 0
                for row in cursor.fetchall():
                    entries_by_type[row["entry_type"]] = row["cnt"]
                    total += row["cnt"]

                # Last watering
                cursor = conn.execute(
                    """
                    SELECT created_at FROM plant_journal
                    WHERE plant_id = ? AND entry_type = 'watering'
                    ORDER BY created_at DESC LIMIT 1
                """,
                    [plant_id],
                )
                row = cursor.fetchone()
                last_watering = dict(row)["created_at"] if row else None

                # Last observation
                cursor = conn.execute(
                    """
                    SELECT created_at FROM plant_journal
                    WHERE plant_id = ? AND entry_type = 'observation'
                    ORDER BY created_at DESC LIMIT 1
                """,
                    [plant_id],
                )
                row = cursor.fetchone()
                last_observation = dict(row)["created_at"] if row else None

                # Last nutrient
                cursor = conn.execute(
                    """
                    SELECT created_at FROM plant_journal
                    WHERE plant_id = ? AND entry_type = 'nutrient'
                    ORDER BY created_at DESC LIMIT 1
                """,
                    [plant_id],
                )
                row = cursor.fetchone()
                last_nutrient = dict(row)["created_at"] if row else None

                # 30-day counts
                cursor = conn.execute(
                    """
                    SELECT
                        SUM(CASE WHEN entry_type = 'watering' THEN 1 ELSE 0 END) as watering_30d,
                        SUM(CASE WHEN entry_type = 'observation' THEN 1 ELSE 0 END) as observation_30d
                    FROM plant_journal
                    WHERE plant_id = ?
                      AND created_at >= datetime('now', '-30 days')
                """,
                    [plant_id],
                )
                counts = cursor.fetchone()
                watering_30d = (dict(counts)["watering_30d"] or 0) if counts else 0
                observation_30d = (dict(counts)["observation_30d"] or 0) if counts else 0

                # Health trend: last 5 health observations
                cursor = conn.execute(
                    """
                    SELECT health_status FROM plant_journal
                    WHERE plant_id = ? AND entry_type = 'observation'
                      AND observation_type = 'health' AND health_status IS NOT NULL
                    ORDER BY created_at DESC LIMIT 5
                """,
                    [plant_id],
                )
                recent_health = [dict(r)["health_status"] for r in cursor.fetchall()]
                health_trend = self._compute_health_trend(recent_health)

                return {
                    "plant_id": plant_id,
                    "total_entries": total,
                    "entries_by_type": entries_by_type,
                    "last_watering": last_watering,
                    "last_observation": last_observation,
                    "last_nutrient": last_nutrient,
                    "watering_count_30d": watering_30d,
                    "observation_count_30d": observation_30d,
                    "health_trend": health_trend,
                }
        except Exception as e:
            logger.error(f"Failed to get journal summary: {e}")
            return {"plant_id": plant_id, "total_entries": 0, "entries_by_type": {}}

    def get_watering_frequency(self, plant_id: int, days: int = 30) -> dict[str, Any]:
        """
        Calculate average watering frequency for a plant.

        Returns:
            Dict with avg_interval_days, total_waterings, period_days
        """
        try:
            query = """
                SELECT created_at
                FROM plant_journal
                WHERE plant_id = ?
                  AND entry_type = 'watering'
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at ASC
            """
            with self.db.connection() as conn:
                cursor = conn.execute(query, [plant_id, f"-{days} days"])
                rows = [dict(r)["created_at"] for r in cursor.fetchall()]

            if len(rows) < 2:
                return {
                    "avg_interval_days": None,
                    "total_waterings": len(rows),
                    "period_days": days,
                }

            from datetime import datetime as dt

            dates = []
            for ts in rows:
                with contextlib.suppress(Exception):
                    dates.append(dt.fromisoformat(ts.replace("Z", "+00:00")))

            if len(dates) < 2:
                return {
                    "avg_interval_days": None,
                    "total_waterings": len(rows),
                    "period_days": days,
                }

            intervals = [(dates[i + 1] - dates[i]).total_seconds() / 86400 for i in range(len(dates) - 1)]
            avg_interval = sum(intervals) / len(intervals)

            return {
                "avg_interval_days": round(avg_interval, 1),
                "total_waterings": len(rows),
                "period_days": days,
            }
        except Exception as e:
            logger.error(f"Failed to get watering frequency: {e}")
            return {"avg_interval_days": None, "total_waterings": 0, "period_days": days}

    def get_entries_paginated(
        self,
        plant_id: int,
        page: int = 1,
        per_page: int = 20,
        entry_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Get paginated journal entries.

        Args:
            plant_id: Plant ID
            page: Page number (1-based)
            per_page: Items per page (default 20)
            entry_type: Optional filter by entry_type

        Returns:
            Dict with items, page, per_page, total_pages, total_count
        """
        try:
            count_query = """
                SELECT COUNT(*) as cnt
                FROM plant_journal
                WHERE plant_id = ?
            """
            data_query = """
                SELECT *
                FROM plant_journal
                WHERE plant_id = ?
            """
            params: list = [plant_id]

            if entry_type:
                count_query += " AND entry_type = ?"
                data_query += " AND entry_type = ?"
                params.append(entry_type)

            data_query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            offset = (max(1, page) - 1) * per_page

            with self.db.connection() as conn:
                cursor = conn.execute(count_query, params)
                total_count = dict(cursor.fetchone())["cnt"]

                cursor = conn.execute(data_query, [*params, per_page, offset])
                items = [dict(row) for row in cursor.fetchall()]

            # Parse extra_data and JSON fields
            import json

            for item in items:
                for field in ("extra_data", "symptoms", "affected_parts", "environmental_factors"):
                    if item.get(field) and isinstance(item[field], str):
                        with contextlib.suppress(json.JSONDecodeError, TypeError):
                            item[field] = json.loads(item[field])

            import math

            total_pages = math.ceil(total_count / per_page) if per_page > 0 else 0

            return {
                "items": items,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
                "total_count": total_count,
            }
        except Exception as e:
            logger.error(f"Failed to get paginated entries: {e}")
            return {
                "items": [],
                "page": page,
                "per_page": per_page,
                "total_pages": 0,
                "total_count": 0,
            }

    @staticmethod
    def _compute_health_trend(recent_statuses: list[str]) -> str | None:
        """Compute health trend from recent health statuses."""
        if not recent_statuses:
            return None
        score_map = {"healthy": 3, "stressed": 2, "diseased": 1}
        scores = [score_map.get(s, 2) for s in recent_statuses]
        if len(scores) < 2:
            return "stable"
        # Compare average of first half vs second half
        mid = len(scores) // 2
        recent_avg = sum(scores[:mid]) / mid if mid > 0 else 0
        older_avg = sum(scores[mid:]) / (len(scores) - mid) if (len(scores) - mid) > 0 else 0
        if recent_avg > older_avg + 0.3:
            return "improving"
        elif recent_avg < older_avg - 0.3:
            return "declining"
        return "stable"

    # ========================================================================
    # Extended Entry Types (Phase 7)
    # ========================================================================

    def create_watering_entry(
        self,
        plant_id: int,
        amount_ml: float | None = None,
        method: str = "manual",
        source: str = "user",
        ph_level: float | None = None,
        ec_level: float | None = None,
        notes: str = "",
        user_id: int | None = None,
        *,
        unit_id: int | None = None,
        amount: float | None = None,
        unit: str = "ml",
        observation_date: str | None = None,
    ) -> int | None:
        """
        Record a watering event.

        Args:
            plant_id: Plant ID
            amount_ml: Amount of water in milliliters
            method: Watering method (manual, automatic, drip)
            source: Event source (user, sensor_triggered, schedule)
            ph_level: pH level of water (optional)
            ec_level: EC level of water (optional)
            notes: Additional notes
            user_id: User who performed watering

        Returns:
            entry_id if successful, None otherwise
        """
        try:
            normalized_unit = (unit or "ml").strip().lower()
            normalized_amount_ml: float | None

            if amount is not None:
                if normalized_unit in ("l", "liter", "liters"):
                    normalized_amount_ml = float(amount) * 1000.0
                else:
                    normalized_amount_ml = float(amount)
            elif amount_ml is not None:
                normalized_amount_ml = float(amount_ml)
            else:
                normalized_amount_ml = None

            stored_unit = normalized_unit if amount is not None else "ml"

            import json

            extra_data = json.dumps(
                {
                    "amount_ml": normalized_amount_ml,
                    "method": method,
                    "source": source,
                    "ph_level": ph_level,
                    "ec_level": ec_level,
                }
            )

            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO plant_journal (
                        plant_id, unit_id, entry_type, observation_type,
                        treatment_type, treatment_name, amount, unit,
                        notes, user_id, observation_date, extra_data
                    )
                    VALUES (?, ?, 'watering', 'watering', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        plant_id,
                        unit_id,
                        method,
                        source,
                        normalized_amount_ml,
                        stored_unit,
                        notes,
                        user_id,
                        observation_date,
                        extra_data,
                    ),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create watering entry: {e}")
            return None

    def create_pruning_entry(
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
            parts_removed: List of parts removed (leaves, branches, fan_leaves, etc.)
            notes: Additional notes
            image_path: Path to image
            user_id: User who performed pruning

        Returns:
            entry_id if successful, None otherwise
        """
        try:
            import json

            parts_json = json.dumps(parts_removed) if parts_removed else None

            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO plant_journal (
                        plant_id, entry_type, treatment_type, treatment_name,
                        affected_parts, notes, image_path, user_id
                    )
                    VALUES (?, 'pruning', ?, ?, ?, ?, ?, ?)
                """,
                    (plant_id, pruning_type, pruning_type, parts_json, notes, image_path, user_id),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create pruning entry: {e}")
            return None

    def create_stage_change_entry(
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
            entry_id if successful, None otherwise
        """
        try:
            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO plant_journal (
                        plant_id, entry_type, observation_type, growth_stage,
                        treatment_type, notes, user_id
                    )
                    VALUES (?, 'stage_change', ?, ?, ?, ?, ?)
                """,
                    (plant_id, from_stage, to_stage, trigger, notes, user_id),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create stage change entry: {e}")
            return None

    def create_harvest_entry(
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
            entry_id if successful, None otherwise
        """
        try:
            import json

            extra_data = json.dumps(
                {
                    "harvest_type": harvest_type,
                    "weight_grams": weight_grams,
                    "quality_rating": quality_rating,
                }
            )

            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO plant_journal (
                        plant_id, entry_type, treatment_type, amount,
                        severity_level, notes, image_path, user_id, extra_data
                    )
                    VALUES (?, 'harvest', ?, ?, ?, ?, ?, ?, ?)
                """,
                    (plant_id, harvest_type, weight_grams, quality_rating, notes, image_path, user_id, extra_data),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create harvest entry: {e}")
            return None

    def create_environmental_adjustment_entry(
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
            adjustment_type: Type of adjustment (fan_speed, light_intensity, light_schedule, temperature_target)
            old_value: Previous setting value
            new_value: New setting value
            reason: Reason for the adjustment
            user_id: User who made the adjustment

        Returns:
            entry_id if successful, None otherwise
        """
        try:
            import json

            extra_data = json.dumps(
                {
                    "adjustment_type": adjustment_type,
                    "old_value": old_value,
                    "new_value": new_value,
                }
            )

            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO plant_journal (
                        plant_id, entry_type, treatment_type,
                        notes, user_id, extra_data
                    )
                    VALUES (?, 'environmental_adjustment', ?, ?, ?, ?)
                """,
                    (plant_id, adjustment_type, reason, user_id, extra_data),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create environmental adjustment entry: {e}")
            return None

    def create_transplant_entry(
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
            entry_id if successful, None otherwise
        """
        try:
            import json

            extra_data = json.dumps(
                {
                    "from_container": from_container,
                    "to_container": to_container,
                    "new_medium": new_medium,
                }
            )

            with self.db.connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO plant_journal (
                        plant_id, entry_type, treatment_type, treatment_name,
                        notes, user_id, extra_data
                    )
                    VALUES (?, 'transplant', 'transplant', ?, ?, ?, ?)
                """,
                    (plant_id, f"{from_container} -> {to_container}", notes, user_id, extra_data),
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create transplant entry: {e}")
            return None
