from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

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
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["user"] = "testuser"
        sess["user_id"] = 1
    return c


def test_growth_unit_lifecycle(client):
    # Create a growth unit (ensure API auth in session)
    # Create unit directly via service to avoid blueprint parameter mismatch
    with client.application.app_context():
        container = client.application.config["CONTAINER"]
        unit_id = container.growth_service.create_unit(name="Unit A", location="Indoor", user_id=1)
    assert unit_id is not None

    # List growth units
    response = client.get("/api/growth/v2/units")
    assert response.status_code == 200
    units_payload = response.get_json() or {}
    units = units_payload.get("data", [])
    assert any(unit.get("id") == unit_id for unit in units)

    # Add a plant to the unit
    response = client.post(
        f"/api/plants/units/{unit_id}/plants",
        json={"name": "Basil", "plant_type": "herb", "current_stage": "Seedling"},
    )
    assert response.status_code == 201
    plant_payload = response.get_json() or {}
    plant = plant_payload.get("data", {})
    assert plant["name"] == "Basil"

    # Fetch plants list
    response = client.get(f"/api/plants/units/{unit_id}/plants")
    assert response.status_code == 200
    plants_payload = response.get_json() or {}
    plants = plants_payload.get("data", {}).get("plants", [])
    assert any(p["plant_id"] == plant["plant_id"] for p in plants)

    # Update thresholds
    response = client.post(
        f"/api/growth/units/{unit_id}/thresholds",
        json={
            "temperature_threshold": 24.5,
            "humidity_threshold": 55.0,
        },
    )
    assert response.status_code == 200
    payload = response.get_json() or {}
    data = payload.get("data", {}) or {}
    assert pytest.approx(data["temperature_threshold"], rel=1e-3) == 24.5


def test_sensor_history_endpoint(app, client):
    with app.app_context():
        database = app.config["CONTAINER"].database
        now = datetime.now(UTC)
        earlier = now - timedelta(hours=1)

        with database.connection() as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info('SensorReading')")}
            conn.execute(
                """
                INSERT INTO Sensor (unit_id, name, sensor_type, protocol, model)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "EnvSensor", "environment_sensor", "GPIO", "mock"),
            )
            sensor_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            if "reading_data" in cols:
                payload_now = json.dumps(
                    {
                        "temperature": 22.0,
                        "humidity": 50.0,
                        "soil_moisture": 40.0,
                        "co2_ppm": 500.0,
                        "voc_ppb": 120.0,
                    }
                )
                payload_earlier = json.dumps(
                    {
                        "temperature": 21.5,
                        "humidity": 48.0,
                        "soil_moisture": 38.0,
                        "co2_ppm": 480.0,
                        "voc_ppb": 110.0,
                    }
                )
                conn.execute(
                    """
                    INSERT INTO SensorReading (sensor_id, timestamp, reading_data, quality_score)
                    VALUES (?, ?, ?, ?)
                    """,
                    (sensor_id, now.isoformat(sep=" "), payload_now, None),
                )
                conn.execute(
                    """
                    INSERT INTO SensorReading (sensor_id, timestamp, reading_data, quality_score)
                    VALUES (?, ?, ?, ?)
                    """,
                    (sensor_id, earlier.isoformat(sep=" "), payload_earlier, None),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO SensorReading (sensor_id, timestamp, temperature, humidity, soil_moisture, co2_ppm, voc_ppb)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sensor_id, now.isoformat(sep=" "), 22.0, 50.0, 40.0, 500.0, 120.0),
                )
                conn.execute(
                    """
                    INSERT INTO SensorReading (sensor_id, timestamp, temperature, humidity, soil_moisture, co2_ppm, voc_ppb)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (sensor_id, earlier.isoformat(sep=" "), 21.5, 48.0, 38.0, 480.0, 110.0),
                )

    response = client.get("/api/analytics/sensors/history")
    assert response.status_code == 200
    payload = response.get_json()
    data = payload.get("data") if isinstance(payload, dict) else payload
    # The API wraps chart data inside the envelope `data` -> `data`.
    chart = (data.get("data") or {}) if isinstance(data, dict) else {}
    assert len(chart.get("timestamps", [])) == 2
    assert chart.get("temperature", [None])[0] is not None


def test_status_endpoint(client):
    response = client.get("/api/v1/dashboard/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
