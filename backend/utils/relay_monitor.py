# relay_monitor.py
import logging
import json
import redis
from utils.event_bus import EventBus

class RelayStatusMonitor:
    """
    Monitors relay status updates from ESP32-C6 modules using Redis.
    Publishes state changes via EventBus for UI or automation triggers.
    """

    def __init__(self, redis_host="localhost", redis_port=6379):
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.event_bus = EventBus()

    def get_all_relay_statuses(self):
        """
        Reads all relay module statuses from Redis. Relay keys are expected to follow:
        unit:<unit_id>:modules:<device_id>:relays

        Returns:
            dict: { unit_id: [ { relay info }, ... ] }
        """
        keys = self.redis_client.keys("unit:*:modules:*:relays")
        relay_data = {}

        for key in keys:
            try:
                parts = key.split(":")
                unit_id = parts[1]
                module_id = parts[3]
                relays_json = self.redis_client.get(key)
                relays = json.loads(relays_json)

                if unit_id not in relay_data:
                    relay_data[unit_id] = []

                for relay in relays:
                    relay["module_id"] = module_id
                    relay_data[unit_id].append(relay)

                    # Publish status
                    self.event_bus.publish("relay_status_update", {
                        "unit_id": unit_id,
                        "module_id": module_id,
                        "relay_id": relay.get("relay_id"),
                        "state": relay.get("state")
                    })

            except Exception as e:
                logging.error(f"Failed to parse relay status for key {key}: {e}")
                continue

        return relay_data

    def get_status_by_unit(self, unit_id):
        """
        Returns relay status for a single unit.

        Args:
            unit_id (str): Unit identifier

        Returns:
            list: List of relay states and metadata for the unit
        """
        pattern = f"unit:{unit_id}:modules:*:relays"
        keys = self.redis_client.keys(pattern)
        statuses = []
        for key in keys:
            try:
                relays = json.loads(self.redis_client.get(key))
                statuses.extend(relays)
            except Exception as e:
                logging.warning(f"Error retrieving relays for key {key}: {e}")
        return statuses
