from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from infrastructure.database.decorators import invalidates_caches, repository_cache
from infrastructure.database.ops.devices import DeviceOperations


@dataclass(frozen=True)
class FriendlyNameLookup:
    sensor_id: int
    unit_id: int | None = None


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
        config_data: dict[str, Any] | None = None,
    ) -> int | None:
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

    @repository_cache(maxsize=128, invalidate_on=["create_actuator", "delete_actuator"])
    def list_actuator_configs(
        self,
        unit_id: int | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
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
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
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
        config_data: dict[str, Any] | None = None,
    ) -> int | None:
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
        config_data: dict[str, Any],
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
        name: str | None = None,
        sensor_type: str | None = None,
        protocol: str | None = None,
        model: str | None = None,
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

    @repository_cache(maxsize=128, invalidate_on=["create_sensor", "delete_sensor"])
    def list_sensor_configs(
        self,
        unit_id: int | None = None,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get sensor configs with pagination, optionally filtered by unit.

        Args:
            unit_id: Filter by unit_id (optional)
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of sensor configuration dictionaries
        """
        kwargs: dict[str, Any] = {}
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
        limit: int | None = None,
        offset: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        List all sensors with pagination.

        Args:
            limit: Number of results per page (default: 100, max: 500)
            offset: Number of results to skip (default: 0)

        Returns:
            List of sensor dictionaries
        """
        return self._backend.get_all_sensors(limit=limit, offset=offset)

    def get_by_friendly_name(self, friendly_name: str) -> FriendlyNameLookup | None:
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

    def find_sensor_config_by_id(self, sensor_id: int) -> dict[str, Any] | None:
        return self._backend.get_sensor_config_by_id(sensor_id)

    def find_actuator_config_by_id(self, actuator_id: int) -> dict[str, Any] | None:
        return self._backend.get_actuator_config_by_id(actuator_id)

    def get_actuator_config_by_id(self, actuator_id: int) -> dict[str, Any] | None:
        """Backward-compatible alias for actuator config lookup."""
        return self._backend.get_actuator_config_by_id(actuator_id)

    def get_actuators_by_ids(self, actuator_ids: list[int]) -> dict[int, dict[str, Any]]:
        """Batch-fetch actuator configs. Returns dict keyed by actuator_id."""
        return self._backend.get_actuators_by_ids(actuator_ids)

    def get_sensors_by_ids(self, sensor_ids: list[int]) -> dict[int, dict[str, Any]]:
        """Batch-fetch sensor configs. Returns dict keyed by sensor_id."""
        return self._backend.get_sensors_by_ids(sensor_ids)

    def find_sensors_by_model(self, sensor_model: str) -> list[Any]:
        return self._backend.get_sensors_by_model(sensor_model)

    # Sensor Readings ----------------------------------------------------------
    def record_sensor_reading(
        self,
        *,
        sensor_id: int,
        reading_data: dict[str, Any],
        quality_score: float = 1.0,
    ) -> int | None:
        """Record sensor reading with JSON data."""
        return self._backend.insert_sensor_reading(
            sensor_id=sensor_id,
            reading_data=reading_data,
            quality_score=quality_score,
        )

    def record_sensor_readings_batch(
        self,
        readings: list[tuple[int, dict[str, Any], float]],
    ) -> int:
        """Batch-insert multiple sensor readings (single transaction)."""
        return self._backend.insert_sensor_readings_batch(readings)

    # Calibration --------------------------------------------------------------
    def save_calibration(
        self,
        sensor_id: int,
        measured_value: float,
        reference_value: float,
        calibration_type: str = "linear",
    ) -> int | None:
        """Save calibration point."""
        return self._backend.save_calibration(
            sensor_id=sensor_id,
            measured_value=measured_value,
            reference_value=reference_value,
            calibration_type=calibration_type,
        )

    def get_calibrations(self, sensor_id: int) -> list[dict[str, Any]]:
        """Get all calibration points for a sensor."""
        return self._backend.get_calibrations(sensor_id)

    # Actuator State History ---------------------------------------------------
    def save_actuator_state(
        self,
        actuator_id: int,
        state: str,
        *,
        value: float | None = None,
        timestamp: str | None = None,
    ) -> int | None:
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
    ) -> int | None:
        """Save health monitoring snapshot."""
        return self._backend.save_health_snapshot(
            sensor_id=sensor_id,
            health_score=health_score,
            status=status,
            error_rate=error_rate,
            total_readings=total_readings,
            failed_readings=failed_readings,
        )

    def get_health_history(self, sensor_id: int, limit: int = 100) -> list[dict[str, Any]]:
        """Get health history for a sensor."""
        return self._backend.get_health_history(sensor_id, limit)

    def get_latest_health_batch(self, sensor_ids: list[int]) -> dict[int, dict[str, Any]]:
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
    ) -> int | None:
        """Log detected anomaly."""
        return self._backend.log_anomaly(
            sensor_id=sensor_id,
            value=value,
            mean_value=mean_value,
            std_deviation=std_deviation,
            z_score=z_score,
        )

    def get_anomalies(self, sensor_id: int, limit: int = 100) -> list[dict[str, Any]]:
        """Get anomalies for a sensor."""
        return self._backend.get_anomalies(sensor_id, limit)

    def count_anomalies_for_sensors(
        self,
        sensor_ids: list[int],
        *,
        start: str | None = None,
        end: str | None = None,
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
    ) -> int | None:
        """Save actuator health monitoring snapshot."""
        return self._backend.save_actuator_health_snapshot(
            actuator_id=actuator_id,
            health_score=health_score,
            status=status,
            total_operations=total_operations,
            failed_operations=failed_operations,
            average_response_time=average_response_time,
        )

    def get_actuator_health_history(self, actuator_id: int, limit: int = 100) -> list[dict[str, Any]]:
        """Get health history for an actuator."""
        return self._backend.get_actuator_health_history(actuator_id, limit)

    # Actuator Anomaly Detection -----------------------------------------------
    def log_actuator_anomaly(
        self,
        actuator_id: int,
        anomaly_type: str,
        severity: str,
        details: dict[str, Any] | None = None,
    ) -> int | None:
        """Log detected actuator anomaly."""
        return self._backend.log_actuator_anomaly(
            actuator_id=actuator_id,
            anomaly_type=anomaly_type,
            severity=severity,
            details=details,
        )

    def get_actuator_anomalies(self, actuator_id: int, limit: int = 100) -> list[dict[str, Any]]:
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
        voltage: float | None = None,
        current: float | None = None,
        energy_kwh: float | None = None,
        power_factor: float | None = None,
        frequency: float | None = None,
        temperature: float | None = None,
        is_estimated: bool = False,
    ) -> int | None:
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
        self, actuator_id: int, limit: int = 1000, hours: int | None = None
    ) -> list[dict[str, Any]]:
        """Get power readings for an actuator."""
        return self._backend.get_actuator_power_readings(actuator_id, limit, hours)

    # Actuator State History ---------------------------------------------------
    def get_actuator_state_history(
        self,
        actuator_id: int,
        *,
        limit: int = 100,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._backend.get_actuator_state_history(actuator_id, limit=limit, since=since, until=until)

    def get_unit_actuator_state_history(
        self,
        unit_id: int,
        *,
        limit: int = 100,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
        return self._backend.get_unit_actuator_state_history(unit_id, limit=limit, since=since, until=until)

    def get_recent_actuator_state(
        self,
        *,
        limit: int = 100,
        unit_id: int | None = None,
    ) -> list[dict[str, Any]]:
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
        endpoint: str | None = None,
        broker: str | None = None,
        port: int | None = None,
        unit_id: int | None = None,
        device_id: str | None = None,
        details: str | None = None,
        timestamp: str | None = None,
    ) -> int | None:
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
        connection_type: str | None = None,
        limit: int = 100,
        since: str | None = None,
        until: str | None = None,
    ) -> list[dict[str, Any]]:
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
        calibration_data: dict[str, Any],
    ) -> int | None:
        """Save actuator calibration (power profile, PWM curve, etc.)."""
        return self._backend.save_actuator_calibration(
            actuator_id=actuator_id,
            calibration_type=calibration_type,
            calibration_data=calibration_data,
        )

    def get_actuator_calibrations(self, actuator_id: int) -> list[dict[str, Any]]:
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
        return self._backend.aggregate_sensor_readings_for_period(period_start, period_end, granularity)

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
        start_date: str | None = None,
        end_date: str | None = None,
        sensor_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
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
        return self._backend.get_sensor_summaries_for_unit(unit_id, start_date, end_date, sensor_type, limit)

    def get_sensor_summary_stats_for_harvest(
        self,
        unit_id: int,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
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
        return self._backend.get_sensor_summary_stats_for_harvest(unit_id, start_date, end_date)
