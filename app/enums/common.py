"""
Common Enumerations
====================

This module contains common enums used across multiple services.
These are application-wide enums that don't fit in device, events, or growth categories.
"""

from enum import Enum


class RiskLevel(str, Enum):
    """
    Risk/severity levels for assessments.
    Used by: disease_predictor, plant_health_monitor
    """
    MINIMAL = "minimal"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

    def __str__(self) -> str:
        return self.value


class HealthLevel(str, Enum):
    """
    System/component health levels.
    Used by: system_health_service, health API, domain health tracking
    """
    HEALTHY = "healthy"
    WARNING = "warning"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


class Priority(str, Enum):
    """
    Priority levels for recommendations and actions.
    Used by: ML predictions, task scheduling, notifications
    """
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

    def __str__(self) -> str:
        return self.value


class DriftRecommendation(str, Enum):
    """
    Model drift action recommendations.
    Used by: drift_detector
    """
    OK = "ok"
    MONITOR = "monitor"
    RETRAIN = "retrain"
    URGENT = "urgent"

    def __str__(self) -> str:
        return self.value


class TrainingDataType(str, Enum):
    """
    ML training data categories.
    Used by: training_data_collector
    """
    DISEASE = "disease"
    CLIMATE = "climate"
    IRRIGATION = "irrigation"
    GROWTH = "growth"

    def __str__(self) -> str:
        return self.value


class AnomalyType(str, Enum):
    """
    Sensor anomaly classifications.
    Used by: anomaly_detection_service
    """
    SPIKE = "spike"
    DROP = "drop"
    STUCK = "stuck"
    OUT_OF_RANGE = "out_of_range"
    RATE_OF_CHANGE = "rate_of_change"
    STATISTICAL = "statistical"

    def __str__(self) -> str:
        return self.value


class AnomalySeverity(str, Enum):
    """
    Anomaly severity levels for energy/sensor anomalies.
    Used by: energy analytics, anomaly detection
    """
    INFO = "info"
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"

    def __str__(self) -> str:
        return self.value


class RequestStatus(str, Enum):
    """
    Workflow request states.
    Used by: irrigation_workflow_service
    """
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    def __str__(self) -> str:
        return self.value


class MQTTSource(str, Enum):
    """
    MQTT message source types.
    Used by: mqtt_sensor_service
    """
    ESP32 = "esp32"
    ZIGBEE = "zigbee2mqtt"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


class DiseaseType(str, Enum):
    """
    Disease type classification.
    Used by: disease_predictor, plant_health_monitor
    """
    FUNGAL = "fungal"
    BACTERIAL = "bacterial"
    VIRAL = "viral"
    PEST = "pest"
    NUTRIENT_DEFICIENCY = "nutrient_deficiency"
    ENVIRONMENTAL_STRESS = "environmental_stress"

    def __str__(self) -> str:
        return self.value


class PlantHealthStatus(str, Enum):
    """
    Plant health status classification.
    Used by: plant_health_monitor
    """
    HEALTHY = "healthy"
    STRESSED = "stressed"
    DISEASED = "diseased"
    PEST_INFESTATION = "pest_infestation"
    NUTRIENT_DEFICIENCY = "nutrient_deficiency"
    DYING = "dying"

    def __str__(self) -> str:
        return self.value


class ControlStrategy(str, Enum):
    """
    Control loop strategy types.
    Used by: control_logic
    """
    HEATING = "heating"
    COOLING = "cooling"
    HUMIDIFYING = "humidifying"
    DEHUMIDIFYING = "dehumidifying"
    WATERING = "watering"
    CO2_ENRICHMENT = "co2_enrichment"
    LIGHT_CONTROL = "light_control"

    def __str__(self) -> str:
        return self.value


class SensorState(str, Enum):
    """
    Sensor health states.
    Used by: sensor_polling_service
    """
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


class ConditionProfileMode(str, Enum):
    """
    Condition profile modes.
    Used by: personalized_learning, profile selection flows
    """
    TEMPLATE = "template"
    ACTIVE = "active"

    def __str__(self) -> str:
        return self.value


class ConditionProfileVisibility(str, Enum):
    """
    Condition profile visibility states.
    Used by: personalized_learning sharing
    """
    PRIVATE = "private"
    LINK = "link"
    PUBLIC = "public"

    def __str__(self) -> str:
        return self.value


class ConditionProfileTarget(str, Enum):
    """
    Link targets for condition profiles.
    Used by: personalized_learning profile links
    """
    UNIT = "unit"
    PLANT = "plant"

    def __str__(self) -> str:
        return self.value


class NotificationType(str, Enum):
    """
    Notification type categories.
    Used by: notifications_service
    """
    LOW_BATTERY = "low_battery"
    PLANT_NEEDS_WATER = "plant_needs_water"
    IRRIGATION_CONFIRM = "irrigation_confirm"
    IRRIGATION_FEEDBACK = "irrigation_feedback"
    IRRIGATION_RECOMMENDATION = "irrigation_recommendation"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    THRESHOLD_PROPOSAL = "threshold_proposal"
    IRRIGATION_SELECTION = "irrigation_selection"
    DEVICE_OFFLINE = "device_offline"
    HARVEST_READY = "harvest_ready"
    PLANT_HEALTH_WARNING = "plant_health_warning"
    SYSTEM_ALERT = "system_alert"
    ML_MODEL_READY = "ml_model_ready"
    ML_MODEL_ACTIVATED = "ml_model_activated"

    def __str__(self) -> str:
        return self.value


class NotificationSeverity(str, Enum):
    """
    Notification severity levels.
    Used by: notifications_service
    """
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

    def __str__(self) -> str:
        return self.value


class NotificationChannel(str, Enum):
    """
    Notification delivery channels.
    Used by: notifications_service
    """
    EMAIL = "email"
    IN_APP = "in_app"
    BOTH = "both"

    def __str__(self) -> str:
        return self.value


class IrrigationFeedback(str, Enum):
    """
    Irrigation feedback response types.
    Used by: notifications_service, irrigation_workflow
    """
    TOO_LITTLE = "too_little"
    JUST_RIGHT = "just_right"
    TOO_MUCH = "too_much"
    TRIGGERED_TOO_EARLY = "triggered_too_early"
    TRIGGERED_TOO_LATE = "triggered_too_late"
    SKIPPED = "skipped"

    def __str__(self) -> str:
        return self.value


class SYSGrowEvent(str, Enum):
    """
    SYSGrow ESP32-C6 device event types.
    Used by: mqtt_sensor_service, sysgrow_adapter
    """
    BRIDGE_INFO = "sysgrow.bridge.info"
    BRIDGE_HEALTH = "sysgrow.bridge.health"
    DEVICE_ONLINE = "sysgrow.device.online"
    DEVICE_OFFLINE = "sysgrow.device.offline"
    DEVICE_DISCOVERED = "sysgrow.device.discovered"
    COMMAND_SENT = "sysgrow.command.sent"
    COMMAND_RESPONSE = "sysgrow.command.response"

    def __str__(self) -> str:
        return self.value
