#!/usr/bin/env python3
"""Scheduler smoke script: registers a short task and runs the scheduler briefly."""
import time
import importlib

# Ensure tasks are registered
import app.workers.scheduled_tasks  # noqa: F401

from app.workers.unified_scheduler import get_scheduler


def main():
    sched = get_scheduler()

    def _smoke_task():
        print("SMOKE: test task executed")

    sched.register_task("test.smoke", _smoke_task)
    sched.schedule_interval("test.smoke", 2, job_id="test_smoke_job", start_immediately=True)

    print("Starting UnifiedScheduler for ~6 seconds...")
    sched.start()
    try:
        time.sleep(6)
    finally:
        sched.stop()
        print("Scheduler smoke run complete")


if __name__ == "__main__":
    main()
