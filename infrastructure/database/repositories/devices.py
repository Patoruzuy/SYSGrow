from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from infrastructure.database.ops.devices import DeviceOperations
from infrastructure.database.decorators import (
    repository_cache,
    invalidates_caches
)


@dataclass(frozen=True)
class FriendlyNameLookup:
    sensor_id: int
    unit_id: Optional[int] = None


class DeviceRepository:
    """Facade over sensor and actuator persistence."""

    def __init__(self, backend: DeviceOperations) -> None:
        self._backend = backend

    # Actuators ----------------------------------------------------------------
    @invalidates_caches
    def create_actuator(
        self,
        *,
        unit_id: int,
        name: str,
        actuator_type: str,
        protocol: str,
        model: str = "Generic",
        config_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        return self._backend.insert_actuator(
            unit_id=unit_id,
            name=name,
            actuator_type=actuator_type,
            protocol=protocol,
            model=model,
            config_data=config_data,
        )

    @invalidates_caches
    def delete_actuator(self, actuator_id: int) -> None:
        self._backend.remove_actuator(actuator_id)

    @repository_cache(maxsize=128, invalidate_on=['create_actuator', 'delete_actuator'])
    def list_actuator_configs(
        self,
        unit_id: Optional[int] = None,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List actuator configurations with pagination.

        Args:
            unit_id: Filter by unit_id (optional)
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of actuator configuration dictionaries
        """
        return self._backend.get_actuator_configs(unit_id=unit_id, limit=limit, offset=offset)

    def list_actuators(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all actuators with pagination.

        Args:
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of actuator dictionaries
        """
        return self._backend.get_all_actuators(limit=limit, offset=offset)

    def was_actuator_triggered_recently(self, unit_id: int, actuator_name: str) -> bool:
        return self._backend.check_actuator_triggered(unit_id, actuator_name)

    # Sensors (New Schema) -----------------------------------------------------
    @invalidates_caches
    def create_sensor(
        self,
        *,
        unit_id: int,
        name: str,
        sensor_type: str,
        protocol: str,
        model: str,
        config_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """Create sensor with new schema."""
        return self._backend.insert_sensor(
            unit_id=unit_id,
            name=name,
            sensor_type=sensor_type,
            protocol=protocol,
            model=model,
            config_data=config_data,
        )

    @invalidates_caches
    def update_sensor_config(
        self,
        *,
        sensor_id: int,
        config_data: Dict[str, Any],
    ) -> bool:
        """Update sensor config_data (upsert pattern)."""
        return self._backend.update_sensor_config(
            sensor_id=sensor_id,
            config_data=config_data,
        )

    @invalidates_caches
    def update_sensor_fields(
        self,
        *,
        sensor_id: int,
        name: Optional[str] = None,
        sensor_type: Optional[str] = None,
        protocol: Optional[str] = None,
        model: Optional[str] = None,
    ) -> bool:
        """Update base sensor fields (name/type/protocol/model)."""
        return self._backend.update_sensor_fields(
            sensor_id=sensor_id,
            name=name,
            sensor_type=sensor_type,
            protocol=protocol,
            model=model,
        )

    @invalidates_caches
    def delete_sensor(self, sensor_id: int) -> None:
        self._backend.remove_sensor(sensor_id)

    @repository_cache(maxsize=128, invalidate_on=['create_sensor', 'delete_sensor'])
    def list_sensor_configs(
        self,
        unit_id: Optional[int] = None,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get sensor configs with pagination, optionally filtered by unit.

        Args:
            unit_id: Filter by unit_id (optional)
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of sensor configuration dictionaries
        """
        kwargs: Dict[str, Any] = {}
        if unit_id is not None:
            kwargs["unit_id"] = unit_id
        if limit is not None:
            kwargs["limit"] = limit
        if offset is not None:
            kwargs["offset"] = offset
        return self._backend.get_sensor_configs(**kwargs)

    def list_sensors(
        self,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List all sensors with pagination.

        Args:
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of sensor dictionaries
        """
        return self._backend.get_all_sensors(limit=limit, offset=offset)

    def get_by_friendly_name(self, friendly_name: str) -> Optional[FriendlyNameLookup]:
        """
        Resolve a Zigbee2MQTT friendly_name to a registered sensor.

        Sensors created via `/api/devices/v2/sensors` store Zigbee2MQTT identity in
        `SensorConfig.config_data` under keys like `friendly_name` or `mqtt_topic`.

        Returns:
            FriendlyNameLookup or None if not found.
        """
        if not friendly_name:
            return None

        try:
            sensors = self.list_sensor_configs()
        except Exception:
            return None

        for sensor in sensors:
            protocol = str(sensor.get("protocol") or "").lower()
            if protocol != "zigbee2mqtt":
                continue

            config = sensor.get("config") or {}
            candidate = (
                config.get("friendly_name")
                or config.get("zigbee_friendly_name")
                or config.get("zigbee2mqtt_friendly_name")
                # Legacy/alternate keys seen in older DB schemas
                or config.get("device_id")
                or config.get("device_name")
            )
            if candidate and str(candidate) == friendly_name:
                unit_id = sensor.get("unit_id")
                return FriendlyNameLookup(
                    sensor_id=int(sensor["sensor_id"]),
                    unit_id=int(unit_id) if unit_id is not None else None,
                )

            # Legacy fallback: some older configs only store the base topic (e.g. "zigbee2mqtt")
            # and rely on the sensor's name to match the Zigbee2MQTT friendly_name.
            sensor_name = sensor.get("name")
            if sensor_name and str(sensor_name) == friendly_name:
                unit_id = sensor.get("unit_id")
                return FriendlyNameLookup(
                    sensor_id=int(sensor["sensor_id"]),
                    unit_id=int(unit_id) if unit_id is not None else None,
                )

            mqtt_topic = config.get("mqtt_topic")
            if mqtt_topic and isinstance(mqtt_topic, str) and mqtt_topic.startswith("zigbee2mqtt/"):
                topic_friendly_name = mqtt_topic.split("/", 1)[1]
                if topic_friendly_name == friendly_name:
                    unit_id = sensor.get("unit_id")
                    return FriendlyNameLookup(
                        sensor_id=int(sensor["sensor_id"]),
                        unit_id=int(unit_id) if unit_id is not None else None,
                    )

        return None

    def find_sensor_by_id(self, sensor_id: int):
        return self._backend.get_sensor_by_id(sensor_id)

    def find_sensor_config_by_id(self, sensor_id: int) -> Optional[Dict[str, Any]]:
        return self._backend.get_sensor_config_by_id(sensor_id)

    def find_actuator_config_by_id(self, actuator_id: int) -> Optional[Dict[str, Any]]:
        return self._backend.get_actuator_config_by_id(actuator_id)

    def get_actuator_config_by_id(self, actuator_id: int) -> Optional[Dict[str, Any]]:
        """Backward-compatible alias for actuator config lookup."""
        return self._backend.get_actuator_config_by_id(actuator_id)

    def find_sensors_by_model(self, sensor_model: str) -> List[Any]:
        return self._backend.get_sensors_by_model(sensor_model)

    # Sensor Readings ----------------------------------------------------------
    def record_sensor_reading(
        self,
        *,
        sensor_id: int,
        reading_data: Dict[str, Any],
        quality_score: float = 1.0,
    ) -> Optional[int]:
        """Record sensor reading with JSON data."""
        return self._backend.insert_sensor_reading(
            sensor_id=sensor_id,
            reading_data=reading_data,
            quality_score=quality_score,
        )

    # Calibration --------------------------------------------------------------
    def save_calibration(
        self,
        sensor_id: int,
        measured_value: float,
        reference_value: float,
        calibration_type: str = "linear",
    ) -> Optional[int]:
        """Save calibration point."""
        return self._backend.save_calibration(
            sensor_id=sensor_id,
            measured_value=measured_value,
            reference_value=reference_value,
            calibration_type=calibration_type,
        )

    def get_calibrations(self, sensor_id: int) -> List[Dict[str, Any]]:
        """Get all calibration points for a sensor."""
        return self._backend.get_calibrations(sensor_id)

    # Actuator State History ---------------------------------------------------
    def save_actuator_state(
        self,
        actuator_id: int,
        state: str,
        *,
        value: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> Optional[int]:
        """Persist an actuator state transition to the database."""
        return self._backend.save_actuator_state(
            actuator_id=actuator_id,
            state=state,
            value=value,
            timestamp=timestamp,
        )

    # Health Monitoring --------------------------------------------------------
    def save_health_snapshot(
        self,
        sensor_id: int,
        health_score: int,
        status: str,
        error_rate: float,
        total_readings: int = 0,
        failed_readings: int = 0,
    ) -> Optional[int]:
        """Save health monitoring snapshot."""
        return self._backend.save_health_snapshot(
            sensor_id=sensor_id,
            health_score=health_score,
            status=status,
            error_rate=error_rate,
            total_readings=total_readings,
            failed_readings=failed_readings,
        )

    def get_health_history(self, sensor_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get health history for a sensor."""
        return self._backend.get_health_history(sensor_id, limit)

    def get_latest_health_batch(
        self, sensor_ids: List[int]
    ) -> Dict[int, Dict[str, Any]]:
        """Get most recent health snapshot for each sensor in a single query.

        Returns a dict mapping sensor_id → latest health row.
        """
        return self._backend.get_latest_health_batch(sensor_ids)

    # Anomaly Detection --------------------------------------------------------
    def log_anomaly(
        self,
        sensor_id: int,
        value: float,
        mean_value: float,
        std_deviation: float,
        z_score: float,
    ) -> Optional[int]:
        """Log detected anomaly."""
        return self._backend.log_anomaly(
            sensor_id=sensor_id,
            value=value,
            mean_value=mean_value,
            std_deviation=std_deviation,
            z_score=z_score,
        )

    def get_anomalies(self, sensor_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get anomalies for a sensor."""
        return self._backend.get_anomalies(sensor_id, limit)

    def count_anomalies_for_sensors(
        self,
        sensor_ids: List[int],
        *,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> int:
        """Count anomalies for a set of sensors, optionally within a datetime range."""
        return self._backend.count_anomalies_for_sensors(sensor_ids, start=start, end=end)

    # Actuator Health ----------------------------------------------------------
    def save_actuator_health_snapshot(
        self,
        actuator_id: int,
        health_score: int,
        status: str,
        total_operations: int = 0,
        failed_operations: int = 0,
        average_response_time: float = 0.0,
    ) -> Optional[int]:
        """Save actuator health monitoring snapshot."""
        return self._backend.save_actuator_health_snapshot(
            actuator_id=actuator_id,
            health_score=health_score,
            status=status,
            total_operations=total_operations,
            failed_operations=failed_operations,
            average_response_time=average_response_time,
        )

    def get_actuator_health_history(self, actuator_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get health history for an actuator."""
        return self._backend.get_actuator_health_history(actuator_id, limit)

    # Actuator Anomaly Detection -----------------------------------------------
    def log_actuator_anomaly(
        self,
        actuator_id: int,
        anomaly_type: str,
        severity: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """Log detected actuator anomaly."""
        return self._backend.log_actuator_anomaly(
            actuator_id=actuator_id,
            anomaly_type=anomaly_type,
            severity=severity,
            details=details,
        )

    def get_actuator_anomalies(self, actuator_id: int, limit: int = 100) -> List[Dict[str, Any]]:
        """Get anomalies for an actuator."""
        return self._backend.get_actuator_anomalies(actuator_id, limit)

    def resolve_actuator_anomaly(self, anomaly_id: int) -> bool:
        """Mark an actuator anomaly as resolved."""
        return self._backend.resolve_actuator_anomaly(anomaly_id)

    # Actuator Power Readings --------------------------------------------------
    def save_actuator_power_reading(
        self,
        actuator_id: int,
        power_watts: float,
        voltage: Optional[float] = None,
        current: Optional[float] = None,
        energy_kwh: Optional[float] = None,
        power_factor: Optional[float] = None,
        frequency: Optional[float] = None,
        temperature: Optional[float] = None,
        is_estimated: bool = False,
    ) -> Optional[int]:
        """Save actuator power reading."""
        return self._backend.save_actuator_power_reading(
            actuator_id=actuator_id,
            power_watts=power_watts,
            voltage=voltage,
            current=current,
            energy_kwh=energy_kwh,
            power_factor=power_factor,
            frequency=frequency,
            temperature=temperature,
            is_estimated=is_estimated,
        )

    def get_actuator_power_readings(
        self, 
        actuator_id: int, 
        limit: int = 1000,
        hours: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get power readings for an actuator."""
        return self._backend.get_actuator_power_readings(actuator_id, limit, hours)

    # Actuator State History ---------------------------------------------------
    def get_actuator_state_history(
        self,
        actuator_id: int,
        *,
        limit: int = 100,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self._backend.get_actuator_state_history(
            actuator_id, limit=limit, since=since, until=until
        )

    def get_unit_actuator_state_history(
        self,
        unit_id: int,
        *,
        limit: int = 100,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self._backend.get_unit_actuator_state_history(
            unit_id, limit=limit, since=since, until=until
        )

    def get_recent_actuator_state(
        self,
        *,
        limit: int = 100,
        unit_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        return self._backend.get_recent_actuator_state(limit=limit, unit_id=unit_id)

    def prune_actuator_state_history(self, days: int) -> int:
        """Delete state history entries older than N days. Returns rows deleted."""
        return self._backend.prune_actuator_state_history(days)

    def prune_sensor_readings(self, days: int) -> int:
        """Delete sensor reading entries older than N days. Returns rows deleted."""
        return self._backend.prune_sensor_readings(days)

    # Connectivity History ----------------------------------------------------
    def save_connectivity_event(
        self,
        *,
        connection_type: str,
        status: str,
        endpoint: Optional[str] = None,
        broker: Optional[str] = None,
        port: Optional[int] = None,
        unit_id: Optional[int] = None,
        device_id: Optional[str] = None,
        details: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> Optional[int]:
        if endpoint is None and broker:
            endpoint = f"{broker}:{port}" if port else broker
        return self._backend.save_connectivity_event(
            connection_type,
            status,
            endpoint=endpoint,
            port=port,
            unit_id=unit_id,
            device_id=device_id,
            details=details,
            timestamp=timestamp,
        )

    def get_connectivity_history(
        self,
        *,
        connection_type: Optional[str] = None,
        limit: int = 100,
        since: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        return self._backend.get_connectivity_history(
            connection_type=connection_type,
            limit=limit,
            since=since,
            until=until,
        )

    # Actuator Calibration -----------------------------------------------------
    def save_actuator_calibration(
        self,
        actuator_id: int,
        calibration_type: str,
        calibration_data: Dict[str, Any],
    ) -> Optional[int]:
        """Save actuator calibration (power profile, PWM curve, etc.)."""
        return self._backend.save_actuator_calibration(
            actuator_id=actuator_id,
            calibration_type=calibration_type,
            calibration_data=calibration_data,
        )

    def get_actuator_calibrations(self, actuator_id: int) -> List[Dict[str, Any]]:
        """Get all calibrations for an actuator."""
        return self._backend.get_actuator_calibrations(actuator_id)

    # Sensor Reading Aggregation (for Harvest Reports) -------------------------
    def aggregate_sensor_readings_for_period(
        self,
        period_start: str,
        period_end: str,
        granularity: str = "daily",
    ) -> int:
        """
        Aggregate sensor readings for a time period and save to SensorReadingSummary.

        This should be run BEFORE pruning to preserve summarized data for harvest reports.

        Args:
            period_start: ISO timestamp for start of period
            period_end: ISO timestamp for end of period
            granularity: 'daily', 'hourly', or 'weekly'

        Returns:
            Number of summary records created
        """
        return self._backend.aggregate_sensor_readings_for_period(
            period_start, period_end, granularity
        )

    def aggregate_readings_by_days_old(self, days_threshold: int) -> int:
        """
        Aggregate all readings older than N days that haven't been summarized yet.

        This creates daily summaries for data that will soon be pruned.

        Args:
            days_threshold: Days threshold (e.g., 25 to aggregate before 30-day prune)

        Returns:
            Total summary records created
        """
        return self._backend.aggregate_readings_by_days_old(days_threshold)

    def get_sensor_summaries_for_unit(
        self,
        unit_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        sensor_type: Optional[str] = None,
        limit: int = 1000,
    ) -> List[Dict[str, Any]]:
        """
        Get aggregated sensor summaries for a unit (used in harvest reports).

        Args:
            unit_id: Growth unit ID
            start_date: Optional start date filter
            end_date: Optional end date filter
            sensor_type: Optional filter by sensor type
            limit: Max records to return

        Returns:
            List of summary records
        """
        return self._backend.get_sensor_summaries_for_unit(
            unit_id, start_date, end_date, sensor_type, limit
        )

    def get_sensor_summary_stats_for_harvest(
        self,
        unit_id: int,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        """
        Get aggregated statistics for a harvest report.

        Combines all summaries in the period to provide overall stats by sensor type.

        Args:
            unit_id: Growth unit ID
            start_date: Cycle start date
            end_date: Cycle end date

        Returns:
            Dict with stats grouped by sensor_type
        """
        return self._backend.get_sensor_summary_stats_for_harvest(
            unit_id, start_date, end_date
        )
