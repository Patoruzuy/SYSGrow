"""
Workers module for background services and scheduled tasks.

This module contains:
- unified_scheduler: Unified scheduler for all background tasks (Celery-compatible)
- scheduled_tasks: Task definitions organized by namespace (plant.*, actuator.*, ml.*, maintenance.*)
"""

__all__ = [
    # New unified scheduler
    "UnifiedScheduler",
    "get_scheduler",
    "register_all_tasks",
    "schedule_default_jobs",
]

# New unified scheduler exports
from app.workers.unified_scheduler import UnifiedScheduler, get_scheduler
from app.workers.scheduled_tasks import register_all_tasks, schedule_default_jobs


