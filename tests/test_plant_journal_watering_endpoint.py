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


def _create_unit(app) -> int:
    with app.app_context():
        container = app.config["CONTAINER"]
        unit_id = container.growth_service.create_unit(
            name="Unit A",
            location="Indoor",
            user_id=1,
        )
    assert unit_id is not None
    return int(unit_id)


def _create_plant(client, unit_id: int) -> int:
    response = client.post(
        f"/api/plants/units/{unit_id}/plants",
        json={
            "name": "Basil",
            "plant_type": "herb",
            "current_stage": "Seedling",
        },
    )
    assert response.status_code == 201
    payload = response.get_json() or {}
    data = payload.get("data") or {}
    plant_id = data.get("plant_id")
    assert plant_id is not None
    return int(plant_id)


def test_journal_watering_endpoint_creates_entry(client, app):
    unit_id = _create_unit(app)
    plant_id = _create_plant(client, unit_id)

    response = client.post(
        "/api/plants/journal/watering",
        data={
            "plant_id": plant_id,
            "unit_id": unit_id,
            "amount": 125,
            "unit": "ml",
            "notes": "manual watering",
        },
    )

    assert response.status_code == 201
    payload = response.get_json() or {}
    assert payload.get("ok") is True
    data = payload.get("data") or {}
    entry_id = data.get("entry_id")
    assert entry_id is not None

    with app.app_context():
        repo = app.config["CONTAINER"].plant_journal_repo
        entries = repo.get_entries(plant_id=plant_id, entry_type="watering", limit=1)

    assert entries
    entry = entries[0]
    assert entry.get("entry_id") == entry_id
    assert entry.get("unit_id") == unit_id
    assert entry.get("entry_type") == "watering"
    assert entry.get("amount") == pytest.approx(125.0)
    assert entry.get("unit") == "ml"
