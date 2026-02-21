"""
System Health Monitoring Service
=========================
Monitors overall system health and reliability.

**REFACTORED (Dec 17, 2025):**
Consolidated HealthMonitoringService functionality into this central coordinator.

Now handles:
- Sensor-specific health tracking (moved from HealthMonitoringService)
- Statistical anomaly detection (via AnomalyDetectionService)
- Infrastructure: API, database, storage status
- Alert generation for health issues
"""

import logging
import os
import shutil
from collections import deque
from datetime import UTC, datetime, timedelta
from typing import Any

try:
    import psutil  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - environment dependent optional dependency
    psutil = None

from app.config import load_config
from app.domain.sensors import HealthLevel
from app.domain.system import SystemHealthLevel, SystemHealthReport, SystemHealthStatus
from app.enums.events import ActivityEvent
from app.utils.event_bus import EventBus
from app.utils.time import iso_now, utc_now

logger = logging.getLogger(__name__)


class SystemHealthService:
    """
    System health monitoring service.

    This is the central coordinator for system health.

    Responsibilities:
    - Infrastructure health (API, DB, storage)
    - Sensor health tracking and reporting
    - Anomaly detection integration
    - Alert generation
    - Health trend analysis
    """

    def __init__(self, anomaly_service: Any | None = None, alert_service: Any | None = None):
        """
        Initialize System Health Service.

        Args:
            anomaly_service: Service for anomaly detection
            alert_service: Service for alert management
        """
        # Infrastructure status
        self.version = load_config.APP_VERSION
        self.api_status = "online"
        self.db_status = "connected"
        self.last_backup = "Not configured"
        self.uptime_start = None
        self.storage_used = 0
        self.storage_total = 0

        # Component health statuses (for custom systems)
        self.health_statuses: dict[int, SystemHealthStatus] = {}

        # Sensor health tracking (moved from HealthMonitoringService)
        self._sensor_entities: dict[int, Any] = {}  # sensor_id -> SensorEntity
        self._last_sensor_report: SystemHealthReport | None = None
        self._sensor_health_history: list[SystemHealthReport] = []
        self.max_sensor_history = 100

        # Integrated services
        self.anomaly_service = anomaly_service
        self.alert_service = alert_service

        config = load_config()
        self._api_health_window_size = max(1, int(getattr(config, "api_health_window_size", 100)))
        self._api_health_min_samples = max(1, int(getattr(config, "api_health_min_samples", 10)))
        self._api_health_error_rate_degraded = float(getattr(config, "api_health_error_rate_degraded", 0.10))
        self._api_health_error_rate_offline = float(getattr(config, "api_health_error_rate_offline", 0.50))
        self._api_health_avg_response_time_ms = int(getattr(config, "api_health_avg_response_time_ms", 2000))
        self._api_health_slow_request_ms = int(getattr(config, "api_health_slow_request_ms", 1000))

        self._system_startup()
        logger.info("System Health Service initialized (unified sensor + infrastructure monitoring).")

    def _system_startup(self) -> None:
        """Initialize system health monitoring on startup."""
        if psutil is None:
            logger.warning("psutil is unavailable; uptime tracking uses service start time.")
            self.uptime_start = utc_now()
            return
        try:
            process = psutil.Process(os.getpid())
            start_time = process.create_time()
            self.uptime_start = datetime.fromtimestamp(start_time, tz=UTC)
            logger.info("System uptime tracking initialized.")
        except Exception as e:
            logger.warning("Failed to calculate server uptime: %s", e)
            self.uptime_start = utc_now()  # Fallback to current time

    # ==================== Sensor Health Tracking (from HealthMonitoringService) ====================

    def register_sensor(self, sensor):
        """
        Register a sensor for health monitoring.

        Args:
            sensor: SensorEntity instance
        """
        self._sensor_entities[sensor.id] = sensor
        logger.info("Registered sensor %s for health monitoring", sensor.id)

    def unregister_sensor(self, sensor_id: int):
        """
        Unregister a sensor from health monitoring.

        Args:
            sensor_id: Sensor ID
        """
        if sensor_id in self._sensor_entities:
            del self._sensor_entities[sensor_id]
            logger.info("Unregistered sensor %s from health monitoring", sensor_id)

    def generate_sensor_health_report(self) -> SystemHealthReport:
        """
        Generate system-wide sensor health report.

        Returns:
            SystemHealthReport with sensor statistics
        """
        total = len(self._sensor_entities)

        if total == 0:
            return SystemHealthReport(
                timestamp=datetime.now(),
                total_sensors=0,
                healthy_sensors=0,
                degraded_sensors=0,
                critical_sensors=0,
                offline_sensors=0,
                system_health_level=HealthLevel.UNKNOWN,
                average_success_rate=0.0,
                issues=["No sensors registered"],
            )

        # Count sensors by health level
        healthy = 0
        degraded = 0
        critical = 0
        offline = 0
        success_rates = []
        issues = []

        for sensor_id, sensor in self._sensor_entities.items():
            health = sensor.get_health_status()

            if health.level == HealthLevel.HEALTHY:
                healthy += 1
            elif health.level == HealthLevel.DEGRADED:
                degraded += 1
                issues.append(f"Sensor {sensor_id} ({sensor.name}): {health.message}")
            elif health.level == HealthLevel.CRITICAL:
                critical += 1
                issues.append(f"CRITICAL: Sensor {sensor_id} ({sensor.name}): {health.message}")
            elif health.level == HealthLevel.OFFLINE:
                offline += 1
                issues.append(f"OFFLINE: Sensor {sensor_id} ({sensor.name})")

            # Collect success rates
            if health.total_reads > 0:
                success_rates.append(health.success_rate)

        # Calculate average success rate
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0.0

        # Determine overall system health
        system_health = self._determine_sensor_system_health(total, healthy, degraded, critical, offline)

        # Create report
        report = SystemHealthReport(
            timestamp=datetime.now(),
            total_sensors=total,
            healthy_sensors=healthy,
            degraded_sensors=degraded,
            critical_sensors=critical,
            offline_sensors=offline,
            system_health_level=system_health,
            average_success_rate=round(avg_success_rate, 2),
            issues=issues,
        )

        # Store report
        self._last_sensor_report = report
        self._sensor_health_history.append(report)

        # Trim history
        if len(self._sensor_health_history) > self.max_sensor_history:
            self._sensor_health_history = self._sensor_health_history[-self.max_sensor_history :]

        return report

    def _determine_sensor_system_health(
        self, total: int, healthy: int, degraded: int, critical: int, offline: int
    ) -> HealthLevel:
        """
        Determine overall sensor system health level.

        Args:
            total: Total sensors
            healthy: Healthy sensor count
            degraded: Degraded sensor count
            critical: Critical sensor count
            offline: Offline sensor count

        Returns:
            HealthLevel
        """
        # Critical if >30% critical or offline
        if (critical + offline) / total > 0.3:
            return HealthLevel.CRITICAL

        # Degraded if >20% degraded, critical, or offline
        if (degraded + critical + offline) / total > 0.2:
            return HealthLevel.DEGRADED

        # Warning if any non-healthy sensors
        if degraded > 0 or critical > 0 or offline > 0:
            return HealthLevel.WARNING

        # Healthy if all sensors healthy
        if healthy == total:
            return HealthLevel.HEALTHY

        return HealthLevel.UNKNOWN

    def get_last_sensor_report(self) -> SystemHealthReport | None:
        """
        Get the last generated sensor health report.

        Returns:
            SystemHealthReport or None
        """
        return self._last_sensor_report

    def get_sensor_health(self, sensor_id: int) -> dict | None:
        """
        Get health status for specific sensor.

        Args:
            sensor_id: Sensor ID

        Returns:
            Health status dict or None
        """
        sensor = self._sensor_entities.get(sensor_id)
        if sensor:
            return sensor.get_health_status().to_dict()
        return None

    def get_unhealthy_sensors(self) -> list[dict]:
        """
        Get list of unhealthy sensors.

        Returns:
            List of sensor info dicts
        """
        unhealthy = []

        for sensor_id, sensor in self._sensor_entities.items():
            health = sensor.get_health_status()

            if health.level not in (HealthLevel.HEALTHY, HealthLevel.UNKNOWN):
                unhealthy.append(
                    {
                        "sensor_id": sensor_id,
                        "name": sensor.name,
                        "type": sensor.sensor_type.value,
                        "health_level": health.level.value,
                        "message": health.message,
                        "consecutive_errors": health.consecutive_errors,
                        "success_rate": health.success_rate,
                    }
                )

        return unhealthy

    def get_sensor_health_trend(self, hours: int = 24) -> dict:
        """
        Get sensor health trend over time.

        Args:
            hours: Hours to look back

        Returns:
            Dict with trend data
        """
        cutoff_time = utc_now() - timedelta(hours=hours)

        # Filter reports within time range
        recent_reports = [r for r in self._sensor_health_history if r.timestamp >= cutoff_time]

        if not recent_reports:
            return {"error": "No health data available for time range"}

        # Calculate trends
        healthy_trend = [r.healthy_sensors for r in recent_reports]
        success_rate_trend = [r.average_success_rate for r in recent_reports]

        return {
            "period_hours": hours,
            "report_count": len(recent_reports),
            "healthy_sensors": {
                "current": healthy_trend[-1] if healthy_trend else 0,
                "average": sum(healthy_trend) / len(healthy_trend) if healthy_trend else 0,
                "trend": healthy_trend,
            },
            "success_rate": {
                "current": success_rate_trend[-1] if success_rate_trend else 0,
                "average": sum(success_rate_trend) / len(success_rate_trend) if success_rate_trend else 0,
                "trend": success_rate_trend,
            },
        }

    def check_sensor_availability(self, sensor_id: int, max_age_seconds: int = 300) -> bool:
        """
        Check if sensor has reported recently.

        Args:
            sensor_id: Sensor ID
            max_age_seconds: Maximum age for last reading (default 5 minutes)

        Returns:
            True if sensor is available
        """
        sensor = self._sensor_entities.get(sensor_id)
        if not sensor:
            return False

        if not sensor._last_read_time:
            return False

        age = (datetime.now() - sensor._last_read_time).total_seconds()
        return age <= max_age_seconds

    # ==================== Custom System Health ====================

    def update_health_status(self, system_id: int, level: SystemHealthLevel, message: str) -> None:
        """Update the health status of a custom system."""
        now = utc_now()
        if system_id in self.health_statuses:
            status = self.health_statuses[system_id]
            status.level = level
            status.message = message
            status.last_check = now
        else:
            status = SystemHealthStatus(system_id=system_id, level=level, message=message, last_check=now)
            self.health_statuses[system_id] = status
        logger.info("Updated health status for system %s: %s", system_id, status.to_dict())

    def get_health_status(self, system_id: int) -> SystemHealthStatus | None:
        """Retrieve the health status of a system."""
        return self.health_statuses.get(system_id)

    def record_incident(self, system_id: int) -> None:
        """Record an incident for a system."""
        if system_id in self.health_statuses:
            self.health_statuses[system_id].record_incident()
            logger.info(
                f"Recorded incident for system {system_id}. Total incidents: {self.health_statuses[system_id].incident_count}"
            )
        else:
            logger.warning("Attempted to record incident for unknown system %s.", system_id)

    def get_overall_health(self) -> list[dict[str, Any]]:
        """Get overall health status for all custom systems."""
        return [status.to_dict() for status in self.health_statuses.values()]

    def get_comprehensive_health_report(self) -> dict[str, Any]:
        """
        Get comprehensive health report aggregating all health sources.

        Returns:
            Dict containing:
            - system_info: Infrastructure status
            - sensor_health: Sensor health statistics
            - anomalies: Recent anomalies from AnomalyDetectionService
            - alerts: Active alerts from AlertService
            - overall_status: Aggregated health level
        """
        report = {"timestamp": iso_now(), "system_info": self.get_system_info(), "overall_status": "healthy"}

        # Get sensor health (now handled directly)
        if self._sensor_entities:
            try:
                sensor_report = self.generate_sensor_health_report()
                report["sensor_health"] = {
                    "total_sensors": sensor_report.total_sensors,
                    "healthy_sensors": sensor_report.healthy_sensors,
                    "degraded_sensors": sensor_report.degraded_sensors,
                    "critical_sensors": sensor_report.critical_sensors,
                    "offline_sensors": sensor_report.offline_sensors,
                    "health_level": sensor_report.system_health_level.value,
                    "average_success_rate": sensor_report.average_success_rate,
                    "issues": sensor_report.issues,
                }

                # Update overall status based on sensor health
                if sensor_report.system_health_level.value in ["critical", "offline"]:
                    report["overall_status"] = "critical"
                elif sensor_report.system_health_level.value == "degraded":
                    report["overall_status"] = "degraded"
            except Exception as e:
                logger.error("Failed to generate sensor health report: %s", e)
                report["sensor_health"] = {"error": str(e)}

        # Get active alerts if available
        if self.alert_service:
            try:
                alert_summary = self.alert_service.get_alert_summary()
                report["alerts"] = alert_summary

                # Critical alerts affect overall status
                if alert_summary.get("active_by_severity", {}).get("critical", 0) > 0:
                    report["overall_status"] = "critical"
                elif alert_summary.get("active_by_severity", {}).get("warning", 0) > 3:
                    report["overall_status"] = "degraded"
            except Exception as e:
                logger.error("Failed to get alert summary: %s", e)
                report["alerts"] = {"error": str(e)}

        # Add custom system health statuses
        if self.health_statuses:
            report["custom_systems"] = self.get_overall_health()

        return report

    def get_system_info(self) -> dict[str, Any]:
        """Get general system information."""
        uptime = self.get_uptime_seconds()
        return {
            "version": self.version,
            "apiStatus": self.api_status,
            "dbStatus": self.db_status,
            "lastBackup": self.last_backup,
            "uptime": uptime,
            "storageUsed": self.storage_used,
            "storageTotal": self.storage_total,
        }

    def check_and_alert_on_health_issues(self) -> list[int]:
        """
        Check system health and create alerts for critical issues.

        Returns:
            List of alert IDs created
        """
        if not self.alert_service:
            logger.warning("Alert service not available, cannot create health alerts")
            return []

        created_alerts = []

        try:
            # Check sensor health (now handled directly)
            if self._sensor_entities:
                unhealthy = self.get_unhealthy_sensors()

                for sensor in unhealthy:
                    # Create alerts for critical sensors
                    if sensor["health_level"] == "critical":
                        alert_id = self.alert_service.create_alert(
                            alert_type=self.alert_service.SENSOR_ANOMALY,
                            severity=self.alert_service.CRITICAL,
                            title=f"Critical: {sensor['name']} Health Issue",
                            message=sensor["message"],
                            source_type="sensor",
                            source_id=sensor["sensor_id"],
                            metadata={
                                "health_level": sensor["health_level"],
                                "success_rate": sensor["success_rate"],
                                "consecutive_errors": sensor["consecutive_errors"],
                            },
                        )
                        created_alerts.append(alert_id)
                    elif sensor["health_level"] == "degraded":
                        alert_id = self.alert_service.create_alert(
                            alert_type=self.alert_service.SENSOR_ANOMALY,
                            severity=self.alert_service.WARNING,
                            title=f"Warning: {sensor['name']} Degraded",
                            message=sensor["message"],
                            source_type="sensor",
                            source_id=sensor["sensor_id"],
                            metadata={"health_level": sensor["health_level"], "success_rate": sensor["success_rate"]},
                        )
                        created_alerts.append(alert_id)

            # Check storage
            if self.storage_total > 0:
                usage_percent = (self.storage_used / self.storage_total) * 100
                if usage_percent > 90:
                    alert_id = self.alert_service.create_alert(
                        alert_type=self.alert_service.SYSTEM_ERROR,
                        severity=self.alert_service.CRITICAL,
                        title="Critical: Storage Almost Full",
                        message=f"Storage usage at {usage_percent:.1f}%",
                        source_type="system",
                        metadata={"usage_percent": usage_percent},
                    )
                    created_alerts.append(alert_id)
                elif usage_percent > 75:
                    alert_id = self.alert_service.create_alert(
                        alert_type=self.alert_service.SYSTEM_ERROR,
                        severity=self.alert_service.WARNING,
                        title="Warning: High Storage Usage",
                        message=f"Storage usage at {usage_percent:.1f}%",
                        source_type="system",
                        metadata={"usage_percent": usage_percent},
                    )
                    created_alerts.append(alert_id)

            # Check DB status
            if self.db_status != "connected":
                alert_id = self.alert_service.create_alert(
                    alert_type=self.alert_service.SYSTEM_ERROR,
                    severity=self.alert_service.CRITICAL,
                    title="Critical: Database Connection Lost",
                    message=f"Database status: {self.db_status}",
                    source_type="system",
                    metadata={"db_status": self.db_status},
                )
                created_alerts.append(alert_id)

            if created_alerts:
                logger.info("Created %s health alerts", len(created_alerts))

        except Exception as e:
            logger.error("Error checking health and creating alerts: %s", e)

        return created_alerts

    def update_infrastructure_status(
        self, api_status: str | None = None, db_status: str | None = None, last_backup: str | None = None
    ) -> None:
        """
        Update infrastructure component statuses.

        Args:
            api_status: API status (online, degraded, offline)
            db_status: Database status (connected, disconnected, error)
            last_backup: Last backup timestamp
        """
        status_changed = False

        if api_status and api_status != self.api_status:
            old_status = self.api_status
            self.api_status = api_status
            status_changed = True
            logger.info("API status changed: %s -> %s", old_status, api_status)

            # Create alert for API issues
            if self.alert_service and api_status in ["degraded", "offline"]:
                severity = self.alert_service.CRITICAL if api_status == "offline" else self.alert_service.WARNING
                self.alert_service.create_alert(
                    alert_type=self.alert_service.SYSTEM_ERROR,
                    severity=severity,
                    title=f"API Status: {api_status.title()}",
                    message=f"API status changed to {api_status}",
                    source_type="infrastructure",
                    metadata={"component": "api", "status": api_status},
                )

        if db_status and db_status != self.db_status:
            old_status = self.db_status
            self.db_status = db_status
            status_changed = True
            logger.info("Database status changed: %s -> %s", old_status, db_status)

            # Create alert for DB issues
            if self.alert_service and db_status != "connected":
                self.alert_service.create_alert(
                    alert_type=self.alert_service.SYSTEM_ERROR,
                    severity=self.alert_service.CRITICAL,
                    title="Database Connection Issue",
                    message=f"Database status: {db_status}",
                    source_type="infrastructure",
                    metadata={"component": "database", "status": db_status},
                )

        if last_backup:
            self.last_backup = last_backup

        if status_changed:
            EventBus.publish(
                ActivityEvent.SYSTEM_HEALTH_CHANGED,
                {
                    "component": "infrastructure",
                    "api_status": self.api_status,
                    "db_status": self.db_status,
                    "timestamp": iso_now(),
                },
            )

    def notify_health_change(self, system_id: int) -> None:
        """Notify other components of a health status change."""
        status = self.get_health_status(system_id)
        if status:
            EventBus.publish(
                ActivityEvent.SYSTEM_HEALTH_CHANGED,
                {
                    "system_id": system_id,
                    "level": status.level.value,
                    "message": status.message,
                    "last_check": status.last_check.isoformat() if status.last_check else None,
                },
            )
            logger.info("Notified health change for system %s.", system_id)

    def get_uptime_seconds(self) -> int:
        """Get the server uptime in seconds from process start time."""
        try:
            return (self.uptime_start and int((utc_now() - self.uptime_start).total_seconds())) or 0
        except Exception as e:
            logger.warning("Failed to calculate server uptime: %s", e)
            return 0

    def storage_usage_update(self, used: int, total: int) -> None:
        """Update storage usage statistics."""
        self.storage_used = used
        self.storage_total = total
        logger.info("Updated storage usage: %s/%s bytes.", used, total)

    def refresh_storage_usage(self, path: str = "/") -> dict[str, Any]:
        """
        Refresh storage usage statistics from filesystem.

        Args:
            path: Path to check (default: root or current drive on Windows)

        Returns:
            Dict with storage metrics
        """
        try:
            # On Windows, use the drive where the app is running
            if os.name == "nt":
                path = os.path.abspath(os.sep)

            if psutil is not None:
                disk_usage = psutil.disk_usage(path)
                total = int(disk_usage.total)
                used = int(disk_usage.used)
                free = int(disk_usage.free)
                usage_percent = float(disk_usage.percent)
            else:
                disk_usage = shutil.disk_usage(path)
                total = int(disk_usage.total)
                used = int(disk_usage.used)
                free = int(disk_usage.free)
                usage_percent = round((used / total) * 100, 1) if total > 0 else 0.0

            self.storage_used = used
            self.storage_total = total

            logger.info("Storage refreshed: %s%% used (%s/%s bytes)", usage_percent, used, total)

            return {
                "total": total,
                "used": used,
                "free": free,
                "percent": usage_percent,
            }
        except Exception as e:
            logger.error("Failed to refresh storage usage: %s", e)
            return {"error": str(e), "total": 0, "used": 0, "free": 0, "percent": 0}

    def check_database_health(self, db_handler: Any | None = None) -> str:
        """
        Check database connection health.

        Args:
            db_handler: Database handler with connection() method

        Returns:
            Status string: "connected", "disconnected", or "error"
        """
        if not db_handler:
            logger.warning("No database handler provided for health check")
            return "unknown"

        try:
            # Try a simple query
            with db_handler.connection() as conn:
                cursor = conn.execute("SELECT 1")
                cursor.fetchone()

            old_status = self.db_status
            self.db_status = "connected"

            if old_status != "connected":
                logger.info("Database health restored: %s -> connected", old_status)
                self.update_infrastructure_status(db_status="connected")

            return "connected"

        except Exception as e:
            logger.error("Database health check failed: %s", e)
            old_status = self.db_status
            self.db_status = "error"

            if old_status != "error":
                self.update_infrastructure_status(db_status="error")

            return "error"

    def check_api_health(self) -> str:
        """
        Check API health based on recent activity and error rates.

        This is a placeholder - actual implementation should track
        request metrics from your API middleware/router.

        Returns:
            Status string: "online", "degraded", or "offline"
        """
        if not hasattr(self, "_api_metrics"):
            return self.api_status

        self._update_api_status_from_metrics()
        return self.api_status

    def record_api_request(self, success: bool, response_time_ms: float) -> None:
        """
        Record an API request for health tracking.

        Args:
            success: Whether the request was successful
            response_time_ms: Response time in milliseconds
        """
        # Initialize tracking if needed
        if not hasattr(self, "_api_metrics"):
            self._api_metrics = {
                "total_requests": 0,
                "failed_requests": 0,
                "slow_requests": 0,
                "avg_response_time": 0.0,
                "response_times": [],
                "recent_results": deque(maxlen=self._api_health_window_size),
                "recent_failures": 0,
            }

        metrics = self._api_metrics
        recent_results = metrics.get("recent_results")
        if recent_results is None:
            recent_results = deque(maxlen=self._api_health_window_size)
            metrics["recent_results"] = recent_results
            metrics["recent_failures"] = 0
        elif getattr(recent_results, "maxlen", None) != self._api_health_window_size:
            recent_results = deque(recent_results, maxlen=self._api_health_window_size)
            metrics["recent_results"] = recent_results
            metrics["recent_failures"] = sum(1 for result in recent_results if result is False)
        elif "recent_failures" not in metrics:
            metrics["recent_failures"] = sum(1 for result in recent_results if result is False)

        metrics["total_requests"] += 1

        if not success:
            metrics["failed_requests"] += 1

        # Track slow requests (above configured threshold)
        if response_time_ms > self._api_health_slow_request_ms:
            metrics["slow_requests"] += 1

        # Track response times (keep last 100)
        metrics["response_times"].append(response_time_ms)
        if len(metrics["response_times"]) > 100:
            metrics["response_times"].pop(0)

        if recent_results is not None:
            if len(recent_results) == recent_results.maxlen:
                removed = recent_results[0]
                if removed is False:
                    metrics["recent_failures"] = max(metrics.get("recent_failures", 0) - 1, 0)
            recent_results.append(success)
            if success is False:
                metrics["recent_failures"] = metrics.get("recent_failures", 0) + 1

        # Calculate average
        if metrics["response_times"]:
            metrics["avg_response_time"] = sum(metrics["response_times"]) / len(metrics["response_times"])

        # Update API status based on metrics
        self._update_api_status_from_metrics()

    def _update_api_status_from_metrics(self) -> None:
        """Update API status based on tracked metrics."""
        if not hasattr(self, "_api_metrics"):
            return

        metrics = self._api_metrics

        recent_results = metrics.get("recent_results")
        recent_total = len(recent_results) if recent_results is not None else 0
        if recent_total > 0:
            error_rate = metrics.get("recent_failures", 0) / recent_total
        else:
            recent_total = min(100, metrics["total_requests"])
            error_rate = metrics["failed_requests"] / recent_total if recent_total > 0 else 0

        sample_count = recent_total if recent_total > 0 else metrics["total_requests"]
        if sample_count < self._api_health_min_samples:
            # Not enough data yet
            return

        old_status = self.api_status

        # Determine status
        if error_rate > self._api_health_error_rate_offline:  # More than offline threshold
            self.api_status = "offline"
        elif (
            error_rate > self._api_health_error_rate_degraded
            or metrics["avg_response_time"] > self._api_health_avg_response_time_ms
        ):  # Above degraded thresholds
            self.api_status = "degraded"
        else:
            self.api_status = "online"

        # Notify if status changed
        if old_status != self.api_status:
            logger.warning("API status changed: %s -> %s", old_status, self.api_status)
            self.update_infrastructure_status(api_status=self.api_status)

    def get_api_metrics(self) -> dict[str, Any]:
        """
        Get current API metrics.

        Returns:
            Dict with API performance metrics
        """
        if not hasattr(self, "_api_metrics"):
            return {
                "total_requests": 0,
                "failed_requests": 0,
                "slow_requests": 0,
                "error_rate": 0.0,
                "avg_response_time_ms": 0.0,
                "status": self.api_status,
            }

        metrics = self._api_metrics
        recent_results = metrics.get("recent_results")
        recent_total = len(recent_results) if recent_results is not None else 0
        if recent_total > 0:
            error_rate = metrics.get("recent_failures", 0) / recent_total
        else:
            recent_total = min(100, metrics["total_requests"])
            error_rate = metrics["failed_requests"] / recent_total if recent_total > 0 else 0

        return {
            "total_requests": metrics["total_requests"],
            "failed_requests": metrics["failed_requests"],
            "slow_requests": metrics["slow_requests"],
            "error_rate": round(error_rate * 100, 2),  # as percentage
            "avg_response_time_ms": round(metrics["avg_response_time"], 2),
            "status": self.api_status,
        }

    def perform_full_health_check(self, db_handler: Any | None = None) -> dict[str, Any]:
        """
        Perform comprehensive health check of all components.

        Args:
            db_handler: Database handler for DB health check

        Returns:
            Complete health status report with computed scores
        """
        logger.info("Performing full health check...")

        # Refresh storage
        storage = self.refresh_storage_usage()

        # Check database
        db_status = self.check_database_health(db_handler)

        # Get API metrics
        api_metrics = self.get_api_metrics()

        # Get comprehensive report
        report = self.get_comprehensive_health_report()

        # Add detailed infrastructure metrics
        report["infrastructure_details"] = {
            "storage": storage,
            "api_metrics": api_metrics,
            "database_status": db_status,
        }

        # Calculate weighted health scores (previously done in JavaScript)
        scores = self._calculate_health_scores(report, storage)
        report["health_scores"] = scores

        logger.info("Health check complete. Overall status: %s, score: %s", report["overall_status"], scores["overall"])

        return report

    def _calculate_health_scores(self, report: dict[str, Any], storage: dict[str, Any]) -> dict[str, Any]:
        """
        Calculate weighted health scores for dashboard display.

        This consolidates client-side score calculations into the backend.

        Args:
            report: The comprehensive health report
            storage: Storage usage metrics

        Returns:
            Dict with overall score and breakdown by category
        """
        # Infrastructure score (40% weight)
        infrastructure_score = 100
        system_info = report.get("system_info", {})
        if system_info.get("apiStatus") != "online":
            infrastructure_score -= 30
        if system_info.get("dbStatus") != "connected":
            infrastructure_score -= 30

        storage_percent = storage.get("percent", 0) if storage else 0
        if storage_percent > 90:
            infrastructure_score -= 20
        elif storage_percent > 75:
            infrastructure_score -= 10

        # Connectivity score (30% weight)
        connectivity_score = 100
        # MQTT status would be checked here if available
        # For now, connectivity is based on API/DB status
        if system_info.get("apiStatus") != "online":
            connectivity_score -= 40

        # Sensor score (30% weight)
        sensor_score = 50  # Default neutral score
        sensor_health = report.get("sensor_health", {})
        if sensor_health and not sensor_health.get("error"):
            total_sensors = sensor_health.get("total_sensors", 0)
            if total_sensors > 0:
                sensor_score = sensor_health.get("average_success_rate", 50)
                if sensor_health.get("critical_sensors", 0) > 0:
                    sensor_score = min(sensor_score, 30)
                elif sensor_health.get("degraded_sensors", 0) > 0:
                    sensor_score = min(sensor_score, 60)

        # Calculate weighted overall score
        overall_score = round((infrastructure_score * 0.4) + (connectivity_score * 0.3) + (sensor_score * 0.3))

        return {
            "overall": overall_score,
            "breakdown": {
                "infrastructure": round(infrastructure_score),
                "connectivity": round(connectivity_score),
                "sensors": round(sensor_score),
            },
        }

    def shutdown(self) -> None:
        """Release external resources before process exit."""
        logger.info("Shutting down System Health Service.")
