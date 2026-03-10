from enum import Enum
from typing import TypeAlias


class WebSocketEvent(str, Enum):
    """WebSocket event names for real-time communication."""

    # Device namespace events
    DEVICE_SENSOR_READING = "device_sensor_reading"
    UNREGISTERED_SENSOR_DATA = "unregistered_sensor_data"

    # Dashboard namespace events
    DASHBOARD_SNAPSHOT = "dashboard_snapshot"

    # Actuator events
    ACTUATOR_STATE_UPDATE = "actuator_state_update"

    # Alert events
    ALERT_CREATED = "alert_created"
    ALERT_RESOLVED = "alert_resolved"


class NotificationEvent(str, Enum):
    SENSOR_ANOMALY = "sensor_anomaly"
    ACTUATOR_ANOMALY = "actuator_anomaly"
    SYSTEM_ALERT = "system_alert"
    PLANT_HEALTH_WARNING = "plant_health_warning"
    PLANT_EVENT = "plant_event"


class NotificationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class IrrigationEligibilityDecision(str, Enum):
    """Decision outcomes for irrigation eligibility tracing."""

    NOTIFY = "notify"
    SKIP = "skip"


class IrrigationSkipReason(str, Enum):
    """Skip reasons for irrigation eligibility tracing."""

    DISABLED = "disabled"
    PENDING_REQUEST = "pending_request"
    HYSTERESIS_NOT_MET = "hysteresis_not_met"
    NO_ACTUATOR = "no_actuator"
    NO_SENSOR = "no_sensor"
    STALE_READING = "stale_reading"
    COOLDOWN_ACTIVE = "cooldown_active"
    MANUAL_MODE_NO_AUTO = "manual_mode_no_auto"
    CALLBACK_ERROR = "callback_error"
    REQUEST_CREATE_FAILED = "request_create_failed"


class SensorEvent(str, Enum):
    TEMPERATURE_UPDATE = "temperature_update"
    HUMIDITY_UPDATE = "humidity_update"
    SOIL_MOISTURE_UPDATE = "soil_moisture_update"
    CO2_UPDATE = "co2_update"
    VOC_UPDATE = "voc_update"
    LIGHT_UPDATE = "light_update"
    PRESSURE_UPDATE = "pressure_update"
    PH_UPDATE = "ph_update"
    EC_UPDATE = "ec_update"
    AIR_QUALITY_UPDATE = "air_quality_update"
    SMOKE_UPDATE = "smoke_update"

    @staticmethod
    def for_type(sensor_type: str) -> "SensorEvent":
        base = sensor_type.replace("_sensor", "") if isinstance(sensor_type, str) else sensor_type
        mapping = {
            "temperature": SensorEvent.TEMPERATURE_UPDATE,
            "humidity": SensorEvent.HUMIDITY_UPDATE,
            "soil_moisture": SensorEvent.SOIL_MOISTURE_UPDATE,
            "moisture": SensorEvent.SOIL_MOISTURE_UPDATE,
            "co2": SensorEvent.CO2_UPDATE,
            "voc": SensorEvent.VOC_UPDATE,
            "temp_humidity": SensorEvent.HUMIDITY_UPDATE,
            "environment": SensorEvent.TEMPERATURE_UPDATE,
        }
        return mapping.get(base, SensorEvent.VOC_UPDATE)


class PlantEvent(str, Enum):
    PLANT_ADDED = "plant_added"
    PLANT_REMOVED = "plant_removed"
    PLANT_STAGE_UPDATE = "plant_stage_update"
    MOISTURE_LEVEL_UPDATED = "moisture_level_updated"
    ACTIVE_PLANT_CHANGED = "active_plant_changed"
    GROWTH_WARNING = "growth_warning"
    GROWTH_TIME_UPDATE = "growth_time_update"
    PLANT_HEALTH_UPDATE = "plant_health_update"


class DeviceEvent(str, Enum):
    SENSOR_CREATED = "sensor_created"
    SENSOR_DELETED = "sensor_deleted"
    ACTUATOR_CREATED = "actuator_created"
    ACTUATOR_DELETED = "actuator_deleted"
    RELAY_STATE_CHANGED = "relay_state_changed"
    DEVICE_COMMAND = "device_command"
    ACTUATOR_ANOMALY_DETECTED = "actuator_anomaly_detected"
    ACTUATOR_ANOMALY_RESOLVED = "actuator_anomaly_resolved"
    ACTUATOR_CALIBRATION_UPDATED = "actuator_calibration_updated"
    ACTUATOR_STATE_CHANGED = "actuator_state_changed"
    CONNECTIVITY_CHANGED = "connectivity_changed"
    ACTUATOR_REGISTERED = "actuator_registered"
    ACTUATOR_UNREGISTERED = "actuator_unregistered"
    DEVICE_AVAILABILITY_CHANGED = "device_availability_changed"


class RuntimeEvent(str, Enum):
    THRESHOLDS_UPDATE = "thresholds_update"
    THRESHOLDS_PERSIST = "thresholds_persist"  # Request to persist thresholds to DB
    THRESHOLDS_PROPOSED = "thresholds_proposed"  # Proposed thresholds awaiting user approval
    ACTIVE_PLANT_SET = "active_plant_set"  # Request to set active plant
    SENSOR_RELOAD = "sensor_reload"


class ActivityEvent(str, Enum):
    """Activity events for logging user actions and system events."""

    PLANT_ADDED = "activity.plant_added"
    PLANT_REMOVED = "activity.plant_removed"
    PLANT_UPDATED = "activity.plant_updated"
    UNIT_CREATED = "activity.unit_created"
    UNIT_UPDATED = "activity.unit_updated"
    UNIT_DELETED = "activity.unit_deleted"
    DEVICE_CONNECTED = "activity.device_connected"
    DEVICE_DISCONNECTED = "activity.device_disconnected"
    DEVICE_CONFIGURED = "activity.device_configured"
    HARVEST_RECORDED = "activity.harvest_recorded"
    HARVEST_UPDATED = "activity.harvest_updated"
    THRESHOLD_OVERRIDE = "activity.threshold_override"
    MANUAL_CONTROL = "activity.manual_control"
    SYSTEM_STARTUP = "activity.system_startup"
    SYSTEM_SHUTDOWN = "activity.system_shutdown"
    USER_LOGIN = "activity.user_login"
    USER_LOGOUT = "activity.user_logout"


EventType: TypeAlias = SensorEvent | PlantEvent | DeviceEvent | RuntimeEvent | ActivityEvent | WebSocketEvent
