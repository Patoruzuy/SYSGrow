"""
Base Data Processor Interface
==============================
Abstract interface for all data processors.

Stage Processors (ValidationProcessor, TransformationProcessor, etc.):
- Implement validate(), transform(), apply_calibration(), enrich()

Pipeline Processors (CompositeProcessor):
- Also implement process() and build_payloads() for full orchestration
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Optional

if TYPE_CHECKING:
    from app.domain.sensors import CalibrationData, SensorEntity, SensorReading
    from app.schemas.events import DashboardSnapshotPayload, DeviceSensorReadingPayload


class ProcessorError(Exception):
    """Exception raised by data processors."""

    pass


@dataclass
class PreparedPayloads:
    """
    Container for ready-to-emit WebSocket payloads.

    Attributes:
        unit_id: The growth unit ID
        device_payload: Payload for device namespace (all sensors)
        dashboard_payload: Payload for dashboard namespace (priority metrics only)
        controller_events: List of (event_name, payload_dict) for EventBus publishing
    """

    unit_id: int
    device_payload: "DeviceSensorReadingPayload"
    dashboard_payload: Optional["DashboardSnapshotPayload"] = None
    controller_events: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


# Type alias for sensor resolver function
SensorResolver = Callable[[int], Any | None]


class IDataProcessor(ABC):
    """
    Abstract interface for sensor data processors.

    Stage Processors (validate, transform, etc.):
        Implement the individual processing stages. These are combined
        by CompositeProcessor or SensorProcessingPipeline.

    Pipeline Processors:
        Also implement process() and build_payloads() to orchestrate
        the full processing flow and emit WebSocket payloads.

    Pipeline: validate -> calibrate -> transform -> enrich -> build_payloads
    """

    # -------------------------------------------------------------------------
    # Stage Methods (required for stage processors)
    # -------------------------------------------------------------------------

    @abstractmethod
    def validate(self, raw_data: dict[str, Any]) -> dict[str, Any]:
        """
        Validate raw sensor data.

        Args:
            raw_data: Raw data from adapter

        Returns:
            Validated data

        Raises:
            ProcessorError: If validation fails
        """
        raise NotImplementedError()

    @abstractmethod
    def transform(self, validated_data: dict[str, Any], sensor: "SensorEntity") -> "SensorReading":
        """
        Transform validated data into SensorReading.

        Args:
            validated_data: Validated data
            sensor: Sensor entity

        Returns:
            SensorReading object
        """
        raise NotImplementedError()

    def apply_calibration(self, data: dict[str, Any], calibration: "CalibrationData") -> dict[str, Any]:
        """
        Apply calibration to data (optional override).

        Args:
            data: Validated data
            calibration: Calibration data

        Returns:
            Calibrated data
        """
        # Default: no calibration
        return data

    def enrich(self, reading: "SensorReading") -> "SensorReading":
        """
        Enrich reading with metadata (optional override).

        Args:
            reading: Sensor reading

        Returns:
            Enriched reading
        """
        # Default: no enrichment
        return reading

    # -------------------------------------------------------------------------
    # Pipeline Methods (required for pipeline processors like CompositeProcessor)
    # -------------------------------------------------------------------------

    def process(self, sensor: "SensorEntity", raw_data: dict[str, Any]) -> "SensorReading":
        """
        Run the full processing pipeline: validate -> calibrate -> transform -> enrich.

        Pipeline processors (CompositeProcessor) must
        implement this method. Stage processors can leave the default.

        Args:
            sensor: The SensorEntity being processed
            raw_data: Raw data dict from MQTT or adapter

        Returns:
            Processed SensorReading

        Raises:
            ProcessorError: If any processing stage fails
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError()

    def build_payloads(self, *, sensor: "SensorEntity", reading: "SensorReading") -> PreparedPayloads | None:
        """
        Build ready-to-emit WebSocket payloads.

        Pipeline processors (CompositeProcessor) must
        implement this method. Stage processors can leave the default.

        Args:
            sensor: The SensorEntity
            reading: The processed SensorReading

        Returns:
            PreparedPayloads with device and optional dashboard payloads,
            or None if unit_id is invalid (payload should be dropped).

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        raise NotImplementedError()
