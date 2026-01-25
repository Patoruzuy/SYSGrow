import paho.mqtt.client as mqtt

from app.hardware.mqtt.client_factory import create_mqtt_client


def test_create_mqtt_client_handles_available_version_flags():
    client = create_mqtt_client("factory-test")

    assert getattr(client, "_client_id", b"").decode() == "factory-test"
    assert getattr(client, "_protocol", None) in (4, getattr(mqtt, "MQTTv311", 4))
    assert hasattr(client, "connect")
