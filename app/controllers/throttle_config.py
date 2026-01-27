"""
Sensor Data Throttling Configuration
=====================================

Configurable throttling for sensor data persistence to balance:
- Database write efficiency (avoid excessive inserts)
- Data quality (capture meaningful changes)
- Historical accuracy (maintain sufficient resolution)

Author: Sebastian Gomez
Date: December 2025
"""

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class ThrottleConfig:
    """
    Configuration for sensor data throttling strategies.
    
    Supports two throttling strategies:
    1. Time-based: Only store readings at intervals (e.g., every 30 minutes)
    2. Change-based: Store when value changes significantly (e.g., >5% change)
    3. Hybrid: Combine both (store if time elapsed OR significant change)
    """
    
    # === Time-based intervals (minutes) ===
    temperature_interval_minutes: int = 30
    humidity_interval_minutes: int = 30
    co2_interval_minutes: int = 30
    voc_interval_minutes: int = 30
    air_quality_interval_minutes: int = 30
    soil_moisture_interval_minutes: int = 60
    lux_interval_minutes: int = 30
    pressure_interval_minutes: int = 30
    ph_interval_minutes: int = 60
    ec_interval_minutes: int = 60
    
    # === Change-based thresholds ===
    # Temperature: Store if changed by this many degrees
    temp_change_threshold_celsius: float = 1.0
    
    # Humidity: Store if changed by this many percentage points
    humidity_change_threshold_percent: float = 5.0
    
    # Soil Moisture: Store if changed by this many percentage points
    soil_moisture_change_threshold_percent: float = 10.0
    
    # CO2: Store if changed by this many ppm
    co2_change_threshold_ppm: float = 100.0
    
    # VOC: Store if changed by this many ppb
    voc_change_threshold_ppb: float = 50.0

    # Air Quality: Store if changed by this much (e.g., IAQ index)
    air_quality_change_threshold: float = 10.0
    
    # Light: Store if changed by this many lux
    light_change_threshold_lux: float = 50.0
    
    # Pressure: Store if changed by this many hPa
    pressure_change_threshold_hpa: float = 1.0
    
    # pH: Store if changed by this much
    ph_change_threshold: float = 0.2
    
    # EC: Store if changed by ~0.1-0.2 mS/cm (100-200 µS/cm)
    ec_change_threshold_us_cm: float = 150.0
    
    # === Strategy Selection ===
    # If True, use HYBRID: Store if (time elapsed OR significant change)
    # If False, use TIME-ONLY: Store only at intervals
    use_hybrid_strategy: bool = True
    
    # === Feature Flags ===
    # Enable/disable throttling entirely (for debugging or high-res logging)
    throttling_enabled: bool = True
    
    # Log every throttle decision (for debugging)
    debug_logging: bool = False
    
    # === Plant Sensor Alert Thresholds ===
    # pH alerting thresholds (for nutrient availability)
    ph_warning_min: float = 5.2
    ph_warning_max: float = 7.2
    ph_critical_min: float = 4.5
    ph_critical_max: float = 8.0
    
    # EC alerting thresholds (for nutrient concentration in mS/cm)
    ec_warning_max: float = 3.0
    ec_critical_max: float = 4.5
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            'time_intervals': {
                'temperature_minutes': self.temperature_interval_minutes,
                'humidity_minutes': self.humidity_interval_minutes,
                'co2_minutes': self.co2_interval_minutes,
                'voc_minutes': self.voc_interval_minutes,
                'air_quality_minutes': self.air_quality_interval_minutes,
                'soil_moisture_minutes': self.soil_moisture_interval_minutes,
                'lux_minutes': self.lux_interval_minutes,
                'pressure_minutes': self.pressure_interval_minutes,
                'ph_minutes': self.ph_interval_minutes,
                'ec_minutes': self.ec_interval_minutes,
            },
            'change_thresholds': {
                'temp_celsius': self.temp_change_threshold_celsius,
                'humidity_percent': self.humidity_change_threshold_percent,
                'soil_moisture_percent': self.soil_moisture_change_threshold_percent,
                'co2': self.co2_change_threshold_ppm,
                'voc': self.voc_change_threshold_ppb,
                'air_quality': self.air_quality_change_threshold,
                'lux': self.light_change_threshold_lux,
                'pressure_hpa': self.pressure_change_threshold_hpa,
                'ph': self.ph_change_threshold,
                'ec_us_cm': self.ec_change_threshold_us_cm,
            },
            'strategy': 'hybrid' if self.use_hybrid_strategy else 'time_only',
            'throttling_enabled': self.throttling_enabled,
            'debug_logging': self.debug_logging,
            'alert_thresholds': {
                'ph_warning_min': self.ph_warning_min,
                'ph_warning_max': self.ph_warning_max,
                'ph_critical_min': self.ph_critical_min,
                'ph_critical_max': self.ph_critical_max,
                'ec_warning_max': self.ec_warning_max,
                'ec_critical_max': self.ec_critical_max,
            },
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ThrottleConfig':
        """Create configuration from dictionary."""
        time_intervals = data.get('time_intervals', {})
        change_thresholds = data.get('change_thresholds', {})
        alert_thresholds = data.get('alert_thresholds', {})
        
        return cls(
            temperature_interval_minutes=time_intervals.get('temperature_minutes', time_intervals.get('temp_humidity_minutes', 30)),
            humidity_interval_minutes=time_intervals.get('humidity_minutes', time_intervals.get('temp_humidity_minutes', 30)),
            co2_interval_minutes=time_intervals.get('co2_minutes', time_intervals.get('co2_voc_minutes', 30)),
            voc_interval_minutes=time_intervals.get('voc_minutes', time_intervals.get('co2_voc_minutes', 30)),
            air_quality_interval_minutes=time_intervals.get('air_quality_minutes', 30),
            soil_moisture_interval_minutes=time_intervals.get('soil_moisture_minutes', 60),
            lux_interval_minutes=time_intervals.get('lux_minutes', time_intervals.get('light_pressure_minutes', 30)),
            pressure_interval_minutes=time_intervals.get('pressure_minutes', time_intervals.get('light_pressure_minutes', 30)),
            ph_interval_minutes=time_intervals.get('ph_minutes', time_intervals.get('ph_ec_minutes', 60)),
            ec_interval_minutes=time_intervals.get('ec_minutes', time_intervals.get('ph_ec_minutes', 60)),
            temp_change_threshold_celsius=change_thresholds.get('temp_celsius', 1.0),
            humidity_change_threshold_percent=change_thresholds.get('humidity_percent', 5.0),
            soil_moisture_change_threshold_percent=change_thresholds.get('soil_moisture_percent', 10.0),
            co2_change_threshold_ppm=change_thresholds.get('co2', change_thresholds.get('co2_ppm', 100.0)),
            voc_change_threshold_ppb=change_thresholds.get('voc', change_thresholds.get('voc_ppb', 50.0)),
            light_change_threshold_lux=change_thresholds.get('lux', change_thresholds.get('light_lux', 500.0)),
            pressure_change_threshold_hpa=change_thresholds.get('pressure_hpa', 5.0),
            ph_change_threshold=change_thresholds.get('ph', 0.2),
            ec_change_threshold_us_cm=change_thresholds.get('ec_us_cm', 150.0),
            use_hybrid_strategy=data.get('strategy', 'hybrid') == 'hybrid',
            throttling_enabled=data.get('throttling_enabled', True),
            debug_logging=data.get('debug_logging', False),
            ph_warning_min=alert_thresholds.get('ph_warning_min', 5.2),
            ph_warning_max=alert_thresholds.get('ph_warning_max', 7.2),
            ph_critical_min=alert_thresholds.get('ph_critical_min', 4.5),
            ph_critical_max=alert_thresholds.get('ph_critical_max', 8.0),
            ec_warning_max=alert_thresholds.get('ec_warning_max', 3.0),
            ec_critical_max=alert_thresholds.get('ec_critical_max', 4.5),
        )


# Default configuration instance
DEFAULT_THROTTLE_CONFIG = ThrottleConfig()
