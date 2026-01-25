"""
Comprehensive test for the Devices API
=====================================

Smoke-checks the key v2 endpoints after backward-compatibility removal.
"""

from __future__ import annotations

from app import create_app


def _safe_json(response) -> dict:
    payload = response.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def test_devices_api():
    app = create_app()

    with app.test_client() as client:
        for path in (
            "/api/devices/config/gpio_pins",
            "/api/devices/config/adc_channels",
            "/api/devices/config/sensor_types",
            "/api/devices/config/actuator_types",
            "/api/growth/v2/units",
            "/api/devices/v2/sensors",
            "/api/devices/v2/actuators",
        ):
            response = client.get(path)
            assert response.status_code == 200

            payload = _safe_json(response)
            assert payload.get("ok") is True

