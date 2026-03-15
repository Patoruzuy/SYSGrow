"""
Enrichment Processor

Enriches sensor readings with additional metadata and computed values.

Features:
- Computes derived values (heat index, dew point, VPD) using psychrometrics module
- Adds contextual metadata (battery, signal quality)
- Calculates quality scores
- Flags anomalies based on thresholds
"""
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING
from .base_processor import IDataProcessor
from app.domain.sensors.reading import ReadingStatus
from app.utils.psychrometrics import (
    calculate_vpd_kpa,
    calculate_dew_point_c,
    calculate_heat_index_c,
    compute_derived_metrics,
)

if TYPE_CHECKING:
    from app.domain.sensors import SensorReading

logger = logging.getLogger(__name__)


class EnrichmentProcessor(IDataProcessor):
    """
    Enriches sensor readings with:
    - Computed values (heat index, dew point, VPD)
    - Contextual metadata
    - Quality scores
    - Trend indicators
    """
    
    def __init__(self):
        """Initialize enrichment processor"""
        pass
    
    def validate(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Pass-through validation (handled by ValidationProcessor)"""
        return raw_data
    
    def transform(self, validated_data: Dict[str, Any], sensor) -> Any:
        """Pass-through transformation (handled by TransformationProcessor)"""
        return validated_data
    
    def enrich(self, reading: 'SensorReading') -> 'SensorReading':
        """
        Enrich reading with computed values and metadata.
        
        Uses psychrometrics module for all derived calculations:
        - Heat index (feels-like temperature)
        - Dew point (condensation temperature)
        - VPD (Vapor Pressure Deficit - critical for plant growth)
        
        Args:
            reading: Sensor reading to enrich
            
        Returns:
            Enriched reading (new instance)
        """
        # Skip enrichment for readings with error status
        if reading.status == ReadingStatus.ERROR:
            return reading

        enriched_data = reading.data.copy()
        
        # Compute derived values if we have the necessary inputs
        temp = enriched_data.get('temperature')
        humidity = enriched_data.get('humidity')
        
        if temp is not None and humidity is not None:
            derived = compute_derived_metrics(temp, humidity)
            
            # Map internal keys to dashboard keys
            if derived.get("heat_index_c") is not None:
                enriched_data['heat_index'] = derived["heat_index_c"]
            
            if derived.get("dew_point_c") is not None:
                enriched_data['dew_point'] = derived["dew_point_c"]
            
            if derived.get("vpd_kpa") is not None:
                enriched_data['vpd'] = derived["vpd_kpa"]
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(enriched_data)
        
        # Create new reading with enriched data
        from dataclasses import replace
        enriched_reading = replace(
            reading,
            data=enriched_data,
            quality_score=quality_score
        )
        
        return enriched_reading
    
    def _calculate_quality_score(self, data: Dict[str, Any]) -> float:
        """
        Calculate a quality score for the reading (0.0 to 1.0).
        
        Args:
            data: Sensor data
            
        Returns:
            Quality score (0.0 = poor, 1.0 = excellent)
        """
        score = 1.0
        
        # Penalize for missing expected fields
        expected_fields = self._get_expected_fields(data)
        present_fields = sum(1 for field in expected_fields if field in data)
        if expected_fields:
            completeness = present_fields / len(expected_fields)
            score *= completeness
        
        # Penalize for low battery (if wireless)
        if 'battery' in data:
            battery = data['battery']
            if battery < 20:
                score *= 0.7
            elif battery < 50:
                score *= 0.9
        
        # Penalize for weak signal (if wireless)
        if 'linkquality' in data:
            lq = data['linkquality']
            if lq < 50:
                score *= 0.7
            elif lq < 100:
                score *= 0.9
        
        # Penalize for error field
        if 'error' in data:
            score *= 0.3
        
        return round(score, 3)
    
    def _get_expected_fields(self, data: Dict[str, Any]) -> list:
        """
        Get list of expected fields based on what's present.
        
        Args:
            data: Sensor data
            
        Returns:
            List of expected field names
        """
        expected = []
        
        # Temperature sensor
        if 'temperature' in data:
            expected.append('temperature')
        
        # Humidity sensor
        if 'humidity' in data:
            expected.append('humidity')
        
        # Soil moisture sensor
        if 'soil_moisture' in data:
            expected.append('soil_moisture')
        
        # Light sensor
        if 'lux' in data or 'illuminance' in data:
            expected.extend(['lux', 'illuminance'])
        
        # CO2 sensor
        if 'co2' in data or 'eco2' in data:
            expected.extend(['co2'])
        
        # VOC sensor
        if 'voc' in data or 'tvoc' in data:
            expected.extend(['voc'])
        
        return expected
