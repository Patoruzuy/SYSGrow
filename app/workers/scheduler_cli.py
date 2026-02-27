from __future__ import annotations

import argparse
import logging
import time

from app.config import load_config, setup_logging
from app.services.container import ServiceContainer

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Run the UnifiedScheduler loop without starting the web server."""
    parser = argparse.ArgumentParser(prog="sysgrow-scheduler")
    parser.add_argument(
        "--start-coordinator",
        action="store_true",
        help="Start the DeviceCoordinator event loop (default: off)",
    )
    args = parser.parse_args(argv)

    config = load_config()
    setup_logging(debug=config.DEBUG)

    container = ServiceContainer.build(config, start_coordinator=args.start_coordinator)
    logger.info("Scheduler running (press Ctrl+C to stop)")

    # If running with no additional commands, just run the scheduler loop
    if not hasattr(args, "command") or args.command is None:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping scheduler...")
        finally:
            try:
                container.shutdown()
            except (RuntimeError, OSError, AttributeError, TypeError):
                logger.exception("Failed to shut down scheduler cleanly")
                return 1
        return 0

    # Support CLI helpers to inspect/manage lightweight var JSON files
    from app.utils.persistent_store import _VAR_DIR, load_json, save_json

    if args.command == "list-json":
        files = [f for f in sorted(__import__("os").listdir(_VAR_DIR)) if f.endswith(".json")]
        for f in files:
            print(f)
        return 0

    if args.command == "show-json":
        if not args.key:
            print("Please specify a filename (e.g. growth_last_run.json)")
            return 2
        data = load_json(args.key)
        import json as _json

        print(_json.dumps(data, indent=2))
        return 0

    if args.command == "delete-json":
        if not args.key:
            print("Please specify a filename to delete")
            return 2
        path = __import__("os").path.join(_VAR_DIR, args.key)
        try:
            __import__("os").remove(path)
            print(f"Deleted {args.key}")
        except FileNotFoundError:
            print("File not found")
            return 2
        return 0

    if args.command == "set-json":
        if not args.key or not args.value:
            print("Please specify filename and JSON value")
            return 2
        import json as _json

        try:
            obj = _json.loads(args.value)
            save_json(args.key, obj)
            print(f"Saved {args.key}")
            return 0
        except (_json.JSONDecodeError, OSError, TypeError, ValueError) as e:
            print(f"Failed to write JSON: {e}")
            return 2

    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(main(sys.argv[1:]))
