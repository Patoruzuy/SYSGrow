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
from .base_processor import IDataProcessor, ProcessorError, PreparedPayloads, SensorResolver
from .validation_processor import ValidationProcessor, ValidationRule, ValidationResult
from .transformation_processor import TransformationProcessor
from .calibration_processor import CalibrationProcessor
from .enrichment_processor import EnrichmentProcessor
from .composite_processor import CompositeProcessor
from .priority_processor import PriorityProcessor, ManualPriority

# Re-export commonly used utilities
from .utils import (
    DASHBOARD_METRICS,
    META_KEYS,
    UNIT_MAP,
    is_meta_key,
    coerce_float,
    coerce_int,
    to_wire_status,
    coerce_numeric_readings,
    infer_power_source,
)

__all__ = [
    # Base
    'IDataProcessor',
    'ProcessorError',
    # Stage Processors
    'ValidationProcessor',
    'ValidationRule',
    'ValidationResult',
    'TransformationProcessor',
    'CalibrationProcessor',
    'EnrichmentProcessor',
    'CompositeProcessor',
    # Priority & Pipeline
    'PriorityProcessor',
    'ManualPriority',
    'SensorResolver',
    'PreparedPayloads',
    # Utilities
    'DASHBOARD_METRICS',
    'META_KEYS',
    'UNIT_MAP',
    'is_meta_key',
    'coerce_float',
    'coerce_int',
    'to_wire_status',
    'coerce_numeric_readings',
    'infer_power_source',
]
