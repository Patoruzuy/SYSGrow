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


def test_recommended_thresholds_requires_plant_type(client):
    response = client.get("/api/growth/thresholds/recommended")
    assert response.status_code == 400
    payload = response.get_json()
    assert payload.get("ok") is False
    assert "plant_type is required" in payload.get("message", "")


def test_recommended_thresholds_happy_path(client, app):
    # This relies on the ThresholdService + PlantJsonHandler seed data.
    # We don't assert exact numeric values (since they may evolve),
    # only that the structure is present and values are numeric.
    response = client.get(
        "/api/growth/thresholds/recommended",
        query_string={"plant_type": "Tomatoes", "growth_stage": "Vegetative"},
    )
    assert response.status_code == 200
    payload = response.get_json()

    assert payload.get("ok") is True
    data = payload.get("data") or {}

    assert data.get("plant_type") == "Tomatoes"
    assert data.get("growth_stage") == "Vegetative"

    thresholds = data.get("thresholds") or {}
    for key in (
        "min_temp",
        "max_temp",
        "min_humidity",
        "max_humidity",
        "min_soil_moisture",
        "max_soil_moisture",
    ):
        assert key in thresholds
        # Values can be None if the underlying dataset is missing,
        # but when present they should be numeric.
        value = thresholds[key]
        if value is not None:
            assert isinstance(value, (int, float))

    # Raw map from ThresholdService should be included for advanced clients.
    raw = data.get("raw")
    assert isinstance(raw, dict)
