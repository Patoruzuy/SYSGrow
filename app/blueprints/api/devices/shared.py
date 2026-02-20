"""
Shared Device Endpoints
Handles system configuration, connectivity history, device aggregation, and error handlers.
"""

from __future__ import annotations

import logging

from flask import Response, request

from app.enums import DeviceCategory
from app.utils.http import safe_route

from ..devices import devices_api
from .utils import (
    _actuator_service,
    _device_repo,
    _fail,
    _growth_service,
    _sensor_service,  # Direct hardware access
    _success,
    _to_csv,
)

logger = logging.getLogger(__name__)

# Check if config module is available
try:
    from app.config import SystemConfigDefaults

    CONFIG_AVAILABLE = True
except ImportError:
    CONFIG_AVAILABLE = False
    logger.warning("SystemConfigDefaults not available, using defaults")

# ======================== SYSTEM CONFIGURATION ========================


@devices_api.get("/config/gpio_pins")
@safe_route("Failed to get available GPIO pins")
def get_available_gpio_pins() -> Response:
    """Get available GPIO pins"""
    if CONFIG_AVAILABLE:
        pins = SystemConfigDefaults.get_available_gpio_pins()
        return _success({"gpio_pins": pins, "count": len(pins)})
    else:
        # Return default pins if config not available
        default_pins = {
            "2": "GPIO 2",
            "3": "GPIO 3",
            "4": "GPIO 4",
            "5": "GPIO 5",
            "18": "GPIO 18",
            "19": "GPIO 19",
            "21": "GPIO 21",
            "22": "GPIO 22",
            "23": "GPIO 23",
            "25": "GPIO 25",
            "26": "GPIO 26",
            "27": "GPIO 27",
        }
        return _success({"gpio_pins": default_pins, "count": len(default_pins)})


@devices_api.get("/config/adc_channels")
@safe_route("Failed to get available ADC channels")
def get_available_adc_channels() -> Response:
    """Get available ADC channels"""
    if CONFIG_AVAILABLE:
        channels = SystemConfigDefaults.get_adc_channels()
        return _success({"adc_channels": channels, "count": len(channels)})
    else:
        # Return default channels if config not available
        default_channels = {"0": "A0", "1": "A1", "2": "A2", "3": "A3"}
        return _success({"adc_channels": default_channels, "count": len(default_channels)})


@devices_api.get("/config/sensor_types")
@safe_route("Failed to get sensor types")
def get_sensor_types() -> Response:
    """Get available sensor types and models"""
    from app.enums import SensorModel, SensorType

    env_models = [
        {"value": SensorModel.MQ2.value, "text": "Smoke/Gas Sensor (MQ2)"},
        {"value": SensorModel.MQ135.value, "text": "Air Quality Sensor (MQ135)"},
        {"value": SensorModel.BME280.value, "text": "BME280 Sensor"},
        {"value": SensorModel.BME680.value, "text": "BME680 Sensor"},
        {"value": SensorModel.ENS160AHT21.value, "text": "Environment Sensor (ENS160+AHT21)"},
        {"value": SensorModel.DHT22.value, "text": "DHT22 Sensor"},
        {"value": SensorModel.DHT11.value, "text": "DHT11 Sensor"},
        {"value": SensorModel.TSL2591.value, "text": "Light Intensity Sensor (TSL2591)"},
        {"value": SensorModel.BH1750.value, "text": "Light Sensor (BH1750)"},
    ]
    plant_models = [
        {"value": SensorModel.SOIL_MOISTURE.value, "text": "Soil Moisture Sensor"},
        {"value": SensorModel.CAPACITIVE_SOIL.value, "text": "Capacitive Soil Sensor"},
        {"value": SensorModel.PH_SENSOR.value, "text": "pH Sensor"},
        {"value": SensorModel.EC_SENSOR.value, "text": "EC Sensor"},
    ]

    # Simplified: only two sensor categories
    sensor_types: dict[str, list[dict[str, str]]] = {
        SensorType.ENVIRONMENTAL.value: env_models,
        SensorType.PLANT.value: plant_models,
    }

    return _success({"sensor_types": sensor_types})


@devices_api.get("/config/actuator_types")
@safe_route("Failed to get actuator types")
def get_actuator_types() -> Response:
    """Get available actuator types"""
    actuator_types = [
        "Light",
        "Heater",
        "Cooler",
        "Humidifier",
        "Dehumidifier",
        "Water-Pump",
        "CO2-Injector",
        "Fan",
        "Extractor",
    ]
    return _success({"actuator_types": actuator_types, "count": len(actuator_types)})


# ======================== CONNECTIVITY HISTORY ========================


@devices_api.get("/connectivity-history")
@safe_route("Failed to get connectivity history")
def get_connectivity_history() -> Response:
    """Get recent connectivity events (MQTT/WiFi/Zigbee)."""
    limit = request.args.get("limit", default=100, type=int)
    since = request.args.get("since")
    until = request.args.get("until")
    connection_type = request.args.get("connection_type")
    repo = _device_repo()
    rows = repo.get_connectivity_history(connection_type=connection_type, limit=limit, since=since, until=until)
    return _success({"history": rows, "count": len(rows)})


@devices_api.get("/connectivity-history.csv")
@safe_route("Failed to export connectivity history CSV")
def export_connectivity_history_csv() -> Response:
    limit = request.args.get("limit", default=1000, type=int)
    since = request.args.get("since")
    until = request.args.get("until")
    connection_type = request.args.get("connection_type")
    repo = _device_repo()
    rows = repo.get_connectivity_history(connection_type=connection_type, limit=limit, since=since, until=until)
    headers = ["timestamp", "connection_type", "status", "endpoint", "broker", "port", "unit_id", "device_id"]
    csv_data = _to_csv(rows, headers)
    filename = f"connectivity_{connection_type}_history.csv" if connection_type else "connectivity_history.csv"
    return Response(csv_data, mimetype="text/csv", headers={"Content-Disposition": f"attachment; filename={filename}"})


# ======================== DEVICE AGGREGATION ========================


@devices_api.get("/all/unit/<int:unit_id>")
@safe_route("Failed to get devices for unit")
def get_all_devices_for_unit(unit_id: int) -> Response:
    """
    Get all devices (sensors + actuators) for a specific unit.

    Returns grouped response with sensors and actuators separated,
    making it easy for frontend to differentiate device types.

    Response format:
    {
        "ok": true,
        "data": {
            "unit_id": 1,
            "sensors": [
                {
                    "sensor_id": 1,
                    "name": "Temperature Sensor",
                    "sensor_type": "temperature",
                    "device_type": "sensor"  // Type indicator
                }
            ],
            "actuators": [
                {
                    "actuator_id": 1,
                    "device": "Water Pump",
                    "actuator_type": "water_pump",
                    "device_type": "actuator"  // Type indicator
                }
            ],
            "total_devices": 2
        }
    }
    """
    sensor_svc = _sensor_service()
    actuator_svc = _actuator_service()
    growth_service = _growth_service()

    # Validate unit exists
    unit = growth_service.get_unit(unit_id)
    if not unit:
        return _fail(f"Growth unit {unit_id} not found", 404)

    # Get sensors for unit (direct hardware access)
    sensors = sensor_svc.list_sensors(unit_id=unit_id)
    sensor_list = []
    for sensor in sensors:
        config = dict(sensor.get("config") or {})
        sensor_list.append(
            {
                "sensor_id": sensor.get("sensor_id"),
                "name": sensor.get("name"),
                "sensor_type": sensor.get("sensor_type"),
                "protocol": sensor.get("protocol"),
                "model": sensor.get("model"),
                "config": config,
                "device_type": DeviceCategory.SENSOR.value,
            }
        )

    # Get actuators for unit (direct hardware access)
    actuators = actuator_svc.list_actuators(unit_id=unit_id)
    actuator_list = []
    for actuator in actuators:
        config = dict(actuator.get("config") or {})
        actuator_list.append(
            {
                "actuator_id": actuator.get("actuator_id"),
                "actuator_type": actuator.get("actuator_type"),
                "name": actuator.get("name"),
                "protocol": actuator.get("protocol"),
                "model": actuator.get("model"),
                "config": config,
                "device_type": DeviceCategory.ACTUATOR.value,
            }
        )

    return _success(
        {
            "unit_id": unit_id,
            "unit_name": unit.get("name"),
            "sensors": sensor_list,
            "actuators": actuator_list,
            "total_devices": len(sensor_list) + len(actuator_list),
            "sensor_count": len(sensor_list),
            "actuator_count": len(actuator_list),
        }
    )


# ======================== ERROR HANDLERS ========================


@devices_api.errorhandler(404)
def not_found(error) -> Response:
    return _fail("Resource not found", 404)


@devices_api.errorhandler(500)
def internal_error(error) -> Response:
    return _fail("Internal server error", 500)
