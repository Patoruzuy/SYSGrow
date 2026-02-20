"""
Environmental Analytics Service
================================

Extracted from AnalyticsService (Sprint 4 – god-service split).

Handles environmental calculations (VPD, trends, correlations, stability)
and system efficiency scoring (energy efficiency, automation effectiveness,
composite scores).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any

from app.constants import AnalysisWindows, DataLimits
from app.utils.time import utc_now
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.devices import DeviceRepository

logger = logging.getLogger(__name__)


class EnvironmentalAnalyticsService:
    """Environmental analytics: VPD, trends, correlations, stability, efficiency scoring."""

    def __init__(
        self,
        repository: AnalyticsRepository,
        device_repository: DeviceRepository | None = None,
    ):
        self.repository = repository
        self.device_repo = device_repository
        self.device_repository = device_repository
        self.logger = logger

    # ── VPD Calculation ──────────────────────────────────────────────

    def calculate_vpd_with_zones(self, temperature: float | None, humidity: float | None) -> dict[str, Any]:
        """
        Calculate Vapor Pressure Deficit with growth stage zone interpretation.

        VPD = SVP × (1 - RH/100)
        where SVP = 0.6108 × exp(17.27 × T / (T + 237.3))
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
            from app.utils.psychrometrics import calculate_vpd_kpa

            vpd_value = calculate_vpd_kpa(temperature, humidity)
            if vpd_value is None:
                raise ValueError("VPD calculation returned None")

            vpd = round(float(vpd_value), 2)

            if vpd < 0.4:
                zone = "too_low"
                status = "low"
                optimal_for: list[str] = []
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
            logger.warning("Error calculating VPD: %s", e)
            return {
                "value": None,
                "unit": "kPa",
                "status": "error",
                "zone": "unknown",
                "optimal_for": [],
                "temperature": temperature,
                "humidity": humidity,
            }

    # ── Metric Trends ────────────────────────────────────────────────

    def analyze_metric_trends(self, readings: list[dict], days: int) -> dict[str, Any]:
        """Analyze environmental trends with statistical rigor."""
        if not readings:
            return {
                "temperature": {"trend": "no_data", "volatility": "unknown"},
                "humidity": {"trend": "no_data", "volatility": "unknown"},
                "soil_moisture": {"trend": "no_data", "volatility": "unknown"},
            }

        temp_values = [r.get("temperature") for r in readings if r.get("temperature") is not None]
        humidity_values = [r.get("humidity") for r in readings if r.get("humidity") is not None]
        moisture_values = [r.get("soil_moisture") for r in readings if r.get("soil_moisture") is not None]

        def _analyze(values: list[float]) -> dict[str, Any]:
            if not values or len(values) < 2:
                return {"trend": "no_data", "volatility": "unknown"}

            avg = sum(values) / len(values)
            variance = sum((x - avg) ** 2 for x in values) / len(values)
            std_dev = variance**0.5

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
            "temperature": _analyze(temp_values),
            "humidity": _analyze(humidity_values),
            "soil_moisture": _analyze(moisture_values),
        }

    # ── Correlations ─────────────────────────────────────────────────

    def calculate_environmental_correlations(self, readings: list[dict]) -> dict[str, Any]:
        """Calculate Pearson correlations between environmental factors."""
        if not readings or len(readings) < 10:
            return {
                "temp_humidity_correlation": None,
                "correlation_interpretation": "insufficient_data",
                "vpd_average": None,
                "vpd_status": "unknown",
                "sample_size": len(readings) if readings else 0,
            }

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

        abs_corr = abs(correlation)
        if abs_corr < 0.3:
            interpretation = "weak"
        elif abs_corr < 0.7:
            interpretation = "moderate"
        else:
            interpretation = "strong"

        from app.utils.psychrometrics import calculate_vpd_kpa

        vpd_values = []
        for temp, rh in paired_values:
            vpd = calculate_vpd_kpa(temp, rh)
            if vpd is not None:
                vpd_values.append(vpd)

        avg_vpd = sum(vpd_values) / len(vpd_values) if vpd_values else None

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

    # ── Environmental Stability ──────────────────────────────────────

    def calculate_environmental_stability(
        self, unit_id: int | None = None, end: datetime | None = None, days: int = 7
    ) -> float:
        """Calculate environmental stability score (0-100) based on temperature/humidity volatility."""
        try:
            window_end = end or utc_now()
            window_start = window_end - timedelta(days=days)

            # Fetch sensor history directly from repository
            readings = self.repository.fetch_sensor_history(window_start, window_end, unit_id=unit_id)

            if not readings:
                self.logger.warning("No sensor readings for stability calculation (unit_id=%s)", unit_id)
                return 70.0

            trends = self.analyze_metric_trends(readings, days)

            temp_stats = trends.get("temperature", {})
            humidity_stats = trends.get("humidity", {})

            def _get_volatility(stats: dict[str, Any], default: float = 0.05) -> float:
                avg = stats.get("average")
                std_dev = stats.get("std_dev")
                if avg is not None and std_dev is not None and avg != 0:
                    return std_dev / avg
                return default

            temp_volatility = min(0.15, _get_volatility(temp_stats))
            humidity_volatility = min(0.15, _get_volatility(humidity_stats))

            temp_stability = max(0, min(100, 100 - (temp_volatility * 500)))
            humidity_stability = max(0, min(100, 100 - (humidity_volatility * 300)))

            # Count anomalies
            if not self.device_repo:
                total_anomalies = 0
            else:
                sensors = (
                    self.device_repo.list_sensor_configs(unit_id=unit_id)
                    if unit_id
                    else self.device_repo.list_sensor_configs()
                )

                sensor_ids: list[int] = []
                for sensor in sensors:
                    sensor_id = sensor.get("sensor_id")
                    if sensor_id is None:
                        continue
                    try:
                        sensor_ids.append(int(sensor_id))
                    except (TypeError, ValueError):
                        self.logger.warning("Invalid sensor_id format: %s", sensor_id)
                        continue

                from app.utils.time import sqlite_timestamp

                total_anomalies = self.device_repo.count_anomalies_for_sensors(
                    sorted(set(sensor_ids)),
                    start=sqlite_timestamp(window_start),
                    end=sqlite_timestamp(window_end),
                )

            anomaly_penalty = min(20, total_anomalies * 2)
            avg_stability = (temp_stability + humidity_stability) / 2
            final_score = max(0, avg_stability - anomaly_penalty)

            self.logger.debug(
                "Environmental stability calculated: %.1f (temp=%.1f, humidity=%.1f, anomalies=%s, penalty=%s)",
                final_score,
                temp_stability,
                humidity_stability,
                total_anomalies,
                anomaly_penalty,
            )

            return final_score

        except Exception as e:
            self.logger.error("Error calculating environmental stability: %s", e, exc_info=True)
            return 70.0

    # ── Energy Efficiency ────────────────────────────────────────────

    def calculate_energy_efficiency(
        self,
        unit_id: int | None = None,
        end: datetime | None = None,
        days: int = 7,
        limit: int = DataLimits.MAX_IN_MEMORY_RECORDS,
    ) -> float:
        """Calculate energy efficiency score (0-100) based on actuator usage patterns."""
        try:
            window_end = end or utc_now()
            window_start = window_end - timedelta(days=days)

            if not self.device_repo:
                return 75.0

            states = self.device_repo.get_recent_actuator_state(limit=limit, unit_id=unit_id)

            if not states:
                self.logger.warning("No actuator states for energy efficiency calculation (unit_id=%s)", unit_id)
                return 75.0

            from app.utils.time import coerce_datetime

            window_states: list[Any] = []
            for state in states:
                if isinstance(state, dict):
                    timestamp = coerce_datetime(state.get("timestamp"))
                else:
                    timestamp = coerce_datetime(getattr(state, "timestamp", None))
                if timestamp and window_start <= timestamp <= window_end:
                    window_states.append(state)

            if len(window_states) < 10:
                self.logger.warning("Insufficient actuator states for analysis: %s < 10", len(window_states))
                return 75.0

            window_days = (window_end - window_start).total_seconds() / 86400
            if window_days <= 0:
                self.logger.error("Invalid time window for energy efficiency calculation")
                return 75.0

            changes_per_day = len(window_states) / window_days

            if 5 <= changes_per_day <= 15:
                efficiency = 95
            elif changes_per_day < 5:
                efficiency = 70 + (changes_per_day * 5)
            else:
                efficiency = max(50, 95 - ((changes_per_day - 15) * 3))

            final_score = min(100, max(0, efficiency))

            self.logger.debug(
                "Energy efficiency calculated: %.1f (changes_per_day=%.1f, window_days=%.1f)",
                final_score,
                changes_per_day,
                window_days,
            )

            return final_score

        except Exception as e:
            self.logger.error("Error calculating energy efficiency: %s", e, exc_info=True)
            return 75.0

    # ── Automation Effectiveness ─────────────────────────────────────

    def calculate_automation_effectiveness(
        self, unit_id: int | None = None, end: datetime | None = None, hours: int = AnalysisWindows.DEFAULT_HOURS
    ) -> float:
        """Calculate automation effectiveness (0-100) based on anomaly response and uptime."""
        try:
            window_end = end or utc_now()
            window_start = window_end - timedelta(hours=hours)

            if not self.device_repo:
                return 75.0

            sensors = (
                self.device_repo.list_sensor_configs(unit_id=unit_id)
                if unit_id
                else self.device_repo.list_sensor_configs()
            )

            sensor_ids: list[int] = []
            for sensor in sensors:
                sensor_id = sensor.get("sensor_id")
                if sensor_id is None:
                    continue
                try:
                    sensor_ids.append(int(sensor_id))
                except (TypeError, ValueError):
                    self.logger.warning("Invalid sensor_id format: %s", sensor_id)
                    continue

            from app.utils.time import sqlite_timestamp

            anomaly_count = self.device_repo.count_anomalies_for_sensors(
                sorted(set(sensor_ids)),
                start=sqlite_timestamp(window_start),
                end=sqlite_timestamp(window_end),
            )

            if anomaly_count == 0:
                anomaly_score = 90.0
            else:
                anomaly_score = max(50, 90 - (anomaly_count * 5))

            from app.services.hardware.actuator_management_service import ActuatorManagementService

            try:
                actuator_service = ActuatorManagementService(self.device_repo)
                actuators = actuator_service.list_actuators()
                if unit_id:
                    actuators = [a for a in actuators if a.get("unit_id") == unit_id]
                if actuators:
                    online_count = sum(1 for a in actuators if a.get("connection_status") == "online")
                    uptime_score = (online_count / len(actuators)) * 100
                else:
                    uptime_score = 80
            except Exception as e:
                self.logger.warning("Could not fetch actuator status: %s", e)
                uptime_score = 80

            automation_score = (anomaly_score * 0.6) + (uptime_score * 0.4)
            final_score = min(100, max(0, automation_score))

            self.logger.debug(
                "Automation effectiveness calculated: %.1f (anomalies=%s, anomaly_score=%.1f, uptime_score=%.1f)",
                final_score,
                anomaly_count,
                anomaly_score,
                uptime_score,
            )

            return final_score

        except Exception as e:
            self.logger.error("Error calculating automation effectiveness: %s", e, exc_info=True)
            return 75.0

    # ── Concurrent Efficiency Scores ─────────────────────────────────

    def calculate_efficiency_scores_concurrent(
        self, unit_id: int | None = None, end: datetime | None = None, include_previous: bool = False
    ) -> dict[str, Any]:
        """Calculate all three efficiency component scores concurrently."""
        window_end = end or utc_now()

        tasks = {
            "environmental": (self.calculate_environmental_stability, {"unit_id": unit_id, "end": window_end}),
            "energy": (self.calculate_energy_efficiency, {"unit_id": unit_id, "end": window_end}),
            "automation": (self.calculate_automation_effectiveness, {"unit_id": unit_id, "end": window_end}),
        }

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

        results: dict[str, Any] = {}

        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_name = {}
            for name, (func, kwargs) in tasks.items():
                future = executor.submit(func, **kwargs)
                future_to_name[future] = name
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    self.logger.error("Error calculating %s efficiency: %s", name, e, exc_info=True)
                    results[name] = 75.0

        return results

    # ── Composite Efficiency Score ───────────────────────────────────

    def get_composite_efficiency_score(
        self,
        unit_id: int | None = None,
        include_previous: bool = True,
        cache_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Calculate composite system efficiency score.

        Components (weighted):
        - Environmental Stability (40%)
        - Energy Efficiency (30%)
        - Automation Effectiveness (30%)

        Args:
            unit_id: Optional unit filter
            include_previous: Whether to include previous week score for trend analysis
            cache_stats: Optional cache statistics from the sensor service
        """
        try:
            import time

            start_time = time.monotonic()
            end = utc_now()

            scores = self.calculate_efficiency_scores_concurrent(
                unit_id=unit_id, end=end, include_previous=include_previous
            )

            env_score = scores.get("environmental", 0.0)
            energy_score = scores.get("energy", 0.0)
            automation_score = scores.get("automation", 0.0)

            previous_env_score = scores.get("previous_environmental", env_score)
            previous_energy_score = scores.get("previous_energy", energy_score)
            previous_automation_score = scores.get("previous_automation", automation_score)

            overall_score = env_score * 0.40 + energy_score * 0.30 + automation_score * 0.30
            previous_overall_score = (
                previous_env_score * 0.40 + previous_energy_score * 0.30 + previous_automation_score * 0.30
            )

            def _get_grade(s: float) -> str:
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

            def _get_trend(curr: float, prev: float) -> str:
                delta = curr - prev
                if delta > 2:
                    return "improving"
                if delta < -2:
                    return "declining"
                return "stable"

            suggestions: list[dict[str, Any]] = []
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
            resolved_cache_stats = cache_stats or {}

            return {
                "overall_score": round(overall_score, 1),
                "components": {
                    "environmental": round(env_score, 1),
                    "energy": round(energy_score, 1),
                    "automation": round(automation_score, 1),
                },
                "grade": _get_grade(overall_score),
                "trend": _get_trend(overall_score, previous_overall_score),
                "suggestions": suggestions,
                "timestamp": end.isoformat(),
                "unit_id": unit_id,
                "performance": {
                    "execution_time_ms": execution_time_ms,
                    "cache_hit_rate": resolved_cache_stats.get("history", {}).get("hit_rate", 0),
                },
            }
        except Exception as e:
            self.logger.error("Error calculating composite efficiency score: %s", e, exc_info=True)
            return {"error": str(e)}
