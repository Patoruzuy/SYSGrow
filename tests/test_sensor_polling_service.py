from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from app.domain.sensors.reading import ReadingStatus, SensorReading
from app.services.hardware.sensor_polling_service import SensorPollingService


class StubProcessor:
    def validate(self, raw_data):
        return raw_data

    def apply_calibration(self, data, calibration):
        return data

    def transform(self, validated_data, sensor):
        return SensorReading(
            sensor_id=int(sensor.id),
            unit_id=int(sensor.unit_id),
            sensor_type=str(getattr(getattr(sensor, "sensor_type", None), "value", "unknown")),
            sensor_name=str(getattr(sensor, "name", f"Sensor {sensor.id}")),
            data=dict(validated_data),
            timestamp=datetime.utcnow(),
            status=ReadingStatus.SUCCESS,
        )

    def enrich(self, reading):
        return reading

    def build_payloads(self, *, sensor, reading):
        # Minimal stub matching CompositeProcessor.build_payloads return shape.
        # We only assert the emitter methods are called, not payload content.
        return SimpleNamespace(
            device_payload={"unit_id": reading.unit_id}, dashboard_payload={"unit_id": reading.unit_id}
        )


class StubSensorManager:
    def __init__(self, *, sensors, sensor_entities, read_fn):
        self._sensors = sensors
        self._sensor_entities = sensor_entities
        self._read_fn = read_fn
        self.read_calls = 0

    def get_all_sensors(self):
        return list(self._sensors)

    def get_sensor(self, sensor_id):
        return self._sensor_entities.get(sensor_id)

    def read_sensor(self, sensor_id):
        self.read_calls += 1
        return self._read_fn(sensor_id)


def test_start_polling_skips_when_no_gpio_sensors():
    emitter = Mock()
    sensor_manager = StubSensorManager(sensors=[], sensor_entities={}, read_fn=lambda _sid: None)
    polling = SensorPollingService(
        sensor_manager=sensor_manager,
        emitter=emitter,
        processor=StubProcessor(),
        poll_interval_s=1,
    )

    started = polling.start_polling()

    assert started is False
    assert polling._is_running is False


def test_gpio_polling_enters_backoff_on_failure():
    protocol_gpio = SimpleNamespace(value="GPIO")
    sensor_stub = SimpleNamespace(id=1, protocol=protocol_gpio)
    sensor_entity = SimpleNamespace(id=1, unit_id=1, name="Test Sensor", _calibration=None)

    def fail_first_read(_sid):
        raise ValueError("failed read")

    manager = StubSensorManager(
        sensors=[sensor_stub],
        sensor_entities={1: sensor_entity},
        read_fn=fail_first_read,
    )
    emitter = Mock()
    polling = SensorPollingService(
        sensor_manager=manager,
        emitter=emitter,
        processor=StubProcessor(),
        poll_interval_s=1,
    )
    polling.base_backoff_s = 0.2
    polling.max_backoff_s = 0.5

    polling._process_single_sensor(1)
    polling._process_single_sensor(1)

    assert manager.read_calls == 1  # Backoff prevented immediate retry
    health = polling._health.get(1)
    assert health is not None
    assert health.backoff_until is not None


def test_emit_sensor_reading_emits_unit_scoped_namespaces():
    emitter = Mock()
    sensor_manager = StubSensorManager(sensors=[], sensor_entities={}, read_fn=lambda _sid: None)
    polling = SensorPollingService(
        sensor_manager=sensor_manager,
        emitter=emitter,
        processor=StubProcessor(),
        poll_interval_s=1,
    )

    prepared = SimpleNamespace(
        device_payload={"unit_id": 1},
        dashboard_payload={"unit_id": 1},
        controller_events=[],
    )
    polling._dispatch_results(prepared)

    emitter.emit_device_sensor_reading.assert_called_once()
    emitter.emit_dashboard_snapshot.assert_called_once()
    emitter.emit_sensor_reading.assert_not_called()
