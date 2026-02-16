"""
Actuator Energy Monitoring
===========================

Endpoints for monitoring and analyzing actuator energy consumption, power readings,
calibrations, and advanced energy analytics including cost trends and optimization.
"""

from __future__ import annotations

import logging

from flask import current_app, request

from app.enums import AnomalySeverity, RiskLevel
from app.utils.http import error_response, safe_error, success_response
from app.utils.time import iso_now

from ...devices import devices_api

logger = logging.getLogger("devices_api.actuators.energy")


def _growth_service():
    """Get growth service from container"""
    return current_app.config["CONTAINER"].growth_service


def _actuator_service():
    """Get actuator management service from container"""
    return current_app.config["CONTAINER"].actuator_management_service


def _device_health_service():
    """Get device health service from container"""
    return current_app.config["CONTAINER"].device_health_service


def _analytics_service():
    """Get analytics service from container"""
    return current_app.config["CONTAINER"].analytics_service


def _success(data: dict | list | None = None, status: int = 200):
    """Return success response"""
    return success_response(data, status)


def _fail(message: str, status: int = 500):
    """Return error response"""
    return error_response(message, status)


# ==================== BASIC POWER CONSUMPTION ====================


@devices_api.get("/actuators/<int:actuator_id>/power")
def get_actuator_power(actuator_id: int):
    """
    Get current power consumption for an actuator.

    Returns:
        {
            "actuator_id": 1,
            "power_watts": 150.5,
            "is_estimated": false,
            "timestamp": "2025-11-15T10:30:00"
        }
    """
    try:
        actuator_svc = _actuator_service()
        actuator = actuator_svc.get_actuator(actuator_id)
        if actuator is None:
            return _fail(f"Actuator {actuator_id} not found", 404)

        actuator_manager = actuator_svc.actuator_manager
        power = actuator_manager.get_power_consumption(actuator_id)

        if power is None:
            return _fail(f"Power data not available for actuator {actuator_id}", 404)

        # Check if it's estimated or real
        is_estimated = True
        energy_monitoring = getattr(actuator_manager, "energy_monitoring", None)
        if energy_monitoring:
            latest = energy_monitoring.get_latest_reading(actuator_id)
            is_estimated = not (latest and latest.power is not None)

        return _success(
            {
                "actuator_id": actuator_id,
                "power_watts": round(power, 2),
                "is_estimated": is_estimated,
                "timestamp": iso_now(),
            }
        )

    except Exception as e:
        return safe_error(e, 500)


@devices_api.get("/actuators/<int:actuator_id>/energy")
def get_actuator_energy_stats(actuator_id: int):
    """
    Get energy consumption statistics for an actuator.

    Query params:
        hours: Number of hours to analyze (default: 24)

    Returns:
        {
            "actuator_id": 1,
            "total_energy_kwh": 3.6,
            "average_power_watts": 150.0,
            "peak_power_watts": 180.0,
            "runtime_hours": 24.0,
            "cost_estimate": 0.43
        }
    """
    try:
        hours = request.args.get("hours", 24, type=int)

        actuator_svc = _actuator_service()
        actuator = actuator_svc.get_actuator(actuator_id)
        if actuator is None:
            return _fail(f"Actuator {actuator_id} not found", 404)

        actuator_manager = actuator_svc.actuator_manager
        stats = actuator_manager.get_energy_stats(actuator_id, hours)

        if not stats:
            return _fail(f"Energy statistics not available for actuator {actuator_id}", 404)

        return _success(stats)

    except Exception as e:
        return safe_error(e, 500)


@devices_api.get("/actuators/<int:actuator_id>/cost")
def get_actuator_cost_estimate(actuator_id: int):
    """
    Get electricity cost estimates for an actuator.

    Query params:
        period: 'daily', 'weekly', 'monthly', 'yearly' (default: monthly)

    Returns:
        {
            "actuator_id": 1,
            "cost": 13.00,
            "energy_kwh": 108.0,
            "period": "monthly"
        }
    """
    try:
        period = request.args.get("period", "monthly", type=str)

        if period not in ["daily", "weekly", "monthly", "yearly"]:
            return _fail("Invalid period. Must be one of: daily, weekly, monthly, yearly", 400)

        actuator_svc = _actuator_service()
        actuator = actuator_svc.get_actuator(actuator_id)
        if actuator is None:
            return _fail(f"Actuator {actuator_id} not found", 404)

        actuator_manager = actuator_svc.actuator_manager
        cost_data = actuator_manager.get_cost_estimate(actuator_id, period)

        if not cost_data:
            return _fail(f"Cost estimate not available for actuator {actuator_id}", 404)

        cost_data["actuator_id"] = actuator_id
        return _success(cost_data)

    except Exception as e:
        return safe_error(e, 500)


@devices_api.get("/actuators/total-power")
def get_total_power():
    """
    Get total power consumption across all actuators in all units.

    Returns:
        {
            "total_power_watts": 450.5,
            "unit_breakdown": [
                {
                    "unit_id": 1,
                    "unit_name": "Greenhouse 1",
                    "power_watts": 300.0,
                    "actuator_count": 3
                }
            ]
        }
    """
    try:
        growth_service = _growth_service()
        units = growth_service.list_units()
        actuator_svc = _actuator_service()

        total_power = 0.0
        unit_breakdown = []

        for unit in units:
            unit_id = unit.get("unit_id")
            actuators = actuator_svc.list_actuators(unit_id=unit_id)
            unit_power = 0.0
            for actuator in actuators:
                actuator_id = actuator.get("actuator_id")
                if actuator_id is None:
                    continue
                unit_power += actuator_svc.actuator_manager.get_power_consumption(int(actuator_id)) or 0.0

            total_power += unit_power
            unit_breakdown.append(
                {
                    "unit_id": unit_id,
                    "unit_name": unit.get("name"),
                    "power_watts": round(unit_power, 2),
                    "actuator_count": len(actuators),
                }
            )

        return _success(
            {"total_power_watts": round(total_power, 2), "unit_breakdown": unit_breakdown, "timestamp": iso_now()}
        )

    except Exception as e:
        return safe_error(e, 500)


# ==================== ACTUATOR POWER READINGS ====================


@devices_api.get("/actuators/<int:actuator_id>/power-readings")
def get_actuator_power_readings(actuator_id: int):
    """Get power readings for an actuator"""
    try:
        limit = request.args.get("limit", 1000, type=int)
        hours = request.args.get("hours", type=int)

        device_health = _device_health_service()
        readings = device_health.get_actuator_power_readings(actuator_id=actuator_id, limit=limit, hours=hours)

        # Calculate statistics
        if readings:
            power_values = [r["power_watts"] for r in readings if r.get("power_watts")]
            avg_power = sum(power_values) / len(power_values) if power_values else 0
            max_power = max(power_values) if power_values else 0
            min_power = min(power_values) if power_values else 0
        else:
            avg_power = max_power = min_power = 0

        return _success(
            {
                "actuator_id": actuator_id,
                "readings": readings,
                "count": len(readings),
                "statistics": {
                    "average_power_watts": round(avg_power, 2),
                    "max_power_watts": round(max_power, 2),
                    "min_power_watts": round(min_power, 2),
                },
            }
        )

    except Exception as e:
        return safe_error(e, 500)


@devices_api.post("/actuators/<int:actuator_id>/power-readings")
def save_actuator_power_reading(actuator_id: int):
    """Save actuator power reading"""
    try:
        data = request.get_json()

        power_watts = data.get("power_watts")
        if power_watts is None:
            return _fail("power_watts is required", 400)

        device_health = _device_health_service()
        reading_id = device_health.save_actuator_power_reading(
            actuator_id=actuator_id,
            power_watts=power_watts,
            voltage=data.get("voltage"),
            current=data.get("current"),
            energy_kwh=data.get("energy_kwh"),
            power_factor=data.get("power_factor"),
            frequency=data.get("frequency"),
            temperature=data.get("temperature"),
            is_estimated=data.get("is_estimated", False),
        )

        if reading_id:
            return _success({"reading_id": reading_id, "message": "Power reading saved successfully"})
        else:
            return _fail("Failed to save power reading", 500)

    except Exception as e:
        return safe_error(e, 500)


# ==================== ACTUATOR CALIBRATION ====================


@devices_api.get("/actuators/<int:actuator_id>/calibrations")
def get_actuator_calibrations(actuator_id: int):
    """Get all calibrations for an actuator"""
    try:
        from ..utils import _device_health_service

        device_health = _device_health_service()
        calibrations = device_health.get_actuator_calibrations(actuator_id)

        # Group by calibration type
        by_type = {}
        for cal in calibrations:
            cal_type = cal.get("calibration_type", "unknown")
            if cal_type not in by_type:
                by_type[cal_type] = []
            by_type[cal_type].append(cal)

        return _success(
            {"actuator_id": actuator_id, "calibrations": calibrations, "count": len(calibrations), "by_type": by_type}
        )

    except Exception as e:
        return safe_error(e, 500)


@devices_api.post("/actuators/<int:actuator_id>/calibrations")
def save_actuator_calibration(actuator_id: int):
    """Save actuator calibration profile"""
    try:
        data = request.get_json()

        calibration_type = data.get("calibration_type")
        calibration_data = data.get("calibration_data")

        if not calibration_type or not calibration_data:
            return _fail("calibration_type and calibration_data are required", 400)
        from ..utils import _device_health_service

        device_health = _device_health_service()
        calibration_id = device_health.save_actuator_calibration(
            actuator_id=actuator_id, calibration_type=calibration_type, calibration_data=calibration_data
        )

        if calibration_id:
            return _success({"calibration_id": calibration_id, "message": "Calibration saved successfully"})
        else:
            return _fail("Failed to save calibration", 500)

    except Exception as e:
        return safe_error(e, 500)


# ==================== ADVANCED ENERGY ANALYTICS ====================


@devices_api.get("/actuators/<int:actuator_id>/energy/cost-trends")
def get_actuator_energy_cost_trends(actuator_id: int):
    """
    Get energy cost trends over time.

    Query Parameters:
    - days: Number of days to analyze (default: 7)

    Returns daily costs, totals, and trend direction.
    """
    try:
        days = request.args.get("days", 7, type=int)

        if days < 1 or days > 365:
            return _fail("days must be between 1 and 365", 400)

        analytics_service = _analytics_service()
        trends = analytics_service.get_actuator_energy_cost_trends(actuator_id, days)

        return _success(trends)

    except Exception as e:
        return safe_error(e, 500)


@devices_api.get("/actuators/<int:actuator_id>/energy/recommendations")
def get_actuator_optimization_recommendations(actuator_id: int):
    """
    Get energy optimization recommendations for an actuator.

    Analyzes power consumption patterns and provides actionable recommendations.
    """
    try:
        analytics_service = _analytics_service()
        recommendations = analytics_service.get_actuator_optimization_recommendations(actuator_id)

        # Calculate total potential savings
        total_savings_kwh = sum(r.get("potential_savings_kwh", 0) for r in recommendations)
        total_savings_usd = sum(r.get("potential_savings_usd", 0) for r in recommendations)

        return _success(
            {
                "actuator_id": actuator_id,
                "recommendations": recommendations,
                "count": len(recommendations),
                "total_potential_savings": {
                    "energy_kwh": round(total_savings_kwh, 2),
                    "cost_usd": round(total_savings_usd, 2),
                },
            }
        )

    except Exception as e:
        return safe_error(e, 500)


@devices_api.get("/actuators/<int:actuator_id>/energy/anomalies")
def detect_actuator_power_anomalies(actuator_id: int):
    """
    Detect power consumption anomalies (spikes, drops, unusual patterns).

    Query Parameters:
    - hours: Hours to analyze (default: 24)
    """
    try:
        hours = request.args.get("hours", 24, type=int)

        if hours < 1 or hours > 720:  # Max 30 days
            return _fail("hours must be between 1 and 720", 400)

        analytics_service = _analytics_service()
        anomalies = analytics_service.detect_actuator_power_anomalies(actuator_id, hours)

        # Group by type
        by_type = {}
        by_severity = {
            AnomalySeverity.CRITICAL.value: [],
            AnomalySeverity.MAJOR.value: [],
            AnomalySeverity.MINOR.value: [],
            AnomalySeverity.INFO.value: [],
        }

        for anomaly in anomalies:
            anom_type = anomaly.get("type", "unknown")
            severity = anomaly.get("severity", AnomalySeverity.INFO.value)

            if anom_type not in by_type:
                by_type[anom_type] = []
            by_type[anom_type].append(anomaly)

            if severity in by_severity:
                by_severity[severity].append(anomaly)

        return _success(
            {
                "actuator_id": actuator_id,
                "period_hours": hours,
                "anomalies": anomalies,
                "count": len(anomalies),
                "by_type": by_type,
                "by_severity": {
                    AnomalySeverity.CRITICAL.value: len(by_severity[AnomalySeverity.CRITICAL.value]),
                    AnomalySeverity.MAJOR.value: len(by_severity[AnomalySeverity.MAJOR.value]),
                    AnomalySeverity.MINOR.value: len(by_severity[AnomalySeverity.MINOR.value]),
                    AnomalySeverity.INFO.value: len(by_severity[AnomalySeverity.INFO.value]),
                },
            }
        )

    except Exception as e:
        return safe_error(e, 500)


@devices_api.get("/actuators/energy/comparative-analysis")
def get_comparative_energy_analysis():
    """
    Get comparative energy analysis across all actuators.

    Query Parameters:
    - unit_id: Optional unit ID to filter by
    """
    try:
        unit_id = request.args.get("unit_id", type=int)

        analytics_service = _analytics_service()
        analysis = analytics_service.get_comparative_energy_analysis(unit_id)

        return _success(analysis)

    except Exception as e:
        return safe_error(e, 500)


@devices_api.get("/actuators/<int:actuator_id>/energy/dashboard")
def get_actuator_energy_dashboard(actuator_id: int):
    """
    Get comprehensive energy dashboard data for an actuator.

    Combines multiple analytics endpoints into a single dashboard view.
    """
    try:
        analytics_service = _analytics_service()

        # Get latest power reading (DeviceHealthService)
        device_health = _device_health_service()
        power_readings = device_health.get_actuator_power_readings(actuator_id, limit=1)
        current_power = power_readings[0] if power_readings else None

        # Get 24-hour trends (now from AnalyticsService)
        cost_trends = analytics_service.get_actuator_energy_cost_trends(actuator_id, days=1)

        # Get recommendations (now from AnalyticsService)
        recommendations = analytics_service.get_actuator_optimization_recommendations(actuator_id)

        # Get recent anomalies (now from AnalyticsService)
        anomalies = analytics_service.detect_actuator_power_anomalies(actuator_id, hours=24)

        # Get 7-day cost trends (now from AnalyticsService)
        weekly_trends = analytics_service.get_actuator_energy_cost_trends(actuator_id, days=7)

        dashboard = {
            "actuator_id": actuator_id,
            "current_status": {
                "power_watts": current_power.get("power_watts") if current_power else 0.0,
                "voltage": current_power.get("voltage") if current_power else None,
                "current": current_power.get("current") if current_power else None,
                "timestamp": current_power.get("created_at") if current_power else None,
            },
            "daily_summary": {
                "total_cost": cost_trends.get("total_cost", 0.0),
                "total_energy_kwh": cost_trends.get("total_energy_kwh", 0.0),
                "trend": cost_trends.get("trend", "unknown"),
            },
            "weekly_summary": {
                "total_cost": weekly_trends.get("total_cost", 0.0),
                "total_energy_kwh": weekly_trends.get("total_energy_kwh", 0.0),
                "average_daily_cost": weekly_trends.get("average_daily_cost", 0.0),
                "trend": weekly_trends.get("trend", "unknown"),
            },
            "optimization": {
                "recommendations_count": len(recommendations),
                "high_priority": len(
                    [
                        r
                        for r in recommendations
                        if r.get("severity") in [RiskLevel.HIGH.value, AnomalySeverity.CRITICAL.value]
                    ]
                ),
                "total_potential_savings_usd": sum(r.get("potential_savings_usd", 0) for r in recommendations),
                "top_recommendations": recommendations[:3],
            },
            "anomalies": {
                "count_24h": len(anomalies),
                "critical": len([a for a in anomalies if a.get("severity") == AnomalySeverity.CRITICAL.value]),
                "major": len([a for a in anomalies if a.get("severity") == AnomalySeverity.MAJOR.value]),
                "recent": anomalies[:5],
            },
        }

        return _success(dashboard)

    except Exception as e:
        return safe_error(e, 500)
