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

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

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
                    entry_type TEXT NOT NULL,  -- 'observation', 'nutrient', 'treatment', 'note'
                    
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
                    
                    FOREIGN KEY (plant_id) REFERENCES Plant(plant_id) ON DELETE CASCADE
                )
            """)
            
            # Create indexes for common queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_journal_plant 
                ON plant_journal(plant_id, created_at DESC)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_journal_type 
                ON plant_journal(entry_type, created_at DESC)
            """)
            
            conn.commit()

    # ========================================================================
    # CREATE Operations
    # ========================================================================

    def create_observation(
        self,
        plant_id: int,
        observation_type: str,
        unit_id: Optional[int] = None,
        health_status: Optional[str] = None,
        severity_level: Optional[int] = None,
        symptoms: Optional[str] = None,
        disease_type: Optional[str] = None,
        affected_parts: Optional[str] = None,
        environmental_factors: Optional[str] = None,
        treatment_applied: Optional[str] = None,
        plant_type: Optional[str] = None,
        growth_stage: Optional[str] = None,
        notes: str = "",
        image_path: Optional[str] = None,
        user_id: Optional[int] = None,
        observation_date: Optional[str] = None
    ) -> Optional[int]:
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
                cursor = conn.execute("""
                    INSERT INTO plant_journal (
                        plant_id, unit_id, entry_type, observation_type, health_status,
                        severity_level, symptoms, disease_type, affected_parts,
                        environmental_factors, treatment_applied, plant_type, growth_stage,
                        notes, image_path, user_id, observation_date
                    )
                    VALUES (?, ?, 'observation', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    plant_id, unit_id, observation_type, health_status,
                    severity_level, symptoms, disease_type, affected_parts,
                    environmental_factors, treatment_applied, plant_type, growth_stage,
                    notes, image_path, user_id, observation_date
                ))
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
        user_id: Optional[int] = None
    ) -> Optional[int]:
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
                cursor = conn.execute("""
                    INSERT INTO plant_journal (
                        plant_id, entry_type, nutrient_type, nutrient_name,
                        amount, unit, notes, user_id
                    )
                    VALUES (?, 'nutrient', ?, ?, ?, ?, ?, ?)
                """, (
                    plant_id, nutrient_type, nutrient_name,
                    amount, unit, notes, user_id
                ))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create nutrient entry: {e}")
            return None

    def create_treatment_entry(
        self,
        plant_id: int,
        treatment_type: str,
        treatment_name: str,
        notes: str = "",
        user_id: Optional[int] = None
    ) -> Optional[int]:
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
                cursor = conn.execute("""
                    INSERT INTO plant_journal (
                        plant_id, entry_type, treatment_type, treatment_name,
                        notes, user_id
                    )
                    VALUES (?, 'treatment', ?, ?, ?, ?)
                """, (plant_id, treatment_type, treatment_name, notes, user_id))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Failed to create treatment entry: {e}")
            return None

    def create_note(
        self,
        plant_id: int,
        notes: str,
        image_path: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Optional[int]:
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
                cursor = conn.execute("""
                    INSERT INTO plant_journal (
                        plant_id, entry_type, notes, image_path, user_id
                    )
                    VALUES (?, 'note', ?, ?, ?)
                """, (plant_id, notes, image_path, user_id))
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
        plant_id: Optional[int] = None,
        unit_id: Optional[int] = None,
        entry_type: Optional[str] = None,
        limit: int = 100,
        days: Optional[int] = None
    ) -> List[Dict[str, Any]]:
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
                params.append(f'-{days} days')

            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)

            with self.db.connection() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get entries: {e}")
            return []

    def get_nutrient_history(
        self,
        plant_id: int,
        nutrient_type: Optional[str] = None,
        days: int = 90
    ) -> List[Dict[str, Any]]:
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
            params = [plant_id, f'-{days} days']

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
        self,
        plant_id: int,
        days: int = 30,
        health_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
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
            params = [plant_id, f'-{days} days']

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

    def get_entry_by_id(self, entry_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a specific journal entry.
        
        Args:
            entry_id: Entry ID
            
        Returns:
            Entry data or None
        """
        try:
            with self.db.connection() as conn:
                cursor = conn.execute("""
                    SELECT j.*, p.name as plant_name, p.unit_id, p.plant_type
                    FROM plant_journal j
                    JOIN Plant p ON j.plant_id = p.plant_id
                    WHERE j.entry_id = ?
                """, (entry_id,))
                row = cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get entry: {e}")
            return None

    # ========================================================================
    # UPDATE Operations
    # ========================================================================

    def update_entry(
        self,
        entry_id: int,
        updates: Dict[str, Any]
    ) -> bool:
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

            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            values = list(updates.values())
            values.append(entry_id)

            with self.db.connection() as conn:
                conn.execute(f"""
                    UPDATE plant_journal
                    SET {set_clause}
                    WHERE entry_id = ?
                """, values)
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

    def get_nutrient_timeline(
        self,
        plant_id: int,
        days: int = 90
    ) -> Dict[str, List[Dict[str, Any]]]:
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
                nutrient_type = entry.get('nutrient_type', 'unknown')
                if nutrient_type not in timeline:
                    timeline[nutrient_type] = []
                timeline[nutrient_type].append(entry)
            
            return timeline

        except Exception as e:
            logger.error(f"Failed to get nutrient timeline: {e}")
            return {}

    def correlate_nutrients_with_health(
        self,
        plant_id: int,
        days: int = 60
    ) -> Dict[str, Any]:
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
                "nutrients_by_type": self._group_by_field(nutrients, 'nutrient_type'),
                "health_by_status": self._group_by_field(health_obs, 'health_status'),
                "timeline": self._merge_timelines(nutrients, health_obs)
            }

        except Exception as e:
            logger.error(f"Failed to correlate data: {e}")
            return {}

    def _group_by_field(self, entries: List[Dict], field: str) -> Dict[str, int]:
        """Group entries by a field and count."""
        counts = {}
        for entry in entries:
            value = entry.get(field, 'unknown')
            counts[value] = counts.get(value, 0) + 1
        return counts

    def _merge_timelines(
        self,
        nutrients: List[Dict],
        health_obs: List[Dict]
    ) -> List[Dict[str, Any]]:
        """Merge nutrient and health timelines chronologically."""
        combined = []
        
        for entry in nutrients:
            combined.append({
                'type': 'nutrient',
                'timestamp': entry.get('created_at'),
                'data': entry
            })
        
        for entry in health_obs:
            combined.append({
                'type': 'health',
                'timestamp': entry.get('created_at'),
                'data': entry
            })
        
        # Sort by timestamp descending
        combined.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return combined
