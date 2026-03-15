from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SYSGROW_SECRET_KEY", "test-secret")
    database_path = tmp_path / "test.db"
    app = create_app({"database_path": str(database_path)})
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def _create_unit(client) -> int:
    response = client.post("/api/growth/v2/units", json={"name": "Unit V2", "location": "Indoor"})
    assert response.status_code in (200, 201)
    data = response.get_json()
    # growth units endpoints return either bare unit or wrapped;
    # support both shapes.
    if isinstance(data, dict) and "unit_id" in data:
        return data["unit_id"]
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        created = data["data"]
        unit_id = created.get("unit_id") or created.get("id")
        if unit_id is not None:
            return unit_id
    pytest.fail(f"Unexpected response shape when creating unit: {data}")


def test_create_sensor_v2_happy_path(client):
    unit_id = _create_unit(client)

    payload = {
        "name": "EnvSensor v2",
        "type": "ENVIRONMENT",
        "model": "ENS160AHT21",
        "unit_id": unit_id,
        "gpio_pin": 18,
        "communication_type": "GPIO",
    }
    response = client.post("/api/devices/v2/sensors", json=payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body.get("ok") is True
    data = body.get("data") or {}
    assert isinstance(data.get("sensor_id"), int)
    assert "created successfully" in data.get("message", "")


def test_create_sensor_v2_validation_error(client):
    # Missing required fields (unit_id, model, type) should trigger validation.
    response = client.post(
        "/api/devices/v2/sensors",
        json={"name": "Broken Sensor"},
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body.get("ok") is False
    assert "Invalid sensor payload" in body.get("message", "")
    assert "errors" in (body.get("details") or {})


def test_create_actuator_v2_happy_path(client):
    unit_id = _create_unit(client)

    payload = {
        "name": "Irrigation Pump v2",
        "type": "WATER_PUMP",
        "unit_id": unit_id,
        "gpio_pin": 23,
    }
    response = client.post("/api/devices/v2/actuators", json=payload)
    assert response.status_code == 201
    body = response.get_json()
    assert body.get("ok") is True
    data = body.get("data") or {}
    assert isinstance(data.get("actuator_id"), int)
    assert "created successfully" in data.get("message", "")


def test_create_actuator_v2_validation_error(client):
    # Missing type and unit_id should fail validation.
    response = client.post(
        "/api/devices/v2/actuators",
        json={"name": "Broken Actuator"},
    )
    assert response.status_code == 400
    body = response.get_json()
    assert body.get("ok") is False
    assert "Invalid actuator payload" in body.get("message", "")
    assert "errors" in (body.get("details") or {})
