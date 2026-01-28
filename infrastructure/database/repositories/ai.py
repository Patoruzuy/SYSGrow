"""
AI Data Repository
===================
Unified repository for AI/ML data access operations.

Consolidates disease prediction, plant health, and ML training data access
following the repository pattern used throughout the application.
"""

from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime, timedelta, timezone
import pandas as pd

if TYPE_CHECKING:
    from infrastructure.database.ops.analytics import AnalyticsOperations

logger = logging.getLogger(__name__)


class AIHealthDataRepository:
    """
    Repository for AI health and disease prediction data access.
    
    Provides domain-specific queries for:
    - Health observations and history
    - Disease training data collection
    - Environmental correlations
    - Recovery tracking
    """

    def __init__(self, backend: "AnalyticsOperations") -> None:
        """
        Initialize with database backend.
        
        Args:
            backend: AnalyticsOperations instance for database access
        """
        self._backend = backend

    def _decode_sensor_payload(self, raw: Optional[str]) -> Dict[str, Any]:
        """Decode SensorReading JSON payload into a dict."""
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    # ========== Health Observations ==========
    # NOTE: Health observations are now stored via PlantJournalService
    # This repository only provides READ access for AI analytics

    def get_observation_by_id(self, observation_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single health observation by ID.
        
        Args:
            observation_id: The observation ID
            
        Returns:
            Observation dict if found, None otherwise
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            cursor.execute(
                """
                SELECT entry_id, unit_id, plant_id, health_status,
                       symptoms, disease_type, severity_level, affected_parts,
                       environmental_factors, treatment_applied, notes,
                       plant_type, growth_stage, image_path, user_id, observation_date
                FROM plant_journal
                WHERE entry_id = ? AND entry_type = 'observation'
            """,
                (observation_id,),
            )

            result = cursor.fetchone()
            if result:
                return {
                    "observation_id": result[0],
                    "unit_id": result[1],
                    "plant_id": result[2],
                    "health_status": result[3],
                    "symptoms": result[4],
                    "disease_type": result[5],
                    "severity_level": result[6],
                    "affected_parts": result[7],
                    "environmental_factors": result[8],
                    "treatment_applied": result[9],
                    "notes": result[10],
                    "plant_type": result[11],
                    "growth_stage": result[12],
                    "image_path": result[13],
                    "user_id": result[14],
                    "observation_date": result[15],
                }
        except Exception as e:
            logger.error(f"Failed to get observation: {e}", exc_info=True)
        return None

    def get_recent_observations(
        self, unit_id: int, plant_id: Optional[int] = None, limit: int = 10, days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get recent health observations for a unit.
        
        Args:
            unit_id: The unit ID
            plant_id: Optional plant ID (defaults to unit's active plant)
            limit: Maximum number of observations to return
            days: Look back period in days
            
        Returns:
            List of observation dicts
        """
        resolved_plant_id = plant_id
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            if resolved_plant_id is None:
                cursor.execute(
                    "SELECT active_plant_id FROM GrowthUnits WHERE unit_id = ? LIMIT 1",
                    (unit_id,),
                )
                active = cursor.fetchone()
                resolved_plant_id = active[0] if active else None

            if resolved_plant_id is None:
                return []

            cursor.execute(
                """
                SELECT entry_id as observation_id, unit_id, plant_id, health_status,
                       symptoms, disease_type, severity_level, affected_parts,
                       environmental_factors, treatment_applied, notes,
                       plant_type, growth_stage, observation_date
                FROM plant_journal
                WHERE unit_id = ?
                  AND plant_id = ?
                  AND entry_type = 'observation'
                  AND created_at >= datetime('now', ?)
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (unit_id, resolved_plant_id, f'-{days} days', limit),
            )

            return [
                {
                    "observation_id": row[0],
                    "unit_id": row[1],
                    "plant_id": row[2],
                    "health_status": row[3],
                    "symptoms": row[4],
                    "disease_type": row[5],
                    "severity_level": row[6],
                    "affected_parts": row[7],
                    "environmental_factors": row[8],
                    "treatment_applied": row[9],
                    "notes": row[10],
                    "plant_type": row[11],
                    "growth_stage": row[12],
                    "observation_date": row[13],
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.error(
                "Failed to get recent observations (unit_id=%s, plant_id=%s): %s",
                unit_id,
                resolved_plant_id,
                e,
                exc_info=True,
            )
            return []

    def get_health_statistics(self, unit_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Get health statistics for a unit.
        
        Args:
            unit_id: The unit ID
            days: Look back period in days
            
        Returns:
            Dict with health statistics
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            cursor.execute(
                """
                SELECT 
                    COUNT(*) as total_observations,
                    SUM(CASE WHEN health_status = 'healthy' THEN 1 ELSE 0 END) as healthy_count,
                    SUM(CASE WHEN health_status = 'stressed' THEN 1 ELSE 0 END) as stressed_count,
                    SUM(CASE WHEN health_status = 'diseased' THEN 1 ELSE 0 END) as diseased_count,
                    AVG(severity_level) as avg_severity
                FROM plant_journal
                WHERE entry_type = 'observation' AND unit_id = ? AND created_at >= datetime('now', '-' || ? || ' days')
            """,
                (unit_id, days),
            )

            result = cursor.fetchone()
            if result:
                return {
                    "total_observations": result[0] or 0,
                    "healthy_count": result[1] or 0,
                    "stressed_count": result[2] or 0,
                    "diseased_count": result[3] or 0,
                    "avg_severity": round(result[4], 2) if result[4] else 0.0,
                }
        except Exception as e:
            logger.error(f"Failed to get health statistics: {e}", exc_info=True)

        return {
            "total_observations": 0,
            "healthy_count": 0,
            "stressed_count": 0,
            "diseased_count": 0,
            "avg_severity": 0.0,
        }

    # ========== Disease Training Data ==========

    def get_health_observations_range(
        self, start_date: str, end_date: str, unit_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get health observations within a date range for training.
        
        Args:
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            unit_id: Optional unit ID filter
            
        Returns:
            List of observations with plant info
        """
        try:
            unit_filter = "AND ph.unit_id = ?" if unit_id else ""
            params = (
                (start_date, end_date, unit_id) if unit_id else (start_date, end_date)
            )

            query = f"""
                SELECT 
                    ph.*,
                    p.plant_type,
                    p.current_stage as growth_stage
                FROM PlantHealthLogs ph
                LEFT JOIN Plants p ON ph.plant_id = p.plant_id
                WHERE ph.observation_date BETWEEN ? AND ?
                {unit_filter}
                ORDER BY ph.observation_date ASC
            """

            db = self._backend.get_db()
            cursor = db.cursor()
            cursor.execute(query, params)
            
            # Convert rows to dicts
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting health observations: {e}", exc_info=True)
            return []

    def get_sensor_aggregates(
        self, unit_id: int, start_date: str, end_date: str
    ) -> Dict[str, float]:
        """
        Get aggregated sensor statistics for a time period.
        
        Used for feature engineering in disease prediction.
        
        Args:
            unit_id: The unit ID
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            
        Returns:
            Dict with aggregated sensor stats
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            # 72-hour aggregates
            cursor.execute(
                """
                SELECT 
                    AVG(CAST(json_extract(reading_data, '$.temperature') AS REAL)) as temp_mean,
                    STDEV(CAST(json_extract(reading_data, '$.temperature') AS REAL)) as temp_std,
                    MAX(CAST(json_extract(reading_data, '$.temperature') AS REAL)) as temp_max,
                    MIN(CAST(json_extract(reading_data, '$.temperature') AS REAL)) as temp_min,
                    AVG(CAST(json_extract(reading_data, '$.humidity') AS REAL)) as humidity_mean,
                    STDEV(CAST(json_extract(reading_data, '$.humidity') AS REAL)) as humidity_std,
                    MAX(CAST(json_extract(reading_data, '$.humidity') AS REAL)) as humidity_max,
                    AVG(CAST(json_extract(reading_data, '$.soil_moisture') AS REAL)) as moisture_mean,
                    STDEV(CAST(json_extract(reading_data, '$.soil_moisture') AS REAL)) as moisture_std,
                    AVG(CAST(json_extract(reading_data, '$.co2') AS REAL)) as co2_mean,
                    AVG(CAST(json_extract(reading_data, '$.voc') AS REAL)) as voc_mean
                FROM SensorReading sr
                JOIN Sensor s ON sr.sensor_id = s.sensor_id
                WHERE s.unit_id = ?
                AND sr.timestamp BETWEEN ? AND ?
            """,
                (unit_id, start_date, end_date),
            )

            result = cursor.fetchone()
            if result:
                columns = [desc[0] for desc in cursor.description]
                aggregates = dict(zip(columns, result))

                # Get 24h patterns as well
                end_24h = datetime.fromisoformat(end_date)
                start_24h = (end_24h - timedelta(hours=24)).isoformat()

                cursor.execute(
                    """
                    SELECT 
                        AVG(CAST(json_extract(reading_data, '$.temperature') AS REAL)) as temp_mean_24h,
                        AVG(CAST(json_extract(reading_data, '$.humidity') AS REAL)) as humidity_mean_24h
                    FROM SensorReading sr
                    JOIN Sensor s ON sr.sensor_id = s.sensor_id
                    WHERE s.unit_id = ?
                    AND sr.timestamp BETWEEN ? AND ?
                """,
                    (unit_id, start_24h, end_date),
                )

                result_24h = cursor.fetchone()
                if result_24h:
                    columns_24h = [desc[0] for desc in cursor.description]
                    aggregates.update(dict(zip(columns_24h, result_24h)))

                return aggregates

            return {}

        except Exception as e:
            logger.warning(f"Error getting sensor aggregates: {e}")
            return {}

    def get_sensor_time_series(
        self, unit_id: int, start_date: str, end_date: str, interval_hours: int = 1
    ) -> pd.DataFrame:
        """
        Get sensor time series data for feature engineering.
        Uses SensorReading for unit-level environmental metrics.

        Args:
            unit_id: Unit ID
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            interval_hours: Resampling interval

        Returns:
            DataFrame with timestamp index and sensor columns
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            cursor.execute(
                """
                SELECT 
                    sr.timestamp,
                    sr.reading_data
                FROM SensorReading sr
                JOIN Sensor s ON s.sensor_id = sr.sensor_id
                WHERE s.unit_id = ?
                  AND sr.timestamp BETWEEN ? AND ?
                ORDER BY sr.timestamp ASC
            """,
                (unit_id, start_date, end_date),
            )

            rows = cursor.fetchall()
            if not rows:
                return pd.DataFrame()

            records: List[Dict[str, Any]] = []
            for row in rows:
                timestamp = row[0]
                payload = self._decode_sensor_payload(row[1])
                if not payload:
                    continue
                record: Dict[str, Any] = {"timestamp": timestamp}
                for key in (
                    "temperature",
                    "humidity",
                    "soil_moisture",
                    "co2",
                    "voc",
                    "air_quality",
                    "pressure",
                    "lux",
                ):
                    if key in payload:
                        record[key] = payload[key]
                records.append(record)

            if not records:
                return pd.DataFrame()

            df = pd.DataFrame(records)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)

            # Merge soil moisture from PlantReadings (plant sensors only)
            try:
                cursor.execute(
                    """
                    SELECT timestamp, soil_moisture
                    FROM PlantReadings
                    WHERE unit_id = ?
                      AND timestamp BETWEEN ? AND ?
                      AND soil_moisture IS NOT NULL
                    ORDER BY timestamp ASC
                    """,
                    (unit_id, start_date, end_date),
                )
                moisture_rows = cursor.fetchall()
                if moisture_rows:
                    moisture_df = pd.DataFrame(moisture_rows, columns=["timestamp", "soil_moisture"])
                    moisture_df["timestamp"] = pd.to_datetime(moisture_df["timestamp"])
                    moisture_df.set_index("timestamp", inplace=True)
                    df = df.join(moisture_df, how="outer")
            except Exception as exc:
                logger.debug("Failed to merge PlantReadings soil moisture: %s", exc, exc_info=True)

            # Resample to regular intervals
            if interval_hours > 0:
                df = df.resample(f"{interval_hours}h").mean()

                return df

        except Exception as e:
            logger.error(f"Error getting sensor time series: {e}", exc_info=True)
            return pd.DataFrame()

    def get_sensor_readings_for_period(
        self, unit_id: int, start_time: str, end_time: str, metric: str
    ) -> List[tuple]:
        """
        Get sensor readings for environmental correlation analysis.

        Args:
            unit_id: Unit ID
            start_time: ISO format start time
            end_time: ISO format end time
            metric: Metric name (temperature, humidity, etc.)

        Returns:
            List of (timestamp, value) tuples
        """
        try:
            # Validate metric to prevent SQL injection
            valid_metrics = [
                "temperature",
                "humidity",
                "soil_moisture",
                "co2",
                "voc",
                "air_quality",
                "pressure",
                "lux",
                "ec",
                "ph",
                "smoke",
                "full_spectrum",
                "infrared",
                "visible"
            ]
            if metric not in valid_metrics:
                logger.warning(f"Invalid metric requested: {metric}")
                return []

            db = self._backend.get_db()
            cursor = db.cursor()

            query = f"""
                SELECT timestamp, CAST(json_extract(reading_data, '$.{metric}') AS REAL)
                FROM SensorReading sr
                JOIN Sensor s ON sr.sensor_id = s.sensor_id
                WHERE s.unit_id = ?
                  AND sr.timestamp BETWEEN ? AND ?
                  AND json_extract(reading_data, '$.{metric}') IS NOT NULL
                ORDER BY timestamp
            """

            cursor.execute(query, (unit_id, start_time, end_time))
            return cursor.fetchall()

        except Exception as e:
            logger.error(f"Failed to get sensor readings: {e}", exc_info=True)
            return []

    def get_disease_statistics(
        self, days: int = 90, unit_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get disease occurrence statistics.

        Args:
            days: Number of days to analyze
            unit_id: Optional unit ID filter

        Returns:
            Dictionary with disease statistics
        """
        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()

            unit_filter = "AND ph.unit_id = ?" if unit_id else ""
            params = (start_date, unit_id) if unit_id else (start_date,)

            db = self._backend.get_db()
            cursor = db.cursor()

            # Disease type distribution
            query = f"""
                SELECT 
                    disease_type,
                    COUNT(*) as count,
                    AVG(severity_level) as avg_severity
                FROM PlantHealthLogs ph
                WHERE observation_date >= ?
                {unit_filter}
                AND disease_type IS NOT NULL
                GROUP BY disease_type
                ORDER BY count DESC
            """

            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            disease_dist = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # Health status distribution
            query = f"""
                SELECT 
                    health_status,
                    COUNT(*) as count
                FROM PlantHealthLogs ph
                WHERE observation_date >= ?
                {unit_filter}
                GROUP BY health_status
                ORDER BY count DESC
            """

            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            health_dist = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # Most common symptoms
            query = f"""
                SELECT 
                    symptoms,
                    COUNT(*) as count
                FROM PlantHealthLogs ph
                WHERE observation_date >= ?
                {unit_filter}
                AND symptoms IS NOT NULL
                GROUP BY symptoms
                ORDER BY count DESC
                LIMIT 10
            """

            cursor.execute(query, params)
            columns = [desc[0] for desc in cursor.description]
            symptom_dist = [dict(zip(columns, row)) for row in cursor.fetchall()]

            return {
                "disease_distribution": disease_dist,
                "health_distribution": health_dist,
                "common_symptoms": symptom_dist,
                "total_observations": (
                    sum(row["count"] for row in health_dist) if health_dist else 0
                ),
            }

        except Exception as e:
            logger.error(f"Error getting disease statistics: {e}", exc_info=True)
            return {}

    # ========== Environmental Correlations ==========

    def save_environmental_correlation(
        self,
        unit_id: int,
        health_status: str,
        severity: int,
        correlations: List[Dict[str, Any]],
        observation_date: Optional[str] = None,
    ) -> Optional[int]:
        """
        Save environmental correlation data for ML training.

        Args:
            unit_id: Growth unit ID
            health_status: Plant health status
            severity: Severity level (1-5)
            correlations: List of correlation dictionaries
            observation_date: ISO format date string

        Returns:
            ID of inserted record, or None on failure
        """
        try:
            import json
            from app.utils.time import iso_now

            db = self._backend.get_db()
            cursor = db.cursor()

            cursor.execute(
                """
                INSERT INTO PlantHealthLogs (
                    unit_id, health_status, severity_level,
                    environmental_factors, observation_date
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    unit_id,
                    health_status,
                    severity,
                    json.dumps({"correlations": correlations}),
                    observation_date or iso_now(),
                ),
            )
            db.commit()
            return cursor.lastrowid

        except Exception as e:
            logger.error(f"Failed to save correlation: {e}", exc_info=True)
            return None

    def get_correlations_for_unit(
        self, unit_id: int, days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Get environmental correlations for a unit.

        Args:
            unit_id: Growth unit ID
            days: Number of days to look back

        Returns:
            List of correlation records
        """
        try:
            import json

            db = self._backend.get_db()
            cursor = db.cursor()

            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            cursor.execute(
                """
                SELECT health_status, severity_level, environmental_factors,
                       observation_date
                FROM PlantHealthLogs
                WHERE unit_id = ? AND observation_date >= ?
                AND environmental_factors IS NOT NULL
                ORDER BY observation_date DESC
                """,
                (unit_id, cutoff),
            )

            results = []
            for row in cursor.fetchall():
                env_factors = row[2]
                if env_factors:
                    try:
                        env_factors = json.loads(env_factors)
                    except json.JSONDecodeError:
                        env_factors = {}

                results.append({
                    "health_status": row[0],
                    "severity_level": row[1],
                    "environmental_factors": env_factors,
                    "observation_date": row[3],
                })

            return results

        except Exception as e:
            logger.error(f"Failed to get correlations: {e}", exc_info=True)
            return []


class AITrainingDataRepository:
    """
    Repository for ML training data operations.
    
    Handles training session metadata, model performance tracking,
    and training data collection.
    """

    def __init__(self, backend: "AnalyticsOperations") -> None:
        """
        Initialize with database backend.
        
        Args:
            backend: AnalyticsOperations instance for database access
        """
        self._backend = backend

    def _decode_sensor_payload(self, raw: Optional[str]) -> Dict[str, Any]:
        """Decode SensorReading JSON payload into a dict."""
        if not raw:
            return {}
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _collect_sensor_training_data(
        self,
        *,
        start_date: str,
        end_date: str,
        unit_id: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Collect sensor readings for training from SensorReading table.
        """
        db = self._backend.get_db()
        cursor = db.cursor()

        unit_filter = "AND s.unit_id = ?" if unit_id else ""
        params = [start_date, end_date]
        if unit_id:
            params.append(unit_id)

        limit_clause = "LIMIT ?" if limit else ""
        if limit:
            params.append(limit)

        cursor.execute(
            f"""
            SELECT
                sr.timestamp,
                s.unit_id,
                ps.plant_id,
                sr.reading_data
            FROM SensorReading sr
            JOIN Sensor s ON s.sensor_id = sr.sensor_id
            LEFT JOIN PlantSensors ps ON ps.sensor_id = sr.sensor_id
            WHERE sr.timestamp BETWEEN ? AND ?
            {unit_filter}
            ORDER BY sr.timestamp ASC
            {limit_clause}
            """,
            params,
        )

        from app.utils.time import coerce_datetime

        env_records: List[Dict[str, Any]] = []
        for row in cursor.fetchall():
            timestamp, row_unit_id, plant_id, reading_data = row
            payload = self._decode_sensor_payload(reading_data)
            if not payload:
                continue
            env_records.append(
                {
                    "timestamp": timestamp,
                    "unit_id": row_unit_id,
                    "plant_id": plant_id,
                    "temperature": payload.get("temperature"),
                    "humidity": payload.get("humidity"),
                    "soil_moisture": None,
                    "co2": payload.get("co2"),
                    "voc": payload.get("voc"),
                    "air_quality": payload.get("air_quality"),
                    "pressure": payload.get("pressure"),
                    "lux": payload.get("lux"),
                }
            )

        # Pull per-plant soil moisture from PlantReadings and merge with latest env metrics.
        plant_params = [start_date, end_date]
        plant_filter = ""
        if unit_id:
            plant_filter = "AND unit_id = ?"
            plant_params.append(unit_id)

        cursor.execute(
            f"""
            SELECT timestamp, unit_id, plant_id, soil_moisture
            FROM PlantReadings
            WHERE timestamp BETWEEN ? AND ?
              AND soil_moisture IS NOT NULL
            {plant_filter}
            ORDER BY timestamp ASC
            """,
            plant_params,
        )
        plant_rows = cursor.fetchall()

        env_records_sorted: List[Dict[str, Any]] = []
        for record in env_records:
            ts = coerce_datetime(record["timestamp"])
            if ts is None:
                continue
            record["_ts"] = ts
            env_records_sorted.append(record)
        env_records_sorted.sort(key=lambda r: r["_ts"])

        records: List[Dict[str, Any]] = []
        records.extend(env_records_sorted)

        env_idx = 0
        current_env: Optional[Dict[str, Any]] = None
        for row in plant_rows:
            timestamp, row_unit_id, plant_id, soil_moisture = row
            ts = coerce_datetime(timestamp)
            if ts is None:
                continue

            while env_idx < len(env_records_sorted) and env_records_sorted[env_idx]["_ts"] <= ts:
                current_env = env_records_sorted[env_idx]
                env_idx += 1

            merged = {
                "timestamp": timestamp,
                "unit_id": row_unit_id,
                "plant_id": plant_id,
                "temperature": current_env.get("temperature") if current_env else None,
                "humidity": current_env.get("humidity") if current_env else None,
                "soil_moisture": soil_moisture,
                "co2": current_env.get("co2") if current_env else None,
                "voc": current_env.get("voc") if current_env else None,
                "air_quality": current_env.get("air_quality") if current_env else None,
                "pressure": current_env.get("pressure") if current_env else None,
                "lux": current_env.get("lux") if current_env else None,
                "_ts": ts,
            }
            records.append(merged)

        records.sort(key=lambda r: r.get("_ts") or coerce_datetime(r.get("timestamp")) or datetime.min.replace(tzinfo=timezone.utc))
        for record in records:
            record.pop("_ts", None)

        return records

    def get_training_data(
        self,
        model_type: str,
        start_date: str,
        end_date: str,
        unit_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get training data for ML models.
        
        Args:
            model_type: Type of model ('climate', 'disease', 'growth')
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            unit_id: Optional unit filter
            
        Returns:
            List of training data records
        """
        try:
            if model_type == "climate":
                # Use SensorReading as the source of truth for training data.
                return self._collect_sensor_training_data(
                    start_date=start_date,
                    end_date=end_date,
                    unit_id=unit_id,
                )

            if model_type == "disease":
                # Get plant health logs for disease prediction
                # Use PlantHealthLogs table which actually exists
                db = self._backend.get_db()
                cursor = db.cursor()
                unit_filter = "AND phl.unit_id = ?" if unit_id else ""
                params = [start_date, end_date]
                if unit_id:
                    params.append(unit_id)
                    
                cursor.execute(
                    f"""
                    SELECT 
                        phl.observation_date as timestamp,
                        phl.severity_level as health_score,
                        phl.symptoms,
                        phl.disease_type,
                        phl.health_status
                    FROM PlantHealthLogs phl
                    WHERE phl.observation_date BETWEEN ? AND ?
                    {unit_filter}
                    ORDER BY phl.observation_date ASC
                    """,
                    params,
                )

                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

            # Generic fallback - use sensor data with a cap.
            return self._collect_sensor_training_data(
                start_date=start_date,
                end_date=end_date,
                unit_id=unit_id,
                limit=10000,
            )
            
        except Exception as e:
            logger.error(f"Failed to get training data: {e}", exc_info=True)
            return []

    def save_training_session(self, session_data: Dict[str, Any]) -> Optional[str]:
        """
        Save an ML training session.

        Args:
            session_data: Dict containing session fields:
                - session_id: str
                - model_type: str
                - start_time: str
                - end_time: str
                - data_points_used: int
                - validation_accuracy: float
                - training_accuracy: float
                - model_parameters: str (JSON)
                - notes: str
                - status: str

        Returns:
            session_id if successful, None otherwise
        """
        try:
            with self._backend.connection() as db:
                cursor = db.cursor()
                cursor.execute(
                    """
                    INSERT INTO MLTrainingSessions
                    (session_id, model_type, start_time, end_time, data_points_used,
                     validation_accuracy, training_accuracy, model_parameters, notes, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        session_data.get("session_id"),
                        session_data.get("model_type"),
                        session_data.get("start_time"),
                        session_data.get("end_time"),
                        session_data.get("data_points_used"),
                        session_data.get("validation_accuracy"),
                        session_data.get("training_accuracy"),
                        session_data.get("model_parameters"),
                        session_data.get("notes"),
                        session_data.get("status", "completed"),
                    ),
                )
                return session_data.get("session_id")
        except Exception as e:
            logger.error(f"Failed to save training session: {e}", exc_info=True)
            return None

    def get_training_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a training session by ID.
        
        Args:
            session_id: The session ID
            
        Returns:
            Session dict if found, None otherwise
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            cursor.execute(
                """
                SELECT session_id, model_type, start_time, end_time,
                       data_points_used, validation_accuracy, training_accuracy,
                       model_parameters, notes, status
                FROM MLTrainingSessions
                WHERE session_id = ?
            """,
                (session_id,),
            )

            result = cursor.fetchone()
            if result:
                return {
                    "session_id": result[0],
                    "model_type": result[1],
                    "start_time": result[2],
                    "end_time": result[3],
                    "data_points_used": result[4],
                    "validation_accuracy": result[5],
                    "training_accuracy": result[6],
                    "model_parameters": result[7],
                    "notes": result[8],
                    "status": result[9],
                }
        except Exception as e:
            logger.error(f"Failed to get training session: {e}", exc_info=True)
        return None

    def list_training_sessions(
        self, model_type: Optional[str] = None, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List recent training sessions.
        
        Args:
            model_type: Optional filter by model type
            limit: Maximum number of sessions to return
            
        Returns:
            List of session dicts
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()

            if model_type:
                cursor.execute(
                    """
                    SELECT session_id, model_type, start_time, end_time,
                           data_points_used, validation_accuracy, training_accuracy, status
                    FROM MLTrainingSessions
                    WHERE model_type = ?
                    ORDER BY start_time DESC
                    LIMIT ?
                """,
                    (model_type, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT session_id, model_type, start_time, end_time,
                           data_points_used, validation_accuracy, training_accuracy, status
                    FROM MLTrainingSessions
                    ORDER BY start_time DESC
                    LIMIT ?
                """,
                    (limit,),
                )

            return [
                {
                    "session_id": row[0],
                    "model_type": row[1],
                    "start_time": row[2],
                    "end_time": row[3],
                    "data_points_used": row[4],
                    "validation_accuracy": row[5],
                    "training_accuracy": row[6],
                    "status": row[7],
                }
                for row in cursor.fetchall()
            ]
        except Exception as e:
            logger.error(f"Failed to list training sessions: {e}", exc_info=True)
            return []

    # ==================== Irrigation ML Training Data ====================

    def get_irrigation_threshold_training_data(
        self,
        unit_id: Optional[int] = None,
        start_date: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get training data for irrigation threshold prediction model.
        
        Combines irrigation timing feedback with environmental context.
        
        Args:
            unit_id: Optional unit filter
            start_date: Optional start date filter (ISO format)
            limit: Maximum records to return
            
        Returns:
            List of training records with features and target
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            # Build WHERE clause
            conditions = ["f.feedback_response IN ('triggered_too_early', 'triggered_too_late')"]
            params = []
            
            if unit_id:
                conditions.append("p.unit_id = ?")
                params.append(unit_id)
            
            if start_date:
                conditions.append("f.created_at >= ?")
                params.append(start_date)
            
            where_clause = " AND ".join(conditions)
            params.append(limit)
            
            cursor.execute(
                f"""
                SELECT 
                    f.feedback_id,
                    f.feedback_response,
                    f.created_at,
                    pref.unit_id,
                    pref.soil_moisture_threshold AS current_threshold,
                    pref.plant_type,
                    pref.growth_stage,
                    p.temperature_at_detection,
                    p.humidity_at_detection,
                    p.soil_moisture_detected,
                    p.hours_since_last_irrigation
                FROM IrrigationFeedback f
                LEFT JOIN PendingIrrigationRequest p ON f.feedback_id = p.feedback_id
                LEFT JOIN IrrigationUserPreference pref ON p.unit_id = pref.unit_id
                WHERE {where_clause}
                ORDER BY f.created_at DESC
                LIMIT ?
                """,
                params,
            )
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get irrigation threshold training data: {e}", exc_info=True)
            return []

    def get_irrigation_response_training_data(
        self,
        unit_id: Optional[int] = None,
        start_date: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get training data for irrigation response prediction model.
        
        Returns records of user responses (approve/delay/cancel) with context.
        
        Args:
            unit_id: Optional unit filter
            start_date: Optional start date filter (ISO format)
            limit: Maximum records to return
            
        Returns:
            List of training records with features and response class
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            # Build WHERE clause
            conditions = ["p.user_response IN ('approve', 'delay', 'cancel')"]
            params = []
            
            if unit_id:
                conditions.append("p.unit_id = ?")
                params.append(unit_id)
            
            if start_date:
                conditions.append("p.detected_at >= ?")
                params.append(start_date)
            
            where_clause = " AND ".join(conditions)
            params.append(limit)
            
            cursor.execute(
                f"""
                SELECT 
                    p.request_id,
                    p.unit_id,
                    p.user_response,
                    p.detected_at,
                    p.responded_at,
                    p.soil_moisture_detected,
                    p.soil_moisture_threshold,
                    p.temperature_at_detection,
                    p.humidity_at_detection,
                    p.vpd_at_detection,
                    p.hours_since_last_irrigation,
                    p.delayed_until,
                    pref.time_of_day_preference,
                    pref.weekday_preference
                FROM PendingIrrigationRequest p
                LEFT JOIN IrrigationUserPreference pref ON p.unit_id = pref.unit_id
                WHERE {where_clause}
                ORDER BY p.detected_at DESC
                LIMIT ?
                """,
                params,
            )
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get irrigation response training data: {e}", exc_info=True)
            return []

    def get_irrigation_timing_training_data(
        self,
        unit_id: Optional[int] = None,
        start_date: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get training data for irrigation timing prediction model.

        Uses delayed irrigation responses with user-selected delayed times.
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()

            conditions = [
                "p.user_response = 'delay'",
                "p.delayed_until IS NOT NULL",
            ]
            params = []

            if unit_id:
                conditions.append("p.unit_id = ?")
                params.append(unit_id)

            if start_date:
                conditions.append("p.detected_at >= ?")
                params.append(start_date)

            where_clause = " AND ".join(conditions)
            params.append(limit)

            cursor.execute(
                f"""
                SELECT
                    p.request_id,
                    p.unit_id,
                    p.detected_at,
                    p.delayed_until,
                    p.soil_moisture_detected,
                    p.soil_moisture_threshold,
                    p.temperature_at_detection,
                    p.humidity_at_detection,
                    p.hours_since_last_irrigation,
                    g.timezone
                FROM PendingIrrigationRequest p
                LEFT JOIN GrowthUnits g ON p.unit_id = g.unit_id
                WHERE {where_clause}
                ORDER BY p.detected_at DESC
                LIMIT ?
                """,
                params,
            )

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get irrigation timing training data: {e}", exc_info=True)
            return []

    def get_irrigation_duration_training_data(
        self,
        unit_id: Optional[int] = None,
        start_date: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get training data for irrigation duration prediction model.
        
        Returns executed irrigations with before/after moisture readings.
        
        Args:
            unit_id: Optional unit filter
            start_date: Optional start date filter (ISO format)
            limit: Maximum records to return
            
        Returns:
            List of training records with features and duration
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            # Build WHERE clause - only use executed irrigations with after readings
            conditions = [
                "p.status = 'executed'",
                "p.soil_moisture_after IS NOT NULL",
                "p.execution_duration_seconds IS NOT NULL",
            ]
            params = []
            
            if unit_id:
                conditions.append("p.unit_id = ?")
                params.append(unit_id)
            
            if start_date:
                conditions.append("p.detected_at >= ?")
                params.append(start_date)
            
            where_clause = " AND ".join(conditions)
            params.append(limit)
            
            cursor.execute(
                f"""
                SELECT 
                    p.request_id,
                    p.unit_id,
                    p.soil_moisture_detected,
                    p.soil_moisture_threshold,
                    p.soil_moisture_after,
                    p.execution_duration_seconds,
                    p.temperature_at_detection,
                    p.humidity_at_detection,
                    p.detected_at,
                    p.executed_at
                FROM PendingIrrigationRequest p
                WHERE {where_clause}
                ORDER BY p.detected_at DESC
                LIMIT ?
                """,
                params,
            )
            
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
            
        except Exception as e:
            logger.error(f"Failed to get irrigation duration training data: {e}", exc_info=True)
            return []

    def get_harvest_training_data(
        self,
        plant_type: Optional[str] = None,
        min_quality: int = 1,
        min_yield: Optional[float] = None,
        days_limit: int = 365,
    ) -> pd.DataFrame:
        """
        Get harvest outcome data for plant-specific model fine-tuning.
        
        This data is used to learn optimal conditions for specific plant types
        based on successful harvests.
        
        Args:
            plant_type: Optional filter by plant type
            min_quality: Minimum quality rating to include (1-5)
            min_yield: Optional minimum yield in grams
            days_limit: How far back to look (default 1 year)
            
        Returns:
            DataFrame with harvest outcomes and growing conditions
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            # Build WHERE clause
            conditions = [
                f"h.harvested_date >= date('now', '-{days_limit} days')",
                "h.quality_rating >= ?",
            ]
            params = [min_quality]
            
            if plant_type:
                conditions.append("p.plant_type = ?")
                params.append(plant_type)
            
            if min_yield is not None:
                conditions.append("h.harvest_weight_grams >= ?")
                params.append(min_yield)
            
            where_clause = " AND ".join(conditions)
            
            cursor.execute(
                f"""
                SELECT 
                    h.harvest_id,
                    h.plant_id,
                    h.unit_id,
                    p.plant_type,
                    p.variety,
                    h.planted_date,
                    h.harvested_date,
                    h.total_days,
                    h.seedling_days,
                    h.vegetative_days,
                    h.flowering_days,
                    h.avg_temperature,
                    h.avg_humidity,
                    h.avg_co2,
                    h.avg_health_score,
                    h.disease_days,
                    h.pest_days,
                    h.total_light_hours,
                    h.avg_ppfd,
                    h.harvest_weight_grams,
                    h.quality_rating,
                    h.grams_per_kwh,
                    h.total_energy_kwh,
                    h.notes
                FROM PlantHarvestSummary h
                JOIN Plants p ON h.plant_id = p.plant_id
                WHERE {where_clause}
                ORDER BY h.quality_rating DESC, h.harvest_weight_grams DESC
                """,
                params,
            )
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            if not rows:
                return pd.DataFrame()
            
            return pd.DataFrame(rows, columns=columns)
            
        except Exception as e:
            logger.error(f"Failed to get harvest training data: {e}", exc_info=True)
            return pd.DataFrame()

    def get_optimal_conditions_by_plant_type(
        self,
        plant_type: str,
        min_quality: int = 4,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """
        Get optimal growing conditions learned from successful harvests.
        
        Analyzes top-quality harvests for a plant type to extract
        optimal temperature, humidity, and other conditions.
        
        Args:
            plant_type: Plant type to analyze
            min_quality: Minimum quality rating for "successful" grows
            limit: Number of top harvests to analyze
            
        Returns:
            Dict with optimal condition ranges
        """
        try:
            # Get harvest data for high-quality grows
            df = self.get_harvest_training_data(
                plant_type=plant_type,
                min_quality=min_quality,
                days_limit=730  # 2 years of data
            )
            
            if df.empty or len(df) < 3:
                return {"error": "Insufficient harvest data", "sample_count": len(df)}
            
            # Limit to top performers
            df = df.head(limit)
            
            # Calculate optimal ranges (mean ± std for stability)
            optimal = {
                "plant_type": plant_type,
                "sample_count": len(df),
                "conditions": {
                    "temperature": {
                        "optimal": round(df["avg_temperature"].mean(), 1),
                        "range_min": round(df["avg_temperature"].mean() - df["avg_temperature"].std(), 1),
                        "range_max": round(df["avg_temperature"].mean() + df["avg_temperature"].std(), 1),
                    },
                    "humidity": {
                        "optimal": round(df["avg_humidity"].mean(), 1),
                        "range_min": round(df["avg_humidity"].mean() - df["avg_humidity"].std(), 1),
                        "range_max": round(df["avg_humidity"].mean() + df["avg_humidity"].std(), 1),
                    },
                },
                "growth_duration": {
                    "avg_total_days": int(df["total_days"].mean()),
                    "avg_vegetative_days": int(df["vegetative_days"].mean()) if df["vegetative_days"].notna().any() else None,
                    "avg_flowering_days": int(df["flowering_days"].mean()) if df["flowering_days"].notna().any() else None,
                },
                "outcomes": {
                    "avg_yield_grams": round(df["harvest_weight_grams"].mean(), 1) if df["harvest_weight_grams"].notna().any() else None,
                    "avg_quality": round(df["quality_rating"].mean(), 2),
                    "avg_health_score": round(df["avg_health_score"].mean(), 2) if df["avg_health_score"].notna().any() else None,
                },
            }
            
            # Add CO2 if available
            if df["avg_co2"].notna().any():
                optimal["conditions"]["co2"] = {
                    "optimal": round(df["avg_co2"].mean(), 0),
                    "range_min": round(df["avg_co2"].mean() - df["avg_co2"].std(), 0),
                    "range_max": round(df["avg_co2"].mean() + df["avg_co2"].std(), 0),
                }
            
            # Add light info if available
            if df["avg_ppfd"].notna().any():
                optimal["conditions"]["ppfd"] = {
                    "optimal": round(df["avg_ppfd"].mean(), 0),
                }
            
            return optimal
            
        except Exception as e:
            logger.error(f"Failed to get optimal conditions: {e}", exc_info=True)
            return {"error": str(e)}

    # ==================== Disease ML Training Data ====================

    def get_disease_occurrence_training_data(
        self,
        unit_id: Optional[int] = None,
        disease_type: Optional[str] = None,
        days_limit: int = 365,
        confirmed_only: bool = True,
    ) -> pd.DataFrame:
        """
        Get disease occurrence data for ML model training.
        
        Args:
            unit_id: Optional filter by unit
            disease_type: Optional filter by disease type
            days_limit: How far back to look
            confirmed_only: Only include user-confirmed occurrences
            
        Returns:
            DataFrame with disease occurrences and environmental features
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            conditions = [f"d.detected_at >= date('now', '-{days_limit} days')"]
            params = []
            
            if unit_id:
                conditions.append("d.unit_id = ?")
                params.append(unit_id)
            
            if disease_type:
                conditions.append("d.disease_type = ?")
                params.append(disease_type)
            
            if confirmed_only:
                conditions.append("d.confirmed_by_user = 1")
            
            where_clause = " AND ".join(conditions)
            
            cursor.execute(
                f"""
                SELECT 
                    d.occurrence_id,
                    d.unit_id,
                    d.disease_type,
                    d.severity,
                    d.detected_at,
                    d.temperature_at_detection,
                    d.humidity_at_detection,
                    d.soil_moisture_at_detection,
                    d.vpd_at_detection,
                    d.avg_temperature_72h,
                    d.avg_humidity_72h,
                    d.avg_soil_moisture_72h,
                    d.humidity_variance_72h,
                    d.plant_type,
                    d.growth_stage,
                    d.days_in_stage,
                    CASE WHEN d.resolved_at IS NOT NULL THEN 1 ELSE 0 END as was_resolved,
                    JULIANDAY(d.resolved_at) - JULIANDAY(d.detected_at) as days_to_resolve
                FROM DiseaseOccurrence d
                WHERE {where_clause}
                ORDER BY d.detected_at DESC
                """,
                params,
            )
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            if not rows:
                return pd.DataFrame()
            
            return pd.DataFrame(rows, columns=columns)
            
        except Exception as e:
            logger.error(f"Failed to get disease occurrence data: {e}", exc_info=True)
            return pd.DataFrame()

    def get_disease_prediction_feedback(
        self,
        unit_id: Optional[int] = None,
        disease_type: Optional[str] = None,
        days_limit: int = 180,
    ) -> pd.DataFrame:
        """
        Get prediction feedback data for model calibration.
        
        Args:
            unit_id: Optional filter by unit
            disease_type: Optional filter by predicted disease type
            days_limit: How far back to look
            
        Returns:
            DataFrame with predictions and outcomes
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            conditions = [
                f"f.prediction_timestamp >= date('now', '-{days_limit} days')",
                "f.actual_disease_occurred IS NOT NULL",  # Only feedback that was collected
            ]
            params = []
            
            if unit_id:
                conditions.append("f.unit_id = ?")
                params.append(unit_id)
            
            if disease_type:
                conditions.append("f.predicted_disease_type = ?")
                params.append(disease_type)
            
            where_clause = " AND ".join(conditions)
            
            cursor.execute(
                f"""
                SELECT 
                    f.feedback_id,
                    f.prediction_id,
                    f.unit_id,
                    f.predicted_disease_type,
                    f.predicted_risk_level,
                    f.predicted_risk_score,
                    f.prediction_timestamp,
                    f.contributing_factors,
                    f.actual_disease_occurred,
                    f.actual_disease_type,
                    f.actual_severity,
                    f.days_to_occurrence,
                    f.was_true_positive,
                    f.was_false_positive,
                    f.was_true_negative,
                    f.was_false_negative
                FROM DiseasePredictionFeedback f
                WHERE {where_clause}
                ORDER BY f.prediction_timestamp DESC
                """,
                params,
            )
            
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            
            if not rows:
                return pd.DataFrame()
            
            return pd.DataFrame(rows, columns=columns)
            
        except Exception as e:
            logger.error(f"Failed to get disease prediction feedback: {e}", exc_info=True)
            return pd.DataFrame()

    def save_disease_occurrence(self, occurrence_data: Dict[str, Any]) -> Optional[int]:
        """
        Save a disease occurrence record.
        
        Args:
            occurrence_data: Dict with occurrence fields
            
        Returns:
            occurrence_id if saved successfully, None otherwise
        """
        try:
            detected_at = occurrence_data.get("detected_at") or datetime.utcnow().isoformat()
            with self._backend.connection() as db:
                cursor = db.cursor()
                cursor.execute(
                    """
                    INSERT INTO DiseaseOccurrence (
                        unit_id, plant_id, disease_type, severity, detected_at,
                        temperature_at_detection, humidity_at_detection, 
                        soil_moisture_at_detection, vpd_at_detection,
                        avg_temperature_72h, avg_humidity_72h, avg_soil_moisture_72h,
                        humidity_variance_72h, confirmed_by_user, symptoms,
                        affected_parts, plant_type, growth_stage, days_in_stage, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        occurrence_data.get("unit_id"),
                        occurrence_data.get("plant_id"),
                        occurrence_data.get("disease_type"),
                        occurrence_data.get("severity", "mild"),
                        detected_at,
                        occurrence_data.get("temperature_at_detection"),
                        occurrence_data.get("humidity_at_detection"),
                        occurrence_data.get("soil_moisture_at_detection"),
                        occurrence_data.get("vpd_at_detection"),
                        occurrence_data.get("avg_temperature_72h"),
                        occurrence_data.get("avg_humidity_72h"),
                        occurrence_data.get("avg_soil_moisture_72h"),
                        occurrence_data.get("humidity_variance_72h"),
                        occurrence_data.get("confirmed_by_user", False),
                        occurrence_data.get("symptoms"),
                        occurrence_data.get("affected_parts"),
                        occurrence_data.get("plant_type"),
                        occurrence_data.get("growth_stage"),
                        occurrence_data.get("days_in_stage"),
                        occurrence_data.get("notes"),
                    ),
                )
                db.commit()
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"Failed to save disease occurrence: {e}", exc_info=True)
            return None

    def save_disease_prediction_feedback(
        self, feedback_data: Dict[str, Any]
    ) -> Optional[int]:
        """
        Save disease prediction feedback for model training.
        
        Args:
            feedback_data: Dict with feedback fields
            
        Returns:
            feedback_id if saved successfully, None otherwise
        """
        try:
            prediction_timestamp = feedback_data.get("prediction_timestamp") or datetime.utcnow().isoformat()
            feedback_timestamp = feedback_data.get("feedback_timestamp") or datetime.utcnow().isoformat()
            with self._backend.connection() as db:
                cursor = db.cursor()
                
                # Determine prediction quality flags
                predicted_high = feedback_data.get("predicted_risk_level") in ["high", "critical"]
                disease_occurred = feedback_data.get("actual_disease_occurred", False)
                
                was_true_positive = predicted_high and disease_occurred
                was_false_positive = predicted_high and not disease_occurred
                was_true_negative = not predicted_high and not disease_occurred
                was_false_negative = not predicted_high and disease_occurred
                
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO DiseasePredictionFeedback (
                        prediction_id, unit_id, predicted_disease_type,
                        predicted_risk_level, predicted_risk_score,
                        prediction_timestamp, contributing_factors,
                        actual_disease_occurred, actual_disease_type,
                        actual_severity, days_to_occurrence, feedback_timestamp,
                        feedback_source, was_true_positive, was_false_positive,
                        was_true_negative, was_false_negative
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        feedback_data.get("prediction_id"),
                        feedback_data.get("unit_id"),
                        feedback_data.get("predicted_disease_type"),
                        feedback_data.get("predicted_risk_level"),
                        feedback_data.get("predicted_risk_score"),
                        prediction_timestamp,
                        feedback_data.get("contributing_factors"),
                        disease_occurred,
                        feedback_data.get("actual_disease_type"),
                        feedback_data.get("actual_severity"),
                        feedback_data.get("days_to_occurrence"),
                        feedback_timestamp,
                        feedback_data.get("feedback_source", "user"),
                        was_true_positive,
                        was_false_positive,
                        was_true_negative,
                        was_false_negative,
                    ),
                )
                db.commit()
                return cursor.lastrowid
                
        except Exception as e:
            logger.error(f"Failed to save prediction feedback: {e}", exc_info=True)
            return None

    def get_disease_prediction_accuracy(
        self, disease_type: Optional[str] = None, days_limit: int = 90
    ) -> Dict[str, Any]:
        """
        Calculate prediction accuracy metrics from feedback data.
        
        Args:
            disease_type: Optional filter by disease type
            days_limit: How far back to analyze
            
        Returns:
            Dict with accuracy metrics (precision, recall, F1, etc.)
        """
        try:
            df = self.get_disease_prediction_feedback(
                disease_type=disease_type,
                days_limit=days_limit,
            )
            
            if df.empty:
                return {"error": "No feedback data available"}
            
            total = len(df)
            tp = df["was_true_positive"].sum()
            fp = df["was_false_positive"].sum()
            tn = df["was_true_negative"].sum()
            fn = df["was_false_negative"].sum()
            
            # Calculate metrics
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            accuracy = (tp + tn) / total if total > 0 else 0
            
            return {
                "total_predictions": total,
                "true_positives": int(tp),
                "false_positives": int(fp),
                "true_negatives": int(tn),
                "false_negatives": int(fn),
                "precision": round(precision, 3),
                "recall": round(recall, 3),
                "f1_score": round(f1, 3),
                "accuracy": round(accuracy, 3),
                "disease_type": disease_type or "all",
                "days_analyzed": days_limit,
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate prediction accuracy: {e}", exc_info=True)
            return {"error": str(e)}

    def get_disease_history(
        self,
        unit_id: Optional[int] = None,
        plant_id: Optional[int] = None,
        disease_type: Optional[str] = None,
        include_resolved: bool = True,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get disease occurrence history with optional filters.

        Args:
            unit_id: Filter by growth unit
            plant_id: Filter by specific plant
            disease_type: Filter by disease type
            include_resolved: Include resolved occurrences (default True)
            limit: Max records to return
            offset: Pagination offset

        Returns:
            List of disease occurrence records
        """
        try:
            with self._backend.connection() as db:
                query = """
                    SELECT
                        occurrence_id, unit_id, plant_id, disease_type, severity,
                        detected_at, resolved_at, treatment_applied, treatment_date,
                        temperature_at_detection, humidity_at_detection,
                        soil_moisture_at_detection, vpd_at_detection,
                        confirmed_by_user, symptoms, affected_parts,
                        plant_type, growth_stage, days_in_stage, notes, image_path
                    FROM DiseaseOccurrence
                    WHERE 1=1
                """
                params: List[Any] = []

                if unit_id is not None:
                    query += " AND unit_id = ?"
                    params.append(unit_id)
                if plant_id is not None:
                    query += " AND plant_id = ?"
                    params.append(plant_id)
                if disease_type:
                    query += " AND disease_type = ?"
                    params.append(disease_type)
                if not include_resolved:
                    query += " AND resolved_at IS NULL"

                query += " ORDER BY detected_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor = db.cursor()
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()

                return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get disease history: {e}", exc_info=True)
            return []

    def get_disease_occurrence_by_id(self, occurrence_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a single disease occurrence by ID.

        Args:
            occurrence_id: The occurrence ID

        Returns:
            Disease occurrence record or None
        """
        try:
            with self._backend.connection() as db:
                cursor = db.cursor()
                cursor.execute(
                    """
                    SELECT
                        occurrence_id, unit_id, plant_id, disease_type, severity,
                        detected_at, resolved_at, treatment_applied, treatment_date,
                        temperature_at_detection, humidity_at_detection,
                        soil_moisture_at_detection, vpd_at_detection,
                        avg_temperature_72h, avg_humidity_72h, avg_soil_moisture_72h,
                        humidity_variance_72h, confirmed_by_user, symptoms, affected_parts,
                        plant_type, growth_stage, days_in_stage, notes, image_path
                    FROM DiseaseOccurrence
                    WHERE occurrence_id = ?
                    """,
                    (occurrence_id,),
                )
                row = cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            logger.error(f"Failed to get disease occurrence {occurrence_id}: {e}", exc_info=True)
            return None

    def resolve_disease_occurrence(
        self,
        occurrence_id: int,
        treatment_applied: str,
        notes: Optional[str] = None,
    ) -> bool:
        """
        Mark a disease occurrence as resolved with treatment details.

        Args:
            occurrence_id: The occurrence ID to resolve
            treatment_applied: Description of treatment applied
            notes: Additional notes about resolution

        Returns:
            True if updated successfully
        """
        try:
            with self._backend.connection() as db:
                cursor = db.cursor()
                cursor.execute(
                    """
                    UPDATE DiseaseOccurrence
                    SET resolved_at = datetime('now'),
                        treatment_applied = ?,
                        treatment_date = date('now'),
                        notes = COALESCE(notes || ' | Resolution: ' || ?, ?)
                    WHERE occurrence_id = ? AND resolved_at IS NULL
                    """,
                    (treatment_applied, notes or '', notes or '', occurrence_id),
                )
                db.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to resolve disease occurrence {occurrence_id}: {e}", exc_info=True)
            return False

    def get_disease_summary_stats(
        self,
        unit_id: Optional[int] = None,
        days_limit: int = 90,
    ) -> Dict[str, Any]:
        """
        Get summary statistics for disease occurrences.

        Args:
            unit_id: Optional filter by unit
            days_limit: How far back to analyze

        Returns:
            Dict with summary statistics
        """
        try:
            with self._backend.connection() as db:
                cursor = db.cursor()

                base_filter = "WHERE detected_at >= datetime('now', ?)"
                params: List[Any] = [f'-{days_limit} days']

                if unit_id is not None:
                    base_filter += " AND unit_id = ?"
                    params.append(unit_id)

                # Total counts
                cursor.execute(
                    f"""
                    SELECT
                        COUNT(*) as total_occurrences,
                        COUNT(CASE WHEN resolved_at IS NOT NULL THEN 1 END) as resolved_count,
                        COUNT(CASE WHEN resolved_at IS NULL THEN 1 END) as active_count,
                        COUNT(DISTINCT plant_id) as affected_plants,
                        COUNT(DISTINCT unit_id) as affected_units
                    FROM DiseaseOccurrence
                    {base_filter}
                    """,
                    tuple(params),
                )
                totals = dict(cursor.fetchone())

                # By disease type
                cursor.execute(
                    f"""
                    SELECT disease_type, COUNT(*) as count
                    FROM DiseaseOccurrence
                    {base_filter}
                    GROUP BY disease_type
                    ORDER BY count DESC
                    """,
                    tuple(params),
                )
                by_type = {row["disease_type"]: row["count"] for row in cursor.fetchall()}

                # By severity
                cursor.execute(
                    f"""
                    SELECT severity, COUNT(*) as count
                    FROM DiseaseOccurrence
                    {base_filter}
                    GROUP BY severity
                    """,
                    tuple(params),
                )
                by_severity = {row["severity"]: row["count"] for row in cursor.fetchall()}

                # Average resolution time
                cursor.execute(
                    f"""
                    SELECT AVG(julianday(resolved_at) - julianday(detected_at)) as avg_resolution_days
                    FROM DiseaseOccurrence
                    {base_filter} AND resolved_at IS NOT NULL
                    """,
                    tuple(params),
                )
                avg_row = cursor.fetchone()
                avg_resolution = round(avg_row["avg_resolution_days"], 1) if avg_row and avg_row["avg_resolution_days"] else None

                return {
                    "period_days": days_limit,
                    "unit_id": unit_id,
                    **totals,
                    "by_disease_type": by_type,
                    "by_severity": by_severity,
                    "avg_resolution_days": avg_resolution,
                }

        except Exception as e:
            logger.error(f"Failed to get disease summary stats: {e}", exc_info=True)
            return {"error": str(e)}

    # ==================== A/B Testing Persistence ====================

    def save_ab_test(self, test_data: Dict[str, Any]) -> bool:
        """
        Save or update an A/B test.
        
        Args:
            test_data: Dict containing test configuration
            
        Returns:
            True if saved successfully
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            cursor.execute(
                """
                INSERT OR REPLACE INTO ABTests (
                    test_id, model_name, version_a, version_b,
                    split_ratio, start_date, end_date, status, min_samples, winner
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    test_data.get("test_id"),
                    test_data.get("model_name"),
                    test_data.get("version_a"),
                    test_data.get("version_b"),
                    test_data.get("split_ratio", 0.5),
                    test_data.get("start_date"),
                    test_data.get("end_date"),
                    test_data.get("status", "running"),
                    test_data.get("min_samples", 100),
                    test_data.get("winner"),
                ),
            )
            db.commit()
            return True
            
        except Exception as e:
            logger.error(f"Failed to save A/B test: {e}", exc_info=True)
            return False

    def get_ab_test(self, test_id: str) -> Optional[Dict[str, Any]]:
        """Get a single A/B test by ID."""
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM ABTests WHERE test_id = ?", (test_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
        except Exception as e:
            logger.error(f"Failed to get A/B test: {e}", exc_info=True)
            return None

    def get_active_ab_tests(self) -> List[Dict[str, Any]]:
        """Get all running A/B tests."""
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            cursor.execute("SELECT * FROM ABTests WHERE status = 'running'")
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get active A/B tests: {e}", exc_info=True)
            return []

    def save_ab_test_result(
        self, test_id: str, version: str, predicted: Any, actual: Any = None, error: float = None
    ) -> Optional[int]:
        """Save an A/B test result."""
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            cursor.execute(
                """
                INSERT INTO ABTestResults (test_id, version, predicted, actual, error)
                VALUES (?, ?, ?, ?, ?)
                """,
                (test_id, version, str(predicted), str(actual) if actual else None, error),
            )
            db.commit()
            return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"Failed to save A/B test result: {e}", exc_info=True)
            return None

    def get_ab_test_results(self, test_id: str) -> List[Dict[str, Any]]:
        """Get all results for an A/B test."""
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            cursor.execute(
                "SELECT * FROM ABTestResults WHERE test_id = ? ORDER BY timestamp",
                (test_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get A/B test results: {e}", exc_info=True)
            return []

    # ==================== Drift Metrics Persistence ====================

    def save_drift_metric(
        self,
        model_name: str,
        prediction: Any,
        actual: Any = None,
        confidence: float = None,
        error: float = None,
    ) -> Optional[int]:
        """
        Save a drift tracking metric.
        
        Args:
            model_name: Name of the model
            prediction: Model prediction value
            actual: Actual value (if known)
            confidence: Prediction confidence
            error: Calculated error
            
        Returns:
            Metric ID if saved successfully
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            cursor.execute(
                """
                INSERT INTO DriftMetrics (model_name, prediction, actual, confidence, error)
                VALUES (?, ?, ?, ?, ?)
                """,
                (model_name, str(prediction), str(actual) if actual else None, confidence, error),
            )
            db.commit()
            return cursor.lastrowid
            
        except Exception as e:
            logger.error(f"Failed to save drift metric: {e}", exc_info=True)
            return None

    def get_drift_metrics(
        self, model_name: str, limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get recent drift metrics for a model.
        
        Args:
            model_name: Model to get metrics for
            limit: Maximum records to return
            
        Returns:
            List of drift metric records
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            cursor.execute(
                """
                SELECT * FROM DriftMetrics 
                WHERE model_name = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (model_name, limit),
            )
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Failed to get drift metrics: {e}", exc_info=True)
            return []

    def cleanup_old_drift_metrics(self, model_name: str, keep_count: int = 1000) -> int:
        """
        Clean up old drift metrics, keeping only the most recent.
        
        Args:
            model_name: Model to clean up
            keep_count: Number of recent records to keep
            
        Returns:
            Number of records deleted
        """
        try:
            db = self._backend.get_db()
            cursor = db.cursor()
            
            cursor.execute(
                """
                DELETE FROM DriftMetrics 
                WHERE model_name = ? AND metric_id NOT IN (
                    SELECT metric_id FROM DriftMetrics 
                    WHERE model_name = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                )
                """,
                (model_name, model_name, keep_count),
            )
            deleted = cursor.rowcount
            db.commit()
            return deleted
            
        except Exception as e:
            logger.error(f"Failed to cleanup drift metrics: {e}", exc_info=True)
            return 0
