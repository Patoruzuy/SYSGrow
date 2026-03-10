"""
Lightweight logger that polls /status/ops and appends a CSV-style line for later analysis.

Usage:
    python scripts/ops_health_logger.py --base http://localhost:5000 --interval 10 --out ops_health.log
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def fetch_json(url: str) -> Dict[str, Any]:
    with urlopen(url, timeout=5) as resp:  # noqa: S310 - controlled URL from args
        return json.loads(resp.read().decode("utf-8"))


def flatten_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    event_bus = payload.get("event_bus", {})
    row: Dict[str, Any] = {
        "ts": payload.get("timestamp") or datetime.datetime.now(datetime.UTC).isoformat() + "Z",
        "event_bus_queue_depth": event_bus.get("queue_depth", 0),
        "event_bus_dropped_events": event_bus.get("dropped_events", 0),
    }
    units = payload.get("units", {}) or {}
    for unit_id, metrics in units.items():
        polling = metrics.get("polling", {})
        controller = metrics.get("controller", {})
        row.update(
            {
                f"unit_{unit_id}_polling_backoff_count": polling.get("backoff_count", 0),
                f"unit_{unit_id}_polling_pending_coalesced": polling.get("pending_coalesced", 0),
                f"unit_{unit_id}_polling_queue_depth": polling.get("queue_depth", 0),
                f"unit_{unit_id}_polling_dropped_events": polling.get("dropped_events", 0),
                f"unit_{unit_id}_polling_mqtt_seen": polling.get("last_seen_count", 0),
                f"unit_{unit_id}_controller_stale_sensors": controller.get("stale_sensors", 0),
                f"unit_{unit_id}_controller_sensor_updates": controller.get("sensor_updates", 0),
            }
        )
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description="Log /status/ops snapshots to a CSV-style file.")
    parser.add_argument("--base", default="http://localhost:5000", help="Base URL of the SYSGrow backend")
    parser.add_argument("--endpoint", default="/status/ops", help="Endpoint to query (default: /status/ops)")
    parser.add_argument("--interval", type=int, default=10, help="Polling interval in seconds")
    parser.add_argument("--out", default="ops_health.log", help="Output file (CSV-style)")
    args = parser.parse_args()

    url = args.base.rstrip("/") + args.endpoint
    outfile = Path(args.out)
    writer = None

    while True:
        try:
            payload = fetch_json(url)
            row = flatten_snapshot(payload)
            if writer is None:
                # Write header on first row
                writer = csv.DictWriter(outfile.open("a", newline=""), fieldnames=list(row.keys()))
                if outfile.stat().st_size == 0:
                    writer.writeheader()
            writer.writerow(row)
            outfile.flush()
            print(f"[{row['ts']}] logged queue_depth={row['event_bus_queue_depth']} dropped={row['event_bus_dropped_events']}")
        except HTTPError as exc:
            print(f"HTTP error {exc.code} calling {url}: {exc.reason}", file=sys.stderr)
        except URLError as exc:
            print(f"Failed to reach {url}: {exc.reason}", file=sys.stderr)
        except Exception as exc:  # pragma: no cover - defensive
            print(f"Unexpected error: {exc}", file=sys.stderr)
        time.sleep(max(1, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())
