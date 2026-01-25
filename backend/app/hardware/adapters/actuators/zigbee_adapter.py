"""
Zigbee Actuator Adapter

Adapter for Zigbee2MQTT actuators.
"""
import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional

from app.utils.event_bus import EventBus

logger = logging.getLogger(__name__)


class ZigbeeActuatorAdapter:
    """
    Zigbee2MQTT protocol adapter for actuators.
    
    Uses MQTT with Zigbee-specific topic format.
    Handles all device-level operations for Zigbee actuators.
    """
    
    def __init__(
        self,
        device_name: str,
        mqtt_client: Any,
        zigbee_id: str,
        topic: str,
        event_bus: Optional[EventBus] = None,
        ieee_address: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize Zigbee adapter.
        
        Args:
            device_name: Name of actuator (friendly name)
            mqtt_client: MQTT client instance
            zigbee_id: Zigbee device ID
            topic: MQTT topic (zigbee2mqtt/{id}/set)
            event_bus: Event bus for events
            ieee_address: IEEE address of the Zigbee device
        """
        self.device_name = device_name
        self.mqtt_client = mqtt_client
        self.zigbee_id = zigbee_id
        self.topic = topic
        self.event_bus = event_bus or EventBus()
        self.ieee_address = ieee_address
        
        # Bridge topic for device operations
        self._bridge_topic = "zigbee2mqtt"
        
        # State tracking
        self._current_state: Optional[str] = None
        self._last_state_update: Optional[datetime] = None
        self._available = True
    
    def turn_on(self):
        """Turn actuator ON via Zigbee2MQTT"""
        payload = json.dumps({"state": "ON"})
        self.mqtt_client.publish(self.topic, payload)
        logger.info(f"Zigbee: Turned ON {self.device_name} ({self.zigbee_id})")
    
    def turn_off(self):
        """Turn actuator OFF via Zigbee2MQTT"""
        payload = json.dumps({"state": "OFF"})
        self.mqtt_client.publish(self.topic, payload)
        logger.info(f"Zigbee: Turned OFF {self.device_name} ({self.zigbee_id})")
    
    def set_level(self, value: float):
        """
        Set actuator level via Zigbee2MQTT.
        
        Args:
            value: Level from 0-100
        """
        payload = json.dumps({
            "state": "ON" if value > 0 else "OFF",
            "brightness": int(value * 2.55)  # Convert 0-100 to 0-255
        })
        self.mqtt_client.publish(self.topic, payload)
        logger.info(f"Zigbee: Set {self.device_name} to {value}% ({self.zigbee_id})")

    def send_command(self, command: dict) -> bool:
        """
        Send arbitrary command to Zigbee2MQTT device.
        
        Args:
            command: Command dictionary (e.g., {'state': 'ON', 'brightness': 100})
            
        Returns:
            True if command was sent successfully
        """
        try:
            payload = json.dumps(command)
            self.mqtt_client.publish(self.topic, payload)
            logger.debug(f"Zigbee: Sent command to {self.device_name}: {command}")
            return True
        except Exception as e:
            logger.error(f"Zigbee: Failed to send command to {self.device_name}: {e}")
            return False
    
    def get_device(self) -> str:
        """Get device identifier"""
        return f"zigbee://{self.zigbee_id}"

    # ==================== Device Operations ====================

    def identify(self, duration: int = 10) -> bool:
        """
        Trigger device identification (e.g., flash LED).
        
        Args:
            duration: Identification duration in seconds
            
        Returns:
            True if command sent successfully
        """
        return self.send_command({"identify": duration})

    def get_state(self) -> Dict[str, Any]:
        """
        Get current device state.
        
        Returns:
            Dictionary with current state and metadata
        """
        return {
            "device_name": self.device_name,
            "zigbee_id": self.zigbee_id,
            "ieee_address": self.ieee_address,
            "current_state": self._current_state,
            "available": self._available,
            "last_update": self._last_state_update.isoformat() if self._last_state_update else None,
        }

    def update_state(self, state_data: Dict[str, Any]) -> None:
        """
        Update cached state from MQTT message.
        
        Called when state update is received from Zigbee2MQTT.
        
        Args:
            state_data: State dictionary from Zigbee2MQTT
        """
        if 'state' in state_data:
            self._current_state = state_data['state']
        self._last_state_update = datetime.now()
        
        # Check availability
        if 'availability' in state_data:
            self._available = state_data['availability'] == 'online'

    def get_device_info(self) -> Dict[str, Any]:
        """
        Get device information and metadata.
        
        Returns:
            Dictionary with device info
        """
        return {
            "device_name": self.device_name,
            "zigbee_id": self.zigbee_id,
            "ieee_address": self.ieee_address,
            "topic": self.topic,
            "protocol": "Zigbee2MQTT",
            "available": self._available,
            "current_state": self._current_state,
            "last_update": self._last_state_update.isoformat() if self._last_state_update else None,
        }

    def rename(self, new_name: str) -> bool:
        """
        Rename device in Zigbee2MQTT.
        
        Sends a rename request to the Zigbee2MQTT bridge.
        
        Args:
            new_name: New friendly name for the device
            
        Returns:
            True if rename command was sent successfully
        """
        if not self.mqtt_client:
            logger.error("MQTT client not available for rename")
            return False
        
        # Use IEEE address if available, otherwise use current name
        device_id = self.ieee_address or self.device_name
        
        payload = {
            "from": device_id,
            "to": new_name,
            "homeassistant_rename": False
        }
        
        try:
            topic = f"{self._bridge_topic}/bridge/request/device/rename"
            self.mqtt_client.publish(topic, json.dumps(payload))
            logger.info(f"Sent rename request for {device_id} -> {new_name}")
            
            # Update local state
            old_name = self.device_name
            self.device_name = new_name
            self.topic = f"zigbee2mqtt/{new_name}/set"
            
            logger.info(f"Updated adapter device_name: {old_name} -> {new_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rename device: {e}")
            return False

    def remove_from_network(self) -> bool:
        """
        Remove device from Zigbee network.
        
        Sends a remove request to the Zigbee2MQTT bridge.
        
        Returns:
            True if remove command was sent successfully
        """
        if not self.mqtt_client:
            logger.error("MQTT client not available for remove")
            return False
        
        device_id = self.ieee_address or self.device_name
        if not device_id:
            logger.error("No device identifier available for remove")
            return False
        
        payload = {"id": device_id}
        
        try:
            topic = f"{self._bridge_topic}/bridge/request/device/remove"
            self.mqtt_client.publish(topic, json.dumps(payload))
            logger.info(f"Sent remove request for device: {device_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove device: {e}")
            return False

    def is_available(self) -> bool:
        """
        Check if device is available/online.
        
        Returns:
            True if device is available
        """
        return self._available

    def cleanup(self) -> None:
        """
        Cleanup resources.
        
        Unsubscribes from MQTT topics if subscribed.
        Called when actuator is unregistered or deleted.
        """
        try:
            # Unsubscribe from state topic if we were subscribed
            state_topic = self.topic.replace('/set', '')
            if hasattr(self.mqtt_client, 'unsubscribe'):
                self.mqtt_client.unsubscribe(state_topic)
            logger.debug(f"Zigbee actuator {self.device_name} cleaned up")
        except Exception as e:
            logger.warning(f"Cleanup failed for Zigbee actuator {self.device_name}: {e}")
