"""
Device Schemas
==============

Pydantic models for device (sensor/actuator) request/response validation.
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.enums import (
    Protocol,
    SensorType,
    SensorModel,
    ActuatorType,
    ActuatorState,
    PowerMode
)


# ============================================================================
# Sensor Schemas
# ============================================================================

class CreateSensorRequest(BaseModel):
    """Request model for creating a new sensor"""
    name: str = Field(..., min_length=1, max_length=100, description="Sensor name")
    type: SensorType = Field(..., description="Sensor type")
    model: SensorModel = Field(..., description="Sensor hardware model")
    protocol: Protocol = Field(default=Protocol.GPIO, description="Communication protocol")
    gpio_pin: Optional[int] = Field(default=None, ge=0, le=40, description="GPIO pin number (if applicable)")
    i2c_address: Optional[str] = Field(default=None, max_length=10, description="I2C address (if applicable)")
    unit_id: int = Field(..., gt=0, description="Associated growth unit ID")
    esp32_id: Optional[int] = Field(default=None, gt=0, description="Associated ESP32 device ID")
    power_mode: PowerMode = Field(default=PowerMode.NORMAL, description="Power management mode")
    min_threshold: Optional[float] = Field(default=None, description="Minimum threshold value")
    max_threshold: Optional[float] = Field(default=None, description="Maximum threshold value")
    mqtt_topic: Optional[str] = Field(default=None, max_length=255, description="MQTT topic for MQTT/zigbee2mqtt devices")
    zigbee_address: Optional[str] = Field(default=None, max_length=64, description="Zigbee device address (if applicable)")
    primary_metrics: Optional[List[str]] = Field(
        default=None,
        description="Optional list of primary metrics for priority selection"
    )

    @field_validator("type", mode="before")
    def _coerce_sensor_type(cls, v):
        """Coerce sensor type to SensorType enum"""
        if isinstance(v, SensorType):
            return v
        if isinstance(v, str):
            # Try direct value match first (e.g., "environment_sensor", "soil_moisture")
            try:
                return SensorType(v)
            except ValueError:
                pass
            # Try uppercase attribute name (e.g., "ENVIRONMENT" -> SensorType.ENVIRONMENT)
            upper = v.upper()
            if hasattr(SensorType, upper):
                return getattr(SensorType, upper)
        raise ValueError(f"Unsupported sensor type '{v}'")

    @field_validator("model", mode="before")
    def _coerce_sensor_model(cls, v):
        if isinstance(v, SensorModel):
            return v
        if isinstance(v, str):
            # Try exact match first
            try:
                return SensorModel(v)
            except ValueError:
                pass
            # Try uppercase with underscore normalization
            upper = v.upper().replace("-", "_")
            if hasattr(SensorModel, upper):
                return getattr(SensorModel, upper)
        raise ValueError(f"Unsupported sensor model '{v}'")

    @field_validator("protocol", mode="before")
    def _coerce_protocol(cls, v):
        if isinstance(v, Protocol):
            return v
        if isinstance(v, str):
            # Try exact match first (handles lowercase values like 'zigbee2mqtt')
            try:
                return Protocol(v)
            except ValueError:
                pass
            # Try uppercase
            upper = v.upper()
            if hasattr(Protocol, upper):
                return getattr(Protocol, upper)
        raise ValueError(f"Unsupported protocol '{v}'")

    @field_validator("i2c_address")
    def validate_i2c_address(cls, v):
        """Validate I2C address format (e.g., 0x76)"""
        if v is not None and not v.startswith("0x"):
            raise ValueError("I2C address must start with 0x")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Temperature Sensor 1",
                "type": "temperature",
                "model": "DHT22",
                "communication_type": "GPIO",
                "gpio_pin": 4,
                "mqtt_topic": "zigbee2mqtt/device_id",
                "zigbee_address": "0x00158d0001a2b3c4",
                "unit_id": 1,
                "power_mode": "normal",
                "min_threshold": 15.0,
                "max_threshold": 30.0,
            }
        }
    )


class UpdateSensorRequest(BaseModel):
    """Request model for updating an existing sensor"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    type: Optional[SensorType] = Field(default=None)
    model: Optional[SensorModel] = Field(default=None)
    communication_type: Optional[Protocol] = Field(default=None)
    gpio_pin: Optional[int] = Field(default=None, ge=0, le=40)
    i2c_address: Optional[str] = Field(default=None, max_length=10)
    power_mode: Optional[PowerMode] = Field(default=None)
    min_threshold: Optional[float] = Field(default=None)
    max_threshold: Optional[float] = Field(default=None)
    primary_metrics: Optional[List[str]] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Sensor Name",
                "min_threshold": 18.0,
                "max_threshold": 28.0,
                "enabled": True,
            }
        }
    )


class SensorResponse(BaseModel):
    """Response model for sensor data"""
    id: int
    name: str
    type: str
    model: str
    communication_type: str
    gpio_pin: Optional[int]
    i2c_address: Optional[str]
    unit_id: int
    esp32_id: Optional[int]
    power_mode: str
    min_threshold: Optional[float]
    max_threshold: Optional[float]
    primary_metrics: Optional[List[str]] = None
    enabled: bool
    last_value: Optional[float]
    last_reading_time: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Temperature Sensor 1",
                "type": "temperature",
                "model": "DHT22",
                "communication_type": "GPIO",
                "gpio_pin": 4,
                "i2c_address": None,
                "unit_id": 1,
                "esp32_id": 1,
                "power_mode": "normal",
                "min_threshold": 15.0,
                "max_threshold": 30.0,
                "enabled": True,
                "last_value": 22.5,
                "last_reading_time": "2024-01-15T10:30:00",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-15T10:30:00",
            }
        }
    )


# ============================================================================
# Actuator Schemas
# ============================================================================

class CreateActuatorRequest(BaseModel):
    """Request model for creating a new actuator"""
    name: str = Field(..., min_length=1, max_length=100, description="Actuator name")
    type: ActuatorType = Field(..., description="Actuator type")
    communication_type: Protocol = Field(default=Protocol.GPIO, description="Communication protocol")
    gpio_pin: Optional[int] = Field(default=None, ge=0, le=40, description="GPIO pin number (if applicable)")
    unit_id: int = Field(..., gt=0, description="Associated growth unit ID")
    esp32_id: Optional[int] = Field(default=None, gt=0, description="Associated ESP32 device ID")
    state: ActuatorState = Field(default=ActuatorState.OFF, description="Initial actuator state")
    power_mode: PowerMode = Field(default=PowerMode.NORMAL, description="Power management mode")

    @field_validator("type", mode="before")
    def _coerce_actuator_type(cls, v):
        mapping = {
            "WATER_PUMP": ActuatorType.WATER_PUMP,
            "CO2_INJECTOR": ActuatorType.CO2_INJECTOR,
            "HUMIDIFIER": ActuatorType.HUMIDIFIER,
            "DEHUMIDIFIER": ActuatorType.DEHUMIDIFIER,
            "LIGHT": ActuatorType.LIGHT,
            "HEATER": ActuatorType.HEATER,
            "COOLER": ActuatorType.COOLER,
            "FAN": ActuatorType.FAN,
            "EXTRACTOR": ActuatorType.EXTRACTOR,
            "RELAY": ActuatorType.RELAY,
            "VALVE": ActuatorType.VALVE,
            "MOTOR": ActuatorType.MOTOR,
        }
        if isinstance(v, ActuatorType):
            return v
        if isinstance(v, str):
            upper = v.upper()
            if upper in mapping:
                return mapping[upper]
            if hasattr(ActuatorType, upper):
                return getattr(ActuatorType, upper)
            try:
                return ActuatorType(v)
            except ValueError:
                pass
        raise ValueError(f"Unsupported actuator type '{v}'")

    @field_validator("communication_type", mode="before")
    def _coerce_comm_type_actuator(cls, v):
        if isinstance(v, Protocol):
            return v
        if isinstance(v, str):
            upper = v.upper()
            if hasattr(Protocol, upper):
                return getattr(Protocol, upper)
            try:
                return Protocol(v)
            except ValueError:
                pass
        raise ValueError(f"Unsupported communication type '{v}'")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Main Grow Light",
                "type": "Light",
                "communication_type": "GPIO",
                "gpio_pin": 5,
                "unit_id": 1,
                "esp32_id": 1,
                "state": "OFF",
                "power_mode": "normal",
            }
        }
    )


class UpdateActuatorRequest(BaseModel):
    """Request model for updating an existing actuator"""
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    type: Optional[ActuatorType] = Field(default=None)
    communication_type: Optional[Protocol] = Field(default=None)
    gpio_pin: Optional[int] = Field(default=None, ge=0, le=40)
    state: Optional[ActuatorState] = Field(default=None)
    power_mode: Optional[PowerMode] = Field(default=None)
    enabled: Optional[bool] = Field(default=None)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Updated Light Name",
                "state": "AUTO",
                "enabled": True,
            }
        }
    )


class ControlActuatorRequest(BaseModel):
    """Request model for controlling actuator state"""
    state: ActuatorState = Field(..., description="Desired actuator state")
    duration: Optional[int] = Field(default=None, ge=0, description="Duration in seconds (for timed operations)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "state": "ON",
                "duration": 3600,
            }
        }
    )


class ActuatorResponse(BaseModel):
    """Response model for actuator data"""
    id: int
    name: str
    type: str
    communication_type: str
    gpio_pin: Optional[int]
    unit_id: int
    esp32_id: Optional[int]
    state: str
    power_mode: str
    enabled: bool
    last_state_change: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "name": "Main Grow Light",
                "type": "Light",
                "communication_type": "GPIO",
                "gpio_pin": 5,
                "unit_id": 1,
                "esp32_id": 1,
                "state": "ON",
                "power_mode": "normal",
                "enabled": True,
                "last_state_change": "2024-01-15T08:00:00",
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-15T08:00:00",
            }
        }
    )
