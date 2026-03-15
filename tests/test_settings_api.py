from __future__ import annotations

import pytest

from app import create_app


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SYSGROW_SECRET_KEY", "test-secret")
    database_path = tmp_path / "test.db"
    app = create_app({"database_path": str(database_path)})
    app.config["TESTING"] = True
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


def _create_unit(client) -> int:
    response = client.post("/api/growth/v2/units", json={"name": "Settings Unit", "location": "Indoor"})
    assert response.status_code in (200, 201)
    payload = response.get_json() or {}
    data = payload.get("data") or {}
    unit_id = data.get("unit_id") or data.get("id")
    assert unit_id is not None
    return unit_id


def test_plants_seeded(app):
    with app.app_context():
        database = app.config["CONTAINER"].database
        with database.connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM Plants").fetchone()[0]
    assert count > 0


def test_hotspot_settings_roundtrip(client):
    response = client.get("/api/settings/hotspot")
    assert response.status_code == 404

    payload = {"ssid": "GrowTent", "password": "secret123"}
    response = client.put("/api/settings/hotspot", json=payload)
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("ok") is True
    data = payload.get("data") or {}
    assert data["ssid"] == "GrowTent"
    assert data["password_present"] is True

    response = client.get("/api/settings/hotspot")
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("ok") is True
    stored = payload.get("data") or {}
    assert stored["ssid"] == "GrowTent"
    assert stored["password_present"] is True

    # Update SSID without changing password
    response = client.put("/api/settings/hotspot", json={"ssid": "GrowTent-2"})
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("ok") is True
    updated = payload.get("data") or {}
    assert updated["ssid"] == "GrowTent-2"
    assert updated["password_present"] is True


def test_camera_settings_roundtrip(client):
    payload = {
        "camera_type": "esp32",
        "ip_address": "192.168.1.10",
        "resolution": 10,
        "quality": 4,
        "brightness": 1,
        "contrast": 0,
        "saturation": 0,
        "flip": 0,
    }
    response = client.put("/api/settings/camera", json=payload)
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("ok") is True
    data = payload.get("data") or {}
    assert data["camera_type"] == "esp32"
    assert data["ip_address"] == "192.168.1.10"

    response = client.get("/api/settings/camera")
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("ok") is True
    stored = payload.get("data") or {}
    assert stored["camera_type"] == "esp32"


def test_device_schedule_roundtrip(client):
    """Test device schedules using the Growth API (replaces deprecated settings/light endpoint)."""
    unit_id = _create_unit(client)
    
    # Set light schedule via Growth API
    response = client.post(
        f"/api/growth/v2/units/{unit_id}/schedules",
        json={"device_type": "light", "start_time": "08:00", "end_time": "20:00", "enabled": True}
    )
    assert response.status_code == 200

    # Get all schedules
    response = client.get(f"/api/growth/v2/units/{unit_id}/schedules")
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("ok") is True
    data = payload.get("data") or {}
    schedules = data.get("device_schedules") or {}
    assert "light" in schedules
    assert schedules["light"]["start_time"] == "08:00"
    assert schedules["light"]["end_time"] == "20:00"


def test_environment_thresholds_validation(client):
    bad_response = client.put(
        "/api/settings/environment",
        json={"temperature_threshold": 24.0, "humidity_threshold": 55.0},
    )
    assert bad_response.status_code == 400

    good_response = client.put(
        "/api/settings/environment",
        json={
            "temperature_threshold": 24.5,
            "humidity_threshold": 55.0,
            "soil_moisture_threshold": 35.0,
        },
    )
    assert good_response.status_code == 200
    payload = good_response.get_json() or {}
    assert payload.get("ok") is True
    data = payload.get("data") or {}
    assert data["temperature_threshold"] == pytest.approx(24.5)
