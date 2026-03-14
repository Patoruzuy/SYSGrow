"""
Device Coordinator Service.

Focused service responsible for coordinating device state across the application,
subscribing to hardware events, and persisting state changes.

Responsibilities:
- Subscribe to hardware EventBus events (actuator state, connectivity)
- Persist state changes to database for historical tracking
- Provide state history queries
- Coordinate between hardware layer and persistence layer

Related services:
- SensorManagementService / ActuatorManagementService: runtime + metadata
- DeviceHealthService: health/calibration/anomaly tracking
- DeviceCoordinator: EventBus → persistence bridge
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.enums.events import DeviceEvent
from app.utils.event_bus import EventBus
from app.utils.time import iso_now
from infrastructure.database.repositories.devices import DeviceRepository

logger = logging.getLogger(__name__)


class DeviceCoordinator:
    """
    Service for coordinating device state and event handling.
    
    This service subscribes to hardware events and persists state changes
    to the database for historical tracking and analysis.
    """
    
    def __init__(
        self,
        repository: DeviceRepository,
        event_bus: Optional[EventBus] = None
    ):
        """
        Initialize DeviceCoordinator.
        
        Args:
            repository: Device repository for database operations
            event_bus: Optional event bus for subscribing to hardware events
        """
        self.repository = repository
        self.event_bus = event_bus or EventBus()
        self._subscriptions = []
        logger.info("DeviceCoordinator initialized")
    
    def start(self) -> None:
        """
        Start coordinator by subscribing to hardware events.
        
        Call this during application initialization to enable state tracking.
        """
        try:
            # Subscribe to actuator state changes
            self._subscriptions.append(
                self.event_bus.subscribe(DeviceEvent.ACTUATOR_STATE_CHANGED, self._on_actuator_state_changed)
            )
            
            # Subscribe to connectivity changes
            self._subscriptions.append(
                self.event_bus.subscribe(DeviceEvent.CONNECTIVITY_CHANGED, self._on_connectivity_changed)
            )
            
            logger.info("DeviceCoordinator started: subscribed to 2 hardware events")
        except Exception as e:
            logger.error(f"Error starting DeviceCoordinator: {e}", exc_info=True)
            raise
    
    def stop(self) -> None:
        """
        Stop coordinator by unsubscribing from all events.
        
        Call this during application shutdown.
        """
        try:
            for unsubscribe in self._subscriptions:
                try:
                    unsubscribe()
                except Exception as unsub_error:
                    logger.warning(f"Error unsubscribing from event: {unsub_error}")
            
            self._subscriptions.clear()
            logger.info("DeviceCoordinator stopped: unsubscribed from all events")
        except Exception as e:
            logger.error(f"Error stopping DeviceCoordinator: {e}", exc_info=True)
    
    # ==================== EventBus Handlers ====================
    
    def _on_actuator_state_changed(self, payload: Dict[str, Any]) -> None:
        """
        Handle actuator state change events from hardware layer.
        
        Args:
            payload: Event payload with actuator_id, state, level, etc.
        """
        try:
            actuator_id = payload.get("actuator_id")
            state = payload.get("state")
            timestamp = payload.get("timestamp")
            value = payload.get("value")
            
            if actuator_id is None:
                logger.warning(f"Invalid actuator state change payload: {payload}")
                return
            
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()
            elif timestamp is None:
                timestamp = iso_now()

            self.repository.save_actuator_state(
                actuator_id=actuator_id,
                state=state,
                value=value,
                timestamp=timestamp,
            )
            
            logger.debug(f"Persisted actuator state change: actuator_id={actuator_id}, state={state}")
            
        except Exception as e:
            logger.error(f"Error handling actuator state change: {e}", exc_info=True)
    
    def _on_connectivity_changed(self, payload: Dict[str, Any]) -> None:
        """
        Handle device connectivity change events.
        
        Args:
            payload: Event payload with connection_type, status, endpoint, etc.
        """
        try:
            connection_type = payload.get("connection_type")
            status = payload.get("status")
            endpoint = payload.get("endpoint")
            port = payload.get("port")
            unit_id = payload.get("unit_id")
            device_id = payload.get("device_id")
            details = payload.get("details")
            timestamp = payload.get("timestamp")
            
            if not connection_type or not status:
                logger.warning(f"Invalid connectivity change payload: {payload}")
                return
            
            if isinstance(timestamp, datetime):
                timestamp = timestamp.isoformat()
            elif timestamp is None:
                timestamp = iso_now()

            if isinstance(details, dict):
                details = json.dumps(details)
            
            self.repository.save_connectivity_event(
                connection_type=connection_type,
                status=status,
                endpoint=endpoint,
                port=port,
                unit_id=unit_id,
                device_id=device_id,
                details=details,
                timestamp=timestamp,
            )
            
            logger.info("Persisted connectivity change: %s %s", connection_type, status)
            
        except Exception as e:
            logger.error(f"Error handling connectivity change: {e}", exc_info=True)
    
    # ==================== State History Queries ====================
    
    def get_actuator_state_history(
        self,
        actuator_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get state change history for an actuator.
        
        Args:
            actuator_id: Actuator identifier
            start_time: Optional start time for filtering
            end_time: Optional end time for filtering
            limit: Maximum number of records to return
            
        Returns:
            List of state change records
        """
        try:
            history = self.repository.get_actuator_state_history(
                actuator_id=actuator_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            logger.debug(f"Retrieved {len(history)} state records for actuator {actuator_id}")
            return history
        except Exception as e:
            logger.error(f"Error getting state history for actuator {actuator_id}: {e}", exc_info=True)
            return []
    
    def get_unit_actuator_state_history(
        self,
        unit_id: int,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        Get state change history for all actuators in a unit.
        
        Args:
            unit_id: Unit identifier
            start_time: Optional start time for filtering
            end_time: Optional end time for filtering
            limit: Maximum number of records to return
            
        Returns:
            List of state change records for all unit actuators
        """
        try:
            history = self.repository.get_unit_actuator_state_history(
                unit_id=unit_id,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            logger.debug(f"Retrieved {len(history)} state records for unit {unit_id}")
            return history
        except Exception as e:
            logger.error(f"Error getting state history for unit {unit_id}: {e}", exc_info=True)
            return []
    
    def get_recent_actuator_state(self, actuator_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the most recent state for an actuator.
        
        Args:
            actuator_id: Actuator identifier
            
        Returns:
            Most recent state record or None
        """
        try:
            state = self.repository.get_recent_actuator_state(actuator_id)
            if state:
                logger.debug(f"Retrieved recent state for actuator {actuator_id}: {state.get('state')}")
            return state
        except Exception as e:
            logger.error(f"Error getting recent state for actuator {actuator_id}: {e}", exc_info=True)
            return None
    
    def get_connectivity_history(
        self,
        device_id: int,
        device_type: str,
        hours: int = 24,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get connectivity history for a device.
        
        Args:
            device_id: Device identifier
            device_type: Type of device ('sensor' or 'actuator')
            hours: Number of hours to look back
            limit: Maximum number of records to return
            
        Returns:
            List of connectivity event records
        """
        try:
            start_time = datetime.utcnow() - timedelta(hours=hours)
            history = self.repository.get_connectivity_history(
                device_id=device_id,
                device_type=device_type,
                start_time=start_time,
                limit=limit
            )
            logger.debug(f"Retrieved {len(history)} connectivity events for {device_type} {device_id}")
            return history
        except Exception as e:
            logger.error(f"Error getting connectivity history for {device_type} {device_id}: {e}", exc_info=True)
            return []
    
    def prune_actuator_state_history(self, days: int = 30) -> int:
        """
        Remove old actuator state history records.
        
        Args:
            days: Remove records older than this many days
            
        Returns:
            Number of records deleted
        """
        try:
            deleted_count = self.repository.prune_actuator_state_history(days)
            logger.info(f"Pruned {deleted_count} actuator state records older than {days} days")
            return deleted_count
        except Exception as e:
            logger.error(f"Error pruning actuator state history: {e}", exc_info=True)
            return 0
