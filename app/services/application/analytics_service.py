"""
Analytics Service

Unified analytics service for both sensor and actuator data.
Provides comprehensive analytics including:
- Sensor readings and statistics
- Actuator energy consumption analysis
- Cost trends and optimization recommendations
- Anomaly detection (sensors and actuators)
- Predictive analytics
- Comparative analysis
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Optional

from app.domain.photoperiod import Photoperiod
from app.services.application.threshold_service import ThresholdService
from app.services.hardware.scheduling_service import SchedulingService
from app.utils.cache import CacheRegistry, TTLCache
from app.utils.time import coerce_datetime, utc_now
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.repositories.growth import GrowthRepository

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Unified analytics service for sensor and actuator data.

    Consolidates all analytics methods for better organization:
    - Sensor analytics (temperature, humidity, soil moisture)
    - Actuator analytics (energy, power, efficiency)
    - Cost analysis and trends
    - Optimization recommendations
    - Anomaly detection
    - Predictive analytics
    """

    def __init__(
        self,
        repository: AnalyticsRepository,
        device_repository: DeviceRepository | None = None,
        growth_repository: GrowthRepository | None = None,
        threshold_service: Optional["ThresholdService"] = None,
        scheduling_service: Optional["SchedulingService"] = None,
    ):
        """
        Initialize analytics service.

        Args:
            repository: AnalyticsRepository for sensor data
            device_repository: DeviceRepository for actuator data (optional)
            growth_repository: GrowthRepository for unit data (optional)
            threshold_service: ThresholdService for centralized threshold reads (optional)
            scheduling_service: SchedulingService for device schedules (optional)
        """
        self.repository = repository
        self.device_repository = device_repository
        self.device_repo = device_repository  # Alias for internal use
        self.growth_repo = growth_repository
        self.threshold_service = threshold_service
        self.scheduling_service = scheduling_service
        self.electricity_rate = 0.12  # $/kWh - should come from config
        self.logger = logger

        # Initialize caches for frequently accessed data
        self._latest_reading_cache = TTLCache(enabled=True, ttl_seconds=5, maxsize=32)
        self._history_cache = TTLCache(enabled=True, ttl_seconds=30, maxsize=128)

        # Register caches for monitoring
        cache_registry = CacheRegistry.get_instance()
        try:
            cache_registry.register("analytics_service.latest_readings", self._latest_reading_cache)
            cache_registry.register("analytics_service.history", self._history_cache)
        except ValueError:
            # Cache already registered (e.g., in tests with multiple instances)
            logger.debug("Analytics caches already registered")

    def get_latest_sensor_reading(self, unit_id: int | None = None) -> dict[str, Any] | None:
        """
        Get the most recent sensor reading, optionally filtered by unit.

        Cached for 5 seconds to reduce database load on frequent dashboard refreshes.

        Args:
            unit_id: Optional unit ID to filter by

        Returns:
            Dictionary with latest sensor data or None if no readings found
        """
        cache_key = f"latest_sensor_{unit_id}"

        def loader():
            try:
                logger.debug(f"Fetching latest sensor reading for unit_id={unit_id}")
                reading = self.repository.get_latest_sensor_reading(unit_id=unit_id)

                if reading:
                    logger.debug(f"Found latest sensor reading with timestamp: {reading.get('timestamp')}")
                else:
                    logger.debug("No sensor readings found")

                return reading
            except Exception as e:
                logger.error(f"Error fetching latest sensor reading: {e}")
                raise

        return self._latest_reading_cache.get(cache_key, loader)

    def get_latest_energy_reading(self) -> dict[str, Any] | None:
        """
        Get the most recent energy reading.

        Returns:
            Dictionary with latest energy data or None if no readings found
        """
        try:
            logger.debug("Fetching latest energy reading")
            reading = self.repository.get_latest_energy_reading()

            if reading:
                logger.debug(f"Found latest energy reading with timestamp: {reading.get('timestamp')}")
            else:
                logger.debug("No energy readings found")

            return reading
        except Exception as e:
            logger.error(f"Error fetching latest energy reading: {e}")
            raise

    def fetch_sensor_history(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch sensor readings within a date range.

        Cached for 30 seconds to improve performance when multiple endpoints
        request the same time window (common in dashboard/analytics pages).

        Args:
            start_datetime: Start of the time range
            end_datetime: End of the time range
            unit_id: Optional unit filter
            sensor_id: Optional sensor filter
            limit: Optional row cap for DB query

        Returns:
            List of sensor readings in chronological order

        Raises:
            ValueError: If date range is invalid
        """
        # Create cache key from query parameters
        cache_key = f"history_{start_datetime.isoformat()}_{end_datetime.isoformat()}_{unit_id}_{sensor_id}_{limit}"

        def loader():
            try:
                # Validate date range
                if start_datetime >= end_datetime:
                    raise ValueError("Start datetime must be before end datetime")

                logger.debug(f"Fetching sensor history from {start_datetime} to {end_datetime}")

                readings = self.repository.fetch_sensor_history(
                    start_datetime,
                    end_datetime,
                    unit_id=unit_id,
                    sensor_id=sensor_id,
                    limit=limit,
                )
                logger.debug(f"Retrieved {len(readings)} sensor readings")

                return readings
            except ValueError as e:
                logger.warning(f"Invalid date range: {e}")
                raise
            except Exception as e:
                logger.error(f"Error fetching sensor history: {e}")
                raise

        return self._history_cache.get(cache_key, loader)

    def get_sensors_history_enriched(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """
        Fetch sensor history with additional analytics (VPD, photoperiod, DIF).

        Args:
            start_datetime: Start of ranges
            end_datetime: End of range
            unit_id: Optional unit filter
            sensor_id: Optional sensor filter
            limit: Optional record limit

        Returns:
            Dictionary with enriched readings and summary statistics
        """
        try:
            # 1. Fetch raw readings
            readings = self.fetch_sensor_history(
                start_datetime, end_datetime, unit_id=unit_id, sensor_id=sensor_id, limit=limit
            )

            # 2. Resolve Photoperiod for DIF/Light analysis
            photoperiod = None
            if self.scheduling_service and unit_id:
                try:
                    schedules = self.scheduling_service.get_schedules_for_unit(unit_id, device_type="light")
                    if schedules:
                        sched = schedules[0]
                        # Create Photoperiod from schedule start/end times
                        from app.domain.photoperiod import Photoperiod

                        photoperiod = Photoperiod(
                            day_start=sched.start_time or "06:00",
                            day_end=sched.end_time or "18:00",
                        )
                except Exception as e:
                    self.logger.debug(f"Failed to get photoperiod from schedule: {e}")

            # 3. Process and Enrich
            enriched = []
            temps = []
            humids = []
            vpds = []

            for r in readings:
                # Calculate VPD
                temp = r.get("temperature")
                humid = r.get("humidity")

                # Basic enrichment
                r_enriched = dict(r)

                if temp is not None and humid is not None:
                    from app.utils.psychrometrics import calculate_vpd_kpa

                    vpd = calculate_vpd_kpa(temp, humid)
                    r_enriched["vpd"] = round(vpd, 2)
                    vpds.append(vpd)
                    temps.append(temp)
                    humids.append(humid)

                # Resolve light status if photoperiod available
                if photoperiod and "timestamp" in r:
                    ts = r["timestamp"]
                    if isinstance(ts, str):
                        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    r_enriched["is_light"] = photoperiod.is_schedule_day(ts)

                enriched.append(r_enriched)

            # 4. Calculate Summary
            summary = {
                "count": len(enriched),
                "avg_temp": round(sum(temps) / len(temps), 2) if temps else 0,
                "avg_humid": round(sum(humids) / len(humids), 2) if humids else 0,
                "avg_vpd": round(sum(vpds) / len(vpds), 2) if vpds else 0,
                "min_temp": min(temps) if temps else 0,
                "max_temp": max(temps) if temps else 0,
            }

            return {"readings": enriched, "summary": summary, "unit_id": unit_id, "timestamp": utc_now().isoformat()}
        except Exception as e:
            self.logger.error(f"Error enriching sensor history: {e}", exc_info=True)
            return {"error": str(e)}

    def get_sensor_statistics(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """
        Calculate statistics for sensor readings in a date range.

        Args:
            start_datetime: Start of the time range
            end_datetime: End of the time range
            unit_id: Optional unit filter
            sensor_id: Optional sensor filter
            limit: Optional row cap

        Returns:
            Dictionary with statistical data (count, averages, min/max, etc.)
        """
        try:
            readings = self.fetch_sensor_history(
                start_datetime,
                end_datetime,
                unit_id=unit_id,
                sensor_id=sensor_id,
                limit=limit,
            )

            if not readings:
                return {"count": 0, "start_date": start_datetime.isoformat(), "end_date": end_datetime.isoformat()}

            # Calculate statistics
            count = len(readings)

            # Extract numeric sensor values for statistics
            temperatures = [r.get("temperature") for r in readings if r.get("temperature") is not None]
            humidities = [r.get("humidity") for r in readings if r.get("humidity") is not None]
            soil_moistures = [r.get("soil_moisture") for r in readings if r.get("soil_moisture") is not None]

            stats = {
                "count": count,
                "start_date": start_datetime.isoformat(),
                "end_date": end_datetime.isoformat(),
                "temperature": self._calculate_value_stats(temperatures),
                "humidity": self._calculate_value_stats(humidities),
                "soil_moisture": self._calculate_value_stats(soil_moistures),
            }

            logger.debug(f"Calculated statistics for {count} readings")
            return stats

        except Exception as e:
            logger.error(f"Error calculating sensor statistics: {e}")
            raise

    # ==================== Actuator Energy Analytics ====================

    def get_actuator_energy_cost_trends(self, actuator_id: int, days: int = 7) -> dict[str, Any]:
        """
        Get energy cost trends over time for an actuator.

        Args:
            actuator_id: Actuator identifier
            days: Number of days to analyze (1-365)

        Returns:
            Dictionary with daily costs, totals, and trend direction
        """
        if not self.device_repository:
            logger.error("DeviceRepository not available for actuator analytics")
            return {
                "actuator_id": actuator_id,
                "error": "DeviceRepository not configured",
                "daily_costs": [],
                "total_cost": 0.0,
            }

        try:
            # Get power readings for the period
            hours = days * 24
            readings = self.device_repository.get_actuator_power_readings(actuator_id, limit=10000, hours=hours)

            if not readings:
                return {
                    "actuator_id": actuator_id,
                    "period_days": days,
                    "daily_costs": [],
                    "total_cost": 0.0,
                    "total_energy_kwh": 0.0,
                    "average_daily_cost": 0.0,
                    "trend": "no_data",
                }

            # Group readings by day
            daily_data = {}

            for reading in readings:
                reading_date = datetime.fromisoformat(reading["created_at"]).date()
                if reading_date not in daily_data:
                    daily_data[reading_date] = {"power_readings": [], "energy_kwh": 0.0}

                if reading.get("power_watts"):
                    daily_data[reading_date]["power_readings"].append(reading["power_watts"])

                if reading.get("energy_kwh"):
                    daily_data[reading_date]["energy_kwh"] = reading["energy_kwh"]

            # Calculate daily costs
            daily_costs = []
            for date in sorted(daily_data.keys()):
                data = daily_data[date]

                # Estimate daily energy if not available
                if data["energy_kwh"] == 0.0 and data["power_readings"]:
                    avg_power = sum(data["power_readings"]) / len(data["power_readings"])
                    hours_covered = len(data["power_readings"]) / 60  # 1-minute intervals
                    data["energy_kwh"] = (avg_power * hours_covered) / 1000.0

                cost = data["energy_kwh"] * self.electricity_rate

                daily_costs.append(
                    {
                        "date": date.isoformat(),
                        "energy_kwh": round(data["energy_kwh"], 3),
                        "cost": round(cost, 2),
                        "avg_power_watts": round(sum(data["power_readings"]) / len(data["power_readings"]), 2)
                        if data["power_readings"]
                        else 0.0,
                    }
                )

            # Calculate totals and trends
            total_cost = sum(d["cost"] for d in daily_costs)
            total_energy = sum(d["energy_kwh"] for d in daily_costs)
            avg_daily_cost = total_cost / len(daily_costs) if daily_costs else 0.0

            # Determine trend
            trend = "stable"
            if len(daily_costs) >= 4:
                mid = len(daily_costs) // 2
                first_half_avg = sum(d["cost"] for d in daily_costs[:mid]) / mid
                second_half_avg = sum(d["cost"] for d in daily_costs[mid:]) / (len(daily_costs) - mid)

                if second_half_avg > first_half_avg * 1.1:
                    trend = "increasing"
                elif second_half_avg < first_half_avg * 0.9:
                    trend = "decreasing"

            logger.info(
                f"📊 Energy cost trends for actuator {actuator_id}: {len(daily_costs)} days, ${total_cost:.2f} total"
            )

            return {
                "actuator_id": actuator_id,
                "period_days": days,
                "daily_costs": daily_costs,
                "total_cost": round(total_cost, 2),
                "total_energy_kwh": round(total_energy, 3),
                "average_daily_cost": round(avg_daily_cost, 2),
                "trend": trend,
                "electricity_rate_kwh": self.electricity_rate,
            }

        except Exception as e:
            logger.error(f"Error calculating cost trends for actuator {actuator_id}: {e}", exc_info=True)
            return {"actuator_id": actuator_id, "error": str(e), "daily_costs": [], "total_cost": 0.0}

    def get_actuator_optimization_recommendations(self, actuator_id: int) -> list[dict[str, Any]]:
        """
        Get energy optimization recommendations for an actuator.

        Analyzes power consumption patterns and provides actionable
        recommendations to reduce costs and improve efficiency.

        Args:
            actuator_id: Actuator identifier

        Returns:
            List of optimization recommendations with potential savings
        """
        if not self.device_repository:
            return [
                {
                    "type": "error",
                    "title": "DeviceRepository Not Configured",
                    "description": "Cannot generate recommendations without device repository",
                    "potential_savings": 0.0,
                }
            ]

        try:
            recommendations = []

            # Get recent power readings
            readings = self.device_repository.get_actuator_power_readings(actuator_id, limit=1000, hours=24)

            if not readings:
                return [
                    {
                        "type": "info",
                        "severity": "info",
                        "title": "Insufficient Data",
                        "description": "Not enough power readings to generate recommendations",
                        "potential_savings_kwh": 0.0,
                        "potential_savings_usd": 0.0,
                    }
                ]

            # Analyze power patterns
            power_values = [r["power_watts"] for r in readings if r.get("power_watts")]
            if not power_values:
                return recommendations

            avg_power = sum(power_values) / len(power_values)
            peak_power = max(power_values)
            min_power = min(power_values)

            # 1. Check for high standby power
            standby_readings = [p for p in power_values if p < avg_power * 0.2]
            if standby_readings:
                avg_standby = sum(standby_readings) / len(standby_readings)
                if avg_standby > 5.0:
                    annual_waste_kwh = (avg_standby * 24 * 365) / 1000
                    annual_cost = annual_waste_kwh * self.electricity_rate
                    recommendations.append(
                        {
                            "type": "high_standby_power",
                            "severity": "medium",
                            "title": "High Standby Power Consumption",
                            "description": f"Device consumes {avg_standby:.1f}W when idle. Consider using a smart plug to completely cut power.",
                            "current_value": round(avg_standby, 2),
                            "potential_savings_kwh": round(annual_waste_kwh, 2),
                            "potential_savings_usd": round(annual_cost, 2),
                        }
                    )

            # 2. Check for inefficient operation (high variance)
            if len(power_values) > 10:
                variance = sum((p - avg_power) ** 2 for p in power_values) / len(power_values)
                if variance > avg_power * 0.5:
                    recommendations.append(
                        {
                            "type": "high_power_variance",
                            "severity": "low",
                            "title": "Unstable Power Consumption",
                            "description": "Device shows high power variance. Check for proper calibration or mechanical issues.",
                            "current_value": round(variance, 2),
                            "potential_savings_kwh": 0.0,
                            "potential_savings_usd": 0.0,
                        }
                    )

            # 3. Check power factor
            power_factors = [r["power_factor"] for r in readings if r.get("power_factor")]
            if power_factors:
                avg_pf = sum(power_factors) / len(power_factors)
                if avg_pf < 0.85:
                    recommendations.append(
                        {
                            "type": "low_power_factor",
                            "severity": "medium",
                            "title": "Poor Power Factor",
                            "description": f"Power factor is {avg_pf:.2f}. Consider adding power factor correction.",
                            "current_value": round(avg_pf, 3),
                            "potential_savings_kwh": 0.0,
                            "potential_savings_usd": round(avg_power * 0.05 * self.electricity_rate, 2),
                        }
                    )

            # 4. Check for high peak power
            if peak_power > avg_power * 2:
                recommendations.append(
                    {
                        "type": "high_peak_power",
                        "severity": "low",
                        "title": "High Peak Power Demand",
                        "description": f"Peak power ({peak_power:.1f}W) is {peak_power / avg_power:.1f}x average. Consider load leveling.",
                        "current_value": round(peak_power, 2),
                        "potential_savings_kwh": 0.0,
                        "potential_savings_usd": 0.0,
                    }
                )

            # 5. Check for always-on devices
            on_time_percentage = len([p for p in power_values if p > 10]) / len(power_values)
            if on_time_percentage > 0.9:
                potential_kwh = (avg_power * 24 * 365 * 0.1) / 1000
                recommendations.append(
                    {
                        "type": "always_on_device",
                        "severity": "low",
                        "title": "Device Always On",
                        "description": f"Device is on {on_time_percentage * 100:.0f}% of the time. Consider scheduling.",
                        "current_value": round(on_time_percentage, 3),
                        "potential_savings_kwh": round(potential_kwh, 2),
                        "potential_savings_usd": round(potential_kwh * self.electricity_rate, 2),
                    }
                )

            if not recommendations:
                recommendations.append(
                    {
                        "type": "optimal",
                        "severity": "info",
                        "title": "Optimal Operation",
                        "description": "Device is operating efficiently with no major optimization opportunities.",
                        "current_value": 0.0,
                        "potential_savings_kwh": 0.0,
                        "potential_savings_usd": 0.0,
                    }
                )

            logger.info(f"💡 Generated {len(recommendations)} recommendations for actuator {actuator_id}")
            return recommendations

        except Exception as e:
            logger.error(f"Error generating recommendations for actuator {actuator_id}: {e}", exc_info=True)
            return []

    def detect_actuator_power_anomalies(self, actuator_id: int, hours: int = 24) -> list[dict[str, Any]]:
        """
        Detect power consumption anomalies (spikes, drops, unusual patterns).

        Uses statistical analysis (3-sigma rule) to identify outliers.

        Args:
            actuator_id: Actuator identifier
            hours: Hours to analyze (1-720)

        Returns:
            List of detected anomalies with severity and details
        """
        if not self.device_repository:
            return []

        try:
            anomalies = []
            readings = self.device_repository.get_actuator_power_readings(actuator_id, limit=5000, hours=hours)

            if len(readings) < 10:
                return anomalies

            power_values = [r["power_watts"] for r in readings if r.get("power_watts") is not None]
            if len(power_values) < 10:
                return anomalies

            # Calculate baseline statistics
            avg_power = sum(power_values) / len(power_values)
            variance = sum((p - avg_power) ** 2 for p in power_values) / len(power_values)
            std_dev = variance**0.5

            # Define thresholds
            threshold_spike = avg_power + (3 * std_dev)
            threshold_drop = max(0, avg_power - (3 * std_dev))

            # Detect anomalies
            for i, reading in enumerate(readings):
                power = reading.get("power_watts")
                if power is None:
                    continue

                timestamp = reading.get("created_at", "")

                # Power spike
                if power > threshold_spike:
                    anomalies.append(
                        {
                            "type": "power_spike",
                            "severity": "major" if power > threshold_spike * 1.5 else "minor",
                            "timestamp": timestamp,
                            "value": round(power, 2),
                            "expected_range": f"{round(avg_power - std_dev, 2)}-{round(avg_power + std_dev, 2)}W",
                            "deviation_percent": round(((power - avg_power) / avg_power) * 100, 1),
                            "description": f"Power spike: {power:.1f}W (normal: {avg_power:.1f}W)",
                        }
                    )

                # Power drop
                elif power < threshold_drop and avg_power > 10:
                    anomalies.append(
                        {
                            "type": "power_drop",
                            "severity": "minor",
                            "timestamp": timestamp,
                            "value": round(power, 2),
                            "expected_range": f"{round(avg_power - std_dev, 2)}-{round(avg_power + std_dev, 2)}W",
                            "deviation_percent": round(((avg_power - power) / avg_power) * 100, 1),
                            "description": f"Power drop: {power:.1f}W (normal: {avg_power:.1f}W)",
                        }
                    )

                # Sudden change
                if i > 0:
                    prev_power = readings[i - 1].get("power_watts")
                    if prev_power is not None and prev_power > 0:
                        change_percent = abs((power - prev_power) / prev_power) * 100
                        if change_percent > 200:
                            anomalies.append(
                                {
                                    "type": "sudden_change",
                                    "severity": "minor",
                                    "timestamp": timestamp,
                                    "value": round(power, 2),
                                    "previous_value": round(prev_power, 2),
                                    "change_percent": round(change_percent, 1),
                                    "description": f"Sudden change: {prev_power:.1f}W → {power:.1f}W",
                                }
                            )

            # Detect extended outages
            zero_streak = 0
            for reading in readings:
                power = reading.get("power_watts", 0)
                if power < 1.0:
                    zero_streak += 1
                else:
                    if zero_streak > 60 and avg_power > 10:
                        anomalies.append(
                            {
                                "type": "extended_outage",
                                "severity": "major",
                                "timestamp": reading.get("created_at", ""),
                                "duration_minutes": zero_streak,
                                "description": f"Device off/disconnected for {zero_streak} minutes",
                            }
                        )
                    zero_streak = 0

            logger.info(f"🔍 Detected {len(anomalies)} power anomalies for actuator {actuator_id}")
            return anomalies

        except Exception as e:
            logger.error(f"Error detecting anomalies for actuator {actuator_id}: {e}", exc_info=True)
            return []

    def get_comparative_energy_analysis(self, unit_id: int | None = None) -> dict[str, Any]:
        """
        Get comparative energy analysis across actuators.

        Analyzes:
        - Consumption breakdown by device type
        - Efficiency rankings
        - Individual consumer performance

        Args:
            unit_id: Optional unit ID to filter by

        Returns:
            Dictionary with comparative statistics and rankings
        """
        if not self.device_repo:
            return {"error": "DeviceRepository not configured"}

        try:
            # 1. Fetch relevant actuators
            actuators = (
                self.device_repo.list_actuators(unit_id=unit_id) if unit_id else self.device_repo.list_actuators()
            )

            total_power = 0.0
            total_daily_cost = 0.0
            by_type = {}
            top_consumers = []

            # 2. Collect data for each actuator
            for actuator in actuators:
                try:
                    act_id = actuator.get("actuator_id")
                    act_type = actuator.get("actuator_type", "unknown")

                    # Get latest power
                    power_readings = self.device_repo.get_actuator_power_readings(act_id, limit=1)
                    p_watts = power_readings[0].get("power_watts", 0.0) if power_readings else 0.0
                    total_power += p_watts

                    # Get 24h cost
                    costs = self.get_actuator_energy_cost_trends(act_id, days=1)
                    cost_val = costs.get("total_cost", 0.0)
                    total_daily_cost += cost_val

                    # Aggregation by type
                    if act_type not in by_type:
                        by_type[act_type] = {"count": 0, "power": 0.0, "cost": 0.0}
                    by_type[act_type]["count"] += 1
                    by_type[act_type]["power"] += p_watts
                    by_type[act_type]["cost"] += cost_val

                    top_consumers.append(
                        {
                            "actuator_id": act_id,
                            "name": actuator.get("name"),
                            "type": act_type,
                            "power_watts": round(p_watts, 1),
                            "daily_cost": round(cost_val, 2),
                        }
                    )
                except Exception as e:
                    self.logger.warning(f"Error comparing actuator {act_id}: {e}")

            # 3. Sort rankings
            top_consumers.sort(key=lambda x: x["power_watts"], reverse=True)

            # 4. Final structure
            analysis = {
                "summary": {
                    "total_actuators": len(actuators),
                    "monitored_actuators": len(top_consumers),
                    "total_power_consumption": round(total_power, 1),
                    "total_daily_cost": round(total_daily_cost, 2),
                    "average_actuator_power": round(total_power / len(actuators), 1) if actuators else 0,
                },
                "by_type": by_type,
                "top_consumers": top_consumers[:5],
                "efficiency_rankings": top_consumers,  # Same sorted list for now
                "unit_id": unit_id,
                "timestamp": utc_now().isoformat(),
            }

            logger.info(f"📊 Generated comparative analysis for unit {unit_id or 'all'}")
            return analysis

        except Exception as e:
            logger.error(f"Error generating comparative analysis: {e}", exc_info=True)
            return {"error": str(e)}

    def get_multi_unit_analytics_overview(self) -> dict[str, Any]:
        """
        Compare environmental conditions and energy usage across all units.

        Returns:
            Dictionary with per-unit statistics and cross-unit rankings.
        """
        if not self.growth_repo:
            return {"error": "GrowthRepository not configured"}

        try:
            # 1. Fetch all units
            units = self.growth_repo.list_units()
            comparisons = []

            for unit in units:
                unit_id = unit.get("unit_id")
                if unit_id is None:
                    continue

                try:
                    # Get latest sensor reading for unit
                    latest_sensor = self.get_latest_sensor_reading(unit_id=unit_id)

                    # Get energy comparison for unit
                    energy_comparison = self.get_comparative_energy_analysis(unit_id)

                    comparisons.append(
                        {
                            "unit_id": unit_id,
                            "unit_name": unit.get("name"),
                            "environment": latest_sensor,
                            "energy": energy_comparison,
                        }
                    )
                except Exception as e:
                    self.logger.warning(f"Could not get comparison for unit {unit_id}: {e}")

            return {"units": comparisons, "total_units": len(comparisons), "timestamp": utc_now().isoformat()}
        except Exception as e:
            self.logger.error(f"Error generating multi-unit analytics overview: {e}", exc_info=True)
            return {"error": str(e)}

    def get_actuators_analytics_overview(self, unit_id: int | None = None) -> dict[str, Any]:
        """
        Get overview of analytics for all actuators in a unit.

        Args:
            unit_id: Optional unit ID filter

        Returns:
            Dictionary with aggregated results for all actuators
        """
        if not self.device_repo:
            return {"error": "DeviceRepository not configured"}

        try:
            # 1. Fetch relevant actuators
            actuators = (
                self.device_repo.list_actuators(unit_id=unit_id) if unit_id else self.device_repo.list_actuators()
            )

            results = []
            for actuator in actuators:
                act_id = actuator.get("actuator_id")
                if act_id is None:
                    continue

                try:
                    # Get dashboard for each actuator
                    dash = self.get_actuator_energy_dashboard(act_id)
                    results.append(dash)
                except Exception as e:
                    self.logger.warning(f"Error enriching actuator {act_id}: {e}")

            return {"unit_id": unit_id, "count": len(results), "actuators": results, "timestamp": utc_now().isoformat()}
        except Exception as e:
            self.logger.error(f"Error generating actuators overview: {e}", exc_info=True)
            return {"error": str(e)}

    def get_actuator_energy_dashboard(self, actuator_id: int) -> dict[str, Any]:
        """
        Get comprehensive energy dashboard data for an actuator.

        Combines multiple analytics into a single dashboard view.

        Args:
            actuator_id: Actuator identifier

        Returns:
            Dictionary with current status, costs, recommendations, anomalies
        """
        if not self.device_repository:
            return {"actuator_id": actuator_id, "error": "DeviceRepository not configured"}

        try:
            # Get latest power reading
            power_readings = self.device_repository.get_actuator_power_readings(actuator_id, limit=1)
            current_power = power_readings[0] if power_readings else None

            # Get trends
            daily_trends = self.get_actuator_energy_cost_trends(actuator_id, days=1)
            weekly_trends = self.get_actuator_energy_cost_trends(actuator_id, days=7)

            # Get recommendations
            recommendations = self.get_actuator_optimization_recommendations(actuator_id)

            # Get anomalies
            anomalies = self.detect_actuator_power_anomalies(actuator_id, hours=24)

            dashboard = {
                "actuator_id": actuator_id,
                "current_status": {
                    "power_watts": current_power.get("power_watts") if current_power else 0.0,
                    "voltage": current_power.get("voltage") if current_power else None,
                    "current": current_power.get("current") if current_power else None,
                    "timestamp": current_power.get("created_at") if current_power else None,
                },
                "daily_summary": {
                    "total_cost": daily_trends.get("total_cost", 0.0),
                    "total_energy_kwh": daily_trends.get("total_energy_kwh", 0.0),
                    "trend": daily_trends.get("trend", "unknown"),
                },
                "weekly_summary": {
                    "total_cost": weekly_trends.get("total_cost", 0.0),
                    "total_energy_kwh": weekly_trends.get("total_energy_kwh", 0.0),
                    "average_daily_cost": weekly_trends.get("average_daily_cost", 0.0),
                    "trend": weekly_trends.get("trend", "unknown"),
                },
                "optimization": {
                    "recommendations_count": len(recommendations),
                    "high_priority": len([r for r in recommendations if r.get("severity") in ["high", "critical"]]),
                    "total_potential_savings_usd": sum(r.get("potential_savings_usd", 0) for r in recommendations),
                    "top_recommendations": recommendations[:3],
                },
                "anomalies": {
                    "count_24h": len(anomalies),
                    "critical": len([a for a in anomalies if a.get("severity") == "critical"]),
                    "major": len([a for a in anomalies if a.get("severity") == "major"]),
                    "recent": anomalies[:5],
                },
            }

            logger.info(f"📊 Generated energy dashboard for actuator {actuator_id}")
            return dashboard

        except Exception as e:
            logger.error(f"Error generating dashboard for actuator {actuator_id}: {e}", exc_info=True)
            return {"actuator_id": actuator_id, "error": str(e)}

    def get_environmental_dashboard_summary(self, unit_id: int | None = None) -> dict[str, Any]:
        """
        Get environmental conditions summary for dashboard.

        Args:
            unit_id: Optional unit filter

        Returns:
            Dictionary with latest conditions, 24h stats, and timestamp.
        """
        try:
            end = utc_now()
            start = end - timedelta(hours=24)

            latest = self.get_latest_sensor_reading(unit_id=unit_id)
            stats = self.get_sensor_statistics(start, end, unit_id=unit_id)

            return {"unit_id": unit_id, "current": latest, "daily_stats": stats, "timestamp": end.isoformat()}
        except Exception as e:
            self.logger.error(f"Error generating environmental summary: {e}", exc_info=True)
            return {"error": str(e)}

    def get_energy_dashboard_summary(self, unit_id: int | None = None, days: int = 7) -> dict[str, Any]:
        """
        Get aggregated energy consumption summary across multiple actuators.

        Calculates:
        - Total costs for all actuators in a unit or across all units
        - Top performing/consuming devices
        - Projections (daily, monthly)
        - Current combined power consumption

        Args:
            unit_id: Optional unit filter
            days: Days to analyze

        Returns:
            Dictionary with energy totals, top consumers, and projections
        """
        if not self.device_repo:
            return {"error": "DeviceRepository not configured"}

        try:
            # 1. Fetch relevant actuators
            actuators = (
                self.device_repo.list_actuators(unit_id=unit_id) if unit_id else self.device_repo.list_actuators()
            )

            total_cost = 0.0
            device_costs = []

            # 2. Aggregate costs
            for actuator in actuators:
                try:
                    act_id = actuator.get("actuator_id")
                    if act_id is None:
                        continue

                    costs = self.get_actuator_energy_cost_trends(act_id, days)
                    cost_val = costs.get("total_cost", 0.0)
                    total_cost += cost_val

                    device_costs.append(
                        {
                            "actuator_id": act_id,
                            "name": actuator.get("name"),
                            "type": actuator.get("actuator_type"),
                            "cost": round(cost_val, 2),
                        }
                    )
                except Exception as e:
                    self.logger.warning(f"Error calculating cost for actuator {actuator.get('actuator_id')}: {e}")

            # Sort by cost
            device_costs.sort(key=lambda x: x["cost"], reverse=True)

            # 3. Projections
            daily_cost = total_cost / days if days > 0 else 0
            monthly_cost = daily_cost * 30

            # 4. Current power (Sum from latest readings)
            # Use ThreadPoolExecutor for concurrent power reading fetch if many actuators
            current_power = 0.0
            for actuator in actuators:
                try:
                    act_id = actuator.get("actuator_id")
                    power_readings = self.device_repo.get_actuator_power_readings(act_id, limit=1)
                    if power_readings:
                        current_power += power_readings[0].get("power_watts", 0.0)
                except Exception:
                    pass

            return {
                "unit_id": unit_id,
                "period_days": days,
                "total_cost": round(total_cost, 2),
                "daily_cost": round(daily_cost, 2),
                "monthly_cost": round(monthly_cost, 2),
                "current_power": round(current_power, 1),
                "daily_energy_kwh": round(current_power * 24 / 1000, 3) if current_power else 0,
                "weekly_energy_kwh": round(current_power * 24 * 7 / 1000, 3) if current_power else 0,
                "total_devices": len(actuators),
                "top_consumers": device_costs[:10],
                "timestamp": utc_now().isoformat(),
            }
        except Exception as e:
            self.logger.error(f"Error generating energy dashboard summary: {e}", exc_info=True)
            return {"error": str(e)}

    # ==================== Predictive Analytics (Phase 5) ====================

    def predict_device_failure(self, actuator_id: int, days_ahead: int = 7) -> dict[str, Any]:
        """
        Predict probability of device failure based on historical patterns.

        Uses simple heuristics for now - can be enhanced with ML models.

        Args:
            actuator_id: Actuator identifier
            days_ahead: Prediction window in days

        Returns:
            Dictionary with failure probability and risk factors
        """
        if not self.device_repository:
            return {"error": "DeviceRepository not configured"}

        try:
            # Get health history
            health_history = self.device_repository.get_actuator_health_history(actuator_id, limit=30)
            anomalies = self.device_repository.get_actuator_anomalies(actuator_id, limit=100)

            if not health_history:
                return {
                    "actuator_id": actuator_id,
                    "failure_probability": 0.0,
                    "risk_level": "unknown",
                    "confidence": 0.0,
                    "message": "Insufficient historical data",
                }

            # Calculate risk factors
            risk_score = 0.0
            risk_factors = []

            # 1. Health score trend
            if len(health_history) >= 2:
                recent_avg = sum(h.get("health_score", 100) for h in health_history[:5]) / min(5, len(health_history))
                older_avg = sum(h.get("health_score", 100) for h in health_history[-5:]) / min(5, len(health_history))

                if recent_avg < older_avg * 0.9:  # 10% decline
                    risk_score += 0.3
                    risk_factors.append(
                        {
                            "factor": "declining_health",
                            "description": f"Health score declining: {older_avg:.1f} → {recent_avg:.1f}",
                            "impact": "high",
                        }
                    )

            # 2. Recent anomalies
            recent_anomalies = [a for a in anomalies if a.get("resolved_at") is None]
            if len(recent_anomalies) > 5:
                risk_score += 0.4
                risk_factors.append(
                    {
                        "factor": "high_anomaly_count",
                        "description": f"{len(recent_anomalies)} unresolved anomalies",
                        "impact": "high",
                    }
                )

            # 3. Error rate
            if health_history:
                latest = health_history[0]
                total_ops = latest.get("total_operations", 0)
                failed_ops = latest.get("failed_operations", 0)
                if total_ops > 0:
                    error_rate = failed_ops / total_ops
                    if error_rate > 0.1:  # >10% error rate
                        risk_score += 0.3
                        risk_factors.append(
                            {
                                "factor": "high_error_rate",
                                "description": f"Error rate: {error_rate * 100:.1f}%",
                                "impact": "medium",
                            }
                        )

            # Calculate failure probability
            failure_probability = min(1.0, risk_score)

            # Determine risk level
            if failure_probability < 0.2:
                risk_level = "low"
            elif failure_probability < 0.5:
                risk_level = "medium"
            elif failure_probability < 0.8:
                risk_level = "high"
            else:
                risk_level = "critical"

            confidence = min(1.0, len(health_history) / 30.0)  # Based on data availability

            logger.info(f"🔮 Failure prediction for actuator {actuator_id}: {failure_probability:.1%} ({risk_level})")

            return {
                "actuator_id": actuator_id,
                "failure_probability": round(failure_probability, 3),
                "risk_level": risk_level,
                "risk_factors": risk_factors,
                "confidence": round(confidence, 2),
                "prediction_window_days": days_ahead,
                "recommendation": self._get_maintenance_recommendation(risk_level),
            }

        except Exception as e:
            logger.error(f"Error predicting failure for actuator {actuator_id}: {e}", exc_info=True)
            return {"error": str(e)}

    def _get_maintenance_recommendation(self, risk_level: str) -> str:
        """Get maintenance recommendation based on risk level"""
        recommendations = {
            "low": "Continue normal operation. Monitor regularly.",
            "medium": "Schedule preventive maintenance within 30 days.",
            "high": "Schedule maintenance within 7 days. Consider backup plan.",
            "critical": "Immediate maintenance required. Prepare for replacement.",
        }
        return recommendations.get(risk_level, "Insufficient data for recommendation")

    def _calculate_value_stats(self, values: list[float]) -> dict[str, Any]:
        """
        Calculate comprehensive statistics for a list of values.

        Returns:
            count, min, max, avg, median, std_dev, range, trend
        """
        if not values:
            return {
                "count": 0,
                "min": None,
                "max": None,
                "avg": None,
                "median": None,
                "std_dev": None,
                "range": None,
                "trend": "stable",
            }

        count = len(values)
        min_val = min(values)
        max_val = max(values)
        avg = sum(values) / count

        # Median
        sorted_values = sorted(values)
        if count % 2 == 0:
            median = (sorted_values[count // 2 - 1] + sorted_values[count // 2]) / 2
        else:
            median = sorted_values[count // 2]

        # Standard deviation
        variance = sum((v - avg) ** 2 for v in values) / count
        std_dev = variance**0.5

        # Trend detection (compare first half avg to second half avg)
        trend = "stable"
        if count >= 4:
            mid = count // 2
            first_half_avg = sum(values[:mid]) / mid
            second_half_avg = sum(values[mid:]) / (count - mid)
            delta = second_half_avg - first_half_avg
            threshold = std_dev * 0.5 if std_dev > 0 else abs(avg) * 0.05
            if delta > threshold:
                trend = "increasing"
            elif delta < -threshold:
                trend = "decreasing"

        return {
            "count": count,
            "min": round(min_val, 2),
            "max": round(max_val, 2),
            "avg": round(avg, 2),
            "median": round(median, 2),
            "std_dev": round(std_dev, 2),
            "range": round(max_val - min_val, 2),
            "trend": trend,
        }

    # ==================== Environmental Analytics ====================

    def calculate_vpd_with_zones(self, temperature: float | None, humidity: float | None) -> dict[str, Any]:
        """
        Calculate Vapor Pressure Deficit (VPD) with growth stage zone interpretation.

        Uses psychrometrics utility for core VPD calculation, then adds
        zone classification and optimal stage recommendations.

        VPD = SVP × (1 - RH/100)
        where SVP = 0.6108 × exp(17.27 × T / (T + 237.3))

        Optimal VPD zones:
        - <0.4 kPa: Too low (risk of mold, poor transpiration)
        - 0.4-0.8 kPa: Seedling/Clone stage (low transpiration demand)
        - 0.8-1.2 kPa: Vegetative stage (moderate transpiration)
        - 1.2-1.5 kPa: Flowering stage (high transpiration)
        - >1.5 kPa: Too high (stress, leaf damage)

        Args:
            temperature: Temperature in Celsius
            humidity: Relative humidity percentage (0-100)

        Returns:
            Dictionary with:
                - value: VPD in kPa
                - unit: 'kPa'
                - status: 'optimal', 'low', 'high', 'unknown', 'error'
                - zone: Zone classification
                - optimal_for: List of growth stages optimal for this VPD
                - temperature: Input temperature
                - humidity: Input humidity
        """
        if temperature is None or humidity is None:
            return {
                "value": None,
                "unit": "kPa",
                "status": "unknown",
                "zone": "unknown",
                "optimal_for": [],
                "temperature": temperature,
                "humidity": humidity,
            }

        try:
            # Use psychrometrics utility for core calculation
            from app.utils.psychrometrics import calculate_vpd_kpa

            vpd_value = calculate_vpd_kpa(temperature, humidity)
            if vpd_value is None:
                raise ValueError("VPD calculation returned None")

            vpd = round(float(vpd_value), 2)

            # Zone classification and optimal stage determination
            if vpd < 0.4:
                zone = "too_low"
                status = "low"
                optimal_for = []
            elif vpd < 0.8:
                zone = "seedling"
                status = "optimal"
                optimal_for = ["seedling", "clone", "early_veg"]
            elif vpd < 1.2:
                zone = "vegetative"
                status = "optimal"
                optimal_for = ["vegetative", "late_veg"]
            elif vpd < 1.5:
                zone = "flowering"
                status = "optimal"
                optimal_for = ["flowering", "bloom"]
            else:
                zone = "too_high"
                status = "high"
                optimal_for = []

            return {
                "value": vpd,
                "unit": "kPa",
                "status": status,
                "zone": zone,
                "optimal_for": optimal_for,
                "temperature": temperature,
                "humidity": humidity,
            }
        except Exception as e:
            logger.warning(f"Error calculating VPD: {e}")
            return {
                "value": None,
                "unit": "kPa",
                "status": "error",
                "zone": "unknown",
                "optimal_for": [],
                "temperature": temperature,
                "humidity": humidity,
            }

    def format_sensor_chart_data(self, readings: list[dict], interval: str | None = None) -> dict[str, Any]:
        """
        Format sensor readings for chart visualization with optional time-series aggregation.

        Returns data structured for popular chart libraries (Chart.js, Recharts, etc.):
        - timestamps: List of ISO datetime strings
        - temperature: List of temperature values
        - humidity: List of humidity values
        - soil_moisture: List of soil moisture values
        - co2: List of CO2 values
        - voc: List of VOC values

        Supports time-series aggregation for downsampling large datasets:
        - '1min': 1-minute intervals
        - '5min': 5-minute intervals
        - '15min': 15-minute intervals
        - '1hour': 1-hour intervals
        - '1day': 1-day intervals

        Args:
            readings: List of sensor reading dictionaries
            interval: Optional aggregation interval (e.g., '5min', '1hour')

        Returns:
            Dictionary with arrays for each metric, aligned by timestamp
        """
        if not readings:
            return {
                "timestamps": [],
                "temperature": [],
                "humidity": [],
                "soil_moisture": [],
                "lux": [],
                "co2": [],
                "voc": [],
            }

        # Time-series aggregation if interval specified
        if interval:
            readings = self._aggregate_sensor_readings(readings, interval)

        # Align metrics by timestamp and merge duplicates
        by_timestamp: dict[str, dict[str, Any]] = {}
        ordered_keys: list[str] = []

        for row in readings:
            raw_ts = row.get("timestamp")
            if raw_ts is None:
                continue

            parsed = coerce_datetime(raw_ts)
            ts_key = parsed.isoformat() if parsed else str(raw_ts)

            if ts_key not in by_timestamp:
                by_timestamp[ts_key] = {
                    "timestamp": ts_key,
                    "temperature": None,
                    "humidity": None,
                    "soil_moisture": None,
                    "lux": None,
                    "co2": None,
                    "voc": None,
                }
                ordered_keys.append(ts_key)

            entry = by_timestamp[ts_key]

            # Update metrics (last value wins for duplicates)
            if row.get("temperature") is not None:
                entry["temperature"] = row.get("temperature")
            if row.get("humidity") is not None:
                entry["humidity"] = row.get("humidity")
            if row.get("soil_moisture") is not None:
                entry["soil_moisture"] = row.get("soil_moisture")
            if row.get("lux") is not None:
                entry["lux"] = row.get("lux")
            if row.get("co2") is not None:
                entry["co2"] = row.get("co2")
            if row.get("voc") is not None:
                entry["voc"] = row.get("voc")

        # Extract aligned arrays
        timestamps = [by_timestamp[key]["timestamp"] for key in ordered_keys]
        temperature = [by_timestamp[key]["temperature"] for key in ordered_keys]
        humidity = [by_timestamp[key]["humidity"] for key in ordered_keys]
        soil_moisture = [by_timestamp[key]["soil_moisture"] for key in ordered_keys]
        lux = [by_timestamp[key]["lux"] for key in ordered_keys]
        co2 = [by_timestamp[key]["co2"] for key in ordered_keys]
        voc = [by_timestamp[key]["voc"] for key in ordered_keys]

        return {
            "timestamps": timestamps,
            "temperature": temperature,
            "humidity": humidity,
            "soil_moisture": soil_moisture,
            "lux": lux,
            "co2": co2,
            "voc": voc,
        }

    def _aggregate_sensor_readings(self, readings: list[dict], interval: str) -> list[dict]:
        """
        Aggregate sensor readings by time interval (enterprise-grade implementation).

        Uses statistical aggregation (mean for most metrics, last for status fields).
        Handles missing data gracefully and preserves data quality.

        Args:
            readings: List of sensor readings with timestamps
            interval: Aggregation interval ('1min', '5min', '15min', '1hour', '1day')

        Returns:
            List of aggregated readings
        """
        if not readings:
            return []

        from collections import defaultdict

        # Parse interval to timedelta
        interval_map = {
            "1min": timedelta(minutes=1),
            "5min": timedelta(minutes=5),
            "15min": timedelta(minutes=15),
            "30min": timedelta(minutes=30),
            "1hour": timedelta(hours=1),
            "6hour": timedelta(hours=6),
            "1day": timedelta(days=1),
        }

        delta = interval_map.get(interval)
        if not delta:
            logger.warning(f"Unknown interval '{interval}', skipping aggregation")
            return readings

        # Group readings by time bucket
        buckets = defaultdict(list)
        for reading in readings:
            timestamp = coerce_datetime(reading.get("timestamp"))
            if not timestamp:
                continue

            # Round timestamp down to interval bucket
            epoch = int(timestamp.timestamp())
            bucket_epoch = (epoch // int(delta.total_seconds())) * int(delta.total_seconds())
            bucket_key = datetime.fromtimestamp(bucket_epoch, tz=timestamp.tzinfo)

            buckets[bucket_key].append(reading)

        # Aggregate each bucket
        aggregated = []
        for bucket_time in sorted(buckets.keys()):
            bucket_readings = buckets[bucket_time]

            # Aggregate numeric metrics (mean)
            def safe_mean(values):
                valid = [v for v in values if v is not None]
                return sum(valid) / len(valid) if valid else None

            temp_values = [r.get("temperature") for r in bucket_readings]
            humidity_values = [r.get("humidity") for r in bucket_readings]
            moisture_values = [r.get("soil_moisture") for r in bucket_readings]
            light_values = [r.get("lux") for r in bucket_readings]
            co2_values = [r.get("co2") for r in bucket_readings]
            voc_values = [r.get("voc") for r in bucket_readings]

            aggregated_reading = {
                "timestamp": bucket_time.isoformat(),
                "temperature": safe_mean(temp_values),
                "humidity": safe_mean(humidity_values),
                "soil_moisture": safe_mean(moisture_values),
                "lux": safe_mean(light_values),
                "co2": safe_mean(co2_values),
                "voc": safe_mean(voc_values),
                "reading_count": len(bucket_readings),  # Metadata for quality assessment
            }

            aggregated.append(aggregated_reading)

        return aggregated

    def analyze_metric_trends(self, readings: list[dict], days: int) -> dict[str, Any]:
        """
        Analyze environmental trends over time with statistical rigor.

        Provides trend direction (stable/rising/falling), volatility assessment,
        and statistical measures for temperature, humidity, and soil moisture.

        Trend detection methodology:
        - Compare first half average vs second half average
        - Classify as stable if change < 0.5 units
        - Calculate volatility using standard deviation thresholds

        Args:
            readings: List of sensor readings
            days: Number of days analyzed (for context)

        Returns:
            Dictionary with trend analysis for each metric:
                - trend: 'rising', 'falling', 'stable', 'no_data'
                - volatility: 'low', 'medium', 'high', 'unknown'
                - average: Mean value
                - std_dev: Standard deviation
                - change: Difference between first/second half averages
        """
        if not readings:
            return {
                "temperature": {"trend": "no_data", "volatility": "unknown"},
                "humidity": {"trend": "no_data", "volatility": "unknown"},
                "soil_moisture": {"trend": "no_data", "volatility": "unknown"},
            }

        # Extract metric values
        temp_values = [r.get("temperature") for r in readings if r.get("temperature") is not None]
        humidity_values = [r.get("humidity") for r in readings if r.get("humidity") is not None]
        moisture_values = [r.get("soil_moisture") for r in readings if r.get("soil_moisture") is not None]

        def analyze_metric(values):
            """Analyze single metric with trend and volatility."""
            if not values or len(values) < 2:
                return {"trend": "no_data", "volatility": "unknown"}

            # Calculate statistics
            avg = sum(values) / len(values)
            variance = sum((x - avg) ** 2 for x in values) / len(values)
            std_dev = variance**0.5

            # Trend: compare first half vs second half
            mid = len(values) // 2
            first_half_avg = sum(values[:mid]) / len(values[:mid])
            second_half_avg = sum(values[mid:]) / len(values[mid:])
            diff = second_half_avg - first_half_avg

            if abs(diff) < 0.5:
                trend = "stable"
            elif diff > 0:
                trend = "rising"
            else:
                trend = "falling"

            # Volatility: based on standard deviation
            if std_dev < 1.0:
                volatility = "low"
            elif std_dev < 3.0:
                volatility = "medium"
            else:
                volatility = "high"

            return {
                "trend": trend,
                "volatility": volatility,
                "average": round(avg, 2),
                "std_dev": round(std_dev, 2),
                "change": round(diff, 2),
            }

        return {
            "temperature": analyze_metric(temp_values),
            "humidity": analyze_metric(humidity_values),
            "soil_moisture": analyze_metric(moisture_values),
        }

    def calculate_environmental_correlations(self, readings: list[dict]) -> dict[str, Any]:
        """
        Calculate correlations between environmental factors with statistical rigor.

        Analyzes:
        - Temperature-Humidity correlation (Pearson's r)
        - Average VPD and optimal zone classification
        - Sample size for statistical significance assessment

        Statistical notes:
        - Pearson correlation coefficient (r) ranges from -1 to 1
        - |r| < 0.3: weak correlation
        - 0.3 <= |r| < 0.7: moderate correlation
        - |r| >= 0.7: strong correlation
        - Minimum 10 samples required for meaningful analysis

        Args:
            readings: List of sensor readings with temperature and humidity

        Returns:
            Dictionary with:
                - temp_humidity_correlation: Pearson's r coefficient
                - correlation_interpretation: 'weak', 'moderate', 'strong'
                - vpd_average: Average VPD in kPa
                - vpd_status: Optimal zone classification
                - sample_size: Number of samples analyzed
        """
        if not readings or len(readings) < 10:
            return {
                "temp_humidity_correlation": None,
                "correlation_interpretation": "insufficient_data",
                "vpd_average": None,
                "vpd_status": "unknown",
                "sample_size": len(readings) if readings else 0,
            }

        # Extract paired temperature-humidity values
        paired_values = [
            (r.get("temperature"), r.get("humidity"))
            for r in readings
            if r.get("temperature") is not None and r.get("humidity") is not None
        ]

        if len(paired_values) < 10:
            return {
                "temp_humidity_correlation": None,
                "correlation_interpretation": "insufficient_data",
                "vpd_average": None,
                "vpd_status": "unknown",
                "sample_size": len(paired_values),
            }

        temp_values = [pair[0] for pair in paired_values]
        humidity_values = [pair[1] for pair in paired_values]

        # Calculate Pearson correlation coefficient
        n = len(temp_values)
        temp_mean = sum(temp_values) / n
        humidity_mean = sum(humidity_values) / n

        numerator = sum((temp_values[i] - temp_mean) * (humidity_values[i] - humidity_mean) for i in range(n))
        temp_std = (sum((t - temp_mean) ** 2 for t in temp_values)) ** 0.5
        humidity_std = (sum((h - humidity_mean) ** 2 for h in humidity_values)) ** 0.5

        if temp_std == 0 or humidity_std == 0:
            correlation = 0.0
        else:
            correlation = numerator / (temp_std * humidity_std)

        # Interpret correlation strength
        abs_corr = abs(correlation)
        if abs_corr < 0.3:
            interpretation = "weak"
        elif abs_corr < 0.7:
            interpretation = "moderate"
        else:
            interpretation = "strong"

        # Calculate average VPD using psychrometrics utility
        from app.utils.psychrometrics import calculate_vpd_kpa

        vpd_values = []
        for temp, rh in paired_values:
            vpd = calculate_vpd_kpa(temp, rh)
            if vpd is not None:
                vpd_values.append(vpd)

        avg_vpd = sum(vpd_values) / len(vpd_values) if vpd_values else None

        # Classify VPD zone
        if avg_vpd is None:
            vpd_status = "unknown"
        elif avg_vpd < 0.4:
            vpd_status = "too_low"
        elif avg_vpd < 0.8:
            vpd_status = "optimal_seedling"
        elif avg_vpd < 1.2:
            vpd_status = "optimal_vegetative"
        elif avg_vpd < 1.5:
            vpd_status = "optimal_flowering"
        else:
            vpd_status = "too_high"

        return {
            "temp_humidity_correlation": round(correlation, 3),
            "correlation_interpretation": interpretation,
            "vpd_average": round(avg_vpd, 2) if avg_vpd else None,
            "vpd_status": vpd_status,
            "sample_size": n,
        }

    def calculate_environmental_stability(
        self, unit_id: int | None = None, end: datetime | None = None, days: int = 7
    ) -> float:
        """
        Calculate environmental stability score based on temperature and humidity volatility.

        This metric evaluates how stable the growing environment is over a given time period.
        Lower volatility and fewer anomalies result in higher stability scores.

        Args:
            unit_id: Filter for specific unit (None = all units)
            end: End of analysis window (default: now)
            days: Number of days to analyze (default: 7)

        Returns:
            Stability score from 0-100 where:
                - 90-100: Excellent stability (minimal fluctuations)
                - 75-89: Good stability (minor fluctuations)
                - 60-74: Fair stability (moderate fluctuations)
                - 0-59: Poor stability (excessive fluctuations or many anomalies)

        Calculation methodology:
            1. Analyze temperature and humidity trends over time window
            2. Calculate volatility ratios (standard deviation / mean)
            3. Convert volatility to stability scores (inverse relationship)
            4. Count anomalies and apply penalty (2 points per anomaly, max 20)
            5. Return weighted average: (temp_stability + humidity_stability) / 2 - anomaly_penalty

        Example:
            >>> service = AnalyticsService()
            >>> score = service.calculate_environmental_stability(unit_id=1, days=7)
            >>> print(f"Stability: {score:.1f}/100")
            Stability: 87.5/100
        """
        try:
            # Define time window
            window_end = end or utc_now()
            window_start = window_end - timedelta(days=days)

            # Fetch sensor history for analysis
            readings = self.fetch_sensor_history(window_start, window_end, unit_id=unit_id)

            if not readings:
                self.logger.warning(f"No sensor readings for stability calculation (unit_id={unit_id})")
                return 70.0  # Neutral score when no data available

            # Analyze trends to calculate volatility
            trends = self.analyze_metric_trends(readings, days)

            # Extract metrics
            temp_stats = trends.get("temperature", {})
            humidity_stats = trends.get("humidity", {})

            # Calculate volatility ratios (std_dev / avg)
            def get_volatility(stats, default=0.05):
                avg = stats.get("average")
                std_dev = stats.get("std_dev")
                if avg is not None and std_dev is not None and avg != 0:
                    return std_dev / avg
                return default

            temp_volatility = get_volatility(temp_stats)
            humidity_volatility = get_volatility(humidity_stats)

            # Cap maximum volatility for scoring calculation
            temp_volatility = min(0.15, temp_volatility)
            humidity_volatility = min(0.15, humidity_volatility)

            # Convert volatility to stability score (0-100)
            # Temperature: 0.15 volatility = 0 score, 0.0 volatility = 100 score
            # Formula: 100 - (volatility * multiplier)
            temp_stability = max(0, min(100, 100 - (temp_volatility * 500)))
            humidity_stability = max(0, min(100, 100 - (humidity_volatility * 300)))

            # Count anomalies in time window (anomalies indicate instability)
            sensors = (
                self.device_repo.list_sensor_configs(unit_id=unit_id)
                if unit_id
                else self.device_repo.list_sensor_configs()
            )

            # Extract sensor IDs for anomaly query
            sensor_ids: list[int] = []
            for sensor in sensors:
                sensor_id = sensor.get("sensor_id")
                if sensor_id is None:
                    continue
                try:
                    sensor_ids.append(int(sensor_id))
                except (TypeError, ValueError):
                    self.logger.warning(f"Invalid sensor_id format: {sensor_id}")
                    continue

            # Count anomalies across all sensors
            from app.utils.time import sqlite_timestamp

            total_anomalies = self.device_repo.count_anomalies_for_sensors(
                sorted(set(sensor_ids)),
                start=sqlite_timestamp(window_start),
                end=sqlite_timestamp(window_end),
            )

            # Apply anomaly penalty (2 points per anomaly, max 20 point reduction)
            anomaly_penalty = min(20, total_anomalies * 2)

            # Calculate final stability score
            avg_stability = (temp_stability + humidity_stability) / 2
            final_score = max(0, avg_stability - anomaly_penalty)

            self.logger.debug(
                f"Environmental stability calculated: {final_score:.1f} "
                f"(temp={temp_stability:.1f}, humidity={humidity_stability:.1f}, "
                f"anomalies={total_anomalies}, penalty={anomaly_penalty})"
            )

            return final_score

        except Exception as e:
            self.logger.error(f"Error calculating environmental stability: {e}", exc_info=True)
            return 70.0  # Return neutral score on error

    def calculate_energy_efficiency(
        self, unit_id: int | None = None, end: datetime | None = None, days: int = 7, limit: int = 1000
    ) -> float:
        """
        Calculate energy efficiency score based on actuator usage patterns.

        This metric evaluates how efficiently actuators are being used. Optimal efficiency
        balances responsiveness (enough state changes) with stability (not excessive cycling).

        Args:
            unit_id: Filter for specific unit (None = all units)
            end: End of analysis window (default: now)
            days: Number of days to analyze (default: 7)
            limit: Maximum number of actuator states to fetch (default: 1000)

        Returns:
            Efficiency score from 0-100 where:
                - 90-100: Optimal (5-15 state changes per day)
                - 75-89: Good (close to optimal range)
                - 60-74: Fair (somewhat inefficient)
                - 0-59: Poor (too few or too many state changes)

        Calculation methodology:
            1. Fetch recent actuator state changes in time window
            2. Calculate state change frequency (changes per day)
            3. Score based on optimal range:
                - Optimal: 5-15 changes/day = 95 points
                - Too few: <5 changes/day = 70 + (changes * 5)
                - Too many: >15 changes/day = 95 - ((changes - 15) * 3)
            4. Cap score between 0-100

        Rationale:
            - Too few changes: System not responsive to environmental conditions
            - Too many changes: Excessive wear on equipment, energy waste from cycling
            - Optimal range: Balanced responsiveness and equipment longevity

        Example:
            >>> service = AnalyticsService()
            >>> score = service.calculate_energy_efficiency(unit_id=1, days=7)
            >>> print(f"Energy efficiency: {score:.1f}/100")
            Energy efficiency: 92.0/100
        """
        try:
            # Define time window
            window_end = end or utc_now()
            window_start = window_end - timedelta(days=days)

            # Fetch actuator state history
            states = self.device_repo.get_recent_actuator_state(limit=limit, unit_id=unit_id)

            if not states:
                self.logger.warning(f"No actuator states for energy efficiency calculation (unit_id={unit_id})")
                return 75.0  # Neutral score when no data available

            # Filter states to time window
            from app.utils.time import coerce_datetime

            window_states: list[Any] = []
            for state in states:
                # Handle both dict and object state formats
                if isinstance(state, dict):
                    timestamp = coerce_datetime(state.get("timestamp"))
                else:
                    timestamp = coerce_datetime(getattr(state, "timestamp", None))

                if timestamp and window_start <= timestamp <= window_end:
                    window_states.append(state)

            # Need minimum sample size for meaningful analysis
            if len(window_states) < 10:
                self.logger.warning(f"Insufficient actuator states for analysis: {len(window_states)} < 10")
                return 75.0

            # Calculate state change frequency (changes per day)
            window_days = (window_end - window_start).total_seconds() / 86400
            if window_days <= 0:
                self.logger.error("Invalid time window for energy efficiency calculation")
                return 75.0

            changes_per_day = len(window_states) / window_days

            # Score based on optimal range (5-15 changes per day)
            if 5 <= changes_per_day <= 15:
                # Optimal range: high efficiency score
                efficiency = 95
            elif changes_per_day < 5:
                # Too few changes: system not responsive enough
                # Scale from 70 (0 changes) to 95 (5 changes)
                efficiency = 70 + (changes_per_day * 5)
            else:
                # Too many changes: excessive cycling
                # Reduce 3 points for each change above 15/day, minimum 50
                efficiency = max(50, 95 - ((changes_per_day - 15) * 3))

            final_score = min(100, max(0, efficiency))

            self.logger.debug(
                f"Energy efficiency calculated: {final_score:.1f} "
                f"(changes_per_day={changes_per_day:.1f}, window_days={window_days:.1f})"
            )

            return final_score

        except Exception as e:
            self.logger.error(f"Error calculating energy efficiency: {e}", exc_info=True)
            return 75.0  # Return neutral score on error

    def calculate_automation_effectiveness(
        self, unit_id: int | None = None, end: datetime | None = None, hours: int = 24
    ) -> float:
        """
        Calculate automation effectiveness based on anomaly response and actuator uptime.

        This metric evaluates how well the automation system is functioning by measuring
        both the number of anomalies (issues detected) and actuator availability (ability to respond).

        Args:
            unit_id: Filter for specific unit (None = all units)
            end: End of analysis window (default: now)
            hours: Number of hours to analyze (default: 24)

        Returns:
            Effectiveness score from 0-100 where:
                - 90-100: Excellent (no anomalies, high uptime)
                - 75-89: Good (few anomalies, good uptime)
                - 60-74: Fair (moderate anomalies or uptime issues)
                - 0-59: Poor (many anomalies or low uptime)

        Calculation methodology:
            1. Count sensor anomalies in time window
            2. Calculate anomaly score: 90 - (anomalies * 5), minimum 50
            3. Check actuator connection status and calculate uptime percentage
            4. Calculate weighted average: (anomaly_score * 0.6) + (uptime_score * 0.4)
            5. Cap final score between 0-100

        Weighting rationale:
            - Anomaly score (60%): Primary indicator of automation quality
            - Uptime score (40%): Secondary indicator of system availability

        Example:
            >>> service = AnalyticsService()
            >>> score = service.calculate_automation_effectiveness(unit_id=1, hours=24)
            >>> print(f"Automation effectiveness: {score:.1f}/100")
            Automation effectiveness: 88.5/100
        """
        try:
            # Define time window
            window_end = end or utc_now()
            window_start = window_end - timedelta(hours=hours)

            # Get all sensors for anomaly counting
            sensors = (
                self.device_repo.list_sensor_configs(unit_id=unit_id)
                if unit_id
                else self.device_repo.list_sensor_configs()
            )

            # Extract sensor IDs
            sensor_ids: list[int] = []
            for sensor in sensors:
                sensor_id = sensor.get("sensor_id")
                if sensor_id is None:
                    continue
                try:
                    sensor_ids.append(int(sensor_id))
                except (TypeError, ValueError):
                    self.logger.warning(f"Invalid sensor_id format: {sensor_id}")
                    continue

            # Count anomalies in time window
            from app.utils.time import sqlite_timestamp

            anomaly_count = self.device_repo.count_anomalies_for_sensors(
                sorted(set(sensor_ids)),
                start=sqlite_timestamp(window_start),
                end=sqlite_timestamp(window_end),
            )

            # Calculate anomaly score (fewer anomalies = better automation)
            if anomaly_count == 0:
                anomaly_score = 90.0  # High score when no issues detected
            else:
                # Reduce 5 points per anomaly, minimum score of 50
                anomaly_score = max(50, 90 - (anomaly_count * 5))

            # Check actuator uptime (availability to respond to automation triggers)
            from app.services.hardware.actuator_management_service import ActuatorManagementService

            try:
                actuator_service = ActuatorManagementService(self.device_repo)
                actuators = actuator_service.list_actuators()

                # Filter by unit_id if specified
                if unit_id:
                    actuators = [a for a in actuators if a.get("unit_id") == unit_id]

                # Calculate uptime percentage
                if actuators:
                    online_count = sum(1 for a in actuators if a.get("connection_status") == "online")
                    uptime_score = (online_count / len(actuators)) * 100
                else:
                    uptime_score = 80  # Default when no actuators configured

            except Exception as e:
                self.logger.warning(f"Could not fetch actuator status: {e}")
                uptime_score = 80  # Default on error

            # Calculate weighted automation effectiveness score
            # 60% weight on anomaly management, 40% weight on system uptime
            automation_score = (anomaly_score * 0.6) + (uptime_score * 0.4)
            final_score = min(100, max(0, automation_score))

            self.logger.debug(
                f"Automation effectiveness calculated: {final_score:.1f} "
                f"(anomalies={anomaly_count}, anomaly_score={anomaly_score:.1f}, "
                f"uptime_score={uptime_score:.1f})"
            )

            return final_score

        except Exception as e:
            self.logger.error(f"Error calculating automation effectiveness: {e}", exc_info=True)
            return 75.0  # Return neutral score on error

    def calculate_efficiency_scores_concurrent(
        self, unit_id: int | None = None, end: datetime | None = None, include_previous: bool = False
    ) -> dict[str, Any]:
        """
        Calculate all three efficiency component scores concurrently.

        Uses ThreadPoolExecutor to run the three independent calculations in parallel,
        improving performance by ~3x compared to sequential execution.

        Args:
            unit_id: Filter for specific unit (None = all units)
            end: End time for analysis (default: now)
            include_previous: If True, also calculate previous week's scores for trend analysis

        Returns:
            Dictionary with:
                - environmental: Environmental stability score (0-100)
                - energy: Energy efficiency score (0-100)
                - automation: Automation effectiveness score (0-100)
                - previous_environmental: Previous week's environmental score (if include_previous)
                - previous_energy: Previous week's energy score (if include_previous)
                - previous_automation: Previous week's automation score (if include_previous)

        Example:
            >>> service = AnalyticsService(repo, device_repo)
            >>> scores = service.calculate_efficiency_scores_concurrent(unit_id=1)
            >>> overall = scores["environmental"] * 0.4 + scores["energy"] * 0.3 + scores["automation"] * 0.3
            >>> print(f"Overall efficiency: {overall:.1f}/100")
            Overall efficiency: 85.3/100
        """
        window_end = end or utc_now()

        # Define calculation tasks
        tasks = {
            "environmental": (self.calculate_environmental_stability, {"unit_id": unit_id, "end": window_end}),
            "energy": (self.calculate_energy_efficiency, {"unit_id": unit_id, "end": window_end}),
            "automation": (self.calculate_automation_effectiveness, {"unit_id": unit_id, "end": window_end}),
        }

        # Add previous week calculations if requested
        if include_previous:
            previous_end = window_end - timedelta(days=7)
            tasks["previous_environmental"] = (
                self.calculate_environmental_stability,
                {"unit_id": unit_id, "end": previous_end},
            )
            tasks["previous_energy"] = (self.calculate_energy_efficiency, {"unit_id": unit_id, "end": previous_end})
            tasks["previous_automation"] = (
                self.calculate_automation_effectiveness,
                {"unit_id": unit_id, "end": previous_end},
            )

        results = {}

        # Execute all calculations concurrently
        with ThreadPoolExecutor(max_workers=6) as executor:
            # Submit all tasks
            future_to_name = {}
            for name, (func, kwargs) in tasks.items():
                future = executor.submit(func, **kwargs)
                future_to_name[future] = name

            # Collect results as they complete
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    self.logger.error(f"Error calculating {name} efficiency: {e}", exc_info=True)
                    # Provide neutral fallback score
                    results[name] = 75.0

        return results

    def get_composite_efficiency_score(
        self, unit_id: int | None = None, include_previous: bool = True
    ) -> dict[str, Any]:
        """
        Calculate composite system efficiency score.

        Components (weighted):
        - Environmental Stability (40%): Temperature, humidity, VPD consistency
        - Energy Efficiency (30%): Power usage optimization
        - Automation Effectiveness (30%): Device response and alert handling

        Args:
            unit_id: Optional unit filter
            include_previous: Whether to include previous week score for trend analysis

        Returns:
            Dictionary with overall score, breakdown, grade, and trend.
        """
        try:
            import time

            start_time = time.monotonic()
            end = utc_now()

            # 1. Calculate component scores
            scores = self.calculate_efficiency_scores_concurrent(
                unit_id=unit_id, end=end, include_previous=include_previous
            )

            # 2. Extract current and previous scores
            env_score = scores.get("environmental", 0.0)
            energy_score = scores.get("energy", 0.0)
            automation_score = scores.get("automation", 0.0)

            previous_env_score = scores.get("previous_environmental", env_score)
            previous_energy_score = scores.get("previous_energy", energy_score)
            previous_automation_score = scores.get("previous_automation", automation_score)

            # 3. Calculate weighted composite score
            overall_score = env_score * 0.40 + energy_score * 0.30 + automation_score * 0.30
            previous_overall_score = (
                previous_env_score * 0.40 + previous_energy_score * 0.30 + previous_automation_score * 0.30
            )

            # 4. Grading logic
            def get_grade(s):
                if s >= 97:
                    return "A+"
                if s >= 93:
                    return "A"
                if s >= 87:
                    return "B+"
                if s >= 80:
                    return "B"
                if s >= 70:
                    return "C"
                if s >= 60:
                    return "D"
                return "F"

            def get_trend(curr, prev):
                delta = curr - prev
                if delta > 2:
                    return "improving"
                if delta < -2:
                    return "declining"
                return "stable"

            # 5. Suggestions logic
            suggestions = []
            if env_score < 70:
                suggestions.append(
                    {
                        "priority": "high",
                        "category": "environmental",
                        "message": "Environmental conditions are unstable. Check sensor calibration and adjust climate control settings.",
                        "action": "view_sensor_analytics",
                        "action_label": "View Analytics",
                    }
                )
            elif env_score < 85:
                suggestions.append(
                    {
                        "priority": "medium",
                        "category": "environmental",
                        "message": "Minor fluctuations detected. Consider adjusting temperature/humidity thresholds.",
                        "action": "view_settings",
                        "action_label": "Adjust Settings",
                    }
                )

            if energy_score < 70:
                suggestions.append(
                    {
                        "priority": "high",
                        "category": "energy",
                        "message": "Frequent device cycling detected. Review automation schedules to reduce energy waste.",
                        "action": "view_energy_analytics",
                        "action_label": "View Energy Usage",
                    }
                )
            elif energy_score < 85:
                suggestions.append(
                    {
                        "priority": "medium",
                        "category": "energy",
                        "message": "Energy usage can be optimized. Review device schedules.",
                        "action": "view_energy_analytics",
                        "action_label": "View Energy Usage",
                    }
                )

            if automation_score < 70:
                suggestions.append(
                    {
                        "priority": "high",
                        "category": "automation",
                        "message": "Multiple anomalies detected with slow response. Check device connectivity.",
                        "action": "check_devices",
                        "action_label": "Check Devices",
                    }
                )

            execution_time_ms = round((time.monotonic() - start_time) * 1000, 2)
            cache_stats = self.get_cache_stats()

            return {
                "overall_score": round(overall_score, 1),
                "components": {
                    "environmental": round(env_score, 1),
                    "energy": round(energy_score, 1),
                    "automation": round(automation_score, 1),
                },
                "grade": get_grade(overall_score),
                "trend": get_trend(overall_score, previous_overall_score),
                "suggestions": suggestions,
                "timestamp": end.isoformat(),
                "unit_id": unit_id,
                "performance": {
                    "execution_time_ms": execution_time_ms,
                    "cache_hit_rate": cache_stats.get("history", {}).get("hit_rate", 0),
                },
            }
        except Exception as e:
            self.logger.error(f"Error calculating composite efficiency score: {e}", exc_info=True)
            return {"error": str(e)}

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics for monitoring and debugging.

        Returns:
            Dictionary with cache metrics for:
            - latest_readings: Cache for get_latest_sensor_reading()
            - history: Cache for fetch_sensor_history()

        Example:
            >>> service = AnalyticsService(repo)
            >>> stats = service.get_cache_stats()
            >>> print(f"History cache hit rate: {stats['history']['hit_rate']}%")
            History cache hit rate: 87.5%
        """
        return {
            "latest_readings": self._latest_reading_cache.get_stats(),
            "history": self._history_cache.get_stats(),
        }

    def clear_caches(self) -> None:
        """
        Clear all caches in the analytics service.

        Useful for testing or after bulk data updates.
        """
        self._latest_reading_cache.clear()
        self._history_cache.clear()
        self.logger.info("Cleared all analytics service caches")

    def warm_cache(self, unit_ids: list[int] | None = None) -> dict[str, Any]:
        """
        Pre-populate caches with frequently accessed data.

        Useful for warming caches after service restart or at scheduled intervals
        to improve initial response times for dashboard/analytics endpoints.

        Args:
            unit_ids: Optional list of unit IDs to warm cache for (None = all units)

        Returns:
            Dictionary with warming statistics:
                - units_processed: Number of units processed
                - latest_readings_cached: Number of latest readings cached
                - history_windows_cached: Number of history windows cached
                - execution_time_ms: Time taken to warm caches

        Example:
            >>> service = AnalyticsService(repo)
            >>> stats = service.warm_cache(unit_ids=[1, 2, 3])
            >>> print(f"Warmed cache for {stats['units_processed']} units in {stats['execution_time_ms']}ms")
            Warmed cache for 3 units in 234ms
        """
        import time

        start_time = time.monotonic()

        units_processed = 0
        latest_readings_cached = 0
        history_windows_cached = 0

        try:
            # Determine which units to process
            if unit_ids is None:
                # Get all units from device repository
                if self.device_repo:
                    try:
                        all_units = self.device_repo.list_units()
                        unit_ids = [u.get("unit_id") for u in all_units if u.get("unit_id")]
                    except Exception as e:
                        self.logger.warning(f"Could not list units for cache warming: {e}")
                        unit_ids = []
                else:
                    unit_ids = []

            # Warm latest readings cache for each unit
            for unit_id in unit_ids:
                try:
                    # Cache latest reading for this unit
                    self.get_latest_sensor_reading(unit_id=unit_id)
                    latest_readings_cached += 1

                    # Cache common time windows (24h, 7d)
                    now = utc_now()

                    # 24 hour window
                    self.fetch_sensor_history(now - timedelta(hours=24), now, unit_id=unit_id, limit=500)
                    history_windows_cached += 1

                    # 7 day window
                    self.fetch_sensor_history(now - timedelta(days=7), now, unit_id=unit_id, limit=1000)
                    history_windows_cached += 1

                    units_processed += 1

                except Exception as e:
                    self.logger.warning(f"Error warming cache for unit {unit_id}: {e}")
                    continue

            # Also cache global latest reading (no unit filter)
            try:
                self.get_latest_sensor_reading(unit_id=None)
                latest_readings_cached += 1
            except Exception as e:
                self.logger.warning(f"Error warming global latest reading cache: {e}")

            execution_time_ms = round((time.monotonic() - start_time) * 1000, 2)

            self.logger.info(
                f"Cache warming complete: {units_processed} units, "
                f"{latest_readings_cached} latest readings, "
                f"{history_windows_cached} history windows in {execution_time_ms}ms"
            )

            return {
                "units_processed": units_processed,
                "latest_readings_cached": latest_readings_cached,
                "history_windows_cached": history_windows_cached,
                "execution_time_ms": execution_time_ms,
            }

        except Exception as e:
            self.logger.error(f"Error during cache warming: {e}", exc_info=True)
            return {
                "units_processed": units_processed,
                "latest_readings_cached": latest_readings_cached,
                "history_windows_cached": history_windows_cached,
                "execution_time_ms": round((time.monotonic() - start_time) * 1000, 2),
                "error": str(e),
            }

    @staticmethod
    def _safe_mean(values: list[float]) -> float | None:
        if not values:
            return None
        valid = [v for v in values if v is not None]
        if not valid:
            return None
        return round(sum(valid) / len(valid), 3)

    def get_enriched_sensor_history(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = 500,
        interval: str | None = None,
        lux_threshold_override: float | None = None,
        prefer_lux: bool = False,
        day_start_override: str | None = None,
        day_end_override: str | None = None,
        unit_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Get sensor history enriched with photoperiod and day/night analysis.

        Args:
            start_datetime: Start time
            end_datetime: End time
            unit_id: Optional unit filter
            sensor_id: Optional sensor filter
            limit: Max readings
            interval: Optional aggregation bucket
            lux_threshold_override: Optional threshold for light sensor
            prefer_lux: Use light sensor for day/night even if schedule exists
            day_start_override: HH:MM start override
            day_end_override: HH:MM end override
            unit_data: Optional unit dict (avoids re-fetching if already available)

        Returns:
            Dictionary with chart data and photoperiod summary
        """
        # 1. Fetch readings
        readings = self.fetch_sensor_history(
            start_datetime,
            end_datetime,
            unit_id=unit_id,
            sensor_id=sensor_id,
            limit=limit,
        )

        # 2. Basic formatting and aggregation
        chart_data = self.format_sensor_chart_data(readings, interval)

        # 3. Timezone normalization and timestamp parsing
        parsed_timestamps = self._normalize_chart_timestamps(chart_data)

        # 4–5. Resolve unit settings and determine source priority
        pp_cfg = self._resolve_photoperiod_config(
            unit_id=unit_id,
            unit_data=unit_data,
            lux_threshold_override=lux_threshold_override,
            prefer_lux=prefer_lux,
            day_start_override=day_start_override,
            day_end_override=day_end_override,
        )

        # 6–7. Photoperiod analysis, mask computation, temperature DIF
        photoperiod_summary = self._compute_photoperiod(
            chart_data,
            parsed_timestamps,
            pp_cfg,
        )

        # Attach masks
        chart_data["is_day_schedule"] = photoperiod_summary.pop("_schedule_mask")
        chart_data["is_day_sensor"] = photoperiod_summary.pop("_sensor_mask")
        chart_data["is_day"] = photoperiod_summary.pop("_day_mask")

        return {
            "start": start_datetime.isoformat(),
            "end": end_datetime.isoformat(),
            "unit_id": unit_id,
            "sensor_id": sensor_id,
            "interval": interval,
            "count": len(readings),
            "data": chart_data,
            "photoperiod": photoperiod_summary,
            "timestamp": utc_now().isoformat(),
        }

    # ------------------------------------------------------------------
    # Helpers extracted from get_enriched_sensor_history
    # ------------------------------------------------------------------

    def _normalize_chart_timestamps(
        self,
        chart_data: dict[str, Any],
    ) -> list[datetime | None]:
        """Parse and normalize chart_data timestamps in-place.

        Returns the list of parsed ``datetime`` objects (``None`` for unparseable).
        """
        parsed: list[datetime | None] = []
        normalized: list[str] = []
        for ts in chart_data.get("timestamps", []):
            dt = coerce_datetime(ts)
            parsed.append(dt)
            normalized.append(dt.isoformat() if dt else str(ts))
        chart_data["timestamps"] = normalized
        return parsed

    def _resolve_photoperiod_config(
        self,
        *,
        unit_id: int | None,
        unit_data: dict[str, Any] | None,
        lux_threshold_override: float | None,
        prefer_lux: bool,
        day_start_override: str | None,
        day_end_override: str | None,
    ) -> dict[str, Any]:
        """Resolve schedule, threshold, and source-priority settings.

        Returns a flat config dict consumed by ``_compute_photoperiod``.
        """
        photoperiod_source = "schedule"
        schedule_present = False
        schedule_enabled = False
        schedule_day_start = day_start_override
        schedule_day_end = day_end_override
        lux_threshold = lux_threshold_override if lux_threshold_override is not None else 100.0

        # Try to load unit data from repo when not provided
        unit = unit_data
        if not unit and unit_id is not None and self.growth_repo:
            try:
                row = self.growth_repo.get_unit(unit_id)
                if row:
                    unit = {k: row[k] for k in row.keys()} if hasattr(row, "keys") else None
            except Exception as e:
                self.logger.warning(f"Failed to fetch unit {unit_id} for analytics: {e}")

        # Light schedule from SchedulingService
        if unit_id is not None and self.scheduling_service:
            try:
                schedules = self.scheduling_service.get_schedules_for_unit(unit_id, device_type="light")
                if schedules:
                    schedule = schedules[0]
                    schedule_present = True
                    schedule_day_start = schedule_day_start or schedule.start_time
                    schedule_day_end = schedule_day_end or schedule.end_time
                    schedule_enabled = bool(schedule.enabled)
                    if schedule.photoperiod:
                        photoperiod_source = (
                            schedule.photoperiod.source.value if schedule.photoperiod.source else "schedule"
                        )
            except Exception as e:
                self.logger.warning(f"Failed to get light schedule from SchedulingService: {e}")

        # Lux threshold from unit / threshold service
        if unit:
            settings = unit.get("settings") or {}
            if lux_threshold_override is None:
                threshold_val = None
                if self.threshold_service and unit_id is not None:
                    thresholds = self.threshold_service.get_unit_thresholds(unit_id)
                    if thresholds:
                        threshold_val = thresholds.lux
                if threshold_val is None:
                    threshold_val = unit.get("lux_threshold")
                if threshold_val is None:
                    threshold_val = settings.get("lux_threshold")
                if threshold_val is not None:
                    lux_threshold = float(threshold_val)

        # Source priority
        if photoperiod_source == "sensor":
            prefer_lux = True
            schedule_enabled = False
        elif photoperiod_source == "hybrid":
            prefer_lux = True

        schedule_day_start = schedule_day_start or "06:00"
        schedule_day_end = schedule_day_end or "18:00"

        return {
            "photoperiod_source": photoperiod_source,
            "schedule_present": schedule_present,
            "schedule_enabled": schedule_enabled,
            "schedule_day_start": schedule_day_start,
            "schedule_day_end": schedule_day_end,
            "lux_threshold": float(lux_threshold),
            "prefer_lux": prefer_lux,
        }

    def _compute_photoperiod(
        self,
        chart_data: dict[str, Any],
        parsed_timestamps: list[datetime | None],
        cfg: dict[str, Any],
    ) -> dict[str, Any]:
        """Build photoperiod masks + temperature DIF analysis.

        Returns the photoperiod summary dict; masks are stored under
        private keys ``_schedule_mask``, ``_sensor_mask``, ``_day_mask``
        so the caller can pop them into ``chart_data``.
        """
        lux_values = chart_data.get("lux", []) or []
        sensor_enabled = any(v is not None for v in lux_values)
        n = len(parsed_timestamps)

        day_mask: list[int | None] = [None] * n
        schedule_mask: list[int | None] = [None] * n
        sensor_mask: list[int | None] = [None] * n

        summary: dict[str, Any] = {
            "photoperiod_source": cfg["photoperiod_source"],
            "schedule_day_start": cfg["schedule_day_start"],
            "schedule_day_end": cfg["schedule_day_end"],
            "schedule_present": cfg["schedule_present"],
            "schedule_enabled": cfg["schedule_enabled"],
            "lux_threshold": cfg["lux_threshold"],
            "prefer_lux": cfg["prefer_lux"],
            "sensor_enabled": sensor_enabled,
            "source": None,
            "agreement_rate": None,
            "schedule_light_hours": None,
            "sensor_light_hours": None,
            "start_offset_minutes": None,
            "end_offset_minutes": None,
            "day_temperature_avg_c": None,
            "night_temperature_avg_c": None,
            "dif_c": None,
        }

        valid_indices = [i for i, ts in enumerate(parsed_timestamps) if ts is not None]
        if valid_indices:
            timestamps_valid = [parsed_timestamps[i] for i in valid_indices if parsed_timestamps[i] is not None]
            lux_valid = [lux_values[i] for i in valid_indices]

            photoperiod = Photoperiod(
                schedule_day_start=cfg["schedule_day_start"],
                schedule_day_end=cfg["schedule_day_end"],
                schedule_enabled=cfg["schedule_enabled"],
                sensor_threshold=cfg["lux_threshold"],
                greenhouse_outside=cfg["prefer_lux"],
                sensor_enabled=sensor_enabled,
            )

            resolved = photoperiod.resolve_mask(timestamps_valid, sensor_values=lux_valid)
            schedule_mask_valid = resolved.get("schedule_mask") or []
            sensor_mask_valid = resolved.get("sensor_mask") or []
            final_mask_valid = resolved.get("final_mask") or []

            for local_idx, original_idx in enumerate(valid_indices):
                if local_idx < len(schedule_mask_valid):
                    schedule_mask[original_idx] = 1 if schedule_mask_valid[local_idx] else 0
                if local_idx < len(sensor_mask_valid):
                    sensor_val = sensor_mask_valid[local_idx]
                    sensor_mask[original_idx] = None if sensor_val is None else (1 if sensor_val else 0)
                if local_idx < len(final_mask_valid):
                    day_mask[original_idx] = 1 if final_mask_valid[local_idx] else 0

            # Alignment analysis
            if sensor_enabled:
                alignment = photoperiod.analyze_alignment(timestamps_valid, lux_valid)
                summary.update(alignment)

            # Final source label
            if sensor_enabled and cfg["prefer_lux"]:
                summary["source"] = "lux"
            elif cfg["schedule_enabled"]:
                summary["source"] = "schedule"
            elif sensor_enabled:
                summary["source"] = "lux"
            else:
                summary["source"] = "schedule"

            # 7. Temperature day/night DIF
            self._apply_temperature_dif(chart_data, day_mask, summary)

        summary["_schedule_mask"] = schedule_mask
        summary["_sensor_mask"] = sensor_mask
        summary["_day_mask"] = day_mask
        return summary

    def _apply_temperature_dif(
        self,
        chart_data: dict[str, Any],
        day_mask: list[int | None],
        summary: dict[str, Any],
    ) -> None:
        """Compute day/night temperature averages and DIF, updating *summary* in-place."""
        temps = chart_data.get("temperature", [])
        day_temps = [t for t, m in zip(temps, day_mask) if isinstance(t, (int, float)) and m == 1]
        night_temps = [t for t, m in zip(temps, day_mask) if isinstance(t, (int, float)) and m == 0]

        day_avg = self._safe_mean(day_temps)
        night_avg = self._safe_mean(night_temps)
        summary["day_temperature_avg_c"] = day_avg
        summary["night_temperature_avg_c"] = night_avg
        if day_avg is not None and night_avg is not None:
            summary["dif_c"] = round(day_avg - night_avg, 3)
