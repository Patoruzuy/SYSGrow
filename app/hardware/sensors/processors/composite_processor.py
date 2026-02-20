"""
Composite Processor
===================
Chains multiple processors into a single pipeline.

Implements both stage methods and pipeline methods (process, build_payloads)
so it can be used directly by mqtt_sensor_service.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Callable, Iterable

from app.enums.events import SensorEvent

from .base_processor import IDataProcessor, PreparedPayloads, ProcessorError
from .utils import (
    UNIT_MAP,
    coerce_int,
    coerce_numeric_readings,
    infer_power_source,
    to_wire_status,
)

if TYPE_CHECKING:
    from app.domain.sensors import CalibrationData, SensorEntity, SensorReading
    from app.hardware.sensors.processors.priority_processor import PriorityProcessor

logger = logging.getLogger(__name__)

# Type alias for sensor resolver
SensorResolver = Callable[[int], Any | None]


class CompositeProcessor(IDataProcessor):
    """
    Composite processor that chains validation, calibration, transformation, and enrichment.

    Implements the full pipeline including process() and build_payloads() methods,
    so it can be used directly by mqtt_sensor_service.

    Pipeline: validate → calibrate → transform → enrich → build_payloads
    """

    def __init__(
        self,
        validator: IDataProcessor,
        calibrator: IDataProcessor,
        transformer: IDataProcessor,
        enricher: IDataProcessor,
        priority: "PriorityProcessor" | None = None,
        resolve_sensor: SensorResolver | None = None,
        units_map: dict[str, str] | None = None,
        meta_keys: Iterable[str] | None = None,
    ):
        """
        Initialize composite processor with individual processors.

        Args:
            validator: Validation processor
            calibrator: Calibration processor
            transformer: Transformation processor
            enricher: Enrichment processor
            priority: Optional PriorityProcessor for dashboard metric selection
            resolve_sensor: Optional function to resolve sensor_id -> SensorEntity
            meta_keys: Override set of metadata keys to exclude from readings
        """
        self.validator = validator
        self.calibrator = calibrator
        self.transformer = transformer
        self.enricher = enricher
        self._priority = priority
        self._resolve_sensor = resolve_sensor

        # Unit string mapping (can be overridden)
        self._units_map = units_map or UNIT_MAP.copy()

        # Keys that should be in meta fields, not readings
        self._meta_keys = set(meta_keys or {"battery", "linkquality", "report_interval"})

    # -------------------------------------------------------------------------
    # Stage Methods
    # -------------------------------------------------------------------------

    def validate(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate raw sensor data using validator processor.

        Args:
            raw_data: Raw data from adapter

        Returns:
            Validated data

        Raises:
            ProcessorError: If validation fails
        """
        return self.validator.validate(raw_data)

    def apply_calibration(self, data: dict[str, Any], calibration: "CalibrationData") -> dict[str, Any]:
        """
        Apply calibration using calibrator processor.

        Args:
            data: Validated data
            calibration: Calibration data

        Returns:
            Calibrated data
        """
        return self.calibrator.apply_calibration(data, calibration)

    def transform(self, validated_data: dict[str, Any], sensor: "SensorEntity") -> "SensorReading":
        """
        Transform validated data into SensorReading using transformer processor.

        Args:
            validated_data: Validated data
            sensor: Sensor entity

        Returns:
            SensorReading object
        """
        return self.transformer.transform(validated_data, sensor)

    def enrich(self, reading: "SensorReading") -> "SensorReading":
        """
        Enrich reading with metadata using enricher processor.

        Args:
            reading: Sensor reading

        Returns:
            Enriched reading
        """
        return self.enricher.enrich(reading)

    # -------------------------------------------------------------------------
    # Pipeline Methods
    # -------------------------------------------------------------------------

    def process(self, sensor: "SensorEntity", raw_data: dict[str, Any]) -> "SensorReading":
        """
        Run the full processing pipeline: validate -> calibrate -> transform -> enrich.

        Args:
            sensor: The SensorEntity being processed
            raw_data: Raw data dict from MQTT or adapter

        Returns:
            Processed SensorReading

        Raises:
            ProcessorError: If any processing stage fails
        """
        if sensor is None:
            raise ProcessorError("sensor is required")
        if not isinstance(raw_data, dict):
            raise ProcessorError("raw_data must be a dict")

        try:
            # 0) Pre-process: Standardize field names & Flatten nested data
            # Delegated to TransformationProcessor to keep standardization logic centralized.
            sanitized = self.transformer.standardize_fields(raw_data, meta_keys=set(self._meta_keys))

            # 1) Validate
            validated = self.validate(sanitized)

            # 2) Apply calibration (if sensor has calibration data)
            calibration = getattr(sensor, "_calibration", None)
            if calibration is not None:
                validated = self.apply_calibration(validated, calibration)

            # 3) Transform to SensorReading
            reading = self.transform(validated, sensor)

            # 4) Enrich
            reading = self.enrich(reading)

            return reading

        except ProcessorError:
            raise
        except Exception as e:
            logger.error("Pipeline processing failed for sensor %s: %s", getattr(sensor, "id", "?"), e)
            raise ProcessorError(f"Processing failed: {e}") from e

    def build_payloads(self, *, sensor: "SensorEntity", reading: "SensorReading") -> PreparedPayloads | None:
        """
        Build ready-to-emit WebSocket payloads.

        Args:
            sensor: The SensorEntity
            reading: The processed SensorReading
        raise NotImplementedError()
        Returns:
            PreparedPayloads with device and optional dashboard payloads,
            or None if unit_id is invalid (payload should be dropped).
        """
        from app.schemas.events import DashboardSnapshotPayload

        # Strict unit_id validation
        unit_id = int(getattr(reading, "unit_id", 0) or 0)
        if unit_id <= 0:
            logger.debug("Dropping payload: invalid unit_id")
            return None

        sensor_id = int(getattr(reading, "sensor_id", getattr(sensor, "id", 0)) or 0)
        if sensor_id <= 0:
            logger.debug("Dropping payload: invalid sensor_id")
            return None

        # Extract reading data
        data = getattr(reading, "data", None) or {}

        # Get numeric readings (excluding meta keys)
        numeric = coerce_numeric_readings(data, exclude_meta=True)
        for k in list(numeric.keys()):
            if k in self._meta_keys:
                numeric.pop(k, None)

        if not numeric:
            logger.debug("Dropping payload: no numeric readings")
            return None

        # Build device payload
        device_payload = self._build_device_payload(
            sensor=sensor,
            reading=reading,
            unit_id=unit_id,
            sensor_id=sensor_id,
            data=data,
            numeric=numeric,
        )

        # Build dashboard payload via priority processor (if available)
        dashboard_payload: DashboardSnapshotPayload | None = None
        if self._priority is not None:
            try:
                dashboard_payload = self._priority.ingest(
                    sensor=sensor,
                    reading=reading,
                    resolve_sensor=self._resolve_sensor,
                )
            except Exception as e:
                logger.warning("Priority processor failed: %s", e)

        controller_events = self._build_controller_events(
            sensor=sensor,
            reading=reading,
            unit_id=unit_id,
            sensor_id=sensor_id,
        )

        return PreparedPayloads(
            unit_id=unit_id,
            device_payload=device_payload,
            dashboard_payload=dashboard_payload,
            controller_events=controller_events,
        )

    def set_priority_processor(self, priority: "PriorityProcessor") -> None:
        """Set or update the priority processor."""
        self._priority = priority

    def set_resolve_sensor(self, resolver: SensorResolver) -> None:
        """Set or update the sensor resolver function."""
        self._resolve_sensor = resolver

    def get_dashboard_snapshot(self, *, unit_id: int):
        """Return the current dashboard snapshot for a unit.

        Uses the priority processor's in-memory state (last readings, primary mapping).
        Returns None if priority processing is disabled or no metrics are available.
        """
        if self._priority is None:
            return None

        try:
            uid = int(unit_id)
        except Exception:
            return None
        if uid <= 0:
            return None

        try:
            return self._priority.build_snapshot_for_unit(
                unit_id=uid,
                resolve_sensor=self._resolve_sensor,
            )
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    def _build_controller_events(
        self,
        *,
        sensor: "SensorEntity",
        reading: "SensorReading",
        unit_id: int,
        sensor_id: int,
    ) -> list[tuple[str, dict[str, Any]]]:
        """Build EventBus events for control/persistence."""
        data = getattr(reading, "data", None) or {}

        ts = getattr(reading, "timestamp", None)
        timestamp = ts.isoformat() if hasattr(ts, "isoformat") else None

        payload_base: dict[str, Any] = {
            "unit_id": unit_id,
            "sensor_id": sensor_id,
            "timestamp": timestamp,
        }

        def is_primary(metric: str) -> bool:
            if self._priority is None:
                return True
            try:
                primary = self._priority.get_primary_sensor(unit_id, metric)
                # If no primary is selected yet, we allow the event through (First sensor wins/Legacy fallback)
                if primary is None:
                    return self._priority.is_primary_metric(sensor, metric)
                return int(primary) == int(sensor_id)
            except Exception:
                return True

        events: list[tuple[str, dict[str, Any]]] = []

        temperature = data.get("temperature")
        humidity = data.get("humidity")
        if temperature is not None and is_primary("temperature"):
            payload = {**payload_base, "temperature": temperature}
            if humidity is not None:
                payload["humidity"] = humidity
            events.append((SensorEvent.TEMPERATURE_UPDATE.value, payload))
        elif humidity is not None and is_primary("humidity"):
            events.append((SensorEvent.HUMIDITY_UPDATE.value, {**payload_base, "humidity": humidity}))

        # Include derived metrics in temperature payload if available and primary.
        if temperature is not None and is_primary("temperature"):
            vpd = data.get("vpd")
            dew_point = data.get("dew_point")
            heat_index = data.get("heat_index")
            if events and events[-1][0] == SensorEvent.TEMPERATURE_UPDATE.value:
                if vpd is not None:
                    events[-1][1]["vpd"] = vpd
                if dew_point is not None:
                    events[-1][1]["dew_point"] = dew_point
                if heat_index is not None:
                    events[-1][1]["heat_index"] = heat_index

        soil_moisture = data.get("soil_moisture")
        if soil_moisture is not None:
            events.append((SensorEvent.SOIL_MOISTURE_UPDATE.value, {**payload_base, "soil_moisture": soil_moisture}))

        co2 = data.get("co2", data.get("co2_ppm"))
        voc = data.get("voc", data.get("voc_ppb"))
        if co2 is not None and is_primary("co2"):
            payload = {**payload_base, "co2": co2}
            if voc is not None:
                payload["voc"] = voc
            events.append((SensorEvent.CO2_UPDATE.value, payload))
        elif voc is not None and is_primary("voc"):
            events.append((SensorEvent.VOC_UPDATE.value, {**payload_base, "voc": voc}))

        # Light (lux) - only from primary light sensor.
        lux = data.get("lux", data.get("illuminance", data.get("light_lux")))
        if lux is not None and is_primary("lux"):
            events.append((SensorEvent.LIGHT_UPDATE.value, {**payload_base, "lux": lux}))

        # Pressure - only from primary pressure sensor (typically environment sensor).
        pressure = data.get("pressure", data.get("pressure_hpa"))
        if pressure is not None and is_primary("pressure"):
            events.append((SensorEvent.PRESSURE_UPDATE.value, {**payload_base, "pressure": pressure}))

        # pH - per-sensor (no primary gating).
        ph = data.get("ph")
        if ph is not None:
            events.append((SensorEvent.PH_UPDATE.value, {**payload_base, "ph": ph}))

        # EC (electrical conductivity) - per-sensor.
        ec = data.get("ec", data.get("electrical_conductivity"))
        if ec is not None:
            events.append((SensorEvent.EC_UPDATE.value, {**payload_base, "ec": ec}))

        return events

    def _build_device_payload(
        self,
        *,
        sensor: "SensorEntity",
        reading: "SensorReading",
        unit_id: int,
        sensor_id: int,
        data: dict[str, Any],
        numeric: dict[str, float],
    ):
        """Build the device sensor reading payload."""
        from app.schemas.events import DeviceSensorReadingPayload
        from app.utils.time import utc_now

        # Extract metadata fields
        battery = coerce_int(data.get("battery"))
        linkquality = coerce_int(data.get("linkquality"))

        # Build units mapping
        units = getattr(reading, "units", None)
        if not isinstance(units, dict) or not units:
            units = {k: self._units_map.get(k, "") for k in numeric}

        # Extract status
        status = to_wire_status(getattr(reading, "status", "success"))

        # Extract timestamp
        ts = getattr(reading, "timestamp", None)
        if hasattr(ts, "isoformat"):
            timestamp = ts.isoformat()
        elif isinstance(ts, str):
            timestamp = ts
        else:
            timestamp = utc_now().isoformat()

        # Quality score
        quality_score = getattr(reading, "quality_score", None)
        if quality_score is None:
            quality_score = data.get("quality_score")
        try:
            quality_score = float(quality_score) if quality_score is not None else None
        except (ValueError, TypeError):
            quality_score = None

        # Anomaly info
        is_anomaly = bool(getattr(reading, "is_anomaly", False))
        anomaly_reason = getattr(reading, "anomaly_reason", None)

        # Calibration flag
        calibration_applied = bool(getattr(reading, "calibration_applied", False))

        # Power source
        power_source = infer_power_source(data)

        # Sensor metadata
        sensor_name = str(getattr(reading, "sensor_name", getattr(sensor, "name", "")) or "")
        sensor_type_raw = getattr(reading, "sensor_type", None) or getattr(sensor, "sensor_type", None)
        if hasattr(sensor_type_raw, "value"):
            sensor_type = str(sensor_type_raw.value)
        else:
            sensor_type = str(sensor_type_raw or "").lower()

        return DeviceSensorReadingPayload(
            schema_version=1,
            sensor_id=sensor_id,
            unit_id=unit_id,
            sensor_name=sensor_name,
            sensor_type=sensor_type,
            readings=numeric,
            units=units,
            status=status,
            timestamp=timestamp,
            battery=battery,
            power_source=power_source,
            linkquality=linkquality,
            quality_score=quality_score,
            is_anomaly=is_anomaly,
            anomaly_reason=anomaly_reason,
            calibration_applied=calibration_applied,
        )
