import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.hardware.mqtt.mqtt_broker_wrapper import MQTTClientWrapper
from app.services.application.zigbee_management_service import (
    ZigbeeManagementService,
)

# Topic constants
ZIGBEE_DEVICES_TOPIC = "zigbee2mqtt/bridge/devices"
ZIGBEE_RENAME_RESPONSE_PREFIX = "zigbee2mqtt/bridge/response/device/rename"


class DummyMessage:
    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload


class DummyClient:
    def __init__(self):
        self.on_message = None
        self.subscriptions = []

    def connect(self, *_args, **_kwargs):
        return 0

    def loop_start(self):
        return None

    def disconnect(self):
        return None

    def loop_stop(self):
        return None

    def subscribe(self, topic):
        self.subscriptions.append(topic)
        return (0, len(self.subscriptions))

    def publish(self, topic, payload):
        return SimpleNamespace(rc=0, topic=topic, payload=payload)


def build_wrapper(dummy_client: DummyClient) -> MQTTClientWrapper:
    with patch(
        "app.hardware.mqtt.mqtt_broker_wrapper.create_mqtt_client",
        return_value=dummy_client,
    ):
        wrapper = MQTTClientWrapper(broker="test", port=1883)
    return wrapper


def test_wrapper_fans_out_callbacks_without_overwrite():
    dummy_client = DummyClient()
    wrapper = build_wrapper(dummy_client)
    events = []

    def zigbee_cb(_client, _userdata, msg):
        events.append(("zigbee", msg.topic, msg.payload))

    def growtent_cb(_client, _userdata, msg):
        events.append(("growtent", msg.topic))

    wrapper.subscribe("zigbee2mqtt/+", zigbee_cb)
    wrapper.subscribe("growtent/+/sensor/+", growtent_cb)

    wrapper._dispatch_message(wrapper.client, None, DummyMessage("zigbee2mqtt/device1", b'{"temp":1}'))
    wrapper._dispatch_message(
        wrapper.client, None, DummyMessage("growtent/1/sensor/soil_moisture", b'{"soil_moisture":55}')
    )

    assert ("zigbee", "zigbee2mqtt/device1", b'{"temp":1}') in events
    assert ("growtent", "growtent/1/sensor/soil_moisture") in events


def test_zigbee_service_uses_wrapper_and_preserves_existing_callbacks():
    dummy_client = DummyClient()
    wrapper = build_wrapper(dummy_client)

    poller_hits = []

    def poller_cb(_client, _userdata, msg):
        poller_hits.append(msg.topic)

    wrapper.subscribe("zigbee2mqtt/+", poller_cb)
    service = ZigbeeManagementService(mqtt_client=wrapper)

    assert ZIGBEE_DEVICES_TOPIC in dummy_client.subscriptions
    assert any(sub.startswith(ZIGBEE_RENAME_RESPONSE_PREFIX) for sub in dummy_client.subscriptions)
    assert wrapper.client.on_message == wrapper._dispatch_message

    wrapper._dispatch_message(wrapper.client, None, DummyMessage(ZIGBEE_DEVICES_TOPIC, b"[]"))
    assert service._devices_event.is_set()

    wrapper._dispatch_message(wrapper.client, None, DummyMessage("zigbee2mqtt/leaf", b'{"temperature":22}'))
    assert "zigbee2mqtt/leaf" in poller_hits
