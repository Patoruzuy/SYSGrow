"""
Calibration Data
================
Manages sensor calibration for accuracy.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Callable, List
from enum import Enum


class CalibrationType(str, Enum):
    """Types of calibration"""
    LINEAR = "linear"  # y = mx + b
    POLYNOMIAL = "polynomial"  # y = a0 + a1*x + a2*x^2 + ...
    LOOKUP_TABLE = "lookup_table"  # Interpolation table
    CUSTOM = "custom"  # Custom calibration function


@dataclass
class CalibrationData:
    """
    Calibration data for a sensor.
    Supports multiple calibration methods.
    """
    sensor_id: int
    calibration_type: CalibrationType
    calibrated_at: datetime
    calibrated_by: str  # User or system
    
    # Linear calibration (y = slope * x + offset)
    slope: Optional[float] = None
    offset: Optional[float] = None
    
    # Polynomial calibration
    coefficients: Optional[List[float]] = None
    
    # Lookup table (value -> calibrated_value)
    lookup_table: Optional[Dict[float, float]] = None
    
    # Custom calibration function (stored as reference, not serializable)
    custom_function: Optional[Callable] = field(default=None, repr=False)
    
    # Metadata
    reference_values: Optional[List[float]] = None  # Known reference points
    measured_values: Optional[List[float]] = None   # Measured values at references
    notes: Optional[str] = None
    
    def apply(self, raw_value: float) -> float:
        """
        Apply calibration to a raw sensor value.
        
        Args:
            raw_value: Raw sensor reading
            
        Returns:
            Calibrated value
        """
        if self.calibration_type == CalibrationType.LINEAR:
            if self.slope is None or self.offset is None:
                raise ValueError("Linear calibration requires slope and offset")
            return (raw_value * self.slope) + self.offset
        
        elif self.calibration_type == CalibrationType.POLYNOMIAL:
            if not self.coefficients:
                raise ValueError("Polynomial calibration requires coefficients")
            result = 0.0
            for i, coef in enumerate(self.coefficients):
                result += coef * (raw_value ** i)
            return result
        
        elif self.calibration_type == CalibrationType.LOOKUP_TABLE:
            if not self.lookup_table:
                raise ValueError("Lookup table calibration requires lookup_table")
            return self._interpolate(raw_value, self.lookup_table)
        
        elif self.calibration_type == CalibrationType.CUSTOM:
            if not self.custom_function:
                raise ValueError("Custom calibration requires custom_function")
            return self.custom_function(raw_value)
        
        return raw_value
    
    def _interpolate(self, value: float, table: Dict[float, float]) -> float:
        """Linear interpolation from lookup table"""
        sorted_keys = sorted(table.keys())
        
        # Out of bounds - extrapolate or clamp
        if value <= sorted_keys[0]:
            return table[sorted_keys[0]]
        if value >= sorted_keys[-1]:
            return table[sorted_keys[-1]]
        
        # Find surrounding points
        for i in range(len(sorted_keys) - 1):
            x1, x2 = sorted_keys[i], sorted_keys[i + 1]
            if x1 <= value <= x2:
                y1, y2 = table[x1], table[x2]
                # Linear interpolation
                return y1 + (y2 - y1) * (value - x1) / (x2 - x1)
        
        return value
    
    def to_dict(self) -> Dict:
        """Convert to dictionary (excludes custom_function)"""
        return {
            'sensor_id': self.sensor_id,
            'calibration_type': self.calibration_type.value,
            'calibrated_at': self.calibrated_at.isoformat(),
            'calibrated_by': self.calibrated_by,
            'slope': self.slope,
            'offset': self.offset,
            'coefficients': self.coefficients,
            'lookup_table': self.lookup_table,
            'reference_values': self.reference_values,
            'measured_values': self.measured_values,
            'notes': self.notes
        }
