"""
Data Processors for Sensors
============================
Processing pipeline for sensor data validation, transformation, and enrichment.

Pipeline Architecture:
    raw_data -> validate -> calibrate -> transform -> enrich -> build_payloads

Main Classes:
- CompositeProcessor: Orchestrates all processing stages (validate -> calibrate -> transform -> enrich)
- PriorityProcessor: Manages dashboard sensor priority and selection

Stage Processors:
- ValidationProcessor: Validates raw sensor data
- CalibrationProcessor: Applies calibration offsets
- TransformationProcessor: Transforms data to SensorReading
- EnrichmentProcessor: Adds computed values (VPD, dew point, etc.)

Utilities:
- utils module: Shared helper functions and constants
"""

from .base_processor import IDataProcessor, PreparedPayloads, ProcessorError, SensorResolver
from .calibration_processor import CalibrationProcessor
from .composite_processor import CompositeProcessor
from .enrichment_processor import EnrichmentProcessor
from .priority_processor import ManualPriority, PriorityProcessor
from .transformation_processor import TransformationProcessor

# Re-export commonly used utilities
from .utils import (
    DASHBOARD_METRICS,
    META_KEYS,
    UNIT_MAP,
    coerce_float,
    coerce_int,
    coerce_numeric_readings,
    infer_power_source,
    is_meta_key,
    to_wire_status,
)
from .validation_processor import ValidationProcessor, ValidationResult, ValidationRule

__all__ = [
    # Utilities
    "DASHBOARD_METRICS",
    "META_KEYS",
    "UNIT_MAP",
    "CalibrationProcessor",
    "CompositeProcessor",
    "EnrichmentProcessor",
    # Base
    "IDataProcessor",
    "ManualPriority",
    "PreparedPayloads",
    # Priority & Pipeline
    "PriorityProcessor",
    "ProcessorError",
    "SensorResolver",
    "TransformationProcessor",
    # Stage Processors
    "ValidationProcessor",
    "ValidationResult",
    "ValidationRule",
    "coerce_float",
    "coerce_int",
    "coerce_numeric_readings",
    "infer_power_source",
    "is_meta_key",
    "to_wire_status",
]
