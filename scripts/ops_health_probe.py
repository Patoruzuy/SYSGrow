"""
Lightweight ops probe to pull health data for dashboards/alerts.

Usage:
    python scripts/ops_health_probe.py --base http://localhost:5000 --endpoint /status/ops
    python scripts/ops_health_probe.py --endpoint /api/dashboard/health

Outputs a compact summary plus the raw JSON for inspection.
"""
import argparse
import json
import sys
from urllib.error import URLError, HTTPError
from urllib.request import urlopen


def fetch_json(url: str) -> dict:
    with urlopen(url, timeout=5) as resp:  # noqa: S310 - controlled URL from args
        return json.loads(resp.read().decode("utf-8"))


def summarize_ops(payload: dict) -> list[str]:
    lines = []
    event_bus = payload.get("event_bus", {})
    lines.append(f"event_bus.queue_depth={event_bus.get('queue_depth', 0)}")
    lines.append(f"event_bus.dropped_events={event_bus.get('dropped_events', 0)}")
    units = payload.get("units", {})
    for unit_id, metrics in units.items():
        polling = metrics.get("polling", {})
        controller = metrics.get("controller", {})
        lines.append(
            f"unit={unit_id} polling.backoff_count={polling.get('backoff_count', 0)} "
            f"pending_coalesced={polling.get('pending_coalesced', 0)} "
            f"queue_depth={polling.get('queue_depth', 0)} "
            f"dropped_events={polling.get('dropped_events', 0)} "
            f"mqtt_seen={polling.get('last_seen_count', 0)} "
            f"controller.stale_sensors={controller.get('stale_sensors', 0)}"
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe SYSGrow health endpoints for ops dashboards.")
    parser.add_argument("--base", default="http://localhost:5000", help="Base URL of the SYSGrow backend")
    parser.add_argument(
        "--endpoint",
        default="/status/ops",
        choices=["/status/ops", "/status/polling", "/api/dashboard/health"],
        help="Endpoint to query",
    )
    args = parser.parse_args()

    url = args.base.rstrip("/") + args.endpoint
    try:
        payload = fetch_json(url)
    except HTTPError as exc:
        print(f"HTTP error {exc.code} when calling {url}: {exc.reason}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Failed to reach {url}: {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Unexpected error calling {url}: {exc}", file=sys.stderr)
        return 1

    if args.endpoint == "/status/ops":
        for line in summarize_ops(payload):
            print(line)
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
