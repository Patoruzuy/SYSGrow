"""
Energy Monitoring Service for Actuators

Tracks power consumption of smart switches and actuators with built-in power monitoring.
Integrates with Zigbee2MQTT smart switches that report energy usage.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Callable

from app.domain.energy import ConsumptionStats, EnergyReading, PowerProfile

logger = logging.getLogger(__name__)


class EnergyMonitoringService:
    """
    Service for monitoring actuator energy consumption.

    Features:
    - Real-time power monitoring from Zigbee2MQTT smart switches
    - Power consumption estimation for non-monitored devices
    - Energy usage statistics and cost calculations
    - Historical data tracking (in-memory + database)
    - Power profiling per actuator type
    """

    def __init__(self, electricity_rate_kwh: float = 0.12, analytics_repo=None):
        """
        Initialize energy monitoring service.

        Args:
            electricity_rate_kwh: Cost per kWh in local currency
            analytics_repo: AnalyticsRepository for database persistence (optional)
        """
        # Storage (in-memory cache for fast access)
        self.readings: dict[int, list[EnergyReading]] = defaultdict(list)
        self.power_profiles: dict[str, PowerProfile] = {}
        self.latest_readings: dict[int, EnergyReading] = {}

        # Database persistence (direct repository access)
        self.analytics_repo = analytics_repo

        # Configuration
        self.electricity_rate = electricity_rate_kwh
        self.max_readings_per_actuator = 1000  # Limit memory usage

        # Callbacks
        self.power_threshold_callbacks: list[Callable[[int, float], None]] = []

        logger.info(f"EnergyMonitoringService initialized (DB persistence: {analytics_repo is not None})")

    def register_power_profile(
        self,
        actuator_type: str,
        rated_power_watts: float,
        standby_power_watts: float = 0.0,
        efficiency_factor: float = 1.0,
        power_curve: dict[int, float] | None = None,
    ) -> None:
        """
        Register a power profile for an actuator type.

        Args:
            actuator_type: Type of actuator
            rated_power_watts: Maximum power consumption
            standby_power_watts: Power when off/standby
            efficiency_factor: Efficiency (0.0-1.0)
            power_curve: Optional power consumption curve (level -> watts)
        """
        profile = PowerProfile(
            actuator_type=actuator_type,
            rated_power_watts=rated_power_watts,
            standby_power_watts=standby_power_watts,
            efficiency_factor=efficiency_factor,
            power_curve=power_curve or {},
        )

        self.power_profiles[actuator_type] = profile
        logger.info(f"Registered power profile for {actuator_type}: {rated_power_watts}W")

    def record_reading(self, reading: EnergyReading) -> None:
        """
        Record an energy reading from a smart switch.
        Stores in memory and persists to database if available.

        Args:
            reading: Energy reading to record
        """
        actuator_id = reading.actuator_id

        # Store in memory (fast access)
        self.readings[actuator_id].append(reading)
        self.latest_readings[actuator_id] = reading

        # Limit memory usage
        if len(self.readings[actuator_id]) > self.max_readings_per_actuator:
            self.readings[actuator_id].pop(0)

        # Persist to database
        if self.analytics_repo:
            # Note: plant_id, unit_id, growth_stage should be passed from ActuatorManager
            self._persist_reading(reading)

        # Check power thresholds
        if reading.power:
            self._check_power_thresholds(actuator_id, reading.power)

        logger.debug(f"Recorded energy reading for actuator {actuator_id}: {reading.power}W")

    def estimate_power(self, actuator_id: int, actuator_type: str, level: float, state: str) -> float | None:
        """
        Estimate power consumption for actuator without built-in monitoring.

        Args:
            actuator_id: Actuator ID
            actuator_type: Type of actuator
            level: Current level (0-100)
            state: Current state ('on', 'off', 'partial')

        Returns:
            Estimated power in watts, or None if no profile available
        """
        if state == "off":
            return 0.0

        profile = self.power_profiles.get(actuator_type)
        if not profile:
            logger.warning(f"No power profile for {actuator_type}")
            return None

        return profile.estimate_power(level)

    def get_latest_reading(self, actuator_id: int) -> EnergyReading | None:
        """Get the latest energy reading for an actuator"""
        return self.latest_readings.get(actuator_id)

    def get_consumption_stats(self, actuator_id: int, hours: int | None = None) -> ConsumptionStats | None:
        """
        Get consumption statistics for an actuator.

        Args:
            actuator_id: Actuator ID
            hours: Number of hours to analyze (None = all)

        Returns:
            ConsumptionStats or None
        """
        readings = self.readings.get(actuator_id, [])
        if not readings:
            return None

        # Filter by time if specified
        if hours:
            cutoff = datetime.now() - timedelta(hours=hours)
            readings = [r for r in readings if r.timestamp >= cutoff]

        if not readings:
            return None

        # Calculate statistics
        power_values = [r.power for r in readings if r.power is not None]
        if not power_values:
            return None

        total_energy_kwh = 0.0
        if readings[-1].energy and readings[0].energy:
            total_energy_kwh = readings[-1].energy - readings[0].energy

        average_power = sum(power_values) / len(power_values)
        peak_power = max(power_values)

        # Calculate runtime (time when power > 0)
        runtime_hours = sum(1 for r in readings if r.power and r.power > 0) / (3600 / 60)  # Assuming 1-minute intervals

        cost = total_energy_kwh * self.electricity_rate

        return ConsumptionStats(
            actuator_id=actuator_id,
            total_energy_kwh=total_energy_kwh,
            average_power_watts=average_power,
            peak_power_watts=peak_power,
            runtime_hours=runtime_hours,
            cost_estimate=cost,
        )

    def get_total_power_consumption(self, actuator_ids: list[int]) -> float:
        """
        Get total current power consumption across multiple actuators.

        Args:
            actuator_ids: List of actuator IDs to sum

        Returns:
            Total power consumption in watts
        """
        total = 0.0
        for actuator_id in actuator_ids:
            latest = self.latest_readings.get(actuator_id)
            if latest and latest.power:
                total += latest.power
        return total

    def get_cost_estimate(self, actuator_id: int, period: str = "daily") -> dict[str, float]:
        """
        Get cost estimates for different periods.

        Args:
            actuator_id: Actuator ID
            period: 'daily', 'weekly', 'monthly', 'yearly'

        Returns:
            Dictionary with cost estimates
        """
        # Get 24-hour stats
        stats = self.get_consumption_stats(actuator_id, hours=24)
        if not stats:
            return {"cost": 0.0, "energy_kwh": 0.0}

        daily_kwh = stats.total_energy_kwh
        daily_cost = stats.cost_estimate

        # Extrapolate to other periods
        multipliers = {"daily": 1, "weekly": 7, "monthly": 30, "yearly": 365}

        multiplier = multipliers.get(period, 1)

        return {
            "cost": round(daily_cost * multiplier, 2),
            "energy_kwh": round(daily_kwh * multiplier, 3),
            "period": period,
        }

    def register_power_threshold_callback(self, callback: Callable[[int, float], None]) -> None:
        """
        Register callback for power threshold alerts.

        Callback signature: callback(actuator_id: int, power: float)
        """
        self.power_threshold_callbacks.append(callback)

    def _check_power_thresholds(self, actuator_id: int, power: float) -> None:
        """Check if power exceeds thresholds and trigger callbacks"""
        # Example: Alert if power exceeds 2000W
        if power > 2000:
            for callback in self.power_threshold_callbacks:
                try:
                    callback(actuator_id, power)
                except Exception as e:
                    logger.error(f"Error in power threshold callback: {e}")

    def clear_readings(self, actuator_id: int) -> None:
        """Clear readings for an actuator"""
        if actuator_id in self.readings:
            del self.readings[actuator_id]
        if actuator_id in self.latest_readings:
            del self.latest_readings[actuator_id]
        logger.info(f"Cleared energy readings for actuator {actuator_id}")

    def get_efficiency_metrics(self, actuator_id: int) -> dict[str, Any] | None:
        """
        Calculate efficiency metrics for an actuator.

        Returns:
            Dictionary with efficiency metrics
        """
        readings = self.readings.get(actuator_id, [])
        if len(readings) < 10:
            return None

        # Power factor analysis
        power_factors = [r.power_factor for r in readings if r.power_factor]
        avg_power_factor = sum(power_factors) / len(power_factors) if power_factors else None

        # Voltage stability
        voltages = [r.voltage for r in readings if r.voltage]
        voltage_variance = 0.0
        if len(voltages) > 1:
            avg_voltage = sum(voltages) / len(voltages)
            voltage_variance = sum((v - avg_voltage) ** 2 for v in voltages) / len(voltages)

        return {
            "average_power_factor": round(avg_power_factor, 3) if avg_power_factor else None,
            "voltage_variance": round(voltage_variance, 2),
            "reading_count": len(readings),
        }

    def _persist_reading(
        self,
        reading: EnergyReading,
        plant_id: int = None,
        unit_id: int = None,
        growth_stage: str = None,
        source_type: str = "unknown",
    ) -> None:
        """
        Persist energy reading to EnergyConsumption table.

        Args:
            reading: EnergyReading to persist
            plant_id: Optional plant ID for lifecycle tracking
            unit_id: Growth unit ID
            growth_stage: Optional current growth stage
            source_type: Device source type ('zigbee', 'gpio', 'mqtt', 'wifi', 'estimated')
        """
        try:
            if reading.power is None:
                return

            timestamp = reading.timestamp.isoformat()
            self.analytics_repo.save_energy_consumption(
                monitor_id=reading.actuator_id,
                timestamp=timestamp,
                voltage=reading.voltage,
                current=reading.current,
                power_watts=reading.power,
                energy_kwh=reading.energy,
                frequency=reading.frequency,
                power_factor=reading.power_factor,
                temperature=reading.temperature,
            )
        except Exception as e:
            logger.error(f"Failed to persist energy reading: {e}")

    def estimate_daily_cost(self, power_watts: float) -> float:
        """
        Estimate daily electricity cost from current power consumption.

        Assumes continuous operation for 24 hours. For actual costs, use
        consumption statistics from real readings.

        Args:
            power_watts: Current power consumption in watts

        Returns:
            Estimated daily cost in local currency (based on electricity_rate)
        """
        if not power_watts or power_watts <= 0:
            return 0.0

        # Calculate daily kWh assuming continuous operation
        daily_kwh = (power_watts * 24) / 1000

        # Apply electricity rate
        return round(daily_kwh * self.electricity_rate, 2)

    def get_energy_summary(self, energy_reading: dict[str, Any] | None) -> dict[str, Any]:
        """
        Build energy dashboard summary from latest power reading.

        Combines current power, estimated daily cost, and trend information
        into a standardized dashboard format.

        Args:
            energy_reading: Latest energy reading dict with keys:
                - power_watts: Current power consumption
                - timestamp: Reading timestamp
                - (optional) trend: Trend indicator

        Returns:
            Dashboard summary dict with keys:
                - current_power_watts: Current power (0.0 if no reading)
                - daily_cost: Estimated daily cost
                - trend: Trend indicator ('stable', 'rising', 'falling')
                - timestamp: Reading timestamp or None
        """
        if not energy_reading:
            return {"current_power_watts": 0.0, "daily_cost": 0.0, "trend": "unknown", "timestamp": None}

        power_watts = energy_reading.get("power_watts", 0.0)

        return {
            "current_power_watts": round(power_watts, 2) if power_watts else 0.0,
            "daily_cost": self.estimate_daily_cost(power_watts),
            "trend": energy_reading.get("trend", "stable"),
            "timestamp": energy_reading.get("timestamp"),
        }


# Default power profiles for common actuators
DEFAULT_POWER_PROFILES = {
    "grow_light": PowerProfile(
        actuator_type="grow_light", rated_power_watts=150.0, standby_power_watts=2.0, efficiency_factor=0.9
    ),
    "water_pump": PowerProfile(
        actuator_type="water_pump", rated_power_watts=50.0, standby_power_watts=1.0, efficiency_factor=0.85
    ),
    "fan": PowerProfile(
        actuator_type="fan",
        rated_power_watts=30.0,
        standby_power_watts=0.5,
        efficiency_factor=0.9,
        power_curve={0: 0.5, 25: 10.0, 50: 18.0, 75: 24.0, 100: 30.0},
    ),
    "heater": PowerProfile(
        actuator_type="heater", rated_power_watts=1500.0, standby_power_watts=5.0, efficiency_factor=0.98
    ),
    "humidifier": PowerProfile(
        actuator_type="humidifier", rated_power_watts=40.0, standby_power_watts=1.0, efficiency_factor=0.88
    ),
}
