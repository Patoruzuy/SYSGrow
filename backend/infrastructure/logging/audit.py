import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict
import sys


class WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """
    A RotatingFileHandler that works better on Windows by closing the file 
    handle before rotation and catching PermissionError exceptions.
    """
    def doRollover(self):
        """
        Do a rollover, as described in __init__().
        Close the log file and rotate it, handling Windows file locking issues.
        """
        if self.stream:
            self.stream.close()
            self.stream = None
        try:
            super().doRollover()
        except PermissionError:
            # On Windows, file may still be locked. Skip rotation and continue logging.
            pass
        finally:
            if not self.stream:
                self.stream = self._open()


class AuditLogger:
    """Structured audit logger that writes append-only records."""

    def __init__(self, log_path: str, level: str = "INFO") -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

        self.logger = logging.getLogger("sysgrow.audit")
        self.logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        self.logger.propagate = False

        # Check if handler already exists to avoid duplicate handlers
        if not any(isinstance(handler, (RotatingFileHandler, WindowsSafeRotatingFileHandler)) 
                   for handler in self.logger.handlers):
            # Use Windows-safe handler on Windows, regular handler elsewhere
            if sys.platform == 'win32':
                handler = WindowsSafeRotatingFileHandler(
                    filename=str(self.log_path),
                    maxBytes=10 * 1024 * 1024,  # 10 MB
                    backupCount=30,
                    encoding="utf-8",
                    delay=True  # Delay opening the file until first write
                )
            else:
                handler = RotatingFileHandler(
                    filename=str(self.log_path),
                    maxBytes=10 * 1024 * 1024,  # 10 MB
                    backupCount=30,
                    encoding="utf-8",
                )
            
            formatter = logging.Formatter(
                fmt="%(asctime)sZ | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_event(self, actor: str, action: str, resource: str, outcome: str, **metadata: Any) -> None:
        payload: Dict[str, Any] = {
            "actor": actor,
            "action": action,
            "resource": resource,
            "outcome": outcome,
        }
        if metadata:
            payload["meta"] = metadata

        self.logger.info(json.dumps(payload))
