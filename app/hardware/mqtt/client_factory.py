"""
Helpers for constructing MQTT clients that work across paho-mqtt 1.x and 2.x.

The 2.x releases add a callback API version flag; we prefer the legacy
v3.1.1 callback signature for existing handlers while remaining compatible
with older installations that do not expose the enum.
"""
from __future__ import annotations

from typing import Any, Dict

import paho.mqtt.client as mqtt


def create_mqtt_client(client_id: str = "", **kwargs: Any) -> mqtt.Client:
    """
    Build an MQTT client that is forward-compatible with paho-mqtt 2.x and
    gracefully degrades when running with 1.x.

    Args:
        client_id: Optional client identifier.
        kwargs: Extra keyword arguments forwarded to the client constructor.
    """
    client_kwargs: Dict[str, Any] = {"client_id": client_id or ""}

    # Keep MQTT v3.1.1 protocol by default for broker compatibility.
    client_kwargs["protocol"] = kwargs.pop("protocol", getattr(mqtt, "MQTTv311", 4))
    client_kwargs.update(kwargs)

    callback_api_version = getattr(mqtt, "CallbackAPIVersion", None)
    if callback_api_version:
        # Favor the legacy callback signature (v3.1.1) so existing handlers
        # with (client, userdata, msg) continue to work under paho 2.x.
        api_candidates = ("V311", "v311", "VERSION1", "V1")
        callback_value = next(
            (getattr(callback_api_version, attr) for attr in api_candidates if hasattr(callback_api_version, attr)),
            None,
        )
        if callback_value is None:
            try:
                callback_value = callback_api_version(4)  # IntEnum in paho 2.x
            except Exception:
                callback_value = 4
        client_kwargs["callback_api_version"] = callback_value

    try:
        return mqtt.Client(**client_kwargs)
    except TypeError:
        # Older paho versions do not support callback_api_version; retry with basics.
        client_kwargs.pop("callback_api_version", None)
        return mqtt.Client(**client_kwargs)
