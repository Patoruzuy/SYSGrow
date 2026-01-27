"""
Validation Processor
====================
Validates sensor readings using configurable rules.
"""
import logging
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass
from enum import Enum
from .base_processor import IDataProcessor, ProcessorError

logger = logging.getLogger(__name__)


class ValidationType(str, Enum):
    """Types of validation rules"""
    REQUIRED_FIELDS = "required_fields"
    TYPE_CHECK = "type_check"
    RANGE_CHECK = "range_check"
    PATTERN_MATCH = "pattern_match"
    CUSTOM = "custom"


@dataclass
class ValidationRule:
    """
    A single validation rule.
    """
    name: str
    validation_type: ValidationType
    params: Dict[str, Any]
    error_message: str
    is_critical: bool = True  # If False, log warning instead of raising error


@dataclass
class ValidationResult:
    """Result of validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]


class ValidationProcessor(IDataProcessor):
    """
    Validates sensor data using a chain of validation rules.
    
    Supports:
    - Required field validation
    - Type checking
    - Range validation (min/max)
    - Pattern matching
    - Custom validation functions
    """
    
    def __init__(self, sensor_type: str):
        """
        Initialize validation processor.
        
        Args:
            sensor_type: Type of sensor (determines default rules)
        """
        self.sensor_type = sensor_type
        self.rules: List[ValidationRule] = []
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Setup default validation rules based on sensor type"""
        from app.domain.sensors import SensorType
        
        # Common rules for all sensors
        self.add_rule(ValidationRule(
            name="no_error_field",
            validation_type=ValidationType.CUSTOM,
            params={'function': lambda data: 'error' not in data},
            error_message="Sensor returned error field",
            is_critical=True
        ))
        
        # Use SensorType enum values for consistency
        if self.sensor_type == SensorType.ENVIRONMENTAL.value:
            # Environmental sensors may have any of these metrics
            # All rules are non-critical since a sensor may not have all metrics
            self.add_temperature_rules(critical=False)
            self.add_humidity_rules(critical=False)
            self.add_light_rules(critical=False)
            self.add_co2_rules(critical=False)
            self.add_pressure_rules(critical=False)
        
        elif self.sensor_type == SensorType.PLANT.value:
            # Plant sensors may have any of these metrics
            self.add_soil_moisture_rules(critical=False)
            self.add_ph_rules(critical=False)
            self.add_ec_rules(critical=False)
            # Some plant sensors also measure temperature/humidity
            self.add_temperature_rules(critical=False)
            self.add_humidity_rules(critical=False)
        
        # Legacy type mappings for backward compatibility
        elif self.sensor_type in ('environment_sensor', 'temp_humidity_sensor'):
            self.add_temperature_rules()
            self.add_humidity_rules()
        
        elif self.sensor_type == 'soil_moisture_sensor':
            self.add_soil_moisture_rules()
    
    def add_temperature_rules(self, critical: bool = True):
        """Add temperature validation rules"""
        self.add_rule(ValidationRule(
            name="temperature_range",
            validation_type=ValidationType.RANGE_CHECK,
            params={'field': 'temperature', 'min': -40.0, 'max': 85.0},
            error_message="Temperature out of valid range (-40°C to 85°C)",
            is_critical=critical
        ))
        
        self.add_rule(ValidationRule(
            name="temperature_type",
            validation_type=ValidationType.TYPE_CHECK,
            params={'field': 'temperature', 'expected_type': (int, float)},
            error_message="Temperature must be numeric",
            is_critical=critical
        ))
    
    def add_humidity_rules(self, critical: bool = True):
        """Add humidity validation rules"""
        self.add_rule(ValidationRule(
            name="humidity_range",
            validation_type=ValidationType.RANGE_CHECK,
            params={'field': 'humidity', 'min': 0.0, 'max': 100.0},
            error_message="Humidity out of valid range (0% to 100%)",
            is_critical=critical
        ))
        
        self.add_rule(ValidationRule(
            name="humidity_type",
            validation_type=ValidationType.TYPE_CHECK,
            params={'field': 'humidity', 'expected_type': (int, float)},
            error_message="Humidity must be numeric",
            is_critical=critical
        ))
    
    def add_soil_moisture_rules(self, critical: bool = True):
        """Add soil moisture validation rules"""
        self.add_rule(ValidationRule(
            name="soil_moisture_range",
            validation_type=ValidationType.RANGE_CHECK,
            params={'field': 'soil_moisture', 'min': 0.0, 'max': 100.0},
            error_message="Soil moisture out of valid range (0% to 100%)",
            is_critical=critical
        ))
        
        self.add_rule(ValidationRule(
            name="soil_moisture_type",
            validation_type=ValidationType.TYPE_CHECK,
            params={'field': 'soil_moisture', 'expected_type': (int, float)},
            error_message="Soil moisture must be numeric",
            is_critical=critical
        ))
    
    def add_light_rules(self, critical: bool = True):
        """Add light/lux validation rules"""
        self.add_rule(ValidationRule(
            name="lux_range",
            validation_type=ValidationType.RANGE_CHECK,
            params={'field': 'lux', 'min': 0.0, 'max': 200000.0},
            error_message="Lux value out of valid range (0 to 200000)",
            is_critical=critical
        ))

    def add_co2_rules(self, critical: bool = True):
        """Add CO2 validation rules"""
        self.add_rule(ValidationRule(
            name="co2_range",
            validation_type=ValidationType.RANGE_CHECK,
            params={'field': 'co2', 'min': 0.0, 'max': 10000.0},
            error_message="CO2 value out of valid range (0 to 10000 ppm)",
            is_critical=critical
        ))
        
        self.add_rule(ValidationRule(
            name="co2_type",
            validation_type=ValidationType.TYPE_CHECK,
            params={'field': 'co2', 'expected_type': (int, float)},
            error_message="CO2 must be numeric",
            is_critical=critical
        ))

    def add_pressure_rules(self, critical: bool = True):
        """Add pressure validation rules"""
        self.add_rule(ValidationRule(
            name="pressure_range",
            validation_type=ValidationType.RANGE_CHECK,
            params={'field': 'pressure', 'min': 300.0, 'max': 1100.0},
            error_message="Pressure out of valid range (300 to 1100 hPa)",
            is_critical=critical
        ))
        
        self.add_rule(ValidationRule(
            name="pressure_type",
            validation_type=ValidationType.TYPE_CHECK,
            params={'field': 'pressure', 'expected_type': (int, float)},
            error_message="Pressure must be numeric",
            is_critical=critical
        ))

    def add_ph_rules(self, critical: bool = True):
        """Add pH validation rules"""
        self.add_rule(ValidationRule(
            name="ph_range",
            validation_type=ValidationType.RANGE_CHECK,
            params={'field': 'ph', 'min': 0.0, 'max': 14.0},
            error_message="pH value out of valid range (0 to 14)",
            is_critical=critical
        ))
        
        self.add_rule(ValidationRule(
            name="ph_type",
            validation_type=ValidationType.TYPE_CHECK,
            params={'field': 'ph', 'expected_type': (int, float)},
            error_message="pH must be numeric",
            is_critical=critical
        ))

    def add_ec_rules(self, critical: bool = True):
        """Add EC (electrical conductivity) validation rules"""
        self.add_rule(ValidationRule(
            name="ec_range",
            validation_type=ValidationType.RANGE_CHECK,
            params={'field': 'ec', 'min': 0.0, 'max': 20.0},
            error_message="EC value out of valid range (0 to 20 mS/cm)",
            is_critical=critical
        ))
        
        self.add_rule(ValidationRule(
            name="ec_type",
            validation_type=ValidationType.TYPE_CHECK,
            params={'field': 'ec', 'expected_type': (int, float)},
            error_message="EC must be numeric",
            is_critical=critical
        ))
    
    def add_rule(self, rule: ValidationRule):
        """Add a validation rule to the chain"""
        self.rules.append(rule)
    
    def validate(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate raw sensor data.
        
        Args:
            raw_data: Raw data from adapter
            
        Returns:
            Validated data (same as input if valid)
            
        Raises:
            ProcessorError: If critical validation fails
        """
        errors = []
        warnings = []
        
        for rule in self.rules:
            try:
                result = self._apply_rule(rule, raw_data)
                if not result:
                    if rule.is_critical:
                        errors.append(rule.error_message)
                    else:
                        warnings.append(rule.error_message)
            except Exception as e:
                logger.error(f"Validation rule '{rule.name}' failed: {e}")
                if rule.is_critical:
                    errors.append(f"{rule.error_message}: {e}")
        
        # Log warnings
        for warning in warnings:
            logger.warning(f"Validation warning: {warning}")
        
        # Raise error if critical validations failed
        if errors:
            error_msg = f"Validation failed: {'; '.join(errors)}"
            logger.error(error_msg)
            raise ProcessorError(error_msg)
        
        return raw_data
    
    def _apply_rule(self, rule: ValidationRule, data: Dict[str, Any]) -> bool:
        """
        Apply a single validation rule.
        
        Args:
            rule: Validation rule
            data: Data to validate
            
        Returns:
            True if validation passes
        """
        if rule.validation_type == ValidationType.REQUIRED_FIELDS:
            required = rule.params.get('fields', [])
            return all(field in data for field in required)
        
        elif rule.validation_type == ValidationType.TYPE_CHECK:
            field = rule.params['field']
            expected_type = rule.params['expected_type']
            
            # Skip if field not present (not required by this rule)
            if field not in data:
                return True
            
            return isinstance(data[field], expected_type)
        
        elif rule.validation_type == ValidationType.RANGE_CHECK:
            field = rule.params['field']
            min_val = rule.params.get('min')
            max_val = rule.params.get('max')
            
            # Skip if field not present
            if field not in data:
                return True
            
            value = data[field]
            
            # Check if numeric
            if not isinstance(value, (int, float)):
                return False
            
            if min_val is not None and value < min_val:
                return False
            if max_val is not None and value > max_val:
                return False
            
            return True
        
        elif rule.validation_type == ValidationType.CUSTOM:
            func = rule.params.get('function')
            if not callable(func):
                raise ValueError(f"Custom validation '{rule.name}' requires callable function")
            return func(data)
        
        else:
            logger.warning(f"Unknown validation type: {rule.validation_type}")
            return True
    
    def transform(self, validated_data: Dict[str, Any], sensor) -> Any:
        """
        Transform validated data to SensorReading.
        (Implemented in TransformationProcessor, this is a pass-through)
        """
        return validated_data
