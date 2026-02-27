"""
System Health Endpoints
=======================

Core system health monitoring endpoints.
"""

from __future__ import annotations

import logging

from flask import Blueprint, Response, request

from app.blueprints.api._common import (
    fail as _fail,
    get_container as _container,
    get_growth_service as _growth_service,
    get_sensor_service as _sensor_service,
    get_system_health_service as _system_health_service,
    success as _success,
)
from app.enums.common import HealthLevel
from app.utils.event_bus import EventBus
from app.utils.http import safe_route
from app.utils.time import iso_now

logger = logging.getLogger("health_api")


def register_system_routes(health_api: Blueprint):
    """Register system health routes on the blueprint."""

    @health_api.get("/ping")
    @safe_route("Failed to handle ping request")
    def ping() -> Response:
        """
        Basic liveness check for monitoring tools.

        Returns:
            {"status": "ok", "timestamp": "..."}
        """
        return _success({"status": "ok", "timestamp": iso_now()})

    @health_api.get("/system")
    @safe_route("Failed to get system health")
    def get_system_health() -> Response:
        """
        Get overall system health including polling, climate controllers, and event bus.

        Returns:
            {
                "status": "healthy|degraded|critical",
                "units": {...},
                "event_bus": {...},
                "summary": {...},
                "timestamp": "2025-12-08T..."
            }
        """
        growth_service = _growth_service()
        sensor_svc = _sensor_service()

        # Get unit runtimes for basic info
        runtimes = growth_service.get_unit_runtimes()

        units = {}
        healthy_count = 0
        degraded_count = 0
        offline_count = 0

        for unit_id, runtime in runtimes.items():
            # Get health data from hardware services (not runtime manager)
            polling_health = sensor_svc.get_polling_health()

            # Get climate controller health from growth service
            controller = growth_service._climate_controllers.get(unit_id)
            controller_health = (
                controller.get_health_status() if controller and hasattr(controller, "get_health_status") else {}
            )

            # Determine unit health status
            is_running = runtime.is_hardware_running()
            has_stale_sensors = len(controller_health.get("stale_sensors", [])) > 0 if controller_health else False

            if is_running and not has_stale_sensors:
                unit_health = HealthLevel.HEALTHY
                healthy_count += 1
            elif is_running:
                unit_health = HealthLevel.DEGRADED
                degraded_count += 1
            else:
                unit_health = HealthLevel.OFFLINE
                offline_count += 1

            units[str(unit_id)] = {
                "unit_id": unit_id,
                "name": runtime.unit_name,
                "hardware_running": is_running,
                "status": str(unit_health),
                "polling": polling_health,
                "controller": controller_health,
            }

        # Overall system status
        total_units = len(runtimes)
        if total_units == 0:
            system_status = HealthLevel.UNKNOWN
        elif offline_count == total_units:
            system_status = HealthLevel.CRITICAL
        elif degraded_count > 0 or offline_count > 0:
            system_status = HealthLevel.DEGRADED
        else:
            system_status = HealthLevel.HEALTHY

        event_bus_metrics = EventBus().get_metrics()

        return _success(
            {
                "status": str(system_status),
                "units": units,
                "event_bus": event_bus_metrics,
                "summary": {
                    "total_units": total_units,
                    "healthy_units": healthy_count,
                    "degraded_units": degraded_count,
                    "offline_units": offline_count,
                },
                "timestamp": iso_now(),
            }
        )

    @health_api.get("/detailed")
    @safe_route("Failed to get detailed health")
    def get_detailed_health() -> Response:
        """
        Get comprehensive health report from SystemHealthService.

        Includes:
        - System info (API, DB, storage, uptime)
        - Sensor health aggregation
        - Active alerts
        - Overall status
        - Infrastructure details (storage, API metrics, DB status)

        Returns:
            Complete health report with all metrics
        """
        container = _container()
        system_health = container.system_health_service
        database = container.database

        # Perform full health check
        report = system_health.perform_full_health_check(db_handler=database)

        return _success(report)

    @health_api.get("/storage")
    @safe_route("Failed to get storage health")
    def get_storage_health() -> Response:
        """
        Get storage usage statistics.

        Returns:
            {
                "total": bytes,
                "used": bytes,
                "free": bytes,
                "percent": percentage
            }
        """
        system_health = _system_health_service()
        storage = system_health.refresh_storage_usage()
        return _success(storage)

    @health_api.get("/api-metrics")
    @safe_route("Failed to get API metrics")
    def get_api_metrics() -> Response:
        """
        Get API performance metrics.

        Returns:
            {
                "total_requests": int,
                "failed_requests": int,
                "slow_requests": int,
                "error_rate": percentage,
                "avg_response_time_ms": float,
                "status": "online|degraded|offline"
            }
        """
        system_health = _system_health_service()
        system_health.check_api_health()
        metrics = system_health.get_api_metrics()
        return _success(metrics)

    @health_api.get("/database")
    @safe_route("Failed to check database health")
    def get_database_health() -> Response:
        """
        Check database connection health and size statistics.

        Returns comprehensive database information including:
        - Connection status
        - Database file sizes (main, WAL, SHM)
        - Table row counts for key tables
        - Warning/critical status based on size thresholds

        Returns:
            {
                "status": "connected|error|unknown",
                "size": {
                    "main_db_mb": float,
                    "wal_mb": float,
                    "shm_mb": float,
                    "total_mb": float,
                    "warning": bool,
                    "critical": bool
                },
                "tables": {
                    "SensorReading": int,
                    "ActuatorStateHistory": int,
                    ...
                },
                "timestamp": ISO timestamp
            }
        """

        from app.services.utilities.database_maintenance_service import DatabaseMaintenanceService

        container = _container()
        system_health = container.system_health_service
        database = container.database
        config = getattr(container, "config", None)

        # Check connection status
        status = system_health.check_database_health(db_handler=database)

        # Get database file path
        db_path = getattr(config, "database_path", "database/sysgrow.db") if config else "database/sysgrow.db"

        # Delegate size info and table counts to DatabaseMaintenanceService
        maintenance = DatabaseMaintenanceService(db_path)

        size_info = maintenance.get_database_size_info()
        size_info["path"] = str(db_path)

        table_counts = maintenance.get_table_row_counts()

        # Add retention settings info
        retention_info = {
            "sensor_retention_days": getattr(config, "sensor_retention_days", 30) if config else 30,
            "actuator_state_retention_days": getattr(config, "actuator_state_retention_days", 90) if config else 90,
        }

        return _success(
            {
                "status": status,
                "size": size_info,
                "tables": table_counts,
                "retention_settings": retention_info,
                "recommendations": _get_db_recommendations(size_info, table_counts),
                "timestamp": iso_now(),
            }
        )

    def _get_db_recommendations(size_info: dict, table_counts: dict) -> list:
        """Generate recommendations based on database metrics."""
        recommendations = []

        if size_info.get("critical"):
            recommendations.append(
                {
                    "severity": "critical",
                    "message": f"Database size ({size_info['total_mb']}MB) exceeds 500MB threshold",
                    "action": "Run data pruning task or reduce retention periods",
                }
            )
        elif size_info.get("warning"):
            recommendations.append(
                {
                    "severity": "warning",
                    "message": f"Database size ({size_info['total_mb']}MB) approaching limit",
                    "action": "Monitor growth and consider reducing retention periods",
                }
            )

        sensor_readings = table_counts.get("SensorReading", 0)
        if sensor_readings > 1000000:
            recommendations.append(
                {
                    "severity": "warning",
                    "message": f"SensorReading table has {sensor_readings:,} rows",
                    "action": "Consider reducing sensor_retention_days or running prune task",
                }
            )

        if size_info.get("wal_mb", 0) > 50:
            recommendations.append(
                {
                    "severity": "info",
                    "message": f"WAL file is {size_info['wal_mb']}MB - consider checkpointing",
                    "action": "Run PRAGMA wal_checkpoint(TRUNCATE) during low activity",
                }
            )

        if not recommendations:
            recommendations.append(
                {"severity": "info", "message": "Database health is good", "action": "No action needed"}
            )

        return recommendations

    @health_api.get("/infrastructure")
    @safe_route("Failed to get infrastructure status")
    def get_infrastructure_status() -> Response:
        """
        Get comprehensive infrastructure component statuses.

        Enhanced endpoint that consolidates all system information including:
        - Application version and uptime
        - API and database status
        - Storage metrics
        - MQTT connection status
        - ML infrastructure availability
        - Zigbee service status
        - Available features

        Returns:
            {
                "version": str,
                "apiStatus": "online|degraded|offline",
                "dbStatus": "connected|error|unknown",
                "lastBackup": str,
                "uptime": seconds,
                "storageUsed": bytes,
                "storageTotal": bytes,
                "mqttStatus": "connected|disconnected|disabled",
                "mlAvailable": bool,
                "zigbeeEnabled": bool,
                "features": {...}
            }
        """
        system_health = _system_health_service()
        container = _container()

        # Get base system info
        info = system_health.get_system_info()

        # Add service availability information
        mqtt_client = getattr(container, "mqtt_client", None)
        zigbee_service = getattr(container, "zigbee_service", None)
        ml_available = bool(getattr(container, "model_registry", None)) and bool(
            getattr(container, "drift_detector", None)
        )

        # Determine MQTT status
        mqtt_status = "disabled"
        if mqtt_client:
            # Check if MQTT has is_connected method
            if hasattr(mqtt_client, "is_connected"):
                mqtt_status = "connected" if mqtt_client.is_connected() else "disconnected"
            else:
                mqtt_status = "connected"  # Assume connected if client exists

        # Add enhanced information
        info.update(
            {
                "mqttStatus": mqtt_status,
                "mlAvailable": ml_available,
                "zigbeeEnabled": zigbee_service is not None,
                "features": {
                    "mqtt": mqtt_client is not None,
                    "ml": ml_available,
                    "zigbee": zigbee_service is not None,
                    "alerts": True,  # Alert system always available
                    "health_monitoring": True,  # Health monitoring always available
                },
            }
        )

        return _success(info)

    @health_api.post("/check-alerts")
    @safe_route("Failed to check health and create alerts")
    def check_health_and_create_alerts() -> Response:
        """
        Check system health and create alerts for critical issues.

        Returns:
            {
                "alerts_created": int,
                "alert_ids": [list of alert IDs]
            }
        """
        system_health = _system_health_service()
        alert_ids = system_health.check_and_alert_on_health_issues()

        return _success({"alerts_created": len(alert_ids), "alert_ids": alert_ids})

    @health_api.get("/cache-stats")
    @safe_route("Failed to get cache statistics")
    def get_cache_statistics() -> Response:
        """
        Get cache statistics from all registered caches in the application.

        Useful for monitoring cache performance and identifying bottlenecks.

        Returns:
            {
                "summary": {
                    "total_caches": int,
                    "total_size": int,
                    "total_maxsize": int,
                    "total_hits": int,
                    "total_misses": int,
                    "overall_hit_rate": float,
                    "total_evictions": int,
                    "enabled_caches": int
                },
                "caches": {
                    "cache_name": {
                        "enabled": bool,
                        "size": int,
                        "maxsize": int,
                        "ttl_seconds": int,
                        "hits": int,
                        "misses": int,
                        "hit_rate": float,
                        "evictions": int,
                        "utilization": float
                    }
                }
            }
        """
        from app.utils.cache import CacheRegistry

        registry = CacheRegistry.get_instance()
        summary = registry.get_summary()
        all_stats = registry.get_all_stats()

        return _success({"summary": summary, "caches": all_stats, "timestamp": iso_now()})

    @health_api.post("/cache-warm")
    @safe_route("Failed to warm caches")
    def warm_caches() -> Response:
        """
        Warm caches by pre-loading frequently accessed data.

        Query params:
        - unit_ids: Comma-separated list of unit IDs (optional, defaults to all units)

        Returns:
            Statistics about cache warming operation including:
            - units_processed: Number of units processed
            - latest_readings_cached: Number of latest readings cached
            - history_windows_cached: Number of history windows cached
            - execution_time_ms: Time taken to warm caches

        Example:
            POST /api/health/cache-warm
            POST /api/health/cache-warm?unit_ids=1,2,3
        """
        from app.blueprints.api._common import get_analytics_service as _analytics_service

        # Parse unit_ids from query params
        unit_ids_param = request.args.get("unit_ids")
        unit_ids = None
        if unit_ids_param:
            try:
                unit_ids = [int(uid.strip()) for uid in unit_ids_param.split(",")]
            except ValueError:
                return _fail("Invalid unit_ids format. Expected comma-separated integers.", 400)

        analytics_service = _analytics_service()
        stats = analytics_service.warm_cache(unit_ids=unit_ids)

        return _success({**stats, "timestamp": iso_now()})

    @health_api.get("/performance-metrics")
    @safe_route("Failed to get performance metrics")
    def get_performance_metrics() -> Response:
        """
        Get performance metrics for monitoring and optimization.

        Includes:
        - Cache statistics (hit rates, sizes, evictions)
        - Service health status
        - Response time benchmarks
        - Resource utilization

        Returns comprehensive performance data for monitoring dashboards.
        """
        from app.blueprints.api._common import get_analytics_service as _analytics_service
        from app.utils.cache import CacheRegistry

        # Get cache registry stats
        cache_registry = CacheRegistry.get_instance()
        cache_summary = cache_registry.get_summary()
        cache_details = cache_registry.get_all_stats()

        # Get analytics service cache stats
        try:
            analytics_service = _analytics_service()
            analytics_cache_stats = analytics_service.get_cache_stats()
        except (RuntimeError, ValueError, TypeError, AttributeError) as e:
            logger.warning("Could not get analytics cache stats: %s", e)
            analytics_cache_stats = {}

        # Compile performance metrics
        metrics = {
            "caches": {"summary": cache_summary, "details": cache_details, "analytics": analytics_cache_stats},
            "recommendations": [],
        }

        # Generate recommendations based on metrics
        if cache_summary.get("overall_hit_rate", 0) < 70:
            metrics["recommendations"].append(
                {
                    "type": "cache_tuning",
                    "severity": "warning",
                    "message": f"Overall cache hit rate is {cache_summary.get('overall_hit_rate', 0):.1f}%. Consider increasing TTL or cache size.",
                    "action": "Review cache configuration and consider warming caches more frequently",
                }
            )

        for cache_name, cache_stats in cache_details.items():
            utilization = cache_stats.get("utilization", 0)
            if utilization > 90:
                metrics["recommendations"].append(
                    {
                        "type": "cache_size",
                        "severity": "info",
                        "message": f"Cache '{cache_name}' is {utilization:.1f}% full. Consider increasing maxsize.",
                        "cache": cache_name,
                    }
                )

            evictions = cache_stats.get("evictions", 0)
            if evictions > 100:
                metrics["recommendations"].append(
                    {
                        "type": "cache_evictions",
                        "severity": "info",
                        "message": f"Cache '{cache_name}' has {evictions} evictions. Consider increasing cache size.",
                        "cache": cache_name,
                    }
                )

        return _success({**metrics, "timestamp": iso_now()})
