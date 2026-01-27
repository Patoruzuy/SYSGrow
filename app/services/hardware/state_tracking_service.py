"""
State tracking service for actuator history and analytics.

Features:
    - State change history
    - Runtime statistics
    - Cycle counting
    - Power consumption tracking
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, List, Optional, Dict, Any
from collections import defaultdict

from app.domain.actuators import ActuatorReading
from app.domain.actuators import ActuatorState

if TYPE_CHECKING:
    from app.services.hardware.actuator_management_service import ActuatorManagementService

# Type alias for backwards compatibility
ActuatorManager = "ActuatorManagementService"

logger = logging.getLogger(__name__)


class StateTrackingService:
    """
    State tracking service for actuator history and analytics.
    
    Features:
    - State change history
    - Runtime statistics
    - Cycle counting
    - Power consumption tracking
    """
    
    def __init__(self, manager: 'ActuatorManager'):
        """
        Initialize state tracking service.
        
        Args:
            manager: ActuatorManager instance
        """
        self.manager = manager
        self.history: Dict[int, List[ActuatorReading]] = defaultdict(list)
        self.max_history_per_actuator = 1000
    
    def record_state_change(self, actuator_id: int, reading: ActuatorReading):
        """
        Record state change.
        
        Args:
            actuator_id: ID of actuator
            reading: State reading
        """
        self.history[actuator_id].append(reading)
        
        # Limit history size
        if len(self.history[actuator_id]) > self.max_history_per_actuator:
            self.history[actuator_id] = self.history[actuator_id][-self.max_history_per_actuator:]
    
    def get_history(
        self,
        actuator_id: int,
        since: Optional[datetime] = None,
        limit: Optional[int] = None
    ) -> List[ActuatorReading]:
        """
        Get state change history.
        
        Args:
            actuator_id: ID of actuator
            since: Only return readings after this time
            limit: Maximum number of readings
            
        Returns:
            List of readings
        """
        readings = self.history.get(actuator_id, [])
        
        if since:
            readings = [r for r in readings if r.timestamp >= since]
        
        if limit:
            readings = readings[-limit:]
        
        return readings
    
    def get_stats(self, actuator_id: int) -> Dict[str, Any]:
        """
        Get statistics for actuator.
        
        Args:
            actuator_id: ID of actuator
            
        Returns:
            Dictionary with statistics
        """
        actuator = self.manager.get_actuator(actuator_id)
        if not actuator:
            return {}
        
        history = self.history.get(actuator_id, [])
        
        # Calculate uptime percentage (last 24 hours) from ON/OFF transitions.
        now = datetime.now()
        since_24h = now - timedelta(hours=24)
        recent = [r for r in history if r.timestamp >= since_24h]

        recent_sorted = sorted(recent, key=lambda r: r.timestamp)
        prior = None
        for r in reversed(history):
            if r.timestamp < since_24h:
                prior = r
                break

        on_start: Optional[datetime] = since_24h if (prior and prior.state == ActuatorState.ON) else None
        on_seconds = 0.0
        for r in recent_sorted:
            if r.state == ActuatorState.ON:
                on_start = r.timestamp
            elif r.state == ActuatorState.OFF and on_start is not None:
                on_seconds += (r.timestamp - on_start).total_seconds()
                on_start = None

        if on_start is not None:
            on_seconds += (now - on_start).total_seconds()

        uptime_pct = (on_seconds / 86400) * 100 if on_seconds > 0 else 0.0
        
        return {
            'actuator_id': actuator_id,
            'name': actuator.name,
            'current_state': actuator.current_state.value,
            'total_runtime_seconds': actuator.total_runtime_seconds,
            'total_runtime_hours': actuator.total_runtime_seconds / 3600,
            'cycle_count': actuator.cycle_count,
            'uptime_24h_pct': round(uptime_pct, 2),
            'state_changes_24h': len(recent),
            'total_state_changes': len(history)
        }
    
    def clear_history(self, actuator_id: Optional[int] = None):
        """
        Clear history.
        
        Args:
            actuator_id: ID of actuator (if None, clears all)
        """
        if actuator_id:
            self.history[actuator_id].clear()
        else:
            self.history.clear()
