"""
Energy Analytics Service
========================

Extracted from AnalyticsService (Sprint 4 – god-service split).

Handles all actuator energy analysis, cost trends, anomaly detection,
optimization recommendations, and predictive device failure analytics.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.constants import AnalysisWindows, DataLimits
from app.utils.time import utc_now
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.repositories.growth import GrowthRepository

logger = logging.getLogger(__name__)


class EnergyAnalyticsService:
    """Energy and actuator analytics: cost trends, anomalies, recommendations, predictions."""

    def __init__(
        self,
        repository: AnalyticsRepository,
        device_repository: DeviceRepository | None = None,
        growth_repository: GrowthRepository | None = None,
        electricity_rate: float = 0.12,
    ):
        self.repository = repository
        self.device_repository = device_repository
        self.device_repo = device_repository
        self.growth_repo = growth_repository
        self.electricity_rate = electricity_rate
        self.logger = logger

    # ── Cost Trends ──────────────────────────────────────────────────

    def get_actuator_energy_cost_trends(self, actuator_id: int, days: int = 7) -> dict[str, Any]:
        """Get energy cost trends over time for an actuator."""
        if not self.device_repository:
            logger.error("DeviceRepository not available for actuator analytics")
            return {
                "actuator_id": actuator_id,
                "error": "DeviceRepository not configured",
                "daily_costs": [],
                "total_cost": 0.0,
            }

        try:
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

            daily_data: dict[Any, dict[str, Any]] = {}
            for reading in readings:
                reading_date = datetime.fromisoformat(reading["created_at"]).date()
                if reading_date not in daily_data:
                    daily_data[reading_date] = {"power_readings": [], "energy_kwh": 0.0}
                if reading.get("power_watts"):
                    daily_data[reading_date]["power_readings"].append(reading["power_watts"])
                if reading.get("energy_kwh"):
                    daily_data[reading_date]["energy_kwh"] = reading["energy_kwh"]

            daily_costs = []
            for date in sorted(daily_data.keys()):
                data = daily_data[date]
                if data["energy_kwh"] == 0.0 and data["power_readings"]:
                    avg_power = sum(data["power_readings"]) / len(data["power_readings"])
                    hours_covered = len(data["power_readings"]) / 60
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

            total_cost = sum(d["cost"] for d in daily_costs)
            total_energy = sum(d["energy_kwh"] for d in daily_costs)
            avg_daily_cost = total_cost / len(daily_costs) if daily_costs else 0.0

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
            logger.error("Error calculating cost trends for actuator %s: %s", actuator_id, e, exc_info=True)
            return {"actuator_id": actuator_id, "error": str(e), "daily_costs": [], "total_cost": 0.0}

    # ── Optimization Recommendations ─────────────────────────────────

    def get_actuator_optimization_recommendations(self, actuator_id: int) -> list[dict[str, Any]]:
        """Get energy optimization recommendations for an actuator."""
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
            recommendations: list[dict[str, Any]] = []
            readings = self.device_repository.get_actuator_power_readings(
                actuator_id, limit=DataLimits.MAX_IN_MEMORY_RECORDS, hours=AnalysisWindows.ENERGY_HISTORY_HOURS
            )

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

            power_values = [r["power_watts"] for r in readings if r.get("power_watts")]
            if not power_values:
                return recommendations

            avg_power = sum(power_values) / len(power_values)
            peak_power = max(power_values)

            # 1. High standby power
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
                            "description": (
                                f"Device consumes {avg_standby:.1f}W when idle. "
                                "Consider using a smart plug to completely cut power."
                            ),
                            "current_value": round(avg_standby, 2),
                            "potential_savings_kwh": round(annual_waste_kwh, 2),
                            "potential_savings_usd": round(annual_cost, 2),
                        }
                    )

            # 2. High variance
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

            # 3. Power factor
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

            # 4. High peak power
            if peak_power > avg_power * 2:
                recommendations.append(
                    {
                        "type": "high_peak_power",
                        "severity": "low",
                        "title": "High Peak Power Demand",
                        "description": (
                            f"Peak power ({peak_power:.1f}W) is {peak_power / avg_power:.1f}x average. "
                            "Consider load leveling."
                        ),
                        "current_value": round(peak_power, 2),
                        "potential_savings_kwh": 0.0,
                        "potential_savings_usd": 0.0,
                    }
                )

            # 5. Always-on
            on_time_percentage = len([p for p in power_values if p > 10]) / len(power_values)
            if on_time_percentage > 0.9:
                potential_kwh = (avg_power * 24 * 365 * 0.1) / 1000
                recommendations.append(
                    {
                        "type": "always_on_device",
                        "severity": "low",
                        "title": "Device Always On",
                        "description": (
                            f"Device is on {on_time_percentage * 100:.0f}% of the time. Consider scheduling."
                        ),
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

            logger.info("💡 Generated %s recommendations for actuator %s", len(recommendations), actuator_id)
            return recommendations

        except Exception as e:
            logger.error("Error generating recommendations for actuator %s: %s", actuator_id, e, exc_info=True)
            return []

    # ── Anomaly Detection ────────────────────────────────────────────

    def detect_actuator_power_anomalies(
        self, actuator_id: int, hours: int = AnalysisWindows.POWER_READINGS_HOURS
    ) -> list[dict[str, Any]]:
        """Detect power consumption anomalies using 3-sigma statistical analysis."""
        if not self.device_repository:
            return []

        try:
            anomalies: list[dict[str, Any]] = []
            readings = self.device_repository.get_actuator_power_readings(
                actuator_id, limit=DataLimits.POWER_READINGS_FETCH, hours=hours
            )

            if len(readings) < 10:
                return anomalies

            power_values = [r["power_watts"] for r in readings if r.get("power_watts") is not None]
            if len(power_values) < 10:
                return anomalies

            avg_power = sum(power_values) / len(power_values)
            variance = sum((p - avg_power) ** 2 for p in power_values) / len(power_values)
            std_dev = variance**0.5

            threshold_spike = avg_power + (3 * std_dev)
            threshold_drop = max(0, avg_power - (3 * std_dev))

            for i, reading in enumerate(readings):
                power = reading.get("power_watts")
                if power is None:
                    continue
                timestamp = reading.get("created_at", "")

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

            # Extended outages
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

            logger.info("🔍 Detected %s power anomalies for actuator %s", len(anomalies), actuator_id)
            return anomalies

        except Exception as e:
            logger.error("Error detecting anomalies for actuator %s: %s", actuator_id, e, exc_info=True)
            return []

    # ── Comparative Analysis ─────────────────────────────────────────

    def get_comparative_energy_analysis(self, unit_id: int | None = None) -> dict[str, Any]:
        """Get comparative energy analysis across actuators."""
        if not self.device_repo:
            return {"error": "DeviceRepository not configured"}

        try:
            actuators = (
                self.device_repo.list_actuators(unit_id=unit_id) if unit_id else self.device_repo.list_actuators()
            )

            total_power = 0.0
            total_daily_cost = 0.0
            by_type: dict[str, dict[str, Any]] = {}
            top_consumers: list[dict[str, Any]] = []

            for actuator in actuators:
                try:
                    act_id = actuator.get("actuator_id")
                    act_type = actuator.get("actuator_type", "unknown")

                    power_readings = self.device_repo.get_actuator_power_readings(act_id, limit=1)
                    p_watts = power_readings[0].get("power_watts", 0.0) if power_readings else 0.0
                    total_power += p_watts

                    costs = self.get_actuator_energy_cost_trends(act_id, days=1)
                    cost_val = costs.get("total_cost", 0.0)
                    total_daily_cost += cost_val

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
                    self.logger.warning("Error comparing actuator %s: %s", actuator.get("actuator_id"), e)

            top_consumers.sort(key=lambda x: x["power_watts"], reverse=True)

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
                "efficiency_rankings": top_consumers,
                "unit_id": unit_id,
                "timestamp": utc_now().isoformat(),
            }

            logger.info("📊 Generated comparative analysis for unit %s", unit_id or "all")
            return analysis

        except Exception as e:
            logger.error("Error generating comparative analysis: %s", e, exc_info=True)
            return {"error": str(e)}

    # ── Multi-Unit Overview ──────────────────────────────────────────

    def get_multi_unit_analytics_overview(
        self,
        *,
        get_latest_sensor_reading: Any = None,
    ) -> dict[str, Any]:
        """
        Compare environmental conditions and energy usage across all units.

        Args:
            get_latest_sensor_reading: Callable(unit_id) for sensor data (injected from facade).
        """
        if not self.growth_repo:
            return {"error": "GrowthRepository not configured"}

        try:
            units = self.growth_repo.list_units()
            comparisons = []

            for unit in units:
                unit_id = unit.get("unit_id")
                if unit_id is None:
                    continue
                try:
                    latest_sensor = None
                    if get_latest_sensor_reading:
                        latest_sensor = get_latest_sensor_reading(unit_id=unit_id)
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
                    self.logger.warning("Could not get comparison for unit %s: %s", unit_id, e)

            return {"units": comparisons, "total_units": len(comparisons), "timestamp": utc_now().isoformat()}
        except Exception as e:
            self.logger.error("Error generating multi-unit analytics overview: %s", e, exc_info=True)
            return {"error": str(e)}

    # ── Actuator Overview / Dashboard ────────────────────────────────

    def get_actuators_analytics_overview(self, unit_id: int | None = None) -> dict[str, Any]:
        """Get overview of analytics for all actuators in a unit."""
        if not self.device_repo:
            return {"error": "DeviceRepository not configured"}

        try:
            actuators = (
                self.device_repo.list_actuators(unit_id=unit_id) if unit_id else self.device_repo.list_actuators()
            )

            results = []
            for actuator in actuators:
                act_id = actuator.get("actuator_id")
                if act_id is None:
                    continue
                try:
                    dash = self.get_actuator_energy_dashboard(act_id)
                    results.append(dash)
                except Exception as e:
                    self.logger.warning("Error enriching actuator %s: %s", act_id, e)

            return {"unit_id": unit_id, "count": len(results), "actuators": results, "timestamp": utc_now().isoformat()}
        except Exception as e:
            self.logger.error("Error generating actuators overview: %s", e, exc_info=True)
            return {"error": str(e)}

    def get_actuator_energy_dashboard(self, actuator_id: int) -> dict[str, Any]:
        """Get comprehensive energy dashboard data for an actuator."""
        if not self.device_repository:
            return {"actuator_id": actuator_id, "error": "DeviceRepository not configured"}

        try:
            power_readings = self.device_repository.get_actuator_power_readings(actuator_id, limit=1)
            current_power = power_readings[0] if power_readings else None

            daily_trends = self.get_actuator_energy_cost_trends(actuator_id, days=1)
            weekly_trends = self.get_actuator_energy_cost_trends(actuator_id, days=7)
            recommendations = self.get_actuator_optimization_recommendations(actuator_id)
            anomalies = self.detect_actuator_power_anomalies(actuator_id, hours=AnalysisWindows.ENERGY_HISTORY_HOURS)

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

            logger.info("📊 Generated energy dashboard for actuator %s", actuator_id)
            return dashboard

        except Exception as e:
            logger.error("Error generating dashboard for actuator %s: %s", actuator_id, e, exc_info=True)
            return {"actuator_id": actuator_id, "error": str(e)}

    def get_energy_dashboard_summary(self, unit_id: int | None = None, days: int = 7) -> dict[str, Any]:
        """Get aggregated energy consumption summary across multiple actuators."""
        if not self.device_repo:
            return {"error": "DeviceRepository not configured"}

        try:
            actuators = (
                self.device_repo.list_actuators(unit_id=unit_id) if unit_id else self.device_repo.list_actuators()
            )

            total_cost = 0.0
            device_costs: list[dict[str, Any]] = []

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
                    self.logger.warning("Error calculating cost for actuator %s: %s", actuator.get("actuator_id"), e)

            device_costs.sort(key=lambda x: x["cost"], reverse=True)

            daily_cost = total_cost / days if days > 0 else 0
            monthly_cost = daily_cost * 30

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
            self.logger.error("Error generating energy dashboard summary: %s", e, exc_info=True)
            return {"error": str(e)}

    # ── Predictive Analytics ─────────────────────────────────────────

    def predict_device_failure(self, actuator_id: int, days_ahead: int = 7) -> dict[str, Any]:
        """Predict probability of device failure based on historical patterns."""
        if not self.device_repository:
            return {"error": "DeviceRepository not configured"}

        try:
            health_history = self.device_repository.get_actuator_health_history(actuator_id, limit=30)
            anomalies = self.device_repository.get_actuator_anomalies(actuator_id, limit=DataLimits.DEFAULT_FETCH_LIMIT)

            if not health_history:
                return {
                    "actuator_id": actuator_id,
                    "failure_probability": 0.0,
                    "risk_level": "unknown",
                    "confidence": 0.0,
                    "message": "Insufficient historical data",
                }

            risk_score = 0.0
            risk_factors: list[dict[str, Any]] = []

            # 1. Health score trend
            if len(health_history) >= 2:
                recent_avg = sum(h.get("health_score", 100) for h in health_history[:5]) / min(5, len(health_history))
                older_avg = sum(h.get("health_score", 100) for h in health_history[-5:]) / min(5, len(health_history))
                if recent_avg < older_avg * 0.9:
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
                    if error_rate > 0.1:
                        risk_score += 0.3
                        risk_factors.append(
                            {
                                "factor": "high_error_rate",
                                "description": f"Error rate: {error_rate * 100:.1f}%",
                                "impact": "medium",
                            }
                        )

            failure_probability = min(1.0, risk_score)

            if failure_probability < 0.2:
                risk_level = "low"
            elif failure_probability < 0.5:
                risk_level = "medium"
            elif failure_probability < 0.8:
                risk_level = "high"
            else:
                risk_level = "critical"

            confidence = min(1.0, len(health_history) / 30.0)

            logger.info("🔮 Failure prediction for actuator %s: %s (%s)", actuator_id, failure_probability, risk_level)

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
            logger.error("Error predicting failure for actuator %s: %s", actuator_id, e, exc_info=True)
            return {"error": str(e)}

    @staticmethod
    def _get_maintenance_recommendation(risk_level: str) -> str:
        """Get maintenance recommendation based on risk level."""
        recommendations = {
            "low": "Continue normal operation. Monitor regularly.",
            "medium": "Schedule preventive maintenance within 30 days.",
            "high": "Schedule maintenance within 7 days. Consider backup plan.",
            "critical": "Immediate maintenance required. Prepare for replacement.",
        }
        return recommendations.get(risk_level, "Insufficient data for recommendation")
