"""
Safety service for actuator interlocks and limits.

Features:
    - Interlock prevention (mutual exclusion)
    - Power limits
    - Runtime limits
    - Cooldown periods
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .actuator_management_service import ActuatorManagementService


logger = logging.getLogger(__name__)


class SafetyService:
    """
    Safety service for actuator interlocks and limits.

    Features:
    - Interlock prevention (mutual exclusion)
    - Power limits
    - Runtime limits
    - Cooldown periods
    """

    def __init__(self, manager: "ActuatorManagementService"):
        """
        Initialize safety service.

        Args:
            manager: ActuatorManagementService instance
        """
        self.manager = manager
        self.interlocks: dict[int, list[int]] = defaultdict(list)
        self.max_runtime: dict[int, float] = {}
        self.cooldown_periods: dict[int, float] = {}
        self.max_total_power: float | None = None

    def register_interlock(self, actuator_id: int, interlocked_with: int):
        """
        Register interlock between actuators.

        Args:
            actuator_id: Primary actuator ID
            interlocked_with: ID of interlocked actuator
        """
        if interlocked_with not in self.interlocks[actuator_id]:
            self.interlocks[actuator_id].append(interlocked_with)

        # Bidirectional interlock
        if actuator_id not in self.interlocks[interlocked_with]:
            self.interlocks[interlocked_with].append(actuator_id)

    def remove_interlock(self, actuator_id: int, interlocked_with: int):
        """
        Remove interlock.

        Args:
            actuator_id: Primary actuator ID
            interlocked_with: ID of interlocked actuator
        """
        if interlocked_with in self.interlocks[actuator_id]:
            self.interlocks[actuator_id].remove(interlocked_with)

        if actuator_id in self.interlocks[interlocked_with]:
            self.interlocks[interlocked_with].remove(actuator_id)

    def can_turn_on(self, actuator_id: int) -> bool:
        """
        Check if actuator can safely turn on.

        Args:
            actuator_id: ID of actuator

        Returns:
            True if safe to turn on
        """
        # Check interlocks
        for interlocked_id in self.interlocks.get(actuator_id, []):
            interlocked = self.manager.get_actuator(interlocked_id)
            if interlocked and interlocked.is_on:
                logger.warning("Interlock active: %s is ON", interlocked_id)
                return False

        # Check cooldown
        actuator = self.manager.get_actuator(actuator_id)
        if actuator and actuator.last_off_time:
            cooldown = self.cooldown_periods.get(actuator_id)
            if cooldown:
                elapsed = (datetime.now() - actuator.last_off_time).total_seconds()
                if elapsed < cooldown:
                    logger.warning("Cooldown active: %ss remaining", cooldown - elapsed)
                    return False

        # Check power limits
        if self.max_total_power and actuator:
            current_power = self._calculate_total_power()
            actuator_power = actuator.config.power_watts or 0
            if current_power + actuator_power > self.max_total_power:
                logger.warning(
                    f"Power limit would be exceeded: {current_power + actuator_power}W > {self.max_total_power}W"
                )
                return False

        return True

    def set_max_runtime(self, actuator_id: int, seconds: float):
        """
        Set maximum runtime for actuator.

        Args:
            actuator_id: ID of actuator
            seconds: Maximum runtime in seconds
        """
        self.max_runtime[actuator_id] = seconds

        actuator = self.manager.get_actuator(actuator_id)
        if actuator:
            actuator.max_runtime_seconds = seconds

    def set_cooldown(self, actuator_id: int, seconds: float):
        """
        Set cooldown period after turning off.

        Args:
            actuator_id: ID of actuator
            seconds: Cooldown period in seconds
        """
        self.cooldown_periods[actuator_id] = seconds

        actuator = self.manager.get_actuator(actuator_id)
        if actuator:
            actuator.cooldown_seconds = seconds

    def set_max_total_power(self, watts: float):
        """
        Set maximum total power consumption.

        Args:
            watts: Maximum power in watts
        """
        self.max_total_power = watts

    def _calculate_total_power(self) -> float:
        """Calculate current total power consumption"""
        total = 0.0
        for actuator in self.manager.get_all_actuators():
            if actuator.is_on and actuator.config.power_watts:
                total += actuator.config.power_watts
        return total
