"""
Actuator Domain Entities

Domain model for actuators with dataclasses.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol as TypingProtocol


class Protocol(str, Enum):
    """Communication protocols"""

    GPIO = "gpio"
    HTTP = "http"
    WIFI = "wifi"
    ZIGBEE = "zigbee"
    ZIGBEE2MQTT = "zigbee2mqtt"
    MODBUS = "modbus"
    BLE = "ble"


# ActuatorType is now defined canonically in app.enums.device and re-exported
# here for backward compatibility.  All members (including PUMP alias) are
# available.  The _missing_ hook on the canonical enum handles legacy lowercase
# values like "pump", "light", etc.
from app.enums.device import ActuatorType


class ActuatorState(str, Enum):
    """Actuator states"""

    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"
    ERROR = "error"
    UNAVAILABLE = "unavailable"


class ControlMode(str, Enum):
    """Control modes for actuators"""

    MANUAL = "manual"
    AUTO = "auto"
    SCHEDULE = "schedule"
    OFF = "off"


@dataclass
class ActuatorConfig:
    """
    Actuator configuration.

    For pump actuators, the `metadata` field stores calibration data:

    Pump-specific metadata fields:
        flow_rate_ml_per_second (float): Calibrated flow rate
        calibration_volume_ml (float): Volume used in calibration
        calibration_duration_seconds (int): Duration of calibration run
        calibrated_at (str): ISO timestamp of calibration
        calibration_confidence (float): 0-1, decreases with feedback adjustments
        last_feedback_adjustment (str): ISO timestamp of last ML adjustment
        feedback_adjustments_count (int): Number of ML-based adjustments
        pressure_rating_psi (float): Optional pump pressure rating
        max_flow_rate_ml_per_second (float): Manufacturer spec (optional)

    Example pump metadata:
        {
            "flow_rate_ml_per_second": 3.5,
            "calibration_volume_ml": 105.0,
            "calibration_duration_seconds": 30,
            "calibrated_at": "2026-01-14T10:30:00Z",
            "calibration_confidence": 0.95,
            "last_feedback_adjustment": "2026-01-14T15:00:00Z",
            "feedback_adjustments_count": 1
        }
    """

    name: str
    actuator_type: ActuatorType
    protocol: Protocol
    # Protocol-specific configuration
    gpio_pin: int | None = None
    mqtt_topic: str | None = None
    ip_address: str | None = None
    zigbee_id: str | None = None
    # Control and safety
    control_mode: ControlMode = ControlMode.MANUAL
    min_value: float = 0.0
    max_value: float = 100.0
    invert_logic: bool = False
    pwm_frequency: int | None = None
    max_runtime_seconds: float | None = None
    cooldown_seconds: float | None = None
    # Monitoring
    power_watts: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActuatorCommand:
    """Command to send to actuator"""

    command_type: str  # 'on', 'off', 'toggle', 'set_brightness', etc.
    value: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ActuatorReading:
    """Reading from actuator (state, power, etc.)"""

    actuator_id: int
    state: ActuatorState
    timestamp: datetime = field(default_factory=datetime.now)
    value: Any = None  # For dimmers, brightness level, etc.
    power: float | None = None  # Current power consumption in watts
    energy: float | None = None  # Cumulative energy in kWh
    runtime_seconds: float | None = None  # Duration of the last ON cycle
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ActuatorAdapter(TypingProtocol):
    """Protocol for actuator adapters"""

    def turn_on(self) -> bool | None:
        """Turn actuator on"""
        ...

    def turn_off(self) -> bool | None:
        """Turn actuator off"""
        ...

    # Optional capabilities supported by some adapters.
    def set_level(self, value: float) -> bool | None:  # pragma: no cover
        ...

    def get_state(self) -> ActuatorState:  # pragma: no cover
        ...

    def is_available(self) -> bool:  # pragma: no cover
        ...

    def cleanup(self) -> None:  # pragma: no cover
        """
        Cleanup resources (unsubscribe MQTT topics, release GPIO, etc.).
        Called when actuator is unregistered or deleted.
        """
        ...


@dataclass
class ActuatorEntity:
    """
    Actuator entity with domain logic.

    This is the main domain object that encapsulates actuator behavior.
    """

    actuator_id: int
    config: ActuatorConfig
    adapter: ActuatorAdapter

    # Runtime state
    current_state: ActuatorState = ActuatorState.UNKNOWN
    last_reading: ActuatorReading | None = None
    last_command: ActuatorCommand | None = None
    control_mode: ControlMode = ControlMode.MANUAL

    # Safety configuration
    interlocks: list[int] = field(default_factory=list)

    # Statistics
    total_runtime_seconds: float = 0.0  # Total runtime in seconds
    cycle_count: int = 0
    last_on_time: datetime | None = None
    last_off_time: datetime | None = None

    # Safety
    is_locked: bool = False
    lock_reason: str | None = None

    # Optional per-device limits (used by SafetyService)
    max_runtime_seconds: float | None = None
    cooldown_seconds: float | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def is_on(self) -> bool:
        return self.current_state == ActuatorState.ON

    def turn_on(self) -> ActuatorReading:
        """Turn actuator on and return an ActuatorReading."""
        if self.is_locked:
            reading = ActuatorReading(
                actuator_id=self.actuator_id,
                state=ActuatorState.ERROR,
                error_message=self.lock_reason or "Actuator is locked",
            )
            self.last_reading = reading
            return reading

        now = datetime.now()
        try:
            result = self.adapter.turn_on()
        except Exception as exc:
            success = False
            error_message = str(exc)
        else:
            success = True if result is None else bool(result)
            error_message = None

        if success:
            self.current_state = ActuatorState.ON
            self.last_on_time = now
            self.cycle_count += 1
            reading = ActuatorReading(
                actuator_id=self.actuator_id,
                state=ActuatorState.ON,
                timestamp=now,
            )
        else:
            reading = ActuatorReading(
                actuator_id=self.actuator_id,
                state=ActuatorState.ERROR,
                timestamp=now,
                error_message=error_message or "Failed to turn on actuator",
            )

        self.last_command = ActuatorCommand(command_type="on", timestamp=now)
        self.last_reading = reading
        return reading

    def turn_off(self) -> ActuatorReading:
        """Turn actuator off and return an ActuatorReading."""
        now = datetime.now()
        try:
            result = self.adapter.turn_off()
        except Exception as exc:
            success = False
            error_message = str(exc)
        else:
            success = True if result is None else bool(result)
            error_message = None

        runtime_seconds: float | None = None
        if success:
            if self.last_on_time:
                runtime_seconds = (now - self.last_on_time).total_seconds()
                self.total_runtime_seconds += runtime_seconds

            self.current_state = ActuatorState.OFF
            self.last_off_time = now
            reading = ActuatorReading(
                actuator_id=self.actuator_id,
                state=ActuatorState.OFF,
                timestamp=now,
                runtime_seconds=runtime_seconds,
            )
        else:
            reading = ActuatorReading(
                actuator_id=self.actuator_id,
                state=ActuatorState.ERROR,
                timestamp=now,
                error_message=error_message or "Failed to turn off actuator",
            )

        self.last_command = ActuatorCommand(command_type="off", timestamp=now)
        self.last_reading = reading
        return reading

    def get_state(self) -> ActuatorReading:
        """Get current state from adapter and return an ActuatorReading."""
        now = datetime.now()
        state: ActuatorState
        if hasattr(self.adapter, "get_state"):
            try:
                raw_state = self.adapter.get_state()  # type: ignore[attr-defined]
            except Exception as exc:
                reading = ActuatorReading(
                    actuator_id=self.actuator_id,
                    state=ActuatorState.ERROR,
                    timestamp=now,
                    error_message=str(exc),
                )
                self.last_reading = reading
                return reading

            if isinstance(raw_state, ActuatorState):
                state = raw_state
            else:
                s = str(raw_state).strip().lower()
                if s == "on":
                    state = ActuatorState.ON
                elif s == "off":
                    state = ActuatorState.OFF
                else:
                    state = ActuatorState.UNKNOWN
        else:
            state = self.current_state

        self.current_state = state
        reading = ActuatorReading(
            actuator_id=self.actuator_id,
            state=state,
            timestamp=now,
        )
        self.last_reading = reading
        return reading

    def is_available(self) -> bool:
        """Check if actuator is available"""
        if hasattr(self.adapter, "is_available"):
            return bool(self.adapter.is_available())  # type: ignore[attr-defined]
        return True

    def toggle(self) -> ActuatorReading:
        """Toggle actuator state."""
        return self.turn_off() if self.is_on else self.turn_on()

    def set_level(self, value: float) -> ActuatorReading:
        """Set actuator level (PWM/dimming) if supported, otherwise fall back to ON/OFF."""
        now = datetime.now()
        if hasattr(self.adapter, "set_level"):
            try:
                result = self.adapter.set_level(value)  # type: ignore[attr-defined]
            except Exception as exc:
                reading = ActuatorReading(
                    actuator_id=self.actuator_id,
                    state=ActuatorState.ERROR,
                    timestamp=now,
                    value=value,
                    error_message=str(exc),
                )
                self.last_reading = reading
                return reading

            success = True if result is None else bool(result)
            if success:
                state = ActuatorState.ON if value > 0 else ActuatorState.OFF
                self.current_state = state
                reading = ActuatorReading(
                    actuator_id=self.actuator_id,
                    state=state,
                    timestamp=now,
                    value=value,
                )
                self.last_command = ActuatorCommand(command_type="set_level", value=value, timestamp=now)
                self.last_reading = reading
                return reading

        # Fallback: treat >0 as ON, else OFF.
        return self.turn_on() if value > 0 else self.turn_off()

    def pulse(self, duration_seconds: float) -> ActuatorReading:
        """Pulse actuator (ON for duration then OFF)."""
        on_reading = self.turn_on()
        if on_reading.state != ActuatorState.ON:
            return on_reading
        time.sleep(max(0.0, float(duration_seconds)))
        return self.turn_off()

    def add_interlock(self, other_actuator_id: int) -> None:
        if other_actuator_id not in self.interlocks:
            self.interlocks.append(other_actuator_id)

    def remove_interlock(self, other_actuator_id: int) -> None:
        if other_actuator_id in self.interlocks:
            self.interlocks.remove(other_actuator_id)

    def lock(self, reason: str) -> None:
        """Lock actuator (safety)"""
        self.is_locked = True
        self.lock_reason = reason

    def unlock(self) -> None:
        """Unlock actuator"""
        self.is_locked = False
        self.lock_reason = None
