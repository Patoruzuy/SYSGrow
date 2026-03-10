"""
Analytics Service — Thin Facade
================================

Sprint 4 refactoring: the original 2,795-line god service has been split
into three focused sub-services.  This facade preserves the public API
so that **no callers need to change** (blueprints, tests, container).

Sub-services:
    * ``SensorAnalyticsService``        – readings, caching, chart data, photoperiod
    * ``EnergyAnalyticsService``        – actuator cost / anomaly / prediction
    * ``EnvironmentalAnalyticsService`` – VPD, trends, correlations, efficiency
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from app.services.application.energy_analytics_service import EnergyAnalyticsService
from app.services.application.environmental_analytics_service import (
    EnvironmentalAnalyticsService,
)
from app.services.application.sensor_analytics_service import SensorAnalyticsService
from app.services.application.threshold_service import ThresholdService
from app.services.hardware.scheduling_service import SchedulingService
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.repositories.growth import GrowthRepository

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Backward-compatible façade that delegates to focused sub-services."""

    # ── Constructor ──────────────────────────────────────────────────

    def __init__(
        self,
        repository: AnalyticsRepository,
        device_repository: DeviceRepository | None = None,
        growth_repository: GrowthRepository | None = None,
        threshold_service: "ThresholdService" | None = None,
        scheduling_service: "SchedulingService" | None = None,
    ):
        self.repository = repository
        self.device_repository = device_repository
        self.device_repo = device_repository
        self.growth_repo = growth_repository
        self.threshold_service = threshold_service
        self.scheduling_service = scheduling_service
        self.logger = logger

        # ---- build sub-services ----
        self._sensor = SensorAnalyticsService(
            repository=repository,
            device_repository=device_repository,
            growth_repository=growth_repository,
            threshold_service=threshold_service,
            scheduling_service=scheduling_service,
        )
        self._energy = EnergyAnalyticsService(
            repository=repository,
            device_repository=device_repository,
            growth_repository=growth_repository,
        )
        self._env = EnvironmentalAnalyticsService(
            repository=repository,
            device_repository=device_repository,
        )

        # Expose caches so external code that references them still works
        self._latest_reading_cache = self._sensor._latest_reading_cache
        self._history_cache = self._sensor._history_cache

    # ══════════════════════════════════════════════════════════════════
    # Sensor Analytics  (delegates → SensorAnalyticsService)
    # ══════════════════════════════════════════════════════════════════

    def get_latest_sensor_reading(self, unit_id: int | None = None) -> dict[str, Any] | None:
        return self._sensor.get_latest_sensor_reading(unit_id)

    def get_latest_energy_reading(self) -> dict[str, Any] | None:
        return self._sensor.get_latest_energy_reading()

    def fetch_sensor_history(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._sensor.fetch_sensor_history(
            start_datetime, end_datetime, unit_id=unit_id, sensor_id=sensor_id, limit=limit
        )

    def get_sensors_history_enriched(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return self._sensor.get_sensors_history_enriched(
            start_datetime, end_datetime, unit_id=unit_id, sensor_id=sensor_id, limit=limit
        )

    def get_sensor_statistics(
        self,
        start_datetime: datetime,
        end_datetime: datetime,
        *,
        unit_id: int | None = None,
        sensor_id: int | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        return self._sensor.get_sensor_statistics(
            start_datetime, end_datetime, unit_id=unit_id, sensor_id=sensor_id, limit=limit
        )

    def get_sensor_summaries_for_unit(
        self,
        unit_id: int,
        start_date: str | None = None,
        end_date: str | None = None,
        sensor_type: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        return self._sensor.get_sensor_summaries_for_unit(
            unit_id, start_date=start_date, end_date=end_date, sensor_type=sensor_type, limit=limit
        )

    def get_sensor_summary_stats_for_harvest(self, unit_id: int, start_date: str, end_date: str) -> dict[str, Any]:
        return self._sensor.get_sensor_summary_stats_for_harvest(unit_id, start_date, end_date)

    def format_sensor_chart_data(self, readings: list[dict], interval: str | None = None) -> dict[str, Any]:
        return self._sensor.format_sensor_chart_data(readings, interval)

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
        return self._sensor.get_enriched_sensor_history(
            start_datetime,
            end_datetime,
            unit_id=unit_id,
            sensor_id=sensor_id,
            limit=limit,
            interval=interval,
            lux_threshold_override=lux_threshold_override,
            prefer_lux=prefer_lux,
            day_start_override=day_start_override,
            day_end_override=day_end_override,
            unit_data=unit_data,
        )

    def get_environmental_dashboard_summary(self, unit_id: int | None = None) -> dict[str, Any]:
        return self._sensor.get_environmental_dashboard_summary(unit_id)

    # ── Plant Readings (Sprint 4 – Task 7) ───────────────────────────

    def get_plant_readings(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """Retrieve paginated plant readings for the frontend."""
        return self._sensor.get_plant_readings(limit=limit, offset=offset)

    def get_latest_plant_readings(self, plant_id: int, limit: int = 50) -> list[dict[str, Any]]:
        return self._sensor.get_latest_plant_readings(plant_id, limit=limit)

    def get_plant_readings_in_window(self, plant_id: int, *, start: str, end: str) -> list[dict[str, Any]]:
        return self._sensor.get_plant_readings_in_window(plant_id, start=start, end=end)

    def get_plants_needing_attention(
        self,
        unit_id: int,
        *,
        moisture_threshold: float = 30.0,
        hours_since_reading: int = 24,
    ) -> list[dict[str, Any]]:
        return self._sensor.get_plants_needing_attention(
            unit_id, moisture_threshold=moisture_threshold, hours_since_reading=hours_since_reading
        )

    # ══════════════════════════════════════════════════════════════════
    # Energy / Actuator Analytics  (delegates → EnergyAnalyticsService)
    # ══════════════════════════════════════════════════════════════════

    def get_actuator_energy_cost_trends(self, actuator_id: int, days: int = 30) -> dict[str, Any]:
        return self._energy.get_actuator_energy_cost_trends(actuator_id, days)

    def get_actuator_optimization_recommendations(self, actuator_id: int) -> dict[str, Any]:
        return self._energy.get_actuator_optimization_recommendations(actuator_id)

    def detect_actuator_power_anomalies(self, actuator_id: int, hours: int = 24) -> dict[str, Any]:
        return self._energy.detect_actuator_power_anomalies(actuator_id, hours)

    def get_comparative_energy_analysis(self, unit_id: int) -> dict[str, Any]:
        return self._energy.get_comparative_energy_analysis(unit_id)

    def get_multi_unit_analytics_overview(self) -> dict[str, Any]:
        return self._energy.get_multi_unit_analytics_overview(
            get_latest_sensor_reading=self._sensor.get_latest_sensor_reading,
        )

    def get_actuators_analytics_overview(self, unit_id: int) -> dict[str, Any]:
        return self._energy.get_actuators_analytics_overview(unit_id)

    def get_actuator_energy_dashboard(self, actuator_id: int) -> dict[str, Any]:
        return self._energy.get_actuator_energy_dashboard(actuator_id)

    def get_energy_dashboard_summary(self, unit_id: int | None = None, days: int = 7) -> dict[str, Any]:
        return self._energy.get_energy_dashboard_summary(unit_id, days)

    def predict_device_failure(self, actuator_id: int, days_ahead: int = 30) -> dict[str, Any]:
        return self._energy.predict_device_failure(actuator_id, days_ahead)

    # ══════════════════════════════════════════════════════════════════
    # Environmental Analytics  (delegates → EnvironmentalAnalyticsService)
    # ══════════════════════════════════════════════════════════════════

    def calculate_vpd_with_zones(self, temperature: float, humidity: float) -> dict[str, Any]:
        return self._env.calculate_vpd_with_zones(temperature, humidity)

    def analyze_metric_trends(self, readings: list[dict], days: int = 7) -> dict[str, Any]:
        return self._env.analyze_metric_trends(readings, days)

    def calculate_environmental_correlations(self, readings: list[dict]) -> dict[str, Any]:
        return self._env.calculate_environmental_correlations(readings)

    def calculate_environmental_stability(
        self,
        unit_id: int,
        end_datetime: datetime | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        return self._env.calculate_environmental_stability(unit_id, end_datetime, days)

    def calculate_energy_efficiency(
        self,
        unit_id: int,
        end_datetime: datetime | None = None,
        days: int = 7,
        limit: int = 5000,
    ) -> dict[str, Any]:
        return self._env.calculate_energy_efficiency(unit_id, end_datetime, days, limit)

    def calculate_automation_effectiveness(
        self,
        unit_id: int,
        end_datetime: datetime | None = None,
        hours: int = 24,
    ) -> dict[str, Any]:
        return self._env.calculate_automation_effectiveness(unit_id, end_datetime, hours)

    def calculate_efficiency_scores_concurrent(
        self,
        unit_id: int,
        end_datetime: datetime | None = None,
        include_previous: bool = False,
    ) -> dict[str, Any]:
        return self._env.calculate_efficiency_scores_concurrent(unit_id, end_datetime, include_previous)

    def get_composite_efficiency_score(
        self,
        unit_id: int,
        include_previous: bool = False,
    ) -> dict[str, Any]:
        return self._env.get_composite_efficiency_score(
            unit_id,
            include_previous=include_previous,
            cache_stats=self._sensor.get_cache_stats(),
        )

    # ══════════════════════════════════════════════════════════════════
    # Cache Management  (delegates → SensorAnalyticsService)
    # ══════════════════════════════════════════════════════════════════

    def get_cache_stats(self) -> dict[str, Any]:
        return self._sensor.get_cache_stats()

    def clear_caches(self) -> None:
        self._sensor.clear_caches()

    def warm_cache(self, unit_ids: list[int] | None = None) -> dict[str, Any]:
        return self._sensor.warm_cache(unit_ids)
