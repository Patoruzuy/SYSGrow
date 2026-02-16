"""
Automated Retraining Service
=============================
Manages automated model retraining based on schedules and triggers.

Features:
- Scheduled periodic retraining
- Drift-triggered retraining
- Performance-based retraining
- Retraining job management
- Event logging and history
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from app.services.ai.drift_detector import ModelDriftDetectorService
    from app.services.ai.ml_trainer import MLTrainerService
    from app.services.ai.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class RetrainingTrigger(Enum):
    """Triggers for automated retraining."""

    SCHEDULED = "scheduled"  # Time-based schedule
    DRIFT_DETECTED = "drift_detected"  # Model drift threshold exceeded
    PERFORMANCE_DROP = "performance_drop"  # Performance degradation
    MANUAL = "manual"  # Manual trigger
    DATA_VOLUME = "data_volume"  # Minimum new data samples reached
    FAILURE_RATE = "failure_rate"  # High prediction error rate


class RetrainingStatus(Enum):
    """Status of retraining job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class RetrainingJob:
    """Configuration for an automated retraining job."""

    job_id: str
    model_type: str
    schedule_type: str  # "daily", "weekly", "monthly", "on_drift"
    enabled: bool = True
    min_samples: int = 100  # Minimum samples before retraining
    drift_threshold: float = 0.15  # Drift threshold for triggering
    performance_threshold: float = 0.80  # Minimum performance score
    schedule_time: str | None = None  # "HH:MM" for daily schedule
    schedule_day: int | None = None  # Day of week (0-6) or month (1-31)
    last_run: datetime | None = None
    next_run: datetime | None = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "job_id": self.job_id,
            "model_type": self.model_type,
            "schedule_type": self.schedule_type,
            "enabled": self.enabled,
            "min_samples": self.min_samples,
            "drift_threshold": self.drift_threshold,
            "performance_threshold": self.performance_threshold,
            "schedule_time": self.schedule_time,
            "schedule_day": self.schedule_day,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
        }


@dataclass
class RetrainingEvent:
    """Record of a retraining event."""

    event_id: str
    job_id: str
    model_type: str
    trigger: RetrainingTrigger
    status: RetrainingStatus
    started_at: datetime
    completed_at: datetime | None = None
    old_version: str | None = None
    new_version: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "event_id": self.event_id,
            "job_id": self.job_id,
            "model_type": self.model_type,
            "trigger": self.trigger.value,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "metrics": self.metrics,
            "error": self.error,
        }


class AutomatedRetrainingService:
    """
    Service for automated model retraining.

    Manages scheduled retraining jobs and drift-triggered retraining.
    """

    def __init__(
        self,
        model_registry: "ModelRegistry",
        drift_detector: "ModelDriftDetectorService",
        ml_trainer: "MLTrainerService",
    ):
        """
        Initialize automated retraining service.

        Args:
            model_registry: Model registry for version management
            drift_detector: Drift detector for monitoring model performance
            ml_trainer: ML trainer for retraining models
        """
        self.model_registry = model_registry
        self.drift_detector = drift_detector
        self.ml_trainer = ml_trainer

        # Job and event storage
        self.jobs: dict[str, RetrainingJob] = {}
        self.events: list[RetrainingEvent] = []
        self.max_events = 1000  # Keep last 1000 events
        self._lock = threading.RLock()
        self._active_event_ids_by_model_type: dict[str, str] = {}
        self._cancel_events_by_event_id: dict[str, threading.Event] = {}
        self._worker_threads_by_event_id: dict[str, threading.Thread] = {}

        # Scheduler state
        # Note: Scheduling is now handled by UnifiedScheduler via ml_drift_check_task()
        # (see app/workers/scheduled_tasks.py). These are kept for backward compatibility.
        self._scheduler_running = True  # Always "running" via UnifiedScheduler

        # Callbacks
        self._on_retraining_start: Callable | None = None
        self._on_retraining_complete: Callable | None = None

        logger.info("AutomatedRetrainingService initialized")

    def setup_irrigation_retraining_jobs(self) -> None:
        """
        Set up default retraining jobs for irrigation ML models.

        Creates jobs for:
        - irrigation_threshold: Weekly on Monday at 03:00
        - irrigation_response: Weekly on Monday at 03:30
        - irrigation_duration: Monthly on 1st at 04:00
        - irrigation_timing: Weekly on Monday at 04:30
        """
        # Threshold optimizer - learns from user feedback
        self.add_job(
            model_type="irrigation_threshold",
            schedule_type="weekly",
            job_id="irrigation_threshold_weekly",
            schedule_day=0,  # Monday
            schedule_time="03:00",
            min_samples=30,
            drift_threshold=0.20,
        )

        # Response predictor - learns user approve/delay/cancel patterns
        self.add_job(
            model_type="irrigation_response",
            schedule_type="weekly",
            job_id="irrigation_response_weekly",
            schedule_day=0,  # Monday
            schedule_time="03:30",
            min_samples=20,
            drift_threshold=0.15,
        )

        # Duration optimizer - learns optimal watering times
        self.add_job(
            model_type="irrigation_duration",
            schedule_type="monthly",
            job_id="irrigation_duration_monthly",
            schedule_day=1,  # 1st of month
            schedule_time="04:00",
            min_samples=15,
            drift_threshold=0.25,
        )

        # Timing predictor - learns preferred irrigation hour
        self.add_job(
            model_type="irrigation_timing",
            schedule_type="weekly",
            job_id="irrigation_timing_weekly",
            schedule_day=0,  # Monday
            schedule_time="04:30",
            min_samples=25,
            drift_threshold=0.20,
        )

        logger.info("Irrigation ML retraining jobs configured")

    def setup_climate_retraining_jobs(self) -> None:
        """Set up retraining jobs for climate optimisation models.

        Creates a weekly job that retrains the climate prediction model
        using recent sensor readings and user adjustments.
        """
        self.add_job(
            model_type="climate_optimizer",
            schedule_type="weekly",
            job_id="climate_optimizer_weekly",
            schedule_day=2,  # Wednesday
            schedule_time="03:00",
            min_samples=20,
            drift_threshold=0.20,
        )

        logger.info("Climate optimizer retraining job configured")

    def cancel_training(
        self,
        *,
        model_type: str | None = None,
        event_id: str | None = None,
    ) -> bool:
        """
        Request cancellation of an active retraining job.

        Args:
            model_type: Cancel the currently running event for this model type.
            event_id: Cancel a specific event by ID.

        Returns:
            True if a cancellation request was applied, False if no matching active job exists.
        """
        with self._lock:
            target_event_ids: list[str] = []

            if event_id:
                if event_id in self._cancel_events_by_event_id:
                    target_event_ids = [event_id]
            elif model_type:
                active_event_id = self._active_event_ids_by_model_type.get(model_type)
                if active_event_id and active_event_id in self._cancel_events_by_event_id:
                    target_event_ids = [active_event_id]
            else:
                target_event_ids = list(self._cancel_events_by_event_id.keys())

            for target_id in target_event_ids:
                self._cancel_events_by_event_id[target_id].set()

            return bool(target_event_ids)

    def add_job(self, model_type: str, schedule_type: str, job_id: str | None = None, **kwargs) -> RetrainingJob:
        """
        Add a new retraining job.

        Args:
            model_type: Type of model to retrain
            schedule_type: Schedule type (daily, weekly, monthly, on_drift)
            job_id: Optional custom job ID
            **kwargs: Additional job configuration

        Returns:
            Created RetrainingJob
        """
        if job_id is None:
            job_id = f"{model_type}_{schedule_type}_{datetime.now().timestamp()}"

        job = RetrainingJob(job_id=job_id, model_type=model_type, schedule_type=schedule_type, **kwargs)

        # Calculate next run time
        job.next_run = self._calculate_next_run(job)

        self.jobs[job_id] = job
        logger.info(f"Added retraining job: {job_id} ({model_type}, {schedule_type})")

        return job

    def remove_job(self, job_id: str) -> bool:
        """Remove a retraining job."""
        if job_id in self.jobs:
            del self.jobs[job_id]
            logger.info(f"Removed retraining job: {job_id}")
            return True
        return False

    def enable_job(self, job_id: str, enabled: bool = True) -> bool:
        """Enable or disable a retraining job."""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = enabled
            logger.info(f"Job {job_id} {'enabled' if enabled else 'disabled'}")
            return True
        return False

    def trigger_retraining(
        self,
        model_type: str,
        trigger: RetrainingTrigger = RetrainingTrigger.MANUAL,
        job_id: str | None = None,
    ) -> RetrainingEvent | None:
        """
        Trigger model retraining.

        Args:
            model_type: Type of model to retrain
            trigger: Reason for retraining
            job_id: Optional job ID that triggered this

        Returns:
            RetrainingEvent or None if failed
        """
        with self._lock:
            existing_event_id = self._active_event_ids_by_model_type.get(model_type)
            if existing_event_id:
                existing = next(
                    (e for e in self.events if e.event_id == existing_event_id),
                    None,
                )
                if existing:
                    return existing

        event_id = f"{model_type}_{datetime.now().timestamp()}"
        event = RetrainingEvent(
            event_id=event_id,
            job_id=job_id or "manual",
            model_type=model_type,
            trigger=trigger,
            status=RetrainingStatus.PENDING,
            started_at=datetime.now(),
        )

        cancel_event = threading.Event()

        with self._lock:
            self._active_event_ids_by_model_type[model_type] = event_id
            self._cancel_events_by_event_id[event_id] = cancel_event
            self._record_event(event)

            worker = threading.Thread(
                target=self._run_retraining,
                args=(event, cancel_event),
                daemon=True,
                name=f"Retraining-{model_type}-{event_id}",
            )
            self._worker_threads_by_event_id[event_id] = worker
            worker.start()

        return event

    def _run_retraining(self, event: RetrainingEvent, cancel_event: threading.Event) -> None:
        class RetrainingCancelled(Exception):
            pass

        from app.socketio.ml_handlers import (
            broadcast_training_cancelled,
            broadcast_training_complete,
            broadcast_training_failed,
            broadcast_training_progress,
            broadcast_training_started,
        )

        def check_cancel() -> None:
            if cancel_event.is_set():
                raise RetrainingCancelled("Cancelled by user")

        def broadcast_progress(progress: float, message: str | None = None) -> None:
            elapsed_seconds = max(0.0, (datetime.now() - event.started_at).total_seconds())
            broadcast_training_progress(
                event.model_type,
                event.old_version or "",
                float(progress),
                metrics=event.metrics,
                stage=None,
                message=message,
                elapsed_seconds=elapsed_seconds,
                eta_seconds=None,
            )

        job_id = event.job_id if event.job_id != "manual" else None

        try:
            check_cancel()

            # Get current model version
            try:
                event.old_version = self.model_registry.get_production_version(event.model_type)
            except Exception:
                event.old_version = None

            # Update status
            event.status = RetrainingStatus.RUNNING
            self._record_event(event)

            # Notify start callback
            if self._on_retraining_start:
                self._on_retraining_start(event)

            broadcast_training_started(event.model_type, event.old_version or "")
            broadcast_progress(5, "Starting retraining...")

            logger.info(f"Starting retraining for {event.model_type} (trigger: {event.trigger.value})")

            # Perform retraining based on model type
            metrics: dict[str, Any] | None = None
            check_cancel()

            if event.model_type == "climate":
                metrics = self.ml_trainer.train_climate_model(
                    cancel_event=cancel_event,
                    progress_callback=lambda p, msg=None: broadcast_progress(p, msg),
                )
            elif event.model_type == "disease":
                metrics = self.ml_trainer.train_disease_model(
                    cancel_event=cancel_event,
                    progress_callback=lambda p, msg=None: broadcast_progress(p, msg),
                )
            elif event.model_type == "growth_stage":
                logger.warning("Growth stage model training not yet implemented")
                metrics = {"success": False, "error": "Growth stage training not implemented"}
            # Irrigation ML models
            elif event.model_type == "irrigation_threshold":
                metrics = self.ml_trainer.train_irrigation_threshold_model(
                    cancel_event=cancel_event,
                    progress_callback=lambda p, msg=None: broadcast_progress(p, msg),
                )
            elif event.model_type == "irrigation_response":
                metrics = self.ml_trainer.train_irrigation_response_model(
                    cancel_event=cancel_event,
                    progress_callback=lambda p, msg=None: broadcast_progress(p, msg),
                )
            elif event.model_type == "irrigation_duration":
                metrics = self.ml_trainer.train_irrigation_duration_model(
                    cancel_event=cancel_event,
                    progress_callback=lambda p, msg=None: broadcast_progress(p, msg),
                )
            elif event.model_type == "irrigation_timing":
                metrics = self.ml_trainer.train_irrigation_timing_model(
                    cancel_event=cancel_event,
                    progress_callback=lambda p, msg=None: broadcast_progress(p, msg),
                )
            else:
                logger.warning(f"Unknown model type for retraining: {event.model_type}")
                metrics = {"success": False, "error": f"Unknown model type: {event.model_type}"}

            check_cancel()

            # Get new model version
            try:
                event.new_version = self.model_registry.get_production_version(event.model_type)
            except Exception:
                event.new_version = None

            # Record metrics
            if metrics:
                if hasattr(metrics, "to_dict"):
                    event.metrics = metrics.to_dict()
                elif isinstance(metrics, dict):
                    event.metrics = metrics
                else:
                    event.metrics = {}

            broadcast_progress(95, "Finalizing...")

            # Update status
            event.status = RetrainingStatus.COMPLETED
            event.completed_at = datetime.now()

            # Update job statistics
            if job_id and job_id in self.jobs:
                job = self.jobs[job_id]
                job.last_run = event.started_at
                job.run_count += 1
                job.success_count += 1
                job.next_run = self._calculate_next_run(job)

            logger.info(f"Retraining completed for {event.model_type}: {event.old_version} → {event.new_version}")

            broadcast_progress(100, "Retraining complete")
            broadcast_training_complete(event.model_type, event.new_version or "", event.metrics)

            # Notify completion callback
            if self._on_retraining_complete:
                self._on_retraining_complete(event)

        except RetrainingCancelled as e:
            event.status = RetrainingStatus.CANCELLED
            event.error = str(e)
            event.completed_at = datetime.now()
            logger.info(f"Retraining cancelled for {event.model_type}: {e}")
            broadcast_training_cancelled(event.model_type, event.old_version or "", str(e))

            if job_id and job_id in self.jobs:
                job = self.jobs[job_id]
                job.last_run = event.started_at
                job.run_count += 1
                job.failure_count += 1

        except Exception as e:
            event.status = RetrainingStatus.FAILED
            event.error = str(e)
            event.completed_at = datetime.now()

            if job_id and job_id in self.jobs:
                job = self.jobs[job_id]
                job.last_run = event.started_at
                job.run_count += 1
                job.failure_count += 1

            logger.error(f"Retraining failed for {event.model_type}: {e}", exc_info=True)
            broadcast_training_failed(event.model_type, event.old_version or "", str(e))

        finally:
            self._record_event(event)

            with self._lock:
                active_id = self._active_event_ids_by_model_type.get(event.model_type)
                if active_id == event.event_id:
                    self._active_event_ids_by_model_type.pop(event.model_type, None)
                self._cancel_events_by_event_id.pop(event.event_id, None)
                self._worker_threads_by_event_id.pop(event.event_id, None)

    def check_drift_triggers(self) -> list[RetrainingEvent]:
        """
        Check for drift-based retraining triggers.

        Returns:
            List of triggered retraining events
        """
        events = []

        for job in self.jobs.values():
            if not job.enabled or job.schedule_type != "on_drift":
                continue

            try:
                # Check drift for this model type
                drift_metrics = self.drift_detector.check_drift(model_name=job.model_type)

                if drift_metrics and drift_metrics.drift_score > job.drift_threshold:
                    logger.warning(
                        f"Drift detected for {job.model_type}: {drift_metrics.drift_score:.3f} > {job.drift_threshold}"
                    )

                    event = self.trigger_retraining(
                        model_type=job.model_type, trigger=RetrainingTrigger.DRIFT_DETECTED, job_id=job.job_id
                    )

                    if event:
                        events.append(event)

            except Exception as e:
                logger.error(f"Error checking drift for {job.model_type}: {e}")

        return events

    def start_scheduler(self):
        """Start the automated retraining scheduler.

        Note: Scheduling is now handled by UnifiedScheduler via ml_drift_check_task()
        (see app/workers/scheduled_tasks.py). This method is kept for backward compatibility.
        """
        # Scheduling is now handled by UnifiedScheduler
        logger.debug("Retraining scheduling is handled by UnifiedScheduler")

    def stop_scheduler(self):
        """Stop the automated retraining scheduler.

        Note: Scheduling is now handled by UnifiedScheduler via ml_drift_check_task()
        (see app/workers/scheduled_tasks.py). This method is kept for backward compatibility.
        """
        # Scheduling is now handled by UnifiedScheduler
        logger.debug("Retraining scheduling is handled by UnifiedScheduler")

    def _calculate_next_run(self, job: RetrainingJob) -> datetime | None:
        """Calculate next run time for a job."""
        if job.schedule_type == "on_drift":
            return None  # Drift-based, no scheduled time

        now = datetime.now()

        if job.schedule_type == "daily":
            if job.schedule_time:
                hour, minute = map(int, job.schedule_time.split(":"))
                next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if next_run <= now:
                    next_run += timedelta(days=1)
                return next_run

        elif job.schedule_type == "weekly":
            if job.schedule_day is not None:
                days_ahead = job.schedule_day - now.weekday()
                if days_ahead <= 0:
                    days_ahead += 7
                return now + timedelta(days=days_ahead)

        elif job.schedule_type == "monthly":
            if job.schedule_day is not None:
                next_run = now.replace(day=job.schedule_day, hour=0, minute=0, second=0)
                if next_run <= now:
                    # Move to next month
                    if now.month == 12:
                        next_run = next_run.replace(year=now.year + 1, month=1)
                    else:
                        next_run = next_run.replace(month=now.month + 1)
                return next_run

        return None

    def _record_event(self, event: RetrainingEvent):
        """Record a retraining event."""
        with self._lock:
            # Ensure a single canonical entry per event_id.
            self.events = [e for e in self.events if e.event_id != event.event_id]
            self.events.append(event)

            # Trim events if exceeds max
            if len(self.events) > self.max_events:
                self.events = self.events[-self.max_events :]

    def get_jobs(self) -> list[RetrainingJob]:
        """Get all retraining jobs."""
        return list(self.jobs.values())

    def get_job(self, job_id: str) -> RetrainingJob | None:
        """Get a specific retraining job."""
        return self.jobs.get(job_id)

    def get_events(self, model_type: str | None = None, limit: int = 100) -> list[RetrainingEvent]:
        """
        Get retraining events.

        Args:
            model_type: Optional filter by model type
            limit: Maximum number of events to return

        Returns:
            List of retraining events
        """
        events = self.events

        if model_type:
            events = [e for e in events if e.model_type == model_type]

        # Return most recent events
        return sorted(events, key=lambda e: e.started_at, reverse=True)[:limit]

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status."""
        return {
            "scheduler_running": self._scheduler_running,
            "total_jobs": len(self.jobs),
            "enabled_jobs": sum(1 for j in self.jobs.values() if j.enabled),
            "total_events": len(self.events),
            "recent_failures": sum(1 for e in self.events[-10:] if e.status == RetrainingStatus.FAILED),
        }

    def set_callbacks(self, on_start: Callable | None = None, on_complete: Callable | None = None):
        """Set callbacks for retraining events."""
        self._on_retraining_start = on_start
        self._on_retraining_complete = on_complete
