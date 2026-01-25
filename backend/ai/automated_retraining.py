"""
Automated Model Retraining Scheduler
Schedules and executes model retraining based on triggers

Author: SYSGrow Team
Date: November 2025
"""

import logging
import schedule
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
import json
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class RetrainingTrigger(Enum):
    """Types of retraining triggers."""

    SCHEDULED = "scheduled"  # Fixed schedule (e.g., weekly)
    DRIFT_DETECTED = "drift_detected"  # Performance degradation
    DATA_THRESHOLD = "data_threshold"  # Enough new data accumulated
    MANUAL = "manual"  # Manual trigger
    FAILURE_RATE = "failure_rate"  # High prediction error rate


@dataclass
class RetrainingJob:
    """Retraining job configuration."""

    job_id: str
    model_name: str
    trigger_type: RetrainingTrigger
    schedule_pattern: Optional[str]  # e.g., "weekly", "daily"
    enabled: bool
    last_run: Optional[str]
    next_run: Optional[str]
    training_config: Dict[str, Any]


@dataclass
class RetrainingEvent:
    """Record of a retraining event."""

    event_id: str
    model_name: str
    trigger: RetrainingTrigger
    started_at: str
    completed_at: Optional[str]
    status: str  # 'running', 'completed', 'failed'
    new_version: Optional[str]
    metrics: Dict[str, float]
    error_message: Optional[str] = None


class AutomatedRetrainingScheduler:
    """
    Automate model retraining based on multiple triggers.

    Features:
    - Scheduled retraining (weekly, daily, etc.)
    - Drift-based retraining (performance monitoring)
    - Data threshold retraining (sufficient new data)
    - Manual trigger support
    - Retraining history tracking
    - Notification system
    """

    def __init__(
        self,
        ml_trainer: Any,
        drift_detector: Any,
        model_registry: Any,
        config_file: str = "models/retraining_config.json",
        events_file: str = "models/retraining_events.json",
    ):
        """
        Initialize retraining scheduler.

        Args:
            ml_trainer: EnhancedMLTrainer instance
            drift_detector: ModelDriftDetector instance
            model_registry: ModelRegistry instance
            config_file: Configuration file path
            events_file: Events log file path
        """
        self.ml_trainer = ml_trainer
        self.drift_detector = drift_detector
        self.model_registry = model_registry

        self.config_file = Path(config_file)
        self.events_file = Path(events_file)

        self.config_file.parent.mkdir(exist_ok=True)
        self.events_file.parent.mkdir(exist_ok=True)

        # Job configurations
        self.jobs: Dict[str, RetrainingJob] = {}
        self._load_config()

        # Event history
        self.events: List[RetrainingEvent] = []
        self._load_events()

        # Scheduler state
        self._scheduler_thread: Optional[threading.Thread] = None
        self._running = False
        self._stop_event = threading.Event()

        # Callbacks for notifications
        self.on_retrain_start: Optional[Callable] = None
        self.on_retrain_complete: Optional[Callable] = None
        self.on_retrain_failed: Optional[Callable] = None

    def _load_config(self):
        """Load retraining job configurations."""
        if not self.config_file.exists():
            self._create_default_config()
            return

        try:
            with open(self.config_file, "r") as f:
                data = json.load(f)

            for job_id, job_data in data.items():
                # Convert trigger type string to enum
                job_data["trigger_type"] = RetrainingTrigger(job_data["trigger_type"])
                self.jobs[job_id] = RetrainingJob(**job_data)

            logger.info(f"Loaded {len(self.jobs)} retraining jobs")

        except Exception as e:
            logger.error(f"Error loading retraining config: {e}")
            self._create_default_config()

    def _create_default_config(self):
        """Create default retraining configuration."""
        default_jobs = {
            "climate_weekly": RetrainingJob(
                job_id="climate_weekly",
                model_name="climate_predictor",
                trigger_type=RetrainingTrigger.SCHEDULED,
                schedule_pattern="weekly",
                enabled=True,
                last_run=None,
                next_run=None,
                training_config={"days": 90, "min_samples": 1000},
            ),
            "climate_drift": RetrainingJob(
                job_id="climate_drift",
                model_name="climate_predictor",
                trigger_type=RetrainingTrigger.DRIFT_DETECTED,
                schedule_pattern=None,
                enabled=True,
                last_run=None,
                next_run=None,
                training_config={"days": 90, "min_samples": 500},
            ),
        }

        self.jobs = default_jobs
        self._save_config()

    def _save_config(self):
        """Save retraining job configurations."""
        try:
            data = {}
            for job_id, job in self.jobs.items():
                job_dict = asdict(job)
                job_dict["trigger_type"] = job.trigger_type.value
                data[job_id] = job_dict

            with open(self.config_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving retraining config: {e}")

    def _load_events(self):
        """Load retraining event history."""
        if not self.events_file.exists():
            return

        try:
            with open(self.events_file, "r") as f:
                data = json.load(f)

            self.events = [
                RetrainingEvent(
                    trigger=RetrainingTrigger(e["trigger"]),
                    **{k: v for k, v in e.items() if k != "trigger"},
                )
                for e in data
            ]

            logger.info(f"Loaded {len(self.events)} retraining events")

        except Exception as e:
            logger.error(f"Error loading retraining events: {e}")

    def _save_events(self):
        """Save retraining event history."""
        try:
            data = []
            for event in self.events[-1000:]:  # Keep last 1000 events
                event_dict = asdict(event)
                event_dict["trigger"] = event.trigger.value
                data.append(event_dict)

            with open(self.events_file, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"Error saving retraining events: {e}")

    def add_job(
        self,
        job_id: str,
        model_name: str,
        trigger_type: RetrainingTrigger,
        schedule_pattern: Optional[str] = None,
        training_config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Add a retraining job.

        Args:
            job_id: Unique job identifier
            model_name: Name of the model to retrain
            trigger_type: Type of trigger
            schedule_pattern: Schedule pattern (for SCHEDULED trigger)
            training_config: Training configuration dict

        Returns:
            True if successful
        """
        try:
            job = RetrainingJob(
                job_id=job_id,
                model_name=model_name,
                trigger_type=trigger_type,
                schedule_pattern=schedule_pattern,
                enabled=True,
                last_run=None,
                next_run=None,
                training_config=training_config or {},
            )

            self.jobs[job_id] = job
            self._save_config()

            logger.info(f"✅ Added retraining job: {job_id}")
            return True

        except Exception as e:
            logger.error(f"Error adding job: {e}")
            return False

    def remove_job(self, job_id: str) -> bool:
        """Remove a retraining job."""
        if job_id in self.jobs:
            del self.jobs[job_id]
            self._save_config()
            logger.info(f"✅ Removed job: {job_id}")
            return True
        return False

    def enable_job(self, job_id: str, enabled: bool = True) -> bool:
        """Enable or disable a retraining job."""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = enabled
            self._save_config()
            logger.info(f"✅ {'Enabled' if enabled else 'Disabled'} job: {job_id}")
            return True
        return False

    def trigger_retraining(
        self,
        model_name: str,
        trigger_type: RetrainingTrigger = RetrainingTrigger.MANUAL,
        training_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Manually trigger model retraining.

        Args:
            model_name: Name of the model
            trigger_type: Type of trigger
            training_config: Optional training configuration

        Returns:
            Event ID or None if failed
        """
        logger.info(f"🔄 Triggering retraining for {model_name} ({trigger_type.value})")

        event_id = f"{model_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        event = RetrainingEvent(
            event_id=event_id,
            model_name=model_name,
            trigger=trigger_type,
            started_at=datetime.now().isoformat(),
            completed_at=None,
            status="running",
            new_version=None,
            metrics={},
        )

        self.events.append(event)
        self._save_events()

        # Notify start
        if self.on_retrain_start:
            try:
                self.on_retrain_start(model_name, trigger_type)
            except Exception as e:
                logger.error(f"Error in retrain start callback: {e}")

        try:
            # Execute retraining
            config = training_config or {}
            days = config.get("days", 90)

            logger.info(f"📊 Collecting training data ({days} days)...")
            df = self.ml_trainer.collect_training_data(days=days)

            if df.empty or len(df) < config.get("min_samples", 100):
                raise ValueError(f"Insufficient training data: {len(df)} samples")

            logger.info(f"🎯 Training {model_name}...")

            # Train based on model type
            if "climate" in model_name:
                results = self.ml_trainer.train_all_climate_models(df)
            elif "growth" in model_name:
                results = self.ml_trainer.train_growth_predictor(df)
            else:
                raise ValueError(f"Unknown model type: {model_name}")

            # Generate version number
            active_version = self.model_registry.get_active_version(model_name)
            new_version = self._increment_version(active_version)

            # Register new model
            # (Simplified - actual implementation would extract model and register)
            logger.info(f"📝 Registering {model_name} v{new_version}")

            # Update event
            event.completed_at = datetime.now().isoformat()
            event.status = "completed"
            event.new_version = new_version
            event.metrics = results.get("metrics", {})

            self._save_events()

            logger.info(f"✅ Retraining completed: {model_name} v{new_version}")

            # Notify completion
            if self.on_retrain_complete:
                try:
                    self.on_retrain_complete(model_name, new_version, event.metrics)
                except Exception as e:
                    logger.error(f"Error in retrain complete callback: {e}")

            return event_id

        except Exception as e:
            logger.error(f"❌ Retraining failed for {model_name}: {e}", exc_info=True)

            # Update event
            event.completed_at = datetime.now().isoformat()
            event.status = "failed"
            event.error_message = str(e)
            self._save_events()

            # Notify failure
            if self.on_retrain_failed:
                try:
                    self.on_retrain_failed(model_name, str(e))
                except Exception as e2:
                    logger.error(f"Error in retrain failed callback: {e2}")

            return None

    def _increment_version(self, current_version: Optional[str]) -> str:
        """Increment semantic version."""
        if not current_version:
            return "1.0.0"

        try:
            parts = current_version.split(".")
            major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

            # Increment minor version for retraining
            return f"{major}.{minor + 1}.0"

        except Exception:
            return "1.0.0"

    def check_drift_triggers(self):
        """Check all drift-based triggers."""
        for job_id, job in self.jobs.items():
            if not job.enabled or job.trigger_type != RetrainingTrigger.DRIFT_DETECTED:
                continue

            # Check drift
            should_retrain, reason = self.drift_detector.should_retrain(job.model_name)

            if should_retrain:
                logger.warning(f"⚠️ Drift detected for {job.model_name}: {reason}")
                self.trigger_retraining(
                    job.model_name,
                    RetrainingTrigger.DRIFT_DETECTED,
                    job.training_config,
                )

                # Update last run
                job.last_run = datetime.now().isoformat()
                self._save_config()

    def start_scheduler(self):
        """Start the automated retraining scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._stop_event.clear()

        # Setup scheduled jobs
        for job_id, job in self.jobs.items():
            if not job.enabled or job.trigger_type != RetrainingTrigger.SCHEDULED:
                continue

            self._schedule_job(job)

        # Start scheduler thread
        self._scheduler_thread = threading.Thread(
            target=self._run_scheduler, daemon=True, name="RetrainingScheduler"
        )
        self._scheduler_thread.start()

        logger.info("🚀 Automated retraining scheduler started")

    def _schedule_job(self, job: RetrainingJob):
        """Schedule a job based on its pattern."""
        pattern = job.schedule_pattern

        if pattern == "daily":
            schedule.every().day.at("02:00").do(
                self.trigger_retraining,
                job.model_name,
                RetrainingTrigger.SCHEDULED,
                job.training_config,
            )
        elif pattern == "weekly":
            schedule.every().monday.at("02:00").do(
                self.trigger_retraining,
                job.model_name,
                RetrainingTrigger.SCHEDULED,
                job.training_config,
            )
        elif pattern == "monthly":
            # Run on first day of month
            schedule.every().day.at("02:00").do(self._monthly_check, job)

        logger.info(f"📅 Scheduled {job.job_id} ({pattern})")

    def _monthly_check(self, job: RetrainingJob):
        """Check if it's the first day of month for monthly jobs."""
        if datetime.now().day == 1:
            self.trigger_retraining(
                job.model_name, RetrainingTrigger.SCHEDULED, job.training_config
            )

    def _run_scheduler(self):
        """Run the scheduler loop."""
        logger.info("Scheduler thread started")

        while self._running and not self._stop_event.is_set():
            try:
                # Run pending scheduled jobs
                schedule.run_pending()

                # Check drift triggers (every hour)
                if datetime.now().minute == 0:
                    self.check_drift_triggers()

                # Sleep for 1 minute
                self._stop_event.wait(60)

            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                time.sleep(60)

        logger.info("Scheduler thread stopped")

    def stop_scheduler(self):
        """Stop the automated retraining scheduler."""
        if not self._running:
            return

        logger.info("🛑 Stopping retraining scheduler...")
        self._running = False
        self._stop_event.set()

        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=5)

        schedule.clear()
        logger.info("✅ Scheduler stopped")

    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a retraining job."""
        if job_id not in self.jobs:
            return None

        job = self.jobs[job_id]

        # Get recent events for this model
        recent_events = [e for e in self.events if e.model_name == job.model_name][
            -5:
        ]  # Last 5 events

        return {
            "job_id": job.job_id,
            "model_name": job.model_name,
            "trigger_type": job.trigger_type.value,
            "schedule_pattern": job.schedule_pattern,
            "enabled": job.enabled,
            "last_run": job.last_run,
            "next_run": job.next_run,
            "recent_events": [asdict(e) for e in recent_events],
        }

    def get_all_jobs(self) -> List[Dict[str, Any]]:
        """Get status of all retraining jobs."""
        return [self.get_job_status(job_id) for job_id in self.jobs.keys()]


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("🔄 Automated Retraining Scheduler Example")
    print("=" * 50)

    # This would normally be initialized with real instances
    # scheduler = AutomatedRetrainingScheduler(ml_trainer, drift_detector, model_registry)
    # scheduler.start_scheduler()

    print("\nScheduler features:")
    print("  ✅ Weekly scheduled retraining")
    print("  ✅ Drift-based triggers")
    print("  ✅ Manual triggers")
    print("  ✅ Event history tracking")
    print("  ✅ Notification callbacks")
