from __future__ import annotations

import json
from datetime import datetime, timedelta

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


def test_efficiency_score_filters_anomalies_and_includes_grade_trend(app, client):
    with app.app_context():
        database = app.config["CONTAINER"].database
        now = datetime.utcnow()

        with database.connection() as conn:
            conn.execute(
                """
                INSERT INTO Sensor (unit_id, name, sensor_type, protocol, model)
                VALUES (?, ?, ?, ?, ?)
                """,
                (1, "EnvSensor", "environment_sensor", "GPIO", "mock"),
            )
            sensor_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            cols = {row[1] for row in conn.execute("PRAGMA table_info('SensorReading')")}
            if "reading_data" not in cols:
                pytest.skip("SensorReading schema missing reading_data payload column")

            reading_payload = json.dumps(
                {
                    "temperature": 22.0,
                    "humidity": 50.0,
                    "soil_moisture": 40.0,
                    "co2_ppm": 500.0,
                    "voc_ppb": 120.0,
                }
            )

            for hours_ago in (1, 2, 3, 4):
                conn.execute(
                    """
                    INSERT INTO SensorReading (sensor_id, timestamp, reading_data, quality_score)
                    VALUES (?, ?, ?, ?)
                    """,
                    (sensor_id, (now - timedelta(hours=hours_ago)).isoformat(), reading_payload, 1.0),
                )

            for days_ago in (8, 9, 10, 11):
                conn.execute(
                    """
                    INSERT INTO SensorReading (sensor_id, timestamp, reading_data, quality_score)
                    VALUES (?, ?, ?, ?)
                    """,
                    (sensor_id, (now - timedelta(days=days_ago)).isoformat(), reading_payload, 1.0),
                )

            conn.execute(
                """
                INSERT INTO SensorAnomaly (sensor_id, value, mean_value, std_deviation, z_score, detected_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    sensor_id,
                    30.0,
                    22.0,
                    1.0,
                    8.0,
                    (now - timedelta(days=9)).isoformat(sep=" "),
                ),
            )
            conn.execute(
                """
                INSERT INTO SensorAnomaly (sensor_id, value, mean_value, std_deviation, z_score, detected_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    sensor_id,
                    30.0,
                    22.0,
                    1.0,
                    8.0,
                    (now - timedelta(hours=12)).isoformat(sep=" "),
                ),
            )

    response = client.get("/api/analytics/efficiency-score?unit_id=1")
    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("ok") is True

    data = payload.get("data") or {}
    assert data.get("grade") in {"A+", "A", "B+", "B", "C", "D", "F"}
    assert data.get("trend") in {"improving", "stable", "declining"}

    components = data.get("components") or {}
    assert components.get("environmental") == pytest.approx(98.0, abs=0.2)

