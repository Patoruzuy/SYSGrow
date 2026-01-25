"""
    This module provides an EventBus class for handling event-driven communication across modules.
    It allows subscribing to events with callback functions and publishing events to notify subscribers.
    Classes:
        EventBus: A singleton class that manages event subscriptions and publishing.
    Methods:
        subscribe(event_name, callback):
        publish(event_name, data=None):

"""
from collections import defaultdict
import threading
import logging

class EventBus:
    """
    Handles event-driven communication across modules.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EventBus, cls).__new__(cls)
                    cls._instance.subscribers = defaultdict(list)
        return cls._instance

    def __init__(self):
        """
        Initializes the EventBus.
        """
        if not hasattr(self, 'subscribers'):
            self.subscribers = defaultdict(list)
        self.lock = threading.Lock()

    def subscribe(self, event_name, callback):
        """
        Subscribes a callback function to an event.

        Args:
            event_name (str): The name of the event to subscribe to.
            callback (callable): The function to be called when the event occurs.
        """
        with self.lock:
            if event_name not in self.subscribers:
                self.subscribers[event_name] = []
            self.subscribers[event_name].append(callback)

    def publish(self, event_name, data=None):
        """
        Publishes an event, calling all subscribed callback functions.

        Args:
            event_name (str): The name of the event to publish.
            data (any, optional): Data to be passed to the callback functions.
        """
        with self.lock:
            if event_name in self.subscribers:
                for callback in self.subscribers[event_name]:
                    try:
                        threading.Thread(target=callback, args=(data,)).start()
                    except Exception as e:
                        logging.error(f"Error in callback for event {event_name}: {e}")
