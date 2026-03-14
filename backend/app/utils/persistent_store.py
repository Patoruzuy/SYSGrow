"""Small persistent JSON store helpers for lightweight temporal data.

Provides `load_json` / `save_json` helpers that store files under the
workspace `var/` directory. Also exposes convenience functions for
the growth last-run store used by `plant_grow_task`.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Directory for lightweight temporal files (persist across restarts)
_VAR_DIR = os.path.join(os.getcwd(), "var")
os.makedirs(_VAR_DIR, exist_ok=True)


def _path(name: str) -> str:
    return os.path.join(_VAR_DIR, name)


class FileLock:
    """Simple file-lock using a lockfile (cross-platform, advisory).

    Note: This is a lightweight lock suitable for single-writer or low-contention
    scenarios on a Raspberry Pi. It uses atomic creation of a .lock file and
    retries until timeout.
    """

    def __init__(self, lock_path: str, timeout: float = 5.0, retry: float = 0.05) -> None:
        self.lock_path = lock_path
        self.timeout = float(timeout)
        self.retry = float(retry)
        self._acquired = False

    def acquire(self) -> bool:
        start = time.time()
        while True:
            try:
                # O_EXCL ensures atomic creation; failing if exists
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.close(fd)
                self._acquired = True
                return True
            except FileExistsError:
                if (time.time() - start) >= self.timeout:
                    return False
                time.sleep(self.retry)

    def release(self) -> None:
        try:
            if self._acquired and os.path.exists(self.lock_path):
                os.unlink(self.lock_path)
        finally:
            self._acquired = False

    def __enter__(self):
        ok = self.acquire()
        if not ok:
            raise TimeoutError(f"Failed to acquire file lock: {self.lock_path}")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.release()


def load_json(name: str) -> Dict[str, Any]:
    path = _path(name)
    lock = path + ".lock"
    try:
        if not os.path.exists(path):
            return {}
        with FileLock(lock):
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh) or {}
    except Exception as e:
        logger.warning("Failed to load JSON store %s: %s", name, e)
        return {}


def save_json(name: str, data: Dict[str, Any]) -> None:
    path = _path(name)
    lock = path + ".lock"
    try:
        with FileLock(lock):
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, path)
    except Exception as e:
        logger.warning("Failed to save JSON store %s: %s", name, e)


# Convenience helpers for growth last-run store
GROWTH_LAST_RUN_FILE = "growth_last_run.json"


def load_growth_last_runs() -> Dict[str, str]:
    return load_json(GROWTH_LAST_RUN_FILE)


def save_growth_last_runs(data: Dict[str, str]) -> None:
    save_json(GROWTH_LAST_RUN_FILE, data)
