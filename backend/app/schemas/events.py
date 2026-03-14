from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal
from app.enums.events import SensorEvent, NotificationEvent, NotificationSeverity

PowerSource = Literal["battery", "mains", "unknown"]
ReadingStatus = Literal["success", "warning", "error", "mock"]  # ensure emitter maps to these
Protocol = Literal[
    "zigbee2mqtt",
    "zigbee",
    "mqtt",
    "esp32",
    "gpio",
    "i2c",
    "adc",
    "spi",
    "onewire",
    "http",
    "modbus",
    "wireless",
    "other",
]
TrendDirection = Literal["rising", "falling", "stable", "unknown"]

class DeviceSensorReadingPayload(BaseModel):
    """Payload for device sensor reading events - supports multi-value sensors."""
    schema_version: int = Field(default=1)

    # Sensor identification
    sensor_id: int
    unit_id: int
    sensor_name: Optional[str] = None
    sensor_type: Optional[str] = None

    # Sensor protocol
    protocol: Optional[Protocol] = None  # useful for UI badges/debug
    # Sensor readings
    readings: Dict[str, float]
    units: Dict[str, str] = Field(default_factory=dict)

    # Metadata
    status: ReadingStatus
    timestamp: str
    # Power/connectivity (for wireless sensors)
    battery: Optional[int] = None
    power_source: PowerSource = "unknown"
    linkquality: Optional[int] = None
    # Quality indicators
    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_anomaly: bool = False
    anomaly_reason: Optional[str] = None
    calibration_applied: bool = False


class MetricSource(BaseModel):
    """Source information for a dashboard metric."""
    sensor_id: int
    sensor_name: Optional[str] = None
    sensor_type: Optional[str] = None
    protocol: Optional[Protocol] = None

    battery: Optional[int] = None
    power_source: PowerSource = "unknown"
    linkquality: Optional[int] = None

    quality_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    status: Optional[ReadingStatus] = None
    is_anomaly: bool = False


class DashboardMetric(BaseModel):
    """A single metric in a dashboard snapshot."""
    value: Optional[float] = None
    unit: Optional[str] = None
    source: Optional[MetricSource] = None
    trend: Optional[TrendDirection] = Field(
        None,
        description="Direction of change since last reading: rising, falling, stable, or unknown"
    )
    trend_delta: Optional[float] = Field(
        None,
        description="Absolute change from previous reading (same units as value)"
    )


class DashboardSnapshotPayload(BaseModel):
    """Payload for dashboard snapshot events."""
    schema_version: int = Field(default=1)
    unit_id: int
    timestamp: str
    # Metrics keyed by reading_type (e.g., "temperature", "humidity", "soil_moisture")
    metrics: Dict[str, DashboardMetric] = Field(
        description="Primary metrics for this unit, keyed by reading type"
    )

class UnregisteredSensorPayload(BaseModel):
    """Payload for unregistered sensor events."""
    schema_version: int = Field(default=1)

    # Known for ESP32 topics; unknown for Zigbee2MQTT unregistered devices.
    unit_id: Optional[int] = None

    registered: bool = Field(default=False)
    protocol: Protocol = "zigbee2mqtt"
    publisher_id: str  # e.g. "zigbee2mqtt:Environment_sensor"
    topic: Optional[str] = None

    friendly_name: Optional[str] = None
    timestamp: str

    raw_data: Dict[str, Any]

    suggested_sensor_type: Optional[str] = None
    detected_capabilities: Optional[List[str]] = None

class SensorUpdatePayload(BaseModel):
    """Payload for sensor update events - single value sensors.
       This is the schema for Event.SensorEvent readings. EventBus events use.
    """
    unit_id: Optional[int | str] = None
    sensor_id: Optional[int]
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    soil_moisture: Optional[float] = None
    co2: Optional[float] = None
    voc: Optional[float] = None
    timestamp: Optional[str] = None

class SensorReadingPayload(BaseModel):
    """This is decrepted in favor of DeviceSensorReadingPayload - use that for new events.
    """
    sensor_id: int
    unit_id: Optional[int] = None
    readings: Dict[str, float]  # e.g., {"temperature": 22.5, "humidity": 65.0, "soil_moisture": 45.0, "lux": 800.0}
    units: Optional[Dict[str, str]] = None  # e.g., {"temperature": "°C", "humidity": "%", "soil_moisture": "%", "lux": "lux"}
    timestamp: Optional[str] = None
    

class SensorAnomalyPayload(BaseModel):
    sensor_id: int
    unit_id: Optional[int] = None
    anomaly_type: str  # e.g., 'out_of_range', 'no_data', 'rapid_change'
    severity: str  # 'low', 'medium', 'high'
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None

class SensorAnomalyResolvedPayload(BaseModel):
    anomaly_id: int
    resolved_at: Optional[str] = None

class SensorCalibrationPayload(BaseModel):
    sensor_id: int
    calibration_type: str  # e.g., 'offset', 'scaling'
    calibration_data: Dict[str, Any]  # e.g., {"offset": -2.0} or {"scaling_factor": 1.05}
    timestamp: Optional[str] = None

class PlantLifecyclePayload(BaseModel):
    unit_id: Optional[int]
    plant_id: int
    new_stage: Optional[str] = None
    days_in_stage: Optional[int] = None


class PlantStageUpdatePayload(BaseModel):
    plant_id: int
    new_stage: str
    days_in_stage: int


class PlantGrowthWarningPayload(BaseModel):
    plant_id: int
    unit_id: Optional[int] = None
    stage: str
    days_in_stage: Optional[int] = None
    days_to_transition: Optional[int] = None
    message: str


class DeviceLifecyclePayload(BaseModel):
    unit_id: int
    sensor_id: Optional[int] = None
    actuator_id: Optional[int] = None


class ActuatorLifecyclePayload(BaseModel):
    actuator_id: int
    name: Optional[str] = None
    actuator_type: Optional[str] = None
    protocol: Optional[str] = None
    unit_id: Optional[int] = None
    timestamp: Optional[str] = None


class ActuatorAnomalyPayload(BaseModel):
    actuator_id: int
    anomaly_id: Optional[int] = None
    anomaly_type: str
    severity: str
    details: Optional[Dict[str, Any]] = None


class ActuatorAnomalyResolvedPayload(BaseModel):
    anomaly_id: int
    resolved_at: Optional[str] = None


class ActuatorCalibrationPayload(BaseModel):
    actuator_id: int
    calibration_type: str
    calibration_data: Dict[str, Any]


class ThresholdsUpdatePayload(BaseModel):
    unit_id: int
    thresholds: Dict[str, Any]


class ThresholdsPersistPayload(BaseModel):
    """Payload for RuntimeEvent.THRESHOLDS_PERSIST - request to persist thresholds to DB."""
    unit_id: int
    thresholds: Dict[str, float]


class ThresholdsProposedPayload(BaseModel):
    """Payload for RuntimeEvent.THRESHOLDS_PROPOSED - proposed thresholds awaiting approval."""
    unit_id: int
    user_id: Optional[int] = None
    plant_id: Optional[int] = None
    plant_type: Optional[str] = None
    growth_stage: Optional[str] = None
    current_thresholds: Dict[str, float]
    proposed_thresholds: Dict[str, float]
    source: Optional[str] = None


class ActivePlantSetPayload(BaseModel):
    """Payload for RuntimeEvent.ACTIVE_PLANT_SET - request to set active plant."""
    unit_id: int
    plant_id: int


class SensorReloadPayload(BaseModel):
    unit_id: Optional[int] = None
    source: Optional[str] = None


class RelayStatePayload(BaseModel):
    device: str
    state: str
    unit_id: Optional[int] = None
    timestamp: Optional[str] = None


class DeviceCommandPayload(BaseModel):
    command: str
    device_id: str
    unit_id: Optional[int] = None
    parameters: Dict[str, Any] = {}
    timestamp: Optional[str] = None


class NotificationPayload(BaseModel):
    """Payload for user-scoped notifications via WebSocket."""
    userId: int
    title: str
    message: str
    event: str = "notification"  # WebSocket event name
    notificationType: Optional[str] = None  # low_battery, plant_needs_water, etc.
    severity: str = "info"  # info, warning, critical
    messageId: Optional[int] = None  # Database message ID
    unitId: Optional[int] = None
    timestamp: Optional[str] = None
    requiresAction: bool = False
    actionType: Optional[str] = None
    actionData: Optional[Dict[str, Any]] = None


class ActuatorStatePayload(BaseModel):
    actuator_id: Optional[int] = None
    unit_id: Optional[int] = None
    device_name: Optional[str] = None
    state: str
    value: Optional[float] = None
    timestamp: Optional[str] = None


class ConnectivityStatePayload(BaseModel):
    connection_type: str  # e.g., 'mqtt', 'wifi', 'zigbee'
    status: str  # 'connected' | 'disconnected' | other
    endpoint: Optional[str] = None  # e.g., broker host:port, ssid, etc.
    port: Optional[int] = None
    unit_id: Optional[int] = None
    device_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: Optional[str] = None

class NotificationEventPayload(BaseModel):
    """System notification payload that is not user-scoped."""
    notification_type: NotificationEvent  # e.g., 'sensor_anomaly', 'actuator_anomaly', 'system_alert'
    severity: NotificationSeverity  # 'info', 'warning', 'critical'
    message: str
    unit_id: Optional[int] = None
    sensor_id: Optional[int] = None
    actuator_id: Optional[int] = None
    plant_id: Optional[int] = None
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
