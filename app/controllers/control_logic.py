"""
ControlLogic: PID climate control for environmental factors.

Handles actuator control for:
- Temperature (heater/cooler)
- Humidity (humidifier/dehumidifier)
- CO2 (injector)
- Light intensity (dimmer)

Note: Irrigation/soil moisture is handled by PlantSensorController + IrrigationWorkflowService.
The user controls irrigation decisions, not PID algorithms.

Author: Sebastian Gomez
Date: 2024
Updated: January 2026 - Removed soil moisture PID (user-controlled irrigation)
"""

import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any, Callable

from app.controllers.control_algorithms import PIDController
from app.domain.actuators import ActuatorState, ActuatorType
from app.domain.control import ControlConfig, ControlMetrics
from app.enums import ControlStrategy
from app.utils.time import iso_now

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ControlLogic:
    """
    PID control logic for environmental factors with actuator management.

    Features:
    - ActuatorType-based mapping instead of string names
    - Configurable PID parameters via ControlConfig
    - Feedback validation and health monitoring
    - Cycle time enforcement to prevent rapid switching
    - Deadband logic to reduce oscillation

    Note:
        Irrigation is user-controlled via IrrigationWorkflowService.
        This class only handles environment control (temp, humidity, CO2, light).
    """

    def __init__(
        self,
        actuator_manager,
        event_bus,
        config: ControlConfig | None = None,
        analytics_repo=None,
        feedback_callback: Callable | None = None,
    ):
        """
        Initialize control logic with dependency injection.

        Args:
            actuator_manager: ActuatorManager instance
            event_bus: EventBus for publishing control events
            config: ControlConfig for PID parameters (optional)
            analytics_repo: Analytics repository for sensor logging (optional)
            feedback_callback: Optional callback for control actions
        """
        self.actuator_manager = actuator_manager
        self.analytics_repo = analytics_repo
        self.event_bus = event_bus
        self.config = config or ControlConfig()
        self.feedback_callback = feedback_callback

        # Type-safe actuator mapping: ActuatorType -> actuator_id
        self.actuator_map: dict[ActuatorType, int] = {}

        # Last action time per actuator to enforce minimum cycle time
        self.last_action_time: dict[int, datetime] = {}

        # Control metrics per strategy
        self.metrics: dict[ControlStrategy, ControlMetrics] = {
            strategy: ControlMetrics() for strategy in ControlStrategy
        }

        # Current state
        self.growth_stage = "vegetative"
        self.enabled = True

        # PID controllers for environmental factors only
        # Note: Irrigation is user-controlled, not PID-controlled
        self.temp_controller = PIDController(
            kp=self.config.temp_kp, ki=self.config.temp_ki, kd=self.config.temp_kd, setpoint=self.config.temp_setpoint
        )
        self.humidity_controller = PIDController(
            kp=self.config.humidity_kp,
            ki=self.config.humidity_ki,
            kd=self.config.humidity_kd,
            setpoint=self.config.humidity_setpoint,
        )
        self.co2_controller = PIDController(
            kp=self.config.co2_kp, ki=self.config.co2_ki, kd=self.config.co2_kd, setpoint=self.config.co2_setpoint
        )
        self.lux_controller = PIDController(
            kp=self.config.lux_kp, ki=self.config.lux_ki, kd=self.config.lux_kd, setpoint=self.config.lux_setpoint
        )

        logger.info(
            "ControlLogic initialized: mode=PID, "
            f"temp_sp={self.config.temp_setpoint}°C, "
            f"humidity_sp={self.config.humidity_setpoint}%"
        )

    def register_actuator(self, actuator_type: ActuatorType, actuator_id: int) -> None:
        """
        Register an actuator for control logic using ActuatorType enum.

        Args:
            actuator_type: ActuatorType enum (e.g., ActuatorType.HEATER)
            actuator_id: Actuator ID from ActuatorManager
        """
        self.actuator_map[actuator_type] = actuator_id
        logger.info(f"Registered actuator: {actuator_type.value} -> ID {actuator_id}")

    def unregister_actuator(self, actuator_type: ActuatorType) -> None:
        """Unregister an actuator."""
        if actuator_type in self.actuator_map:
            del self.actuator_map[actuator_type]
            logger.info(f"Unregistered actuator: {actuator_type.value}")

    def _get_actuator_id(self, actuator_type: ActuatorType) -> int | None:
        """Get actuator ID by ActuatorType enum."""
        return self.actuator_map.get(actuator_type)

    def _can_act(self, actuator_id: int) -> bool:
        """
        Check if enough time has passed since last action (cycle time enforcement).

        Args:
            actuator_id: Actuator ID

        Returns:
            True if action is allowed
        """
        last_action = self.last_action_time.get(actuator_id)
        if not last_action:
            return True

        elapsed = (datetime.now() - last_action).total_seconds()
        return elapsed >= (self.config.min_cycle_time or 60)

    def _execute_actuator_command(self, actuator_id: int, command: str, strategy: ControlStrategy) -> bool:
        """
        Execute actuator command with validation and metrics tracking.

        Args:
            actuator_id: Actuator ID
            command: 'on' or 'off'
            strategy: Control strategy for metrics

        Returns:
            True if command succeeded
        """
        if not self.enabled:
            logger.warning("Control logic disabled, skipping command")
            return False

        # Check cycle time
        if not self._can_act(actuator_id):
            return False

        metrics = self.metrics[strategy]
        start_time = time.time()

        try:
            # Execute command
            if command == "on":
                result = self.actuator_manager.turn_on(actuator_id)
            elif command == "off":
                result = self.actuator_manager.turn_off(actuator_id)
            else:
                raise ValueError(f"Invalid command: {command}")

            # Check result
            success = result.state != ActuatorState.ERROR

            # Update metrics
            metrics.total_actions += 1
            if success:
                metrics.successful_actions += 1
                metrics.consecutive_errors = 0
                logger.info("Actuator %s -> %s (Strategy: %s)", actuator_id, command, strategy.value)
            else:
                metrics.failed_actions += 1
                metrics.consecutive_errors += 1
                logger.error("Actuator %s command failed: %s", actuator_id, result.error_message)

            # Update response time
            response_time = time.time() - start_time
            if metrics.average_response_time == 0:
                metrics.average_response_time = response_time
            else:
                # Exponential moving average
                metrics.average_response_time = 0.8 * metrics.average_response_time + 0.2 * response_time

            now = datetime.now()
            metrics.last_action_time = now
            self.last_action_time[actuator_id] = now

            # Callback notification
            if self.feedback_callback:
                self.feedback_callback(
                    {
                        "actuator_id": actuator_id,
                        "command": command,
                        "success": success,
                        "strategy": strategy.value,
                        "response_time": response_time,
                    }
                )

            # Disable control if too many consecutive errors
            if metrics.consecutive_errors >= self.config.max_consecutive_errors:
                logger.critical(
                    f"Control strategy {strategy.value} disabled due to {metrics.consecutive_errors} consecutive errors"
                )
                self.enabled = False

            return success

        except Exception as e:
            logger.error(f"Exception executing actuator command: {e}")
            metrics.failed_actions += 1
            metrics.consecutive_errors += 1
            return False

    def _execute_actuator_level(self, actuator_id: int, level: float, strategy: ControlStrategy) -> bool:
        """
        Execute actuator level command (PWM/dimming) with validation and metrics tracking.

        Args:
            actuator_id: Actuator ID
            level: Level from 0-100
            strategy: Control strategy for metrics

        Returns:
            True if command succeeded
        """
        if not self.enabled:
            return False

        # Clamp level to 0-100
        level = max(0.0, min(100.0, float(level)))

        # Check cycle time
        if not self._can_act(actuator_id):
            return False

        metrics = self.metrics[strategy]
        start_time = time.time()

        try:
            # Execute command
            result = self.actuator_manager.set_level(actuator_id, level)

            # Check result
            success = result.state != ActuatorState.ERROR

            # Update metrics
            metrics.total_actions += 1
            if success:
                metrics.successful_actions += 1
                metrics.consecutive_errors = 0
                logger.info("Actuator %s level -> %s%% (Strategy: %s)", actuator_id, level, strategy.value)
            else:
                metrics.failed_actions += 1
                metrics.consecutive_errors += 1
                logger.error("Actuator %s level command failed: %s", actuator_id, result.error_message)

            # Update response time
            response_time = time.time() - start_time
            metrics.average_response_time = 0.8 * getattr(metrics, "average_response_time", 0) + 0.2 * response_time

            now = datetime.now()
            metrics.last_action_time = now
            self.last_action_time[actuator_id] = now

            # Callback notification
            if self.feedback_callback:
                self.feedback_callback(
                    {
                        "actuator_id": actuator_id,
                        "command": "set_level",
                        "level": level,
                        "success": success,
                        "strategy": strategy.value,
                        "response_time": response_time,
                    }
                )

            return success
        except Exception as e:
            logger.error(f"Exception setting actuator level: {e}")
            metrics.failed_actions += 1
            metrics.consecutive_errors += 1
            return False

    def control_temperature(self, data: dict[str, Any]) -> bool:
        """
        Control temperature using PID.

        Args:
            data: Sensor data with 'temperature', 'unit_id', and optional 'plant_stage'

        Returns:
            True if control action succeeded
        """
        temperature = float(data.get("temperature", 0))

        target_temp = self.config.temp_setpoint

        # Apply deadband to reduce oscillation
        error = abs(temperature - target_temp)
        if error < self.config.temp_deadband:
            return True

        control_signal = self.temp_controller.compute(temperature, target_temp)
        success = True

        try:
            if control_signal > 0:
                # Need heating
                heater_id = self._get_actuator_id(ActuatorType.HEATER)
                cooler_id = self._get_actuator_id(ActuatorType.FAN)  # Fan for cooling

                if heater_id:
                    success = self._execute_actuator_command(heater_id, "on", ControlStrategy.HEATING)
                if cooler_id:
                    self._execute_actuator_command(cooler_id, "off", ControlStrategy.COOLING)

            elif control_signal < 0:
                # Need cooling
                heater_id = self._get_actuator_id(ActuatorType.HEATER)
                cooler_id = self._get_actuator_id(ActuatorType.FAN)

                if cooler_id:
                    success = self._execute_actuator_command(cooler_id, "on", ControlStrategy.COOLING)
                if heater_id:
                    self._execute_actuator_command(heater_id, "off", ControlStrategy.HEATING)

            return success

        except Exception as e:
            logger.error(f"Temperature control error: {e}")
            return False

    def control_humidity(self, data: dict[str, Any]) -> bool:
        """
        Control humidity using PID.

        Args:
            data: Sensor data with 'humidity' and 'unit_id'

        Returns:
            True if control action succeeded
        """
        humidity = float(data.get("humidity", 0))

        target_humidity = self.config.humidity_setpoint

        # Apply deadband
        error = abs(humidity - target_humidity)
        if error < self.config.humidity_deadband:
            return True

        control_signal = self.humidity_controller.compute(humidity, target_humidity)
        success = True

        try:
            if control_signal > 0:
                # Need humidification
                humidifier_id = self._get_actuator_id(ActuatorType.HUMIDIFIER)
                dehumidifier_id = self._get_actuator_id(ActuatorType.DEHUMIDIFIER)

                if humidifier_id:
                    success = self._execute_actuator_command(humidifier_id, "on", ControlStrategy.HUMIDIFYING)
                if dehumidifier_id:
                    self._execute_actuator_command(dehumidifier_id, "off", ControlStrategy.DEHUMIDIFYING)

            elif control_signal < 0:
                # Need dehumidification
                humidifier_id = self._get_actuator_id(ActuatorType.HUMIDIFIER)
                dehumidifier_id = self._get_actuator_id(ActuatorType.DEHUMIDIFIER)

                if dehumidifier_id:
                    success = self._execute_actuator_command(dehumidifier_id, "on", ControlStrategy.DEHUMIDIFYING)
                if humidifier_id:
                    self._execute_actuator_command(humidifier_id, "off", ControlStrategy.HUMIDIFYING)

            return success

        except Exception as e:
            logger.error(f"Humidity control error: {e}")
            return False

    def control_co2(self, data: dict[str, Any]) -> bool:
        """
        Control CO2 enrichment using PID.

        Args:
            data: Sensor data with 'co2' and 'unit_id'

        Returns:
            True if control action succeeded
        """
        co2_ppm = float(data.get("co2", 0))
        target_co2 = self.config.co2_setpoint

        # Deadband check
        if abs(co2_ppm - target_co2) < self.config.co2_deadband:
            return True

        control_signal = self.co2_controller.compute(co2_ppm, target_co2)
        success = True

        try:
            actuator_id = self._get_actuator_id(ActuatorType.CO2_INJECTOR)
            if actuator_id:
                if control_signal > 0:
                    # CO2 too low, turn on injector
                    success = self._execute_actuator_command(actuator_id, "on", ControlStrategy.CO2_ENRICHMENT)
                else:
                    # CO2 reached target or higher, turn off injector
                    success = self._execute_actuator_command(actuator_id, "off", ControlStrategy.CO2_ENRICHMENT)
            return success
        except Exception as e:
            logger.error(f"CO2 control error: {e}")
            return False

    def control_lux(self, data: dict[str, Any]) -> bool:
        """
        Control Light intensity (Lux) using PID and Dimming.

        Args:
            data: Sensor data with 'lux' and 'unit_id'

        Returns:
            True if control action succeeded
        """
        lux = float(data.get("lux", 0))
        target_lux = self.config.lux_setpoint

        # Deadband check
        if abs(lux - target_lux) < self.config.lux_deadband:
            return True

        control_signal = self.lux_controller.compute(lux, target_lux)

        # Clamp PID output to 0-100 for PWM level
        level = max(0.0, min(100.0, control_signal))

        success = True
        try:
            actuator_id = self._get_actuator_id(ActuatorType.LIGHT)
            if actuator_id:
                success = self._execute_actuator_level(actuator_id, level, ControlStrategy.LIGHT_CONTROL)
            return success
        except Exception as e:
            logger.error(f"Lux control error: {e}")
            return False

    def update_thresholds(self, data: dict[str, Any]) -> None:
        """
        Update setpoints for the controllers.

        Args:
            data: Dictionary with 'temperature', 'humidity', 'co2', 'lux' setpoints

        Note:
            Soil moisture thresholds are handled by IrrigationWorkflowService.
        """
        if "temperature" in data:
            self.temp_controller.setpoint = float(data["temperature"])
            self.config.temp_setpoint = float(data["temperature"])
            logger.info(f"Updated temperature setpoint: {self.config.temp_setpoint}°C")

        if "humidity" in data:
            self.humidity_controller.setpoint = float(data["humidity"])
            self.config.humidity_setpoint = float(data["humidity"])
            logger.info(f"Updated humidity setpoint: {self.config.humidity_setpoint}%")

        if "co2" in data:
            self.co2_controller.setpoint = float(data["co2"])
            self.config.co2_setpoint = float(data["co2"])
            logger.info(f"Updated CO2 setpoint: {self.config.co2_setpoint} PPM")

        if "lux" in data:
            self.lux_controller.setpoint = float(data["lux"])
            self.config.lux_setpoint = float(data["lux"])
            logger.info(f"Updated Lux setpoint: {self.config.lux_setpoint} LUX")

    def update_pid_parameters(self, controller_name: str, kp: float, ki: float, kd: float) -> None:
        """
        Update PID parameters dynamically.

        Args:
            controller_name: 'temperature', 'humidity', 'co2' or 'lux'
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
        """
        if controller_name == "temperature":
            self.temp_controller.kp = kp
            self.temp_controller.ki = ki
            self.temp_controller.kd = kd
            self.config.temp_kp = kp
            self.config.temp_ki = ki
            self.config.temp_kd = kd
        elif controller_name == "humidity":
            self.humidity_controller.kp = kp
            self.humidity_controller.ki = ki
            self.humidity_controller.kd = kd
            self.config.humidity_kp = kp
            self.config.humidity_ki = ki
            self.config.humidity_kd = kd
        elif controller_name == "co2":
            self.co2_controller.kp = kp
            self.co2_controller.ki = ki
            self.co2_controller.kd = kd
            self.config.co2_kp = kp
            self.config.co2_ki = ki
            self.config.co2_kd = kd
        elif controller_name == "lux":
            self.lux_controller.kp = kp
            self.lux_controller.ki = ki
            self.lux_controller.kd = kd
            self.config.lux_kp = kp
            self.config.lux_ki = ki
            self.config.lux_kd = kd
        else:
            logger.warning(f"Unknown controller: {controller_name}")
            return

        logger.info(f"Updated PID parameters for {controller_name}: Kp={kp}, Ki={ki}, Kd={kd}")

    def get_metrics(self) -> dict[str, Any]:
        """
        Get control loop performance metrics.

        Returns:
            Dictionary with metrics for all strategies
        """
        return {strategy.value: metrics.to_dict() for strategy, metrics in self.metrics.items()}

    def reset_metrics(self) -> None:
        """Reset all control metrics."""
        self.metrics = {strategy: ControlMetrics() for strategy in ControlStrategy}
        logger.info("Control metrics reset")

    def enable(self) -> None:
        """Enable control logic."""
        self.enabled = True
        logger.info("Control logic enabled")

    def disable(self) -> None:
        """Disable control logic."""
        self.enabled = False
        logger.info("Control logic disabled")

    def get_status(self) -> dict[str, Any]:
        """
        Get comprehensive control logic status.

        Returns:
            Status dictionary
        """
        return {
            "enabled": self.enabled,
            "mode": "PID",
            "growth_stage": self.growth_stage,
            "config": {
                "temp_setpoint": self.config.temp_setpoint,
                "humidity_setpoint": self.config.humidity_setpoint,
                "co2_setpoint": self.config.co2_setpoint,
                "lux_setpoint": self.config.lux_setpoint,
                "temp_deadband": self.config.temp_deadband,
                "humidity_deadband": self.config.humidity_deadband,
                "co2_deadband": self.config.co2_deadband,
                "lux_deadband": self.config.lux_deadband,
                "min_cycle_time": self.config.min_cycle_time,
            },
            "registered_actuators": {
                actuator_type.value: actuator_id for actuator_type, actuator_id in self.actuator_map.items()
            },
            "metrics": self.get_metrics(),
            "timestamp": iso_now(),
        }
