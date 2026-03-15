"""
ML Readiness Monitor Service
=============================

Monitors ML training data collection and notifies users when models
have enough data for activation.

This service:
1. Tracks data collection progress for each ML model type
2. Detects when enough data is available for training
3. Sends notifications to users when models become ready
4. Handles model activation on user consent

Author: SYSGrow Team
Date: January 2026
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.utils.time import iso_now

if TYPE_CHECKING:
    from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository
    from app.services.application.notifications_service import NotificationsService

logger = logging.getLogger(__name__)


# Model configuration with user-friendly descriptions
MODEL_CONFIG = {
    "response_predictor": {
        "display_name": "User Response Predictor",
        "required_samples": 20,
        "description": "Predicts whether you'll approve, delay, or cancel irrigation requests",
        "benefits": [
            "Auto-approves irrigation when you usually approve",
            "Skips notifications when you usually cancel",
            "Learns your daily patterns and preferences",
        ],
    },
    "threshold_optimizer": {
        "display_name": "Soil Moisture Optimizer",
        "required_samples": 30,
        "description": "Optimizes soil moisture thresholds based on your feedback",
        "benefits": [
            "Reduces 'too dry' or 'too wet' situations",
            "Automatically adjusts thresholds per plant type",
            "Adapts to seasonal changes",
        ],
    },
    "duration_optimizer": {
        "display_name": "Watering Duration Optimizer",
        "required_samples": 15,
        "description": "Predicts the optimal watering duration for your setup",
        "benefits": [
            "Prevents overwatering and underwatering",
            "Saves water by optimizing pump run time",
            "Learns from soil moisture recovery patterns",
        ],
    },
    "timing_predictor": {
        "display_name": "Irrigation Timing Predictor",
        "required_samples": 25,
        "description": "Learns your preferred irrigation times",
        "benefits": [
            "Schedules irrigation at your preferred times",
            "Avoids inconvenient notification hours",
            "Adapts to your weekly routine",
        ],
    },
}


@dataclass
class ModelReadinessStatus:
    """Status of a specific ML model's data readiness."""
    
    model_name: str
    display_name: str
    required_samples: int
    current_samples: int
    is_ready: bool = field(init=False)
    is_activated: bool = False
    notification_sent: bool = False
    description: str = ""
    benefits: List[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        self.is_ready = self.current_samples >= self.required_samples
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage toward readiness."""
        if self.required_samples <= 0:
            return 100.0
        return min(100.0, (self.current_samples / self.required_samples) * 100)
    
    @property
    def samples_needed(self) -> int:
        """Calculate remaining samples needed."""
        return max(0, self.required_samples - self.current_samples)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "model_name": self.model_name,
            "display_name": self.display_name,
            "required_samples": self.required_samples,
            "current_samples": self.current_samples,
            "is_ready": self.is_ready,
            "is_activated": self.is_activated,
            "notification_sent": self.notification_sent,
            "progress_percent": round(self.progress_percent, 1),
            "samples_needed": self.samples_needed,
            "description": self.description,
            "benefits": self.benefits,
        }


@dataclass
class IrrigationMLReadiness:
    """Overall irrigation ML readiness status for a unit."""
    
    unit_id: int
    models: Dict[str, ModelReadinessStatus] = field(default_factory=dict)
    last_checked: Optional[str] = None
    
    @property
    def any_ready_not_activated(self) -> bool:
        """Check if any model is ready but not yet activated."""
        return any(
            m.is_ready and not m.is_activated 
            for m in self.models.values()
        )
    
    @property
    def ready_not_notified(self) -> List[ModelReadinessStatus]:
        """Get models that are ready but user hasn't been notified."""
        return [
            m for m in self.models.values()
            if m.is_ready and not m.is_activated and not m.notification_sent
        ]
    
    @property
    def all_models_activated(self) -> bool:
        """Check if all ready models are activated."""
        return all(
            m.is_activated for m in self.models.values() if m.is_ready
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "unit_id": self.unit_id,
            "models": {k: v.to_dict() for k, v in self.models.items()},
            "any_ready_not_activated": self.any_ready_not_activated,
            "all_models_activated": self.all_models_activated,
            "last_checked": self.last_checked,
        }


class MLReadinessMonitorService:
    """
    Monitors ML training data collection and notifies users
    when models have enough data for activation.
    
    This service runs periodically to:
    1. Check data collection progress for each unit
    2. Detect when models have enough training data
    3. Send notifications to users about ready models
    4. Track which models have been activated
    """
    
    def __init__(
        self,
        irrigation_ml_repo: "IrrigationMLRepository",
        notifications_service: Optional["NotificationsService"] = None,
    ):
        """
        Initialize ML readiness monitor.
        
        Args:
            irrigation_ml_repo: Repository for irrigation ML data
            notifications_service: Service for sending notifications
        """
        self._ml_repo = irrigation_ml_repo
        self._notifications = notifications_service
        
        logger.info("MLReadinessMonitorService initialized")
    
    def set_notifications_service(self, service: "NotificationsService") -> None:
        """Set notifications service (for circular dependency resolution)."""
        self._notifications = service
    
    def check_irrigation_readiness(
        self,
        unit_id: int,
    ) -> IrrigationMLReadiness:
        """
        Check readiness of all irrigation ML models for a unit.
        
        Args:
            unit_id: Growth unit ID to check
            
        Returns:
            IrrigationMLReadiness with status of all models
        """
        # Get sample counts from repository
        readiness_status = self._ml_repo.get_ml_readiness_status(unit_id)
        
        # Build model status objects with config
        models = {}
        for model_name, config in MODEL_CONFIG.items():
            ml_status = readiness_status.get(model_name)
            
            models[model_name] = ModelReadinessStatus(
                model_name=model_name,
                display_name=config["display_name"],
                required_samples=config["required_samples"],
                current_samples=ml_status.current_samples if ml_status else 0,
                is_activated=ml_status.is_enabled if ml_status else False,
                notification_sent=ml_status.notification_sent_at is not None if ml_status else False,
                description=config["description"],
                benefits=config["benefits"],
            )
        
        return IrrigationMLReadiness(
            unit_id=unit_id,
            models=models,
            last_checked=iso_now(),
        )
    
    def check_and_notify(self, user_id: int, unit_id: int) -> List[str]:
        """
        Check readiness and send notifications for newly ready models.
        
        Args:
            user_id: User ID to notify
            unit_id: Growth unit ID to check
            
        Returns:
            List of model names that triggered notifications
        """
        readiness = self.check_irrigation_readiness(unit_id)
        notified_models = []
        
        for model in readiness.ready_not_notified:
            success = self._send_model_ready_notification(
                user_id=user_id,
                unit_id=unit_id,
                model_status=model,
            )
            if success:
                # Mark as notified
                self._ml_repo.mark_ml_notification_sent(unit_id, model.model_name)
                notified_models.append(model.model_name)
                logger.info(
                    f"Sent ML readiness notification for {model.display_name} "
                    f"(unit={unit_id}, user={user_id})"
                )
        
        return notified_models
    
    def check_all_units(self) -> Dict[int, List[str]]:
        """
        Check all units for ML readiness and send notifications.
        
        Called by scheduled task to periodically check all units.
        
        Returns:
            Dict mapping unit_id to list of notified model names
        """
        results = {}
        
        try:
            unit_ids = self._ml_repo.get_units_with_workflow_enabled()

            for unit_id in unit_ids:
                # Get user_id for this unit (assuming 1 for now, should query)
                user_id = 1  # TODO: Get actual user_id from unit

                notified = self.check_and_notify(user_id, unit_id)
                results[unit_id] = notified
            
            if results:
                notified_units = [unit_id for unit_id, models in results.items() if models]
                if notified_units:
                    logger.info(f"ML readiness check complete: {len(notified_units)} units notified")
            
        except Exception as exc:
            logger.error(f"Error checking ML readiness for all units: {exc}")
        
        return results
    
    def _send_model_ready_notification(
        self,
        user_id: int,
        unit_id: int,
        model_status: ModelReadinessStatus,
    ) -> bool:
        """
        Send notification about model readiness.
        
        Args:
            user_id: User ID to notify
            unit_id: Growth unit ID
            model_status: Status of the ready model
            
        Returns:
            True if notification sent successfully
        """
        if not self._notifications:
            logger.warning("Notifications service not available")
            return False
        
        try:
            from app.services.application.notifications_service import (
                NotificationType,
                NotificationSeverity,
            )
            
            title = f"ML Ready: {model_status.display_name}"

            benefits_text = "\n".join(f"- {b}" for b in model_status.benefits[:2])
            message = (
                f"Great news! Your irrigation system has collected enough data to enable "
                f"the {model_status.display_name}.\n\n"
                f"What this means:\n{benefits_text}\n\n"
                f"Would you like to activate this feature?"
            )
            
            notification_id = self._notifications.send_notification(
                user_id=user_id,
                notification_type=NotificationType.ML_MODEL_READY,
                title=title,
                message=message,
                severity=NotificationSeverity.INFO,
                source_type="ml_readiness",
                source_id=unit_id,
                unit_id=unit_id,
                requires_action=True,
                action_type="ml_model_activation",
                action_data={
                    "model_name": model_status.model_name,
                    "unit_id": unit_id,
                    "display_name": model_status.display_name,
                },
            )
            
            return notification_id is not None
            
        except Exception as exc:
            logger.error(f"Failed to send ML readiness notification: {exc}")
            return False
    
    def activate_model(
        self,
        user_id: int,
        unit_id: int,
        model_name: str,
    ) -> bool:
        """
        Activate a specific ML model for a unit.
        
        Called when user approves model activation from notification.
        
        Args:
            user_id: User ID (for audit logging)
            unit_id: Growth unit ID
            model_name: Name of the model to activate
            
        Returns:
            True if activation succeeded
        """
        if model_name not in MODEL_CONFIG:
            logger.warning(f"Unknown model name: {model_name}")
            return False
        
        success = self._ml_repo.enable_ml_model(unit_id, model_name, enabled=True)
        
        if success:
            logger.info(
                f"Activated ML model {model_name} for unit {unit_id} "
                f"(user={user_id})"
            )
            
            # Send confirmation notification
            self._send_activation_confirmation(user_id, unit_id, model_name)
        
        return success
    
    def deactivate_model(
        self,
        user_id: int,
        unit_id: int,
        model_name: str,
    ) -> bool:
        """
        Deactivate a specific ML model for a unit.
        
        Args:
            user_id: User ID (for audit logging)
            unit_id: Growth unit ID
            model_name: Name of the model to deactivate
            
        Returns:
            True if deactivation succeeded
        """
        if model_name not in MODEL_CONFIG:
            logger.warning(f"Unknown model name: {model_name}")
            return False
        
        success = self._ml_repo.enable_ml_model(unit_id, model_name, enabled=False)
        
        if success:
            logger.info(
                f"Deactivated ML model {model_name} for unit {unit_id} "
                f"(user={user_id})"
            )
        
        return success
    
    def _send_activation_confirmation(
        self,
        user_id: int,
        unit_id: int,
        model_name: str,
    ) -> None:
        """Send confirmation notification after model activation."""
        if not self._notifications:
            return
        
        try:
            from app.services.application.notifications_service import (
                NotificationType,
                NotificationSeverity,
            )
            
            config = MODEL_CONFIG.get(model_name, {})
            display_name = config.get("display_name", model_name)
            
            self._notifications.send_notification(
                user_id=user_id,
                notification_type=NotificationType.ML_MODEL_ACTIVATED,
                title=f"ML Activated: {display_name}",
                message=(
                    f"The {display_name} is now active and learning from your "
                    f"irrigation patterns. You'll see smarter recommendations soon!"
                ),
                severity=NotificationSeverity.INFO,
                source_type="ml_activation",
                source_id=unit_id,
                unit_id=unit_id,
            )
        except Exception as exc:
            logger.debug(f"Failed to send activation confirmation: {exc}")
    
    def get_activation_status(self, unit_id: int) -> Dict[str, bool]:
        """
        Get activation status of all ML models for a unit.
        
        Args:
            unit_id: Growth unit ID
            
        Returns:
            Dict mapping model_name to activation status
        """
        readiness = self.check_irrigation_readiness(unit_id)
        return {
            name: status.is_activated 
            for name, status in readiness.models.items()
        }
