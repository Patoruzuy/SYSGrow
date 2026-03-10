from typing import Any, Literal

from pydantic import BaseModel, Field

from app.enums.events import NotificationEvent, NotificationSeverity

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
    sensor_name: str | None = None
    sensor_type: str | None = None

    # Sensor protocol
    protocol: Protocol | None = None  # useful for UI badges/debug
    # Sensor readings
    readings: dict[str, float]
    units: dict[str, str] = Field(default_factory=dict)

    # Metadata
    status: ReadingStatus
    timestamp: str
    # Power/connectivity (for wireless sensors)
    battery: int | None = None
    power_source: PowerSource = "unknown"
    linkquality: int | None = None
    # Quality indicators
    quality_score: float | None = Field(None, ge=0.0, le=1.0)
    is_anomaly: bool = False
    anomaly_reason: str | None = None
    calibration_applied: bool = False


class MetricSource(BaseModel):
    """Source information for a dashboard metric."""

    sensor_id: int
    sensor_name: str | None = None
    sensor_type: str | None = None
    protocol: Protocol | None = None

    battery: int | None = None
    power_source: PowerSource = "unknown"
    linkquality: int | None = None

    quality_score: float | None = Field(None, ge=0.0, le=1.0)
    status: ReadingStatus | None = None
    is_anomaly: bool = False


class DashboardMetric(BaseModel):
    """A single metric in a dashboard snapshot."""

    value: float | None = None
    unit: str | None = None
    source: MetricSource | None = None
    trend: TrendDirection | None = Field(
        None, description="Direction of change since last reading: rising, falling, stable, or unknown"
    )
    trend_delta: float | None = Field(None, description="Absolute change from previous reading (same units as value)")


class DashboardSnapshotPayload(BaseModel):
    """Payload for dashboard snapshot events."""

    schema_version: int = Field(default=1)
    unit_id: int
    timestamp: str
    # Metrics keyed by reading_type (e.g., "temperature", "humidity", "soil_moisture")
    metrics: dict[str, DashboardMetric] = Field(description="Primary metrics for this unit, keyed by reading type")


class UnregisteredSensorPayload(BaseModel):
    """Payload for unregistered sensor events."""

    schema_version: int = Field(default=1)

    # Known for ESP32 topics; unknown for Zigbee2MQTT unregistered devices.
    unit_id: int | None = None

    registered: bool = Field(default=False)
    protocol: Protocol = "zigbee2mqtt"
    publisher_id: str  # e.g. "zigbee2mqtt:Environment_sensor"
    topic: str | None = None

    friendly_name: str | None = None
    timestamp: str

    raw_data: dict[str, Any]

    suggested_sensor_type: str | None = None
    detected_capabilities: list[str] | None = None


class SensorUpdatePayload(BaseModel):
    """Payload for sensor update events - single value sensors.
    This is the schema for Event.SensorEvent readings. EventBus events use.
    """

    unit_id: int | str | None = None
    sensor_id: int | None
    temperature: float | None = None
    humidity: float | None = None
    soil_moisture: float | None = None
    co2: float | None = None
    voc: float | None = None
    timestamp: str | None = None


class SensorReadingPayload(BaseModel):
    """This is decrepted in favor of DeviceSensorReadingPayload - use that for new events."""

    sensor_id: int
    unit_id: int | None = None
    readings: dict[str, float]  # e.g., {"temperature": 22.5, "humidity": 65.0, "soil_moisture": 45.0, "lux": 800.0}
    units: dict[str, str] | None = (
        None  # e.g., {"temperature": "°C", "humidity": "%", "soil_moisture": "%", "lux": "lux"}
    )
    timestamp: str | None = None


class SensorAnomalyPayload(BaseModel):
    sensor_id: int
    unit_id: int | None = None
    anomaly_type: str  # e.g., 'out_of_range', 'no_data', 'rapid_change'
    severity: str  # 'low', 'medium', 'high'
    details: dict[str, Any] | None = None
    timestamp: str | None = None


class SensorAnomalyResolvedPayload(BaseModel):
    anomaly_id: int
    resolved_at: str | None = None


class SensorCalibrationPayload(BaseModel):
    sensor_id: int
    calibration_type: str  # e.g., 'offset', 'scaling'
    calibration_data: dict[str, Any]  # e.g., {"offset": -2.0} or {"scaling_factor": 1.05}
    timestamp: str | None = None


class PlantLifecyclePayload(BaseModel):
    unit_id: int | None
    plant_id: int
    new_stage: str | None = None
    days_in_stage: int | None = None


class PlantStageUpdatePayload(BaseModel):
    plant_id: int
    new_stage: str
    days_in_stage: int


class PlantGrowthWarningPayload(BaseModel):
    plant_id: int
    unit_id: int | None = None
    stage: str
    days_in_stage: int | None = None
    days_to_transition: int | None = None
    message: str


class DeviceLifecyclePayload(BaseModel):
    unit_id: int
    sensor_id: int | None = None
    actuator_id: int | None = None


class ActuatorLifecyclePayload(BaseModel):
    actuator_id: int
    name: str | None = None
    actuator_type: str | None = None
    protocol: str | None = None
    unit_id: int | None = None
    timestamp: str | None = None


class ActuatorAnomalyPayload(BaseModel):
    actuator_id: int
    anomaly_id: int | None = None
    anomaly_type: str
    severity: str
    details: dict[str, Any] | None = None


class ActuatorAnomalyResolvedPayload(BaseModel):
    anomaly_id: int
    resolved_at: str | None = None


class ActuatorCalibrationPayload(BaseModel):
    actuator_id: int
    calibration_type: str
    calibration_data: dict[str, Any]


class ThresholdsUpdatePayload(BaseModel):
    unit_id: int
    thresholds: dict[str, Any]


class ThresholdsPersistPayload(BaseModel):
    """Payload for RuntimeEvent.THRESHOLDS_PERSIST - request to persist thresholds to DB."""

    unit_id: int
    thresholds: dict[str, float]


class ThresholdsProposedPayload(BaseModel):
    """Payload for RuntimeEvent.THRESHOLDS_PROPOSED - proposed thresholds awaiting approval."""

    unit_id: int
    user_id: int | None = None
    plant_id: int | None = None
    plant_type: str | None = None
    growth_stage: str | None = None
    current_thresholds: dict[str, float]
    proposed_thresholds: dict[str, float]
    source: str | None = None


class ActivePlantSetPayload(BaseModel):
    """Payload for RuntimeEvent.ACTIVE_PLANT_SET - request to set active plant."""

    unit_id: int
    plant_id: int


class SensorReloadPayload(BaseModel):
    unit_id: int | None = None
    source: str | None = None


class RelayStatePayload(BaseModel):
    device: str
    state: str
    unit_id: int | None = None
    timestamp: str | None = None


class DeviceCommandPayload(BaseModel):
    command: str
    device_id: str
    unit_id: int | None = None
    parameters: dict[str, Any] = {}
    timestamp: str | None = None


class NotificationPayload(BaseModel):
    """Payload for user-scoped notifications via WebSocket."""

    userId: int
    title: str
    message: str
    event: str = "notification"  # WebSocket event name
    notificationType: str | None = None  # low_battery, plant_needs_water, etc.
    severity: str = "info"  # info, warning, critical
    messageId: int | None = None  # Database message ID
    unitId: int | None = None
    timestamp: str | None = None
    requiresAction: bool = False
    actionType: str | None = None
    actionData: dict[str, Any] | None = None


class ActuatorStatePayload(BaseModel):
    actuator_id: int | None = None
    unit_id: int | None = None
    device_name: str | None = None
    state: str
    value: float | None = None
    timestamp: str | None = None


class ConnectivityStatePayload(BaseModel):
    connection_type: str  # e.g., 'mqtt', 'wifi', 'zigbee'
    status: str  # 'connected' | 'disconnected' | other
    endpoint: str | None = None  # e.g., broker host:port, ssid, etc.
    port: int | None = None
    unit_id: int | None = None
    device_id: str | None = None
    details: dict[str, Any] | None = None
    timestamp: str | None = None


class NotificationEventPayload(BaseModel):
    """System notification payload that is not user-scoped."""

    notification_type: NotificationEvent  # e.g., 'sensor_anomaly', 'actuator_anomaly', 'system_alert'
    severity: NotificationSeverity  # 'info', 'warning', 'critical'
    message: str
    unit_id: int | None = None
    sensor_id: int | None = None
    actuator_id: int | None = None
    plant_id: int | None = None
    timestamp: str | None = None
    metadata: dict[str, Any] | None = None
