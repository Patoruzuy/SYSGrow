"""
Quick helper to inspect a unit's thresholds/schedules via GrowthService to aid debugging.

Usage:
    python scripts/debug_thresholds_and_schedules.py --unit 2 --db database/sysgrow.db
"""
from __future__ import annotations

import argparse
from pprint import pprint

from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from infrastructure.database.repositories.growth import GrowthRepository
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.logging.audit import AuditLogger
from app.services.application.growth_service import GrowthService


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--unit", type=int, required=True, help="Unit ID to inspect")
    parser.add_argument("--db", default="database/sysgrow.db", help="Path to SQLite DB")
    args = parser.parse_args()

    handler = SQLiteDatabaseHandler(args.db)
    repo = GrowthRepository(handler)
    analytics_repo = AnalyticsRepository(handler)
    svc = GrowthService(growth_repo=repo, analytics_repo=analytics_repo, audit_logger=AuditLogger(log_path="logs/audit.log"))

    runtime = svc.get_unit_runtime(args.unit)
    print(f"Runtime present: {bool(runtime)}")
    if runtime:
        print("Runtime settings device_schedules type:", type(runtime.settings.device_schedules))
        print("Runtime settings device_schedules:", runtime.settings.device_schedules)
        print("Runtime thresholds:", {
            "temperature_threshold": runtime.settings.temperature_threshold,
            "humidity_threshold": runtime.settings.humidity_threshold,
            "soil_moisture_threshold": runtime.settings.soil_moisture_threshold,
        })

    print("\nDB row:")
    row = repo.get_unit(args.unit)
    pprint(dict(row) if row else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
