"""
Application Constants
=====================

Centralized constants to replace magic numbers throughout the codebase.
Organized by domain for easy discovery and maintenance.

Usage:
    from app.constants import SENSOR_POLLING_INTERVAL_SECONDS
    from app.constants import Thresholds, Timeouts, Pagination
"""

# =============================================================================
# Timing Constants (seconds unless otherwise noted)
# =============================================================================

class Timeouts:
    """Timeout values for various operations."""
    # Network/API
    HTTP_REQUEST_TIMEOUT = 30  # seconds
    MQTT_CONNECT_TIMEOUT = 10  # seconds
    MQTT_RECONNECT_DELAY = 5  # seconds
    MQTT_KEEPALIVE = 60  # seconds

    # Hardware
    SENSOR_READ_TIMEOUT = 5  # seconds
    ACTUATOR_COMMAND_TIMEOUT = 10  # seconds
    GPIO_DEBOUNCE_MS = 50  # milliseconds

    # Database
    DB_QUERY_TIMEOUT = 30  # seconds
    DB_CONNECTION_TIMEOUT = 10  # seconds


class Intervals:
    """Polling and scheduling intervals."""
    # Sensor polling
    SENSOR_POLLING_DEFAULT = 60  # seconds
    SENSOR_POLLING_MIN = 10  # seconds
    SENSOR_POLLING_MAX = 300  # seconds

    # Actuator checks
    SCHEDULE_CHECK_INTERVAL = 30  # seconds
    ACTUATOR_STATE_CHECK = 60  # seconds

    # Health monitoring
    HEALTH_CHECK_INTERVAL = 300  # seconds (5 minutes)
    DEVICE_HEALTH_CHECK = 600  # seconds (10 minutes)

    # ML/AI
    ML_INFERENCE_THROTTLE = 60  # seconds (max 1 per minute)
    ML_DRIFT_CHECK = 3600  # seconds (1 hour)

    # Continuous monitoring
    CONTINUOUS_MONITOR_INTERVAL = 300  # seconds (5 minutes)
    CONTINUOUS_MONITOR_MAX = 900  # seconds (15 minutes)


# =============================================================================
# Pagination Constants
# =============================================================================

class Pagination:
    """Pagination defaults and limits."""
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 500
    DEFAULT_OFFSET = 0

    # Specific endpoints
    SENSOR_READINGS_DEFAULT = 100
    SENSOR_READINGS_MAX = 1000
    ALERTS_DEFAULT = 50
    ALERTS_MAX = 200
    HARVEST_REPORTS_DEFAULT = 20
    HARVEST_REPORTS_MAX = 100


# =============================================================================
# Data Retention Constants (days)
# =============================================================================

class Retention:
    """Data retention periods in days."""
    SENSOR_READINGS_DEFAULT = 30
    SENSOR_READINGS_MIN = 7
    SENSOR_READINGS_MAX = 365

    ACTUATOR_STATE_HISTORY = 90
    ALERTS_DEFAULT = 30
    ML_TRAINING_DATA = 180
    AUDIT_LOGS = 90

    # Aggregation threshold (days before retention cutoff to aggregate)
    AGGREGATION_BUFFER = 5


# =============================================================================
# Environmental Thresholds
# =============================================================================

class EnvironmentThresholds:
    """Environmental monitoring thresholds."""
    # Temperature (Celsius)
    TEMP_MIN_SAFE = 10.0
    TEMP_MAX_SAFE = 40.0
    TEMP_CRITICAL_LOW = 5.0
    TEMP_CRITICAL_HIGH = 45.0

    # Humidity (%)
    HUMIDITY_MIN_SAFE = 30.0
    HUMIDITY_MAX_SAFE = 80.0
    HUMIDITY_CRITICAL_LOW = 20.0
    HUMIDITY_CRITICAL_HIGH = 90.0

    # Soil Moisture (%)
    SOIL_MOISTURE_MIN = 20.0
    SOIL_MOISTURE_MAX = 80.0
    SOIL_MOISTURE_CRITICAL_LOW = 10.0
    SOIL_MOISTURE_CRITICAL_HIGH = 90.0

    # CO2 (ppm)
    CO2_MIN = 400
    CO2_MAX = 1500
    CO2_CRITICAL_HIGH = 2000

    # Light (lux)
    LIGHT_LOW_THRESHOLD = 100
    LIGHT_HIGH_THRESHOLD = 50000


# Tolerance values for threshold updates (minimum change required to trigger update)
THRESHOLD_UPDATE_TOLERANCE: dict[str, float] = {
    "temperature_threshold": 0.5,      # 0.5°C minimum change
    "humidity_threshold": 1.0,         # 1% minimum change
    "soil_moisture_threshold": 2.0,    # 2% minimum change
    "co2_threshold": 50.0,             # 50 ppm minimum change
    "voc_threshold": 10.0,             # 10 ppb minimum change
    "lux_threshold": 100.0,            # 100 lux minimum change
    "air_quality_threshold": 5.0,              # 5 AQI points minimum change
}


# Default night-time adjustments applied when plants_info.json has no explicit
# night values.  Keys match EnvironmentalThresholds field names.
# Temperature drops during the dark period (plant respiration, DIF strategy).
# Humidity rises as transpiration slows.  Lux drops to 0 (lights off).
NIGHT_THRESHOLD_ADJUSTMENTS: dict[str, float] = {
    "temperature": -3.0,    # °C — drop 3°C at night
    "humidity":    +5.0,    # %  — humidity rises when transpiration slows
    "lux":         0.0,     # absolute value — lights off at night
}


class VPDThresholds:
    """Vapor Pressure Deficit thresholds by growth stage."""
    # Seedling/Clone (kPa)
    SEEDLING_MIN = 0.4
    SEEDLING_MAX = 0.8
    SEEDLING_TARGET = 0.6

    # Vegetative (kPa)
    VEGETATIVE_MIN = 0.8
    VEGETATIVE_MAX = 1.2
    VEGETATIVE_TARGET = 1.0

    # Flowering (kPa)
    FLOWERING_MIN = 1.0
    FLOWERING_MAX = 1.5
    FLOWERING_TARGET = 1.2

    # Late flowering (kPa)
    LATE_FLOWERING_MIN = 1.2
    LATE_FLOWERING_MAX = 1.6
    LATE_FLOWERING_TARGET = 1.4


# =============================================================================
# Control System Constants
# =============================================================================

class ControlConstants:
    """Control loop and PID constants."""
    # Cycle times (seconds)
    MIN_CYCLE_TIME = 60  # Minimum time between actuator state changes
    CONTROL_LOOP_INTERVAL = 30  # Control loop execution interval

    # Deadband (percentage around setpoint)
    TEMPERATURE_DEADBAND = 0.5
    HUMIDITY_DEADBAND = 2.0
    SOIL_MOISTURE_DEADBAND = 5.0

    # PID defaults
    DEFAULT_KP = 1.0
    DEFAULT_KI = 0.1
    DEFAULT_KD = 0.05

    # Output limits
    OUTPUT_MIN = 0.0
    OUTPUT_MAX = 100.0


# =============================================================================
# Alert System Constants
# =============================================================================

class AlertConstants:
    """Alert system configuration."""
    # Deduplication
    DEDUPE_WINDOW_MINUTES = 15
    MAX_ALERTS_PER_HOUR = 10

    # Severity thresholds
    CRITICAL_THRESHOLD = 0.9
    WARNING_THRESHOLD = 0.7
    INFO_THRESHOLD = 0.5


# =============================================================================
# Growing Medium Configuration
# =============================================================================

from dataclasses import dataclass


@dataclass(frozen=True)
class GrowingMediumProperties:
    """Properties of a growing medium affecting irrigation."""

    name: str
    retention_coefficient: float  # Water retention (1.0 = baseline soil)
    drainage_rate: float  # How fast water drains (ml/hour/liter)
    evaporation_multiplier: float  # Evaporation speed relative to soil
    recommended_moisture_min: float  # Minimum % for healthy growth
    recommended_moisture_max: float  # Maximum % for healthy growth


class GrowingMediumConfig:
    """Growing medium configurations for irrigation calculations."""

    SOIL = GrowingMediumProperties(
        name="soil",
        retention_coefficient=1.0,
        drainage_rate=5.0,
        evaporation_multiplier=1.0,
        recommended_moisture_min=40.0,
        recommended_moisture_max=70.0,
    )

    COCO_COIR = GrowingMediumProperties(
        name="coco",
        retention_coefficient=0.8,  # Drains faster, needs more frequent watering
        drainage_rate=10.0,
        evaporation_multiplier=1.2,
        recommended_moisture_min=50.0,
        recommended_moisture_max=80.0,
    )

    PERLITE = GrowingMediumProperties(
        name="perlite",
        retention_coefficient=0.6,  # Very fast drainage
        drainage_rate=20.0,
        evaporation_multiplier=1.5,
        recommended_moisture_min=30.0,
        recommended_moisture_max=60.0,
    )

    HYDRO = GrowingMediumProperties(
        name="hydro",
        retention_coefficient=0.4,  # Minimal retention
        drainage_rate=50.0,
        evaporation_multiplier=0.5,  # Less surface evaporation
        recommended_moisture_min=80.0,
        recommended_moisture_max=100.0,
    )

    CLAY_PEBBLES = GrowingMediumProperties(
        name="clay_pebbles",
        retention_coefficient=0.5,
        drainage_rate=30.0,
        evaporation_multiplier=0.8,
        recommended_moisture_min=60.0,
        recommended_moisture_max=90.0,
    )

    _REGISTRY: dict[str, GrowingMediumProperties] = {
        "soil": SOIL,
        "coco": COCO_COIR,
        "coco_coir": COCO_COIR,
        "perlite": PERLITE,
        "hydro": HYDRO,
        "hydroponics": HYDRO,
        "clay_pebbles": CLAY_PEBBLES,
        "leca": CLAY_PEBBLES,
    }

    @classmethod
    def get(cls, medium_name: str) -> GrowingMediumProperties:
        """Get medium properties by name, defaults to SOIL."""
        return cls._REGISTRY.get(medium_name.lower().strip(), cls.SOIL)

    @classmethod
    def list_all(cls) -> list[str]:
        """List all available growing medium names."""
        return list(cls._REGISTRY.keys())


# =============================================================================
# ML/AI Constants
# =============================================================================


class MLConstants:
    """Machine learning configuration."""

    # Training data requirements
    MIN_TRAINING_SAMPLES = 100
    OPTIMAL_TRAINING_SAMPLES = 500

    # Model confidence
    HIGH_CONFIDENCE_THRESHOLD = 0.85
    MEDIUM_CONFIDENCE_THRESHOLD = 0.70
    LOW_CONFIDENCE_THRESHOLD = 0.50

    # Drift detection
    DRIFT_THRESHOLD = 0.15
    DRIFT_CHECK_SAMPLES = 50

    # Prediction windows
    PREDICTION_HORIZON_HOURS = 72


# =============================================================================
# Database Constants
# =============================================================================

class DatabaseConstants:
    """Database configuration."""
    # Connection pool
    POOL_SIZE_DEFAULT = 5
    POOL_SIZE_MAX = 10
    MAX_OVERFLOW = 10

    # Query limits
    MAX_IN_CLAUSE_ITEMS = 500
    BATCH_INSERT_SIZE = 100


# =============================================================================
# Hardware Constants
# =============================================================================

class HardwareConstants:
    """Hardware-specific constants."""
    # ESP32
    ESP32_MAX_RETRIES = 3
    ESP32_RETRY_DELAY = 2  # seconds

    # Relay
    RELAY_MAX_ON_TIME = 3600  # seconds (1 hour safety limit)
    RELAY_COOLDOWN = 60  # seconds between activations

    # Sensor quality
    READING_QUALITY_THRESHOLD = 0.7
    MAX_CONSECUTIVE_FAILURES = 5


# =============================================================================
# File Size Constants
# =============================================================================

class FileSizeConstants:
    """File size limits."""
    # Logs
    LOG_MAX_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
    LOG_BACKUP_COUNT = 3

    # Uploads
    MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

    # Database warnings
    DB_SIZE_WARNING_MB = 500
    DB_SIZE_CRITICAL_MB = 1000


# =============================================================================
# Rate Limiting Constants
# =============================================================================

class RateLimitConstants:
    """API rate limiting."""
    DEFAULT_REQUESTS_PER_MINUTE = 60
    DEFAULT_WINDOW_SECONDS = 60

    # Per-endpoint overrides
    AUTH_REQUESTS_PER_MINUTE = 10
    ML_INFERENCE_PER_MINUTE = 5
    BULK_OPERATIONS_PER_MINUTE = 10


# =============================================================================
# Export commonly used constants at module level for convenience
# =============================================================================

# Timing
SENSOR_POLLING_INTERVAL_SECONDS = Intervals.SENSOR_POLLING_DEFAULT
SCHEDULE_CHECK_INTERVAL_SECONDS = Intervals.SCHEDULE_CHECK_INTERVAL
HEALTH_CHECK_INTERVAL_SECONDS = Intervals.HEALTH_CHECK_INTERVAL

# Pagination
DEFAULT_PAGE_SIZE = Pagination.DEFAULT_PAGE_SIZE
MAX_PAGE_SIZE = Pagination.MAX_PAGE_SIZE

# Retention
SENSOR_RETENTION_DAYS = Retention.SENSOR_READINGS_DEFAULT
ACTUATOR_STATE_RETENTION_DAYS = Retention.ACTUATOR_STATE_HISTORY
ALERT_RETENTION_DAYS = Retention.ALERTS_DEFAULT

# Control
MIN_CYCLE_TIME_SECONDS = ControlConstants.MIN_CYCLE_TIME
CONTROL_LOOP_INTERVAL_SECONDS = ControlConstants.CONTROL_LOOP_INTERVAL

# Alerting
ALERT_DEDUPE_WINDOW_MINUTES = AlertConstants.DEDUPE_WINDOW_MINUTES
MAX_ALERTS_PER_HOUR = AlertConstants.MAX_ALERTS_PER_HOUR

# Irrigation
IRRIGATION_THRESHOLDS = EnvironmentThresholds.SOIL_MOISTURE_MIN, EnvironmentThresholds.SOIL_MOISTURE_MAX
IRRIGATION_DURATIONS = {'soil_type': 30}  # seconds, example default per soil type
GROWTH_STAGE_MOISTURE_ADJUSTMENTS = {
    'germination': -10.0,
    'seedling': -5.0,
    'vegetative': 0.0,
    'flowering': 5.0,
    'fruiting': 7.5,
    'late_flowering': 10.0
}  # adjustments in percentage points
BAYESIAN_DEFAULTS = {
    'min_variance': 10.0,
    'prior_mean': 50.0,
    'prior_variance': 100.0,
    'observation_variance': 25.0
}

# Growth Stage Volume Multipliers (for irrigation calculations)
GROWTH_STAGE_VOLUME_MULTIPLIERS = {
    'germination': 0.5,
    'seedling': 0.7,
    'vegetative': 1.0,
    'flowering': 1.2,
    'fruiting': 1.3,
    'harvest': 0.8,
}

# Reference pot size for scaling calculations
REFERENCE_POT_SIZE_LITERS = 5.0

# Pump calibration defaults
PUMP_CALIBRATION_DEFAULTS = {
    'default_flow_rate_ml_per_second': 3.33,  # ~200ml/min
    'calibration_duration_seconds': 30,
    'min_duration_seconds': 5,
    'max_duration_seconds': 600,
}
