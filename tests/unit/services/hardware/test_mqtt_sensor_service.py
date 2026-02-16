"""
Unit Tests for MQTTSensorService
=================================
Tests for unified MQTT sensor service (Zigbee + ESP32).
"""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.schemas.events import DeviceSensorReadingPayload
from app.services.hardware.mqtt_sensor_service import MQTTSensorService


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client"""
    client = Mock()
    client.subscribe = Mock()
    return client


@pytest.fixture
def mock_emitter():
    """Mock emitter service"""
    emitter = Mock()
    emitter.emit_device_sensor_reading = Mock()
    emitter.emit_dashboard_snapshot = Mock()
    emitter.emit_unregistered_sensor_data = Mock()
    return emitter


@pytest.fixture
def mock_sensor_manager():
    """Mock sensor manager (SensorManagementService)"""
    manager = Mock()
    manager.get_sensor_entity = Mock()
    manager.get_sensor_by_friendly_name = Mock()
    return manager


@pytest.fixture
def mock_processor():
    """Mock processor pipeline (process + build_payloads)."""
    processor = Mock()
    processor.process = Mock()
    processor.build_payloads = Mock()
    return processor


@pytest.fixture
def mqtt_sensor_service(mock_mqtt_client, mock_emitter, mock_sensor_manager, mock_processor):
    """Create MQTTSensorService instance"""
    return MQTTSensorService(
        mqtt_client=mock_mqtt_client,
        emitter=mock_emitter,
        sensor_manager=mock_sensor_manager,
        processor=mock_processor,
    )


def _make_msg(topic: str, payload_obj) -> Mock:
    msg = Mock()
    msg.topic = topic
    msg.payload = json.dumps(payload_obj).encode()
    return msg


class TestMQTTSensorServiceInitialization:
    """Test service initialization"""

    def test_subscribes_to_topics(self, mqtt_sensor_service, mock_mqtt_client):
        """Should subscribe to Zigbee and ESP32 topics"""
        # Verify subscriptions
        assert mock_mqtt_client.subscribe.call_count >= 3

        # Check for expected topics
        calls = mock_mqtt_client.subscribe.call_args_list
        topics = [call[0][0] for call in calls]

        assert "zigbee2mqtt/+" in topics
        # Current implementation subscribes to SYSGrow-style topics
        assert "sysgrow/+" in topics
        assert "sysgrow/+/availability" in topics

    def test_initializes_basic_state(self, mqtt_sensor_service):
        """Should initialize basic routing state"""
        assert isinstance(mqtt_sensor_service.last_seen, dict)
        assert isinstance(mqtt_sensor_service.sensor_health, dict)


class TestZigbeeMessageHandling:
    """Test Zigbee2MQTT message handling"""

    def test_handles_registered_zigbee_message_emits_device_payload(
        self,
        mqtt_sensor_service,
        mock_sensor_manager,
        mock_processor,
        mock_emitter,
    ):
        """Registered Zigbee2MQTT device should be processed and emitted to /devices."""
        # Create sensor object returned by sensor manager
        sensor = Mock()
        sensor.id = 1
        sensor.unit_id = 1
        sensor.name = "Test Sensor"
        sensor.sensor_type = "environment_sensor"
        sensor.protocol = "zigbee2mqtt"
        mock_sensor_manager.get_sensor_entity.return_value = sensor
        mock_sensor_manager.get_sensor_by_friendly_name.return_value = sensor

        reading = SimpleNamespace(
            sensor_id=1,
            unit_id=1,
            data={"temperature": 22.5},
            status=SimpleNamespace(value="success"),
            timestamp=SimpleNamespace(isoformat=lambda: "2026-01-02T00:00:00Z"),
            is_anomaly=False,
        )
        mock_processor.process.return_value = reading

        device_payload = DeviceSensorReadingPayload(
            sensor_id=1,
            unit_id=1,
            sensor_name="Test Sensor",
            sensor_type="environment_sensor",
            protocol="zigbee2mqtt",
            readings={"temperature": 22.5},
            units={"temperature": "°C"},
            status="success",
            timestamp="2026-01-02T00:00:00Z",
        )

        prepared = SimpleNamespace(unit_id=1, device_payload=device_payload, dashboard_payload=None)
        mock_processor.build_payloads.return_value = prepared

        msg = _make_msg("zigbee2mqtt/temp_sensor_1", {"temperature": 22.5})
        mqtt_sensor_service._on_message(None, None, msg)

        mock_sensor_manager.get_sensor_by_friendly_name.assert_called_once_with("temp_sensor_1")
        mock_sensor_manager.get_sensor_entity.assert_any_call(1)
        mock_processor.process.assert_called_once()
        mock_processor.build_payloads.assert_called_once()
        mock_emitter.emit_device_sensor_reading.assert_called_once()

    def test_skips_bridge_messages(self, mqtt_sensor_service, mock_processor, mock_emitter):
        """Should skip Zigbee2MQTT bridge messages"""
        msg = _make_msg("zigbee2mqtt/bridge", {"type": "bridge"})
        mqtt_sensor_service._on_message(None, None, msg)
        mock_processor.process.assert_not_called()
        mock_emitter.emit_device_sensor_reading.assert_not_called()

    def test_handles_unknown_device(self, mqtt_sensor_service):
        """Should handle unknown Zigbee device gracefully"""
        # No friendly-name resolution available

        msg = _make_msg("zigbee2mqtt/unknown_device", {"temperature": 22.5})
        mqtt_sensor_service._on_message(None, None, msg)


class TestESP32MessageHandling:
    """Test ESP32 custom sensor message handling"""

    def test_handles_registered_esp32_message(
        self, mqtt_sensor_service, mock_sensor_manager, mock_processor, mock_emitter
    ):
        """Registered ESP32 payload should be processed and emitted."""
        sensor = Mock()
        sensor.id = 1
        sensor.unit_id = 1
        sensor.name = "ESP32 Temp Sensor"
        sensor.sensor_type = "environment_sensor"
        sensor.protocol = "esp32"
        mock_sensor_manager.get_sensor_entity.return_value = sensor

        reading = SimpleNamespace(
            sensor_id=1,
            unit_id=1,
            data={"temperature": 23.0},
            status=SimpleNamespace(value="success"),
            timestamp=SimpleNamespace(isoformat=lambda: "2026-01-02T00:00:00Z"),
            is_anomaly=False,
        )
        mock_processor.process.return_value = reading

        device_payload = DeviceSensorReadingPayload(
            sensor_id=1,
            unit_id=1,
            sensor_name="ESP32 Temp Sensor",
            sensor_type="environment_sensor",
            protocol="esp32",
            readings={"temperature": 23.0},
            units={"temperature": "°C"},
            status="success",
            timestamp="2026-01-02T00:00:00Z",
        )
        prepared = SimpleNamespace(unit_id=1, device_payload=device_payload, dashboard_payload=None)
        mock_processor.build_payloads.return_value = prepared

        # The service expects SYSGrow-style topics; simulate device state topic
        mock_sensor_manager.get_sensor_by_friendly_name.return_value = sensor
        msg = _make_msg("sysgrow/device_1", {"temperature": 23.0, "sensor_id": 1})
        mqtt_sensor_service._on_message(None, None, msg)

        mock_sensor_manager.get_sensor_by_friendly_name.assert_any_call("device_1")
        mock_processor.process.assert_called_once()
        mock_processor.build_payloads.assert_called_once()
        mock_emitter.emit_device_sensor_reading.assert_called_once()

    def test_handles_reload_request(self, mqtt_sensor_service, mock_processor, mock_emitter):
        """Should handle ESP32 reload request without crashing."""
        msg = Mock()
        msg.topic = "sysgrow/bridge/response/reload"
        msg.payload = b"{}"
        mqtt_sensor_service._on_message(None, None, msg)
        mock_processor.process.assert_not_called()
        mock_emitter.emit_device_sensor_reading.assert_not_called()

    def test_validates_unit_id_match(self, mqtt_sensor_service, mock_sensor_manager):
        """Should validate unit_id matches between topic and sensor"""
        sensor = Mock()
        sensor.id = 1
        sensor.unit_id = 2  # Different from topic
        mock_sensor_manager.get_sensor_entity.return_value = sensor

        mock_sensor_manager.get_sensor_by_friendly_name.return_value = sensor
        msg = _make_msg("sysgrow/device_1", {"temperature": 23.0, "sensor_id": 1})
        mqtt_sensor_service._on_message(None, None, msg)


class TestUnregisteredESP32:
    def test_emits_unregistered_payload_for_unknown_sensor(
        self, mqtt_sensor_service, mock_sensor_manager, mock_emitter
    ):
        mock_sensor_manager.get_sensor_entity.return_value = None

        # Simulate an unregistered sysgrow device state
        mock_sensor_manager.get_sensor_by_friendly_name.return_value = None
        msg = _make_msg("sysgrow/unknown_device", {"soil_moisture": 45})
        mqtt_sensor_service._on_message(None, None, msg)
        mock_emitter.emit_unregistered_sensor_data.assert_called_once()
