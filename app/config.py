"""
Configuration for SYSGrow  and AI/ML Services
==================================================
Main application runtime settings and service configurations.
This configuration enables all AI services with sensible defaults.
Adjust values based on your Raspberry Pi performance.
Setups the logging configuration as well.
"""

import os
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "t", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Environment variable {name} must be an integer.") from None


def _env_int_multi(names: tuple[str, ...], default: int) -> int:
    for name in names:
        value = os.getenv(name)
        if value is None:
            continue
        try:
            return int(value)
        except ValueError:
            raise ValueError(f"Environment variable {name} must be an integer.") from None
    return default


@dataclass
class AppConfig:
    """Runtime configuration loaded from environment variables."""

    environment: str = field(default_factory=lambda: os.getenv("SYSGROW_ENV", "development"))
    devhost_enabled: bool = field(default_factory=lambda: _env_bool("SYSGROW_DEVHOST_ENABLED", True))
    secret_key: str = field(default_factory=lambda: os.getenv("SYSGROW_SECRET_KEY", "SYSGrowDevSecretKey"))
    database_path: str = field(default_factory=lambda: os.getenv("SYSGROW_DATABASE_PATH", "database/sysgrow.db"))

    # SQLite memory tuning — defaults are Pi-friendly (8 MB cache, 32 MB mmap).
    # Desktop / CI can override via env vars for better performance.
    db_cache_size_kb: int = field(default_factory=lambda: _env_int("SYSGROW_DB_CACHE_SIZE_KB", 8_000))
    db_mmap_size_bytes: int = field(default_factory=lambda: _env_int("SYSGROW_DB_MMAP_SIZE_BYTES", 33_554_432))

    enable_mqtt: bool = field(default_factory=lambda: _env_bool("SYSGROW_ENABLE_MQTT", True))
    mqtt_broker_host: str = field(default_factory=lambda: os.getenv("SYSGROW_MQTT_HOST", "localhost"))
    mqtt_broker_port: int = field(default_factory=lambda: _env_int("SYSGROW_MQTT_PORT", 1883))
    socketio_cors_origins: str = field(default_factory=lambda: os.getenv("SYSGROW_SOCKETIO_CORS", "*"))

    cache_enabled: bool = field(default_factory=lambda: _env_bool("SYSGROW_CACHE_ENABLED", True))
    cache_ttl_seconds: int = field(default_factory=lambda: _env_int("SYSGROW_CACHE_TTL", 30))
    cache_maxsize: int = field(default_factory=lambda: _env_int("SYSGROW_CACHE_MAXSIZE", 128))
    actuator_state_retention_days: int = field(
        default_factory=lambda: _env_int("SYSGROW_ACTUATOR_STATE_RETENTION_DAYS", 90)
    )
    sensor_retention_days: int = field(default_factory=lambda: _env_int("SYSGROW_SENSOR_RETENTION_DAYS", 30))
    models_path: str = field(default_factory=lambda: os.getenv("SYSGROW_MODELS_PATH", "models"))

    # Session Configuration
    session_lifetime_default_minutes: int = field(
        default_factory=lambda: _env_int("SYSGROW_SESSION_LIFETIME_DEFAULT", 60)
    )
    session_lifetime_remember_days: int = field(
        default_factory=lambda: _env_int("SYSGROW_SESSION_LIFETIME_REMEMBER", 30)
    )

    # API Health Monitoring
    api_health_window_size: int = field(default_factory=lambda: _env_int("SYSGROW_API_HEALTH_WINDOW_SIZE", 100))
    api_health_min_samples: int = field(default_factory=lambda: _env_int("SYSGROW_API_HEALTH_MIN_SAMPLES", 10))
    api_health_error_rate_degraded: float = field(
        default_factory=lambda: float(os.getenv("SYSGROW_API_HEALTH_ERROR_RATE_DEGRADED", "0.10"))
    )
    api_health_error_rate_offline: float = field(
        default_factory=lambda: float(os.getenv("SYSGROW_API_HEALTH_ERROR_RATE_OFFLINE", "0.50"))
    )
    api_health_avg_response_time_ms: int = field(
        default_factory=lambda: _env_int("SYSGROW_API_HEALTH_AVG_RESPONSE_TIME_MS", 2000)
    )
    api_health_slow_request_ms: int = field(
        default_factory=lambda: _env_int("SYSGROW_API_HEALTH_SLOW_REQUEST_MS", 1000)
    )

    eventbus_queue_size: int = field(default_factory=lambda: _env_int("SYSGROW_EVENTBUS_QUEUE_SIZE", 1024))
    eventbus_worker_count: int = field(default_factory=lambda: _env_int("SYSGROW_EVENTBUS_WORKER_COUNT", 2))

    DEBUG: bool = field(default_factory=lambda: _env_bool("SYSGROW_DEBUG", False))
    audit_log_path: str = field(default_factory=lambda: os.getenv("SYSGROW_AUDIT_LOG_PATH", "logs/audit.log"))
    log_level: str = field(default_factory=lambda: os.getenv("SYSGROW_LOG_LEVEL", "INFO"))

    # Rate Limiting
    rate_limit_enabled: bool = field(
        default_factory=lambda: _env_bool(
            "SYSGROW_RATE_LIMIT_ENABLED",
            os.getenv("SYSGROW_ENV", "development") != "development",
        )
    )
    rate_limit_default_limit: int = field(
        default_factory=lambda: _env_int_multi(
            ("SYSGROW_RATE_LIMIT_DEFAULT_LIMIT", "SYSGROW_RATE_LIMIT_DEFAULT"),
            60,
        )
    )
    rate_limit_default_window_seconds: int = field(
        default_factory=lambda: _env_int_multi(
            ("SYSGROW_RATE_LIMIT_DEFAULT_WINDOW_SECONDS", "SYSGROW_RATE_LIMIT_WINDOW"),
            60,
        )
    )
    rate_limit_burst: int = field(default_factory=lambda: _env_int("SYSGROW_RATE_LIMIT_BURST", 10))

    # Upload / request size limits
    max_upload_mb: int = field(default_factory=lambda: _env_int("SYSGROW_MAX_UPLOAD_MB", 16))

    # Login brute-force protection
    login_max_attempts: int = field(default_factory=lambda: _env_int("SYSGROW_LOGIN_MAX_ATTEMPTS", 5))
    login_lockout_minutes: int = field(default_factory=lambda: _env_int("SYSGROW_LOGIN_LOCKOUT_MINUTES", 15))

    # AI Feature Flags
    enable_continuous_monitoring: bool = field(
        default_factory=lambda: os.getenv("ENABLE_CONTINUOUS_MONITORING", "True").lower() == "true"
    )
    enable_personalized_learning: bool = field(
        default_factory=lambda: os.getenv("ENABLE_PERSONALIZED_LEARNING", "True").lower() == "true"
    )
    enable_training_data_collection: bool = field(
        default_factory=lambda: os.getenv("ENABLE_TRAINING_DATA_COLLECTION", "True").lower() == "true"
    )
    enable_automated_retraining: bool = field(
        default_factory=lambda: os.getenv("ENABLE_AUTOMATED_RETRAINING", "True").lower() == "true"
    )

    # AI Service Configuration
    continuous_monitoring_interval: int = field(
        default_factory=lambda: int(os.getenv("CONTINUOUS_MONITORING_INTERVAL", "300"))
    )
    personalized_profiles_path: str = field(
        default_factory=lambda: os.getenv("PERSONALIZED_PROFILES_PATH", "data/user_profiles")
    )
    training_data_path: str = field(default_factory=lambda: os.getenv("TRAINING_DATA_PATH", "data/training"))
    models_path: str = field(default_factory=lambda: os.getenv("MODELS_PATH", "models"))

    # Retraining Configuration
    retraining_drift_threshold: float = field(
        default_factory=lambda: float(os.getenv("RETRAINING_DRIFT_THRESHOLD", "0.15"))
    )
    retraining_check_interval: int = field(default_factory=lambda: int(os.getenv("RETRAINING_CHECK_INTERVAL", "3600")))

    # Model Configuration
    model_min_training_samples: int = field(default_factory=lambda: int(os.getenv("MODEL_MIN_TRAINING_SAMPLES", "100")))
    model_cache_predictions: bool = field(
        default_factory=lambda: os.getenv("MODEL_CACHE_PREDICTIONS", "True").lower() == "true"
    )

    # Performance Configuration
    max_concurrent_predictions: int = field(default_factory=lambda: int(os.getenv("MAX_CONCURRENT_PREDICTIONS", "3")))
    use_model_quantization: bool = field(
        default_factory=lambda: os.getenv("USE_MODEL_QUANTIZATION", "True").lower() == "true"
    )

    # Notification Configuration
    notify_critical_insights: bool = field(
        default_factory=lambda: os.getenv("NOTIFY_CRITICAL_INSIGHTS", "True").lower() == "true"
    )
    notification_cooldown_minutes: int = field(
        default_factory=lambda: int(os.getenv("NOTIFICATION_COOLDOWN_MINUTES", "60"))
    )

    # Logging Configuration
    ai_log_level: str = field(default_factory=lambda: os.getenv("AI_LOG_LEVEL", "INFO"))
    ai_log_predictions: bool = field(default_factory=lambda: _env_bool("AI_LOG_PREDICTIONS", True))
    ai_log_training_details: bool = field(default_factory=lambda: _env_bool("AI_LOG_TRAINING_DETAILS", True))
    ai_metrics_export_interval: int = field(default_factory=lambda: _env_int("AI_METRICS_EXPORT_INTERVAL", 3600))

    # Additional Feature Flags
    enable_ab_testing: bool = field(default_factory=lambda: _env_bool("ENABLE_AB_TESTING", True))
    enable_drift_detection: bool = field(default_factory=lambda: _env_bool("ENABLE_DRIFT_DETECTION", True))
    enable_computer_vision: bool = field(default_factory=lambda: _env_bool("ENABLE_COMPUTER_VISION", False))

    # LLM Configuration
    # Provider: "none" (disabled), "openai", "anthropic", "local"
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "none"))
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))
    llm_local_model_path: str = field(
        default_factory=lambda: os.getenv(
            "LLM_LOCAL_MODEL_PATH",
            "LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct",
        )
    )
    llm_local_device: str = field(default_factory=lambda: os.getenv("LLM_LOCAL_DEVICE", "auto"))
    llm_local_quantize: bool = field(default_factory=lambda: _env_bool("LLM_LOCAL_QUANTIZE", False))
    llm_local_torch_dtype: str = field(default_factory=lambda: os.getenv("LLM_LOCAL_TORCH_DTYPE", "float16"))
    llm_max_tokens: int = field(default_factory=lambda: _env_int("LLM_MAX_TOKENS", 512))
    llm_temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.3")))
    llm_timeout: int = field(default_factory=lambda: _env_int("LLM_TIMEOUT", 30))

    # Monitoring Configuration
    monitoring_max_insights_per_unit: int = field(
        default_factory=lambda: _env_int("MONITORING_MAX_INSIGHTS_PER_UNIT", 50)
    )
    monitoring_alert_threshold: str = field(default_factory=lambda: os.getenv("MONITORING_ALERT_THRESHOLD", "warning"))

    # Training Data Configuration
    training_data_min_quality_score: float = field(
        default_factory=lambda: float(os.getenv("TRAINING_DATA_MIN_QUALITY_SCORE", "0.6"))
    )
    training_data_min_sensor_readings: int = field(
        default_factory=lambda: _env_int("TRAINING_DATA_MIN_SENSOR_READINGS", 24)
    )
    training_data_retention_days: int = field(default_factory=lambda: _env_int("TRAINING_DATA_RETENTION_DAYS", 365))

    # Model Configuration (Extended)
    model_validation_split: float = field(default_factory=lambda: float(os.getenv("MODEL_VALIDATION_SPLIT", "0.2")))
    model_cross_validation_folds: int = field(default_factory=lambda: _env_int("MODEL_CROSS_VALIDATION_FOLDS", 5))
    model_cache_ttl: int = field(default_factory=lambda: _env_int("MODEL_CACHE_TTL", 300))

    # Retraining Configuration (Extended)
    retraining_performance_threshold: float = field(
        default_factory=lambda: float(os.getenv("RETRAINING_PERFORMANCE_THRESHOLD", "0.80"))
    )
    retraining_max_concurrent_jobs: int = field(default_factory=lambda: _env_int("RETRAINING_MAX_CONCURRENT_JOBS", 1))
    retraining_schedule_climate: str = field(default_factory=lambda: os.getenv("RETRAINING_SCHEDULE_CLIMATE", "weekly"))
    retraining_schedule_disease: str = field(
        default_factory=lambda: os.getenv("RETRAINING_SCHEDULE_DISEASE", "on_drift")
    )
    retraining_schedule_growth: str = field(default_factory=lambda: os.getenv("RETRAINING_SCHEDULE_GROWTH", "monthly"))

    # Drift Detection Configuration
    drift_detection_window_size: int = field(default_factory=lambda: _env_int("DRIFT_DETECTION_WINDOW_SIZE", 100))
    drift_detection_accuracy_threshold: float = field(
        default_factory=lambda: float(os.getenv("DRIFT_DETECTION_ACCURACY_THRESHOLD", "0.10"))
    )
    drift_detection_confidence_threshold: float = field(
        default_factory=lambda: float(os.getenv("DRIFT_DETECTION_CONFIDENCE_THRESHOLD", "0.60"))
    )
    drift_detection_error_rate_threshold: float = field(
        default_factory=lambda: float(os.getenv("DRIFT_DETECTION_ERROR_RATE_THRESHOLD", "0.20"))
    )

    # Performance Settings
    prediction_timeout_seconds: int = field(default_factory=lambda: _env_int("PREDICTION_TIMEOUT_SECONDS", 30))
    enable_gpu_acceleration: bool = field(default_factory=lambda: _env_bool("ENABLE_GPU_ACCELERATION", False))

    # Notification Configuration (Extended)
    notify_disease_risk_threshold: str = field(
        default_factory=lambda: os.getenv("NOTIFY_DISEASE_RISK_THRESHOLD", "high")
    )
    notify_climate_issues: bool = field(default_factory=lambda: _env_bool("NOTIFY_CLIMATE_ISSUES", True))
    notify_growth_stage_transitions: bool = field(
        default_factory=lambda: _env_bool("NOTIFY_GROWTH_STAGE_TRANSITIONS", True)
    )

    # Computer Vision Configuration (Optional)
    cv_model_type: str = field(default_factory=lambda: os.getenv("CV_MODEL_TYPE", "mobilenet_v2"))
    cv_inference_device: str = field(default_factory=lambda: os.getenv("CV_INFERENCE_DEVICE", "cpu"))
    cv_confidence_threshold: float = field(default_factory=lambda: float(os.getenv("CV_CONFIDENCE_THRESHOLD", "0.7")))
    cv_capture_interval: int = field(default_factory=lambda: _env_int("CV_CAPTURE_INTERVAL", 21600))

    # Personalization Configuration
    personalized_min_grows_for_profile: int = field(
        default_factory=lambda: _env_int("PERSONALIZED_MIN_GROWS_FOR_PROFILE", 3)
    )
    personalized_similarity_threshold: float = field(
        default_factory=lambda: float(os.getenv("PERSONALIZED_SIMILARITY_THRESHOLD", "0.6"))
    )

    # A/B Testing Configuration
    ab_testing_default_split_ratio: float = field(
        default_factory=lambda: float(os.getenv("AB_TESTING_DEFAULT_SPLIT_RATIO", "0.5"))
    )
    ab_testing_min_samples: int = field(default_factory=lambda: _env_int("AB_TESTING_MIN_SAMPLES", 100))
    ab_testing_significance_threshold: float = field(
        default_factory=lambda: float(os.getenv("AB_TESTING_SIGNIFICANCE_THRESHOLD", "0.05"))
    )
    ab_testing_auto_promote_winner: bool = field(
        default_factory=lambda: _env_bool("AB_TESTING_AUTO_PROMOTE_WINNER", False)
    )

    # Default insecure secret key - used only for detection
    _DEFAULT_SECRET_KEY: str = field(default="SYSGrowDevSecretKey", init=False, repr=False)

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # SECURITY: Fail fast if using default secret key in production
        if self.environment == "production":
            if self.secret_key == self._DEFAULT_SECRET_KEY:
                raise RuntimeError(
                    "SECURITY ERROR: Cannot use default secret key in production!\n"
                    "Set SYSGROW_SECRET_KEY environment variable to a secure random value.\n"
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )

            # SECURITY: Fail fast if using default AES key for WiFi credential encryption
            try:
                from app.hardware.actuators.utils.encryption import is_using_default_key

                if is_using_default_key():
                    raise RuntimeError(
                        "SECURITY ERROR: Cannot use default AES encryption key in production!\n"
                        "Set SYSGROW_AES_KEY environment variable to a secure random value.\n"
                        'Generate one with: python -c "import secrets; print(secrets.token_hex(16))"\n'
                        "Note: The same key must be configured in ESP32 firmware."
                    )
            except ImportError:
                # Encryption module not available (pycryptodome not installed)
                pass

    def as_flask_config(self) -> dict[str, Any]:
        """Render configuration values for Flask application."""
        secret = self.secret_key or os.getenv("FLASK_SECRET_KEY", "SYSGrowDevSecretKey")
        if not secret:
            raise RuntimeError(
                "Missing SYSGROW_SECRET_KEY or FLASK_SECRET_KEY environment variable. "
                "Production systems must set an explicit secret key."
            )

        return {
            "ENV": self.environment,
            "SECRET_KEY": secret,
            "DATABASE_PATH": self.database_path,
            "MQTT_BROKER_HOST": self.mqtt_broker_host,
            "MQTT_BROKER_PORT": self.mqtt_broker_port,
            "SOCKETIO_CORS_ALLOWED_ORIGINS": self.socketio_cors_origins,
            "AUDIT_LOG_PATH": self.audit_log_path,
            "DEBUG": self.DEBUG,
            "ACTUATOR_STATE_RETENTION_DAYS": self.actuator_state_retention_days,
        }


@dataclass
class AIConfiguration:
    """AI/ML service configuration settings"""

    # ==================== FEATURE TOGGLES ====================
    # Enable/disable AI services individually

    enable_continuous_monitoring: bool = True
    """Enable continuous background monitoring every N seconds"""

    enable_personalized_learning: bool = True
    """Enable user-specific model personalization"""

    enable_training_data_collection: bool = True
    """Enable automated training data collection"""

    enable_automated_retraining: bool = True
    """Enable scheduled model retraining"""

    enable_ab_testing: bool = True
    """Enable A/B testing for model versions"""

    enable_drift_detection: bool = True
    """Enable model performance drift monitoring"""

    enable_computer_vision: bool = False
    """Enable camera-based disease detection (requires camera + TensorFlow)"""

    enable_community_learning: bool = False
    """Enable opt-in anonymous data sharing for community learning"""

    # ==================== MONITORING SETTINGS ====================

    continuous_monitoring_interval: int = 300
    """Seconds between monitoring checks (300 = 5 minutes)
    Raspberry Pi recommendation: 300-600 (5-10 minutes)
    Development/Testing: 60-120 (1-2 minutes)
    Production with many units: 600-900 (10-15 minutes)
    """

    monitoring_max_insights_per_unit: int = 50
    """Maximum insights to store per unit in memory"""

    monitoring_alert_threshold: str = "warning"
    """Minimum alert level to trigger notifications: info, warning, critical"""

    # ==================== PERSONALIZATION SETTINGS ====================

    personalized_profiles_path: str = "data/user_profiles"
    """Directory for storing user environment profiles"""

    personalized_min_grows_for_profile: int = 3
    """Minimum completed grows before creating personalized recommendations"""

    personalized_similarity_threshold: float = 0.6
    """Minimum similarity score (0-1) for matching similar growers"""

    # ==================== TRAINING DATA SETTINGS ====================

    training_data_path: str = "data/training"
    """Directory for storing prepared training datasets"""

    training_data_min_quality_score: float = 0.6
    """Minimum data quality score (0-1) to include in training"""

    training_data_min_sensor_readings: int = 24
    """Minimum sensor readings (hours) before using data"""

    training_data_collection_schedule: str = "0 2 * * *"
    """Cron schedule for data collection (default: 2 AM daily)"""

    training_data_retention_days: int = 365
    """Days to retain training data (older data is archived)"""

    # ==================== MODEL SETTINGS ====================

    models_path: str = "models"
    """Directory for storing trained ML models"""

    model_min_training_samples: int = 100
    """Minimum samples required to train a model"""

    model_validation_split: float = 0.2
    """Fraction of data to use for validation (0.2 = 20%)"""

    model_cross_validation_folds: int = 5
    """Number of folds for cross-validation"""

    model_cache_predictions: bool = True
    """Cache model predictions to reduce inference time"""

    model_cache_ttl: int = 300
    """Seconds to cache predictions (300 = 5 minutes)"""

    # ==================== RETRAINING SETTINGS ====================

    retraining_check_interval: int = 3600
    """Seconds between retraining checks (3600 = 1 hour)"""

    retraining_drift_threshold: float = 0.15
    """Drift score threshold to trigger retraining (0.15 = 15% drift)"""

    retraining_performance_threshold: float = 0.80
    """Minimum performance score (0.80 = 80% accuracy)"""

    retraining_schedule_climate: str = "weekly"
    """Climate model retraining: daily, weekly, monthly, on_drift"""

    retraining_schedule_disease: str = "on_drift"
    """Disease model retraining: daily, weekly, monthly, on_drift"""

    retraining_schedule_growth: str = "monthly"
    """Growth model retraining: daily, weekly, monthly, on_drift"""

    retraining_max_concurrent_jobs: int = 1
    """Maximum concurrent retraining jobs (Raspberry Pi: keep at 1)"""

    # ==================== DRIFT DETECTION SETTINGS ====================

    drift_detection_window_size: int = 100
    """Number of recent predictions to analyze for drift"""

    drift_detection_accuracy_threshold: float = 0.10
    """Alert if accuracy drops by this amount (0.10 = 10%)"""

    drift_detection_confidence_threshold: float = 0.60
    """Alert if average confidence falls below this (0.60 = 60%)"""

    drift_detection_error_rate_threshold: float = 0.20
    """Alert if error rate exceeds this (0.20 = 20%)"""

    # ==================== A/B TESTING SETTINGS ====================

    ab_testing_default_split_ratio: float = 0.5
    """Default traffic split for A/B tests (0.5 = 50/50)"""

    ab_testing_min_samples: int = 100
    """Minimum samples per variant before analysis"""

    ab_testing_significance_threshold: float = 0.05
    """Statistical significance threshold (p-value)"""

    ab_testing_auto_promote_winner: bool = False
    """Automatically promote winning model to production"""

    # ==================== COMPUTER VISION SETTINGS ====================

    cv_model_type: str = "mobilenet_v2"
    """Computer vision model: mobilenet_v2, efficientnet_b0, resnet50"""

    cv_inference_device: str = "cpu"
    """Inference device: cpu, gpu, tpu (Raspberry Pi: use cpu)"""

    cv_image_size: tuple[int, int] = (224, 224)
    """Input image size for model (width, height)"""

    cv_confidence_threshold: float = 0.7
    """Minimum confidence for disease detection (0.7 = 70%)"""

    cv_capture_interval: int = 21600
    """Seconds between automated captures (21600 = 6 hours)"""

    # ==================== PERFORMANCE SETTINGS ====================

    max_concurrent_predictions: int = 3
    """Maximum concurrent model predictions (Raspberry Pi: 1-3)"""

    prediction_timeout_seconds: int = 30
    """Timeout for model predictions"""

    use_model_quantization: bool = True
    """Use quantized models for faster inference (Raspberry Pi: True)"""

    enable_gpu_acceleration: bool = False
    """Enable GPU acceleration if available (Raspberry Pi 5: can try True)"""

    # ==================== NOTIFICATION SETTINGS ====================

    notify_critical_insights: bool = True
    """Send notifications for critical insights"""

    notify_disease_risk_threshold: str = "high"
    """Disease risk level to trigger notification: moderate, high, critical"""

    notify_climate_issues: bool = True
    """Send notifications for climate control issues"""

    notify_growth_stage_transitions: bool = True
    """Send notifications when plant ready for next stage"""

    notification_cooldown_minutes: int = 60
    """Minimum minutes between same notification (avoid spam)"""

    # ==================== LOGGING SETTINGS ====================

    ai_log_level: str = "INFO"
    """Logging level for AI services: DEBUG, INFO, WARNING, ERROR"""

    ai_log_predictions: bool = True
    """Log all model predictions for debugging"""

    ai_log_training_details: bool = True
    """Log detailed training metrics"""

    ai_metrics_export_interval: int = 3600
    """Seconds between metrics export (for monitoring dashboards)"""


# ==================== RASPBERRY PI PROFILES ====================


class RaspberryPiProfiles:
    """Pre-configured profiles for different Raspberry Pi models"""

    @staticmethod
    def pi_3_config() -> dict:
        """Raspberry Pi 3 - Conservative settings"""
        return {
            "continuous_monitoring_interval": 600,  # 10 minutes
            "max_concurrent_predictions": 1,
            "use_model_quantization": True,
            "enable_gpu_acceleration": False,
            "model_cache_predictions": True,
            "retraining_check_interval": 7200,  # 2 hours
            "db_cache_size_kb": 4_000,  # 4 MB  — Pi 3 has 1 GB RAM
            "db_mmap_size_bytes": 16_777_216,  # 16 MB
        }

    @staticmethod
    def pi_4_config() -> dict:
        """Raspberry Pi 4 - Balanced settings"""
        return {
            "continuous_monitoring_interval": 300,  # 5 minutes
            "max_concurrent_predictions": 2,
            "use_model_quantization": True,
            "enable_gpu_acceleration": False,
            "model_cache_predictions": True,
            "retraining_check_interval": 3600,  # 1 hour
            "db_cache_size_kb": 16_000,  # 16 MB — Pi 4 has 2-8 GB RAM
            "db_mmap_size_bytes": 67_108_864,  # 64 MB
        }

    @staticmethod
    def pi_5_config() -> dict:
        """Raspberry Pi 5 - Performance settings"""
        return {
            "continuous_monitoring_interval": 180,  # 3 minutes
            "max_concurrent_predictions": 3,
            "use_model_quantization": False,  # Can handle full models
            "enable_gpu_acceleration": True,  # Try GPU acceleration
            "model_cache_predictions": True,
            "retraining_check_interval": 3600,  # 1 hour
            "db_cache_size_kb": 32_000,  # 32 MB — Pi 5 has 4-8 GB RAM
            "db_mmap_size_bytes": 134_217_728,  # 128 MB
        }

    @staticmethod
    def development_config() -> dict:
        """Development/Testing - Fast iteration"""
        return {
            "continuous_monitoring_interval": 60,  # 1 minute
            "max_concurrent_predictions": 5,
            "use_model_quantization": False,
            "enable_gpu_acceleration": True,
            "model_cache_predictions": False,  # Fresh predictions for testing
            "retraining_check_interval": 1800,  # 30 minutes
            "ai_log_level": "DEBUG",
            "db_cache_size_kb": 64_000,  # 64 MB — desktops have plenty of RAM
            "db_mmap_size_bytes": 268_435_456,  # 256 MB
        }


# ==================== CONFIGURATION VALIDATION ====================


def validate_ai_config(config: AppConfig) -> list[str]:
    """
    Validate AI configuration and return list of warnings.

    Args:
        config: AppConfig instance

    Returns:
        List of warning messages (empty if all valid)
    """
    warnings = []

    # Check monitoring interval
    if config.continuous_monitoring_interval < 60:
        warnings.append(
            f"Monitoring interval ({config.continuous_monitoring_interval}s) is very short. "
            "Recommended: 300-600s for Raspberry Pi"
        )

    # Check training samples
    if config.model_min_training_samples < 50:
        warnings.append(
            f"Minimum training samples ({config.model_min_training_samples}) is low. "
            "Models may not perform well. Recommended: 100+"
        )

    # Check concurrent predictions
    if config.max_concurrent_predictions > 3:
        warnings.append(
            f"Concurrent predictions ({config.max_concurrent_predictions}) may overload Raspberry Pi. Recommended: 1-3"
        )

    # Check drift threshold
    if config.retraining_drift_threshold < 0.05:
        warnings.append(
            f"Drift threshold ({config.retraining_drift_threshold}) is very sensitive. "
            "May trigger frequent retraining. Recommended: 0.10-0.20"
        )

    # Check directories exist
    for _path_name, path_value in [
        ("models_path", config.models_path),
        ("training_data_path", config.training_data_path),
        ("personalized_profiles_path", config.personalized_profiles_path),
    ]:
        path = Path(path_value)
        if not path.exists():
            warnings.append(f"Directory does not exist: {path_value}")

    return warnings


def setup_logging(debug: bool = False) -> None:
    """Setup logging configuration."""
    import logging
    import sys
    from logging.handlers import RotatingFileHandler

    log_level = logging.DEBUG if debug else logging.INFO

    # Root logger
    root = logging.getLogger()
    root.setLevel(log_level)

    # Keep existing handlers but avoid adding duplicates when create_app is called multiple times
    has_console = any(getattr(h, "name", "") == "sysgrow_console" for h in root.handlers)
    has_file = any(getattr(h, "name", "") == "sysgrow_file" for h in root.handlers)
    added_handler = False

    # Console handler (force UTF-8 to avoid UnicodeEncodeError on Windows terminals)
    stream = sys.stdout
    with suppress(AttributeError, ValueError):
        stream.reconfigure(encoding="utf-8", errors="replace")
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    if not has_console:
        console_handler = logging.StreamHandler(stream=stream)
        console_handler.name = "sysgrow_console"
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        root.addHandler(console_handler)
        added_handler = True

    # File handler
    if not has_file:
        os.makedirs("logs", exist_ok=True)
        file_handler = RotatingFileHandler(
            "logs/sysgrow.log",
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.name = "sysgrow_file"
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
        added_handler = True

    # Ensure handler levels follow the desired log level
    for handler in root.handlers:
        if getattr(handler, "name", "") in {"sysgrow_console", "sysgrow_file"}:
            handler.setLevel(log_level)

    if added_handler:
        root.info(f"Logging initialized at level: {logging.getLevelName(log_level)}")

    if _env_bool("SYSGROW_SILENCE_WERKZEUG", True):
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # Silence SocketIO/EngineIO polling logs to reduce I/O on Raspberry Pi
    # These generate excessive logs (every 10s) that contributed to 565MB log files
    if _env_bool("SYSGROW_SILENCE_SOCKETIO", True):
        logging.getLogger("socketio").setLevel(logging.WARNING)
        logging.getLogger("engineio").setLevel(logging.WARNING)


def load_config() -> AppConfig:
    """Helper for callers to load and validate configuration."""
    config = AppConfig()

    # Apply Raspberry Pi optimizations if running on Pi
    try:
        import logging

        from app.utils.raspberry_pi_optimizer import get_optimizer

        logger = logging.getLogger("config_loader")
        optimizer = get_optimizer()

        if optimizer._is_raspberry_pi():
            logger.info("Applying Raspberry Pi optimizations for %s", optimizer.profile.model)

            # Override config with optimized values if not explicitly set in env
            if not os.getenv("CONTINUOUS_MONITORING_INTERVAL"):
                config.continuous_monitoring_interval = optimizer.profile.recommended_monitoring_interval
            if not os.getenv("MAX_CONCURRENT_PREDICTIONS"):
                config.max_concurrent_predictions = optimizer.profile.recommended_max_predictions
            if not os.getenv("USE_MODEL_QUANTIZATION"):
                config.use_model_quantization = optimizer.profile.use_quantization

            # Disable resource-intensive features on low-end hardware
            if optimizer.profile.ram_mb < 2048:
                logger.warning("Low RAM detected - disabling some AI features")
                config.enable_automated_retraining = False
                config.enable_personalized_learning = False

            # Scale SQLite memory to available RAM (only if not set via env)
            if not os.getenv("SYSGROW_DB_CACHE_SIZE_KB"):
                ram = optimizer.profile.ram_mb
                if ram < 2048:  # Pi 3 — 1 GB
                    config.db_cache_size_kb = 4_000  # 4 MB
                elif ram < 4096:  # Pi 4 2 GB variant
                    config.db_cache_size_kb = 8_000  # 8 MB (default)
                else:  # Pi 4 4/8 GB, Pi 5
                    config.db_cache_size_kb = 32_000  # 32 MB

            if not os.getenv("SYSGROW_DB_MMAP_SIZE_BYTES"):
                ram = optimizer.profile.ram_mb
                if ram < 2048:
                    config.db_mmap_size_bytes = 16_777_216  # 16 MB
                elif ram < 4096:
                    config.db_mmap_size_bytes = 33_554_432  # 32 MB (default)
                else:
                    config.db_mmap_size_bytes = 134_217_728  # 128 MB
    except Exception as e:
        logger.warning("Could not apply Pi optimizations: %s", e)

    return config
