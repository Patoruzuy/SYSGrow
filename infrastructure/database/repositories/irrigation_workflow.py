"""Repository for Irrigation Workflow data access."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

logger = logging.getLogger(__name__)


class IrrigationWorkflowRepository:
    """Repository for irrigation workflow data access."""

    def __init__(self, db_handler: "SQLiteDatabaseHandler"):
        self._db = db_handler

    # ========== Pending Irrigation Requests ==========

    def create_request(
        self,
        unit_id: int,
        soil_moisture_detected: float,
        soil_moisture_threshold: float,
        user_id: int = 1,
        plant_id: Optional[int] = None,
        actuator_id: Optional[int] = None,
        actuator_type: str = "water_pump",
        sensor_id: Optional[int] = None,
        scheduled_time: Optional[str] = None,
        expires_at: Optional[str] = None,
        # ML context fields (Phase 1)
        temperature_at_detection: Optional[float] = None,
        humidity_at_detection: Optional[float] = None,
        vpd_at_detection: Optional[float] = None,
        lux_at_detection: Optional[float] = None,
        hours_since_last_irrigation: Optional[float] = None,
        plant_type: Optional[str] = None,
        growth_stage: Optional[str] = None,
    ) -> Optional[int]:
        """Create a new pending irrigation request with ML context."""
        return self._db.create_pending_irrigation_request(
            unit_id=unit_id,
            soil_moisture_detected=soil_moisture_detected,
            soil_moisture_threshold=soil_moisture_threshold,
            user_id=user_id,
            plant_id=plant_id,
            actuator_id=actuator_id,
            actuator_type=actuator_type,
            sensor_id=sensor_id,
            scheduled_time=scheduled_time,
            expires_at=expires_at,
            temperature_at_detection=temperature_at_detection,
            humidity_at_detection=humidity_at_detection,
            vpd_at_detection=vpd_at_detection,
            lux_at_detection=lux_at_detection,
            hours_since_last_irrigation=hours_since_last_irrigation,
            plant_type=plant_type,
            growth_stage=growth_stage,
        )

    def get_request(self, request_id: int) -> Optional[Dict[str, Any]]:
        """Get a pending irrigation request by ID."""
        return self._db.get_pending_irrigation_request(request_id)

    def get_requests_for_unit(
        self,
        unit_id: int,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get pending irrigation requests for a unit."""
        return self._db.get_pending_requests_for_unit(unit_id, status)

    def get_requests_for_user(
        self,
        user_id: int,
        status: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Get pending irrigation requests for a user."""
        return self._db.get_pending_requests_for_user(user_id, status, limit)

    def get_due_requests(self, current_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get requests that are due for execution."""
        return self._db.get_requests_due_for_execution(current_time)

    def claim_due_requests(
        self,
        current_time: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Atomically claim due requests for execution."""
        return self._db.claim_due_requests(current_time, limit)

    def mark_execution_started(
        self,
        request_id: int,
        started_at_utc: str,
        planned_duration_seconds: int,
    ) -> bool:
        """Mark a request as executing with a planned duration."""
        return self._db.mark_execution_started(request_id, started_at_utc, planned_duration_seconds)

    def get_executing_requests(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get requests currently executing."""
        return self._db.get_executing_requests(limit)

    def get_expired_requests(self, current_time: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get expired requests."""
        return self._db.get_expired_requests(current_time)

    def update_status(
        self,
        request_id: int,
        status: str,
        user_response: Optional[str] = None,
        delayed_until: Optional[str] = None,
    ) -> bool:
        """Update request status."""
        return self._db.update_request_status(request_id, status, user_response, delayed_until)

    def record_execution(
        self,
        request_id: int,
        success: bool,
        duration_seconds: Optional[int] = None,
        soil_moisture_after: Optional[float] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Record execution results."""
        return self._db.record_execution(
            request_id, success, duration_seconds, soil_moisture_after, error
        )

    def acquire_unit_lock(
        self,
        unit_id: int,
        lock_seconds: int,
        current_time: Optional[str] = None,
    ) -> bool:
        """Acquire a unit-level irrigation lock with a TTL."""
        return self._db.acquire_unit_lock(unit_id, lock_seconds, current_time)

    def release_unit_lock(self, unit_id: int) -> bool:
        """Release a unit-level irrigation lock."""
        return self._db.release_unit_lock(unit_id)

    def create_execution_log(
        self,
        *,
        request_id: Optional[int],
        user_id: Optional[int],
        unit_id: int,
        plant_id: Optional[int],
        sensor_id: Optional[str],
        trigger_reason: str,
        trigger_moisture: Optional[float],
        threshold_at_trigger: Optional[float],
        triggered_at_utc: str,
        planned_duration_s: Optional[int],
        pump_actuator_id: Optional[str],
        valve_actuator_id: Optional[str],
        assumed_flow_ml_s: Optional[float],
        estimated_volume_ml: Optional[float],
        execution_status: str,
        execution_error: Optional[str],
        executed_at_utc: str,
        post_moisture_delay_s: Optional[int],
        created_at_utc: Optional[str] = None,
    ) -> Optional[int]:
        """Create an irrigation execution log entry."""
        return self._db.create_execution_log(
            request_id=request_id,
            user_id=user_id,
            unit_id=unit_id,
            plant_id=plant_id,
            sensor_id=sensor_id,
            trigger_reason=trigger_reason,
            trigger_moisture=trigger_moisture,
            threshold_at_trigger=threshold_at_trigger,
            triggered_at_utc=triggered_at_utc,
            planned_duration_s=planned_duration_s,
            pump_actuator_id=pump_actuator_id,
            valve_actuator_id=valve_actuator_id,
            assumed_flow_ml_s=assumed_flow_ml_s,
            estimated_volume_ml=estimated_volume_ml,
            execution_status=execution_status,
            execution_error=execution_error,
            executed_at_utc=executed_at_utc,
            post_moisture_delay_s=post_moisture_delay_s,
            created_at_utc=created_at_utc,
        )

    def update_execution_log_status(
        self,
        request_id: int,
        *,
        execution_status: str,
        actual_duration_s: Optional[int] = None,
        estimated_volume_ml: Optional[float] = None,
        execution_error: Optional[str] = None,
    ) -> bool:
        """Update execution log status for a request."""
        return self._db.update_execution_log_status(
            request_id,
            execution_status=execution_status,
            actual_duration_s=actual_duration_s,
            estimated_volume_ml=estimated_volume_ml,
            execution_error=execution_error,
        )

    def get_execution_logs_pending_post_capture(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution logs awaiting post-watering moisture capture."""
        return self._db.get_execution_logs_pending_post_capture(limit)

    def update_execution_log_post_moisture(
        self,
        log_id: int,
        *,
        post_moisture: float,
        post_measured_at_utc: str,
        delta_moisture: Optional[float],
        recommendation: Optional[str],
    ) -> bool:
        """Update execution log with post-watering moisture data."""
        return self._db.update_execution_log_post_moisture(
            log_id,
            post_moisture=post_moisture,
            post_measured_at_utc=post_measured_at_utc,
            delta_moisture=delta_moisture,
            recommendation=recommendation,
        )

    def create_eligibility_trace(
        self,
        *,
        plant_id: Optional[int],
        unit_id: int,
        sensor_id: Optional[str],
        moisture: Optional[float],
        threshold: Optional[float],
        decision: str,
        skip_reason: Optional[str],
        evaluated_at_utc: str,
    ) -> Optional[int]:
        """Create an irrigation eligibility trace entry."""
        return self._db.create_eligibility_trace(
            plant_id=plant_id,
            unit_id=unit_id,
            sensor_id=sensor_id,
            moisture=moisture,
            threshold=threshold,
            decision=decision,
            skip_reason=skip_reason,
            evaluated_at_utc=evaluated_at_utc,
        )

    def create_manual_irrigation_log(
        self,
        *,
        user_id: int,
        unit_id: int,
        plant_id: int,
        watered_at_utc: str,
        amount_ml: Optional[float],
        notes: Optional[str],
        pre_moisture: Optional[float],
        pre_moisture_at_utc: Optional[str],
        settle_delay_min: int,
        created_at_utc: Optional[str] = None,
    ) -> Optional[int]:
        """Create a manual irrigation log entry."""
        return self._db.create_manual_irrigation_log(
            user_id=user_id,
            unit_id=unit_id,
            plant_id=plant_id,
            watered_at_utc=watered_at_utc,
            amount_ml=amount_ml,
            notes=notes,
            pre_moisture=pre_moisture,
            pre_moisture_at_utc=pre_moisture_at_utc,
            settle_delay_min=settle_delay_min,
            created_at_utc=created_at_utc,
        )

    def get_manual_logs_pending_post_capture(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get manual irrigation logs pending post-watering capture."""
        return self._db.get_manual_logs_pending_post_capture(limit=limit)

    def update_manual_log_post_moisture(
        self,
        log_id: int,
        *,
        post_moisture: float,
        post_moisture_at_utc: str,
        delta_moisture: Optional[float],
    ) -> bool:
        """Update manual irrigation log with post-watering moisture."""
        return self._db.update_manual_log_post_moisture(
            log_id,
            post_moisture=post_moisture,
            post_moisture_at_utc=post_moisture_at_utc,
            delta_moisture=delta_moisture,
        )

    def get_manual_logs_for_plant(
        self,
        plant_id: int,
        *,
        start_ts: str,
        end_ts: str,
    ) -> List[Dict[str, Any]]:
        """Fetch manual irrigation logs for a plant within a time window."""
        return self._db.get_manual_logs_for_plant(
            plant_id,
            start_ts=start_ts,
            end_ts=end_ts,
        )

    def get_execution_logs_for_plant(
        self,
        plant_id: int,
        *,
        start_ts: str,
        end_ts: str,
    ) -> List[Dict[str, Any]]:
        """Fetch irrigation execution logs for a plant within a time window."""
        return self._db.get_execution_logs_for_plant(
            plant_id,
            start_ts=start_ts,
            end_ts=end_ts,
        )

    def get_execution_logs_for_unit(
        self,
        unit_id: int,
        *,
        start_ts: str,
        end_ts: str,
        limit: int = 200,
        plant_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch irrigation execution logs for a unit within a time window."""
        return self._db.get_execution_logs_for_unit(
            unit_id,
            start_ts=start_ts,
            end_ts=end_ts,
            limit=limit,
            plant_id=plant_id,
        )

    def get_eligibility_traces_for_unit(
        self,
        unit_id: int,
        *,
        start_ts: str,
        end_ts: str,
        limit: int = 200,
        plant_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch irrigation eligibility traces for a unit within a time window."""
        return self._db.get_eligibility_traces_for_unit(
            unit_id,
            start_ts=start_ts,
            end_ts=end_ts,
            limit=limit,
            plant_id=plant_id,
        )

    def get_manual_logs_for_unit(
        self,
        unit_id: int,
        *,
        start_ts: str,
        end_ts: str,
        limit: int = 200,
        plant_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch manual irrigation logs for a unit within a time window."""
        return self._db.get_manual_logs_for_unit(
            unit_id,
            start_ts=start_ts,
            end_ts=end_ts,
            limit=limit,
            plant_id=plant_id,
        )

    def get_plant_irrigation_model(self, plant_id: int) -> Optional[Dict[str, Any]]:
        """Fetch stored irrigation model for a plant."""
        return self._db.get_plant_irrigation_model(plant_id)

    def upsert_plant_irrigation_model(
        self,
        *,
        plant_id: int,
        drydown_rate_per_hour: Optional[float],
        sample_count: int,
        confidence: Optional[float],
        updated_at_utc: str,
    ) -> bool:
        """Insert or update a plant irrigation model row."""
        return self._db.upsert_plant_irrigation_model(
            plant_id=plant_id,
            drydown_rate_per_hour=drydown_rate_per_hour,
            sample_count=sample_count,
            confidence=confidence,
            updated_at_utc=updated_at_utc,
        )

    def link_notification(self, request_id: int, notification_id: int) -> bool:
        """Link notification to request."""
        return self._db.link_notification(request_id, notification_id)

    def link_feedback(self, request_id: int, feedback_id: int) -> bool:
        """Link feedback to request."""
        return self._db.link_feedback(request_id, feedback_id)

    def get_request_by_feedback_id(self, feedback_id: int) -> Optional[Dict[str, Any]]:
        """Get pending request associated with a feedback record."""
        return self._db.get_request_by_feedback_id(feedback_id)

    def get_latest_execution_log_for_request(self, request_id: int) -> Optional[Dict[str, Any]]:
        """Get most recent execution log for a request."""
        return self._db.get_latest_execution_log_for_request(request_id)

    def mark_ml_collected(self, request_id: int, preference_score: Optional[float] = None) -> bool:
        """Mark ML data collected."""
        return self._db.mark_ml_data_collected(request_id, preference_score)

    def has_active_request(
        self,
        unit_id: int,
        plant_id: Optional[int] = None,
        actuator_id: Optional[int] = None,
    ) -> bool:
        """Check if unit has active pending request."""
        return self._db.has_active_request_for_unit(
            unit_id,
            plant_id=plant_id,
            actuator_id=actuator_id,
        )

    def get_last_completed_irrigation(
        self,
        unit_id: int,
        plant_id: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get the most recent completed irrigation for a unit or plant."""
        return self._db.get_last_completed_irrigation(unit_id, plant_id)

    def get_ml_training_samples_count(self, unit_id: Optional[int] = None) -> Dict[str, int]:
        """Get count of ML training samples by model type."""
        return self._db.count_ml_training_samples(unit_id)

    def get_ml_training_data(
        self,
        min_records: int = 20,
        unit_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Get ML training data for irrigation models."""
        return self._db.get_ml_training_data(min_records, unit_id)

    def get_history(self, unit_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Get irrigation request history for a unit."""
        return self._db.get_irrigation_request_history(unit_id, limit)

    # ========== Workflow Configuration ==========

    def get_config(self, unit_id: int) -> Optional[Dict[str, Any]]:
        """Get workflow configuration for a unit."""
        return self._db.get_workflow_config(unit_id)

    def save_config(self, unit_id: int, config: Dict[str, Any]) -> bool:
        """Save workflow configuration."""
        return self._db.upsert_workflow_config(unit_id, config)

    # ========== User Preferences ==========

    def get_user_preference(self, user_id: int, unit_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get user preferences."""
        return self._db.get_user_preference(user_id, unit_id)

    def update_preference_on_response(
        self,
        user_id: int,
        response_type: str,
        response_time_seconds: float,
        unit_id: Optional[int] = None,
    ) -> bool:
        """Update user preference based on response."""
        return self._db.update_user_preference_on_response(
            user_id, response_type, response_time_seconds, unit_id
        )

    def update_moisture_feedback(
        self,
        user_id: int,
        feedback_type: str,
        unit_id: Optional[int] = None,
    ) -> bool:
        """Update moisture feedback statistics."""
        return self._db.update_user_moisture_feedback(user_id, feedback_type, unit_id)

    def update_threshold_belief(
        self,
        user_id: int,
        unit_id: int,
        threshold_mean: float,
        threshold_variance: float,
        sample_count: int,
        belief_json: str,
    ) -> bool:
        """
        Update Bayesian threshold belief for a user/unit.
        
        Stores the belief parameters for persistence and ML learning.
        """
        return self._db.update_threshold_belief(
            user_id=user_id,
            unit_id=unit_id,
            threshold_mean=threshold_mean,
            threshold_variance=threshold_variance,
            sample_count=sample_count,
            belief_json=belief_json,
        )
