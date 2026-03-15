# utils/event_bus.py
from collections import defaultdict
import threading

class EventBus:
    """Handles event-driven communication across modules."""
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EventBus, cls).__new__(cls)
                    cls._instance.subscribers = defaultdict(list)
        return cls._instance

    def subscribe(self, event_name, callback):
        """Registers a function to listen for an event."""
        self.subscribers[event_name].append(callback)

    def publish(self, event_name, data=None):
        """Broadcasts an event to all subscribers."""
        if event_name in self.subscribers:
            for callback in self.subscribers[event_name]:
                threading.Thread(target=callback, args=(data,)).start()
