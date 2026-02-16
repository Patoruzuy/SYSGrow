"""
Centralized scheduling service for all background tasks.

This scheduler is designed to be Celery-compatible, making future migration seamless.
All scheduled tasks across the application go through this single service.

Design Principles:
- Single scheduler loop thread (Pi-friendly)
- Bounded worker pool for job execution (prevents unbounded thread creation)
- Celery-compatible job interface
- Namespace-based job organization
- Support for interval, daily, weekly, and one-time schedules

Future Celery Migration:
- Jobs are defined as regular functions with @scheduler.task decorator
- When migrating to Celery, replace @scheduler.task with @celery.task
- Job scheduling calls (schedule_interval, schedule_daily) become celery beat config

Author: SYSGrow Team
Date: December 2024
"""

from __future__ import annotations

import heapq
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Status of a scheduled job."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ScheduleType(Enum):
    """Types of schedules."""

    INTERVAL = "interval"  # Every N seconds/minutes/hours
    DAILY = "daily"  # At specific time each day
    WEEKLY = "weekly"  # Specific day and time each week
    ONCE = "once"  # One-time execution
    CRON = "cron"  # Cron-like expression (future)


@dataclass
class JobResult:
    """Result of a job execution."""

    job_id: str
    success: bool
    started_at: datetime
    completed_at: datetime
    result: Any = None
    error: str | None = None

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()


@dataclass
class ScheduledJob:
    """
    A scheduled job configuration.

    Designed to be Celery-compatible:
    - task_name maps to Celery task name
    - args/kwargs map to task arguments
    - schedule_type/interval map to Celery beat schedule
    """

    job_id: str
    task_name: str
    namespace: str  # e.g., "plant", "actuator", "ml", "maintenance"
    schedule_type: ScheduleType
    enabled: bool = True

    # Task execution
    func: Callable | None = None
    args: tuple = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)

    # Schedule configuration
    interval_seconds: int | None = None  # For INTERVAL type
    time_of_day: str | None = None  # "HH:MM" for DAILY type
    day_of_week: int | None = None  # 0-6 (Mon-Sun) for WEEKLY type
    run_at: datetime | None = None  # For ONCE type

    # Execution tracking
    next_run: datetime | None = None
    last_run: datetime | None = None
    run_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_error: str | None = None

    # Options (kept for forward-compat; not enforcing hard timeouts in threads)
    max_retries: int = 0
    retry_delay_seconds: int = 60
    timeout_seconds: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary (for API responses)."""
        return {
            "job_id": self.job_id,
            "task_name": self.task_name,
            "namespace": self.namespace,
            "schedule_type": self.schedule_type.value,
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "time_of_day": self.time_of_day,
            "day_of_week": self.day_of_week,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_error": self.last_error,
        }

    def to_celery_schedule(self) -> dict[str, Any]:
        """
        Convert to Celery beat schedule format.

        Use this when migrating to Celery:
        ```python
        app.conf.beat_schedule = {job.job_id: job.to_celery_schedule() for job in scheduler.get_jobs()}
        ```
        """
        from datetime import timedelta as td

        schedule_config = {
            "task": self.task_name,
            "args": self.args,
            "kwargs": self.kwargs,
        }

        if self.schedule_type == ScheduleType.INTERVAL:
            # Celery: schedule=timedelta(seconds=N)
            schedule_config["schedule"] = td(seconds=self.interval_seconds or 60)

        elif self.schedule_type == ScheduleType.DAILY:
            # Celery: schedule=crontab(hour=H, minute=M)
            if self.time_of_day:
                h, m = self.time_of_day.split(":")
                schedule_config["schedule_crontab"] = {"hour": int(h), "minute": int(m)}

        elif self.schedule_type == ScheduleType.WEEKLY:
            # Celery: schedule=crontab(hour=H, minute=M, day_of_week=D)
            if self.time_of_day and self.day_of_week is not None:
                h, m = self.time_of_day.split(":")
                schedule_config["schedule_crontab"] = {
                    "hour": int(h),
                    "minute": int(m),
                    "day_of_week": self.day_of_week,
                }

        return schedule_config


class UnifiedScheduler:
    """
    Centralized scheduler for all background tasks.

    Key improvements in this version:
    - No unbounded thread creation: uses a bounded ThreadPoolExecutor.
    - Heap de-duplication: heap stores immutable entries and skips stale items.
    - Interval drift reduction: INTERVAL schedules advance from the *scheduled time*,
      not from "now" (fixed-rate scheduling).

    Implementation note on the heap:
    - We store heap entries as tuples: (run_at_ts, seq, job_id)
    - seq is a monotonic counter to ensure stable ordering when timestamps match
    - We do NOT try to delete heap entries in-place (expensive); instead, we skip stale entries:
        - job removed -> skip
        - job disabled -> skip
        - job.next_run changed -> skip

    Celery Migration:
        When moving to Celery, replace:
        - @scheduler.task -> @celery.task
        - scheduler.schedule_* -> celery beat configuration
        - scheduler.run_now -> task.delay() or task.apply_async()
    """

    _instance: "UnifiedScheduler" | None = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "UnifiedScheduler":
        """Singleton pattern - ensures only one scheduler instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    cls._instance = instance
        return cls._instance

    def __init__(
        self,
        check_interval_seconds: float = 1.0,
        max_history: int = 1000,
        max_workers: int = 4,
    ):
        """
        Initialize the unified scheduler.

        Args:
            check_interval_seconds: How often to check for due jobs (default 1s)
            max_history: Maximum job execution history to keep
            max_workers: Maximum number of concurrent job executions
        """
        # Prevent re-initialization
        if hasattr(self, "_initialized") and self._initialized:
            return

        self._check_interval = float(check_interval_seconds)
        self._max_history = int(max_history)
        self._max_workers = int(max_workers)

        # Job storage
        self._jobs: dict[str, ScheduledJob] = {}
        self._tasks: dict[str, Callable] = {}  # task_name -> function

        # Heap storage
        # Entries: (run_at_ts, seq, job_id)
        self._job_heap: list[tuple[float, int, str]] = []
        self._heap_seq = 0

        # Execution history
        self._history: list[JobResult] = []

        # Thread management
        self._running = False
        self._thread: threading.Thread | None = None
        self._job_lock = threading.RLock()

        # Bounded executor for job execution
        self._executor: ThreadPoolExecutor | None = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="UnifiedSchedulerJob",
        )

        # Callbacks
        self._on_job_start: Callable[[ScheduledJob], None] | None = None
        self._on_job_complete: Callable[[ScheduledJob, JobResult], None] | None = None
        self._on_job_error: Callable[[ScheduledJob, Exception], None] | None = None

        self._initialized = True
        logger.info("UnifiedScheduler initialized (singleton)")

    # ==================== Task Registration ====================

    def task(self, name: str) -> Callable:
        """
        Decorator to register a task.

        Celery-compatible: Replace with @celery.task(name=name) when migrating.

        Usage:
            @scheduler.task("plant.health_check")
            def check_plant_health(unit_id: int):
                pass
        """

        def decorator(func: Callable) -> Callable:
            self._tasks[name] = func
            logger.debug(f"Registered task: {name}")

            @wraps(func)
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)

            # Celery-compat helpers (sync in this scheduler; you can later map to Celery async)
            wrapper.delay = lambda *a, **kw: self.run_now(name, args=a, kwargs=kw)
            wrapper.apply_async = lambda args=(), kwargs=None, **opts: self.run_now(
                name, args=args, kwargs=kwargs or {}
            )

            return wrapper

        return decorator

    def register_task(self, name: str, func: Callable) -> None:
        """Register a task function programmatically."""
        self._tasks[name] = func
        logger.debug(f"Registered task: {name}")

    def clear_jobs(self) -> None:
        """Remove all scheduled jobs and pending heap entries."""
        with self._job_lock:
            self._jobs.clear()
            self._job_heap.clear()
            self._heap_seq = 0

    def clear_history(self) -> None:
        """Clear execution history."""
        with self._job_lock:
            self._history.clear()

    def _ensure_executor(self) -> None:
        """Ensure an executor is available (supports stop() -> start() restarts)."""
        if self._executor is not None:
            return
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="UnifiedSchedulerJob",
        )

    # ==================== Heap Helpers ====================

    def _push_heap(self, job: ScheduledJob) -> None:
        """
        Push the job's next_run into the heap.

        We do not attempt to remove existing entries for this job.
        Instead, _process_due_jobs() skips stale entries by validating:
        - job exists
        - job enabled
        - entry timestamp equals job.next_run timestamp
        """
        if not job.enabled or not job.next_run:
            return
        self._heap_seq += 1
        heapq.heappush(self._job_heap, (job.next_run.timestamp(), self._heap_seq, job.job_id))

    # ==================== Job Scheduling ====================

    def schedule_interval(
        self,
        task_name: str,
        interval_seconds: int,
        *,
        job_id: str | None = None,
        namespace: str | None = None,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        enabled: bool = True,
        start_immediately: bool = False,
    ) -> ScheduledJob:
        """Schedule a task to run at regular intervals."""
        if job_id is None:
            job_id = f"{task_name}_{int(time.time())}"

        if namespace is None:
            namespace = task_name.split(".")[0] if "." in task_name else "default"

        now = datetime.now()
        next_run = now if start_immediately else (now + timedelta(seconds=int(interval_seconds)))

        job = ScheduledJob(
            job_id=job_id,
            task_name=task_name,
            namespace=namespace,
            schedule_type=ScheduleType.INTERVAL,
            enabled=enabled,
            args=args,
            kwargs=kwargs or {},
            interval_seconds=int(interval_seconds),
            next_run=next_run,
        )

        self._add_job(job)
        logger.info(f"Scheduled interval job: {job_id} (every {interval_seconds}s)")
        return job

    def schedule_daily(
        self,
        task_name: str,
        time_of_day: str,
        *,
        job_id: str | None = None,
        namespace: str | None = None,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> ScheduledJob:
        """Schedule a task to run daily at a specific time."""
        if job_id is None:
            job_id = f"{task_name}_daily_{time_of_day.replace(':', '')}"

        if namespace is None:
            namespace = task_name.split(".")[0] if "." in task_name else "default"

        next_run = self._calculate_next_daily(time_of_day)

        job = ScheduledJob(
            job_id=job_id,
            task_name=task_name,
            namespace=namespace,
            schedule_type=ScheduleType.DAILY,
            enabled=enabled,
            args=args,
            kwargs=kwargs or {},
            time_of_day=time_of_day,
            next_run=next_run,
        )

        self._add_job(job)
        logger.info(f"Scheduled daily job: {job_id} (at {time_of_day})")
        return job

    def schedule_weekly(
        self,
        task_name: str,
        day_of_week: int,
        time_of_day: str,
        *,
        job_id: str | None = None,
        namespace: str | None = None,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> ScheduledJob:
        """Schedule a task to run weekly on a specific day and time."""
        if job_id is None:
            days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            job_id = f"{task_name}_weekly_{days[int(day_of_week)]}_{time_of_day.replace(':', '')}"

        if namespace is None:
            namespace = task_name.split(".")[0] if "." in task_name else "default"

        next_run = self._calculate_next_weekly(int(day_of_week), time_of_day)

        job = ScheduledJob(
            job_id=job_id,
            task_name=task_name,
            namespace=namespace,
            schedule_type=ScheduleType.WEEKLY,
            enabled=enabled,
            args=args,
            kwargs=kwargs or {},
            time_of_day=time_of_day,
            day_of_week=int(day_of_week),
            next_run=next_run,
        )

        self._add_job(job)
        logger.info(f"Scheduled weekly job: {job_id} (day {day_of_week} at {time_of_day})")
        return job

    def schedule_once(
        self,
        task_name: str,
        run_at: datetime,
        *,
        job_id: str | None = None,
        namespace: str | None = None,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
    ) -> ScheduledJob:
        """Schedule a task to run once at a specific time."""
        if job_id is None:
            job_id = f"{task_name}_once_{int(run_at.timestamp())}"

        if namespace is None:
            namespace = task_name.split(".")[0] if "." in task_name else "default"

        job = ScheduledJob(
            job_id=job_id,
            task_name=task_name,
            namespace=namespace,
            schedule_type=ScheduleType.ONCE,
            enabled=True,
            args=args,
            kwargs=kwargs or {},
            run_at=run_at,
            next_run=run_at,
        )

        self._add_job(job)
        logger.info(f"Scheduled one-time job: {job_id} (at {run_at})")
        return job

    def run_now(
        self,
        task_name: str,
        *,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
    ) -> JobResult | None:
        """
        Run a task immediately (synchronously).

        Celery-compatible: Maps to task.delay() or task.apply_async()
        """
        func = self._tasks.get(task_name)
        if func is None:
            logger.error(f"Task not found: {task_name}")
            return None

        started_at = datetime.now()
        try:
            result = func(*args, **(kwargs or {}))
            completed_at = datetime.now()

            job_result = JobResult(
                job_id=f"{task_name}_immediate_{int(started_at.timestamp())}",
                success=True,
                started_at=started_at,
                completed_at=completed_at,
                result=result,
            )
            self._record_history(job_result)
            return job_result

        except Exception as e:
            completed_at = datetime.now()
            logger.error(f"Immediate task {task_name} failed: {e}", exc_info=True)

            job_result = JobResult(
                job_id=f"{task_name}_immediate_{int(started_at.timestamp())}",
                success=False,
                started_at=started_at,
                completed_at=completed_at,
                error=str(e),
            )
            self._record_history(job_result)
            return job_result

    # ==================== Job Management ====================

    def _add_job(self, job: ScheduledJob) -> None:
        """Add a job to the scheduler."""
        with self._job_lock:
            self._jobs[job.job_id] = job
            self._push_heap(job)

    def remove_job(self, job_id: str) -> bool:
        """Remove a job from the scheduler."""
        with self._job_lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                # Note: we do not delete heap entries in-place; they will be skipped as stale.
                logger.info(f"Removed job: {job_id}")
                return True
        return False

    def enable_job(self, job_id: str, enabled: bool = True) -> bool:
        """Enable or disable a job."""
        with self._job_lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            job.enabled = bool(enabled)

            if job.enabled:
                # If next_run is missing (e.g., previously disabled), recompute a sensible next run.
                if job.next_run is None:
                    self._schedule_next_run(job, reference_time=datetime.now())
                self._push_heap(job)

            logger.info(f"Job {job_id} {'enabled' if job.enabled else 'disabled'}")
            return True

    def pause_job(self, job_id: str) -> bool:
        """Pause a job (alias for disable)."""
        return self.enable_job(job_id, enabled=False)

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job (alias for enable)."""
        return self.enable_job(job_id, enabled=True)

    def get_job(self, job_id: str) -> ScheduledJob | None:
        """Get a job by ID."""
        return self._jobs.get(job_id)

    def get_jobs(
        self,
        namespace: str | None = None,
        enabled_only: bool = False,
    ) -> list[ScheduledJob]:
        """Get all jobs, optionally filtered."""
        jobs = list(self._jobs.values())

        if namespace:
            jobs = [j for j in jobs if j.namespace == namespace]

        if enabled_only:
            jobs = [j for j in jobs if j.enabled]

        return jobs

    def get_namespaces(self) -> set[str]:
        """Get all job namespaces."""
        return {job.namespace for job in self._jobs.values()}

    # ==================== Scheduler Control ====================

    def start(self) -> None:
        """Start the scheduler background thread."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._ensure_executor()

        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="UnifiedScheduler",
        )
        self._thread.start()
        logger.info("UnifiedScheduler started")

    def stop(self, wait: bool = True, timeout: float = 5.0) -> None:
        """
        Stop the scheduler.

        Args:
            wait: Wait for scheduler thread to finish
            timeout: Maximum wait time in seconds
        """
        if not self._running:
            return

        self._running = False

        if wait and self._thread:
            self._thread.join(timeout=timeout)

        # Executor shutdown (bounded worker pool)
        if self._executor:
            self._executor.shutdown(wait=wait)
            self._executor = None

        logger.info("UnifiedScheduler stopped")

    def shutdown(self, wait: bool = True, timeout: float = 5.0) -> None:
        """Alias for stop(); matches other services' shutdown() convention."""
        self.stop(wait=wait, timeout=timeout)

    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running

    def _run_loop(self) -> None:
        """Main scheduler loop."""
        logger.debug("Scheduler loop started")

        while self._running:
            try:
                self._process_due_jobs()
                time.sleep(self._check_interval)
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                time.sleep(1)

        logger.debug("Scheduler loop ended")

    # ==================== Core Scheduling Logic ====================

    def _process_due_jobs(self) -> None:
        """Process all jobs that are due to run."""
        now_ts = datetime.now().timestamp()

        with self._job_lock:
            while self._job_heap:
                run_at_ts, _seq, job_id = self._job_heap[0]

                # Not due yet
                if run_at_ts > now_ts:
                    break

                # Pop candidate entry
                heapq.heappop(self._job_heap)

                job = self._jobs.get(job_id)
                if not job:
                    continue  # removed -> stale heap entry

                if not job.enabled or not job.next_run:
                    continue  # disabled -> skip

                # Stale entry check: if job.next_run changed since this entry was pushed, skip it
                if abs(job.next_run.timestamp() - run_at_ts) > 1e-6:
                    continue

                # We will execute for the scheduled time represented by this heap entry
                scheduled_for = job.next_run

                # Schedule next run *before* submitting execution:
                # - prevents missed schedules if execution is long
                # - fixes interval drift by advancing from the scheduled time
                self._schedule_next_run(job, reference_time=scheduled_for, scheduled_time=scheduled_for)
                self._push_heap(job)

                # Submit execution to bounded executor (prevents unbounded thread creation)
                if not self._executor:
                    logger.warning("Executor unavailable; skipping job execution")
                    continue

                try:
                    self._executor.submit(self._execute_job, job_id, scheduled_for)
                except Exception as e:
                    logger.error(f"Failed to submit job {job_id} to executor: {e}", exc_info=True)

    def _execute_job(self, job_id: str, scheduled_for: datetime) -> None:
        """
        Execute a single job.

        Args:
            job_id: Job identifier
            scheduled_for: The time this run was scheduled to occur (used for consistency)
        """
        with self._job_lock:
            job = self._jobs.get(job_id)

        # Job may have been removed/disabled between scheduling and execution
        if not job or not job.enabled:
            return

        started_at = datetime.now()

        # Notify start callback
        if self._on_job_start:
            try:
                self._on_job_start(job)
            except Exception as e:
                logger.warning(f"Job start callback failed: {e}")

        try:
            func = job.func or self._tasks.get(job.task_name)
            if func is None:
                raise ValueError(f"Task function not found: {job.task_name}")

            result = func(*job.args, **job.kwargs)

            completed_at = datetime.now()

            with self._job_lock:
                job.last_run = started_at
                job.run_count += 1
                job.success_count += 1
                job.last_error = None

            job_result = JobResult(
                job_id=job.job_id,
                success=True,
                started_at=started_at,
                completed_at=completed_at,
                result=result,
            )
            self._record_history(job_result)

            # Notify completion callback
            if self._on_job_complete:
                try:
                    self._on_job_complete(job, job_result)
                except Exception as e:
                    logger.warning(f"Job complete callback failed: {e}")

            logger.debug(
                f"Job {job.job_id} completed in {job_result.duration_seconds:.2f}s "
                f"(scheduled_for={scheduled_for.isoformat()})"
            )

        except Exception as e:
            completed_at = datetime.now()

            with self._job_lock:
                job.last_run = started_at
                job.run_count += 1
                job.failure_count += 1
                job.last_error = str(e)

            job_result = JobResult(
                job_id=job.job_id,
                success=False,
                started_at=started_at,
                completed_at=completed_at,
                error=str(e),
            )
            self._record_history(job_result)

            # Notify error callback
            if self._on_job_error:
                try:
                    self._on_job_error(job, e)
                except Exception as cb_e:
                    logger.warning(f"Job error callback failed: {cb_e}")

            logger.error(f"Job {job.job_id} failed: {e}", exc_info=True)

    def _schedule_next_run(
        self,
        job: ScheduledJob,
        *,
        reference_time: datetime,
        scheduled_time: datetime | None = None,
    ) -> None:
        """
        Calculate and set the next run time for a job.

        Args:
            job: ScheduledJob to update
            reference_time: time basis for calculations (usually "now" or scheduled_for)
            scheduled_time: if provided, indicates the scheduled time for the run that just fired

        Interval drift fix:
        - For INTERVAL schedules, advance from the scheduled time (fixed-rate),
          not from the completion time or "now".
        """
        if job.schedule_type == ScheduleType.INTERVAL:
            interval = int(job.interval_seconds or 60)

            # Fixed-rate: advance from scheduled_time if provided, else reference_time
            base = scheduled_time or reference_time

            # Always move forward at least one interval; do not “pile up” missed runs.
            next_run = base + timedelta(seconds=interval)

            # If we're far behind (e.g., system slept), skip ahead to the first future slot
            now = datetime.now()
            if next_run <= now:
                delta_seconds = (now - next_run).total_seconds()
                skips = int(delta_seconds // interval) + 1
                next_run = next_run + timedelta(seconds=skips * interval)

            job.next_run = next_run
            return

        if job.schedule_type == ScheduleType.DAILY:
            job.next_run = self._calculate_next_daily(job.time_of_day or "00:00")
            return

        if job.schedule_type == ScheduleType.WEEKLY:
            job.next_run = self._calculate_next_weekly(job.day_of_week or 0, job.time_of_day or "00:00")
            return

        if job.schedule_type == ScheduleType.ONCE:
            # One-time jobs don't repeat
            job.next_run = None
            job.enabled = False
            return

    def _calculate_next_daily(self, time_of_day: str) -> datetime:
        """Calculate next occurrence of a daily time."""
        now = datetime.now()
        hour, minute = map(int, time_of_day.split(":"))

        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return next_run

    def _calculate_next_weekly(self, day_of_week: int, time_of_day: str) -> datetime:
        """Calculate next occurrence of a weekly time."""
        now = datetime.now()
        hour, minute = map(int, time_of_day.split(":"))

        days_ahead = int(day_of_week) - now.weekday()
        if days_ahead < 0:
            days_ahead += 7
        elif days_ahead == 0:
            target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target_time <= now:
                days_ahead = 7

        next_run = now + timedelta(days=days_ahead)
        return next_run.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _record_history(self, result: JobResult) -> None:
        """Record job execution in history."""
        with self._job_lock:
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history :]

    # ==================== Callbacks ====================

    def set_callbacks(
        self,
        on_start: Callable[[ScheduledJob], None] | None = None,
        on_complete: Callable[[ScheduledJob, JobResult], None] | None = None,
        on_error: Callable[[ScheduledJob, Exception], None] | None = None,
    ) -> None:
        """Set callbacks for job lifecycle events."""
        self._on_job_start = on_start
        self._on_job_complete = on_complete
        self._on_job_error = on_error

    # ==================== Status & History ====================

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status."""
        with self._job_lock:
            enabled_jobs = [j for j in self._jobs.values() if j.enabled]
            pending = sum(1 for j in enabled_jobs if j.next_run is not None)

            return {
                "running": self._running,
                "total_jobs": len(self._jobs),
                "enabled_jobs": len(enabled_jobs),
                "namespaces": list(self.get_namespaces()),
                "pending_jobs": pending,  # stable count (not heap length)
                "history_size": len(self._history),
                "recent_failures": sum(1 for r in self._history[-20:] if not r.success),
                "max_workers": self._max_workers,
            }

    def health_check(self) -> dict[str, Any]:
        """
        Perform a comprehensive health check on the scheduler.

        Returns a structured health report including:
        - Overall health status (healthy/degraded/unhealthy)
        - Scheduler running state
        - Job execution statistics
        - Recent failure analysis
        - Stale job detection

        Returns:
            Health check report dictionary
        """
        with self._job_lock:
            now = datetime.now()

            # Basic status
            is_running = self._running
            total_jobs = len(self._jobs)
            enabled_jobs = [j for j in self._jobs.values() if j.enabled]

            # Recent execution analysis
            recent_history = self._history[-50:] if self._history else []
            recent_failures = [r for r in recent_history if not r.success]
            failure_rate = len(recent_failures) / len(recent_history) if recent_history else 0.0

            # Stale job detection (jobs that haven't run in expected time)
            stale_jobs = []
            for job in enabled_jobs:
                if job.last_run and job.schedule_type == ScheduleType.INTERVAL:
                    expected_interval = timedelta(seconds=job.interval_seconds or 60)
                    time_since_last = now - job.last_run
                    if time_since_last > expected_interval * 3:  # 3x overdue
                        stale_jobs.append(
                            {
                                "job_id": job.job_id,
                                "task_name": job.task_name,
                                "last_run": job.last_run.isoformat(),
                                "expected_interval_seconds": job.interval_seconds,
                                "overdue_seconds": time_since_last.total_seconds() - (job.interval_seconds or 60),
                            }
                        )

            # Determine overall health
            if not is_running:
                health = "unhealthy"
                health_reason = "Scheduler is not running"
            elif failure_rate > 0.5:
                health = "unhealthy"
                health_reason = f"High failure rate: {failure_rate:.0%}"
            elif stale_jobs:
                health = "degraded"
                health_reason = f"{len(stale_jobs)} stale job(s) detected"
            elif failure_rate > 0.2:
                health = "degraded"
                health_reason = f"Elevated failure rate: {failure_rate:.0%}"
            else:
                health = "healthy"
                health_reason = "All systems operational"

            # Recent failures detail
            failure_summary = {}
            for r in recent_failures:
                if r.job_id not in failure_summary:
                    failure_summary[r.job_id] = {"count": 0, "last_error": None}
                failure_summary[r.job_id]["count"] += 1
                failure_summary[r.job_id]["last_error"] = r.error

            return {
                "health": health,
                "reason": health_reason,
                "timestamp": now.isoformat(),
                "scheduler_running": is_running,
                "statistics": {
                    "total_jobs": total_jobs,
                    "enabled_jobs": len(enabled_jobs),
                    "recent_executions": len(recent_history),
                    "recent_failures": len(recent_failures),
                    "failure_rate": round(failure_rate, 3),
                },
                "stale_jobs": stale_jobs,
                "failure_summary": failure_summary,
                "thread_pool_active": self._executor is not None,
            }

    def get_history(
        self,
        job_id: str | None = None,
        namespace: str | None = None,
        limit: int = 100,
    ) -> list[JobResult]:
        """Get job execution history."""
        results = list(self._history)

        if job_id:
            results = [r for r in results if r.job_id == job_id]

        if namespace:
            ns_job_ids = {j.job_id for j in self._jobs.values() if j.namespace == namespace}
            results = [r for r in results if r.job_id in ns_job_ids]

        return sorted(results, key=lambda r: r.started_at, reverse=True)[: int(limit)]

    def export_celery_config(self) -> dict[str, Any]:
        """Export scheduler configuration in Celery beat format."""
        return {job.job_id: job.to_celery_schedule() for job in self._jobs.values() if job.enabled}


def get_scheduler() -> UnifiedScheduler:
    """Get the singleton UnifiedScheduler instance."""
    return UnifiedScheduler()
