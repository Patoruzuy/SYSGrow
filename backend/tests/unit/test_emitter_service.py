from datetime import datetime

from app.domain.sensors.reading import ReadingStatus, SensorReading
from app.utils.emitters import SOCKETIO_NAMESPACE_DEVICES, EmitterService


class FakeSocketIO:
    def __init__(self) -> None:
        self.emits: list[dict] = []

    def emit(self, event, payload, room=None, namespace="/"):
        self.emits.append(
            {
                "event": event,
                "payload": payload,
                "room": room,
                "namespace": namespace,
            }
        )


def test_emit_sensor_reading_filters_non_numeric_fields():
    sio = FakeSocketIO()
    emitter = EmitterService(sio=sio, replay_maxlen=10)

    reading = SensorReading(
        sensor_id=12,
        unit_id=1,
        sensor_type="environment_sensor",
        sensor_name="Environment_sensor",
        data={
            "temperature": 14.3,
            "humidity": 74,
            "temperature_unit": "celsius",
            "linkquality": 172,
        },
        timestamp=datetime.now(),
        status=ReadingStatus.SUCCESS,
    )

    emitter.emit_sensor_reading(sensor_id=12, reading=reading, namespace=SOCKETIO_NAMESPACE_DEVICES)

    sensor_reading_event = next(e for e in sio.emits if e["event"] == "device_sensor_reading")
    assert sensor_reading_event["room"] == "unit_1"
    assert sensor_reading_event["payload"]["readings"]["temperature"] == 14.3
    assert sensor_reading_event["payload"]["readings"]["humidity"] == 74.0
    assert sensor_reading_event["payload"]["readings"]["linkquality"] == 172.0
    assert "temperature_unit" not in sensor_reading_event["payload"]["readings"]

    emitted_events = {e["event"] for e in sio.emits}
    assert "device_sensor_reading" in emitted_events
