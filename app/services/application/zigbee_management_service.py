"""
Zigbee Management Service

Unified service for managing all Zigbee2MQTT operations including:
- Device discovery (sensors, actuators, all device types)
- Capability detection (power monitoring, switching, sensing)
- Device control (commands, state monitoring)
- Bridge management (permit join, rename, remove, health checks)
"""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

from app.hardware.mqtt.mqtt_broker_wrapper import MQTTClientWrapper
from app.utils.time import iso_now

logger = logging.getLogger(__name__)


@dataclass
class DeviceCapability:
    """Capability/feature of a Zigbee2MQTT device"""
    name: str
    type: str  # 'binary', 'numeric', 'enum', 'composite'
    access: int  # Bitfield: 1=read, 2=write, 4=report
    property: str  # MQTT property name
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_step: Optional[float] = None
    values: Optional[List[str]] = None  # For enum
    unit: Optional[str] = None
    
    @property
    def is_readable(self) -> bool:
        return bool(self.access & 1)
    
    @property
    def is_writable(self) -> bool:
        return bool(self.access & 2)
    
    @property
    def is_reportable(self) -> bool:
        return bool(self.access & 4)


@dataclass
class DiscoveredDevice:
    """Discovered Zigbee2MQTT device (sensor or actuator)"""
    ieee_address: str
    friendly_name: str
    model: str
    vendor: str
    description: str
    device_type: str  # 'switch', 'light', 'plug', 'sensor', 'combo_sensor', etc.
    capabilities: List[DeviceCapability]
    supports_power_monitoring: bool
    power_capabilities: Dict[str, DeviceCapability]
    endpoints: List[int]
    discovered_at: datetime
    
    @property
    def is_sensor(self) -> bool:
        """Check if device is a sensor"""
        return 'sensor' in self.device_type.lower()
    
    @property
    def is_actuator(self) -> bool:
        """Check if device is an actuator (switch, light, plug, etc.)"""
        return self.device_type in ['switch', 'light', 'plug', 'dimmer', 'valve', 'cover']
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'ieee_address': self.ieee_address,
            'friendly_name': self.friendly_name,
            'model': self.model,
            'vendor': self.vendor,
            'description': self.description,
            'device_type': self.device_type,
            'is_sensor': self.is_sensor,
            'is_actuator': self.is_actuator,
            'supports_power_monitoring': self.supports_power_monitoring,
            'endpoints': self.endpoints,
            'discovered_at': self.discovered_at.isoformat(),
            'capabilities': [
                {
                    'name': cap.name,
                    'type': cap.type,
                    'property': cap.property,
                    'access': cap.access,
                    'readable': cap.is_readable,
                    'writable': cap.is_writable
                }
                for cap in self.capabilities
            ]
        }


class ZigbeeManagementService:
    """
    Unified service for all Zigbee2MQTT operations.
    
    Features:
    - Device discovery (sensors and actuators)
    - Capability detection and parsing
    - Device state monitoring
    - Device control (commands)
    - Bridge management (permit join, rename, remove, health)
    - Automatic device registration callbacks
    """
    
    def __init__(self, mqtt_client: Any, bridge_topic: str = "zigbee2mqtt"):
        """
        Initialize Zigbee management service.
        
        Args:
            mqtt_client: MQTT client (MQTTClientWrapper or paho.mqtt.client.Client)
            bridge_topic: Base MQTT topic for Zigbee2MQTT bridge
        """
        self._mqtt_wrapper: Optional[MQTTClientWrapper] = mqtt_client if isinstance(mqtt_client, MQTTClientWrapper) else None
        self.client = mqtt_client.client if isinstance(mqtt_client, MQTTClientWrapper) else mqtt_client
        self.bridge_topic = bridge_topic
        
        # Storage
        self.discovered_devices: Dict[str, DiscoveredDevice] = {}  # ieee -> device
        self.device_states: Dict[str, Dict[str, Any]] = {}  # friendly_name -> state
        self.last_health: Optional[Dict] = None
        self.last_rename_response: Optional[Dict] = None
        
        # Callbacks
        self.discovery_callbacks: List[Callable[[DiscoveredDevice], None]] = []
        self.state_callbacks: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        
        # Synchronization events
        self._devices_event = threading.Event()
        self._health_event = threading.Event()
        self._rename_event = threading.Event()
        
        # Track which devices we've already announced to avoid log spam
        self._announced_devices: set[str] = set()  # ieee addresses
        
        # Debounce bridge info messages
        self._last_bridge_info_time: float = 0
        
        # Subscribe to all Zigbee2MQTT topics
        self._subscribe_to_topics()

        self.is_online = self._get_bridge_state()
        
        logger.info("Zigbee Management Service initialized")
    
    def _subscribe_to_topics(self) -> None:
        """Subscribe to all Zigbee2MQTT topics"""
        if not self.client:
            logger.warning("No MQTT client available for Zigbee2MQTT")
            return
        
        topics = [
            f"{self.bridge_topic}/bridge/devices",      # Device list
            f"{self.bridge_topic}/bridge/info",         # Bridge info
            f"{self.bridge_topic}/bridge/event",        # Events (join, leave)
            f"{self.bridge_topic}/bridge/health",       # Bridge health
            f"{self.bridge_topic}/bridge/response/device/rename/#",  # Rename responses
            f"{self.bridge_topic}/+",                   # All device messages
            f"{self.bridge_topic}/+/state",             # Device states
        ]
        
        try:
            if self._mqtt_wrapper:
                for topic in topics:
                    self._mqtt_wrapper.subscribe(topic, self._on_message)
            else:
                self.client.on_message = self._on_message
                for topic in topics:
                    self.client.subscribe(topic)
            
            logger.info(f"Subscribed to {len(topics)} Zigbee2MQTT topics")
        except Exception as e:
            logger.warning(f"Failed to subscribe to Zigbee2MQTT topics: {e}")

    def _get_bridge_state(self) -> Optional[str]:
        """Get current bridge state
        
        Returns:
            Bridge state string or None if unavailable
            """
        if not self.client:
            return None
        
        try:
            topic = f"{self.bridge_topic}/bridge/state"
            self.client.publish(topic, "")  # Request state
            self._health_event.wait(timeout=5)
            if self.last_health and self.last_health.get('state') == 'online':
                 return True
        except Exception as e:
            logger.error(f"Error getting bridge state: {e}", exc_info=True)
        
        return None
    
    def _on_message(self, client, userdata, msg) -> None:
        """Handle all incoming MQTT messages"""
        try:
            topic = msg.topic
            payload_raw = msg.payload.decode() if msg.payload else ""
            
            # Bridge devices list
            if topic == f"{self.bridge_topic}/bridge/devices":
                self._handle_devices_message(payload_raw)
            
            # Bridge info
            elif topic == f"{self.bridge_topic}/bridge/info":
                self._handle_info_message(payload_raw)
            
            # Bridge events (device join/leave)
            elif topic == f"{self.bridge_topic}/bridge/event":
                self._handle_event_message(payload_raw)
            
            # Bridge health
            elif topic == f"{self.bridge_topic}/bridge/health":
                self._handle_health_message(payload_raw)
            
            # Rename responses
            elif topic.startswith(f"{self.bridge_topic}/bridge/response/device/rename"):
                self._handle_rename_response(payload_raw)
            
            # Skip availability messages (these are just "online"/"offline" strings)
            elif topic.endswith('/availability'):
                # Don't process - these are simple string messages, not JSON
                pass
            
            # Device state messages
            elif topic.endswith('/state'):
                parts = topic.split('/')
                if len(parts) >= 2:
                    friendly_name = parts[1]
                    self._handle_state_message(friendly_name, payload_raw)
            
            # General device messages (includes power monitoring)
            elif topic.startswith(self.bridge_topic) and '/' in topic:
                parts = topic.split('/')
                if len(parts) >= 2 and parts[-1] not in ['state', 'set', 'get', 'bridge', 'availability']:
                    friendly_name = parts[1]
                    self._handle_device_message(friendly_name, payload_raw)
        
        except Exception as e:
            logger.error(f"Error handling MQTT message: {e}")
    
    def _handle_devices_message(self, payload: str) -> None:
        """Handle bridge/devices message - receiving this indicates bridge is online"""
        try:
            data = json.loads(payload)

            # Devices message means bridge is online
            self.is_online = True

            if isinstance(data, list):
                new_devices = 0
                for device_data in data:
                    ieee = device_data.get('ieee_address')
                    if ieee and ieee not in self.discovered_devices:
                        new_devices += 1
                    self._process_device(device_data)

                self._devices_event.set()

                # Only log if there are new devices or this is first run
                if new_devices > 0:
                    logger.info(f"Zigbee2MQTT: {len(self.discovered_devices)} devices total, {new_devices} new")
                elif len(self.discovered_devices) == len(data) and not self._announced_devices:
                    # First run - log once
                    logger.info(f"Zigbee2MQTT: {len(self.discovered_devices)} devices discovered")
                else:
                    logger.debug(f"Zigbee2MQTT: {len(self.discovered_devices)} devices (no changes)")

        except Exception as e:
            logger.error(f"Error processing devices message: {e}")
    
    def _handle_info_message(self, payload: str) -> None:
        """Handle bridge/info message - receiving this indicates bridge is online"""
        try:
            import time
            data = json.loads(payload)

            # Bridge info message means bridge is online
            self.is_online = True

            # Debounce: only log once per 60 seconds
            now = time.time()
            if now - self._last_bridge_info_time < 60:
                return

            self._last_bridge_info_time = now
            logger.info(
                f"Zigbee2MQTT bridge: version={data.get('version')}, "
                f"coordinator={data.get('coordinator', {}).get('type')}"
            )
        except Exception as e:
            logger.error(f"Error processing info message: {e}")
    
    def _handle_event_message(self, payload: str) -> None:
        """Handle bridge/event message (device join/leave)"""
        try:
            event = json.loads(payload)
            event_type = event.get('type')
            
            if event_type == 'device_joined':
                device = event.get('data', {}).get('device', {})
                friendly_name = device.get('friendly_name')
                ieee = device.get('ieee_address')
                
                logger.info(f"New Zigbee2MQTT device joined: {friendly_name} ({ieee})")
                
                # Request full device list update
                self.request_device_list()
            
            elif event_type == 'device_leave':
                ieee = event.get('data', {}).get('ieee_address')
                if ieee in self.discovered_devices:
                    logger.info(f"Zigbee2MQTT device left: {ieee}")
                    del self.discovered_devices[ieee]
        
        except Exception as e:
            logger.error(f"Error processing event message: {e}")
    
    def _handle_health_message(self, payload: str) -> None:
        """Handle bridge/health message"""
        try:
            self.last_health = json.loads(payload) if payload else {}
            # Update is_online based on health status
            if self.last_health.get('status') == 'healthy':
                self.is_online = True
            self._health_event.set()
        except Exception:
            pass
    
    def _handle_rename_response(self, payload: str) -> None:
        """Handle device rename response"""
        try:
            self.last_rename_response = json.loads(payload) if payload else {}
            self._rename_event.set()
        except Exception:
            pass
    
    def _handle_state_message(self, friendly_name: str, payload: str) -> None:
        """Handle device state message"""
        try:
            # Skip empty or whitespace-only payloads
            if not payload or not payload.strip():
                logger.debug(f"Skipping empty state message for {friendly_name}")
                return
            
            # Skip non-JSON availability messages
            payload_stripped = payload.strip()
            if payload_stripped in ['online', 'offline', '']:
                logger.debug(f"Skipping availability message for {friendly_name}: {payload_stripped}")
                return
            
            data = json.loads(payload)
            self.device_states[friendly_name] = data
            
            # Trigger state callbacks
            if friendly_name in self.state_callbacks:
                for callback in self.state_callbacks[friendly_name]:
                    try:
                        callback(data)
                    except Exception as e:
                        logger.error(f"Error in state callback: {e}")
        
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in state message for {friendly_name}: {payload[:100]}... - {e}")
        except Exception as e:
            logger.error(f"Error processing state message for {friendly_name}: {e}")
    
    def _handle_device_message(self, friendly_name: str, payload: str) -> None:
        """Handle general device message (includes power monitoring)"""
        try:
            # Skip empty or whitespace-only payloads
            if not payload or not payload.strip():
                logger.debug(f"Skipping empty device message for {friendly_name}")
                return
            
            # Skip non-JSON availability messages
            payload_stripped = payload.strip()
            if payload_stripped in ['online', 'offline', '']:
                logger.debug(f"Skipping availability message for {friendly_name}: {payload_stripped}")
                return
            
            data = json.loads(payload)
            
            # Update device state with all data
            if friendly_name not in self.device_states:
                self.device_states[friendly_name] = {}
            
            self.device_states[friendly_name].update(data)
            
            # Log power monitoring data if present
            if any(key in data for key in ['power', 'voltage', 'current', 'energy']):
                logger.debug(
                    f"Power data for {friendly_name}: "
                    f"power={data.get('power')}W, "
                    f"voltage={data.get('voltage')}V, "
                    f"current={data.get('current')}A, "
                    f"energy={data.get('energy')}kWh"
                )
        
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in device message for {friendly_name}: {payload[:100]}... - {e}")
        except Exception as e:
            logger.error(f"Error processing device message for {friendly_name}: {e}")
    
    def _process_device(self, device_data: Dict[str, Any]) -> None:
        """Process and register discovered device"""
        try:
            ieee_address = device_data.get('ieee_address')
            if not ieee_address:
                return
            
            # Check if device already registered (prevent duplicates)
            is_new_device = ieee_address not in self.discovered_devices
            already_announced = ieee_address in self._announced_devices
            
            if not is_new_device:
                # Update existing device silently
                existing_device = self.discovered_devices[ieee_address]
                logger.debug(f"Device {ieee_address} already registered as '{existing_device.friendly_name}', skipping...")
                return  # Don't re-process or re-announce
            
            # Extract device info
            friendly_name = device_data.get('friendly_name', ieee_address)
            model_id = device_data.get('model_id') or device_data.get('definition', {}).get('model', 'unknown')
            manufacturer = device_data.get('manufacturer', 'unknown')
            description = device_data.get('description', '')
            definition = device_data.get('definition', {})
            
            # Parse capabilities
            capabilities = []
            power_capabilities = {}
            
            exposes = definition.get('exposes', [])
            for expose in exposes:
                caps = self._parse_capability(expose)
                for cap in caps:
                    capabilities.append(cap)
                    
                    # Check for power monitoring
                    if cap.property in ['power', 'voltage', 'current', 'energy']:
                        power_capabilities[cap.property] = cap
            
            # Determine device type
            device_type = self._detect_device_type(capabilities)
            
            # Check if supports power monitoring
            supports_power = bool(power_capabilities)
            
            # Get endpoints
            endpoints = device_data.get('endpoints', {})
            endpoint_ids = list(endpoints.keys()) if isinstance(endpoints, dict) else []
            
            # Create discovered device
            device = DiscoveredDevice(
                ieee_address=ieee_address,
                friendly_name=friendly_name,
                model=model_id,
                vendor=manufacturer,
                description=description,
                device_type=device_type,
                capabilities=capabilities,
                supports_power_monitoring=supports_power,
                power_capabilities=power_capabilities,
                endpoints=endpoint_ids,
                discovered_at=datetime.now()
            )
            
            self.discovered_devices[ieee_address] = device
            
            # Only log if this is the first time we're announcing this device
            if not already_announced:
                logger.info(
                    f"Discovered Zigbee2MQTT device: {friendly_name} "
                    f"(type={device_type}, sensor={device.is_sensor}, "
                    f"actuator={device.is_actuator}, power={supports_power})"
                )
                self._announced_devices.add(ieee_address)
            
            # Trigger discovery callbacks only for new devices
            if is_new_device:
                for callback in self.discovery_callbacks:
                    try:
                        callback(device)
                    except Exception as e:
                        logger.error(f"Error in discovery callback: {e}")
        
        except Exception as e:
            logger.error(f"Error processing device: {e}")
    
    def _parse_capability(self, expose: Dict[str, Any]) -> List[DeviceCapability]:
        """Parse capability from expose definition"""
        capabilities = []
        
        try:
            feature_type = expose.get('type')
            
            # Handle composite types (light, switch with features)
            if feature_type in ['composite', 'light', 'switch', 'climate']:
                features = expose.get('features', [])
                for feature in features:
                    caps = self._parse_capability(feature)
                    capabilities.extend(caps)
                return capabilities
            
            # Handle simple types
            if feature_type == 'binary':
                capabilities.append(DeviceCapability(
                    name=expose.get('name', 'unknown'),
                    type='binary',
                    access=expose.get('access', 7),
                    property=expose.get('property', expose.get('name', 'unknown')),
                    values=[expose.get('value_off'), expose.get('value_on')]
                ))
            
            elif feature_type == 'numeric':
                capabilities.append(DeviceCapability(
                    name=expose.get('name', 'unknown'),
                    type='numeric',
                    access=expose.get('access', 7),
                    property=expose.get('property', expose.get('name', 'unknown')),
                    value_min=expose.get('value_min'),
                    value_max=expose.get('value_max'),
                    value_step=expose.get('value_step'),
                    unit=expose.get('unit')
                ))
            
            elif feature_type == 'enum':
                capabilities.append(DeviceCapability(
                    name=expose.get('name', 'unknown'),
                    type='enum',
                    access=expose.get('access', 7),
                    property=expose.get('property', expose.get('name', 'unknown')),
                    values=expose.get('values', [])
                ))
        
        except Exception as e:
            logger.error(f"Error parsing capability: {e}")
        
        return capabilities
    
    def _detect_device_type(self, capabilities: List[DeviceCapability]) -> str:
        """Detect device type from capabilities"""
        cap_props = {cap.property.lower() for cap in capabilities}
        cap_names = {cap.name.lower() for cap in capabilities}
        
        # Check for actuators (writable devices)
        writable_caps = [cap for cap in capabilities if cap.is_writable]
        
        if 'brightness' in cap_props or 'color' in cap_props or 'color_temp' in cap_props:
            return 'light'
        elif 'state' in cap_props and writable_caps:
            # Has writable state = actuator
            if any(p in cap_props for p in ['power', 'voltage', 'current', 'energy']):
                return 'plug'  # Smart plug with power monitoring
            return 'switch'
        elif 'position' in cap_props:
            return 'cover'
        
        # Check for sensors (read-only devices or devices with sensor capabilities)
        has_temp = any(p in cap_props for p in ['temperature', 'temp'])
        has_humidity = any(p in cap_props for p in ['humidity', 'relative_humidity'])
        has_soil = any(p in cap_props for p in ['soil_moisture', 'moisture'])
        has_light = any(p in cap_props for p in ['illuminance', 'illuminance_lux', 'lux'])
        has_pressure = 'pressure' in cap_props
        has_co2 = any(p in cap_props for p in ['co2', 'voc', 'eco2'])
        
        sensor_count = sum([has_temp, has_humidity, has_soil, has_light, has_pressure, has_co2])
        
        if sensor_count >= 3:
            return 'combo_sensor'  # Multi-sensor (4-in-1, 3-in-1)
        elif has_soil:
            return 'soil_moisture_sensor'
        elif has_light:
            return 'light_sensor'
        elif has_temp and has_humidity:
            return 'temp_humidity_sensor'
        elif has_temp:
            return 'temperature_sensor'
        elif has_humidity:
            return 'humidity_sensor'
        elif has_co2:
            return 'air_quality_sensor'
        elif has_pressure:
            return 'pressure_sensor'
        
        return 'unknown'
    
    # Public API Methods
    
    def register_discovery_callback(self, callback: Callable[[DiscoveredDevice], None]) -> None:
        """Register callback for device discovery"""
        self.discovery_callbacks.append(callback)
        logger.info("Registered discovery callback")
    
    def force_rediscovery(self) -> None:
        """Force a complete rediscovery of all devices (clears cache and triggers callbacks)"""
        logger.info("Forcing Zigbee device rediscovery...")
        self._announced_devices.clear()
        old_devices = self.discovered_devices.copy()
        self.discovered_devices.clear()
        
        # Request fresh device list from bridge
        self.client.publish(f"{self.bridge_topic}/bridge/config/devices/get", "")
        
        logger.info(f"Rediscovery initiated (cleared {len(old_devices)} cached devices)")
    
    def register_state_callback(
        self,
        friendly_name: str,
        callback: Callable[[Dict[str, Any]], None]
    ) -> None:
        """Register callback for device state updates"""
        if friendly_name not in self.state_callbacks:
            self.state_callbacks[friendly_name] = []
        self.state_callbacks[friendly_name].append(callback)
    
    def get_discovered_devices(self) -> List[DiscoveredDevice]:
        """Get all discovered devices"""
        return list(self.discovered_devices.values())
    
    def get_sensors(self) -> List[DiscoveredDevice]:
        """Get only sensor devices"""
        return [dev for dev in self.discovered_devices.values() if dev.is_sensor]
    
    def get_actuators(self) -> List[DiscoveredDevice]:
        """Get only actuator devices"""
        return [dev for dev in self.discovered_devices.values() if dev.is_actuator]
    
    def get_device_by_ieee(self, ieee_address: str) -> Optional[DiscoveredDevice]:
        """Get device by IEEE address"""
        return self.discovered_devices.get(ieee_address)
    
    def get_device_by_friendly_name(self, friendly_name: str) -> Optional[DiscoveredDevice]:
        """Get device by friendly name"""
        for device in self.discovered_devices.values():
            if device.friendly_name == friendly_name:
                return device
        return None
    
    def get_device_state(self, friendly_name: str) -> Optional[Dict[str, Any]]:
        """Get current state of a device"""
        return self.device_states.get(friendly_name)
    
    def send_command(
        self,
        friendly_name: str,
        command: Dict[str, Any]
    ) -> bool:
        """
        Send command to a Zigbee2MQTT device.
        
        .. deprecated::
            Use adapter.send_command() via SensorManagementService or 
            ActuatorManagementService for registered devices. This method
            is retained for unregistered device fallback.
        
        Args:
            friendly_name: Device friendly name
            command: Command dictionary (e.g., {'state': 'ON'})
            
        Returns:
            True if command sent successfully
        """
        if not self.client:
            logger.error("No MQTT client available")
            return False
        
        try:
            topic = f"{self.bridge_topic}/{friendly_name}/set"
            payload = json.dumps(command)
            
            self.client.publish(topic, payload)
            logger.debug(f"Sent command to {friendly_name}: {command}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send command to {friendly_name}: {e}")
            return False
    
    def request_device_list(self) -> bool:
        """Request device list from Zigbee2MQTT bridge"""
        if not self.client:
            return False
        
        try:
            topic = f"{self.bridge_topic}/bridge/request/devices"
            self.client.publish(topic, "")
            logger.info("Requested device list from Zigbee2MQTT")
            return True
        
        except Exception as e:
            logger.error(f"Failed to request device list: {e}")
            return False
    
    def get_devices(self, timeout: float = 2.0) -> List[DiscoveredDevice]:
        """
        Request and return device list with timeout.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            List of discovered devices
        """
        self._devices_event.clear()
        self.request_device_list()
        self._devices_event.wait(timeout=timeout)
        return self.get_discovered_devices()
    
    def get_device_names(self, timeout: float = 2.0) -> List[str]:
        """Get list of device friendly names"""
        devices = self.get_devices(timeout=timeout)
        return [dev.friendly_name for dev in devices]
    
    def find_devices(self, timeout: float = 2.0) -> Dict[str, str]:
        """
        Return mapping of IEEE address -> friendly_name.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Dict mapping IEEE addresses to friendly names
        """
        devices = self.get_devices(timeout=timeout)
        return {dev.ieee_address: dev.friendly_name for dev in devices}
    
    def permit_device_join(self, time: int = 254, device_type: Optional[str] = None) -> bool:
        """
        Allow new Zigbee devices to join the network.
        
        Args:
            time: Time in seconds (default 254 = ~4 minutes)
            device_type: Optional device type filter
            
        Returns:
            True if command sent successfully
        """
        payload = {"time": time}
        if device_type:
            payload["device"] = device_type
        
        try:
            topic = f"{self.bridge_topic}/bridge/request/permit_join"
            result = self.client.publish(topic, json.dumps(payload))
            
            if hasattr(result, 'rc') and result.rc != 0:
                raise RuntimeError(f"MQTT publish failed with code {result.rc}")
            
            logger.info(f"Permit join enabled for {time} seconds")
            return True
        
        except Exception as e:
            logger.error(f"Failed to enable permit join: {e}")
            return False
    
    def get_bridge_health(self, timeout: float = 2.0) -> Optional[Dict]:
        """
        Get bridge health status.
        
        Args:
            timeout: Timeout in seconds
            
        Returns:
            Health status dict or None
        """
        self._health_event.clear()
        self.last_health = None
        
        try:
            topic = f"{self.bridge_topic}/bridge/request/health"
            self.client.publish(topic, "{}")
            self._health_event.wait(timeout=timeout)
            return self.last_health
        
        except Exception as e:
            logger.error(f"Failed to get bridge health: {e}")
            return None
    
    def rename_device(
        self,
        ieee_address: str,
        new_name: str,
        timeout: float = 3.0
    ) -> Dict[str, Any]:
        """
        Rename a Zigbee2MQTT device.
        
        Args:
            ieee_address: IEEE address of device
            new_name: New friendly name
            timeout: Timeout in seconds
            
        Returns:
            Response dict with status
            
        Raises:
            TimeoutError: If no response within timeout
        """
        payload = {
            "from": str(ieee_address),
            "to": str(new_name),
            "homeassistant_rename": False
        }
        
        self._rename_event.clear()
        self.last_rename_response = None
        
        try:
            topic = f"{self.bridge_topic}/bridge/request/device/rename"
            self.client.publish(topic, json.dumps(payload))
            
            response_received = self._rename_event.wait(timeout=timeout)
            
            if not response_received:
                raise TimeoutError(f"No rename response for {ieee_address} within {timeout}s")
            
            return self.last_rename_response or {}
        
        except Exception as e:
            logger.error(f"Failed to rename device: {e}")
            raise
    
    def remove_device(
        self,
        ieee_address: Optional[str] = None,
        friendly_name: Optional[str] = None
    ) -> bool:
        """
        Remove a device from the Zigbee network.
        
        Args:
            ieee_address: IEEE address of device
            friendly_name: Friendly name of device
            
        Returns:
            True if command sent successfully
            
        Raises:
            ValueError: If neither ieee_address nor friendly_name provided
        """
        if not ieee_address and not friendly_name:
            raise ValueError("Either ieee_address or friendly_name must be provided")
        
        payload = {}
        if ieee_address:
            payload["id"] = str(ieee_address)
        else:
            payload["id"] = str(friendly_name)
        
        try:
            topic = f"{self.bridge_topic}/bridge/request/device/remove"
            self.client.publish(topic, json.dumps(payload))
            logger.info(f"Remove device request sent: {ieee_address or friendly_name}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to remove device: {e}")
            return False
    
    def clear_discovered_devices(self) -> None:
        """Clear discovered devices list"""
        self.discovered_devices.clear()
        self.device_states.clear()
        logger.info("Cleared discovered devices")

