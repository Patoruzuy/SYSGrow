"""Repository for Irrigation ML operations.

This repository provides high-level methods for ML-related irrigation
data access, following the repository pattern used elsewhere in the project.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.utils.time import iso_now

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)


@dataclass
class MLReadinessStatus:
    """Status of ML readiness for irrigation models."""
    
    model_name: str
    required_samples: int
    current_samples: int
    is_ready: bool = field(init=False)
    percentage_ready: float = field(init=False)
    is_enabled: bool = False
    notification_sent_at: Optional[str] = None
    
    def __post_init__(self) -> None:
        self.is_ready = self.current_samples >= self.required_samples
        self.percentage_ready = min(
            100.0,
            (self.current_samples / self.required_samples * 100) if self.required_samples > 0 else 0
        )


@dataclass
class IrrigationMLContext:
    """Environmental context at irrigation detection time."""
    
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    vpd: Optional[float] = None
    lux: Optional[float] = None
    hours_since_last_irrigation: Optional[float] = None
    plant_type: Optional[str] = None
    growth_stage: Optional[str] = None
    soil_moisture: Optional[float] = None
    soil_moisture_threshold: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            "temperature_at_detection": self.temperature,
            "humidity_at_detection": self.humidity,
            "vpd_at_detection": self.vpd,
            "lux_at_detection": self.lux,
            "hours_since_last_irrigation": self.hours_since_last_irrigation,
            "plant_type": self.plant_type,
            "growth_stage": self.growth_stage,
        }


class IrrigationMLRepository:
    """Repository for irrigation ML data access."""
    
    # Minimum samples required for each model
    MODEL_THRESHOLDS = {
        "response_predictor": 20,
        "threshold_optimizer": 30,
        "duration_optimizer": 15,
        "timing_predictor": 25,
    }
    
    def __init__(self, db_handler: "SQLiteDatabaseHandler") -> None:
        """Initialize with database handler."""
        self._db = db_handler
    
    def get_ml_readiness_status(
        self,
        unit_id: Optional[int] = None,
    ) -> Dict[str, MLReadinessStatus]:
        """
        Get ML readiness status for all irrigation models.
        
        Returns a dict with status for each model type.
        """
        # Get sample counts
        counts = self._db.count_ml_training_samples(unit_id)
        
        # Get current ML settings
        config = None
        if unit_id:
            config = self._db.get_workflow_config(unit_id)
        
        results = {}
        for model_name, threshold in self.MODEL_THRESHOLDS.items():
            current = counts.get(model_name, 0)
            enabled_key = f"ml_{model_name}_enabled"
            notified_key = f"ml_{model_name}_notified_at"
            
            results[model_name] = MLReadinessStatus(
                model_name=model_name,
                required_samples=threshold,
                current_samples=current,
                is_enabled=bool(config.get(enabled_key)) if config else False,
                notification_sent_at=config.get(notified_key) if config else None,
            )
        
        return results
    
    def get_units_ready_for_ml_activation(self) -> List[Dict[str, Any]]:
        """
        Find units that have enough data for ML activation but haven't been notified.
        
        Returns list of units with their ready models.
        """
        try:
            db = self._db.get_db()
            
            # Get all units with workflow configs
            cur = db.execute("""
                SELECT DISTINCT unit_id FROM IrrigationWorkflowConfig
                WHERE workflow_enabled = 1
            """)
            unit_ids = [row[0] for row in cur.fetchall()]
            
            ready_units = []
            for unit_id in unit_ids:
                status = self.get_ml_readiness_status(unit_id)
                ready_models = []
                
                for model_name, model_status in status.items():
                    if (
                        model_status.is_ready 
                        and not model_status.is_enabled
                        and not model_status.notification_sent_at
                    ):
                        ready_models.append(model_name)
                
                if ready_models:
                    ready_units.append({
                        "unit_id": unit_id,
                        "ready_models": ready_models,
                        "status": status,
                    })
            
            return ready_units
            
        except Exception as exc:
            logger.error(f"Failed to get units ready for ML activation: {exc}")
            return []

    def get_units_with_workflow_enabled(self) -> List[int]:
        """
        Get all unit IDs with workflow enabled.

        Returns:
            List of unit IDs
        """
        try:
            db = self._db.get_db()
            cur = db.execute(
                """
                SELECT DISTINCT unit_id FROM IrrigationWorkflowConfig
                WHERE workflow_enabled = 1
                """
            )
            return [row[0] for row in cur.fetchall()]
        except Exception as exc:
            logger.error(f"Failed to get units with workflow enabled: {exc}")
            return []
    
    def mark_ml_notification_sent(
        self,
        unit_id: int,
        model_name: str,
    ) -> bool:
        """Mark that a notification was sent for ML readiness."""
        try:
            db = self._db.get_db()
            col_name = f"ml_{model_name}_notified_at"
            
            db.execute(
                f"""
                UPDATE IrrigationWorkflowConfig
                SET {col_name} = ?, updated_at = ?
                WHERE unit_id = ?
                """,
                (iso_now(), iso_now(), unit_id),
            )
            db.commit()
            return True
        except Exception as exc:
            logger.error(f"Failed to mark ML notification sent: {exc}")
            return False
    
    def enable_ml_model(
        self,
        unit_id: int,
        model_name: str,
        enabled: bool = True,
    ) -> bool:
        """Enable or disable an ML model for a unit."""
        try:
            db = self._db.get_db()
            col_name = f"ml_{model_name}_enabled"
            
            db.execute(
                f"""
                UPDATE IrrigationWorkflowConfig
                SET {col_name} = ?, updated_at = ?
                WHERE unit_id = ?
                """,
                (1 if enabled else 0, iso_now(), unit_id),
            )
            db.commit()
            logger.info(f"ML model {model_name} {'enabled' if enabled else 'disabled'} for unit {unit_id}")
            return True
        except Exception as exc:
            logger.error(f"Failed to enable ML model: {exc}")
            return False
    
    def get_training_data_for_model(
        self,
        model_name: str,
        unit_id: Optional[int] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get training data for a specific ML model.
        
        Each model type requires different data:
        - response_predictor: Environmental context + user response
        - threshold_optimizer: Context + timing feedback
        - volume_feedback: Context + volume feedback
        - duration_optimizer: Context + execution result
        - timing_predictor: Context + delay patterns
        """
        try:
            db = self._db.get_db()
            base_where = "WHERE temperature_at_detection IS NOT NULL"
            unit_clause = f" AND p.unit_id = {unit_id}" if unit_id else ""
            
            if model_name == "response_predictor":
                query = f"""
                    SELECT 
                        p.*,
                        pref.time_of_day_preference,
                        pref.weekday_preference
                    FROM PendingIrrigationRequest p
                    LEFT JOIN IrrigationUserPreference pref 
                        ON p.unit_id = pref.unit_id
                    {base_where} {unit_clause}
                    AND p.user_response IN ('approve', 'delay', 'cancel')
                    ORDER BY p.detected_at DESC
                    LIMIT {limit}
                """
            elif model_name == "threshold_optimizer":
                query = f"""
                    SELECT 
                        p.*,
                        f.feedback_response
                    FROM PendingIrrigationRequest p
                    INNER JOIN IrrigationFeedback f ON p.feedback_id = f.feedback_id
                    {base_where} {unit_clause}
                    AND f.feedback_response IN ('triggered_too_early', 'triggered_too_late')
                    ORDER BY p.detected_at DESC
                    LIMIT {limit}
                """
            elif model_name == "volume_feedback":
                query = f"""
                    SELECT
                        p.*,
                        f.feedback_response
                    FROM PendingIrrigationRequest p
                    INNER JOIN IrrigationFeedback f ON p.feedback_id = f.feedback_id
                    {base_where} {unit_clause}
                    AND f.feedback_response IN ('too_little', 'just_right', 'too_much')
                    ORDER BY p.detected_at DESC
                    LIMIT {limit}
                """
            elif model_name == "duration_optimizer":
                query = f"""
                    SELECT
                        p.request_id,
                        p.unit_id,
                        p.temperature_at_detection,
                        p.humidity_at_detection,
                        p.vpd_at_detection,
                        p.lux_at_detection,
                        COALESCE(l.trigger_moisture, p.soil_moisture_detected) AS soil_moisture_detected,
                        l.post_moisture AS soil_moisture_after,
                        COALESCE(l.actual_duration_s, l.planned_duration_s, p.execution_duration_seconds)
                            AS execution_duration_seconds,
                        l.executed_at_utc
                    FROM PendingIrrigationRequest p
                    INNER JOIN IrrigationExecutionLog l
                        ON l.request_id = p.request_id
                    {base_where} {unit_clause}
                    AND p.status = 'executed'
                    AND l.post_moisture IS NOT NULL
                    ORDER BY p.detected_at DESC
                    LIMIT {limit}
                """
            elif model_name == "timing_predictor":
                query = f"""
                    SELECT p.*
                    FROM PendingIrrigationRequest p
                    {base_where} {unit_clause}
                    AND p.user_response = 'delay'
                    AND p.delayed_until IS NOT NULL
                    ORDER BY p.detected_at DESC
                    LIMIT {limit}
                """
            else:
                logger.warning(f"Unknown model name: {model_name}")
                return []
            
            cur = db.execute(query)
            return [dict(row) for row in cur.fetchall()]
            
        except Exception as exc:
            logger.error(f"Failed to get training data for {model_name}: {exc}")
            return []

    def get_plant_irrigation_model(self, plant_id: int) -> Optional[Dict[str, Any]]:
        """Fetch dry-down model for a plant (if available)."""
        try:
            db = self._db.get_db()
            cur = db.execute(
                "SELECT * FROM PlantIrrigationModel WHERE plant_id = ?",
                (plant_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
        except Exception as exc:
            logger.error(f"Failed to fetch plant irrigation model for {plant_id}: {exc}")
            return None
    
    def calculate_hours_since_last_irrigation(
        self,
        unit_id: int,
    ) -> Optional[float]:
        """Calculate hours since the last successful irrigation."""
        last_irrigation = self._db.get_last_completed_irrigation(unit_id)
        
        if not last_irrigation or not last_irrigation.get("executed_at"):
            return None
        
        try:
            last_time = datetime.fromisoformat(last_irrigation["executed_at"])
            now = datetime.now(last_time.tzinfo) if last_time.tzinfo else datetime.now()
            delta = now - last_time
            return delta.total_seconds() / 3600  # Hours
        except Exception as exc:
            logger.error(f"Failed to calculate hours since irrigation: {exc}")
            return None
    
    def build_ml_context(
        self,
        unit_id: int,
        current_readings: Dict[str, float],
        plant_info: Optional[Dict[str, Any]] = None,
    ) -> IrrigationMLContext:
        """
        Build ML context from current readings and historical data.
        
        Args:
            unit_id: The grow unit ID
            current_readings: Dict with temperature, humidity, vpd, lux, soil_moisture
            plant_info: Optional dict with plant_type, growth_stage
        """
        hours_since = self.calculate_hours_since_last_irrigation(unit_id)
        
        return IrrigationMLContext(
            temperature=current_readings.get("temperature"),
            humidity=current_readings.get("humidity"),
            vpd=current_readings.get("vpd"),
            lux=current_readings.get("lux"),
            hours_since_last_irrigation=hours_since,
            plant_type=plant_info.get("plant_type") if plant_info else None,
            growth_stage=plant_info.get("growth_stage") if plant_info else None,
            soil_moisture=current_readings.get("soil_moisture"),
        )
