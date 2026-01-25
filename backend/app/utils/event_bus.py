"""
Lightweight EventBus singleton used across app/services/workers.

Key invariants (enforced by call sites + tests):
  - Event topics come from enums in app.enums.events (EventType).
  - Payloads are typed dataclasses / Pydantic models in app.schemas.events.
  - Subscribers always receive a plain dict payload.
"""
import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from enum import Enum
from queue import Full, Queue
from typing import Any, Callable, Dict, Hashable, Iterable, Optional

from app.config import load_config
from pydantic import BaseModel

from app.enums.events import EventType

# Drop warning configuration
_DROP_WARNING_THRESHOLD = 10  # Log summary every N drops
_DROP_WARNING_INTERVAL_SECONDS = 60  # Minimum seconds between drop summaries


class EventBus:
    """
    Handles event-driven communication across modules.

    Singleton so publishers/subscribers share the same routing table.
    """

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventBus":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super(EventBus, cls).__new__(cls)
                    instance.subscribers = defaultdict(list)
                    instance._queue_size = load_config().eventbus_queue_size
                    instance._queue = Queue(maxsize=instance._queue_size)
                    instance._worker_pool_size = load_config().eventbus_worker_count
                    instance._workers_started = False
                    instance._dropped_events = 0
                    instance._drops_by_event: Dict[str, int] = defaultdict(int)
                    instance._drops_since_last_warning = 0
                    instance._last_drop_warning_time = 0.0
                    cls._instance = instance
        return cls._instance

    def __init__(self) -> None:
        """
        Initializes the EventBus if not already initialized.
        """
        if not hasattr(self, "subscribers"):
            self.subscribers: Dict[Hashable, list[Callable[[Any], None]]] = defaultdict(list)
        self.lock = threading.Lock()
        if not getattr(self, "_workers_started", False):
            self._start_workers()

    def _start_workers(self) -> None:
        """Spin up a small worker pool to avoid unbounded thread creation."""
        with self.lock:
            if getattr(self, "_workers_started", False):
                return
            self._workers: list[threading.Thread] = []
            for _ in range(self._worker_pool_size):
                worker = threading.Thread(target=self._worker_loop, daemon=True)
                worker.start()
                self._workers.append(worker)
            self._workers_started = True
            logging.info(
                "EventBus workers started (pool=%s queue=%s)",
                self._worker_pool_size,
                self._queue_size,
            )

    def subscribe(self, event_name: EventType | str, callback: Callable[[Any], None]) -> Callable[[], None]:
        """
        Subscribes a callback function to an event.

        Args:
            event_name: The enum topic (preferred) or raw string.
            callback: Function to call when the event occurs.
        """
        name = event_name.value if isinstance(event_name, Enum) else event_name
        with self.lock:
            if name not in self.subscribers:
                self.subscribers[name] = []
            self.subscribers[name].append(callback)

        def unsubscribe() -> None:
            with self.lock:
                callbacks = self.subscribers.get(name, [])
                try:
                    callbacks.remove(callback)
                except ValueError:
                    return

        return unsubscribe

    def _worker_loop(self) -> None:
        """Worker thread loop to process events from the queue."""
        while True:
            event_name, callback, payload = self._queue.get()
            try:
                callback(payload)
            except Exception as exc:  # pragma: no cover - defensive
                logging.error("Error in callback for event %s: %s", event_name, exc)
            finally:
                self._queue.task_done()

    def publish(self, event_name: EventType | str, data: Any | None = None) -> None:
        """
        Publishes an event, calling all subscribed callback functions.

        Args:
            event_name: The enum topic (preferred) or raw string.
            data: Payload object (Pydantic model, dataclass, or dict/primitive).
        """
        name = event_name.value if isinstance(event_name, Enum) else event_name

        # Normalize payload for subscribers: they always receive a dict or primitive.
        if isinstance(data, BaseModel):
            payload: Any = data.model_dump()
        elif is_dataclass(data):
            payload = asdict(data)
        else:
            payload = data

        with self.lock:
            callbacks: Iterable[Callable[[Any], None]] = self.subscribers.get(name, [])
            callbacks = list(callbacks)
        for callback in callbacks:
            try:
                self._queue.put_nowait((name, callback, payload))
            except Full:
                self._record_drop(name)
                break

    def _record_drop(self, event_name: str) -> None:
        """Record a dropped event and log periodic warnings."""
        self._dropped_events += 1
        self._drops_by_event[event_name] += 1
        self._drops_since_last_warning += 1

        # Check if we should log a summary warning
        now = time.time()
        should_warn = (
            self._drops_since_last_warning >= _DROP_WARNING_THRESHOLD
            and (now - self._last_drop_warning_time) >= _DROP_WARNING_INTERVAL_SECONDS
        )

        if should_warn:
            # Build summary of top dropped events
            top_drops = sorted(
                self._drops_by_event.items(), key=lambda x: x[1], reverse=True
            )[:5]
            top_drops_str = ", ".join(f"{k}:{v}" for k, v in top_drops)

            logging.warning(
                "EventBus dropping events! queue_size=%d, total_dropped=%d, "
                "recent_drops=%d, top_dropped_events=[%s]. "
                "Consider increasing SYSGROW_EVENTBUS_QUEUE_SIZE or reducing event volume.",
                self._queue_size,
                self._dropped_events,
                self._drops_since_last_warning,
                top_drops_str,
            )
            self._drops_since_last_warning = 0
            self._last_drop_warning_time = now

    def listener(self, event_name: EventType | str) -> Callable[[Callable[[Any], None]], Callable[[Any], None]]:
        """
        Decorator for subscribing a function to an event at definition time.

        Args:
            event_name: The enum topic (preferred) or raw string.
        """

        def decorator(func: Callable[[Any], None]) -> Callable[[Any], None]:
            self.subscribe(event_name, func)
            return func

        return decorator

    def get_metrics(self) -> Dict[str, Any]:
        """Return lightweight metrics for health endpoints/logging."""
        try:
            queue_depth = self._queue.qsize()
        except Exception:
            queue_depth = 0

        # Get top 5 dropped event types for diagnostics
        drops_by_event = getattr(self, "_drops_by_event", {})
        top_dropped = dict(
            sorted(drops_by_event.items(), key=lambda x: x[1], reverse=True)[:5]
        )

        return {
            "queue_depth": queue_depth,
            "queue_size": getattr(self, "_queue_size", 0),
            "dropped_events": getattr(self, "_dropped_events", 0),
            "drops_by_event_top5": top_dropped,
            "subscribers": sum(len(values) for values in self.subscribers.values()),
            "is_dropping": getattr(self, "_drops_since_last_warning", 0) > 0,
        }

    def get_instance(self) -> "EventBus":
        """Get the singleton instance of the EventBus."""
        return self._instance if self._instance else self